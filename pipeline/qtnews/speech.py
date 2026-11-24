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
    "ChatGPT": "Чат Джи-Пи-Ти", "OpenAI": "Оупен-Эй-Ай", "GPT": "Джи-Пи-Ти", "xAI": "Икс-Эй-Ай", "GTA": "Джи Ти Эй",
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
        if b == "5":  # 3,5 → «үш жарым» — так говорят в эфире
            return f"{kk_number(int(a))} жарым" if int(a) else "жарты"
        return f"{kk_number(int(a))} бүтін {kk_number(int(b))}"
    return kk_number(int(tok))


NBSP = "\u00a0"
NUM = r"\d{1,3}(?: \d{3})+|\d+(?:[.,]\d+)?"


ROMAN = {"I": 1, "V": 5, "X": 10}


def _roman(tok: str) -> int | None:
    if not re.fullmatch(r"X{0,3}(IX|IV|V?I{0,3})", tok) or not tok:
        return None
    total = 0
    for i, ch in enumerate(tok):
        v = ROMAN[ch]
        total += -v if i + 1 < len(tok) and ROMAN[tok[i + 1]] > v else v
    return total


# --- казахская грамматика: порядковые числительные и падежные окончания -------------------------------
BACK, FRONT = set("аоұы"), set("әөүіеиэ")
VOICELESS = set("кқпстфхцчшщбвгд")  # б/в/г/д на конце (заимствования) звучат глухо: миллиардтан, заводқа
SONOR_MNN = set("мнң")


def _back(word: str) -> bool:
    for ch in reversed(word.lower()):
        if ch in BACK:
            return True
        if ch in FRONT:
            return False
    return True


def kk_ordinal(n: int) -> str:
    """бір → бірінші, отыз → отызыншы, жиырма → жиырмасыншы, 2030 → екі мың отызыншы."""
    words = kk_number(n).split(" ")
    last = words[-1]
    special = {"жиырма": "жиырмасыншы", "қырық": "қырқыншы", "алты": "алтыншы"}
    if last in special:
        words[-1] = special[last]
    elif last[-1] in "аеыіоөұүюяэә":  # «у» как согласный: елу → елуінші
        words[-1] = last + ("ншы" if _back(last) else "нші")
    else:
        words[-1] = last + ("ыншы" if _back(last) else "інші")
    return " ".join(words)


CASES = {  # окончание (как написано после дефиса) → падеж
    "ның": "gen", "нің": "gen", "дың": "gen", "дің": "gen", "тың": "gen", "тің": "gen",
    "ға": "dat", "ге": "dat", "қа": "dat", "ке": "dat", "на": "dat", "не": "dat",
    "да": "loc", "де": "loc", "та": "loc", "те": "loc", "нда": "loc", "нде": "loc",
    "дан": "abl", "ден": "abl", "тан": "abl", "тен": "abl", "нан": "abl", "нен": "abl",
    "ны": "acc", "ні": "acc", "ды": "acc", "ді": "acc", "ты": "acc", "ті": "acc", "н": "acc",
    "мен": "ins", "бен": "ins", "пен": "ins",
}


def kk_inflect(word: str, case: str, possessive: bool = False) -> str:
    """Падежное окончание к слову по закону сингармонизма (Ұйымы + gen → Ұйымының, Одақ + gen → Одақтың)."""
    back, last = _back(word), word[-1].lower()
    a, e = ("а", "ы") if back else ("е", "і")
    vowel = last in "аеыіоөұүэәяюи"
    if possessive:
        return word + {"gen": f"н{e}ң", "dat": f"н{a}", "loc": f"нд{a}", "abl": f"н{a}н", "acc": "н",
                       "ins": "мен"}[case]
    if case == "gen":
        c = "н" if vowel or last in SONOR_MNN else "т" if last in VOICELESS else "д"
        return word + f"{c}{e}ң"
    if case == "dat":
        return word + (("қ" if back else "к") if last in VOICELESS else ("ғ" if back else "г")) + a
    if case == "loc":
        return word + ("т" if last in VOICELESS else "д") + a
    if case == "abl":
        c = "т" if last in VOICELESS else "н" if last in SONOR_MNN else "д"
        return word + f"{c}{a}н"
    if case == "acc":
        c = "н" if vowel else "т" if last in VOICELESS else "д"
        return word + c + e
    if case == "ins":
        return word + ("п" if last in VOICELESS else "б" if last in "лмнңзж" else "м") + "ен"
    return word


