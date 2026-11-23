from datetime import datetime, timedelta, timezone

import pytest

from qtnews.config import Config
from qtnews.db import Database
from qtnews.telegram import (CAPTION_LIMIT, PER_RUN, TelegramError, build_post, normalize_channel,
                             post_to_telegram)

NOW = datetime(2026, 11, 23, 10, 0, tzinfo=timezone.utc)


def art(i, **kw):
    a = {"id": i, "slug": f"news-{i}", "title": f"Жаңалық {i}", "excerpt": "Анонс.",
         "updatedAt": "2026-11-23T09:00:00.000Z", "category": {"slug": "ai"}, "sources": [{"name": "Reuters"}]}
    a.update(kw)
    return a


class FakeCMS:
    def __init__(self, settings, articles):
        self.settings, self.articles, self.updates = settings, articles, []

    def telegram_settings(self):
        return dict(self.settings)

    def update_telegram_settings(self, data):
        self.updates.append(data)
        self.settings.update(data)

    def published_since(self, since_iso, limit=50):
        return list(self.articles)


class FakeTG:
    def __init__(self, photo_error=None, fail=None, chat_error=None):
        self.photos, self.messages = [], []
        self.photo_error, self.fail, self.chat_error = photo_error, fail, chat_error

    def get_chat(self, chat_id):
        if self.chat_error:
            raise self.chat_error
        return {"title": "TechTalQ"}

    def send_photo(self, chat_id, photo, caption, button_url):
        if self.fail:
            raise self.fail
        if self.photo_error:
            raise TelegramError(self.photo_error, 400)
        self.photos.append((chat_id, photo, caption, button_url))
        return {"message_id": 100 + len(self.photos)}

    def send_message(self, chat_id, text, button_url):
        self.messages.append((chat_id, text, button_url))
        return {"message_id": 500 + len(self.messages)}


def settings(**kw):
    s = {"enabled": True, "botToken": "123:abc", "channel": "techtalq", "dailyLimit": 40, "lookbackHours": 6,
         "channelTitle": "TechTalQ"}
    s.update(kw)
    return s


@pytest.fixture
def db():
    d = Database("sqlite:///:memory:")
    d.init_schema()
    return d


def test_normalize_channel():
    assert normalize_channel("techtalq") == "@techtalq"
    assert normalize_channel("https://t.me/techtalq/") == "@techtalq"
    assert normalize_channel("@techtalq") == "@techtalq"
    assert normalize_channel("-1001234567890") == "-1001234567890"


def test_post_is_html_escaped_and_fits_limit():
    p = build_post(art(1, title="A <b> & B", excerpt="сөз " * 600), "https://techtalq.kz")
    assert p.startswith("<b>A &lt;b&gt; &amp; B</b>")
    assert len(p) <= CAPTION_LIMIT
    assert "Дереккөз: Reuters" in p and "<i>" in p


def test_posts_up_to_per_run_with_photo_and_button(db):
    cms, tg = FakeCMS(settings(), [art(i) for i in range(1, 6)]), FakeTG()
    s = post_to_telegram(Config(), db, cms, tg, now=NOW)
    assert s["posted"] == PER_RUN and s["articles"] == [1, 2, 3]
    chat, photo, caption, url = tg.photos[0]
    assert chat == "@techtalq"
    assert photo.startswith("https://techtalq.kz/ig/news-1?v=")
    assert url == "https://techtalq.kz/zhanalyq/news-1"
    assert db.social_get(1, "telegram")["permalink"] == "https://t.me/techtalq/101"
    # следующий запуск берёт оставшиеся, без повторов
    s2 = post_to_telegram(Config(), db, cms, tg, now=NOW + timedelta(minutes=30))
    assert s2["articles"] == [4, 5]
    assert post_to_telegram(Config(), db, cms, tg, now=NOW + timedelta(hours=1))["posted"] == 0


def test_falls_back_to_text_when_photo_cannot_be_fetched(db):
    cms, tg = FakeCMS(settings(), [art(1)]), FakeTG(photo_error="Bad Request: failed to get HTTP URL content")
    s = post_to_telegram(Config(), db, cms, tg, now=NOW)
    assert s["posted"] == 1 and not tg.photos and len(tg.messages) == 1


def test_channel_error_is_explained_in_admin(db):
    cms = FakeCMS(settings(), [art(1)])
    tg = FakeTG(fail=TelegramError("Forbidden: bot is not a member of the channel chat", 403))
    s = post_to_telegram(Config(), db, cms, tg, now=NOW)
    assert s["failed"] == 1
    assert "администратором" in cms.settings["lastError"]
    assert db.social_get(1, "telegram")["attempts"] == 1


def test_first_run_checks_channel(db):
    cms = FakeCMS(settings(channelTitle=""), [art(1)])
    s = post_to_telegram(Config(), db, cms, FakeTG(chat_error=TelegramError("Bad Request: chat not found", 400)),
                         now=NOW)
    assert s["skipped"] == "channel" and "не найден" in cms.settings["lastError"]
    cms2 = FakeCMS(settings(channelTitle=""), [art(1)])
    assert post_to_telegram(Config(), db, cms2, FakeTG(), now=NOW)["posted"] == 1
    assert cms2.settings["channelTitle"] == "TechTalQ"


def test_daily_limit_and_disabled(db):
    cms, tg = FakeCMS(settings(dailyLimit=2), [art(i) for i in range(1, 6)]), FakeTG()
    assert post_to_telegram(Config(), db, cms, tg, now=NOW)["posted"] == 2
    assert post_to_telegram(Config(), db, cms, tg, now=NOW + timedelta(minutes=30))["skipped"] == "daily limit"
    assert post_to_telegram(Config(), db, FakeCMS(settings(enabled=False), [art(9)]), tg, now=NOW)["skipped"] == "disabled"
