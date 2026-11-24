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

import html
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from .cms import CMSClient
from .config import Config
from .db import Database
from .llm import LLM, LLMError, complete_json
from .speech import for_speech, parse_dictionary
from .social import InstagramClient, InstagramError, _parse, build_caption
from .telegram import TelegramClient, TelegramError, article_url, build_post, normalize_channel

log = logging.getLogger(__name__)

REEL = "reel"
MAX_ATTEMPTS = 2
STALE_RENDER = timedelta(hours=2)
ELEVEN = "https://api.elevenlabs.io/v1"
DEFAULT_VOICES = {"f": "EXAVITQu4vr4xnSDxMaL", "m": "JBFqnCBsd6RMkjVDRZzb"}  # премиум-голоса ElevenLabs по умолчанию

SCRIPT_SYSTEM = (
    "Сен — Instagram Reels пен TikTok-қа арналған қазақ тіліндегі IT-жаңалықтар арнасының сценаристісің. "
    "Мақсатың — адам бірінші секундта тоқтап, соңына дейін қарап, пікір жазып, арнаға жазылатындай мәтін. "
    "Жанды сөйлеу тілінде, қысқа сөйлемдермен, көрерменге тек «сіз» деп тікелей айт (ешқашан «сен» емес). Кіріспе, сәлемдесу, "
    "«бүгін біз айтамыз» сияқты бос сөз жоқ — бірден іске. Тек мақаладағы фактілерді қолдан, ойдан қоспа, "
    "асыра сілтеме. ДӘЛДІК: кім кімге не істегенін мақаладағыдай нақты жаз — компанияның әрекетін оның иесіне "
    "немесе басшысына телме, «сотқа берді» мен «сотталды», «жоспарлап отыр» мен «жасады» сияқты ұғымдарды шатастырма. "
    "Сот талабы, айыптау, күдік — дәлелденген факт емес: оларды міндетті түрде иесіне сілтеп жаз "
    "(«арызға сәйкес», «прокурорлардың айтуынша», «компания айыпталуда»). Хук та осы ережеге бағынады. Сандарды ЦИФРМЕН жаз (77–80%, 2026, 1,5 млн емес — 1 500 000), мақаладағы мәнін өзгертпе: аралық болса — аралықты толық бер, жуықтама. Пайыздан кейін септік жалғауын қос: «91–94%-ға дейін», «80%-дан». Сөзбен жазуды бағдарлама өзі жасайды. Сілтеме, эмодзи, хэштег жазба. "
    "Ағылшын атаулары өз қалпында."
)
SCRIPT_PROMPT = """Мақала:
Тақырып: {title}
Анонс: {excerpt}
Мәтін: {body}

Рилс сценарийін JSON түрінде жаз (барлығы 75–110 сөз, 35–45 секунд):
{{
  "hook": "алғашқы 2 секундта тоқтататын бір сөйлем: таңғалдыратын факт, сан немесе сұрақ (6–14 сөз)",
  "lead": "не болғанын бір сөйлеммен түсіндір (10–18 сөз)",
  "body": "неге маңызды: мәні, қарапайым адамға, Қазақстанға не өзгереді, қызықты деталь; 3–4 қысқа сөйлем, 40–65 сөз",
  "question": "пікір жазуға шақыратын даулы немесе жеке сұрақ (6–12 сөз)",
  "subjects": ["нақты нысандар ағылшынша: компания, өнім, қала (1–3 атау, адам аты емес)"],
  "say": {{"мәтіндегі ӘРБІР латын әріпті атау": "дауыстап айтылуы кириллицамен: аббревиатура әріптеп, бос орынмен; атаудағы сан немесе рим цифры — ҚАЗАҚША сөзбен (мысалы: \"GTA VI\": \"Джи Ти Эй алты\", \"iPhone 17\": \"Айфон он жеті\", \"The Witness\": \"Зе Уитнес\", \"Dear Esther\": \"Дир Эстер\", \"Rockstar Games\": \"Рокстар Геймс\")"}},
  "broll": ["5 сұрау ағылшынша, мәтіндегі сөйлемдердің ретімен — әр сөйлемге бір кадр, 2–4 сөз", "…", "…", "…", "…"]
}}
subjects — бейнемұрағаттан нақты кадр іздеуге (мысалы: "Nvidia", "Stuttgart", "iPhone 17").
broll — стоктық бейнелерде (Pixabay) шынымен бар кадрлар: адамдардың әрекеті мен заттар, сөйлемнің мағынасына сай
(мысалы: "woman scrolling phone", "hands typing laptop", "judge gavel", "server room", "city traffic night",
"businessman signing document"). Абстрактілі ұғым ("lawsuit", "regulation") емес — көзбен көрінетін нәрсе.
Адам аты-жөні, бренд атауы болмасын (стоктағы бөтен адамды сол адам етіп көрсетпеу үшін)."""
SUBSCRIBE = "Пікіріңізді жазыңыз. Мұндай жаңалықтарды жіберіп алмау үшін жазылыңыз!"

