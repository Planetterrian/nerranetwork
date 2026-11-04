"""Nov 3 2026 — the daily audit becomes an instrument.

The Grok reviewer's 1-10 is the network's only daily editorial number. It
read flat at 6.1-6.2 from Sep 21; 12 of 75 INCOHERENT criticals in 16 days
were artifacts of the instrument; the score lived only in an issue title
(``api/daily-review.json`` is overwritten every run) so no surface showed a
show's score over time — SpaceX's 5.38 over Oct 18 - Nov 2, the lowest daily
show, was recomputed by hand from git history; the audit had opened 151
dated issues nobody closed; and seven shows promised minutes they did not
deliver with nothing reading the drift.

* every YES quotes the sentence it is about, and a quote the text does not
  contain (or no quote) is downgraded to info and counted as ungrounded;
* the score persists per reviewed episode (``api/editorial_score_history.json``,
  90-day window, on daily-audit.yml's add-paths) and the dashboard reads a
  14-day mean per show beside the audience headline;
* SpaceX's ledger carries the number;
* ONE rolling issue, edited in place; a dated issue only for a critical that
  repeats on three of a show's episodes running; the dated backlog closes;
* the promised length is computed from the show's own last 14 episodes
  (``engine.cadence``), applied per show on the operator's yes, and the
  daily audit warns — never fails — on a public string that drifts.

No test here calls a model: the reviewer client is a fake.
"""

from __future__ import annotations

import datetime
import importlib
import json
import re
import statistics
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


def _rv():
    return importlib.import_module("review_episodes")


TEXT = (
    "Tesla delivered more cars in Norway this month than in any October on record. "
    "A delivery delay would not alter either result. "
    "The pack holds spare room for LFP cells, the filing says. "
    "Shares closed Friday at four hundred and two dollars."
)


# ---------------------------------------------------------------------------
# 1. Every YES quotes a sentence found in the text
# ---------------------------------------------------------------------------

