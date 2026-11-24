"""Подготовка текста к озвучке: числа — правильными казахскими словами, бренды — так, как их произносят.

ИИ пишет числа цифрами, а словами их делает код: так не бывает ошибок вроде «токсан» или «сегіздік».
Английские названия голос читает по-казахски буквами («ЧатГПТ» → «чатгэпэтэ»), поэтому даём ему
произношение кириллицей одним словом через дефис, а субтитры возвращаем к оригиналу по карте display_map.
"""
from __future__ import annotations

import re

ONES = ["", "бір", "екі", "үш", "төрт", "бес", "алты", "жеті", "сегіз", "тоғыз"]
TENS = ["", "он", "жиырма", "отыз", "қырық", "елу", "алпыс", "жетпіс", "сексен", "тоқсан"]
SCALES = [(1_000_000_000, "миллиард"), (1_000_000, "миллион"), (1000, "мың")]

# как произносить (одним словом — чтобы субтитры можно было вернуть к оригиналу)
BRANDS = {
    "ChatGPT": "Чат-Джи-Пи-Ти", "OpenAI": "Оупен-Эй-Ай", "GPT": "Джи-Пи-Ти", "xAI": "Икс-Эй-Ай",
    "SpaceX": "Спейс-Икс", "Grok": "Грок", "Google": "Гугл", "Gemini": "Джемини", "Apple": "Эппл",
    "iPhone": "Айфон", "iPad": "Айпэд", "MacBook": "Макбук", "Microsoft": "Майкрософт", "Windows": "Уиндоус",
    "Copilot": "Копайлот", "Nvidia": "Энвидиа", "NVIDIA": "Энвидиа", "Meta": "Мета", "WhatsApp": "Уотсап",
    "Instagram": "Инстаграм", "Facebook": "Фейсбук", "YouTube": "Ютуб", "TikTok": "Тикток", "Telegram": "Телеграм",
    "Tesla": "Тесла", "Samsung": "Самсунг", "Galaxy": "Гэлакси", "Amazon": "Амазон", "Anthropic": "Антропик",
    "Claude": "Клод", "DeepSeek": "Дипсик", "Huawei": "Хуавэй", "Xiaomi": "Сяоми", "Netflix": "Нетфликс",
    "Steam": "Стим", "PlayStation": "Плейстейшн", "Xbox": "Иксбокс", "Starlink": "Старлинк", "Android": "Андроид", "Siri": "Сири", "Alexa": "Алекса", "Bitcoin": "Биткоин", "Kaspi": "Каспи",
    "Pro": "Про", "Plus": "Плюс", "Free": "Фри", "Max": "Макс", "Ultra": "Ультра",
    "Business": "Бизнес", "Enterprise": "Энтерпрайз", "AI": "Эй-Ай",
}
# частые ошибки ИИ в написании чисел словами
SPELLING = {"токсан": "тоқсан", "кырык": "қырық", "Токсан": "Тоқсан", "сегіздік пайыз": "сегіз пайыз"}


def kk_number(n: int) -> str:
    if n == 0:
        return "нөл"
    parts: list[str] = []
    for value, name in SCALES:
        if n >= value:
            head = n // value
            parts.append(name if (head == 1 and value == 1000) else f"{kk_number(head)} {name}")
            n %= value
    if n >= 100:
        h = n // 100
        parts.append("жүз" if h == 1 else f"{ONES[h]} жүз")
        n %= 100
    if n >= 10:
        parts.append(TENS[n // 10])
        n %= 10
    if n:
        parts.append(ONES[n])
    return " ".join(parts)


def _num(tok: str) -> str:
    tok = tok.replace(" ", "")
    if re.fullmatch(r"\d+[.,]\d+", tok):
        a, b = re.split(r"[.,]", tok)
        return f"{kk_number(int(a))} бүтін {kk_number(int(b))}"
    return kk_number(int(tok))


NUM = r"\d{1,3}(?: \d{3})+|\d+(?:[.,]\d+)?"


def numbers_to_words(text: str) -> str:
    # диапазон с процентом: 77–80% → жетпіс жеті – сексен пайыз
    # суффикс после процента пишется слитно: 80%-дан → сексен пайыздан
    text = re.sub(rf"({NUM})\s*[–—-]\s*({NUM})\s*%(?:-(\w+))?",
                  lambda m: f"{_num(m[1])} – {_num(m[2])} пайыз{m[3] or ''}", text)
    text = re.sub(rf"({NUM})\s*%(?:-(\w+))?", lambda m: f"{_num(m[1])} пайыз{m[2] or ''}", text)
    text = re.sub(rf"({NUM})\s*[–—]\s*({NUM})", lambda m: f"{_num(m[1])} – {_num(m[2])}", text)
    # номер версии в названии (GPT-6.2, iPhone 17) — «алты нүкте екі»
    text = re.sub(r"(?<=\w)[- ](\d+)\.(\d+)(?![\d%])", lambda m: f" {kk_number(int(m[1]))} нүкте {kk_number(int(m[2]))}", text)
    text = re.sub(r"(?<=[^\W\d])-(\d+)(?![\d.,])", lambda m: f" {kk_number(int(m[1]))}", text)
    text = re.sub(rf"(?<![\w.])({NUM})(?![\w])", lambda m: _num(m[1]), text)
    return text


def for_speech(text: str) -> tuple[str, dict[str, str]]:
    """Текст для голоса и карта «как произносится» → «как писать в субтитрах»."""
    for wrong, right in SPELLING.items():
        text = text.replace(wrong, right)
    shown: dict[str, str] = {}
    for brand in sorted(BRANDS, key=len, reverse=True):
        pattern = rf"(?<![\w-]){re.escape(brand)}(?![\w])"
        if re.search(pattern, text):
            text = re.sub(pattern, BRANDS[brand], text)
            shown[BRANDS[brand]] = brand
    return numbers_to_words(text), shown


def to_display(word: str, shown: dict[str, str]) -> str:
    for spoken in sorted(shown, key=len, reverse=True):
        if spoken in word:
            word = word.replace(spoken, shown[spoken])
    return word
