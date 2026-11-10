"""Преобразование упрощённого Markdown в формат Lexical JSON (редактор Payload CMS).

Поддерживается: абзацы, заголовки ##/###, маркированные и нумерованные списки,
**жирный**, *курсив*, [ссылки](https://...). Этого достаточно для новостей.
"""
from __future__ import annotations

import re
from typing import Any

BOLD, ITALIC = 1, 2
_INLINE = re.compile(r"(\*\*(?P<b>.+?)\*\*|\*(?P<i>[^*]+?)\*|\[(?P<lt>[^\]]+)\]\((?P<lu>https?://[^)\s]+)\))")


def _text(text: str, fmt: int = 0) -> dict[str, Any]:
    return {"type": "text", "text": text, "format": fmt, "detail": 0, "mode": "normal", "style": "", "version": 1}


def _block(kind: str, children: list[dict], **extra: Any) -> dict[str, Any]:
    return {"type": kind, "children": children, "direction": "ltr", "format": "", "indent": 0, "version": 1, **extra}


def inline(text: str) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    pos = 0
    for m in _INLINE.finditer(text):
        if m.start() > pos:
            nodes.append(_text(text[pos:m.start()]))
        if m.group("b"):
            nodes.append(_text(m.group("b"), BOLD))
        elif m.group("i"):
            nodes.append(_text(m.group("i"), ITALIC))
        else:
            nodes.append({
                "type": "link", "children": [_text(m.group("lt"))], "direction": "ltr", "format": "",
                "indent": 0, "version": 3,
                "fields": {"linkType": "custom", "url": m.group("lu"), "newTab": True},
            })
        pos = m.end()
    if pos < len(text):
        nodes.append(_text(text[pos:]))
    return nodes or [_text("")]


def markdown_to_lexical(md: str) -> dict[str, Any]:
    children: list[dict[str, Any]] = []
    list_items: list[dict[str, Any]] = []
    list_type: str | None = None
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            children.append(_block("paragraph", inline(" ".join(paragraph)), textFormat=0, textStyle=""))
            paragraph.clear()

    def flush_list() -> None:
        nonlocal list_type
        if list_items:
            tag = "ul" if list_type == "bullet" else "ol"
            children.append(_block("list", list(list_items), listType=list_type, start=1, tag=tag))
            list_items.clear()
        list_type = None

    for raw in md.replace("\r\n", "\n").split("\n"):
        line = raw.strip()
        heading = re.match(r"^(#{2,4})\s+(.+)$", line)
        bullet = re.match(r"^[-*•]\s+(.+)$", line)
        number = re.match(r"^\d+[.)]\s+(.+)$", line)
        if not line:
            flush_paragraph()
            flush_list()
        elif heading:
            flush_paragraph()
            flush_list()
            level = min(len(heading.group(1)), 4)
            children.append(_block("heading", inline(heading.group(2).strip()), tag=f"h{level}"))
        elif bullet or number:
            flush_paragraph()
            kind = "bullet" if bullet else "number"
            if list_type and list_type != kind:
                flush_list()
            list_type = kind
            content = (bullet or number).group(1)  # type: ignore[union-attr]
            list_items.append(_block("listitem", inline(content), value=len(list_items) + 1))
        else:
            flush_list()
            paragraph.append(line.lstrip("# ").strip() if line.startswith("# ") else line)
    flush_paragraph()
    flush_list()
    return {"root": {"type": "root", "children": children, "direction": "ltr", "format": "", "indent": 0,
                     "version": 1}}