PICK_PROMPT = """Төмендегі соңғы IT-жаңалықтардың ішінен Instagram Reels пен TikTok-та ең көп қаралатын, талқыланатын
бірін таңда: қарапайым адамға түсінікті, таңғалдыратын, күнделікті өмірге (смартфон, ақша, жұмыс, ЖИ, қауіпсіздік,
танымал брендтер) қатысты, пікір тудыратын. Тар салалық, құрғақ қаржы немесе тек мамандарға қызық жаңалықты таңдама.

{items}

JSON: {{"id": таңдалған жаңалықтың id-і (сан), "why": "неге — бір сөйлем"}}"""


class ElevenLabsError(RuntimeError):
    pass


class ElevenLabsClient:
    def __init__(self, api_key: str, user_agent: str, timeout: int = 120):
        self.session = requests.Session()
        self.session.headers.update({"xi-api-key": api_key, "User-Agent": user_agent})
        self.timeout = timeout

    def speak(self, text: str, voice_id: str, model: str, stability: float = 0.5) -> dict:
        """Озвучка с таймкодами символов: {audio_base64, alignment: {characters, *_times_seconds}}.
        stability: 0 — живее и эмоциональнее (v3 «Creative»), 0.5 — естественно, 1 — ровно."""
        resp = self.session.post(f"{ELEVEN}/text-to-speech/{voice_id}/with-timestamps", timeout=self.timeout,
                                 params={"output_format": "mp3_44100_128"},
                                 json={"text": text, "model_id": model,
                                       "voice_settings": {"stability": stability, "similarity_boost": 0.8, "style": 0.35}})
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

    def add_voice(self, name: str, audio: bytes, filename: str = "sample.mp3", description: str = "") -> str:
        """Мгновенный клон голоса (Instant Voice Cloning) по образцу. Возвращает voice_id."""
        resp = self.session.post(f"{ELEVEN}/voices/add", timeout=self.timeout,
                                 data={"name": name, "description": description, "remove_background_noise": "true"},
                                 files=[("files", (filename, audio, "audio/mpeg"))])
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail")
                msg = detail.get("message") if isinstance(detail, dict) else str(detail)
            except ValueError:
                msg = resp.text[:300]
            raise ElevenLabsError(f"ElevenLabs {resp.status_code}: {msg}")
        return str(resp.json()["voice_id"])


def clone_voice(cfg: Config, cms: CMSClient, payload: dict, eleven: ElevenLabsClient | None = None) -> dict:
    """Клон голоса диктора: образец лежит зашифрованным (Fernet) по ссылке, ключ приходит в запросе.
    Полученный voice_id записывается в настройки рилсов."""
    from cryptography.fernet import Fernet

    s = cms.reels_settings()
    key = (s.get("elevenlabsApiKey") or "").strip()
    if not key:
        return {"error": "no elevenlabs key"}
    raw = requests.get(payload["url"], timeout=60, headers={"User-Agent": cfg.user_agent})
    raw.raise_for_status()
    audio = Fernet(payload["fernet_key"].encode()).decrypt(raw.content)
    eleven = eleven or ElevenLabsClient(key, cfg.user_agent)
    vid = eleven.add_voice(payload.get("name") or "TechTalQ диктор", audio,
                           description="Диктор TechTalQ (с разрешения владельца голоса)")
    cms.update_reels_settings({"voiceId": vid})
    return {"voice_id": vid}


PEXELS = "https://api.pexels.com/videos/search"


def pexels_clips(api_key: str, queries: list[str], user_agent: str, want: int = 2, timeout: int = 30) -> list[dict]:
    """Вертикальные стоковые видео Pexels по запросам (бесплатная лицензия, без обязательного указания автора)."""
    clips: list[dict] = []
    seen: set[int] = set()
    for q in queries + ["person using smartphone", "hands typing laptop"]:
        if len(clips) >= want:
            break
        try:
            r = requests.get(PEXELS, timeout=timeout, headers={"Authorization": api_key, "User-Agent": user_agent},
                             params={"query": q, "orientation": "portrait", "size": "medium", "per_page": 12})
            r.raise_for_status()
        except requests.RequestException as exc:
            log.warning("Pexels «%s»: %s", q, exc)
            continue
        for v in r.json().get("videos") or []:
            if v.get("id") in seen or (v.get("duration") or 0) < 5:
                continue
            files = [f for f in v.get("video_files") or [] if f.get("file_type") == "video/mp4"
                     and (f.get("height") or 0) > (f.get("width") or 0) and 1000 <= (f.get("height") or 0) <= 2600]
            if not files:
                continue
            f = min(files, key=lambda f: abs((f.get("height") or 0) - 1920))
            seen.add(v["id"])
            clips.append({"url": f["link"], "query": q, "duration": v.get("duration"),
                          "credit": f"{(v.get('user') or {}).get('name') or 'автор'} / Pexels", "page": v.get("url")})
            break
    return clips


