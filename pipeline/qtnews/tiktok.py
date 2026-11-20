"""Отправка новостей сайта в TikTok черновиками (Content Posting API, MEDIA_UPLOAD, фото).

Каждый запуск отправляет не больше одного черновика: самую раннюю из свежих опубликованных статей,
которой ещё нет в TikTok. TikTok присылает владельцу уведомление во «Входящие», пост публикуется
оттуда в пару нажатий. Картинка — та же 1080×1350 (/ig/<slug>), её адрес должен быть подтверждён в
приложении TikTok (URL prefix). Access-токен живёт 24 часа — продлевается refresh-токеном (365 дней).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from .cms import CMSClient
from .config import Config
from .db import Database
from .social import _parse, build_caption, image_url

log = logging.getLogger(__name__)

NETWORK = "tiktok"
API = "https://open.tiktokapis.com/v2"
MAX_ATTEMPTS = 3
REFRESH_BEFORE = timedelta(hours=2)
TITLE_LIMIT = 90


class TikTokError(RuntimeError):
    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.code = code


class TikTokClient:
    def __init__(self, user_agent: str, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent

    @staticmethod
    def _check(resp: requests.Response) -> dict:
        try:
            data = resp.json()
        except ValueError:
            data = {}
        err = data.get("error")
        if isinstance(err, dict) and err.get("code") not in (None, "", "ok"):
            raise TikTokError(f"{err.get('code')}: {err.get('message') or ''}".strip(": "), err.get("code"))
        if isinstance(err, str) and err:
            raise TikTokError(f"{err}: {data.get('error_description') or ''}".strip(": "), err)
        if resp.status_code >= 400:
            raise TikTokError(resp.text[:300])
        return data

    def refresh(self, client_key: str, client_secret: str, refresh_token: str) -> dict:
        resp = self.session.post(f"{API}/oauth/token/", timeout=self.timeout, data={
            "client_key": client_key, "client_secret": client_secret,
            "grant_type": "refresh_token", "refresh_token": refresh_token})
        return self._check(resp)

    def upload_photo_draft(self, token: str, image: str, title: str, description: str) -> str:
        resp = self.session.post(f"{API}/post/publish/content/init/", timeout=self.timeout,
                                 headers={"Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json; charset=UTF-8"},
                                 json={
                                     "post_info": {"title": title, "description": description},
                                     "source_info": {"source": "PULL_FROM_URL", "photo_cover_index": 0,
                                                     "photo_images": [image]},
                                     "post_mode": "MEDIA_UPLOAD",
                                     "media_type": "PHOTO",
                                 })
        data = self._check(resp)
        return str((data.get("data") or {}).get("publish_id") or "")


def tiktok_title(article: dict) -> str:
    t = (article.get("title") or "").strip()
    return t if len(t) <= TITLE_LIMIT else t[: TITLE_LIMIT - 1].rstrip() + "…"


def post_to_tiktok(cfg: Config, db: Database, cms: CMSClient, client: TikTokClient | None = None,
                   now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    stats: dict[str, Any] = {"sent": 0, "failed": 0}
    s = cms.tiktok_settings()
    if not s.get("enabled"):
        stats["skipped"] = "disabled"
        return stats
    token, refresh = s.get("accessToken") or "", s.get("refreshToken") or ""
    if not token or not refresh:
        stats["skipped"] = "not connected"
        return stats
    client = client or TikTokClient(cfg.user_agent)

    # Access-токен живёт сутки — продлеваем заранее
    expires = _parse(s.get("accessExpiresAt"))
    if not expires or expires - now < REFRESH_BEFORE:
        try:
            tok = client.refresh(cfg.tiktok_client_key, cfg.tiktok_client_secret, refresh)
            token = str(tok["access_token"])
            data = {"accessToken": token,
                    "accessExpiresAt": (now + timedelta(seconds=int(tok.get("expires_in") or 86400))).isoformat()}
            if tok.get("refresh_token"):
                data["refreshToken"] = tok["refresh_token"]
                data["refreshExpiresAt"] = (now + timedelta(seconds=int(tok.get("refresh_expires_in") or 31536000))).isoformat()
            cms.update_tiktok_settings(data)
            stats["token_refreshed"] = True
        except (TikTokError, KeyError) as exc:
            note = f"{now:%d.%m %H:%M} UTC: не удалось продлить доступ к TikTok ({exc}) — нажмите «Переподключить TikTok»."
            cms.update_tiktok_settings({"lastError": note})
            stats.update(skipped="token", error=str(exc)[:200])
            db.log_run("tiktok", stats)
            return stats

    if db.social_count_since(NETWORK, (now - timedelta(hours=24)).isoformat()) >= int(s.get("dailyLimit") or 5):
        stats["skipped"] = "daily limit"
        return stats

    since = now - timedelta(hours=int(s.get("lookbackHours") or 6))
    for article in cms.published_since(since.isoformat()):
        rec = db.social_get(article["id"], NETWORK)
        if rec and (rec["status"] in ("posted", "posting") or rec["attempts"] >= MAX_ATTEMPTS):
            continue
        try:
            db.social_save(article["id"], NETWORK, "posting", attempt=True)
            publish_id = client.upload_photo_draft(
                token, image_url(article, cfg.site_url), tiktok_title(article),
                build_caption(article, cfg.site_url, s.get("hashtags") or ""))
            db.social_save(article["id"], NETWORK, "posted", media_id=publish_id)
            cms.update_tiktok_settings({"lastPostAt": now.isoformat(), "lastError": ""})
            stats.update(sent=1, article=article["id"], publish_id=publish_id)
        except TikTokError as exc:
            msg = str(exc)[:300]
            log.warning("TikTok: статья %s не отправлена: %s", article.get("id"), msg)
            db.social_save(article["id"], NETWORK, "failed", error=msg)  # попытка уже учтена при «posting»
            try:
                cms.update_tiktok_settings({"lastError": f"{now:%d.%m %H:%M} UTC: {msg}"})
            except Exception:  # noqa: BLE001
                pass
            stats.update(failed=1, error=msg)
        break  # не больше одного черновика за запуск
    db.log_run("tiktok", stats)
    return stats
