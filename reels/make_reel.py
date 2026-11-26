"""Один рилс: подготовка у конвейера → рендер → релиз GitHub → публикация.

Запускается в GitHub Actions (.github/workflows/reels.yml). Секреты не нужны: конвейеру
предъявляется OIDC-токен GitHub (audience techtalq-reels), видео кладётся в релиз `reels`
этого же репозитория через встроенный GITHUB_TOKEN.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
import render  # noqa: E402

PIPELINE = os.environ.get("PIPELINE_URL", "https://qazaqtech-pipeline.vercel.app").rstrip("/")
REPO = os.environ.get("GITHUB_REPOSITORY", "smash-web/qazaqtech-new")
RELEASE = "reels"


def oidc_token() -> str:
    url, tok = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL"), os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
    if not url or not tok:
        manual = os.environ.get("PIPELINE_TOKEN")  # локальный запуск: CRON_SECRET
        if manual:
            return manual
        raise SystemExit("Нет OIDC: в workflow нужно permissions: id-token: write")
    r = requests.get(f"{url}&audience=techtalq-reels", headers={"Authorization": f"Bearer {tok}"}, timeout=30)
    r.raise_for_status()
    return r.json()["value"]


def call(step: str, body: dict | None = None, timeout: int = 320) -> dict:
    r = requests.post(f"{PIPELINE}/api/run", params={"step": step}, json=body or {}, timeout=timeout,
                      headers={"Authorization": f"Bearer {oidc_token()}"})
    if r.status_code >= 400:
        raise RuntimeError(f"{step}: HTTP {r.status_code} {r.text[:300]}")
    return r.json()


def upload(path: Path) -> str:
    """Видео → релиз `reels` репозитория; возвращает публичную ссылку на файл."""
    env = {**os.environ}
    if subprocess.run(["gh", "release", "view", RELEASE, "-R", REPO], env=env, capture_output=True).returncode != 0:
        subprocess.run(["gh", "release", "create", RELEASE, "-R", REPO, "--title", "Рилсы TechTalQ",
                        "--notes", "Готовые рилсы с диктором. Файлы публикуются автоматически.", "--latest=false"],
                       env=env, check=True)
    subprocess.run(["gh", "release", "upload", RELEASE, str(path), "-R", REPO, "--clobber"], env=env, check=True)
    return f"https://github.com/{REPO}/releases/download/{RELEASE}/{path.name}"


def scene_times(job: dict) -> tuple[float, float, float, float | None]:
    al = job["alignment"]
    st, en = al["character_start_times_seconds"], al["character_end_times_seconds"]
    n = len(st)
    intro_end = st[min(job["intro_chars"], n - 1)]
    outro_start = st[min(job["outro_char"], n - 1)]
    hc = job.get("headline_char")
    headline = st[min(hc, n - 1)] if hc else None
    return intro_end, outro_start, en[-1] + 0.9, headline


PREVIEW = os.environ.get("PREVIEW", "").lower() in ("1", "true", "yes")


def main() -> int:
    prep = call("reel_prepare", {"force": True} if PREVIEW else {"event": os.environ.get("GITHUB_EVENT_NAME", "")})
    job = prep.get("job")
    if not job:
        print("Рилс не нужен:", {k: v for k, v in prep.items() if k != "seconds"})
        return 0
    aid = job["article_id"]
    print(f"Статья {aid}: {job['title']}")
    print("Хук на экране:", job.get("teaser"))
    print("Текст диктора:", job.get("text"))
    print("Запросы видео:", job.get("queries"))
    try:
        work = Path(tempfile.mkdtemp(prefix="reel-"))
        audio = work / "voice.mp3"
        audio.write_bytes(base64.b64decode(job["audio_base64"]))
        photo = work / "photo.jpg"
        resp = requests.get(job["photo_url"], timeout=60, headers={"User-Agent": "TechTalqReels/1.0"})
        resp.raise_for_status()
        photo.write_bytes(resp.content)
        if resp.headers.get("content-type", "").endswith("webp"):
            photo = photo.rename(work / "photo.webp")
        clips, credits, own = [], [], []
        for i, c in enumerate(job.get("broll") or []):
            try:
                v = requests.get(c["url"], timeout=120, headers={"User-Agent": "TechTalqReels/1.0"})
                v.raise_for_status()
                path = work / f"broll{i}.mp4"
                path.write_bytes(v.content)
                clips.append(path)
                credits.append(c.get("credit", ""))
                own.append(bool(c.get("source")))
                print(f"Видео {i + 1}: «{c.get('query')}» — {c.get('credit')}, {c.get('page')}")
            except requests.RequestException as exc:
                print("Видео не скачалось:", exc)
        broll = render.broll_frames(clips, work / "broll") if clips else []
        intro_end, outro_start, duration, headline = scene_times(job)
        reel = render.build_reel(title=job["title"], category=job["category"], teaser=job["teaser"],
                                 date_label=job["date_label"], photo=photo, alignment=job["alignment"],
                                 duration=duration, intro_end=intro_end, outro_start=outro_start,
                                 headline_start=headline, ticker=job.get("ticker") or [],
                                 broll=[dict(b, credit=credits[b["src"]], own=own[b["src"]]) for b in broll],
                                 photo_credit=job.get("photo_credit") or "", display_map=job.get("display_map"),
                                 presenter=bool(job.get("show_presenter")))
        out = work / f"techtalq-{aid}-{job['slug'][:60]}.mp4"
        render.render_video(reel, audio, out)
        size = out.stat().st_size
        print(f"Видео: {duration:.1f} с, {size / 1e6:.1f} МБ")
        url = upload(out)
        print("Ссылка:", url)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        call("reel_publish", {"article_id": aid, "error": f"{type(exc).__name__}: {exc}"[:300]})
        return 1
    if PREVIEW:  # предпросмотр: видео в релизе, в соцсети не публикуем
        call("reel_publish", {"article_id": aid, "preview_url": url})
        print("ПРЕДПРОСМОТР:", url)
        return 0
    res = call("reel_publish", {"article_id": aid, "video_url": url, "teaser": job.get("teaser")}, timeout=320)
    print(json.dumps({k: v for k, v in res.items() if k != "seconds"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