PIXABAY = "https://pixabay.com/api/videos/"
_STOP = {"the", "and", "with", "view", "closeup", "close", "shot", "scene", "background"}


def pixabay_clips(api_key: str, queries: list[str], user_agent: str, want: int = 2, timeout: int = 30) -> list[dict]:
    """Стоковые видео Pixabay (бесплатная лицензия Pixabay). Чаще горизонтальные — в рилсе кадрируются по центру."""
    clips: list[dict] = []
    seen: set[int] = set()
    for q in queries + ["person using smartphone", "hands typing laptop"]:
        if len(clips) >= want:
            break
        try:
            r = requests.get(PIXABAY, timeout=timeout, headers={"User-Agent": user_agent},
                             params={"key": api_key, "q": q[:100], "per_page": 10, "safesearch": "true"})
            r.raise_for_status()
            hits = r.json().get("hits") or []
        except (requests.RequestException, ValueError) as exc:
            log.warning("Pixabay «%s»: %s", q, str(exc).replace(api_key, "***"))
            continue
        words = {w for w in re.findall(r"[a-z]{3,}", q.lower()) if w not in _STOP}
        vert = lambda h: any((v or {}).get("height", 0) > (v or {}).get("width", 0) for v in (h.get("videos") or {}).values())  # noqa: E731
        hits = sorted(hits, key=lambda h: not vert(h))  # вертикальные — первыми, порядок релевантности внутри сохраняем
        for h in hits:
            if h.get("id") in seen or (h.get("duration") or 0) < 5:
                continue
            tags = str(h.get("tags") or "").lower()
            if words and not any(w in tags for w in words):  # Pixabay находит «похожее» — берём только по тегам
                continue
            vids = h.get("videos") or {}
            # вертикальные — в приоритете; иначе самое крупное (кадрируем)
            files = [v for v in (vids.get(k) for k in ("large", "medium")) if v and v.get("url")]
            if not files:
                continue
            f = max(files, key=lambda v: ((v.get("height") or 0) > (v.get("width") or 0), v.get("height") or 0))
            if (f.get("height") or 0) < 720:
                continue
            seen.add(h["id"])
            clips.append({"url": f["url"], "query": q, "duration": h.get("duration"), "page": h.get("pageURL"),
                          "credit": f"{h.get('user') or 'автор'} / Pixabay"})
            break
    return clips


# --- подбор кадров по смыслу ---------------------------------------------------------------------------
def stock_candidates(queries: list[str], user_agent: str, pexels_key: str = "", pixabay_key: str = "",
                     per_query: int = 4, timeout: int = 25) -> list[dict]:
    """Кандидаты со стоков с описанием (теги Pixabay, название ролика Pexels) — дальше их отбирает ИИ."""
    out: list[dict] = []
    seen: set[str] = set()
    for q in queries:
        if pexels_key:
            try:
                r = requests.get(PEXELS, timeout=timeout, headers={"Authorization": pexels_key, "User-Agent": user_agent},
                                 params={"query": q, "orientation": "portrait", "size": "medium", "per_page": per_query})
                r.raise_for_status()
                for v in r.json().get("videos") or []:
                    files = [f for f in v.get("video_files") or [] if f.get("file_type") == "video/mp4"
                             and (f.get("height") or 0) > (f.get("width") or 0) and 1000 <= (f.get("height") or 0) <= 2600]
                    key = f"px{v.get('id')}"
                    if not files or key in seen or (v.get("duration") or 0) < 4:
                        continue
                    f = min(files, key=lambda f: abs((f.get("height") or 0) - 1920))
                    slug = re.sub(r"-\d+/?$", "", str(v.get("url") or "").rstrip("/").rsplit("/", 1)[-1]).replace("-", " ")
                    seen.add(key)
                    out.append({"key": key, "url": f["link"], "query": q, "desc": slug, "vertical": True,
                                "duration": v.get("duration"), "page": v.get("url"),
                                "credit": f"{(v.get('user') or {}).get('name') or 'автор'} / Pexels"})
            except (requests.RequestException, ValueError) as exc:
                log.warning("Pexels «%s»: %s", q, exc)
        if pixabay_key:
            try:
                r = requests.get(PIXABAY, timeout=timeout, headers={"User-Agent": user_agent},
                                 params={"key": pixabay_key, "q": q[:100], "per_page": 10, "safesearch": "true"})
                r.raise_for_status()
                n = 0
                for h in r.json().get("hits") or []:
                    key = f"pb{h.get('id')}"
                    vids = h.get("videos") or {}
                    files = [v for v in (vids.get(k) for k in ("large", "medium")) if v and v.get("url")]
                    if not files or key in seen or (h.get("duration") or 0) < 4:
                        continue
                    f = max(files, key=lambda v: ((v.get("height") or 0) > (v.get("width") or 0), v.get("height") or 0))
                    if (f.get("height") or 0) < 720:
                        continue
                    seen.add(key)
                    out.append({"key": key, "url": f["url"], "query": q, "desc": str(h.get("tags") or ""),
                                "vertical": (f.get("height") or 0) > (f.get("width") or 0), "duration": h.get("duration"),
                                "page": h.get("pageURL"), "credit": f"{h.get('user') or 'автор'} / Pixabay"})
                    n += 1
                    if n >= per_query:
                        break
            except (requests.RequestException, ValueError) as exc:
                log.warning("Pixabay «%s»: %s", q, str(exc).replace(pixabay_key, "***"))
    return out


