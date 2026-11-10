"""Клиент REST API Payload CMS: настройки редакции, источники, глоссарий, публикация статей."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests

log = logging.getLogger(__name__)


class CMSError(RuntimeError):
    pass


@dataclass
class EditorialSettings:
    auto_publish: bool = False
    daily_quota: int = 18
    min_score: float = 5.5
    publish_from_hour: int = 7
    publish_to_hour: int = 23
    style_guide: str = ""
    selection_guidance: str = ""
    pipeline_enabled: bool = True


class CMSClient:
    def __init__(self, base_url: str, api_key: str, user_collection: str = "users", timeout: int = 30):
        if not api_key:
            raise CMSError("CMS_API_KEY не задан")
        self.base = base_url.rstrip("/") + "/api"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"{user_collection} API-Key {api_key}",
            "Content-Type": "application/json",
        })

    def _req(self, method: str, path: str, **kw: Any) -> Any:
        resp = self.session.request(method, self.base + path, timeout=self.timeout, **kw)
        if resp.status_code >= 400:
            raise CMSError(f"CMS {method} {path} → {resp.status_code}: {resp.text[:400]}")
        return resp.json()

    def _all(self, collection: str, where: dict[str, str] | None = None) -> list[dict]:
        docs: list[dict] = []
        page = 1
        while True:
            params = {"limit": 200, "page": page, "depth": 0, **(where or {})}
            data = self._req("GET", f"/{collection}", params=params)
            docs.extend(data.get("docs", []))
            if not data.get("hasNextPage"):
                return docs
            page += 1

    # --- справочники ------------------------------------------------------------
    def settings(self) -> EditorialSettings:
        g = self._req("GET", "/globals/pipeline-settings", params={"depth": 0})
        return EditorialSettings(
            auto_publish=bool(g.get("autoPublish", False)),
            daily_quota=int(g.get("dailyQuota") or 18),
            min_score=float(g.get("minScore") or 5.5),
            publish_from_hour=int(g.get("publishFromHour") if g.get("publishFromHour") is not None else 7),
            publish_to_hour=int(g.get("publishToHour") or 23),
            style_guide=g.get("styleGuide") or "",
            selection_guidance=g.get("selectionGuidance") or "",
            pipeline_enabled=bool(g.get("pipelineEnabled", True)),
        )

    def sources(self) -> list[dict]:
        return self._all("sources", {"where[active][equals]": "true"})

    def glossary(self) -> list[dict]:
        return self._all("glossary")

    def categories(self) -> list[dict]:
        return self._all("categories")

    # --- статьи -------------------------------------------------------------------
    def find_article_by_story(self, story_id: int) -> dict | None:
        data = self._req("GET", "/articles", params={
            "where[pipelineStoryId][equals]": str(story_id), "limit": 1, "depth": 0})
        docs = data.get("docs", [])
        return docs[0] if docs else None

    def slug_exists(self, slug: str) -> bool:
        data = self._req("GET", "/articles", params={"where[slug][equals]": slug, "limit": 1, "depth": 0})
        return bool(data.get("docs"))

    def create_article(self, payload: dict) -> dict:
        data = self._req("POST", "/articles", json=payload)
        return data.get("doc", data)

    def update_article(self, article_id: int | str, payload: dict) -> dict:
        data = self._req("PATCH", f"/articles/{article_id}", json=payload)
        return data.get("doc", data)

    def articles_without_cover(self, limit: int = 10) -> list[dict]:
        """Опубликованные статьи и статьи, отложенные из-за отсутствия фото."""
        data = self._req("GET", "/articles", params={
            "where[coverImage][exists]": "false", "where[status][in]": "published,review",
            "sort": "-createdAt", "limit": limit, "depth": 1})
        return data.get("docs", [])

    # --- медиа --------------------------------------------------------------------
    def used_image_pages(self) -> set[str]:
        """Страницы Commons, чьи фото уже есть в медиатеке (из подписи), — чтобы не повторяться."""
        pages: set[str] = set()
        for m in self._all("media"):
            credit = m.get("credit") or ""
            if "commons.wikimedia.org" in credit:
                pages.add(credit.rsplit(" — ", 1)[-1].strip())
        return pages

    def upload_media(self, content: bytes, filename: str, mime: str, alt: str, credit: str) -> dict:
        import json as _json

        resp = requests.post(
            self.base + "/media",
            headers={"Authorization": self.session.headers["Authorization"]},
            files={"file": (filename, content, mime)},
            data={"_payload": _json.dumps({"alt": alt[:200], "credit": credit[:500]}, ensure_ascii=False)},
            timeout=max(self.timeout, 60),
        )
        if resp.status_code >= 400:
            raise CMSError(f"CMS POST /media → {resp.status_code}: {resp.text[:400]}")
        data = resp.json()
        return data.get("doc", data)
