"""Memory, books and content lake review (Nov 13 2026).

Review: docs/reviews/memory_books_lake_review_2026_11_13.md.
"""

from __future__ import annotations

import sqlite3

from engine import content_lake as cl
from engine import show_memory as sm
from engine import tesla_memory as tm


_JUNK_THEMES = {"recurring_themes": {"happened neutral": 610,
                                     "context perspectives": 597}}


class TestThemeBlockStaysOutOfThePrompt:
    def test_flag_is_off(self):
        assert tm.THEME_BLOCK_IN_PROMPT is False

    def test_show_memory_section_has_no_theme_block(self, tmp_path):
        cfg = sm.get_config("omni_view") or next(iter(sm.SHOW_MEMORY_CONFIGS.values()))
        sm.save_theme_history(dict(_JUNK_THEMES), tmp_path, cfg)
        section = sm.build_memory_section(tmp_path, cfg)
        assert "RECURRING THEMES" not in section
        assert "happened neutral" not in section

    def test_tesla_context_has_empty_theme_block(self, tmp_path):
        tm.save_theme_history(dict(_JUNK_THEMES), tmp_path)
        ctx = tm.get_tesla_memory_context(tmp_path)
        assert ctx["tesla_theme_context_block"] == ""


def _record(n: int, slug: str = "tesla") -> cl.EpisodeRecord:
    digest = (f"# Show\n\n**Robot factory opens in Texas {n}**\n"
              "Tesla said the humanoid line starts in March.\n"
              "Source: https://example.com/a\n")
    et = cl.extract_entities_and_topics(digest, slug)
    return cl.EpisodeRecord(
        show_slug=slug, episode_num=n, date=f"2026-11-{n:02d}",
        title=f"T{n}", hook=f"H{n}", digest_md=digest, podcast_script="",
        summary=digest[:500], headlines=[], source_urls=[],
        entities=et["entities"], topics=et["topics"],
        word_count=len(digest.split()), show_name="S", language="en")


def _dump(db) -> list:
    conn = sqlite3.connect(str(db))
    try:
        return [conn.execute(q).fetchall() for q in (
            "SELECT show_slug, episode_num, date, title, headlines, "
            "source_urls, entities, topics FROM episodes ORDER BY 1, 2",
            "SELECT item_key, title, urls, kind, tokens FROM items ORDER BY 1",
            "SELECT count(*) FROM episodes_fts",
            "SELECT count(*) FROM items_fts",
        )]
    finally:
        conn.close()


class TestBulkWriterMatchesPerEpisodeStore:
    def test_same_rows(self, tmp_path):
        a, b = tmp_path / "a.db", tmp_path / "b.db"
        for n in (1, 2, 3):
            cl.store_episode(_record(n), a)
        with cl.bulk_writer(b) as conn:
            for n in (1, 2, 3):
                cl.store_episode(_record(n), b, conn=conn)
        assert _dump(a) == _dump(b)

    def test_one_bad_record_does_not_sink_the_batch(self, tmp_path):
        db = tmp_path / "c.db"
        bad = _record(2)
        bad.date = None  # NOT NULL column
        with cl.bulk_writer(db) as conn:
            for rec in (_record(1), bad, _record(3)):
                cl.store_episode(rec, db, conn=conn)
        eps = [r[1] for r in _dump(db)[0]]
        assert eps == [1, 3]

    def test_topics_match_the_case_insensitive_patterns(self):
        import re
        text = "The FDA cleared a CRISPR trial; Gigafactory output and LLM news."
        old = sorted(t for t, p in cl._TOPIC_PATTERNS.items() if re.search(p, text))
        assert cl.extract_entities_and_topics(text, "x")["topics"] == old


class TestStatusesFromVerifiedClaims:
    """Patrick's decision A (Nov 13): each run writes a tracked program's
    status from the first VERIFIED claim in its own ledger that is about it."""

    @staticmethod
    def _tracker():
        return {"programs": {
            "starlink": {"display_name": "Starlink", "status": "seed",
                         "key_open_questions": []},
            "argentina_economy": {"display_name": "Argentina Economy",
                                  "status": "seed2", "key_open_questions": []},
        }}

    def test_verified_claim_becomes_the_status(self):
        t = self._tracker()
        claims = [{"claim": "Starlink passed ten million users.",
                   "source_url": "https://e.com/s", "status": "verified"}]
        assert sm.apply_ledger_statuses(t, claims, 9, "2026-11-13") == ["starlink"]
        p = t["programs"]["starlink"]
        assert p["status"] == "Starlink passed ten million users."
        assert p["status_from_ledger"] and p["seed_status"] == "seed"
        assert p["last_major_update_episode"] == 9
        block = sm.build_narrative_status_block(t, "X")
        assert "Latest verified fact: Starlink passed" in block

    def test_one_shared_word_is_not_enough(self):
        t = self._tracker()
        claims = [{"claim": "Argentina's women won the rugby sevens.",
                   "status": "verified"}]
        assert sm.apply_ledger_statuses(t, claims, 9, "2026-11-13") == []
        assert t["programs"]["argentina_economy"]["status"] == "seed2"

    def test_unverified_claims_never_become_memory(self, tmp_path):
        import json
        led = tmp_path / "Show_Ep9_20261113_claims.json"
        led.write_text(json.dumps({"claims": [
            {"claim": "Starlink lost a satellite.", "status": "unverified_not_found"},
            {"claim": "Starlink launched 24 satellites.", "status": "verified_from_fetched"},
        ]}), encoding="utf-8")
        assert sm.find_episode_ledger(tmp_path, 9) == led
        got = sm.verified_ledger_claims(led)
        assert [c["claim"] for c in got] == ["Starlink launched 24 satellites."]

    def test_post_generate_writes_statuses(self):
        import inspect
        assert "update_statuses_from_ledger" in inspect.getsource(sm.memory_post_generate)
        src = open("run_show.py", encoding="utf-8").read()
        assert "apply_ledger_statuses" in src  # Tesla's own tracker too
