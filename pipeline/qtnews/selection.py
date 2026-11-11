"""Отбор сюжетов для публикации с учётом дневной квоты и равномерности в течение дня."""
from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from . import db as dbm
from .db import Database, Story


def day_start_utc(tz: str, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(ZoneInfo(tz))
    start = datetime.combine(local.date(), time(0), tzinfo=ZoneInfo(tz))
    return start.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def slots_for_this_run(*, quota: int, done_today: int, max_per_run: int, tz: str, interval_min: int,
                       publish_from: int = 7, publish_to: int = 23, now: datetime | None = None) -> int:
    """Сколько статей выпустить в этот запуск, чтобы квота распределилась по дню."""
    remaining = quota - done_today
    if remaining <= 0:
        return 0
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(ZoneInfo(tz))
    if not (publish_from <= local.hour < publish_to):
        return 0
    end = datetime.combine(local.date(), time(0), tzinfo=ZoneInfo(tz)) + timedelta(hours=publish_to)
    minutes_left = max(0.0, (end - local).total_seconds() / 60)
    runs_left = max(1, math.floor(minutes_left / max(1, interval_min)))
    return max(0, min(max_per_run, remaining, math.ceil(remaining / runs_left)))


# Компании и их «маркеры»: по ним определяем, о ком сюжет, чтобы лента не превращалась в ленту одной компании.
TOPICS: dict[str, tuple[str, ...]] = {
    "anthropic": ("anthropic", "claude"),
    "openai": ("openai", "chatgpt", "sam altman", "altman"),
    "nvidia": ("nvidia", "jensen huang", "huang"),
    "apple": ("apple", "iphone", "ipad", "macbook", "ios", "macos", "tim cook", "airpods", "vision pro"),
    "google": ("google", "alphabet", "deepmind", "gemini", "android", "pixel", "youtube", "waymo"),
    "microsoft": ("microsoft", "windows", "copilot", "azure", "xbox", "nadella"),
    "meta": ("meta", "facebook", "instagram", "whatsapp", "zuckerberg"),
    "amazon": ("amazon", "aws", "alexa", "bezos"),
    "musk": ("tesla", "spacex", "xai", "grok", "starlink", "musk", "neuralink"),
    "samsung": ("samsung", "galaxy"),
    "tsmc": ("tsmc",), "intel": ("intel",), "amd": ("amd",), "softbank": ("softbank",),
    "huawei": ("huawei",), "xiaomi": ("xiaomi",), "bytedance": ("bytedance", "tiktok"),
    "netflix": ("netflix",), "uber": ("uber",), "sony": ("sony", "playstation"), "nintendo": ("nintendo",),
}
_TOPIC_RE = {t: re.compile(r"\b(" + "|".join(re.escape(a) for a in al) + r")\b", re.I) for t, al in TOPICS.items()}


def topics_of(title: str) -> set[str]:
    return {t for t, rx in _TOPIC_RE.items() if rx.search(title or "")}


def pick(stories: list[Story], n: int, min_score: float, *, recent: list[Story] | None = None,
         max_per_topic: int = 2, topic_penalty: float = 1.0, category_penalty: float = 0.25) -> list[Story]:
    """Лучшие по оценке с поправкой на разнообразие.

    recent — сюжеты, вышедшие за последние сутки. Правила:
      * об одной компании — не больше max_per_topic статей в сутки (сверх лимита — только если больше нечего);
      * каждая уже вышедшая статья о той же компании снижает оценку на topic_penalty,
        каждая статья той же рубрики — на category_penalty (не больше 1.5);
      * за один запуск — не больше одного сюжета на рубрику, если есть альтернатива.
    """
    topic_n: Counter[str] = Counter()
    cat_n: Counter[str | None] = Counter()
    for r in recent or []:
        topic_n.update(topics_of(r.title))
        cat_n[r.category] += 1
    pool = [s for s in stories if s.final_score >= min_score]
    chosen: list[Story] = []
    run_cats: set[str | None] = set()

    def capped(s: Story) -> bool:
        return any(topic_n[t] >= max_per_topic for t in topics_of(s.title))

    def effective(s: Story) -> float:
        t_pen = topic_penalty * max((topic_n[t] for t in topics_of(s.title)), default=0)
        c_pen = min(1.5, category_penalty * cat_n[s.category]) if s.category is not None else 0.0
        return s.final_score - t_pen - c_pen

    while len(chosen) < n and pool:
        tiers = (
            [s for s in pool if not capped(s) and (s.category is None or s.category not in run_cats)],
            [s for s in pool if not capped(s)],
            pool,  # все оставшиеся сверх лимита по компании — берём, только если иначе пусто
        )
        tier = next(t for t in tiers if t)
        best = max(tier, key=effective)  # при равенстве — первый, т.е. с большей исходной оценкой
        pool.remove(best)
        chosen.append(best)
        run_cats.add(best.category)
        topic_n.update(topics_of(best.title))
        cat_n[best.category] += 1
    return chosen


def select_for_run(db: Database, *, quota: int, min_score: float, max_per_run: int, tz: str, interval_min: int,
                   window_hours: int, publish_from: int = 7, publish_to: int = 23,
                   now: datetime | None = None, spare: int = 0) -> tuple[list[Story], int]:
    """Возвращает (кандидаты, сколько статей выпустить). Кандидатов на spare больше — на случай,
    если часть отсеется перед написанием (дубль, мало материала)."""
    now = now or datetime.now(timezone.utc)
    done = db.count_published_since(day_start_utc(tz, now))
    n = slots_for_this_run(quota=quota, done_today=done, max_per_run=max_per_run, tz=tz,
                           interval_min=interval_min, publish_from=publish_from, publish_to=publish_to, now=now)
    if n == 0:
        return [], 0
    since = (now - timedelta(hours=window_hours)).replace(microsecond=0).isoformat()
    # SELECTED — на случай, если прошлый запуск прервался посреди работы (дубль исключит проверка в CMS).
    # Сюжеты, которые не удалось написать 3 раза, больше не берём.
    pool = [s for s in db.stories_by_status([dbm.SCORED, dbm.SELECTED, dbm.FAILED], since) if s.attempts < 3]
    pool.sort(key=lambda s: (s.status != dbm.SELECTED, -s.final_score))  # недописанные в прошлый раз — первыми
    day_ago = (now - timedelta(hours=24)).replace(microsecond=0).isoformat()
    chosen = pick(pool, n + spare, min_score, recent=db.stories_updated_since([dbm.PUBLISHED, dbm.IN_REVIEW], day_ago))
    with db.tx():
        for s in chosen:
            db.update_story(s.id, status=dbm.SELECTED)
    return chosen, n
