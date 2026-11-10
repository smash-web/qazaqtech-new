"""Подбор фото к статье: только свободные лицензии с Wikimedia Commons.

Правила редакции:
  * лицензии CC BY / CC BY-SA / CC0 / Public domain (без NC/ND и «fair use»);
  * без фото реальных людей (личные права, портреты) — продукты, здания, техника, логотипы;
  * подпись: автор, лицензия, ссылка на страницу файла.
Если по запросам ИИ ничего не нашлось — берём запасные запросы по рубрике, чтобы фото было всегда.
"""
from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass

import requests

log = logging.getLogger(__name__)

COMMONS_API = "https://commons.wikimedia.org/w/api.php"

# Запасные запросы по рубрикам: нейтральные, всегда находятся
CATEGORY_FALLBACK: dict[str, list[str]] = {
    "ai": ["artificial intelligence data center", "GPU server rack", "neural network chip"],
    "gadgets": ["smartphone close-up", "laptop computer desk", "consumer electronics"],
    "big-tech": ["technology company headquarters", "silicon valley campus", "data center building"],
    "dev": ["source code on screen", "programmer laptop code", "computer keyboard close-up"],
    "policy": ["parliament building", "courthouse columns", "european commission berlaymont"],
    "security": ["computer security padlock keyboard", "server room cables", "binary code screen"],
    "business": ["office skyscraper technology company", "stock exchange trading floor", "silicon valley campus"],
    "startups": ["startup office", "silicon valley", "coworking space laptop"],
    "space": ["rocket launch", "satellite in orbit", "spacecraft"],
    "science": ["laboratory research equipment", "microscope laboratory"],
    "hardware": ["computer chip wafer", "motherboard close-up", "semiconductor fab"],
    "transport": ["electric car charging", "autonomous vehicle"],
    "games": ["video game controller", "gaming console"],
}
DEFAULT_FALLBACK = ["computer server room", "circuit board close-up", "laptop computer desk"]

_PEOPLE = re.compile(
    r"\b(people|persons?|portraits?|men|women|man|woman|headshots?|selfies?|children|births|deaths|"
    r"politicians?|businesspeople|executives?|ceos?|speakers?|celebrities|actors?|actresses)\b", re.I)
_BAD_TITLE = re.compile(r"\b(map|diagram|chart|graph|flag|coat of arms|signature|screenshot|icon|svg)\b", re.I)


@dataclass
class ImageCandidate:
    title: str            # File:...
    page_url: str         # страница файла на Commons
    image_url: str        # уменьшенная копия для загрузки
    width: int
    height: int
    mime: str
    author: str
    license: str

    @property
    def credit(self) -> str:
        lic = self.license
        if lic.lower().startswith(("public domain", "pd")):
            lic = "қоғамдық игілік"
        return f"Сурет: {self.author} / Wikimedia Commons, {lic} — {self.page_url}"


def _strip(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", html.unescape(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def license_ok(short: str, usage: str = "") -> bool:
    s = f"{short} {usage}".lower()
    if any(bad in s for bad in ("-nc", " nc", "-nd", " nd", "fair use", "non-free", "noncommercial")):
        return False
    return s.startswith(("cc by", "cc-by", "cc0", "public domain", "pd")) or "public domain" in s


def acceptable(c: ImageCandidate, categories: str, restrictions: str) -> bool:
    if c.mime not in ("image/jpeg", "image/png", "image/webp"):
        return False
    if c.width < 900 or c.height < 450:
        return False
    ratio = c.width / max(c.height, 1)
    if not 1.15 <= ratio <= 2.4:  # нужна горизонтальная картинка под обложку 16:9
        return False
    if "personality" in restrictions.lower():  # на фото есть узнаваемые люди
        return False
    if _PEOPLE.search(categories) or _PEOPLE.search(c.title):
        return False
    if _BAD_TITLE.search(c.title):
        return False
    return True


class ImageFinder:
    def __init__(self, user_agent: str, timeout: int = 20, thumb_width: int = 1600):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self.timeout = timeout
        self.thumb_width = thumb_width

    def search(self, query: str, limit: int = 20) -> list[ImageCandidate]:
        params = {
            "action": "query", "format": "json", "formatversion": "2",
            "generator": "search", "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": "6", "gsrlimit": str(limit),
            "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": str(self.thumb_width),
            "iiextmetadatafilter": "LicenseShortName|UsageTerms|Artist|Credit|Categories|Restrictions",
        }
        try:
            resp = self.session.get(COMMONS_API, params=params, timeout=self.timeout)
            resp.raise_for_status()
            pages = resp.json().get("query", {}).get("pages", [])
        except (requests.RequestException, ValueError) as exc:
            log.warning("Commons: поиск «%s» не удался: %s", query, exc)
            return []
        pages.sort(key=lambda p: p.get("index", 0))
        out: list[ImageCandidate] = []
        for p in pages:
            info = (p.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})
            val = lambda k: (meta.get(k) or {}).get("value", "")  # noqa: E731
            short, usage = _strip(val("LicenseShortName")), _strip(val("UsageTerms"))
            if not license_ok(short, usage):
                continue
            author = _strip(val("Artist")) or _strip(val("Credit")) or "белгісіз автор"
            c = ImageCandidate(
                title=p.get("title", ""), page_url=info.get("descriptionurl", ""),
                image_url=info.get("thumburl") or info.get("url", ""),
                width=int(info.get("width") or 0), height=int(info.get("height") or 0),
                mime=info.get("mime", ""), author=author[:120], license=short or usage,
            )
            if c.image_url and acceptable(c, _strip(val("Categories")), _strip(val("Restrictions"))):
                out.append(c)
        return out

    def download(self, c: ImageCandidate) -> bytes:
        resp = self.session.get(c.image_url, timeout=self.timeout)
        resp.raise_for_status()
        if len(resp.content) > 4 * 1024 * 1024:
            raise ValueError("Слишком большой файл")
        return resp.content

    def find(self, queries: list[str], category: str | None, used_pages: set[str]) -> ImageCandidate | None:
        """Первый подходящий и ещё не использованный кандидат: сначала запросы ИИ, потом запасные по рубрике."""
        plan = [q for q in queries if q.strip()][:4]
        plan += CATEGORY_FALLBACK.get(category or "", []) + DEFAULT_FALLBACK
        seen: set[str] = set()
        reused: ImageCandidate | None = None
        for q in plan:
            if q.lower() in seen:
                continue
            seen.add(q.lower())
            for c in self.search(q):
                if c.page_url not in used_pages:
                    log.info("Фото по запросу «%s»: %s", q, c.title)
                    return c
                reused = reused or c
        return reused


def filename_for(c: ImageCandidate, slug: str) -> str:
    ext = {"image/png": "png", "image/webp": "webp"}.get(c.mime, "jpg")
    return f"{slug[:60] or 'cover'}.{ext}"
