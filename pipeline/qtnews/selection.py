"""Отбор сюжетов для публикации с учётом дневной квоты и равномерности в течение дня."""
from __future__ import annotations

import math
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


def pick(stories: list[Story], n: int, min_score: float) -> list[Story]:
    """Лучшие по оценке, но не больше одного сюжета на рубрику за запуск, если есть альтернатива."""
    candidates = [s for s in stories if s.final_score >= min_score]
    candidates.sort(key=lambda s: s.final_score, reverse=True)
    chosen: list[Story] = []
    used: set[str | None] = set()
    for s in candidates:
        if len(chosen) >= n:
            break
        if s.category in used and s.category is not None:
            continue
        chosen.append(s)
        used.add(s.category)
    for s in candidates:  # добираем, если рубрик не хватило
        if len(chosen) >= n:
            break
        if s not in chosen:
            chosen.append(s)
    return chosen


def select_for_run(db: Database, *, quota: int, min_score: float, max_per_run: int, tz: str, interval_min: int,
                   window_hours: int, publish_from: int = 7, publish_to: int = 23,
                   now: datetime | None = None) -> list[Story]:
    now = now or datetime.now(timezone.utc)
    done = db.count_published_since(day_start_utc(tz, now))
    n = slots_for_this_run(quota=quota, done_today=done, max_per_run=max_per_run, tz=tz,
                           interval_min=interval_min, publish_from=publish_from, publish_to=publish_to, now=now)
    if n == 0:
        return []
    since = (now - timedelta(hours=window_hours)).replace(microsecond=0).isoformat()
    # SELECTED — на случай, если прошлый запуск прервался посреди работы (дубль исключит проверка в CMS).
    # Сюжеты, которые не удалось написать 3 раза, больше не берём.
    pool = [s for s in db.stories_by_status([dbm.SCORED, dbm.SELECTED, dbm.FAILED], since) if s.attempts < 3]
    chosen = pick(pool, n, min_score)
    with db.tx():
        for s in chosen:
            db.update_story(s.id, status=dbm.SELECTED)
    return chosen
