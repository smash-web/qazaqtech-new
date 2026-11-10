"""Хранилище конвейера: сырые новости (items) и сюжеты (stories).

Работает с PostgreSQL (прод) и SQLite (локально/тесты) через один тонкий слой.
Время хранится строкой ISO-8601 в UTC — сортируется одинаково в обеих СУБД.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id {pk},
    source_id TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_weight REAL NOT NULL DEFAULT 5,
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    published_at TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    story_id BIGINT
);
CREATE INDEX IF NOT EXISTS idx_items_published ON items(published_at);
CREATE INDEX IF NOT EXISTS idx_items_story ON items(story_id);

CREATE TABLE IF NOT EXISTS stories (
    id {pk},
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    heuristic_score REAL NOT NULL DEFAULT 0,
    llm_score REAL,
    final_score REAL NOT NULL DEFAULT 0,
    category TEXT,
    score_reason TEXT,
    article_id TEXT,
    error TEXT,
    attempts INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_stories_status ON stories(status);
CREATE INDEX IF NOT EXISTS idx_stories_created ON stories(created_at);

CREATE TABLE IF NOT EXISTS run_log (
    id {pk},
    started_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    stats TEXT NOT NULL DEFAULT '{{}}'
);
"""

# Статусы сюжета
NEW, SCORED, SELECTED, PUBLISHED, IN_REVIEW, SKIPPED, FAILED = (
    "new", "scored", "selected", "published", "review", "skipped", "failed",
)


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Item:
    id: int
    source_id: str
    source_name: str
    source_weight: float
    url: str
    title: str
    summary: str
    published_at: str
    story_id: int | None


@dataclass
class Story:
    id: int
    title: str
    created_at: str
    status: str
    heuristic_score: float
    llm_score: float | None
    final_score: float
    category: str | None
    score_reason: str | None
    article_id: str | None
    attempts: int


