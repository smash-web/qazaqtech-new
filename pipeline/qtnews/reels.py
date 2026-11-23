"""Рилсы с 2D-диктором: подготовка (сценарий + озвучка) и публикация готового видео.

Ролик собирается в GitHub Actions (.github/workflows/reels.yml, папка reels/):
  1. Actions → POST /api/run?step=reel_prepare — здесь выбирается главная свежая статья, ИИ пишет
     казахский текст для диктора, ElevenLabs озвучивает его с таймкодами символов.
  2. Actions рендерит MP4 (диктор, синхронизация губ, фон новости, субтитры) и кладёт его в релиз
     репозитория `reels` (публичная ссылка).
  3. Actions → POST /api/run?step=reel_publish {article_id, video_url} — видео уходит в Instagram Reels,
     Telegram и (по желанию) черновиком в TikTok.
Учёт — social_posts: network 'reel' (сам ролик) и 'reel_instagram' / 'reel_telegram' / 'reel_tiktok'.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from .cms import CMSClient
from .config import Config
from .db import Database
from .llm import LLM, LLMError, complete_json
from .social import InstagramClient, InstagramError, _parse, build_caption
from .telegram import TelegramClient, TelegramError, article_url, build_post, normalize_channel

log = logging.getLogger(__name__)

REEL = "reel"
MAX_ATTEMPTS = 2
STALE_RENDER = timedelta(hours=2)
ELEVEN = "https://api.elevenlabs.io/v1"
DEFAULT_VOICES = {"f": "EXAVITQu4vr4xnSDxMaL", "m": "JBFqnCBsd6RMkjVDRZzb"}  # премиум-голоса ElevenLabs по умолчанию
# Как диктор произносит бренд и концовку (в субтитрах их нет — показываются только во вступлении/концовке)
SPOKEN_BRAND = "Тек Ток"
OUTRO = "Толығы біздің сайтта. Жазылыңыз!"

SCRIPT_SYSTEM = (
    "Сен — TechTalQ IT-жаңалықтар арнасының дикторына мәтін жазатын редакторсың. "
    "Қазақ тілінде, әдеби, бірақ жанды сөйлеу тілінде жазасың. Тек берілген мақаладағы фактілерді қолдан, "
    "ештеңе ойдан қоспа. Сандарды сөзбен жаз (мысалы, «екі жүз елу миллион»). Сілтеме, эмодзи, хэштег жазба. "
    "Ағылшын атаулары (Apple, Nvidia) өз қалпында қалсын."
)
SCRIPT_PROMPT = """Мақала:
Тақырып: {title}
Анонс: {excerpt}
Мәтін: {body}

