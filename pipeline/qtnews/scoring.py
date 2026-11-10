"""Оценка важности сюжетов: эвристика + оценка редактора-ИИ."""
from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timezone

from . import db as dbm
from .db import Database, Item, Story
from .llm import LLM, LLMError, complete_json

log = logging.getLogger(__name__)

# Рекламные и «купонные» публикации (промокоды, распродажи, подборки скидок) — не новости
JUNK_TITLE = re.compile(
    r"(promo ?codes?|coupons?|discount codes?|\d+% off|\$\d+ off|best .* deals|deals? of the|on sale|black friday|"
    r"cyber monday|referral deals|gift guide|best tv shows to stream)",
    re.I,
)

HEURISTIC_WEIGHT = 0.4
LLM_WEIGHT = 0.6
FRESHNESS_HALF_LIFE_H = 12


def heuristic_score(items: list[Item], now: datetime | None = None) -> float:
    """0..10: охват (сколько разных источников), их авторитетность и свежесть."""
    if not items:
        return 0.0
    now = now or datetime.now(timezone.utc)
    by_source: dict[str, float] = {}
    for it in items:
        by_source[it.source_id] = max(by_source.get(it.source_id, 0), it.source_weight)
    coverage = min(1.0, math.log1p(len(by_source)) / math.log1p(8))        # 8+ источников = максимум
    authority = min(1.0, max(by_source.values()) / 10 * 0.6 + sum(by_source.values()) / 40 * 0.4)
    newest = max(datetime.fromisoformat(i.published_at) for i in items)
    age_h = max(0.0, (now - newest).total_seconds() / 3600)
    freshness = 0.5 ** (age_h / FRESHNESS_HALF_LIFE_H)
    return round(10 * (0.45 * coverage + 0.35 * authority + 0.20 * freshness), 2)


_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "security": ("hack", "vulnerab", "breach", "ransomware", "exploit", "malware", "cyber", "zero-day", "phishing",
                 "spyware", "leak"),
    "ai": (" ai ", "ai-", "openai", "chatgpt", "llm", "anthropic", "claude", "gemini", "deepmind", "copilot",
           "artificial intelligence", "machine learning", "neural", "model", "agent"),
    "startups": ("raises", "funding", "series a", "series b", "series c", "valuation", "startup", "venture",
                 "seed round", "unicorn", "acquire", "acquisition", "ipo"),
    "policy": ("regulat", "antitrust", "lawsuit", "ftc", "doj", "european commission", "eu ", "ban ", "congress",
               "senate", "court", "fine", "tariff", "export control", "law"),
    "gadgets": ("iphone", "pixel", "galaxy", "laptop", "macbook", "smartwatch", "watch", "headphones", "airpods",
                "tablet", "ipad", "console", "camera", "vision pro", "foldable"),
    "dev": ("developer", "github", "programming", "python", "javascript", "typescript", "rust", "api", "open source",
            "open-source", "linux", "kubernetes", "framework", "sdk"),
    "science": ("space", "nasa", "spacex", "rocket", "satellite", "quantum", "physics", "research", "scientists",
                "climate", "fusion"),
    "big-tech": ("apple", "google", "microsoft", "meta", "amazon", "nvidia", "tesla", "samsung", "alphabet", "tsmc"),
}


def guess_category(items: list[Item], allowed: set[str]) -> str | None:
    """Грубая рубрикация по ключевым словам — используется, если ИИ не подключён или ошибся."""
    text = " " + " ".join(f"{i.title} {i.summary[:300]}" for i in items).lower() + " "
    best, best_hits = None, 0
    for slug, words in _CATEGORY_KEYWORDS.items():
        if slug not in allowed:
            continue
        hits = sum(text.count(w) for w in words)
        if hits > best_hits:
            best, best_hits = slug, hits
    return best


SCORER_SYSTEM = """Сен — халықаралық технологиялық басылымның бас редакторысың.
Your job: rank technology news stories for a Kazakh-language tech news portal.
Audience: IT specialists, students, entrepreneurs and tech-curious readers in Kazakhstan and Central Asia.
Prefer: major industry moves, AI, big-tech strategy, security incidents, important launches, research breakthroughs,
regulation, anything relevant to Kazakhstan/Central Asia. Penalize: deals/coupons, minor rumours, sponsored content,
listicles, reviews of niche products, celebrity gossip, near-duplicates of each other.
Answer ONLY with JSON."""


def build_scoring_prompt(batch: list[tuple[Story, list[Item]]], categories: list[dict], extra_guidance: str) -> str:
    cats = ", ".join(f'{c["slug"]} ({c["name"]})' for c in categories) or "general"
    lines = []
    for story, items in batch:
        sources = sorted({i.source_name for i in items})
        heads = " | ".join(dict.fromkeys(i.title for i in items[:5]))
        lines.append(f'- id={story.id}; sources({len(sources)}): {", ".join(sources)}; headlines: {heads}')
    return (
        f"Editorial guidance from the editor-in-chief:\n{extra_guidance or '(none)'}\n\n"
        f"Allowed category slugs: {cats}\n\n"
        "Stories:\n" + "\n".join(lines) + "\n\n"
        'Return JSON: {"stories": [{"id": <int>, "score": <0-10 number, how important and interesting for our '
        'audience>, "category": "<one allowed slug>", "reason": "<max 15 words, English>"}]}'
    )


def score_stories(db: Database, llm: LLM | None, model: str, since: str, categories: list[dict],
                  guidance: str = "", batch_size: int = 25) -> dict[str, int]:
    stories = db.stories_by_status([dbm.NEW], since)
    if not stories:
        return {"scored": 0}
    pairs = [(s, db.items_for_story(s.id)) for s in stories]
    allowed = {c["slug"] for c in categories}

    junk = {s.id for s, items in pairs if items and all(JUNK_TITLE.search(i.title) for i in items)}
    with db.tx():
        for s, items in pairs:
            if s.id in junk:
                db.update_story(s.id, status=dbm.SKIPPED, score_reason="promo/deals")
                continue
            h = heuristic_score(items)
            db.update_story(s.id, heuristic_score=h, final_score=h, status=dbm.SCORED,
                            category=guess_category(items, allowed))
    pairs = [(s, items) for s, items in pairs if s.id not in junk]

    llm_scored = 0
    if llm is not None:
        for start in range(0, len(pairs), batch_size):
            batch = pairs[start:start + batch_size]
            try:
                data = complete_json(llm, model=model, system=SCORER_SYSTEM, max_tokens=3000, temperature=0.2,
                                     prompt=build_scoring_prompt(batch, categories, guidance))
            except LLMError as exc:
                log.error("Оценка LLM не удалась, используем эвристику: %s", exc)
                continue
            heur = {s.id: heuristic_score(items) for s, items in batch}
            with db.tx():
                for row in data.get("stories", []) if isinstance(data, dict) else []:
                    sid = int(row.get("id", -1))
                    if sid not in heur:
                        continue
                    llm_score = max(0.0, min(10.0, float(row.get("score", 0))))
                    final = round(HEURISTIC_WEIGHT * heur[sid] + LLM_WEIGHT * llm_score, 2)
                    fields = {"llm_score": llm_score, "final_score": final,
                              "score_reason": str(row.get("reason", ""))[:300]}
                    if row.get("category") in allowed:
                        fields["category"] = row["category"]
                    db.update_story(sid, **fields)
                    llm_scored += 1
    return {"scored": len(pairs), "llm_scored": llm_scored, "skipped_junk": len(junk)}
