import json
from datetime import datetime, timedelta, timezone

import pytest

from qtnews.config import Config
from qtnews.db import Database
from qtnews.reels import (REEL, SUBSCRIBE, lexical_text, pick_article, prepare_reel, publish_reel, write_script)

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
    def __init__(self, body=BODY, pick=None):
        self.body, self.pick = body, pick

    def complete(self, **kw):
        if "id=" in kw.get("prompt", ""):
            return json.dumps({"id": self.pick, "why": "қызық"})
        return json.dumps({"hook": "Apple сотқа екі жүз елу миллион доллар төлейді", "lead": "Siri кешіккені үшін",
                           "body": self.body, "question": "Сіз Siri-ді қолданасыз ба", "teaser": "Apple 250 млн доллар төлейді",
                           "subjects": ["Apple"], "broll": ["iphone in hand"]})


class FakeEleven:
    def __init__(self):
        self.calls = []

    def speak(self, text, voice, model, stability=0.5):
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
    s = {"enabled": True, "elevenlabsApiKey": "xi", "perDay": 3, "lookbackHours": 12, "presenter": "m",
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


def test_script_hook_first_and_question_outro():
    s = write_script(FakeLLM(), "m", art(1))
    assert s["intro"] == "Apple сотқа екі жүз елу миллион доллар төлейді. Siri кешіккені үшін."
    assert s["outro"] == f"Сіз Siri-ді қолданасыз ба? {SUBSCRIBE}" and s["subjects"] == ["Apple"]
    assert s["teaser"] == "Apple сотқа екі жүз елу миллион доллар төлейді."


def test_pick_uses_ai_choice(db):
    cms = FakeCMS(settings(), [art(1, score=9), art(2, score=4), art(3, score=7)])
    assert pick_article(cms, db, cms.settings, NOW, FakeLLM(pick=2), "m")["id"] == 2
    assert pick_article(cms, db, cms.settings, NOW, FakeLLM(pick=99), "m")["id"] == 1


def test_pick_prefers_important_with_cover(db):
    cms = FakeCMS(settings(), [art(1, score=9, cover=False), art(2, score=4), art(3, score=7)])
    assert pick_article(cms, db, cms.settings, NOW)["id"] == 3


def test_prepare_returns_job_with_scene_boundaries(db):
    cms, el = FakeCMS(settings(), [art(1)]), FakeEleven()
    job = prepare_reel(Config(), db, cms, FakeLLM(), el, now=NOW)["job"]
    text = job["text"]
    assert text[job["intro_chars"]:].startswith("Эппл компаниясы")
    assert prepare_reel(Config(), db, FakeCMS(settings(enabled=False), [art(5)]), FakeLLM(), el, now=NOW, force=True)["job"]["article_id"] == 5
    assert text[job["outro_char"]:].startswith("Сіз Siri-ді") and text.endswith(SUBSCRIBE)
    assert text[job["headline_char"]:].startswith("Siri кешіккені")
    assert job["photo_url"] == "https://techtalq.kz/api/media/file/p-hero.jpg"
    assert job["date_label"] == "23 ҚАРАША" and el.calls[0][1] == "JBFqnCBsd6RMkjVDRZzb"
    assert db.social_get(1, REEL)["status"] == "rendering"
    # пока ролик собирается, ту же статью повторно не берём
    assert prepare_reel(Config(), db, cms, FakeLLM(), el, now=NOW + timedelta(minutes=5)) == {"skip": "no fresh articles"}


def test_prepare_skips(db):
    assert prepare_reel(Config(), db, FakeCMS(settings(enabled=False), [art(1)]), FakeLLM(), now=NOW)["skip"] == "disabled"
    assert prepare_reel(Config(), db, FakeCMS(settings(elevenlabsApiKey=""), [art(1)]), FakeLLM(), now=NOW)["skip"] == "no elevenlabs key"
    cms = FakeCMS(settings(), [art(1)])
    r = prepare_reel(Config(), db, cms, FakeLLM(body="қысқа"), FakeEleven(), now=NOW)
    assert r["skip"] == "error" and "неполный" in cms.settings["lastError"]


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

    def send_video_file(self, chat_id, video_url, **payload):
        return self._call("sendVideo", chat_id=chat_id, video=video_url, **payload)


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


def test_pexels_picks_vertical_hd(monkeypatch):
    from qtnews import reels

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"videos": [
                {"id": 1, "duration": 3, "video_files": [{"file_type": "video/mp4", "width": 1080, "height": 1920, "link": "short"}]},
                {"id": 2, "duration": 12, "url": "https://pexels.com/v/2", "user": {"name": "Ann"}, "video_files": [
                    {"file_type": "video/mp4", "width": 1920, "height": 1080, "link": "landscape"},
                    {"file_type": "video/mp4", "width": 720, "height": 1280, "link": "sd"},
                    {"file_type": "video/mp4", "width": 1080, "height": 1920, "link": "hd"}]}]}

    monkeypatch.setattr(reels.requests, "get", lambda *a, **k: Resp())
    clips = reels.pexels_clips("key", ["data center"], "ua", want=1)
    assert clips == [{"url": "hd", "query": "data center", "duration": 12, "credit": "Ann / Pexels", "page": "https://pexels.com/v/2"}]