Рилс үшін диктор мәтінін JSON түрінде жаз:
{{
  "teaser": "экрандағы қысқа тақырып, 38 таңбадан аспасын",
  "headline": "жаңалықтың мәнін айтатын бір сөйлем, 8–14 сөз",
  "body": "жаңалықтың толық мазмұны: 3–4 қысқа сөйлем, барлығы 45–70 сөз"
}}"""


class ElevenLabsError(RuntimeError):
    pass


class ElevenLabsClient:
    def __init__(self, api_key: str, user_agent: str, timeout: int = 120):
        self.session = requests.Session()
        self.session.headers.update({"xi-api-key": api_key, "User-Agent": user_agent})
        self.timeout = timeout

    def speak(self, text: str, voice_id: str, model: str) -> dict:
        """Озвучка с таймкодами символов: {audio_base64, alignment: {characters, *_times_seconds}}."""
        resp = self.session.post(f"{ELEVEN}/text-to-speech/{voice_id}/with-timestamps", timeout=self.timeout,
                                 params={"output_format": "mp3_44100_128"},
                                 json={"text": text, "model_id": model,
                                       "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "style": 0.25}})
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail")
                msg = detail.get("message") if isinstance(detail, dict) else str(detail)
            except ValueError:
                msg = resp.text[:300]
            raise ElevenLabsError(f"ElevenLabs {resp.status_code}: {msg}")
        data = resp.json()
        if not data.get("audio_base64") or not data.get("alignment"):
            raise ElevenLabsError("ElevenLabs вернул ответ без звука или таймкодов")
        return data


def lexical_text(node: Any, limit: int = 3000) -> str:
    """Текст статьи из Lexical JSON (абзацы через перевод строки)."""
    out: list[str] = []

    def walk(n: Any) -> None:
        if isinstance(n, dict):
            if n.get("type") == "text" and n.get("text"):
                out.append(n["text"])
            for ch in n.get("children") or []:
                walk(ch)
            if n.get("type") in ("paragraph", "heading", "listitem"):
                out.append("\n")
        elif isinstance(n, list):
            for ch in n:
                walk(ch)

    walk((node or {}).get("root") if isinstance(node, dict) else node)
    text = re.sub(r"\n{2,}", "\n", "".join(out)).strip()
    return text[:limit]


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("«", "").replace("»", "")).strip()


def write_script(llm: LLM, model: str, article: dict) -> dict:
    data = complete_json(llm, model=model, system=SCRIPT_SYSTEM, max_tokens=1500, temperature=0.5,
                         prompt=SCRIPT_PROMPT.format(title=article.get("title", ""), excerpt=article.get("excerpt", ""),
                                                     body=lexical_text(article.get("content"))))
    teaser = _clean(data.get("teaser") or article.get("title", ""))
    headline, body = _clean(data.get("headline", "")), _clean(data.get("body", ""))
    if len(body.split()) < 15 or not headline:
        raise LLMError("ИИ вернул слишком короткий текст для рилса")
    if len(teaser) > 42:
        teaser = teaser[:41].rstrip() + "…"
    intro = f"Сәлеметсіз бе! {SPOKEN_BRAND} жаңалықтары. {headline}"
    if not intro.endswith((".", "!", "?")):
        intro += "."
    return {"teaser": teaser, "intro": intro, "body": body, "outro": OUTRO}


def _ok_to_render(rec: dict | None, now: datetime) -> bool:
    if not rec:
        return True
    if rec["status"] == "posted" or rec["attempts"] >= MAX_ATTEMPTS:
        return False
    if rec["status"] == "rendering":
        updated = _parse(rec.get("updated_at"))
        return bool(updated and now - updated > STALE_RENDER)
    return True


def pick_article(cms: CMSClient, db: Database, settings: dict, now: datetime) -> dict | None:
    since = now - timedelta(hours=int(settings.get("lookbackHours") or 12))
    cands = [a for a in cms.published_since(since.isoformat()) if a.get("coverImage") and _ok_to_render(db.social_get(a["id"], REEL), now)]
    if not cands:
        return None
    # главная новость: самая важная, при равенстве — самая свежая
    return max(cands, key=lambda a: (float(a.get("importanceScore") or 0), a.get("publishedAt") or ""))


def _media_url(media: Any, site_url: str) -> str | None:
    if not isinstance(media, dict):
        return None
    url = (media.get("sizes") or {}).get("hero", {}).get("url") or media.get("url")
    if not url:
        return None
    return url if url.startswith("http") else f"{site_url}{url}"


KZ_MONTHS = ["ҚАҢТАР", "АҚПАН", "НАУРЫЗ", "СӘУІР", "МАМЫР", "МАУСЫМ", "ШІЛДЕ", "ТАМЫЗ", "ҚЫРКҮЙЕК", "ҚАЗАН", "ҚАРАША", "ЖЕЛТОҚСАН"]


def prepare_reel(cfg: Config, db: Database, cms: CMSClient, llm: LLM | None, eleven: ElevenLabsClient | None = None,
                 now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    s = cms.reels_settings()
    if not s.get("enabled"):
        return {"skip": "disabled"}
    key = (s.get("elevenlabsApiKey") or "").strip()
    if not key:
        return {"skip": "no elevenlabs key"}
    if db.social_count_since(REEL, (now - timedelta(hours=24)).isoformat()) >= int(s.get("perDay") or 3):
        return {"skip": "daily limit"}
    if llm is None:
        return {"skip": "no llm"}
    article = pick_article(cms, db, s, now)
    if not article:
        return {"skip": "no fresh articles"}
    aid = article["id"]
    db.social_save(aid, REEL, "rendering", attempt=True)
    try:
        script = write_script(llm, cfg.writer_model, article)
        gender = "f" if s.get("presenter") == "f" else "m"
        voice = (s.get("voiceId") or "").strip() or DEFAULT_VOICES[gender]
        text = f"{script['intro']} {script['body']} {script['outro']}"
        eleven = eleven or ElevenLabsClient(key, cfg.user_agent)
        tts = eleven.speak(text, voice, (s.get("model") or "eleven_v3").strip())
    except (LLMError, ElevenLabsError, requests.RequestException) as exc:
        msg = str(exc)[:300]
        db.social_save(aid, REEL, "failed", error=msg)
        cms.update_reels_settings({"lastError": f"{now:%d.%m %H:%M} UTC: {msg}"})
        db.log_run("reel_prepare", {"article": aid, "error": msg})
        return {"skip": "error", "error": msg}
    local = now.astimezone(timezone(timedelta(hours=5)))
    cat = article.get("category")
    job = {
        "article_id": aid, "slug": article.get("slug"), "title": article.get("title"),
        "category": (cat.get("name") if isinstance(cat, dict) else None) or "Технология",
        "teaser": script["teaser"], "date_label": f"{local.day} {KZ_MONTHS[local.month - 1]}",
        "photo_url": _media_url(article.get("coverImage"), cfg.site_url), "presenter": gender,
        # где в тексте начинаются новость и концовка — по ним сцены переключаются
        "intro_chars": len(script["intro"]) + 1, "outro_char": len(script["intro"]) + 1 + len(script["body"]) + 1,
        "text": text, "audio_base64": tts["audio_base64"], "alignment": tts["alignment"],
    }
    db.log_run("reel_prepare", {"article": aid, "chars": len(text)})
    return {"job": job}


# --- публикация ------------------------------------------------------------------------------------
def _ig_reel(cfg: Config, s: dict, article: dict, video_url: str, client: InstagramClient | None) -> str:
    token, ig_id = s.get("accessToken") or "", s.get("igUserId") or ""
    if not token or not ig_id:
        raise InstagramError("Instagram не подключён")
    client = client or InstagramClient(cfg.user_agent, timeout=60)
    caption = build_caption(article, cfg.site_url, s.get("hashtags") or "")
    params: dict[str, Any] = {"media_type": "REELS", "video_url": video_url, "caption": caption, "share_to_feed": "true"}
    try:
        container = client._call("POST", f"{ig_id}/media", token, is_ai_generated="true", **params)["id"]
    except InstagramError as exc:
        if "is_ai_generated" not in str(exc):
            raise
        container = client._call("POST", f"{ig_id}/media", token, **params)["id"]
    client.wait_ready(str(container), token, timeout=200, pause=6)
    media_id = client.publish(ig_id, token, str(container))
    return client.permalink(media_id, token) or media_id


def _tg_reel(cfg: Config, s: dict, article: dict, video_url: str, client: TelegramClient | None) -> str:
    token, channel = (s.get("botToken") or "").strip(), normalize_channel(s.get("channel") or "")
    if not token or not channel:
        raise TelegramError("Telegram не подключён")
    client = client or TelegramClient(token, cfg.user_agent, timeout=120)
    url = article_url(article, cfg.site_url)
    msg = client._call("sendVideo", chat_id=channel, video=video_url, caption=build_post(article, cfg.site_url),
                       parse_mode="HTML", supports_streaming=True, width=1080, height=1920,
                       reply_markup={"inline_keyboard": [[{"text": "Толығы оқу →", "url": url}]]})
    mid = str(msg.get("message_id") or "")
    return f"https://t.me/{channel[1:]}/{mid}" if channel.startswith("@") else mid


def _tt_reel(cfg: Config, s: dict, article: dict, video_url: str) -> str:
    """Черновик видео в TikTok (FILE_UPLOAD: файл скачиваем и загружаем одним куском)."""
    token = s.get("accessToken") or ""
    if not token:
        raise RuntimeError("TikTok не подключён")
    video = requests.get(video_url, timeout=120).content
    size = len(video)
    init = requests.post("https://open.tiktokapis.com/v2/post/publish/inbox/video/init/", timeout=60,
                         headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"},
                         json={"source_info": {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": size,
                                               "total_chunk_count": 1}}).json()
    err = init.get("error") or {}
    if err.get("code") not in (None, "", "ok"):
        raise RuntimeError(f"TikTok: {err.get('code')} {err.get('message') or ''}")
    data = init.get("data") or {}
    put = requests.put(data["upload_url"], data=video, timeout=300,
                       headers={"Content-Type": "video/mp4", "Content-Range": f"bytes 0-{size - 1}/{size}"})
    if put.status_code >= 400:
        raise RuntimeError(f"TikTok upload {put.status_code}: {put.text[:200]}")
    return str(data.get("publish_id") or "")


def publish_reel(cfg: Config, db: Database, cms: CMSClient, payload: dict, ig: InstagramClient | None = None,
                 tg: TelegramClient | None = None, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    aid = payload.get("article_id")
    if not aid:
        return {"error": "article_id required"}
    if payload.get("error"):
        msg = str(payload["error"])[:300]
        db.social_save(aid, REEL, "failed", error=msg)
        cms.update_reels_settings({"lastError": f"{now:%d.%m %H:%M} UTC: сборка видео: {msg}"})
        db.log_run("reel_publish", {"article": aid, "error": msg})
        return {"failed": msg}
    video_url = payload["video_url"]
    s = cms.reels_settings()
    article = cms.article(aid)
    db.social_save(aid, REEL, "posted", media_id=video_url)
    result: dict[str, Any] = {"article": aid, "video": video_url}
    errors: list[str] = []
    targets = [("instagram", s.get("publishInstagram", True), lambda: _ig_reel(cfg, cms.instagram_settings(), article, video_url, ig)),
               ("telegram", s.get("publishTelegram", True), lambda: _tg_reel(cfg, cms.telegram_settings(), article, video_url, tg)),
               ("tiktok", s.get("publishTikTok", False), lambda: _tt_reel(cfg, cms.tiktok_settings(), article, video_url))]
    for name, on, fn in targets:
        if not on:
            continue
        net = f"reel_{name}"
        rec = db.social_get(aid, net)
        if rec and rec["status"] == "posted":
            continue
        try:
            db.social_save(aid, net, "posting", attempt=True)
            link = fn()
            db.social_save(aid, net, "posted", permalink=link)
            result[name] = link
        except Exception as exc:  # noqa: BLE001 — одна сеть не должна мешать другим
            msg = str(exc)[:300]
            log.warning("Рилс %s → %s: %s", aid, name, msg)
            db.social_save(aid, net, "failed", error=msg)
            errors.append(f"{name}: {msg}")
    update: dict[str, Any] = {"lastReelAt": now.isoformat(), "lastVideoUrl": video_url}
    update["lastError"] = f"{now:%d.%m %H:%M} UTC: " + "; ".join(errors) if errors else ""
    cms.update_reels_settings(update)
    result["errors"] = errors
    db.log_run("reel_publish", result)
    return result