def _with_suffix(phrase: str, suffix: str, possessive: bool = False) -> str:
    case = CASES.get(suffix.lower())
    if not case:
        return phrase + suffix
    head, _, last = phrase.rpartition(" ")
    return (head + " " if head else "") + kk_inflect(last, case, possessive)


# казахские аббревиатуры — голос читает их как слово («бругро»), поэтому говорим полностью
ABBR = {  # аббревиатура → (полностью, оканчивается притяжательным -ы/-і/-сы/-сі)
    "БҰҰ": ("Біріккен Ұлттар Ұйымы", True), "АҚШ": ("Америка Құрама Штаттары", True),
    "ЕО": ("Еуропалық Одақ", False), "ҚР": ("Қазақстан Республикасы", True), "ҚХР": ("Қытай Халық Республикасы", True),
    "РФ": ("Ресей Федерациясы", True), "ТМД": ("Тәуелсіз Мемлекеттер Достастығы", True),
    "ЕАЭО": ("Еуразиялық экономикалық одақ", False), "ДДСҰ": ("Дүниежүзілік денсаулық сақтау ұйымы", True),
    "ХВҚ": ("Халықаралық валюта қоры", True), "ҰҚК": ("Ұлттық қауіпсіздік комитеті", True),
    "ІІМ": ("Ішкі істер министрлігі", True), "ҰБТ": ("Ұлттық бірыңғай тестілеу", False),
    "ЖИ": ("жасанды интеллект", False), "ЖОО": ("жоғары оқу орны", True),
    "БАҚ": ("бұқаралық ақпарат құралдары", True), "ҚМГ": ("ҚазМұнайГаз", False),
}


def expand_abbr(text: str) -> str:
    for ab in sorted(ABBR, key=len, reverse=True):
        full, poss = ABBR[ab]
        text = re.sub(rf"(?<![\w-]){ab}(?:-(\w+))?(?![\w])",
                      lambda m, full=full, poss=poss: _with_suffix(full, m[1], poss) if m[1] else full, text)
    return text


MONTHS = "қаңтар|ақпан|наурыз|сәуір|мамыр|маусым|шілде|тамыз|қыркүйек|қазан|қараша|желтоқсан"


def _n(tok: str) -> int:
    return int(tok.replace(" ", ""))


def ordinals(text: str) -> str:
    num = r"\d{1,3}(?: \d{3})+|\d+"
    # 2030-ыншы, 41-інші, 5-ші → порядковое
    text = re.sub(rf"(?<![\w.,])({num})\s*-?\s*(?:ыншы|інші|ншы|нші|шы|ші)(?![\w])", lambda m: kk_ordinal(_n(m[1])), text)
    # годы и даты: «2030 жылға» → «екі мың отызыншы жылға», «24 қараша» → «жиырма төртінші қараша»
    # (только календарный год 1900–2099: «5 жыл бұрын» — это количество, «бес жыл»)
    text = re.sub(r"(?<![\w.,])((?:19|20)\d\d)(\s+)(?=жыл)", lambda m: kk_ordinal(int(m[1])) + m[2], text, flags=re.I)
    text = re.sub(rf"(?<![\w.,])([1-9]|[12]\d|3[01])(\s+)(?={MONTHS})", lambda m: kk_ordinal(int(m[1])) + m[2], text, flags=re.I)
    # «1-орын», «3-сынып»: число через дефис со словом — порядковое; с падежным окончанием — количественное
    def hyphen(m: re.Match) -> str:
        n, word = _n(m[1]), m[2]
        if word.lower() in CASES or word.lower() in ("сы", "сі", "ы", "і"):
            return _with_suffix(kk_number(n), word)
        return f"{kk_ordinal(n)} {word}"
    return re.sub(rf"(?<![\w.,])({num})-([а-яәіңғүұқөһё]+)", hyphen, text, flags=re.I)


