import json
from datetime import datetime, timedelta, timezone

import pytest

from qtnews.config import Config
from qtnews.db import Database
from qtnews.reels import (OUTRO, REEL, SPOKEN_BRAND, lexical_text, pick_article, prepare_reel, publish_reel,
                          write_script)

NOW = datetime(2026, 11, 23, 10, 0, tzinfo=timezone.utc)
BODY = "Apple компаниясы сот ісін реттеу үшін екі жүз елу миллион доллар төлейді. " * 2


def art(i, score=5, cover=True, **kw):
    a = {"id": i, "slug": f"news-{i}", "title": f"Жаңалық {i}", "excerpt": "Анонс.", "importanceScore": score,
         "publishedAt": f"2026-11-23T0{i}:00:00.000Z", "category": {"name": "Ірі компаниялар", "slug": "big-tech"},
         "coverImage": {"url": "/api/media/file/p.jpg", "sizes": {"hero": {"url": "/api/media/file/p-hero.jpg"}}} if cover else None,
         "content": {"root": {"children": [{"type": "paragraph", "children": [{"type": "text", "text": "Бірінші абзац."}]},
                                          {"type": "paragraph", "children": [{"type": "text", "text": "Екінші абзац."}]}]}},
         "sources": [{"name": "Reuters"}]}
    a.update(kw)
    return a


class FakeLLM:
    def __init__(self, body=BODY):
        self.body = body

    def complete(self, **kw):
        return json.dumps({"teaser": "Apple 250 млн доллар төлейді", "headline": "Apple Siri кешігуі үшін сотқа ақша төлейді",
                           "body": self.body})


class FakeEleven:
    def __init__(self):
        self.calls = []

    def speak(self, text, voice, model):
        self.calls.append((text, voice, model))
        return {"audio_base64": "QUJD", "alignment": {"characters": list(text), "character_start_times_seconds": [0] * len(text),
                                                     "character_end_times_seconds": [0.1] * len(text)}}


class FakeCMS:
    def __init__(self, settings, articles):
        self.settings, self.articles, self.updates = settings, articles, []

    def reels_settings(self):
        return dict(self.settings)

    def update_reels_settings(self, data):
        self.updates.append(data)
        self.settings.update(data)

    def published_since(self, since_iso, limit=50):
        return list(self.articles)

    def article(self, aid):
        return next(a for a in self.articles if a["id"] == aid)

    def instagram_settings(self):
        return {"accessToken": "tok", "igUserId": "17841"}

    def telegram_settings(self):
        return {"botToken": "1:a", "channel": "techtalq"}

    def tiktok_settings(self):
        return {}


def settings(**kw):
    s = {"enabled": True, "elevenlabsApiKey": "xi", "perDay": 3, "lookbackHours": 12, "presenter": "f",
         "model": "eleven_v3", "publishInstagram": True, "publishTelegram": True, "publishTikTok": False}
    s.update(kw)
    return s


@pytest.fixture
def db():
    d = Database("sqlite:///:memory:")
    d.init_schema()
    return d


def test_lexical_text():
    assert lexical_text(art(1)["content"]) == "Бірінші абзац.\nЕкінші абзац."


def test_script_has_greeting_and_outro():
    s = write_script(FakeLLM(), "m", art(1))
    assert s["intro"].startswith(f"Сәлеметсіз бе! {SPOKEN_BRAND} жаңалықтары.") and s["outro"] == OUTRO
    assert len(s["teaser"]) <= 42


def test_pick_prefers_important_with_cover(db):
    cms = FakeCMS(settings(), [art(1, score=9, cover=False), art(2, score=4), art(3, score=7)])
    assert pick_article(cms, db, cms.settings, NOW)["id"] == 3


def test_prepare_returns_job_with_scene_boundaries(db):
    cms, el = FakeCMS(settings(), [art(1)]), FakeEleven()
    job = prepare_reel(Config(), db, cms, FakeLLM(), el, now=NOW)["job"]
    text = job["text"]
    assert text[job["intro_chars"]:].startswith("Apple компаниясы")
    assert text[job["outro_char"]:] == OUTRO
    assert job["photo_url"] == "https://techtalq.kz/api/media/file/p-hero.jpg"
    assert job["date_label"] == "23 ҚАРАША" and el.calls[0][1] == "EXAVITQu4vr4xnSDxMaL"
    assert db.social_get(1, REEL)["status"] == "rendering"
    # пока ролик собирается, ту же статью повторно не берём
    assert prepare_reel(Config(), db, cms, FakeLLM(), el, now=NOW + timedelta(minutes=5)) == {"skip": "no fresh articles"}


def test_prepare_skips(db):
    assert prepare_reel(Config(), db, FakeCMS(settings(enabled=False), [art(1)]), FakeLLM(), now=NOW)["skip"] == "disabled"
    assert prepare_reel(Config(), db, FakeCMS(settings(elevenlabsApiKey=""), [art(1)]), FakeLLM(), now=NOW)["skip"] == "no elevenlabs key"
    cms = FakeCMS(settings(), [art(1)])
    r = prepare_reel(Config(), db, cms, FakeLLM(body="қысқа"), FakeEleven(), now=NOW)
    assert r["skip"] == "error" and "короткий" in cms.settings["lastError"]


class FakeIG:
    def __init__(self):
        self.calls = []

    def _call(self, method, path, token, **params):
        self.calls.append((path, params))
        return {"id": "c1"}

    def wait_ready(self, *a, **k):
        pass

    def publish(self, ig_id, token, container):
        return "m1"

    def permalink(self, media_id, token):
        return "https://instagram.com/reel/x"


class FakeTG:
    def __init__(self):
        self.calls = []

    def _call(self, method, **payload):
        self.calls.append((method, payload))
        return {"message_id": 7}


def test_publish_to_instagram_and_telegram(db):
    cms, ig, tg = FakeCMS(settings(), [art(1)]), FakeIG(), FakeTG()
    r = publish_reel(Config(), db, cms, {"article_id": 1, "video_url": "https://github.com/x/r.mp4"}, ig, tg, now=NOW)
    assert r["instagram"] == "https://instagram.com/reel/x" and r["telegram"] == "https://t.me/techtalq/7"
    assert ig.calls[0][1]["media_type"] == "REELS" and ig.calls[0][1]["video_url"].endswith("r.mp4")
    assert tg.calls[0][0] == "sendVideo"
    assert db.social_get(1, REEL)["status"] == "posted" and cms.settings["lastError"] == ""


def test_publish_records_render_error(db):
    cms = FakeCMS(settings(), [art(1)])
    publish_reel(Config(), db, cms, {"article_id": 1, "error": "ffmpeg упал"}, now=NOW)
    assert db.social_get(1, REEL)["status"] == "failed" and "ffmpeg" in cms.settings["lastError"]
