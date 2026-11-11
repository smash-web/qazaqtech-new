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
    """Если к уже оценённому (или отложенному из-за нехватки материала) сюжету пришли новые источники — переоценить."""
    return db.get_story(story_id).status in ("scored", "thin")



def similar_stories(db: Database, story_id: int, since: str) -> list[tuple[int, float, str]]:
    """Уже вышедшие (или на модерации) сюжеты, похожие на данный, — по сходству заголовков.

    Кластеризация иногда делит одно событие на несколько сюжетов (издания пишут заголовки по-разному),
    поэтому перед написанием статьи сверяемся с тем, что уже вышло. IDF считается по всему окну публикаций,
    чтобы частые слова («IPO», «AI») весили меньше редких имён и цифр.
    """
    mine = db.items_for_story(story_id)
    others = db.items_of_stories(["published", "review"], since, story_id)
    if not mine or not others:
        return []
    corpus = db.clustered_items_since(since)
    docs = [tokenize(i.title) for i in mine] + [tokenize(i.title) for i in others] + \
        [tokenize(i.title) for i in corpus]
    vectors = tfidf_matrix(docs)
    sims = vectors[len(mine): len(mine) + len(others)] @ vectors[: len(mine)].T  # (others × mine)
    best: dict[int, tuple[float, str]] = {}
    for row, item in enumerate(others):
        sim = float(sims[row].max())
        if item.story_id is not None and sim > best.get(item.story_id, (-1.0, ""))[0]:
            best[item.story_id] = (sim, item.title)
    return sorted(((sid, sim, title) for sid, (sim, title) in best.items()), key=lambda x: -x[1])


def duplicate_of(db: Database, story_id: int, since: str, threshold: float = 0.45) -> int | None:
    """Эвристика без ИИ: дубль, если заголовки очень похожи."""
    sims = similar_stories(db, story_id, since)
    return sims[0][0] if sims and sims[0][1] >= threshold else None