class TestEveryYesQuotesItsSentence:

    def test_unquoted_yes_is_info_and_quoted_found_yes_stays_a_finding(self):
        rv = _rv()
        reply = (
            "FACTUAL_ERRORS: NO\n"
            "FACTUAL_DOUBT: NO\n"
            'INCOHERENT: YES — "A delivery delay would not alter either result." — no referent\n'
            "REPETITIVE: YES — the hook is restated in the body\n"
            'OFF_TOPIC: YES — "Shares closed Friday at four hundred and two dollars." — market tape\n'
            "TONE_BREAK: NO\n"
            "INCOMPLETE: NO\n"
            "QUALITY_SCORE: 6\n"
            "SUMMARY: Fine.\n"
        )
        ep = rv.EpisodeReview(show_slug="tesla", show_name="Tesla", episode_num=1,
                              date="2026-11-03")
        rv.apply_review_reply(ep, reply, TEXT)
        by_title = {i.title: i.severity for i in ep.issues}
        assert by_title["AI review: Incoherent"] == "critical"
        assert by_title["AI review: Off Topic"] == "warning"
        ungrounded = [t for t in by_title if t.startswith("AI review: Repetitive")]
        assert ungrounded and by_title[ungrounded[0]] == "info"
        assert "ungrounded" in ungrounded[0]
        assert ep.grounded_flags == ["INCOHERENT", "OFF_TOPIC"]
        assert ep.ungrounded_flags == ["REPETITIVE"]
        assert ep.quality_score == 6
        assert ep.flags["FACTUAL_ERRORS"] is False and ep.flags["REPETITIVE"] is True

    def test_a_quote_the_text_does_not_contain_is_ungrounded(self):
        rv = _rv()
        reply = ('INCOHERENT: YES — "Musk named the new cluster Spam and Gun Range." — what\n'
                 "QUALITY_SCORE: 5\n")
        ep = rv.EpisodeReview(show_slug="spacex", show_name="SpaceX", episode_num=2,
                              date="2026-11-03")
        rv.apply_review_reply(ep, reply, TEXT)
        assert ep.ungrounded_flags == ["INCOHERENT"]
        assert not [i for i in ep.issues if i.severity == "critical"
                    and i.title.startswith("AI review")]

    def test_a_word_is_not_a_sentence(self):
        rv = _rv()
        assert not rv.quote_is_grounded("Spam", "Musk named one cluster Spam.")
        assert not rv.quote_is_grounded("either result", TEXT)
        assert rv.quote_is_grounded("A delivery delay would not alter either result.", TEXT)

    def test_an_elided_quote_and_bold_markers_still_ground(self):
        rv = _rv()
        reply = ('**INCOHERENT:** YES — “Tesla delivered more cars … than in any '
                 'October on record.” — which month\n**QUALITY_SCORE:** 7\n')
        parsed = rv.parse_review_reply(reply, TEXT)
        assert parsed["flags"] == {"INCOHERENT": True}
        assert parsed["findings"][0]["grounded"] is True
        assert parsed["score"] == 7

    def test_score_outside_one_to_ten_is_unmeasured_never_zero(self):
        rv = _rv()
        assert rv.parse_review_reply("QUALITY_SCORE: 0\n", TEXT)["score"] is None
        assert rv.parse_review_reply("QUALITY_SCORE: 11\n", TEXT)["score"] is None
        assert rv.parse_review_reply("no score here", TEXT)["score"] is None

    def test_factual_doubt_stays_a_note_and_the_names_survive(self):
        rv = _rv()
        reply = 'FACTUAL_DOUBT: YES — "The pack holds spare room for LFP cells, the filing says." — memory\n'
        ep = rv.EpisodeReview(show_slug="tesla", show_name="T", episode_num=3, date="2026-11-03")
        rv.apply_review_reply(ep, reply, TEXT)
        assert [(i.severity, i.title) for i in ep.issues] == [
            ("info", "AI review: Factual Doubt (reviewer memory only)")]
        assert ep.grounded_flags == [] and ep.ungrounded_flags == []
        src = (ROOT / "review_episodes.py").read_text(encoding="utf-8")
        assert "FACTUAL_ERRORS" in src and "FACTUAL_DOUBT" in src
        assert "EVERY YES MUST QUOTE" in src

    def test_the_review_call_grounds_against_the_text_it_sent(self, monkeypatch):
        """End to end through ai_review_episode with a fake client — no model."""
        rv = _rv()
        import openai

        sent = {}
        reply = ('INCOHERENT: YES — "A delivery delay would not alter either result." — x\n'
                 "REPETITIVE: YES — restated\nQUALITY_SCORE: 4\nSUMMARY: thin\n")

        class _Msg:
            content = reply

        class _Choice:
            message = _Msg()

        class _Resp:
            choices = [_Choice()]
            usage = None

        class _Client:
            def __init__(self, **kw):
                self.chat = type("Chat", (), {})()
                self.chat.completions = type("Comp", (), {})()

                def _create(**kw):
                    sent.update(kw)
                    return _Resp()
                self.chat.completions.create = _create

        monkeypatch.setattr(openai, "OpenAI", _Client)
        monkeypatch.setenv("GROK_API_KEY", "test-key")
        monkeypatch.setattr(rv, "_load_reviewer_settings", lambda slug: ("test-reviewer", 1500, 0.3))
        ep = rv.EpisodeReview(show_slug="spacex", show_name="SpaceX Daily", episode_num=9,
                              date="2026-11-03", reader_text=TEXT)
        rv.ai_review_episode(ep)
        assert "EVERY YES MUST QUOTE" in sent["messages"][0]["content"]
        assert ep.ai_reviewed and ep.quality_score == 4
        assert ep.grounded_flags == ["INCOHERENT"] and ep.ungrounded_flags == ["REPETITIVE"]
        assert {i.title: i.severity for i in ep.issues}["AI quality score: 4/10"] == "warning"


