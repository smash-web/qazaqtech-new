"""Публикация новостей сайта в Telegram-канал (Bot API).

Бот должен быть администратором канала с правом публиковать сообщения. Каждый запуск выкладывает
до PER_RUN свежих опубликованных статей, которых ещё нет в канале (от ранних к поздним): картинка
1080×1350 с сайта (/ig/<slug>), подпись — заголовок, анонс, источник, пометка об ИИ — и кнопка
«Толық оқу» со ссылкой на статью. Если Telegram не смог скачать картинку, уходит текстовый пост
со ссылкой (превью статьи Telegram построит сам).
"""
from __future__ import annotations

import html
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from .cms import CMSClient
from .config import Config
from .db import Database
from .social import AI_NOTE, image_url

log = logging.getLogger(__name__)

NETWORK = "telegram"
API = "https://api.telegram.org"
MAX_ATTEMPTS = 3
PER_RUN = 3
CAPTION_LIMIT = 1024  # лимит подписи к фото в Telegram
# Ошибки, при которых Telegram не смог взять картинку по ссылке — тогда шлём текстовый пост
PHOTO_ERRORS = ("failed to get http url content", "wrong file identifier", "wrong type of the web page content",
                "photo_invalid_dimensions", "image_process_failed")


class TelegramError(RuntimeError):
    def __init__(self, message: str, code: int | None = None, retry_after: int | None = None):
        super().__init__(message)
        self.code = code
        self.retry_after = retry_after


class TelegramClient:
    def __init__(self, token: str, user_agent: str, timeout: int = 30):
        self.base = f"{API}/bot{token}"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent

    def _call(self, method: str, **payload: Any) -> Any:
        try:
            resp = self.session.post(f"{self.base}/{method}", json=payload, timeout=self.timeout)
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            raise TelegramError(f"Telegram недоступен: {exc}") from exc
        if not data.get("ok"):
            params = data.get("parameters") or {}
            raise TelegramError(str(data.get("description") or "unknown error"), data.get("error_code"),
                                params.get("retry_after"))
        return data["result"]

    def send_video_file(self, chat_id: str, video_url: str, **payload: Any) -> dict:
        """sendVideo загрузкой файла: по ссылке GitHub (редирект на подписанный адрес) Telegram видео не скачивает."""
        try:
            video = requests.get(video_url, timeout=120).content
            fields = {k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list, bool)) else str(v))
                      for k, v in {"chat_id": chat_id, **payload}.items()}
            resp = self.session.post(f"{self.base}/sendVideo", data=fields, timeout=max(self.timeout, 180),
                                     files={"video": ("reel.mp4", video, "video/mp4")})
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            raise TelegramError(f"Telegram недоступен: {exc}") from exc
        if not data.get("ok"):
            raise TelegramError(str(data.get("description") or "unknown error"), data.get("error_code"))
        return data["result"]

    def get_chat(self, chat_id: str) -> dict:
        return self._call("getChat", chat_id=chat_id)

    def send_photo(self, chat_id: str, photo: str, caption: str, button_url: str) -> dict:
        return self._call("sendPhoto", chat_id=chat_id, photo=photo, caption=caption, parse_mode="HTML",
                          reply_markup=_button(button_url))

    def send_message(self, chat_id: str, text: str, button_url: str) -> dict:
        return self._call("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML",
                          link_preview_options={"url": button_url, "prefer_large_media": True},
                          reply_markup=_button(button_url))


def _button(url: str) -> dict:
    return {"inline_keyboard": [[{"text": "Толық оқу →", "url": url}]]}


def normalize_channel(raw: str) -> str:
    """@techtalq, t.me/techtalq, https://t.me/techtalq → @techtalq; числовой id (-100…) — как есть."""
    c = (raw or "").strip()
    for prefix in ("https://", "http://"):
        if c.startswith(prefix):
            c = c[len(prefix):]
    if c.startswith("t.me/") or c.startswith("telegram.me/"):
        c = c.split("/", 1)[1]
    c = c.strip("/")
    if not c or c.lstrip("-").isdigit() or c.startswith("@"):
        return c
    return "@" + c


def article_url(article: dict, site_url: str) -> str:
    return f"{site_url.rstrip('/')}/zhanalyq/{article['slug']}"


