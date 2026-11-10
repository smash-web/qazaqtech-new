"""Группировка публикаций разных источников об одном событии в «сюжеты».

Используется TF-IDF + косинусное сходство (numpy, без внешних сервисов).
Для 1–5 тыс. публикаций в сутки этого достаточно; при росте модуль можно
заменить на эмбеддинги + pgvector, не меняя остальной конвейер.
"""
from __future__ import annotations

import math
import re
from collections import Counter

import numpy as np

from .db import Database, Item

_STOP = set("""
a an the and or but if then of to in on for with at by from as is are was were be been being it its this that these
those has have had do does did not no so than too very can will just about into over after before up down out new
how why what when where who which you your we our they their he she his her i my me us them more most also says said
report reports according via now today week year amid could would should may might gets get make makes made one two
""".split())
_TOKEN = re.compile(r"[a-z0-9][a-z0-9+#.\-]*[a-z0-9+#]|[a-z0-9]")


_SUFFIXES = ("ations", "ation", "ings", "ing", "ers", "ies", "ied", "ed", "es", "er", "ly", "s")


def stem(token: str) -> str:
    """Очень лёгкий стеммер для английского: exploited/exploits → exploit, companies → compan."""
    if len(token) <= 4 or not token.isalpha():
        return token
    for suf in _SUFFIXES:
        if token.endswith(suf) and len(token) - len(suf) >= 4:
            return token[: -len(suf)]
    return token


def tokenize(text: str) -> list[str]:
    tokens = [stem(t) for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 1]
    # Биграммы помогают отличать «apple vision» от «apple watch»
    return tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]


def _doc(item: Item) -> list[str]:
    # Заголовок важнее анонса — повторяем его токены
    return tokenize(item.title) * 2 + tokenize(item.summary[:400])


def tfidf_matrix(docs: list[list[str]]) -> np.ndarray:
    if not docs:
        return np.zeros((0, 0))
    df: Counter[str] = Counter()
    for d in docs:
        df.update(set(d))
    vocab = {t: i for i, t in enumerate(df)}
    n = len(docs)
    idf = np.array([math.log((1 + n) / (1 + df[t])) + 1 for t in vocab])
    mat = np.zeros((n, len(vocab)))
    for row, d in enumerate(docs):
        for t, c in Counter(d).items():
            mat[row, vocab[t]] = 1 + math.log(c)
    mat *= idf
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return mat / norms


def cluster_new_items(db: Database, since: str, threshold: float) -> dict[str, int]:
    """Распределяет новые публикации по существующим или новым сюжетам."""
    existing = db.clustered_items_since(since)
    fresh = db.unclustered_items(since)
    if not fresh:
        return {"new_items": 0, "new_stories": 0, "attached": 0}

    all_items = existing + fresh
    vectors = tfidf_matrix([_doc(i) for i in all_items])
    story_of: list[int | None] = [i.story_id for i in existing] + [None] * len(fresh)
    new_stories = attached = 0

    with db.tx():
        for idx in range(len(existing), len(all_items)):
            item = all_items[idx]
            assigned = [j for j in range(len(all_items)) if story_of[j] is not None and j != idx]
            best_story, best_sim = None, 0.0
            if assigned:
                sims = vectors[assigned] @ vectors[idx]
                k = int(np.argmax(sims))
                best_sim = float(sims[k])
                best_story = story_of[assigned[k]]
            if best_story is not None and best_sim >= threshold:
                story_of[idx] = best_story
                attached += 1
            else:
                story_of[idx] = db.create_story(item.title)
                new_stories += 1
            db.assign_item(item.id, story_of[idx])  # type: ignore[arg-type]
            if best_story is not None and story_of[idx] == best_story and _needs_rescore(db, best_story):
                db.update_story(best_story, status="new")

    return {"new_items": len(fresh), "new_stories": new_stories, "attached": attached}


def _needs_rescore(db: Database, story_id: int) -> bool:
    """Если к уже оценённому сюжету пришли новые источники — переоценить его."""
    return db.get_story(story_id).status == "scored"