_VIDEO_URL = re.compile(r"""https?://[^\s"'<>()]+?\.(?:mp4|webm|m4v)(?:\?[^\s"'<>()]*)?""", re.I)
_SKIP_VIDEO = ("preview", "thumb", "teaser-small", "/ads/", "doubleclick", "advert")


def source_videos(article: dict, user_agent: str, timeout: int = 20, limit: int = 3) -> list[dict]:
    """Видео из самой новости: прямые файлы (mp4/webm) со страниц первоисточников — пресс-релизы, блоги
    компаний (Apple Newsroom, OpenAI, NVIDIA…). Встроенные YouTube/Vimeo не берём."""
    out: list[dict] = []
    for src in article.get("sources") or []:
        url, name = (src or {}).get("url"), (src or {}).get("name") or ""
        if not url or len(out) >= limit:
            continue
        try:
            r = requests.get(url, timeout=timeout, headers={"User-Agent": user_agent, "Accept": "text/html"})
            if r.status_code >= 400 or "html" not in r.headers.get("Content-Type", "html"):
                continue
            html_text = r.text[:2_000_000]
        except requests.RequestException as exc:
            log.info("Видео из источника %s: %s", url, exc)
            continue
        found: list[str] = []
        # og:video и VideoObject в JSON-LD — главное видео страницы; затем <video>/<source>
        for m in re.finditer(r'<meta[^>]+(?:property|name)=["\'](?:og:video(?::secure_url|:url)?|twitter:player:stream)["\'][^>]*>', html_text, re.I):
            c = re.search(r'content=["\']([^"\']+)', m.group(0))
            if c:
                found.append(c.group(1))
        found += re.findall(r'"contentUrl"\s*:\s*"([^"]+)"', html_text)
        found += re.findall(r'<(?:video|source)[^>]+src=["\']([^"\']+)', html_text, re.I)
        found += _VIDEO_URL.findall(html_text)
        seen: set[str] = set()
        for v in found:
            v = html.unescape(v.replace("\\/", "/")).strip()
            if v.startswith("//"):
                v = "https:" + v
            elif v.startswith("/"):
                v = re.match(r"https?://[^/]+", url).group(0) + v
            if v in seen or not _VIDEO_URL.fullmatch(v.split("#")[0]) or any(x in v.lower() for x in _SKIP_VIDEO):
                continue
            seen.add(v)
            try:  # файл должен реально отдаваться и быть не крошечным (не иконка-анимация)
                h = requests.head(v, timeout=timeout, allow_redirects=True, headers={"User-Agent": user_agent})
                size = int(h.headers.get("Content-Length") or 0)
                if h.status_code >= 400 or (size and (size < 300_000 or size > 150_000_000)):
                    continue
            except requests.RequestException:
                continue
            out.append({"key": f"src{len(out)}", "url": v, "query": "первоисточник", "desc": f"видео из {name}",
                        "vertical": False, "page": url, "credit": name or "первоисточник", "source": True})
            if len(out) >= limit:
                break
    return out


NASA_API = "https://images-api.nasa.gov"


