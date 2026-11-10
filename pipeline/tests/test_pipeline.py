import json
from datetime import datetime, timedelta, timezone

import pytest

from qtnews import db as dbm
from qtnews.cluster import cluster_new_items
from qtnews.config import Config
from qtnews.db import Database
from qtnews.feeds import extract_main_text, normalize_url, parse_feed
from qtnews.lexical import markdown_to_lexical
from qtnews.llm import extract_json
from qtnews.main import process
from qtnews.cms import EditorialSettings
from qtnews.scoring import heuristic_score, score_stories
from qtnews.selection import pick, slots_for_this_run
from qtnews.slug import slugify
from qtnews.writer import SourceMaterial, write_article

NOW = datetime.now(timezone.utc).replace(microsecond=0)
ISO = lambda dt: dt.isoformat()  # noqa: E731

RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>
<item><title>OpenAI unveils new reasoning model</title><link>https://ex.com/a?utm_source=rss</link>
<description>&lt;p&gt;OpenAI on Monday released...&lt;/p&gt;</description><pubDate>Mon, 09 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title></title><link>https://ex.com/empty</link></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Nvidia earnings beat</title><link rel="alternate" href="https://ex.org/n/"/>
<updated>2026-11-09T12:00:00Z</updated><summary>Revenue up</summary></entry></feed>"""


@pytest.fixture
def db():
    d = Database("sqlite:///:memory:")
    d.init_schema()
    return d


def add(db, src, title, summary="", hours_ago=1, weight=7):
    with db.tx():
        return db.add_item(source_id=src, source_name=src.title(), source_weight=weight,
                           url=f"https://{src}.com/{abs(hash(title))}", title=title, summary=summary,
                           published_at=ISO(NOW - timedelta(hours=hours_ago)))


# --- feeds -------------------------------------------------------------------------------
def test_parse_rss_and_atom():
    now = datetime(2026, 11, 10, tzinfo=timezone.utc)
    rss = parse_feed(RSS, now)
    assert len(rss) == 1
    assert rss[0].url == "https://ex.com/a"
    assert rss[0].summary.startswith("OpenAI on Monday")
    assert rss[0].published_at == "2026-11-09T10:00:00+00:00"
    atom = parse_feed(ATOM, now)
    assert atom[0].url == "https://ex.org/n" and atom[0].title == "Nvidia earnings beat"


def test_future_dates_clamped_and_url_normalized():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert parse_feed(RSS, now)[0].published_at == now.isoformat()
    assert normalize_url("HTTPS://Ex.com/a/?b=1&utm_medium=x#frag") == "https://ex.com/a?b=1"


def test_extract_main_text_drops_chrome():
    html = "<html><nav>menu menu menu menu menu menu menu menu menu</nav><article><p>" + "Fact. " * 20 + \
           "</p><script>x()</script></article></html>"
    text = extract_main_text(html)
    assert "Fact." in text and "menu" not in text and "x()" not in text


# --- db ----------------------------------------------------------------------------------
def test_duplicate_urls_ignored(db):
    with db.tx():
        assert db.add_item(source_id="a", source_name="A", source_weight=5, url="https://x/1", title="t",
                           summary="", published_at=ISO(NOW)) is not None
        assert db.add_item(source_id="b", source_name="B", source_weight=5, url="https://x/1", title="t",
                           summary="", published_at=ISO(NOW)) is None


# --- clustering ----------------------------------------------------------------------------
def test_clustering_groups_same_event(db):
    add(db, "verge", "Apple announces iPhone 18 Pro with new periscope camera", "Apple unveiled iPhone 18 Pro")
    add(db, "reuters", "Apple unveils iPhone 18 Pro, adds periscope camera", "Apple Inc unveiled iPhone 18 Pro")
    add(db, "wired", "Microsoft patches critical Windows zero-day exploited by hackers", "Security update")
    stats = cluster_new_items(db, ISO(NOW - timedelta(days=2)), 0.42)
    assert stats == {"new_items": 3, "new_stories": 2, "attached": 1}
    # Новая публикация о том же событии прикрепляется к существующему сюжету
    add(db, "cnbc", "iPhone 18 Pro: Apple's periscope camera explained", "Apple iPhone 18 Pro camera")
    assert cluster_new_items(db, ISO(NOW - timedelta(days=2)), 0.42)["attached"] == 1


# --- scoring -------------------------------------------------------------------------------
def test_heuristic_prefers_coverage_and_freshness(db):
    from qtnews.db import Item
    mk = lambda s, h, w=7: Item(0, s, s, w, "u", "t", "", ISO(NOW - timedelta(hours=h)), 1)  # noqa: E731
    one = heuristic_score([mk("a", 1)])
    many = heuristic_score([mk(s, 1) for s in "abcde"])
    old = heuristic_score([mk(s, 30) for s in "abcde"])
    assert many > one and many > old and 0 <= one <= 10


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def complete(self, **kw):
        self.prompts.append(kw)
        r = self.responses.pop(0)
        return r(kw) if callable(r) else r


def test_score_stories_with_llm(db):
    add(db, "verge", "Big AI launch")
    cluster_new_items(db, ISO(NOW - timedelta(days=1)), 0.42)
    sid = db.stories_by_status([dbm.NEW], "0")[0].id
    llm = FakeLLM([json.dumps({"stories": [{"id": sid, "score": 9, "category": "ai", "reason": "big"}]})])
    out = score_stories(db, llm, "m", "0", [{"slug": "ai", "name": "ЖИ"}])
    s = db.get_story(sid)
    assert out["llm_scored"] == 1 and s.status == dbm.SCORED and s.category == "ai" and s.llm_score == 9


def test_score_survives_llm_failure(db):
    add(db, "verge", "Something")
    cluster_new_items(db, "0", 0.42)
    score_stories(db, FakeLLM(["no json here", "still nothing"]), "m", "0", [])
    assert db.stories_by_status([dbm.SCORED], "0")[0].final_score > 0


# --- selection -----------------------------------------------------------------------------
def test_slots_spread_quota_over_day():
    noon = datetime(2026, 11, 10, 7, 0, tzinfo=timezone.utc)  # 12:00 в Алматы (UTC+5)
    n = slots_for_this_run(quota=18, done_today=6, max_per_run=3, tz="Asia/Almaty", interval_min=60, now=noon)
    assert 1 <= n <= 3
    assert slots_for_this_run(quota=18, done_today=18, max_per_run=3, tz="Asia/Almaty", interval_min=60,
                              now=noon) == 0
    night = datetime(2026, 11, 9, 21, 0, tzinfo=timezone.utc)  # 02:00 ночи
    assert slots_for_this_run(quota=18, done_today=0, max_per_run=3, tz="Asia/Almaty", interval_min=60,
                              now=night) == 0


def test_pick_diversifies_categories():
    from qtnews.db import Story
    mk = lambda i, sc, c: Story(i, "t", "", dbm.SCORED, 0, None, sc, c, None, None, 0)  # noqa: E731
    stories = [mk(1, 9, "ai"), mk(2, 8.9, "ai"), mk(3, 7, "security"), mk(4, 3, "gadgets")]
    assert [s.id for s in pick(stories, 2, 5)] == [1, 3]
    assert [s.id for s in pick(stories, 3, 5)] == [1, 3, 2]


# --- lexical / slug / json ----------------------------------------------------------------
def test_markdown_to_lexical():
    lex = markdown_to_lexical("Лид **маңызды**.\n\n## Тақырып\n\n- бір\n- [екі](https://a.kz)\n\nСоңы")
    kinds = [c["type"] for c in lex["root"]["children"]]
    assert kinds == ["paragraph", "heading", "list", "paragraph"]
    assert lex["root"]["children"][0]["children"][1] == {**lex["root"]["children"][0]["children"][1], "format": 1}
    link = lex["root"]["children"][2]["children"][1]["children"][0]
    assert link["type"] == "link" and link["fields"]["url"] == "https://a.kz"


def test_slugify_kazakh():
    assert slugify("Қазақстанда жасанды интеллект: OpenAI жаңа моделі") == \
        "qazaqstanda-zhasandy-intellekt-openai-zhanga-modeli"


def test_extract_json_variants():
    assert extract_json('ok ```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('prefix {"a": [1, 2]} suffix') == {"a": [1, 2]}


# --- writer + end-to-end ------------------------------------------------------------------
ARTICLE = {"title": "OpenAI жаңа ойлау моделін таныстырды", "excerpt": "Лид", "tags": ["OpenAI", "ЖИ"],
           "body_markdown": "OpenAI компаниясы жаңа модель шығарды. " * 20, "seo_title": "OpenAI",
           "seo_description": "desc", "category": "ai"}


def test_write_article_runs_qa():
    llm = FakeLLM([json.dumps(ARTICLE),
                   json.dumps({"ok": True, "issues": ["термин түзетілді"], "article": {**ARTICLE, "title": ARTICLE["title"] + "!"}})])
    d = write_article(llm, "m", [SourceMaterial("Verge", "https://v", "h", "s")], glossary=[{"term": "AI", "kk": "ЖИ"}],
                      categories=[{"slug": "ai", "name": "ЖИ"}], style_guide="", suggested_category=None)
    assert d.qa_ok and d.title.endswith("!") and d.sources == [{"name": "Verge", "url": "https://v"}]
    assert "AI → ЖИ" in llm.prompts[0]["prompt"]


class FakeCMS:
    def __init__(self, auto_publish):
        self.auto = auto_publish
        self.created = []

    def settings(self):
        return EditorialSettings(auto_publish=self.auto, daily_quota=50, min_score=0, publish_from_hour=0,
                                 publish_to_hour=24)

    def categories(self):
        return [{"id": 7, "slug": "ai", "name": "ЖИ"}]

    def glossary(self):
        return []

    def find_article_by_story(self, sid):
        return None

    def slug_exists(self, slug):
        return False

    def create_article(self, payload):
        self.created.append(payload)
        return {"id": "art1"}


@pytest.mark.parametrize("auto,expected", [(True, "published"), (False, "review")])
def test_process_end_to_end(db, auto, expected):
    add(db, "verge", "OpenAI launches reasoning model o5", "OpenAI launched o5")
    add(db, "reuters", "OpenAI launches o5 reasoning model", "OpenAI launched o5 on Monday")

    def scorer(kw):
        sid = int(kw["prompt"].split("id=")[1].split(";")[0])
        return json.dumps({"stories": [{"id": sid, "score": 9, "category": "ai", "reason": "x"}]})

    llm = FakeLLM([scorer, json.dumps(ARTICLE), json.dumps({"ok": True, "issues": [], "article": ARTICLE})])
    cms = FakeCMS(auto)
    cfg = Config(database_url="sqlite:///:memory:", max_articles_per_run=3)
    stats = process(cfg, db, cms, llm, None)
    assert stats["selected"] == 1 and len(cms.created) == 1
    art = cms.created[0]
    assert art["status"] == expected and art["category"] == 7 and art["pipelineStoryId"] > 0
    assert art["content"]["root"]["children"][0]["type"] == "paragraph"
    # повторный запуск не создаёт дубль
    assert process(cfg, db, cms, FakeLLM([]), None)["selected"] == 0


def test_process_without_ai_creates_review_drafts(db):
    add(db, "verge", "Hackers exploit zero-day vulnerability in Chrome", "Google patched a zero-day exploit")
    add(db, "wired", "Chrome zero-day vulnerability exploited by hackers", "Attackers exploited the bug")
    cms = FakeCMS(auto_publish=True)  # даже с автопубликацией черновики без перевода не публикуются
    cms.categories = lambda: [{"id": 1, "slug": "security", "name": "Киберқауіпсіздік"}, {"id": 2, "slug": "ai", "name": "ЖИ"}]
    stats = process(Config(database_url="sqlite:///:memory:", max_articles_per_run=3), db, cms, None, None)
    assert stats["review"] == 1 and stats["published"] == 0
    art = cms.created[0]
    assert art["status"] == "review" and art["needsTranslation"] is True and art["aiGenerated"] is False
    assert art["category"] == 1 and len(art["sources"]) == 2
    texts = [n.get("text", "") for b in art["content"]["root"]["children"] for n in b.get("children", [])]
    assert any("Аударма күтілуде" in t for t in texts)


def test_guess_category():
    from qtnews.db import Item
    from qtnews.scoring import guess_category
    it = lambda t: Item(0, "s", "s", 5, "u", t, "", ISO(NOW), 1)  # noqa: E731
    allowed = {"ai", "security", "startups", "gadgets"}
    assert guess_category([it("OpenAI releases new model for ChatGPT")], allowed) == "ai"
    assert guess_category([it("Startup raises $50M Series B at $1B valuation")], allowed) == "startups"
    assert guess_category([it("Weather is nice")], allowed) is None
