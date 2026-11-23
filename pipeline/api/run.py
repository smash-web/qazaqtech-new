"""HTTP-точка запуска конвейера для Vercel (Python runtime).

Вызывается планировщиком (pg_cron в Supabase) каждые 30 минут:
    POST /api/run            — сбор + обработка
    POST /api/run?step=collect | process | covers | social | tiktok | telegram
    POST /api/run?step=reel_prepare | reel_publish  — для workflow рилсов (тело — JSON)
Заголовок: Authorization: Bearer <CRON_SECRET>; рилсы — Bearer <OIDC-токен GitHub Actions>
"""
from __future__ import annotations

import hmac
import json
import logging
import os
import sys
import time
import traceback
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from qtnews.config import load  # noqa: E402
from qtnews.main import backfill_covers, build_with_cfg, collect, make_images, process  # noqa: E402
from qtnews.social import post_to_instagram  # noqa: E402
from qtnews.tiktok import post_to_tiktok  # noqa: E402
from qtnews.telegram import post_to_telegram  # noqa: E402
from qtnews.reels import prepare_reel, publish_reel  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def _authorized(header: str | None) -> bool:
    secret = os.environ.get("CRON_SECRET", "")
    return bool(secret) and hmac.compare_digest(header or "", f"Bearer {secret}")


REEL_STEPS = ("reel_prepare", "reel_publish")


def _authorized_reels(header: str | None) -> bool:
    """Шаги рилсов: CRON_SECRET (ручной запуск) или OIDC-токен workflow reels.yml."""
    if _authorized(header):
        return True
    token = (header or "").removeprefix("Bearer ").strip()
    if not token.count(".") == 2:
        return False
    try:
        from qtnews.gh_oidc import verify
        verify(token)
        return True
    except Exception as exc:  # noqa: BLE001
        logging.warning("OIDC отклонён: %s", exc)
        return False


class handler(BaseHTTPRequestHandler):  # noqa: N801 — имя требует Vercel
    def _send(self, code: int, body: dict) -> None:
        data = json.dumps(body, ensure_ascii=False, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # проверка, что функция жива (без запуска)
        self._send(200, {"ok": True, "service": "qtnews-pipeline"})

    def do_POST(self) -> None:
        step = parse_qs(urlparse(self.path).query).get("step", ["both"])[0]
        auth = self.headers.get("Authorization")
        if not (_authorized_reels(auth) if step in REEL_STEPS else _authorized(auth)):
            self._send(401, {"error": "unauthorized"})
            return
        payload: dict = {}
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                payload = {}
        started = time.time()
        deadline = time.monotonic()  # уточняется после загрузки конфига
        result: dict = {"step": step}
        db = None
        try:
            cfg = load()
            deadline += cfg.run_budget_seconds
            db, cms, llm, fetcher, cfg = build_with_cfg(cfg)
            if step in ("both", "collect"):
                result["collect"] = collect(cfg, db, cms, fetcher)
            if step in ("both", "process"):
                result["process"] = process(cfg, db, cms, llm, fetcher, make_images(cfg), deadline=deadline)
            if step == "covers":
                if getattr(llm, "budget", None) is not None:
                    llm.budget.deadline = deadline
                result["covers"] = backfill_covers(cfg, cms, llm, make_images(cfg), cms.used_image_pages(),
                                                   limit=8, deadline=deadline)
            if step == "social":
                result["social"] = post_to_instagram(cfg, db, cms)
            if step == "tiktok":
                result["tiktok"] = post_to_tiktok(cfg, db, cms)
            if step == "telegram":
                result["telegram"] = post_to_telegram(cfg, db, cms)
            if step == "reel_prepare":
                result.update(prepare_reel(cfg, db, cms, llm, force=bool(payload.get("force"))))
            if step == "reel_publish":
                result.update(publish_reel(cfg, db, cms, payload))
            result["seconds"] = round(time.time() - started, 1)
            self._send(200, result)
        except Exception as exc:  # noqa: BLE001
            logging.error("Ошибка запуска: %s\n%s", exc, traceback.format_exc())
            self._send(500, {"error": str(exc)[:500], "step": step})
        finally:
            if db is not None:
                db.close()