# ---------------------------------------------------------------------------
# 2. The score persists
# ---------------------------------------------------------------------------

def _scored_ep(rv, slug="spacex", num=150, date="2026-11-03", score=5,
               grounded=("INCOHERENT",), ungrounded=(), crit_titles=("AI review: Incoherent",)):
    ep = rv.EpisodeReview(show_slug=slug, show_name=slug, episode_num=num, date=date)
    ep.ai_reviewed = True
    ep.quality_score = score
    ep.flags = {"INCOHERENT": bool(grounded or ungrounded), "REPETITIVE": False}
    ep.grounded_flags = list(grounded)
    ep.ungrounded_flags = list(ungrounded)
    for t in crit_titles:
        ep.issues.append(rv.Issue(slug, num, "critical", t, "d"))
    return ep


class TestTheScorePersists:

    def test_daily_review_json_carries_the_score_and_the_precision_floor(self, tmp_path):
        rv = _rv()
        a = _scored_ep(rv, grounded=("INCOHERENT",), ungrounded=("REPETITIVE",))
        b = rv.EpisodeReview(show_slug="tesla", show_name="T", episode_num=700, date="2026-11-03")
        out = tmp_path / "daily-review.json"
        rv.write_review_json(datetime.date(2026, 11, 3), [a, b], [], out)
        data = json.loads(out.read_text(encoding="utf-8"))
        ep_a, ep_b = data["episodes"]
        assert ep_a["quality_score"] == 5
        assert ep_a["flags"] == {"INCOHERENT": True, "REPETITIVE": False}
        assert ep_a["grounded_flags"] == ["INCOHERENT"]
        assert ep_a["ungrounded_flags"] == ["REPETITIVE"]
        assert ep_b["quality_score"] is None  # the AI layer did not run: null, never 0
        s = data["summary"]
        assert s["audit_flags_grounded"] == 1 and s["audit_flags_ungrounded"] == 1
        assert s["audit_flags_grounded_share"] == 0.5
        out2 = tmp_path / "clean.json"
        rv.write_review_json(datetime.date(2026, 11, 3), [b], [], out2)
        s2 = json.loads(out2.read_text(encoding="utf-8"))["summary"]
        assert s2["audit_flags_grounded_share"] is None and s2["quality_score_mean"] is None

    def test_one_row_per_review_pruned_past_ninety_days(self, tmp_path):
        rv = _rv()
        path = tmp_path / "editorial_score_history.json"
        path.write_text(json.dumps({"rows": [
            {"date": "2026-07-01", "show": "spacex", "episode": 1, "score": 5},
            {"date": "2026-10-01", "show": "spacex", "episode": 120, "score": 6},
        ]}), encoding="utf-8")
        today = datetime.date(2026, 11, 3)
        rows = rv.append_editorial_score_history(
            today, [_scored_ep(rv, num=150), _scored_ep(rv, slug="tesla", num=700, score=7)],
            path=path)
        assert [(r["show"], r["episode"]) for r in rows] == [
            ("spacex", 120), ("spacex", 150), ("tesla", 700)]
        new = rows[1]
        assert new == {
            "date": "2026-11-03", "show": "spacex", "episode": 150, "score": 5,
            "flags": {"INCOHERENT": True, "REPETITIVE": False},
            "grounded": ["INCOHERENT"], "ungrounded": [], "critical": 1,
            "criticals": ["AI review: Incoherent"], "reviewed_on": "2026-11-03",
        }
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        assert on_disk["retention_days"] == 90 and len(on_disk["rows"]) == 3
        # one row per line — the daily commit is a few lines of diff
        assert sum(1 for ln in path.read_text().splitlines() if ln.strip().startswith('{"date"')) == 3

    def test_a_second_run_replaces_its_row_but_never_erases_a_score(self, tmp_path):
        rv = _rv()
        path = tmp_path / "h.json"
        today = datetime.date(2026, 11, 3)
        rv.append_editorial_score_history(today, [_scored_ep(rv, score=5)], path=path)
        rv.append_editorial_score_history(today, [_scored_ep(rv, score=6)], path=path)
        rows = rv.load_editorial_score_history(path)
        assert len(rows) == 1 and rows[0]["score"] == 6
        structural_only = rv.EpisodeReview(show_slug="spacex", show_name="s",
                                           episode_num=150, date="2026-11-03")
        rows = rv.append_editorial_score_history(today, [structural_only], path=path)
        assert len(rows) == 1 and rows[0]["score"] == 6

    def test_the_committed_history_parses(self):
        data = json.loads((ROOT / "api" / "editorial_score_history.json").read_text(encoding="utf-8"))
        assert data["retention_days"] == 90 and isinstance(data["rows"], list)
        for row in data["rows"]:
            assert {"date", "show", "episode", "score", "flags", "critical"} <= set(row)
            assert row["score"] is None or 1 <= row["score"] <= 10

    def test_the_audit_commits_the_history(self):
        wf = (ROOT / ".github" / "workflows" / "daily-audit.yml").read_text(encoding="utf-8")
        at = wf.index("add-paths:")
        block = wf[at:wf.index("commit-message:", at)]
        assert "api/editorial_score_history.json" in block

    def test_run_review_appends_before_the_issue_step(self):
        src = (ROOT / "review_episodes.py").read_text(encoding="utf-8")
        body = src[src.index("def run_review("):src.index("def write_review_json(")]
        assert body.index("append_editorial_score_history(") < body.index("create_github_issue(")


