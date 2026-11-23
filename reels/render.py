"""Сборка рилса TechTalQ 1080×1920: HTML-шаблон + картинка диктора с анимированным ртом → кадры (Playwright/Chromium) → MP4 (ffmpeg).

Хронометраж задаёт озвучка: таймкоды символов ElevenLabs (alignment) превращаются в фазы рта
(визе́мы) и субтитры по словам. Сцены: студия (приветствие и анонс) → новость на фоне, диктор в
круге слева внизу → студия (концовка с призывом подписаться).
"""
from __future__ import annotations

import base64
import json
import math
import os
import random
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).parent
FPS = 30
W, H = 1080, 1920

# Казахская кириллица → форма рта
O_SHAPE = set("оөуұүюОӨУҰҮЮ")
WIDE = set("аәеэяАӘЕЭЯ")
MID = set("ыіиӣйЫІИЙ")
CLOSED = set("мбпвфМБПВФ")
VOWELS = O_SHAPE | WIDE | MID | set("aeiouAEIOU")


@dataclass
class Word:
    text: str
    start: float
    end: float


def host_svg() -> str:
    """Накладка на картинку диктора: фазы рта и веки (reels/host.py)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("host", HERE / "host.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod.overlay_svg()


def visemes(chars: list[str], starts: list[float], ends: list[float]) -> list[list]:
    """Таймкоды символов → [[начало, конец, форма рта]]; паузы — рот закрыт."""
    out: list[list] = []
    for ch, s, e in zip(chars, starts, ends):
        if ch in CLOSED:
            shape = "closed"
        elif ch in O_SHAPE:
            shape = "o"
        elif ch in WIDE:
            shape = "wide"
        elif ch in MID:
            shape = "mid"
        elif ch.isalpha() or ch.isdigit():
            shape = "small"
        else:
            shape = "closed"
        e = max(e, s + 0.04)
        if out and out[-1][2] == shape and s - out[-1][1] < 0.03:
            out[-1][1] = e
        else:
            out.append([round(s, 3), round(e, 3), shape])
    # слишком короткие открытия (<50 мс) сливаем с соседними, чтобы рот не «дрожал»
    merged: list[list] = []
    for v in out:
        if merged and v[1] - v[0] < 0.05:
            merged[-1][1] = v[1]
        else:
            merged.append(v)
    return merged


def words(chars: list[str], starts: list[float], ends: list[float]) -> list[Word]:
    res: list[Word] = []
    cur, ws, we = "", None, None
    for ch, s, e in zip(chars, starts, ends):
        if ch.isspace():
            if cur:
                res.append(Word(cur, ws, we))
            cur, ws = "", None
            continue
        if ws is None:
            ws = s
        cur += ch
        we = e
    if cur:
        res.append(Word(cur, ws, we))
    return res


def phrases(ws: list[Word], max_words: int = 6, max_chars: int = 34) -> list[dict]:
    """Слова → фразы для субтитров: рвём по знакам препинания и по длине."""
    out, cur = [], []
    for w in ws:
        cur.append(w)
        text_len = sum(len(x.text) + 1 for x in cur)
        if re.search(r"[.!?…:;,]$", w.text) or len(cur) >= max_words or text_len >= max_chars:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    res = []
    for i, ph in enumerate(out):
        end = out[i + 1][0].start if i + 1 < len(out) else ph[-1].end + 0.4
        res.append({"start": ph[0].start, "end": end,
                    "words": [{"text": w.text, "start": w.start, "end": w.end} for w in ph]})
    return res


def blinks(duration: float, seed: int = 7) -> list[float]:
    rnd, t, out = random.Random(seed), 1.2, []
    while t < duration:
        out.append(round(t, 2))
        t += rnd.uniform(2.6, 4.4)
    return out


def data_url(path: Path) -> str:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def sentence_starts(chars: list[str], starts: list[float]) -> list[float]:
    """Время начала каждого предложения (после . ! ? и пробела)."""
    out = []
    for i in range(1, len(chars)):
        if chars[i - 1] in ".!?…" and chars[i].isspace():
            j = i
            while j < len(chars) and chars[j].isspace():
                j += 1
            if j < len(chars):
                out.append(starts[j])
    return out


def plan_shots(intro_end: float, outro_start: float, end: float, headline_start: float | None,
               sentences: list[float]) -> list[dict]:
    """Монтаж: общий план → средний (анонс) → новость → крупный план в студии на одном предложении → новость → концовка."""
    hs = headline_start if headline_start and 0.8 < headline_start < intro_end - 0.6 else None
    shots: list[dict] = []
    if hs:
        shots += [{"type": "studio", "start": 0, "end": hs, "cam0": "wide", "cam1": "wide2"},
                  {"type": "studio", "start": hs, "end": intro_end, "cam0": "medium", "cam1": "medium2"}]
    else:
        shots.append({"type": "studio", "start": 0, "end": intro_end, "cam0": "wide", "cam1": "medium"})
    news_len = outro_start - intro_end
    inner = [x for x in sentences if intro_end + 3 < x < outro_start - 3]
    ins = None
    if news_len > 11 and inner:
        b = min(inner, key=lambda x: abs(x - (intro_end + news_len * .55)))
        nxt = [x for x in sentences if x > b + 1.5]
        ins = (b, min(nxt[0] if nxt else b + 4, b + 4.5, outro_start - 3))
        if ins[1] - ins[0] < 2:
            ins = None
    if ins:
        shots += [{"type": "news", "start": intro_end, "end": ins[0]},
                  {"type": "studio", "start": ins[0], "end": ins[1], "cam0": "close", "cam1": "close2"},
                  {"type": "news", "start": ins[1], "end": outro_start}]
    else:
        shots.append({"type": "news", "start": intro_end, "end": outro_start})
    shots.append({"type": "studio", "start": outro_start, "end": end + 1, "cam0": "close2", "cam1": "medium"})
    return [{**x, "start": round(x["start"], 3), "end": round(x["end"], 3)} for x in shots]


def plan_cuts(shots: list[dict], clips: int, word_starts: list[float], step: float = 2.7) -> list[dict]:
    """Склейки внутри новостных отрезков: фото новости и видео по очереди, смена примерно каждые 2,7 с (по началу слова)."""
    items = [("photo", None)] + [("clip", i) for i in range(clips)]
    if clips:
        items = [items[1], items[0]] + items[2:]  # видео сразу после студии — динамичнее
    cuts, n, played = [], 0, {}
    for sh in shots:
        if sh["type"] != "news":
            continue
        t, first = sh["start"], True
        while t < sh["end"] - 0.05:
            target = t + step
            near = [w for w in word_starts if target - 0.6 <= w <= target + 0.6]
            e = min(near, key=lambda w: abs(w - target)) if near else target
            if sh["end"] - e < step * 0.6:
                e = sh["end"]
            kind, ci = items[n % len(items)]
            cut = {"start": round(t, 3), "end": round(e, 3), "kind": kind, "dir": 1 if n % 2 == 0 else -1, "first": first}
            if kind == "clip":
                cut["clip"], cut["from"] = ci, round(played.get(ci, 0.0), 3)
                played[ci] = played.get(ci, 0.0) + (e - t)
            cuts.append(cut)
            n, t, first = n + 1, e, False
    return cuts or [{"start": 0, "end": 1e9, "kind": "photo"}]


def broll_frames(clips: list[Path], out_dir: Path, seconds: float = 18, fps: int = FPS) -> list[dict]:
    """Стоковые клипы → JPEG-кадры 1080×1920 (кадрирование по центру) для шаблона."""
    res = []
    for i, clip in enumerate(clips):
        d = out_dir / f"b{i}"
        d.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-t", str(seconds), "-i", str(clip),
                        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps}",
                        "-q:v", "3", str(d / "%05d.jpg")], check=True)
        n = len(list(d.glob("*.jpg")))
        if n:
            res.append({"dir": d.resolve().as_uri(), "count": n, "src": i})
    return res


def build_reel(*, title: str, category: str, teaser: str, date_label: str, photo: Path, alignment: dict,
               duration: float, intro_end: float, outro_start: float, headline_start: float | None = None,
               ticker: list[str] | None = None, broll: list[dict] | None = None, photo_credit: str = "",
               gender: str = "m") -> dict:
    chars, st, en = alignment["characters"], alignment["character_start_times_seconds"], alignment["character_end_times_seconds"]
    all_words = words(chars, st, en)
    news_words = [w for w in all_words if intro_end - 0.05 <= w.start < outro_start]
    shots = plan_shots(intro_end, outro_start, duration, headline_start, sentence_starts(chars, st))
    return {
        "title": title, "category": category.upper(), "teaser": teaser, "dateLabel": date_label,
        "photo": data_url(photo), "photoCredit": photo_credit, "hostImage": data_url(HERE / "assets" / "host.jpg"),
        "hostSvg": host_svg(), "ticker": ticker or [], "broll": broll or [],
        "visemes": visemes(chars, st, en), "phrases": phrases(news_words, max_words=3, max_chars=18),
        "blinks": blinks(duration), "shots": shots,
        "cuts": plan_cuts(shots, len(broll or []), [w.start for w in news_words]),
        "timeline": {"introEnd": intro_end, "outroStart": outro_start, "end": duration},
    }


def render_frames(reel: dict, out_dir: Path, fps: int = FPS, times: list[float] | None = None) -> list[Path]:
    from playwright.sync_api import sync_playwright
    html = (HERE / "template.html").read_text(encoding="utf-8")
    html = html.replace("<script>\n/* Данные", f"<script>window.REEL = {json.dumps(reel, ensure_ascii=False)};</script>\n<script>\n/* Данные", 1)
    page_path = out_dir / "reel.html"
    page_path.write_text(html, encoding="utf-8")
    exe = os.environ.get("CHROME_PATH") or None
    paths: list[Path] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=exe, args=["--no-sandbox", "--disable-gpu"])
        page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        page.goto(page_path.resolve().as_uri())
        page.wait_for_function("window.render !== undefined")
        page.evaluate("document.fonts.ready")
        if times is None:
            n = math.ceil(reel["timeline"]["end"] * fps)
            times = [i / fps for i in range(n)]
        for i, t in enumerate(times):
            page.evaluate(f"render({t})")
            page.evaluate("window.ready()")
            path = out_dir / f"f{i:05d}.jpg"
            page.screenshot(path=str(path), type="jpeg", quality=92)
            paths.append(path)
        browser.close()
    return paths


def render_video(reel: dict, audio: Path, out: Path, fps: int = FPS, music: Path | None = None) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="reel-"))
    try:
        render_frames(reel, tmp, fps)
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps), "-i", str(tmp / "f%05d.jpg"), "-i", str(audio)]
        if music:
            cmd += ["-stream_loop", "-1", "-i", str(music), "-filter_complex",
                    "[2:a]volume=0.12[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=2[a]", "-map", "0:v", "-map", "[a]"]
        else:
            cmd += ["-map", "0:v", "-map", "1:a"]
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(fps),
                "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-shortest", "-movflags", "+faststart", str(out)]
        subprocess.run(cmd, check=True)
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