def nasa_candidates(queries: list[str], user_agent: str, per_query: int = 2, timeout: int = 25) -> list[dict]:
    """Видео NASA (общественное достояние) — для новостей о космосе; уместность решает ИИ."""
    out: list[dict] = []
    for q in queries[:4]:
        try:
            r = requests.get(f"{NASA_API}/search", timeout=timeout, headers={"User-Agent": user_agent},
                             params={"q": q, "media_type": "video", "page_size": per_query * 3})
            r.raise_for_status()
            items = (r.json().get("collection") or {}).get("items") or []
        except (requests.RequestException, ValueError) as exc:
            log.info("NASA «%s»: %s", q, exc)
            continue
        n = 0
        for it in items:
            d = (it.get("data") or [{}])[0]
            nid = d.get("nasa_id")
            if not nid or any(c.get("key") == f"nasa{nid}" for c in out):
                continue
            try:
                assets = requests.get(f"{NASA_API}/asset/{requests.utils.quote(nid)}", timeout=timeout,
                                      headers={"User-Agent": user_agent}).json()
                files = [a.get("href") for a in (assets.get("collection") or {}).get("items") or []]
            except (requests.RequestException, ValueError):
                continue
            mp4 = next((f for tag in ("~mobile.mp4", "~medium.mp4", "~small.mp4") for f in files if f and f.endswith(tag)), None)
            if not mp4:
                continue
            out.append({"key": f"nasa{nid}", "url": mp4.replace("http://", "https://"), "query": q,
                        "desc": f"NASA: {d.get('title', '')} — {', '.join((d.get('keywords') or [])[:6])}",
                        "vertical": False, "page": f"https://images.nasa.gov/details/{nid}", "credit": "NASA"})
            n += 1
            if n >= per_query:
                break
    return out


CLIP_PROMPT = """Рилс-новость: «{title}».
Предложения диктора (по порядку) и что нужно показать:
{sentences}

Кандидаты — стоковые видео (id: описание/теги{vert}):
{cands}

Для каждого предложения выбери ОДИН ролик, который по смыслу подходит к теме новости и к этому предложению.
Строго: не бери кадры, не связанные с темой (природа, еда, животные и т.п. в IT-новости), и никогда — курение,
алкоголь, оружие, кровь, обнажёнку. Лучше null, чем случайный кадр. Вертикальные (V) предпочтительнее.
Один ролик — не больше одного раза.
JSON: {{"picks": [id или null для каждого предложения по порядку]}}"""


def choose_clips(llm: LLM, model: str, title: str, sentences: list[str], cands: list[dict]) -> list[dict]:
    if not cands:
        return []
    lines = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(sentences))
    cl = "\n".join(f"{c['key']}: {c['desc'][:120]}{' (V)' if c.get('vertical') else ''}" for c in cands)
    try:
        data = complete_json(llm, model=model, system="Ты — бильд-редактор новостных рилсов.", max_tokens=600,
                             temperature=0.1, prompt=CLIP_PROMPT.format(title=title, sentences=lines, cands=cl, vert="; V — вертикальный"))
    except LLMError as exc:
        log.warning("Рилс: отбор кадров ИИ не удался: %s", exc)
        return []
    picks = data.get("picks") if isinstance(data, dict) else data if isinstance(data, list) else []
    by_key, used, res = {c["key"]: c for c in cands}, set(), []
    for k in picks or []:
        c = by_key.get(str(k)) if k else None
        if c and c["key"] not in used:
            used.add(c["key"])
            res.append(c)
    return res


COMMONS_API = "https://commons.wikimedia.org/w/api.php"


def _transcoded(url: str, height: int) -> str:
    """Оригинал на Commons → готовая копия WebM нужной высоты (Commons хранит их рядом)."""
    m = re.match(r"(https://upload\.wikimedia\.org/wikipedia/commons)/(\w/\w\w)/(.+)$", url)
    if not m:
        return url
    return f"{m.group(1)}/transcoded/{m.group(2)}/{m.group(3)}/{m.group(3)}.{height}p.vp9.webm"


def commons_clips(subjects: list[str], user_agent: str, want: int = 2, timeout: int = 25) -> list[dict]:
    """Видео со свободной лицензией с Wikimedia Commons по точным названиям из новости (с указанием автора)."""
    from .images import _strip, license_ok
    sess = requests.Session()
    sess.headers["User-Agent"] = user_agent
    clips: list[dict] = []
    seen: set[str] = set()
    for q in subjects:
        if len(clips) >= want:
            break
        try:
            r = sess.get(COMMONS_API, timeout=timeout, params={
                "action": "query", "format": "json", "formatversion": "2", "generator": "search",
                "gsrsearch": f"{q} filetype:video", "gsrnamespace": "6", "gsrlimit": "10",
                "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata",
                "iiextmetadatafilter": "LicenseShortName|UsageTerms|Artist|Credit|Restrictions"})
            r.raise_for_status()
            pages = sorted(r.json().get("query", {}).get("pages", []), key=lambda p: p.get("index", 0))
        except (requests.RequestException, ValueError) as exc:
            log.warning("Commons видео «%s»: %s", q, exc)
            continue
        for p in pages:
            info = (p.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})
            val = lambda k: (meta.get(k) or {}).get("value", "")  # noqa: E731
            short = _strip(val("LicenseShortName"))
            dur = float(info.get("duration") or 0)
            if (not license_ok(short, _strip(val("UsageTerms"))) or "personality" in _strip(val("Restrictions")).lower()
                    or not str(info.get("mime", "")).startswith(("video/", "application/ogg"))
                    or (dur and dur < 4) or info.get("url") in seen):
                continue
            url = None
            for h in (720, 480):
                cand = _transcoded(info.get("url", ""), h)
                try:
                    if sess.head(cand, timeout=timeout, allow_redirects=True).status_code == 200:
                        url = cand
                        break
                except requests.RequestException:
                    pass
            if not url:
                continue
            seen.add(info["url"])
            author = (_strip(val("Artist")) or _strip(val("Credit")) or "белгісіз автор")[:60]
            clips.append({"url": url, "query": q, "duration": dur or None, "page": info.get("descriptionurl"),
                          "credit": f"{author} / Wikimedia Commons, {short}"})
            break
    return clips


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


