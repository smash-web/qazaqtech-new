"""ЧПУ (slug) для казахских заголовков: транслитерация кириллицы в латиницу."""
from __future__ import annotations

import re
import unicodedata

_MAP = {
    "а": "a", "ә": "a", "б": "b", "в": "v", "г": "g", "ғ": "g", "д": "d", "е": "e", "ё": "yo", "ж": "zh",
    "з": "z", "и": "i", "й": "i", "к": "k", "қ": "q", "л": "l", "м": "m", "н": "n", "ң": "ng", "о": "o",
    "ө": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ұ": "u", "ү": "u", "ф": "f", "х": "h",
    "һ": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "і": "i", "ь": "", "э": "e",
    "ю": "yu", "я": "ya",
}


def slugify(title: str, max_len: int = 80) -> str:
    out = []
    for ch in title.lower():
        if ch in _MAP:
            out.append(_MAP[ch])
        else:
            out.append(unicodedata.normalize("NFKD", ch).encode("ascii", "ignore").decode())
    slug = re.sub(r"[^a-z0-9]+", "-", "".join(out)).strip("-")
    if len(slug) > max_len:
        slug = slug[:max_len].rsplit("-", 1)[0]
    return slug or "zhanalyq"
