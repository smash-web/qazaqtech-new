from datetime import datetime, timedelta, timezone

import pytest

from qtnews.config import Config
from qtnews.db import Database
from qtnews.social import AI_NOTE, CAPTION_LIMIT, InstagramError, build_caption, image_url, post_to_instagram

NOW = datetime(2026, 11, 18, 10, 0, tzinfo=timezone.utc)
SITE = "https://techtalq.kz"


def art(i, **kw):
    a = {"id": i, "slug": f"news-{i}", "title": f"Жаңалық {i}", "excerpt": "Қысқа анонс.",
         "updatedAt": "2026-11-18T09:00:00.000Z", "category": {"slug": "ai", "name": "ЖИ"},
         "sources": [{"name": "Reuters"}, {"name": "Reuters"}, {"name": "The Verge"}]}
    a.update(kw)
    return a


class FakeCMS:
    def __init__(self, settings, articles):
        self.settings, self.articles, self.updates = settings, articles, []

    def instagram_settings(self):
        return dict(self.settings)

    def update_instagram_settings(self, data):
        self.updates.append(data)
        self.settings.update(data)

    def published_since(self, since_iso, limit=50):
        return list(self.articles)


class FakeIG:
    def __init__(self, fail_on=None):
        self.posts, self.fail_on = [], fail_on

    def create_image(self, ig_id, token, url, caption):
        if self.fail_on == "create":
            raise InstagramError("bad image")
        self.posts.append((url, caption))
        return "c1"

    def wait_ready(self, container, token, timeout=60):
        return None

    def publish(self, ig_id, token, container):
        return f"m{len(self.posts)}"

    def permalink(self, media_id, token):
        return f"https://instagram.com/p/{media_id}"


def settings(**kw):
    s = {"enabled": True, "accessToken": "tok", "igUserId": "17841", "dailyLimit": 20, "lookbackHours": 6,
         "hashtags": "#TechTalQ #технология", "tokenUpdatedAt": (NOW - timedelta(days=1)).isoformat()}
    s.update(kw)
    return s


@pytest.fixture
def db():
    d = Database("sqlite:///:memory:")
    d.init_schema()
    return d


def test_caption_has_title_link_sources_ai_note_and_tags():
    c = build_caption(art(1), SITE, "#TechTalQ #ai")
    assert c.startswith("Жаңалық 1\n\nҚысқа анонс.")
    assert "techtalq.kz сайтында" in c
    assert "Дереккөз: Reuters, The Verge" in c
    assert AI_NOTE in c
    assert "#TechTalQ" in c and "#ЖасандыИнтеллект" in c
    assert c.lower().count("#ai") == 1  # дубль хештега убран


def test_caption_fits_instagram_limit():
    c = build_caption(art(1, excerpt="сөз " * 2000), SITE)
    assert len(c) <= CAPTION_LIMIT and AI_NOTE in c


def test_image_url_is_versioned():
    assert image_url(art(7), SITE).startswith("https://techtalq.kz/ig/news-7?v=")


def test_posts_one_per_run_and_skips_already_posted(db):
    cms, ig = FakeCMS(settings(), [art(1), art(2)]), FakeIG()
    s1 = post_to_instagram(Config(), db, cms, ig, now=NOW)
    s2 = post_to_instagram(Config(), db, cms, ig, now=NOW + timedelta(minutes=30))
    s3 = post_to_instagram(Config(), db, cms, ig, now=NOW + timedelta(minutes=60))
    assert (s1["article"], s2["article"]) == (1, 2)
    assert s3["posted"] == 0
    assert [u for u, _ in ig.posts] == [image_url(art(1), "https://techtalq.kz"), image_url(art(2), "https://techtalq.kz")]
    assert db.social_get(1, "instagram")["permalink"] == "https://instagram.com/p/m1"


def test_disabled_or_not_connected(db):
    assert post_to_instagram(Config(), db, FakeCMS(settings(enabled=False), [art(1)]), FakeIG(), now=NOW)["skipped"] == "disabled"
    assert post_to_instagram(Config(), db, FakeCMS(settings(accessToken=""), [art(1)]), FakeIG(), now=NOW)["skipped"] == "not connected"


def test_daily_limit(db):
    cms, ig = FakeCMS(settings(dailyLimit=1), [art(1), art(2)]), FakeIG()
    post_to_instagram(Config(), db, cms, ig, now=NOW)
    assert post_to_instagram(Config(), db, cms, ig, now=NOW + timedelta(minutes=30))["skipped"] == "daily limit"


def test_failure_is_retried_then_given_up(db):
    cms, ig = FakeCMS(settings(), [art(1)]), FakeIG(fail_on="create")
    for k in range(4):
        post_to_instagram(Config(), db, cms, ig, now=NOW + timedelta(minutes=30 * k))
    assert db.social_get(1, "instagram")["attempts"] == 3
    assert "bad image" in cms.settings["lastError"]


def test_warns_before_token_expiry_and_keeps_posting(db):
    cms = FakeCMS(settings(tokenExpiresAt=(NOW + timedelta(days=3)).isoformat()), [art(1)])
    stats = post_to_instagram(Config(), db, cms, FakeIG(), now=NOW)
    assert "token_expires" in stats and stats["posted"] == 1
    assert cms.updates[0]["lastError"].startswith("Доступ к Instagram истекает")


def test_never_expiring_token_has_no_warning(db):
    cms = FakeCMS(settings(tokenExpiresAt=None), [art(1)])
    stats = post_to_instagram(Config(), db, cms, FakeIG(), now=NOW)
    assert "token_expires" not in stats