TAGS_RULE = ("\nҮн тегтері: hook, lead, body, question ішінде ElevenLabs v3 тегтерін қолдан — сөйлем алдында "
             "[excited], [curious], [serious], [surprised], [thoughtful] немесе үзіліс үшін [pause]. Әр өріске 1–2 тегтен "
             "артық емес, тегтер тек ағылшынша, төртбұрышты жақшада.")


def write_script(llm: LLM, model: str, article: dict, tags: bool = False) -> dict:
    data = complete_json(llm, model=model, system=SCRIPT_SYSTEM, max_tokens=2000, temperature=0.7,
                         prompt=SCRIPT_PROMPT.format(title=article.get("title", ""), excerpt=article.get("excerpt", ""),
                                                     body=lexical_text(article.get("content"))) + (TAGS_RULE if tags else ""))
    if isinstance(data, list):  # иногда ИИ оборачивает ответ в список
        data = next((x for x in data if isinstance(x, dict)), {})
    hook, lead = _clean(data.get("hook", "")), _clean(data.get("lead", ""))
    body, question = _clean(data.get("body", "")), _clean(data.get("question", ""))
    if not hook or not lead or len(body.split()) < 15:
        raise LLMError("ИИ вернул неполный сценарий рилса")
    end = lambda x: x if x.endswith((".", "!", "?", "…")) else x + "."  # noqa: E731
    hook, lead, body = end(hook), end(lead), end(body)
    # на экране — ровно то, что говорит диктор (без тегов эмоций)
    teaser = re.sub(r"\s*\[[^\]]*\]\s*", " ", hook).strip()
    if question and not question.endswith("?"):
        question = question.rstrip(".!") + "?"
    broll = [_clean(q)[:60] for q in (data.get("broll") or []) if isinstance(q, str) and q.strip() and q.strip() != "…"][:6]
    subjects = [_clean(q)[:60] for q in (data.get("subjects") or []) if isinstance(q, str) and q.strip()][:3]
    raw_say = data.get("say") if isinstance(data.get("say"), dict) else {}
    say = {str(k).strip(): str(v).strip() for k, v in raw_say.items()
           if str(k).strip() and str(v).strip() and re.search(r"[A-Za-z]", str(k))}
    return {"teaser": teaser, "hook": hook, "intro": f"{hook} {lead}", "body": body, "say": say,
            "outro": f"{question} {SUBSCRIBE}".strip(), "broll": broll, "subjects": subjects}


def _ok_to_render(rec: dict | None, now: datetime, force: bool = False) -> bool:
    if not rec:
        return True
    if force and rec["status"] in ("preview", "failed"):  # ручной предпросмотр можно пересобрать
        return True
    if rec["status"] in ("posted", "preview") or rec["attempts"] >= MAX_ATTEMPTS:
        return False
    if rec["status"] == "rendering":
        updated = _parse(rec.get("updated_at"))
        return bool(updated and now - updated > STALE_RENDER)
    return True


def pick_article(cms: CMSClient, db: Database, settings: dict, now: datetime, llm: LLM | None = None,
                 model: str = "", force: bool = False) -> dict | None:
    since = now - timedelta(hours=int(settings.get("lookbackHours") or 12))
    cands = [a for a in cms.published_since(since.isoformat()) if a.get("coverImage") and _ok_to_render(db.social_get(a["id"], REEL), now, force)]
    if not cands:
        return None
    cands.sort(key=lambda a: (float(a.get("importanceScore") or 0), a.get("publishedAt") or ""), reverse=True)
    if llm is not None and len(cands) > 1:
        top = cands[:12]
        items = "\n".join(f"id={a['id']}: {a.get('title', '')} — {(a.get('excerpt') or '')[:200]}" for a in top)
        try:
            pick = complete_json(llm, model=model, system="Сен — вирустық контент редакторысың.", max_tokens=300,
                                 temperature=0.2, prompt=PICK_PROMPT.format(items=items))
            if isinstance(pick, list):
                pick = next((x for x in pick if isinstance(x, dict)), {})
            chosen = next((a for a in top if str(a["id"]) == str(pick.get("id"))), None)
            if chosen:
                log.info("Рилс: выбрана статья %s — %s", chosen["id"], pick.get("why"))
                return chosen
        except LLMError as exc:
            log.warning("Рилс: выбор новости ИИ не удался: %s", exc)
    return cands[0]