# ---------------------------------------------------------------------------
# 3. The dashboard reads the score beside the audience headline
# ---------------------------------------------------------------------------

def _gd():
    return importlib.import_module("scripts.generate_dashboard")


class TestTheDashboardReadsTheScore:

    def _root(self, tmp_path, rows):
        (tmp_path / "api").mkdir()
        (tmp_path / "shows").mkdir()
        for slug in ("spacex", "tesla"):
            (tmp_path / "shows" / f"{slug}.yaml").write_text("name: x\n", encoding="utf-8")
        (tmp_path / "shows" / "network_meta.yaml").write_text("{}\n", encoding="utf-8")
        (tmp_path / "api" / "editorial_score_history.json").write_text(
            json.dumps({"rows": rows}), encoding="utf-8")
        return tmp_path

    def test_fourteen_day_means_with_floors(self, tmp_path):
        gd = _gd()
        today = datetime.date(2026, 11, 3)
        rows = []
        for i in range(12):
            day = (today - datetime.timedelta(days=i)).isoformat()
            rows.append({"date": day, "show": "spacex", "episode": 200 - i, "score": 5,
                         "critical": 1, "grounded": ["INCOHERENT"], "ungrounded": ["REPETITIVE"]})
        rows.append({"date": today.isoformat(), "show": "tesla", "episode": 700, "score": 8,
                     "critical": 0})
        rows.append({"date": "2026-10-01", "show": "tesla", "episode": 680, "score": 1,
                     "critical": 3})  # outside the window
        s = gd.build_editorial_score_section(self._root(tmp_path, rows), today=today)
        assert s["shows"]["spacex"] == {"mean": 5.0, "n": 12, "reviews": 12, "critical": 12}
        assert s["shows"]["tesla"]["mean"] is None  # one review: under the floor, never 0
        assert s["network"]["mean"] == round((12 * 5 + 8) / 13, 2)
        assert s["network"]["flags_grounded_share"] == 0.5
        assert s["lowest"] == ["spacex"]

    def test_no_history_is_unconfigured_not_zero(self, tmp_path):
        gd = _gd()
        (tmp_path / "api").mkdir()
        assert gd.build_editorial_score_section(tmp_path)["configured"] is False

    def test_live_keys_exist_for_every_show(self, tmp_path):
        gd = _gd()
        m = gd._editorial_score_live_metrics(self._root(tmp_path, []))
        assert set(m) == {"editorial_score_14d_mean", "editorial_score_14d_spacex",
                          "editorial_score_14d_tesla"}
        assert all(v is None for v in m.values())
        live = gd._experiment_live_metrics(ROOT)
        assert "editorial_score_14d_mean" in live and "editorial_score_14d_spacex" in live
        assert "editorial_score_14d_network_meta" not in live

    def test_the_tile_sits_beside_the_audience_headline(self):
        html = (ROOT / "management.html").read_text(encoding="utf-8")
        ah = html.index('statTile("Audience · RSS downloads 7d"')
        es = html.index('statTile("Editorial score · 14d"')
        assert ah < es < html.index('statTile("RSS downloads · all-time"')
        src = (ROOT / "scripts" / "generate_dashboard.py").read_text(encoding="utf-8")
        assert '"editorial_score": build_editorial_score_section(root)' in src