def build_post(article: dict, site_url: str, limit: int = CAPTION_LIMIT) -> str:
    """Подпись в HTML: жирный заголовок, анонс (обрезается под лимит), источник, пометка об ИИ."""
    title = html.escape((article.get("title") or "").strip())
    excerpt = (article.get("excerpt") or "").strip()
    names: list[str] = []
    for s in article.get("sources") or []:
        name = (s or {}).get("name")
        if name and name not in names:
            names.append(name)
    tail = []
    if names:
        tail.append("Дереккөз: " + html.escape(", ".join(names[:3])))
    tail.append(f"<i>{html.escape(AI_NOTE)}</i>")
    end = "\n".join(tail)
    head = f"<b>{title}</b>"
    # Лимит Telegram считается по видимому тексту, но теги считаем тоже — с запасом
    room = limit - len(head) - len(end) - 4
    if excerpt and room > 40:
        short = excerpt if len(excerpt) <= room else excerpt[: room - 1].rstrip() + "…"
        head += "\n\n" + html.escape(short)
    return f"{head}\n\n{end}"


def _explain(exc: TelegramError) -> str:
    msg = str(exc)
    low = msg.lower()
    if exc.code == 401:
        return "Токен бота неверный — проверьте его в @BotFather."
    if "chat not found" in low:
        return "Канал не найден — проверьте адрес канала (например, @techtalq)."
    if exc.code == 403 or "not enough rights" in low or "need administrator rights" in low:
        return "Бот не может писать в канал — добавьте его администратором с правом публиковать сообщения."
    return msg


def post_to_telegram(cfg: Config, db: Database, cms: CMSClient, client: TelegramClient | None = None,
                     now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    stats: dict[str, Any] = {"posted": 0, "failed": 0}
    s = cms.telegram_settings()
    if not s.get("enabled"):
        stats["skipped"] = "disabled"
        return stats
    token, channel = (s.get("botToken") or "").strip(), normalize_channel(s.get("channel") or "")
    if not token or not channel:
        stats["skipped"] = "not connected"
        return stats
    client = client or TelegramClient(token, cfg.user_agent)

    # Первый запуск после настройки: проверяем канал и запоминаем его название
    if not s.get("channelTitle"):
        try:
            chat = client.get_chat(channel)
            cms.update_telegram_settings({"channelTitle": chat.get("title") or channel, "lastError": ""})
        except TelegramError as exc:
            cms.update_telegram_settings({"lastError": f"{now:%d.%m %H:%M} UTC: {_explain(exc)}"})
            stats.update(skipped="channel", error=str(exc)[:200])
            db.log_run("telegram", stats)
            return stats

    left = int(s.get("dailyLimit") or 40) - db.social_count_since(NETWORK, (now - timedelta(hours=24)).isoformat())
    if left <= 0:
        stats["skipped"] = "daily limit"
        return stats

    since = now - timedelta(hours=int(s.get("lookbackHours") or 6))
    for article in cms.published_since(since.isoformat()):
        if stats["posted"] >= min(PER_RUN, left):
            break
        rec = db.social_get(article["id"], NETWORK)
        if rec and (rec["status"] in ("posted", "posting") or rec["attempts"] >= MAX_ATTEMPTS):
            continue
        url = article_url(article, cfg.site_url)
        text = build_post(article, cfg.site_url)
        try:
            db.social_save(article["id"], NETWORK, "posting", attempt=True)
            try:
                msg = client.send_photo(channel, image_url(article, cfg.site_url), text, url)
            except TelegramError as exc:
                if not any(p in str(exc).lower() for p in PHOTO_ERRORS):
                    raise
                log.info("Telegram: картинка статьи %s не загрузилась (%s) — пост без фото", article["id"], exc)
                msg = client.send_message(channel, text, url)
            msg_id = str(msg.get("message_id") or "")
            link = f"https://t.me/{channel[1:]}/{msg_id}" if channel.startswith("@") and msg_id else None
            db.social_save(article["id"], NETWORK, "posted", media_id=msg_id, permalink=link)
            stats["posted"] += 1
            stats.setdefault("articles", []).append(article["id"])
        except TelegramError as exc:
            note = _explain(exc)
            log.warning("Telegram: статья %s не опубликована: %s", article.get("id"), exc)
            db.social_save(article["id"], NETWORK, "failed", error=str(exc)[:300])
            stats.update(failed=stats["failed"] + 1, error=note)
            try:
                cms.update_telegram_settings({"lastError": f"{now:%d.%m %H:%M} UTC: {note}"})
            except Exception:  # noqa: BLE001
                pass
            break  # при ошибке канала/лимита дальше не идём — попробуем в следующий запуск
    if stats["posted"]:
        cms.update_telegram_settings({"lastPostAt": now.isoformat(), **({} if stats["failed"] else {"lastError": ""})})
    db.log_run("telegram", stats)
    return stats
