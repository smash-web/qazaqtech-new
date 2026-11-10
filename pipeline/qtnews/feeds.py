"""Загрузка и разбор RSS/Atom-лент, извлечение текста статьи."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import requests
from bs4 import BeautifulSoup
from lxml import etree

log = logging.getLogger(__name__)

_TRACKING_PARAMS = re.compile(r"^(utm_|fbclid$|gclid$|mc_|ref$|cmpid$|guccounter$)")
_XML_PARSER = etree.XMLParser(recover=True, resolve_entities=False, no_network=True, huge_tree=False)


@dataclass
class FeedEntry:
    url: str
    title: str
    summary: str
    published_at: str  # ISO UTC


def normalize_url(url: str) -> str:
    """Убирает трекинговые параметры и фрагмент — для дедупликации."""
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not _TRACKING_PARAMS.match(k)]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def html_to_text(html: str, limit: int | None = None) -> str:
    if not html:
        return ""
    text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] if limit else text


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _local(tag: object) -> str:
    return etree.QName(tag).localname if isinstance(tag, str) else ""


def _child_text(el: etree._Element, *names: str) -> str:
    for child in el:
        if _local(child.tag) in names and child.text:
            return child.text.strip()
    return ""


def parse_feed(xml: bytes, now: datetime | None = None) -> list[FeedEntry]:
    """Разбирает RSS 2.0 / RSS 1.0 / Atom. Записи без ссылки или заголовка пропускаются."""
    now = now or datetime.now(timezone.utc)
    root = etree.fromstring(xml, _XML_PARSER)
    if root is None:
        return []
    entries: list[FeedEntry] = []
    for el in root.iter():
        name = _local(el.tag)
        if name not in ("item", "entry"):
            continue
        title = html_to_text(_child_text(el, "title"))
        link = ""
        if name == "entry":  # Atom: <link rel="alternate" href="...">
            for child in el:
                if _local(child.tag) == "link" and child.get("rel", "alternate") == "alternate" and child.get("href"):
                    link = child.get("href")
                    break
        link = link or _child_text(el, "link")
        if not link:
            guid = _child_text(el, "guid", "id")
            link = guid if guid.startswith("http") else ""
        summary = html_to_text(_child_text(el, "description", "summary", "encoded", "content"), limit=1500)
        published = _parse_date(_child_text(el, "pubDate", "published", "updated", "date")) or now
        if published > now:  # защита от дат из будущего
            published = now
        if title and link:
            entries.append(FeedEntry(normalize_url(link), title, summary,
                                     published.replace(microsecond=0).isoformat()))
    return entries


class Fetcher:
    def __init__(self, user_agent: str, timeout: int = 20):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept-Language": "en;q=0.9"})
        self.timeout = timeout

    def get(self, url: str) -> bytes:
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        if len(resp.content) > 8 * 1024 * 1024:
            raise ValueError(f"Слишком большой ответ: {url}")
        return resp.content

    def fetch_feed(self, feed_url: str) -> list[FeedEntry]:
        return parse_feed(self.get(feed_url))

    def fetch_article_text(self, url: str, limit: int = 6000) -> str:
        """Достаёт основной текст страницы — только как исходный материал для фактов."""
        try:
            html = self.get(url)
        except Exception as exc:  # noqa: BLE001
            log.info("Не удалось загрузить %s: %s", url, exc)
            return ""
        return extract_main_text(html, limit)


def extract_main_text(html: bytes | str, limit: int = 6000) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "noscript", "figure"]):
        tag.decompose()
    container = soup.find("article") or soup.find("main") or soup.body or soup
    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    text = "\n".join(p for p in paragraphs if len(p) > 40)
    return re.sub(r"[ \t]+", " ", text)[:limit]