# ---------------------------------------------------------------------------
# 4. One rolling issue
# ---------------------------------------------------------------------------

class _FakeGh:
    def __init__(self, open_issues=None):
        self.issues = list(open_issues or [])
        self.created, self.edited, self.closed = [], [], []
        self._next = 900

    def ensure_label(self, name, color):
        pass

    def list_open(self, label, limit=1000):
        return [dict(i) for i in self.issues]

    def create(self, title, body, labels):
        self._next += 1
        url = f"https://github.com/o/r/issues/{self._next}"
        self.created.append((title, body, labels))
        self.issues.append({"number": self._next, "title": title, "url": url})
        return url

    def edit(self, number, body):
        self.edited.append((number, body))
        return True

    def close(self, number, comment):
        self.closed.append((number, comment))
        self.issues = [i for i in self.issues if i["number"] != number]
        return True


def _history(slug, crit_by_day):
    return [{"date": day, "show": slug, "episode": 100 + n, "score": 4,
             "criticals": crits, "reviewed_on": day}
            for n, (day, crits) in enumerate(crit_by_day)]


class TestOneRollingIssue:

    def test_first_run_creates_then_edits_in_place(self):
        rv = _rv()
        gh = _FakeGh()
        ep = _scored_ep(rv)
        url = rv.create_github_issue("2026-11-03", [ep], client=gh, history_rows=[])
        assert [c[0] for c in gh.created] == [rv.ROLLING_ISSUE_TITLE]
        assert url and "| spacex | Ep150 | 5/10 | 1 critical |" in gh.created[0][1]
        rv.create_github_issue("2026-11-04", [ep], client=gh, history_rows=[])
        assert len(gh.created) == 1 and len(gh.edited) == 1
        assert "2026-11-04" in gh.edited[0][1]

    def test_the_dated_backlog_closes_pointing_at_the_rolling_issue(self):
        rv = _rv()
        old = [{"number": n, "title": f"Daily Review 2026-10-{n:02d}: 3 critical issue(s) across 2 show(s)",
                "url": f"u{n}"} for n in range(1, 6)]
        rolling = {"number": 77, "title": rv.ROLLING_ISSUE_TITLE,
                   "url": "https://github.com/o/r/issues/77"}
        other = {"number": 88, "title": "Bug: something else", "url": "u88"}
        gh = _FakeGh(old + [rolling, other])
        rv.create_github_issue("2026-11-03", [_scored_ep(rv)], client=gh, history_rows=[])
        assert sorted(n for n, _ in gh.closed) == [1, 2, 3, 4, 5]
        assert all("issues/77" in c for _, c in gh.closed)
        assert gh.edited and gh.edited[0][0] == 77 and not gh.created

    def test_the_backlog_drains_oldest_first_a_bounded_number_a_run(self):
        rv = _rv()
        old = [{"number": n, "title": f"Daily Review 2026-09-{(n % 28) + 1:02d}: 1 warning(s) across 1 show(s)",
                "url": f"u{n}"} for n in range(200, 200 + rv._SWEEP_MAX_PER_RUN + 10)]
        gh = _FakeGh(list(reversed(old)))
        assert rv.close_superseded_daily_issues(gh, "https://r") == rv._SWEEP_MAX_PER_RUN
        assert [n for n, _ in gh.closed] == list(range(200, 200 + rv._SWEEP_MAX_PER_RUN))
        assert rv.close_superseded_daily_issues(gh, "https://r") == 10

    def test_a_dated_issue_only_on_a_three_episode_repeat(self):
        rv = _rv()
        crit = ["AI review: Incoherent"]
        two = _history("spacex", [("2026-11-02", crit), ("2026-11-03", crit)])
        gh = _FakeGh()
        rv.create_github_issue("2026-11-03", [_scored_ep(rv)], client=gh, history_rows=two)
        assert [c[0] for c in gh.created] == [rv.ROLLING_ISSUE_TITLE]

        three = _history("spacex", [("2026-11-01", crit), ("2026-11-02", crit),
                                    ("2026-11-03", crit + ["AI quality score: N/N"])])
        gh = _FakeGh()
        rv.create_github_issue("2026-11-03", [_scored_ep(rv)], client=gh, history_rows=three)
        titles = [c[0] for c in gh.created]
        assert titles[0] == rv.ROLLING_ISSUE_TITLE
        assert titles[1:] == ["Daily Review 2026-11-03: repeated critical — spacex: AI review: Incoherent"]
        assert gh.created[1][2] == ["automated-review", "severity: critical"]
        # the streak's issue is open: day four opens nothing new
        four = three + _history("spacex", [("2026-11-04", crit)])
        four[-1]["episode"] = 200
        rv.create_github_issue("2026-11-04", [_scored_ep(rv)], client=gh, history_rows=four)
        assert len([t for t, _, _ in gh.created if "repeated critical" in t]) == 1
        assert not gh.closed  # the sweep closes the old dated shape only
        assert not rv._DAILY_TITLE_RE.match(titles[1])

    def test_a_streak_that_ended_earlier_never_reopens(self):
        rv = _rv()
        crit = ["Digest too short (N words)"]
        rows = _history("tesla", [("2026-10-28", crit), ("2026-10-29", crit), ("2026-10-30", crit)])
        assert rv.find_repeated_criticals(rows, "2026-11-03") == []
        assert rv.find_repeated_criticals(rows, "2026-10-30")[0]["key"] == crit[0]

    def test_numbers_never_split_a_streak(self):
        rv = _rv()
        assert rv.critical_key("AI quality score: 3/10") == rv.critical_key("AI quality score: 2/10")

    def test_a_single_show_run_never_overwrites_the_days_table(self):
        rv = _rv()
        gh = _FakeGh([{"number": 77, "title": rv.ROLLING_ISSUE_TITLE, "url": "u"},
                      {"number": 1, "title": "Daily Review 2026-10-01: 1 warning(s) across 1 show(s)",
                       "url": "u1"}])
        assert rv.create_github_issue("2026-11-03", [_scored_ep(rv)], client=gh,
                                      history_rows=[], edit_rolling=False) is None
        assert not gh.edited and not gh.created and not gh.closed

    def test_the_body_fits_github(self):
        rv = _rv()
        eps = []
        for n in range(60):
            ep = _scored_ep(rv, num=n)
            ep.issues.extend(rv.Issue("spacex", n, "info", "AI review note", "x" * 2000)
                             for _ in range(2))
            eps.append(ep)
        body = rv._review_issue_body("2026-11-03", eps, [i for e in eps for i in e.issues])
        assert len(body) <= rv._ISSUE_BODY_MAX and "truncated" in body


