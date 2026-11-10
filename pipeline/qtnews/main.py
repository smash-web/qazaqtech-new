"""Точка входа конвейера.

    python -m qtnews.main init-db     — создать таблицы
    python -m qtnews.main collect     — собрать ленты источников
    python -m qtnews.main process     — сгруппировать, оценить, отобрать, написать и опубликовать
    python -m qtnews.main run         — бесконечный цикл по расписанию (для Docker)
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import logging
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from . import db as dbm
from .cluster import cluster_new_items
from .cms import CMSClient, CMSError
from .config import Config, load
from .db import Database
from .feeds import Fetcher
from .lexical import markdown_to_lexical
from .llm import AnthropicClient, GeminiClient, LLM, LLMError
from .scoring import score_stories
from .selection import select_for_run
from .slug import slugify
from .writer import materials_from_items, untranslated_draft, write_article

log = logging.getLogger("qtnews")


def _since(hours: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).replace(microsecond=0).isoformat()


# --- этап 1: сбор ---------------------------------------------------------------------------------
def collect(cfg: Config, db: Database, cms: CMSClient, fetcher: Fetcher) -> dict:
    stats = {"sources": 0, "fetched": 0, "added": 0, "errors": 0}
    cutoff = _since(cfg.story_window_hours)
    sources = [s for s in cms.sources() if s.get("feedUrl")]
    stats["sources"] = len(sources)

    def fetch(src: dict):
        try:
            return src, fetcher.fetch_feed(src["feedUrl"]), None
        except Exception as exc:  # noqa: BLE001 — один упавший источник не должен ронять сбор
            return src, [], exc

    # Ленты качаем параллельно (сеть — узкое место), пишем в БД последовательно
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(fetch, sources))
    stats["failed_sources"] = []
    for src, entries, exc in results:
        if exc is not None:
            stats["errors"] += 1
            stats["failed_sources"].append(src.get("name"))
            log.warning("Источник %s недоступен: %s", src.get("name"), exc)
            continue
        with db.tx():
            for e in entries:
                stats["fetched"] += 1
                if e.published_at < cutoff:
                    continue
                if db.add_item(source_id=str(src["id"]), source_name=src.get("name", ""),
                               source_weight=float(src.get("weight") or 5), url=e.url, title=e.title,
                               summary=e.summary, published_at=e.published_at):
                    stats["added"] += 1
    db.log_run("collect", stats)
    log.info("Сбор: %s", stats)
    return stats


# --- этап 2: обработка ----------------------------------------------------------------------------
def process(cfg: Config, db: Database, cms: CMSClient, llm: LLM | None, fetcher: Fetcher | None) -> dict:
    settings = cms.settings()
    if not settings.pipeline_enabled:
        log.info("Конвейер выключен в админке")
        return {"disabled": True}
    since = _since(cfg.story_window_hours)
    categories = cms.categories()
    stats: dict = {}
    stats["cluster"] = cluster_new_items(db, since, cfg.cluster_threshold)
    stats["score"] = score_stories(db, llm, cfg.scorer_model, since, categories, settings.selection_guidance)

    chosen = select_for_run(
        db, quota=settings.daily_quota, min_score=settings.min_score, max_per_run=cfg.max_articles_per_run,
        tz=cfg.timezone, interval_min=cfg.process_interval_min, window_hours=cfg.story_window_hours,
        publish_from=settings.publish_from_hour, publish_to=settings.publish_to_hour,
    )
    stats["selected"] = len(chosen)
    if not chosen:
        db.log_run("process", stats)
        return stats

    glossary = cms.glossary()
    cat_ids = {c["slug"]: c["id"] for c in categories}
    published = review = failed = 0
    for story in chosen:
        try:
            if cms.find_article_by_story(story.id):  # идемпотентность при повторном запуске
                with db.tx():
                    db.update_story(story.id, status=dbm.PUBLISHED)
                continue
            materials = materials_from_items(db.items_for_story(story.id))
            if fetcher and cfg.fetch_full_text:
                for m in materials[:3]:
                    m.full_text = fetcher.fetch_article_text(m.url)
            if llm is None:
                # Режим без ИИ: черновик с исходными материалами уходит редактору на перевод/модерацию
                draft = untranslated_draft(materials, story.category)
                go_live = False
            else:
                draft = write_article(llm, cfg.writer_model, materials, glossary=glossary, categories=categories,
                                      style_guide=settings.style_guide, suggested_category=story.category,
                                      qa_model=cfg.qa_model or None)
                go_live = settings.auto_publish and draft.qa_ok
            slug = slugify(draft.title)
            if cms.slug_exists(slug):
                slug = f"{slug}-{story.id}"
            doc = cms.create_article({
                "title": draft.title,
                "slug": slug,
                "excerpt": draft.excerpt,
                "content": markdown_to_lexical(draft.body_markdown),
                "category": cat_ids.get(draft.category or ""),
                "tags": [{"tag": t} for t in draft.tags],
                "sources": draft.sources,
                "status": "published" if go_live else "review",
                "publishedAt": datetime.now(timezone.utc).isoformat() if go_live else None,
                "aiGenerated": llm is not None,
                "needsTranslation": llm is None,
                "importanceScore": story.final_score,
                "pipelineStoryId": story.id,
                "qaNotes": "\n".join(draft.qa_issues),
                "meta": {"title": draft.seo_title, "description": draft.seo_description},
            })
            with db.tx():
                db.update_story(story.id, status=dbm.PUBLISHED if go_live else dbm.IN_REVIEW,
                                article_id=str(doc.get("id")), error=None)
            published += go_live
            review += not go_live
            log.info("Статья %s: %s (%s)", "опубликована" if go_live else "на модерации", draft.title, doc.get("id"))
        except (LLMError, CMSError) as exc:
            failed += 1
            log.error("Сюжет %s не обработан: %s", story.id, exc)
            with db.tx():
                db.update_story(story.id, status=dbm.FAILED, error=str(exc)[:1000], attempts=story.attempts + 1)
    stats.update({"published": published, "review": review, "failed": failed})
    db.log_run("process", stats)
    log.info("Обработка: %s", stats)
    return stats


# --- запуск ---------------------------------------------------------------------------------------
def make_llm(cfg: Config) -> tuple[LLM | None, Config]:
    """Выбор ИИ-провайдера: Claude (если есть ключ), иначе бесплатный Gemini, иначе режим без ИИ."""
    if cfg.anthropic_api_key:
        return AnthropicClient(cfg.anthropic_api_key, cfg.anthropic_base_url), cfg
    if cfg.gemini_api_key:
        log.info("ИИ-провайдер: Google Gemini (%s / %s / %s)", cfg.gemini_writer_model, cfg.gemini_qa_model,
                 cfg.gemini_scorer_model)
        return GeminiClient(cfg.gemini_api_key), replace(
            cfg, writer_model=cfg.gemini_writer_model, qa_model=cfg.gemini_qa_model,
            scorer_model=cfg.gemini_scorer_model)
    log.warning("Нет ключа ИИ — режим без ИИ: черновики с исходниками уходят на модерацию")
    return None, cfg


def build(cfg: Config) -> tuple[Database, CMSClient, LLM | None, Fetcher]:
    """Внимание: модели выбранного провайдера возвращаются через cfg — используйте build_with_cfg."""
    db, cms, llm, fetcher, _ = build_with_cfg(cfg)
    return db, cms, llm, fetcher


def build_with_cfg(cfg: Config) -> tuple[Database, CMSClient, LLM | None, Fetcher, Config]:
    db = Database(cfg.database_url)
    db.init_schema()
    cms = CMSClient(cfg.cms_url, cfg.cms_api_key, cfg.cms_user_collection)
    llm, cfg = make_llm(cfg)
    return db, cms, llm, Fetcher(cfg.user_agent), cfg


def run_forever(cfg: Config) -> None:
    db, cms, llm, fetcher, cfg = build_with_cfg(cfg)
    stop = {"flag": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.update(flag=True))
    next_collect = next_process = 0.0
    while not stop["flag"]:
        now = time.monotonic()
        try:
            if now >= next_collect:
                collect(cfg, db, cms, fetcher)
                next_collect = now + cfg.collect_interval_min * 60
            if now >= next_process:
                process(cfg, db, cms, llm, fetcher)
                next_process = now + cfg.process_interval_min * 60
        except Exception:  # noqa: BLE001 — воркер не должен падать; ошибка уходит в лог
            log.exception("Ошибка цикла конвейера")
            next_collect = max(next_collect, now + 300)
            next_process = max(next_process, now + 300)
        time.sleep(15)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="qtnews")
    parser.add_argument("command", choices=["init-db", "collect", "process", "run"])
    args = parser.parse_args(argv)
    cfg = load()
    if args.command == "run":
        run_forever(cfg)
        return 0
    db, cms, llm, fetcher, cfg = build_with_cfg(cfg)
    if args.command == "collect":
        collect(cfg, db, cms, fetcher)
    elif args.command == "process":
        process(cfg, db, cms, llm, fetcher)
    return 0


if __name__ == "__main__":
    sys.exit(main())