def numbers_to_words(text: str) -> str:
    text = ordinals(text)
    # римские цифры после названия (GTA VI, Civilization VII) — по-казахски
    text = re.sub(r"(?<=\w[\s\u00a0])([IVX]{2,5})(?![\w])",
                  lambda m: kk_number(_roman(m[1])) if _roman(m[1]) else m[1], text)
    # диапазон с процентом: 77–80% → жетпіс жеті – сексен пайыз
    # суффикс после процента пишется слитно: 80%-дан → сексен пайыздан
    text = re.sub(rf"({NUM})\s*[–—-]\s*({NUM})\s*%(?:-(\w+))?",
                  lambda m: f"{_num(m[1])} – {_num(m[2])} пайыз{m[3] or ''}", text)
    text = re.sub(rf"({NUM})\s*%(?:-(\w+))?", lambda m: f"{_num(m[1])} пайыз{m[2] or ''}", text)
    text = re.sub(r"пайыз дейін", "пайызға дейін", text)  # «91–94% дейін» → «…пайызға дейін»
    text = re.sub(rf"({NUM})\s*[–—]\s*({NUM})", lambda m: f"{_num(m[1])} – {_num(m[2])}", text)
    # номер версии в названии (GPT-6.2, iPhone 17) — «алты нүкте екі»
    text = re.sub(r"(?<=\w)[- ](\d+)\.(\d+)(?![\d%])", lambda m: f" {kk_number(int(m[1]))} нүкте {kk_number(int(m[2]))}", text)
    text = re.sub(r"(?<=[^\W\d])-(\d+)(?![\d.,])", lambda m: f" {kk_number(int(m[1]))}", text)
    text = re.sub(rf"(?<![\w.])({NUM})(?![\w])", lambda m: _num(m[1]), text)
    return text


def for_speech(text: str, extra: dict[str, str] | None = None) -> tuple[str, dict[str, str]]:
    """Текст для голоса и карта «как произносится» → «как писать в субтитрах».
    extra — произношение остальных латинских названий от ИИ (наш словарь BRANDS важнее)."""
    for wrong, right in SPELLING.items():
        text = text.replace(wrong, right)
    say = {**BRANDS, **(extra or {})}  # extra: словарь из админки и подсказки ИИ (админка важнее всего)
    # «GTA VI» целиком — одним названием, чтобы и в субтитрах осталось «GTA VI»
    for name, rom in re.findall(r"(?<![\w-])([A-Z][\w]*) ([IVX]{2,5})(?![\w])", text):
        full = f"{name} {rom}"
        if full not in say and _roman(rom):
            say[full] = f"{say.get(name, name)} {kk_number(_roman(rom))}"
    shown: dict[str, str] = {}
    for brand in sorted(say, key=len, reverse=True):
        pattern = rf"(?<![\w-]){re.escape(brand)}(?![\w])"
        if re.search(pattern, text):
            # буквы и части — через неразрывный пробел: голос делает паузу («Джи Ти Эй»), а для субтитров это одно слово
            spoken = re.sub(r"\s+", NBSP, say[brand].strip())  # дефисы оставляем — так голос читает буквы слитно и естественно
            text = re.sub(pattern, spoken, text)
            shown[spoken] = brand
    return numbers_to_words(expand_abbr(text)), shown


def parse_dictionary(text: str) -> dict[str, str]:
    """Словарь произношения из админки: строки «GTA VI = Джи Ти Эй алты»."""
    out: dict[str, str] = {}
    for line in (text or "").splitlines():
        if "=" in line:
            k, v = (x.strip() for x in line.split("=", 1))
            if k and v:
                out[k] = v
    return out


def to_display(word: str, shown: dict[str, str]) -> str:
    for spoken in sorted(shown, key=len, reverse=True):
        if spoken in word:
            word = word.replace(spoken, shown[spoken])
    return word