# ---------------------------------------------------------------------------
# 5. SpaceX's ledger carries the number
# ---------------------------------------------------------------------------

class TestSpaceXLedgerCarriesTheScore:

    def test_the_entry_parses_and_names_the_live_metric(self):
        path = ROOT / "docs" / "reviews" / "ledger" / "spacex.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        entries = [r for r in data["reviews"]
                   if str(r.get("date")) == "2026-11-03"
                   and "network_review_2026_11_03" in str(r.get("doc") or "")]
        assert len(entries) == 1
        pred = entries[0]["predictions"][0]
        assert pred["metric"].startswith("editorial_score_14d_spacex")
        assert "5.23" in pred["baseline"] and "6.3" in pred["expected"]
        live = _gd()._experiment_live_metrics(ROOT)
        assert pred["metric"].split()[0] in live

    def test_the_splice_kept_the_files_list_indentation(self):
        """Appended by text splice after the Oct 8 entry, at column 0 like
        every entry in this file (a later review appends after it)."""
        text = (ROOT / "docs" / "reviews" / "ledger" / "spacex.yaml").read_text(encoding="utf-8")
        assert "  agent_cost_usd: 0.1983\n- date: '2026-11-03'\n  pr: null\n" in text


# ---------------------------------------------------------------------------
# 6. The promised length is computed, and drift warns
# ---------------------------------------------------------------------------

