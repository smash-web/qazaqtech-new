"""Публикация новостей сайта в Instagram (Instagram API with Instagram Login).

Каждый запуск (раз в 30 минут) выкладывает не больше одного поста: самую раннюю из свежих
опубликованных статей, которой ещё нет в Instagram. Картинку 1080×1350 JPEG рисует сайт
(/ig/<slug>), подпись — анонс, ссылка на сайт, источники, пометка об ИИ и хештеги.
Токен (60 дней) продлевается автоматически раз в неделю.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from .cms import CMSClient
from .config import Config
from .db import Database

log = logging.getLogger(__name__)

NETWORK = "instagram"
GRAPH = "https://graph.instagram.com"
MAX_ATTEMPTS = 3
REFRESH_EVERY = timedelta(days=7)
CAPTION_LIMIT = 2200

# Хештег рубрики (по slug)
CATEGORY_TAGS = {
    "ai": "#ЖасандыИнтеллект #AI",
    "big-tech": "#BigTech",
    "startups": "#стартап",
    "security": "#киберқауіпсіздік",
    "gadgets": "#гаджеттер",
    "dev": "#бағдарламалау",
    "science": "#ғылым",
    "policy": "#цифрлықсаясат",
}
AI_NOTE = "Материал жасанды интеллект көмегімен дайындалды."


class InstagramError(RuntimeError):
    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


class InstagramClient:
    def __init__(self, user_agent: str, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent

    def _call(self, method: str, path: str, token: str, **params: Any) -> dict:
        params["access_token"] = token
        kw = {"params": params} if method == "GET" else {"data": params}
        resp = self.session.request(method, f"{GRAPH}/{path.lstrip('/')}", timeout=self.timeout, **kw)
        try:
            data = resp.json()
        except ValueError:
            data = {}
        if resp.status_code >= 400 or "error" in data:
            err = data.get("error") or {}
            msg = err.get("error_user_msg") or err.get("message") or resp.text[:300]
            raise InstagramError(str(msg), err.get("code"))
        return data

    def refresh(self, token: str) -> tuple[str, int]:
        data = self._call("GET", "refresh_access_token", token, grant_type="ig_refresh_token")
        return str(data["access_token"]), int(data.get("expires_in") or 60 * 24 * 3600)

    def create_image(self, ig_id: str, token: str, image_url: str, caption: str) -> str:
        try:
            data = self._call("POST", f"{ig_id}/media", token, image_url=image_url, caption=caption,
                              is_ai_generated="true")
        except InstagramError as exc:
            # Метка «AI info» появилась в API в 2026 году; если версия её не знает — пробуем без неё
            # (пометка об ИИ всё равно есть в подписи).
            if "is_ai_generated" not in str(exc):
                raise
            data = self._call("POST", f"{ig_id}/media", token, image_url=image_url, caption=caption)
        return str(data["id"])

    def wait_ready(self, container_id: str, token: str, timeout: float = 60, pause: float = 3) -> None:
        end = time.monotonic() + timeout
        while True:
            status = self._call("GET", container_id, token, fields="status_code,status").get("status_code")
            if status in (None, "FINISHED"):
                return
            if status in ("ERROR", "EXPIRED"):
                raise InstagramError(f"Instagram не принял картинку (статус {status})")
            if time.monotonic() > end:
                raise InstagramError("Instagram слишком долго обрабатывает картинку")
            time.sleep(pause)

    def publish(self, ig_id: str, token: str, container_id: str) -> str:
        return str(self._call("POST", f"{ig_id}/media_publish", token, creation_id=container_id)["id"])

    def permalink(self, media_id: str, token: str) -> str | None:
        try:
            return self._call("GET", media_id, token, fields="permalink").get("permalink")
        except InstagramError:
            return None


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def build_caption(article: dict, site_url: str, extra_tags: str = "") -> str:
    """Подпись к посту. Ссылки в подписи Instagram некликабельны — адрес сайта пишем текстом."""
    title = (article.get("title") or "").strip()
    excerpt = (article.get("excerpt") or "").strip()
    host = site_url.replace("https://", "").replace("http://", "").rstrip("/")
    names: list[str] = []
    for s in article.get("sources") or []:
        name = (s or {}).get("name")
        if name and name not in names:
            names.append(name)
    cat = article.get("category")
    cat_slug = cat.get("slug") if isinstance(cat, dict) else ""
    tags: list[str] = []
    for t in f"{extra_tags} {CATEGORY_TAGS.get(cat_slug or '', '')}".split():
        if t.startswith("#") and t.lower() not in {x.lower() for x in tags}:
            tags.append(t)
    tags = tags[:15]

    tail = [f"Толығы — {host} сайтында (сілтеме профильде)."]
    if names:
        tail.append("Дереккөз: " + ", ".join(names[:3]))
    tail.append(AI_NOTE)
    end = "\n".join(tail) + ("\n\n" + " ".join(tags) if tags else "")

    head = title
    room = CAPTION_LIMIT - len(end) - len(head) - 4
    if excerpt and room > 40:
        head += "\n\n" + (excerpt if len(excerpt) <= room else excerpt[: room - 1].rstrip() + "…")
    return f"{head}\n\n{end}"


def image_url(article: dict, site_url: str) -> str:
    v = int((_parse(article.get("updatedAt")) or datetime.now(timezone.utc)).timestamp())
    return f"{site_url}/ig/{article['slug']}?v={v}"


def post_to_instagram(cfg: Config, db: Database, cms: CMSClient, client: InstagramClient | None = None,
                      now: datetime | None = None, wait_timeout: float = 60) -> dict:
    now = now or datetime.now(timezone.utc)
    stats: dict[str, Any] = {"posted": 0, "failed": 0}
    s = cms.instagram_settings()
    if not s.get("enabled"):
        stats["skipped"] = "disabled"
        return stats
    token, ig_id = s.get("accessToken") or "", s.get("igUserId") or ""
    if not token or not ig_id:
        stats["skipped"] = "not connected"
        return stats
    client = client or InstagramClient(cfg.user_agent)

    # Продление токена раз в неделю (долгий токен живёт 60 дней)
    updated = _parse(s.get("tokenUpdatedAt"))
    if not updated or now - updated > REFRESH_EVERY:
        try:
            token, expires_in = client.refresh(token)
            cms.update_instagram_settings({
                "accessToken": token, "tokenUpdatedAt": now.isoformat(),
                "tokenExpiresAt": (now + timedelta(seconds=expires_in)).isoformat()})
            stats["token_refreshed"] = True
        except InstagramError as exc:
            log.warning("Instagram: не удалось продлить токен: %s", exc)
            stats["token_error"] = str(exc)[:200]

    limit = int(s.get("dailyLimit") or 20)
    if db.social_count_since(NETWORK, (now - timedelta(hours=24)).isoformat()) >= limit:
        stats["skipped"] = "daily limit"
        return stats

    since = now - timedelta(hours=int(s.get("lookbackHours") or 6))
    for article in cms.published_since(since.isoformat()):
        rec = db.social_get(article["id"], NETWORK)
        # «posting» — публикация была начата, но не подтверждена: не повторяем, чтобы не выложить дважды
        if rec and (rec["status"] in ("posted", "posting") or rec["attempts"] >= MAX_ATTEMPTS):
            continue
        try:
            caption = build_caption(article, cfg.site_url, s.get("hashtags") or "")
            container = client.create_image(ig_id, token, image_url(article, cfg.site_url), caption)
            client.wait_ready(container, token, timeout=wait_timeout)
            db.social_save(article["id"], NETWORK, "posting", attempt=True)
            media_id = client.publish(ig_id, token, container)
            link = client.permalink(media_id, token)
            db.social_save(article["id"], NETWORK, "posted", media_id=media_id, permalink=link)
            cms.update_instagram_settings({"lastPostAt": now.isoformat(), "lastError": ""})
            stats.update(posted=1, article=article["id"], permalink=link)
        except InstagramError as exc:
            msg = str(exc)[:300]
            log.warning("Instagram: статья %s не опубликована: %s", article.get("id"), msg)
            db.social_save(article["id"], NETWORK, "failed", error=msg, attempt=True)
            note = "Доступ к Instagram истёк — переподключите аккаунт." if exc.code == 190 else msg
            try:
                cms.update_instagram_settings({"lastError": f"{now:%d.%m %H:%M} UTC: {note}"})
            except Exception:  # noqa: BLE001
                pass
            stats.update(failed=1, error=msg)
        break  # не больше одного поста за запуск
    db.log_run("social", stats)
    return stats