def _media_url(media: Any, site_url: str) -> str | None:
    if not isinstance(media, dict):
        return None
    url = (media.get("sizes") or {}).get("hero", {}).get("url") or media.get("url")
    if not url:
        return None
    return url if url.startswith("http") else f"{site_url}{url}"


KZ_MONTHS = ["ҚАҢТАР", "АҚПАН", "НАУРЫЗ", "СӘУІР", "МАМЫР", "МАУСЫМ", "ШІЛДЕ", "ТАМЫЗ", "ҚЫРКҮЙЕК", "ҚАЗАН", "ҚАРАША", "ЖЕЛТОҚСАН"]


def prepare_reel(cfg: Config, db: Database, cms: CMSClient, llm: LLM | None, eleven: ElevenLabsClient | None = None,
                 now: datetime | None = None, force: bool = False) -> dict:
    """force — ручной запуск (предпросмотр): без проверки «Делать рилсы» и дневного лимита."""
    now = now or datetime.now(timezone.utc)
    s = cms.reels_settings()
    if not s.get("enabled") and not force:
        return {"skip": "disabled"}
    key = (s.get("elevenlabsApiKey") or "").strip()
    if not key:
        return {"skip": "no elevenlabs key"}
    if not force and db.social_count_since(REEL, (now - timedelta(hours=24)).isoformat()) >= int(s.get("perDay") or 3):
        return {"skip": "daily limit"}
    if llm is None:
        return {"skip": "no llm"}
    article = pick_article(cms, db, s, now, llm, cfg.writer_model, force)
    if not article:
        return {"skip": "no fresh articles"}
    aid = article["id"]
    db.social_save(aid, REEL, "rendering", attempt=True)
    try:
        script = write_script(llm, cfg.writer_model, article, tags=bool(s.get("audioTags")))
        gender = "f" if s.get("presenter") == "f" else "m"
        voice = (s.get("voiceId") or "").strip() or DEFAULT_VOICES[gender]
        # голосу — числа словами и бренды с произношением; длины частей считаем уже по озвучиваемому тексту
        say = {**(script.get("say") or {}), **parse_dictionary(s.get("pronunciations") or "")}
        script["say"] = say
        hook_s, shown = for_speech(script["hook"], script.get("say"))
        lead_s, m2 = for_speech(script["intro"][len(script["hook"]) + 1:], script.get("say"))
        body_s, m3 = for_speech(script["body"], script.get("say"))
        outro_s, m4 = for_speech(script["outro"], script.get("say"))
        shown.update(m2), shown.update(m3), shown.update(m4)
        intro_s = f"{hook_s} {lead_s}"
        text = f"{intro_s} {body_s} {outro_s}"
        eleven = eleven or ElevenLabsClient(key, cfg.user_agent)
        stability = {"creative": 0.0, "natural": 0.5, "robust": 1.0}.get(s.get("voiceStyle") or "natural", 0.5)
        tts = eleven.speak(text, voice, (s.get("model") or "eleven_v3").strip(), stability)
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
        "photo_credit": re.sub(r"^(Сурет|Фото|Photo)\s*:\s*", "", str((article.get("coverImage") or {}).get("credit") or "").split(" — ")[0]).strip()[:80],
        # где в тексте начинаются новость и концовка — по ним сцены переключаются
        "intro_chars": len(intro_s) + 1, "outro_char": len(intro_s) + 1 + len(body_s) + 1,
        "headline_char": len(hook_s) + 1,  # смена плана — на втором предложении вступления
        "display_map": shown,
        "show_presenter": bool(s.get("showPresenter")),  # выкл — без диктора, видео с первой секунды  # «Чат-Джи-Пи-Ти» в субтитрах → «ChatGPT»
        # бегущая строка — другие свежие заголовки
        "ticker": [a.get("title") for a in cms.published_since((now - timedelta(hours=24)).isoformat())
                   if a.get("id") != aid and a.get("title")][-6:][::-1],
        "text": text, "audio_base64": tts["audio_base64"], "alignment": tts["alignment"],
        "queries": {"subjects": script.get("subjects"), "broll": script.get("broll")},
    }
    # видео: как в новостных рилсах — вертикальные стоковые кадры по одному на предложение. Pexels (больше всего
    # вертикальных) → Pixabay → Commons (точные названия, но обычно горизонтально)
    queries = script.get("broll") or []
    sentences = [x for x in re.split(r"(?<=[.!?…])\s+", f"{script['intro']} {script['body']}") if x.strip()]
    sentences = [re.sub(r"\[[^\]]*\]\s*", "", x) for x in sentences][:len(queries) or 6]
    cands = stock_candidates(queries, cfg.user_agent, (s.get("pexelsApiKey") or "").strip(),
                             (s.get("pixabayApiKey") or "").strip())
    space = any(w in f"{article.get('title', '')} {' '.join(queries)}".lower()
                for w in ("nasa", "space", "ғарыш", "spacex", "rocket", "зымыран", "satellite", "спутник", "starlink", "moon", "mars", "марс"))
    if space:
        cands += nasa_candidates((script.get("subjects") or []) + queries, cfg.user_agent)
    own = source_videos(article, cfg.user_agent)  # видео из самой новости — лучшие кадры, идут первыми
    clips = own + choose_clips(llm, cfg.writer_model, article.get("title") or "", sentences[len(own):] or sentences, cands)
    log.info("Рилс: видео из источника %d, кандидатов со стоков %d", len(own), len(cands))
    if len(clips) < 3 and script.get("subjects"):
        clips += commons_clips(script["subjects"], cfg.user_agent, want=min(2, 6 - len(clips)))
    job["broll"] = clips[:6]
    db.log_run("reel_prepare", {"article": aid, "chars": len(text), "broll": len(job.get("broll") or [])})
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
    msg = client.send_video_file(channel, video_url, caption=build_post(article, cfg.site_url),
                       parse_mode="HTML", supports_streaming=True, width=1080, height=1920,
                       reply_markup={"inline_keyboard": [[{"text": "Толық оқу →", "url": url}]]})
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