def _cadence():
    return importlib.import_module("engine.cadence")


def _fake_show(root: Path, slug: str, minutes, rss: str = "", start=datetime.date(2026, 10, 1)):
    out = root / "digests" / slug
    out.mkdir(parents=True)
    (root / "shows").mkdir(exist_ok=True)
    (root / "shows" / f"{slug}.yaml").write_text(yaml.safe_dump({
        "episode": {"output_dir": f"digests/{slug}"},
        "publishing": {"rss_description": rss},
    }), encoding="utf-8")
    for n, m in enumerate(minutes, start=1):
        day = (start + datetime.timedelta(days=n)).strftime("%Y%m%d")
        (out / f"Show_Ep{n:03d}_{day}.md").write_text("x", encoding="utf-8")
        (out / f"metrics_ep{n:03d}.json").write_text(
            json.dumps({"counters": {"audio_duration_s": m * 60}}), encoding="utf-8")
    return out


class TestPromisedLengthIsComputed:

    def test_unintended_consequences_matches_its_committed_median(self):
        cad = _cadence()
        out = ROOT / "digests" / "unintended_consequences"
        dates = {}
        for md in out.glob("*.md"):
            m = re.search(r"_Ep0*(\d+)_(\d{8})\.md$", md.name)
            if m:
                dates.setdefault(int(m.group(1)), m.group(2))
        rows = []
        for mf in out.glob("metrics_ep*.json"):
            ep = int(re.search(r"(\d+)", mf.name).group(1))
            secs = (json.loads(mf.read_text()).get("counters") or {}).get("audio_duration_s")
            if ep in dates and secs:
                rows.append((dates[ep], ep, float(secs) / 60))
        rows.sort()
        got = cad.episode_length_for_slug("unintended_consequences")
        if len(rows) < cad.LENGTH_MIN_EPISODES:
            pytest.skip("fewer than five dated UC episodes in this checkout")
        median = statistics.median(m for _, _, m in rows[-14:])
        n = int(re.fullmatch(r"~(\d+) min", got).group(1))
        assert abs(n - median) <= 1

    def test_registry_string_under_five_episodes(self, tmp_path):
        cad = _cadence()
        _fake_show(tmp_path, "newshow", [9, 9, 9])
        assert cad.episode_length_for_slug("newshow", registry="~12 min", root=tmp_path) == "~12 min"
        assert cad.median_episode_minutes("newshow", root=tmp_path) is None

    def test_dated_by_the_digest_name_never_mtime(self, tmp_path):
        cad = _cadence()
        # 20 episodes: the first six ran 30 min, the newest fourteen 8 min.
        out = _fake_show(tmp_path, "s", [30] * 6 + [8] * 14)
        import os
        for i, mf in enumerate(sorted(out.glob("metrics_ep*.json"))):
            os.utime(mf, (10_000_000 - i * 1000, 10_000_000 - i * 1000))  # oldest file newest
        assert cad.episode_length_for_slug("s", registry="~30 min", root=tmp_path) == "~8 min"

    def test_pages_keep_the_registry_string_until_the_operators_yes(self, tmp_path):
        cad = _cadence()
        _fake_show(tmp_path, "s", [8] * 14)
        assert cad.published_episode_length("s", "~15 min", root=tmp_path,
                                            computed=()) == "~15 min"
        assert cad.published_episode_length("s", "~15 min", root=tmp_path,
                                            computed={"s"}) == "~8 min"
        # an opt-in names a real show (a typo would silently opt in nothing)
        for slug in cad.COMPUTED_LENGTH_SHOWS:
            assert (ROOT / "shows" / f"{slug}.yaml").exists(), slug
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        assert "_apply_published_episode_lengths()" in src

    def test_stated_lengths_are_read_by_shape(self):
        cad = _cadence()
        assert [s[:2] for s in cad.stated_minutes("in about twelve minutes")] == [(12.0, 12.0)]
        assert [s[:2] for s in cad.stated_minutes("~15-18 min")] == [(15.0, 18.0)]
        assert cad.stated_minutes("skippers who sleep in 20-minute fragments") == []

    def test_drift_warns_for_top_worlds_twelve_minutes_and_never_fails(self, tmp_path, capsys,
                                                                    monkeypatch):
        cad = _cadence()
        _fake_show(tmp_path, "omni_view_world", [9.3] * 14,
                   rss="Ten stories, one sign of progress — in about twelve minutes.")
        registry = {"omni_view_world": {
            "about_text": "The whole world in about twelve minutes.",
            "episode_length": "~11-13 min"}}
        report = cad.length_drift_report(tmp_path, registry=registry)
        assert {(r["field"], r["phrase"]) for r in report} == {
            ("rss_description", "about twelve minutes"),
            ("about_text", "about twelve minutes")}
        script = importlib.import_module("scripts.check_promised_lengths")
        monkeypatch.setattr(cad, "length_drift_report", lambda root: report)
        assert script.main() == 0
        out = capsys.readouterr().out
        assert "::warning::omni_view_world rss_description" in out
        assert "about twelve minutes" in out

    def test_the_audit_runs_the_check_and_never_fails_on_it(self):
        wf = (ROOT / ".github" / "workflows" / "daily-audit.yml").read_text(encoding="utf-8")
        at = wf.index("python scripts/check_promised_lengths.py")
        step = wf[wf.rindex("- name:", 0, at):at]
        assert "continue-on-error: true" in step and "if: always()" in step


class TestLessonShowsCarryNoStoryRecurrence:
    """The Aug 16 note exempts lesson shows — their recurrence is curriculum."""

    @pytest.mark.parametrize("slug", ["privet_russian"])
    def test_off(self, slug):
        from engine.config import load_config
        assert load_config(ROOT / "shows" / f"{slug}.yaml").story_recurrence is False


def test_the_reviewer_has_room_for_quoted_flags_and_the_score():
    """Nov 4 2026: each YES carries a quoted sentence and the score line comes
    after the seven flags, so the network's reviewer budget leaves room for
    them; a reply capped short loses QUALITY_SCORE, the instrument's number
    (watch ``ai_reviewed`` against ``ai_scored`` in api/daily-review.json)."""
    from engine.config import load_config
    root = Path(__file__).resolve().parent.parent
    for slug in ("spacex", "tesla", "omni_view_world"):
        assert load_config(root / "shows" / f"{slug}.yaml").llm.reviewer_max_tokens >= 3000