def test_commons_transcoded_url():
    from qtnews.reels import _transcoded
    assert _transcoded("https://upload.wikimedia.org/wikipedia/commons/a/ab/Nvidia_GPU.webm", 720) == \
        "https://upload.wikimedia.org/wikipedia/commons/transcoded/a/ab/Nvidia_GPU.webm/Nvidia_GPU.webm.720p.vp9.webm"


def test_preview_is_not_published_or_repicked(db):
    cms = FakeCMS(settings(), [art(1)])
    r = publish_reel(Config(), db, cms, {"article_id": 1, "preview_url": "https://x/r.mp4"}, now=NOW)
    assert r == {"preview": "https://x/r.mp4"} and db.social_get(1, REEL)["status"] == "preview"
    assert pick_article(cms, db, cms.settings, NOW) is None


def test_pixabay_picks_large_and_hides_key(monkeypatch):
    from qtnews import reels

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"hits": [
                {"id": 1, "duration": 3, "videos": {"large": {"url": "short", "width": 1920, "height": 1080}}},
                {"id": 3, "duration": 20, "tags": "mountains, nature", "videos": {"large": {"url": "hills", "width": 1920, "height": 1080}}},
                {"id": 2, "duration": 14, "user": "Bob", "pageURL": "https://pixabay.com/v/2", "tags": "server, data",
                 "videos": {"large": {"url": "big", "width": 1920, "height": 1080}, "medium": {"url": "mid", "width": 1280, "height": 720}}}]}

    monkeypatch.setattr(reels.requests, "get", lambda *a, **k: Resp())
    assert reels.pixabay_clips("k", ["server"], "ua", want=1) == [
        {"url": "big", "query": "server", "duration": 14, "page": "https://pixabay.com/v/2", "credit": "Bob / Pixabay"}]


def test_tags_hidden_on_screen():
    class L(FakeLLM):
        def complete(self, **kw):
            return json.dumps({"hook": "[excited] Apple сотқа ақша төлейді", "lead": "Siri үшін", "body": BODY, "question": "Қалай ойлайсыз"})
    s = write_script(L(), "m", art(1), tags=True)
    assert s["teaser"] == "Apple сотқа ақша төлейді." and s["intro"].startswith("[excited]")


def test_review_caption_puts_hook_first():
    from qtnews.reels import review_caption
    art = {"title": "Заголовок", "excerpt": "Анонс", "sources": [{"name": "The Verge"}], "category": None}
    cap = review_caption(art, "https://techtalq.kz", "Хук сөйлем", "#TechTalQ")
    assert cap.startswith("Хук сөйлем\n\nЗаголовок")
    assert "#TechTalQ" in cap


def test_add_voice_returns_id(monkeypatch):
    from qtnews.reels import ElevenLabsClient

    class R:
        status_code = 200
        def json(self):
            return {"voice_id": "v123"}
    c = ElevenLabsClient("k", "ua")
    seen = {}
    def fake_post(url, **kw):
        seen.update(url=url, **kw)
        return R()
    monkeypatch.setattr(c.session, "post", fake_post)
    assert c.add_voice("Диктор", b"abc") == "v123"
    assert seen["url"].endswith("/voices/add") and seen["files"][0][0] == "files"


def test_speech_numbers_and_brands():
    from qtnews.speech import for_speech, kk_number
    assert kk_number(94) == "тоқсан төрт" and kk_number(1919) == "мың тоғыз жүз он тоғыз"
    spoken, shown = for_speech("ChatGPT деңгейі 77–80%-дан 91–94%-ға өсті, GPT-6.2")
    assert "сексен пайыздан" in spoken and "тоқсан төрт пайызға" in spoken
    assert "Чат-Джи-Пи-Ти" in spoken and "алты нүкте екі" in spoken and shown["Чат-Джи-Пи-Ти"] == "ChatGPT"
    assert "токсан" not in for_speech("токсан")[0]
