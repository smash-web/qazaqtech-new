"""HTTP-точка запуска конвейера для Vercel (Python runtime).

Вызывается планировщиком (pg_cron в Supabase) каждые 30 минут:
    POST /api/run            — сбор + обработка
    POST /api/run?step=collect | process | covers
Заголовок: Authorization: Bearer <CRON_SECRET>
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

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def _authorized(header: str | None) -> bool:
    secret = os.environ.get("CRON_SECRET", "")
    return bool(secret) and hmac.compare_digest(header or "", f"Bearer {secret}")


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
        if not _authorized(self.headers.get("Authorization")):
            self._send(401, {"error": "unauthorized"})
            return
        step = parse_qs(urlparse(self.path).query).get("step", ["both"])[0]
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
            result["seconds"] = round(time.time() - started, 1)
            self._send(200, result)
        except Exception as exc:  # noqa: BLE001
            logging.error("Ошибка запуска: %s\n%s", exc, traceback.format_exc())
            self._send(500, {"error": str(exc)[:500], "step": step})
        finally:
            if db is not None:
                db.close()
