from datetime import datetime, timedelta, timezone

import pytest

from qtnews.config import Config
from qtnews.db import Database
from qtnews.tiktok import TITLE_LIMIT, TikTokError, post_to_tiktok, tiktok_title

NOW = datetime(2026, 11, 20, 16, 0, tzinfo=timezone.utc)


def art(i, **kw):
    a = {"id": i, "slug": f"news-{i}", "title": f"Жаңалық {i}", "excerpt": "Анонс.",
         "updatedAt": "2026-11-20T15:00:00.000Z", "category": {"slug": "ai"}, "sources": [{"name": "Reuters"}]}
    a.update(kw)
    return a


class FakeCMS:
    def __init__(self, settings, articles):
        self.settings, self.articles, self.updates = settings, articles, []

    def tiktok_settings(self):
        return dict(self.settings)

    def update_tiktok_settings(self, data):
        self.updates.append(data)
        self.settings.update(data)

    def published_since(self, since_iso, limit=50):
        return list(self.articles)


class FakeTT:
    def __init__(self, fail=None, refresh_fail=False):
        self.drafts, self.refreshed, self.fail, self.refresh_fail = [], 0, fail, refresh_fail

    def refresh(self, key, secret, refresh_token):
        if self.refresh_fail:
            raise TikTokError("invalid_grant", "invalid_grant")
        self.refreshed += 1
        return {"access_token": "new-access", "expires_in": 86400, "refresh_token": "new-refresh",
                "refresh_expires_in": 31536000}

    def upload_photo_draft(self, token, image, title, description):
        if self.fail:
            raise TikTokError(self.fail)
        self.drafts.append((token, image, title, description))
        return f"p_pub_url~{len(self.drafts)}"


def settings(**kw):
    s = {"enabled": True, "accessToken": "acc", "refreshToken": "ref", "dailyLimit": 5, "lookbackHours": 6,
         "accessExpiresAt": (NOW + timedelta(hours=20)).isoformat(), "hashtags": "#TechTalQ"}
    s.update(kw)
    return s


@pytest.fixture
def db():
    d = Database("sqlite:///:memory:")
    d.init_schema()
    return d


def test_title_is_trimmed_to_tiktok_limit():
    assert len(tiktok_title(art(1, title="сөз " * 60))) <= TITLE_LIMIT


def test_sends_one_draft_per_run_with_site_image(db):
    cms, tt = FakeCMS(settings(), [art(1), art(2)]), FakeTT()
    s1 = post_to_tiktok(Config(), db, cms, tt, now=NOW)
    s2 = post_to_tiktok(Config(), db, cms, tt, now=NOW + timedelta(minutes=30))
    assert (s1["article"], s2["article"]) == (1, 2)
    assert tt.drafts[0][1].startswith("https://techtalq.kz/ig/news-1?v=")
    assert "#TechTalQ" in tt.drafts[0][3]
    assert post_to_tiktok(Config(), db, cms, tt, now=NOW + timedelta(hours=1))["sent"] == 0


def test_refreshes_access_token_before_expiry(db):
    cms, tt = FakeCMS(settings(accessExpiresAt=(NOW + timedelta(minutes=30)).isoformat()), [art(1)]), FakeTT()
    stats = post_to_tiktok(Config(), db, cms, tt, now=NOW)
    assert tt.refreshed == 1 and stats["token_refreshed"]
    assert cms.settings["refreshToken"] == "new-refresh"
    assert tt.drafts[0][0] == "new-access"


def test_refresh_failure_asks_to_reconnect(db):
    cms = FakeCMS(settings(accessExpiresAt=None), [art(1)])
    stats = post_to_tiktok(Config(), db, cms, FakeTT(refresh_fail=True), now=NOW)
    assert stats["skipped"] == "token" and "Переподключить TikTok" in cms.settings["lastError"]


def test_failure_retried_then_given_up(db):
    cms, tt = FakeCMS(settings(), [art(1)]), FakeTT(fail="url_ownership_unverified")
    for k in range(4):
        post_to_tiktok(Config(), db, cms, tt, now=NOW + timedelta(minutes=30 * k))
    assert db.social_get(1, "tiktok")["attempts"] == 3
    assert "url_ownership_unverified" in cms.settings["lastError"]


def test_disabled_and_daily_limit(db):
    assert post_to_tiktok(Config(), db, FakeCMS(settings(enabled=False), [art(1)]), FakeTT(), now=NOW)["skipped"] == "disabled"
    cms, tt = FakeCMS(settings(dailyLimit=1), [art(1), art(2)]), FakeTT()
    post_to_tiktok(Config(), db, cms, tt, now=NOW)
    assert post_to_tiktok(Config(), db, cms, tt, now=NOW + timedelta(minutes=30))["skipped"] == "daily limit"
