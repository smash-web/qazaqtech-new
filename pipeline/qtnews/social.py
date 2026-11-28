"""Публикация новостей сайта в Instagram (Instagram API with Unified Login, graph.facebook.com).

Каждый запуск (раз в 30 минут) выкладывает не больше одного поста: самую раннюю из свежих
опубликованных статей, которой ещё нет в Instagram. Картинку 1080×1350 JPEG рисует сайт
(/ig/<slug>), подпись — анонс, ссылка на сайт, источники, пометка об ИИ и хештеги.
Токен системного пользователя бизнес-портфолио обычно бессрочный; если у токена есть срок,
за неделю до него в админке появляется просьба переподключить аккаунт.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from .cms import CMSClient
from .config import Config
from .db import Database

log = logging.getLogger(__name__)

NETWORK = "instagram"
GRAPH = f"https://graph.facebook.com/{os.environ.get('META_GRAPH_VERSION', 'v26.0')}"
MAX_ATTEMPTS = 3
WARN_BEFORE_EXPIRY = timedelta(days=7)
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


def share_candidates(cms: CMSClient, db: Database, s: dict, network: str, field: str, now: datetime,
                     max_attempts: int) -> list[dict]:
    """Режим «manual» — только статьи, отмеченные редактором кнопкой; «auto» — свежие опубликованные по очереди.
    В ручном режиме повторная заявка редактора (после ошибки) снимает ограничение попыток."""
    out = []
    if (s.get("mode") or "auto") == "manual":
        for a in cms.share_requests(field):
            rec = db.social_get(a["id"], network)
            if rec and rec["status"] in ("posted", "posting"):
                continue
            requested = _parse(a.get(field))
            if rec and rec["attempts"] >= max_attempts and not (requested and _parse(rec.get("updated_at")) and requested > _parse(rec["updated_at"])):
                continue
            out.append(a)
        return out
    since = now - timedelta(hours=int(s.get("lookbackHours") or 6))
    for a in cms.published_since(since.isoformat()):
        rec = db.social_get(a["id"], network)
        if rec and (rec["status"] in ("posted", "posting") or rec["attempts"] >= max_attempts):
            continue
        out.append(a)
    return out


def mark_article(cms: CMSClient, article_id: Any, field: str, text: str) -> None:
    """Итог публикации — в статью, редактор видит его рядом с кнопкой."""
    try:
        cms.update_article(article_id, {field: text[:300]})
    except Exception as exc:  # noqa: BLE001
        log.warning("Не удалось записать статус в статью %s: %s", article_id, exc)


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

    # Токен со сроком (не системного пользователя) — заранее просим переподключить
    expires = _parse(s.get("tokenExpiresAt"))
    if expires and expires - now < WARN_BEFORE_EXPIRY:
        note = f"Доступ к Instagram истекает {expires:%d.%m.%Y} — нажмите «Переподключить Instagram»."
        if s.get("lastError") != note:
            cms.update_instagram_settings({"lastError": note})
        stats["token_expires"] = expires.isoformat()

    limit = int(s.get("dailyLimit") or 20)
    if db.social_count_since(NETWORK, (now - timedelta(hours=24)).isoformat()) >= limit:
        stats["skipped"] = "daily limit"
        return stats

    manual = (s.get("mode") or "auto") == "manual"
    # «posting» — публикация была начата, но не подтверждена: не повторяем, чтобы не выложить дважды
    for article in share_candidates(cms, db, s, NETWORK, "instagramRequestedAt", now, MAX_ATTEMPTS):
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
            if manual:
                mark_article(cms, article["id"], "instagramStatus", f"✓ Опубликовано {now:%d.%m %H:%M} UTC {link or ''}".strip())
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
            if manual:
                mark_article(cms, article["id"], "instagramStatus", f"✕ Ошибка: {note}")
        break  # не больше одного поста за запуск
    db.log_run("social", stats)
    return stats