def review_caption(article: dict, site_url: str, teaser: str = "", hashtags: str = "") -> str:
    """Готовый текст для ручной публикации в Instagram: хук + обычная подпись."""
    base = build_caption(article, site_url, hashtags)
    hook = (teaser or "").strip()
    return f"{hook}\n\n{base}" if hook and hook not in base else base


def _review_reel(cfg: Config, s: dict, article: dict, video_url: str, teaser: str, client: TelegramClient | None) -> str:
    """Присылает готовый рилс и текст подписи в личный чат — для ручной публикации в Instagram."""
    token, chat = (s.get("_botToken") or "").strip(), (s.get("reviewChatId") or "").strip()
    if not token or not chat:
        raise TelegramError("не задан чат для рилсов или бот Telegram")
    client = client or TelegramClient(token, cfg.user_agent, timeout=120)
    msg = client.send_video_file(chat, video_url, supports_streaming=True, width=1080, height=1920,
                       caption=f"🎬 Рилс для Instagram\n{(article.get('title') or '')[:900]}")
    if not s.get("_skipCaption"):
        client._call("sendMessage", chat_id=chat, text=review_caption(article, cfg.site_url, teaser, s.get("_hashtags") or ""),
                     disable_web_page_preview=True)
    return str(msg.get("message_id") or "")


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
    if payload.get("preview_url"):
        db.social_save(aid, REEL, "preview", media_id=payload["preview_url"])
        db.log_run("reel_publish", {"article": aid, "preview": payload["preview_url"]})
        return {"preview": payload["preview_url"]}
    video_url = payload["video_url"]
    s = cms.reels_settings()
    article = cms.article(aid)
    if not payload.get("review_only"):
        db.social_save(aid, REEL, "posted", media_id=video_url)
    result: dict[str, Any] = {"article": aid, "video": video_url}
    errors: list[str] = []
    targets = [("instagram", s.get("publishInstagram", True), lambda: _ig_reel(cfg, cms.instagram_settings(), article, video_url, ig)),
               ("telegram", s.get("publishTelegram", True), lambda: _tg_reel(cfg, cms.telegram_settings(), article, video_url, tg)),
               ("tiktok", s.get("publishTikTok", False), lambda: _tt_reel(cfg, cms.tiktok_settings(), article, video_url)),
               ("review", bool((s.get("reviewChatId") or "").strip()),
                lambda: _review_reel(cfg, {**s, "_botToken": cms.telegram_settings().get("botToken"),
                                           "_hashtags": cms.instagram_settings().get("hashtags"),
                                           "_skipCaption": bool(payload.get("skip_caption"))},
                                     article, video_url, str(payload.get("teaser") or ""), tg))]
    if payload.get("review_only"):  # повторно прислать рилс себе, без публикации в сети
        targets = [t for t in targets if t[0] == "review"]
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