class Database:
    def __init__(self, url: str):
        self.url = url
        if url.startswith("sqlite:///"):
            self.kind = "sqlite"
            self._conn = sqlite3.connect(url[len("sqlite:///"):] or ":memory:", check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        elif url.startswith(("postgres://", "postgresql://")):
            import psycopg  # type: ignore
            from psycopg.rows import dict_row  # type: ignore

            self.kind = "postgres"
            # prepare_threshold=None — без prepared statements, иначе ломается пулер Supabase (transaction mode)
            self._conn = psycopg.connect(url, row_factory=dict_row, autocommit=False, prepare_threshold=None)
            schema = os.environ.get("PIPELINE_DB_SCHEMA", "").strip()
            if schema:
                if not schema.replace("_", "").isalnum():
                    raise ValueError("PIPELINE_DB_SCHEMA: только буквы, цифры и _")
                with self._conn.cursor() as cur:
                    cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
                    cur.execute(f'SET search_path TO "{schema}"')
                self._conn.commit()
        else:
            raise ValueError(f"Неподдерживаемый DATABASE_URL: {url}")

    # --- низкоуровневые операции -------------------------------------------------
    def _sql(self, sql: str) -> str:
        return sql.replace("?", "%s") if self.kind == "postgres" else sql

    def execute(self, sql: str, params: tuple | list = ()) -> Any:
        cur = self._conn.cursor()
        cur.execute(self._sql(sql), params)
        return cur

    def query(self, sql: str, params: tuple | list = ()) -> list[dict]:
        cur = self.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

    def insert_returning_id(self, sql: str, params: tuple | list) -> int:
        if self.kind == "postgres":
            cur = self.execute(sql + " RETURNING id", params)
            return int(cur.fetchone()["id"])
        cur = self.execute(sql, params)
        return int(cur.lastrowid)

    @contextmanager
    def tx(self) -> Iterator["Database"]:
        try:
            yield self
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def init_schema(self) -> None:
        pk = "BIGSERIAL PRIMARY KEY" if self.kind == "postgres" else "INTEGER PRIMARY KEY AUTOINCREMENT"
        with self.tx():
            for stmt in SCHEMA.format(pk=pk).split(";"):
                if stmt.strip():
                    self.execute(stmt)

    def close(self) -> None:
        self._conn.close()

    # --- items ---------------------------------------------------------------------
    def add_item(self, *, source_id: str, source_name: str, source_weight: float, url: str,
                 title: str, summary: str, published_at: str) -> int | None:
        """Добавляет новость; возвращает id или None, если URL уже есть."""
        if self.query("SELECT id FROM items WHERE url = ?", (url,)):
            return None
        return self.insert_returning_id(
            "INSERT INTO items (source_id, source_name, source_weight, url, title, summary, published_at, fetched_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (source_id, source_name, source_weight, url, title, summary, published_at, utcnow()),
        )

    def unclustered_items(self, since: str) -> list[Item]:
        rows = self.query(
            "SELECT * FROM items WHERE story_id IS NULL AND published_at >= ? ORDER BY published_at", (since,)
        )
        return [_item(r) for r in rows]

    def items_for_story(self, story_id: int) -> list[Item]:
        return [_item(r) for r in self.query("SELECT * FROM items WHERE story_id = ? ORDER BY published_at", (story_id,))]

    def clustered_items_since(self, since: str) -> list[Item]:
        rows = self.query(
            "SELECT i.* FROM items i JOIN stories s ON s.id = i.story_id WHERE s.created_at >= ?", (since,)
        )
        return [_item(r) for r in rows]

    def assign_item(self, item_id: int, story_id: int) -> None:
        self.execute("UPDATE items SET story_id = ? WHERE id = ?", (story_id, item_id))

    # --- stories -------------------------------------------------------------------
    def create_story(self, title: str) -> int:
        now = utcnow()
        return self.insert_returning_id(
            "INSERT INTO stories (title, created_at, updated_at) VALUES (?, ?, ?)", (title, now, now)
        )

    def get_story(self, story_id: int) -> Story:
        return _story(self.query("SELECT * FROM stories WHERE id = ?", (story_id,))[0])

    def stories_by_status(self, statuses: list[str], since: str) -> list[Story]:
        marks = ",".join("?" for _ in statuses)
        rows = self.query(
            f"SELECT * FROM stories WHERE status IN ({marks}) AND created_at >= ? ORDER BY final_score DESC",
            (*statuses, since),
        )
        return [_story(r) for r in rows]

    def update_story(self, story_id: int, **fields: Any) -> None:
        if not fields:
            return
        fields["updated_at"] = utcnow()
        cols = ", ".join(f"{k} = ?" for k in fields)
        self.execute(f"UPDATE stories SET {cols} WHERE id = ?", (*fields.values(), story_id))

    def count_published_since(self, since: str) -> int:
        rows = self.query(
            "SELECT COUNT(*) AS n FROM stories WHERE status IN (?, ?) AND updated_at >= ?",
            (PUBLISHED, IN_REVIEW, since),
        )
        return int(rows[0]["n"])

    def log_run(self, kind: str, stats: dict) -> None:
        with self.tx():
            self.execute("INSERT INTO run_log (started_at, kind, stats) VALUES (?, ?, ?)",
                         (utcnow(), kind, json.dumps(stats, ensure_ascii=False)))


def _item(r: dict) -> Item:
    return Item(id=r["id"], source_id=r["source_id"], source_name=r["source_name"],
                source_weight=float(r["source_weight"]), url=r["url"], title=r["title"],
                summary=r["summary"], published_at=r["published_at"], story_id=r["story_id"])


def _story(r: dict) -> Story:
    return Story(id=r["id"], title=r["title"], created_at=r["created_at"], status=r["status"],
                 heuristic_score=float(r["heuristic_score"]),
                 llm_score=None if r["llm_score"] is None else float(r["llm_score"]),
                 final_score=float(r["final_score"]), category=r["category"],
                 score_reason=r["score_reason"], article_id=r["article_id"], attempts=int(r["attempts"]))
