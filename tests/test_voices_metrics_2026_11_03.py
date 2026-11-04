"""Mira's rooms become readable (Nov 3 2026, six-month review: efficiency-5 +
voices-8).

``api/dashboard.json`` read $0.00 and ``episodes 0`` for both interview shows
while Ep15 published Nov 1 and 34 rehearsal rooms used ~870 Voice Agent
minutes in two days; ``common.llm()`` discarded every usage object; the
survey, the grades, the eight audio measures and the yield lived only in
Supabase; the Oct 23 billing stop killed 16 show runs with no warning before
the slate. What binds now:

* ``common.llm()`` records (step, meta) through ``pipelines/voices/costs.py``,
  which normalises the SDK usage OBJECT first — the raw object made
  ``record_llm_usage_from_meta`` return False silently (the $0 path);
* ``post_interview.py`` writes ``credit_usage_<date>_room_<id8>.json`` with
  ``services.voice_agent`` (minutes × the ONE rate in ``engine.tracking``,
  labelled estimated) and the room's research lookups; ``narrate.py`` adds
  the takes; ``rehearsal.py`` writes ``credit_usage_<date>_rehearsal_<id8>.json``;
* the rollup classifies both, sums ``voice_agent`` and ``rehearsal``, and
  counts a room as an episode only with ``published: true`` (set by the
  nightly builder from ``interviews.status``, never by publish_episode);
* ``scripts/build_voices_metrics.py`` writes null for every table it could
  not read and exits 0; the dashboard emits the three register metrics;
* the two Voices workflows commit the credit globs (they had no commit step);
* the fire tick pings xAI at the 03:30 ET slot and posts the quota message
  to the webhook on the provider's credit wording.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
sys.path.insert(0, str(ROOT))

from engine import tracking  # noqa: E402
import costs  # noqa: E402


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(name, None)
    return mod


class _Usage:
    """The SDK's usage object as xai_grok returns it (NOT a dict)."""
    prompt_tokens = 900
    completion_tokens = 120
    total_tokens = 1020
    prompt_tokens_details = type("D", (), {"cached_tokens": 100})()


class _Show:
    slug = "age_of_ai"
    name = "The Age of AI"

    def __init__(self, root: Path):
        self.audio_subdir = "digests/age_of_ai"
        self._root = root


@pytest.fixture
def show(tmp_path, monkeypatch):
    monkeypatch.setattr(costs, "ROOT", tmp_path)
    costs.reset()
    return _Show(tmp_path)


# ---------------------------------------------------------------------------
# 1. llm() records the usage; the raw object was the $0 path
# ---------------------------------------------------------------------------

class TestLlmUsageIsRecorded:

    def test_llm_records_an_sdk_usage_object(self, monkeypatch):
        import common
        import digests.xai_grok as xg
        monkeypatch.setattr(xg, "grok_generate_text", lambda **kw: (
            "  hello  ", {"provider": "openai_compat", "model": "grok-4.3", "usage": _Usage()}))
        costs.reset()
        assert common.llm("prompt", step="editorial_passes") == "hello"
        step = costs.tracker()["services"]["grok_api"]["editorial_passes"]
        assert step["prompt_tokens"] == 900
        assert step["completion_tokens"] == 120
        assert step["cached_tokens"] == 100
        assert step["model"] == "grok-4.3"
        assert step["estimated_cost_usd"] > 0

    def test_the_raw_object_was_recorded_as_nothing(self):
        t = tracking.create_tracker("X", 0)
        raw = {"model": "grok-4.3", "usage": _Usage()}
        assert tracking.record_llm_usage_from_meta(t, "s", raw) is False   # the $0 path
        assert costs.record_llm("s", raw, into=t) is True
        assert t["services"]["grok_api"]["s"]["total_tokens"] == 1020

    def test_normalise_meta_shapes(self):
        obj = costs.normalise_meta({"model": "m", "usage": _Usage()})
        assert obj["usage"] == {"prompt_tokens": 900, "completion_tokens": 120, "cached_tokens": 100}
        as_dict = costs.normalise_meta({"model": "m", "usage": {
            "prompt_tokens": 10, "completion_tokens": 5,
            "prompt_tokens_details": {"cached_tokens": 3}}})
        assert as_dict["usage"] == {"prompt_tokens": 10, "completion_tokens": 5, "cached_tokens": 3}
        # The Responses path returns no usage: nothing is recorded, never a zero step.
        responses = costs.normalise_meta({"provider": "openai_responses", "model": "m"})
        assert "usage" not in responses
        t = tracking.create_tracker("X", 0)
        assert costs.record_llm("s", responses, into=t) is False
        assert "s" not in t["services"]["grok_api"]
        assert costs.normalise_meta(None) is None

    def test_llm_default_step_and_the_two_post_interview_steps(self):
        src = (ROOT / "pipelines/voices/common.py").read_text(encoding="utf-8")
        assert 'step: str = "voices_llm"' in src and "costs.record_llm(step, meta)" in src
        post = (ROOT / "pipelines/voices/post_interview.py").read_text(encoding="utf-8")
        assert 'step="editorial_passes"' in post and 'step="interview_retro"' in post
        for step in ("voices_llm", "editorial_passes", "interview_retro"):
            assert step in tracking._STEP_LABELS


# ---------------------------------------------------------------------------
# 2. the rate has one owner; the room file sums to minutes × rate
# ---------------------------------------------------------------------------

class TestVoiceAgentLine:

    def test_one_owner_of_the_rate(self, monkeypatch):
        assert tracking.VOICE_AGENT_COST_PER_MIN == pytest.approx(0.05)
        monkeypatch.delenv("XAI_VOICE_COST_PER_MIN", raising=False)
        assert tracking.voice_agent_rate_per_min() == pytest.approx(0.05)
        monkeypatch.setenv("XAI_VOICE_COST_PER_MIN", "0.08")
        assert tracking.voice_agent_rate_per_min() == pytest.approx(0.08)
        src = (ROOT / "pipelines/voices/rehearsal.py").read_text(encoding="utf-8")
        assert "VOICE_COST_PER_MIN = voice_agent_rate_per_min()" in src
        assert 'os.environ.get("XAI_VOICE_COST_PER_MIN")' not in src

    def test_record_voice_agent_usage_is_additive_and_labelled_estimated(self, monkeypatch):
        monkeypatch.delenv("XAI_VOICE_COST_PER_MIN", raising=False)
        t = tracking.create_tracker("The Age of AI", 0)
        tracking.record_voice_agent_usage(t, 44.0, sessions=1)
        tracking.record_voice_agent_usage(t, 2.5, sessions=6)   # narration takes
        agent = t["services"]["voice_agent"]
        assert agent["minutes"] == pytest.approx(46.5)
        assert agent["sessions"] == 7
        assert agent["basis"] == "estimated"
        assert agent["estimated_cost_usd"] == pytest.approx(46.5 * 0.05)
        assert agent["rate_per_min"] == pytest.approx(0.05)

    def test_save_usage_total_includes_the_voice_agent(self, tmp_path, monkeypatch):
        monkeypatch.delenv("XAI_VOICE_COST_PER_MIN", raising=False)
        t = tracking.create_tracker("The Age of AI", 0)
        tracking.record_voice_agent_usage(t, 40.0, sessions=1)
        tracking.record_tts_usage(t, 1000, provider="grok")
        path = tracking.save_usage(t, tmp_path, filename="credit_usage_2026-11-03_room_abcdef12.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["total_estimated_cost_usd"] == pytest.approx(2.0 + 0.015)

    def test_room_credit_file_from_a_run_row(self, show, monkeypatch):
        monkeypatch.delenv("XAI_VOICE_COST_PER_MIN", raising=False)
        run = {"id": "0f3c9a1e-1111-2222-3333-444444444444", "interview_id": "iv-1",
               "session_kind": "interview", "duration_sec": 2635,
               "grok_session_log": {"research_lookups": 3}}
        # The editorial passes this process ran.
        costs.record_llm("editorial_passes", {"model": "grok-4.3", "usage": _Usage()})
        path = costs.write_room_credit_file(show, run, interview={"id": "iv-1"}, published=False)
        assert path is not None
        assert path.parent == show._root / "digests" / "age_of_ai"
        assert path.name == f"credit_usage_{dt.date.today().isoformat()}_room_0f3c9a1e.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        agent = data["services"]["voice_agent"]
        assert agent["minutes"] == pytest.approx(2635 / 60, abs=0.01)
        assert agent["sessions"] == 1
        assert agent["estimated_cost_usd"] == pytest.approx(2635 / 60 * 0.05, abs=0.001)
        assert data["services"]["search_api"]["calls"] == 3
        assert data["services"]["grok_api"]["editorial_passes"]["total_tokens"] == 1020
        assert data["kind"] == "room" and data["published"] is False
        assert data["room"]["interview_id"] == "iv-1" and data["room"]["duration_sec"] == 2635
        gd = _load("gd_voices_pass", "scripts/generate_dashboard.py")
        assert gd._credit_file_kind(path, "age_of_ai") == "room"

    def test_narration_lands_on_the_room_file(self, show, monkeypatch):
        monkeypatch.delenv("XAI_VOICE_COST_PER_MIN", raising=False)
        run = {"id": "0f3c9a1e-1111-2222-3333-444444444444", "duration_sec": 600}
        path = costs.write_room_credit_file(show, run)
        before = json.loads(path.read_text(encoding="utf-8"))["total_estimated_cost_usd"]
        again = costs.add_narration_usage(show, run["id"], minutes=3.0, sessions=5)
        assert again == path
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["services"]["voice_agent"]["minutes"] == pytest.approx(13.0)
        assert data["services"]["voice_agent"]["sessions"] == 6
        assert data["narration"] == {"minutes": 3.0, "takes": 5, "tts_chars": 0}
        assert data["total_estimated_cost_usd"] == pytest.approx(before + 3.0 * 0.05)
        # No file yet (a narration re-run on another day): one is made.
        fresh = costs.add_narration_usage(show, "deadbeef-0000", tts_chars=2000)
        assert fresh is not None and fresh.name.endswith("_room_deadbeef.json")
        assert json.loads(fresh.read_text(encoding="utf-8"))["services"]["tts_api"]["characters"] == 2000
        # No run id: nothing recorded, nothing raised.
        assert costs.add_narration_usage(show, "", minutes=1.0) is None

    def test_narrate_records_takes_and_the_tts_fallback(self):
        src = (ROOT / "pipelines/voices/narrate.py").read_text(encoding="utf-8")
        assert "def record_narration_usage(" in src
        assert "costs.add_narration_usage(show, os.environ.get(\"INTERVIEW_RUN_ID\"" in src
        agent_path = src[src.index("def narrate("):src.index("def _narrate_with_tts(")]
        assert "take_minutes += _duration(part) / 60.0" in agent_path
        assert "record_narration_usage(show, minutes=take_minutes, sessions=takes)" in agent_path
        tts_path = src[src.index("def _narrate_with_tts("):]
        assert "record_narration_usage(show, tts_chars=" in tts_path

    def test_post_interview_writes_the_room_file_on_both_paths(self):
        src = (ROOT / "pipelines/voices/post_interview.py").read_text(encoding="utf-8")
        assert "def write_room_credit(" in src
        assert "costs.write_room_credit_file(show, run, interview=interview, published=False)" in src
        main = src[src.index("def main()"):src.index("def send_gate1_email(")]
        assert "write_room_credit(run, interview, show)" in main
        short = src[src.index("def handle_too_short("):src.index("def _ext_of(")]
        assert "write_room_credit(run, interview, show)" in short
        # publish_episode never sets the flag — the nightly builder does.
        pub = (ROOT / "pipelines/voices/publish_episode.py").read_text(encoding="utf-8")
        assert "credit_usage" not in pub and "published\"] = True" not in pub

    def test_rehearsal_room_writes_its_credit_file(self, show, monkeypatch):
        monkeypatch.delenv("XAI_VOICE_COST_PER_MIN", raising=False)
        record = {"arm": "proposed", "fixture": "roddy",
                  "run_id": "9b2d4e6f-aaaa-bbbb-cccc-dddddddddddd",
                  "measured_at": "2026-11-02T10:00:00Z", "planned_minutes": 15,
                  "room_log": {"length_min": 15.3}}
        path = costs.write_rehearsal_credit_file(show, record)
        assert path.name == "credit_usage_2026-11-02_rehearsal_9b2d4e6f.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["kind"] == "rehearsal" and data["published"] is False
        agent = data["services"]["voice_agent"]
        assert agent["sessions"] == 2
        assert agent["minutes"] == pytest.approx(30.6)
        assert data["total_estimated_cost_usd"] == pytest.approx(30.6 * 0.05)
        gd = _load("gd_voices_pass2", "scripts/generate_dashboard.py")
        assert gd._credit_file_kind(path, "age_of_ai") == "rehearsal"
        src = (ROOT / "pipelines/voices/rehearsal.py").read_text(encoding="utf-8")
        body = src[src.index("def measure_and_write("):src.index("def run_one(")]
        assert "write_credit_file(run, record)" in body


# ---------------------------------------------------------------------------
# 3. the rollup: the two kinds, the two buckets, episodes only when published
# ---------------------------------------------------------------------------

class TestRollupReadsTheRooms:

    def _write(self, ddir: Path, name: str, payload: dict) -> None:
        ddir.mkdir(parents=True, exist_ok=True)
        (ddir / name).write_text(json.dumps(payload), encoding="utf-8")

    def _tree(self, tmp_path, published: bool):
        today = dt.date.today().isoformat()
        ddir = tmp_path / "digests" / "age_of_ai"
        self._write(ddir, f"credit_usage_{today}_room_0f3c9a1e.json", {
            "date": today, "kind": "room", "published": published,
            "services": {"grok_api": {"total_cost_usd": 0.12},
                         "tts_api": {"estimated_cost_usd": 0.0},
                         "search_api": {"estimated_cost_usd": 0.015},
                         "voice_agent": {"minutes": 44.0, "sessions": 1, "estimated_cost_usd": 2.2}},
            "total_estimated_cost_usd": 2.335,
        })
        self._write(ddir, f"credit_usage_{today}_rehearsal_9b2d4e6f.json", {
            "date": today, "kind": "rehearsal", "published": False,
            "services": {"grok_api": {"total_cost_usd": 0.0},
                         "tts_api": {"estimated_cost_usd": 0.0},
                         "voice_agent": {"minutes": 30.6, "sessions": 2, "estimated_cost_usd": 1.53}},
            "total_estimated_cost_usd": 1.53,
        })
        return tmp_path

    def test_buckets_and_the_published_rule(self, tmp_path):
        gd = _load("gd_voices_pass3", "scripts/generate_dashboard.py")
        assert "voice_agent" in gd._COST_KEYS and "rehearsal" in gd._COST_KEYS
        assert set(gd._new_cost_bucket()) >= {"voice_agent", "rehearsal"}
        shows = [{"slug": "age_of_ai", "name": "The Age of AI"}]
        out = gd.aggregate_costs(self._tree(tmp_path, published=False), shows)
        net = out["network_last_7_days"]
        assert net["voice_agent"] == pytest.approx(2.2)
        assert net["rehearsal"] == pytest.approx(1.53)
        assert net["grok"] == pytest.approx(0.12)
        assert net["search"] == pytest.approx(0.015)
        assert net["total"] == pytest.approx(2.335 + 1.53)
        assert net["files"] == 2
        assert net["episodes"] == 0              # unpublished room, fixture room
        out = gd.aggregate_costs(self._tree(tmp_path, published=True), shows)
        assert out["network_last_7_days"]["episodes"] == 1
        assert out["per_show"]["age_of_ai"]["last_7_days"]["episodes"] == 1
        # A fixture room never reads as show cost.
        assert out["per_show"]["age_of_ai"]["last_7_days"]["voice_agent"] == pytest.approx(2.2)
        note = out["projections"]["note"]
        assert "Voice Agent" in note and "rehearsal" in note

    def test_the_card_reads_the_two_lines_and_has_the_rooms_card(self):
        src = (ROOT / "management.html").read_text(encoding="utf-8")
        assert "n7.voice_agent" in src and "n7.rehearsal" in src
        assert 'sectionCard("Mira\'s rooms"' in src
        assert src.count("// Mira's rooms (Nov 3 2026)") == 1       # one card, never two
        card = src[src.index("// Mira's rooms (Nov 3 2026)"):src.index("// Pipeline health")]
        assert "fmtOrDash(sv.answered)" in card
        assert "fmtOrDash(last.pacing)" in card
        assert "fmtOrDash(month.booked)" in card and "fmtOrDash(month.published)" in card
        assert "moneyOrDash(cost.median_usd)" in card
        assert "data.voices" in card


# ---------------------------------------------------------------------------
# 4. the nightly builder: null, never 0, and exit 0
# ---------------------------------------------------------------------------

class TestVoicesMetricsBuilder:

    def _unreachable(self, table, query):
        raise ConnectionError("supabase unreachable")

    def test_unreachable_supabase_writes_null_for_every_table_and_exits_0(self, tmp_path, monkeypatch):
        bm = _load("build_voices_metrics_pass", "scripts/build_voices_metrics.py")
        monkeypatch.setattr(bm, "ROOT", tmp_path)
        (tmp_path / "shows").mkdir()
        for slug in ("age_of_ai", "nerra_voices"):
            src = ROOT / "shows" / f"{slug}.yaml"
            (tmp_path / "shows" / f"{slug}.yaml").write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        reader = bm.Reader(self._unreachable)
        data = bm.build(tmp_path, reader=reader, credentials=True,
                        now=dt.datetime(2026, 11, 3, 12, tzinfo=dt.timezone.utc))
        assert data["supabase_read"] is False
        assert set(data["unreadable"]) >= {"interviews", "editorial_packages", "episode_grades"}
        for slug, block in data["shows"].items():
            for key in ("survey", "grades", "audio", "yield", "room_to_publish_days", "rooms_published"):
                assert block[key] is None, (slug, key)
            assert block["guest_mix"] is None
            # The room credit files on disk are still read: none → measured none, not null.
            assert block["cost"] == {"rooms_costed": 0, "median_usd": None, "rooms": [], "rate_basis": "estimated"}
        monkeypatch.setenv("VOICES_SUPABASE_URL", "https://x.invalid")
        monkeypatch.setenv("VOICES_SUPABASE_SERVICE_KEY", "k")
        Original = bm.Reader
        monkeypatch.setattr(bm, "Reader", lambda select=None: Original(self._unreachable))
        assert bm.main(["--out", "api/voices_metrics.json"]) == 0
        written = json.loads((tmp_path / "api" / "voices_metrics.json").read_text(encoding="utf-8"))
        assert written["shows"]["age_of_ai"]["survey"] is None
        assert written["first_generated_at"] == written["generated_at"]

    def test_no_credentials_leaves_an_existing_file_alone(self, tmp_path, monkeypatch):
        bm = _load("build_voices_metrics_pass2", "scripts/build_voices_metrics.py")
        monkeypatch.setattr(bm, "ROOT", tmp_path)
        for name in ("VOICES_SUPABASE_URL", "VOICES_SUPABASE_SERVICE_KEY",
                     "SUPABASE_URL", "SUPABASE_SERVICE_KEY"):
            monkeypatch.delenv(name, raising=False)
        out = tmp_path / "api" / "voices_metrics.json"
        out.parent.mkdir()
        out.write_text('{"generated_at": "2026-11-01T00:00:00+00:00", "shows": {"age_of_ai": {}}}',
                       encoding="utf-8")
        assert bm.main(["--out", "api/voices_metrics.json"]) == 0
        assert json.loads(out.read_text(encoding="utf-8"))["generated_at"] == "2026-11-01T00:00:00+00:00"

    def _fake_select(self, tables):
        def select(table, query):
            if table not in tables:
                raise ConnectionError(table)
            if table == "episode_metrics":
                ids = query.split("in.(")[1].rstrip(")").split(",")
                return [r for r in tables[table] if r["interview_id"] in ids]
            return tables[table]
        return select

    def test_the_blocks_from_a_fixture_record(self, tmp_path, monkeypatch):
        bm = _load("build_voices_metrics_pass3", "scripts/build_voices_metrics.py")
        now = dt.datetime(2026, 11, 3, 12, tzinfo=dt.timezone.utc)
        ddir = tmp_path / "digests" / "age_of_ai"
        ddir.mkdir(parents=True)
        (ddir / "Age_of_AI_Ep015_20261101.md").write_text("# ep", encoding="utf-8")
        (ddir / "credit_usage_2026-10-28_room_aaaa1111.json").write_text(json.dumps({
            "date": "2026-10-28", "kind": "room", "published": False,
            "room": {"run_id": "aaaa1111-x", "interview_id": "iv-pub"},
            "services": {"voice_agent": {"minutes": 44}}, "total_estimated_cost_usd": 2.4}),
            encoding="utf-8")
        (ddir / "credit_usage_2026-10-19_room_bbbb2222.json").write_text(json.dumps({
            "date": "2026-10-19", "kind": "room", "published": False,
            "room": {"run_id": "bbbb2222-x", "interview_id": "iv-cancel"},
            "services": {}, "total_estimated_cost_usd": 1.0}), encoding="utf-8")
        tables = {
            "interviews": [
                {"id": "iv-pub", "show": "age_of_ai", "status": "published", "episode_number": 15,
                 "scheduled_at": "2026-10-28T20:00:00Z", "session_kind": "interview"},
                {"id": "iv-cancel", "show": "age_of_ai", "status": "cancelled",
                 "cancel_reason": "reschedule requested: travelling", "scheduled_at": "2026-10-19T18:00:00Z"},
                {"id": "iv-cancel2", "show": "age_of_ai", "status": "cancelled",
                 "cancel_reason": None, "scheduled_at": "2026-10-20T18:00:00Z"},
                {"id": "iv-miss", "show": "age_of_ai", "status": "missed", "scheduled_at": "2026-10-26T18:00:00Z"},
                {"id": "iv-sched", "show": "age_of_ai", "status": "scheduled", "scheduled_at": "2026-11-04T18:00:00Z"},
                {"id": "iv-reh", "show": "age_of_ai", "status": "rehearsal", "session_kind": "rehearsal",
                 "scheduled_at": "2026-10-23T18:00:00Z"},
                {"id": "iv-hello", "show": "age_of_ai", "status": "archived", "session_kind": "hello",
                 "scheduled_at": "2026-10-23T18:00:00Z"},
                {"id": "iv-nv", "show": "nerra_voices", "status": "published", "episode_number": 4,
                 "scheduled_at": "2026-10-23T18:00:00Z"},
            ],
            "editorial_packages": [
                {"interview_id": "iv-pub", "survey_rating": 5, "survey_answered_at": "2026-10-30T10:00:00Z"},
                {"interview_id": "iv-nv", "survey_rating": 3, "survey_answered_at": "2026-10-25T10:00:00Z"},
                {"interview_id": "iv-miss", "survey_rating": 2, "survey_answered_at": "2026-09-01T10:00:00Z"},
            ],
            "episode_grades": [
                {"interview_id": "iv-pub", "show": "age_of_ai", "overall": 5, "pacing": 4, "warmth": 7,
                 "created_at": "2026-10-28T22:00:00Z"},
                {"interview_id": "iv-nv", "show": "nerra_voices", "overall": 4, "pacing": 3, "warmth": 5,
                 "created_at": "2026-10-23T22:00:00Z"},
            ],
            "episode_metrics": [
                {"interview_id": "iv-pub", "overlap_events": 1, "turn_gap_ms_median": 4280,
                 "mira_turn_sec_median": 4.9, "closing_round_complete": False, "metrics_basis": "audio"},
            ],
        }
        data = bm.build(tmp_path, now=now, reader=bm.Reader(self._fake_select(tables)), credentials=True)
        aoai = data["shows"]["age_of_ai"]
        assert aoai["survey"]["answered"] == 2 and aoai["survey"]["mean"] == 3.5
        assert aoai["survey"]["answered_30d"] == 1 and aoai["survey"]["ratings_30d"] == [5]
        assert aoai["grades"] == [{"date": "2026-10-28", "interview_id": "iv-pub",
                                   "overall": 5.0, "pacing": 4.0, "warmth": 7.0}]
        assert aoai["audio"]["rooms"] == 1 and aoai["audio"]["basis_audio"] == 1
        assert aoai["audio"]["medians"]["turn_gap_ms_median"] == 4280
        assert aoai["audio"]["medians"]["closing_round_complete_share"] == 0.0
        oct = aoai["yield"]["months"]["2026-10"]
        assert oct["booked"] == 4 and oct["published"] == 1 and oct["cancelled"] == 2 and oct["missed"] == 1
        assert oct["cancelled_by_reason"] == {"reschedule requested": 1, "no reason given": 1}
        assert aoai["yield"]["months"]["2026-11"]["other"] == 1
        assert aoai["yield"]["current_month"] == "2026-11"
        assert aoai["room_to_publish_days"] == {"median": 4.0, "n": 1}
        assert aoai["guest_mix"] is None
        assert aoai["cost"]["rooms_costed"] == 2 and aoai["cost"]["median_usd"] == 2.4
        assert aoai["cost"]["rooms"][0]["published"] is True       # the builder set it
        assert aoai["rooms_published"] == 1
        assert data["unreadable"] == ["guest_applications"] or data["unreadable"] == []
        flagged = json.loads((ddir / "credit_usage_2026-10-28_room_aaaa1111.json").read_text(encoding="utf-8"))
        assert flagged["published"] is True
        unflagged = json.loads((ddir / "credit_usage_2026-10-19_room_bbbb2222.json").read_text(encoding="utf-8"))
        assert unflagged["published"] is False
        nv = data["shows"]["nerra_voices"]
        assert nv["survey"]["answered"] == 1 and nv["grades"][0]["pacing"] == 3.0

    def test_reason_labels_are_text_never_a_verdict(self):
        bm = _load("build_voices_metrics_pass4", "scripts/build_voices_metrics.py")
        assert bm.reason_label(None) == "no reason given"
        assert bm.reason_label("Reschedule requested: flight") == "reschedule requested"
        assert bm.reason_label("cancelled in Cal.com: x") == "cancelled in cal.com"
        assert bm.reason_label("  Our fault, the link was dead  ") == "our fault, the link was dead"
        src = (ROOT / "scripts/build_voices_metrics.py").read_text(encoding="utf-8")
        assert "our-side" not in src and "guest-side" not in src


# ---------------------------------------------------------------------------
# 5. the dashboard: the section and the three register metrics
# ---------------------------------------------------------------------------

class TestDashboardVoices:

    def _root(self, tmp_path, shows):
        (tmp_path / "api").mkdir()
        (tmp_path / "digests").mkdir()
        (tmp_path / "api" / "voices_metrics.json").write_text(json.dumps({
            "generated_at": "2026-11-03T06:00:00+00:00", "unreadable": [], "shows": shows}),
            encoding="utf-8")
        return tmp_path

    def test_metrics_are_null_without_the_file(self, tmp_path):
        gd = _load("gd_voices_pass4", "scripts/generate_dashboard.py")
        (tmp_path / "api").mkdir()
        (tmp_path / "digests").mkdir()
        m = gd._experiment_live_metrics(tmp_path)
        for key in ("voices_survey_mean_30d", "voices_pacing_grade_median_5", "voices_cost_per_room_usd"):
            assert key in m and m[key] is None
        assert gd.build_voices_section(tmp_path)["configured"] is False

    def test_metrics_pool_the_voices_shows(self, tmp_path):
        gd = _load("gd_voices_pass5", "scripts/generate_dashboard.py")
        root = self._root(tmp_path, {
            "age_of_ai": {"survey": {"ratings_30d": [5, 4]},
                          "grades": [{"date": "2026-10-28", "pacing": 4}, {"date": "2026-10-19", "pacing": 5},
                                     {"date": "2026-10-05", "pacing": 7}],
                          "cost": {"rooms": [{"date": "2026-10-28", "total_usd": 2.4},
                                             {"date": "2026-10-19", "total_usd": 1.0}]}},
            "nerra_voices": {"survey": {"ratings_30d": [3]},
                             "grades": [{"date": "2026-10-23", "pacing": 3}],
                             "cost": {"rooms": [{"date": "2026-10-23", "total_usd": 3.0}]}},
        })
        m = gd._experiment_live_metrics(root)
        assert m["voices_survey_mean_30d"] == 4.0
        # The four most recent pacing grades sorted [3, 4, 5, 7]; the file's
        # median convention (index n // 2, as the render medians use) is 5.
        assert m["voices_pacing_grade_median_5"] == 5.0
        assert m["voices_cost_per_room_usd"] == 2.4
        section = gd.build_voices_section(root)
        assert section["configured"] is True and set(section["shows"]) == {"age_of_ai", "nerra_voices"}
        src = (ROOT / "scripts/generate_dashboard.py").read_text(encoding="utf-8")
        assert '"voices": build_voices_section(root),' in src

    def test_the_nightly_builds_and_commits_the_file(self):
        wf = (ROOT / ".github/workflows/nightly-maintenance.yml").read_text(encoding="utf-8")
        step = wf[wf.index("Build Nerra Voices metrics"):wf.index("Build audience headline")]
        assert "python scripts/build_voices_metrics.py --out api/voices_metrics.json" in step
        assert "VOICES_SUPABASE_URL: ${{ secrets.VOICES_SUPABASE_URL }}" in step
        assert "VOICES_SUPABASE_SERVICE_KEY: ${{ secrets.VOICES_SUPABASE_SERVICE_KEY }}" in step
        assert wf.index("Build Nerra Voices metrics") < wf.index("Generate Management Dashboard")
        block = wf[wf.index("add-paths:"):wf.index("commit-message:", wf.index("add-paths:"))]
        assert "api/voices_metrics.json" in block
        # The builder sets published: true on a room's credit file; the
        # nightly must commit it or the flag never reaches main.
        assert "digests/age_of_ai/credit_usage_*.json" in block
        assert "digests/nerra_voices/credit_usage_*.json" in block


# ---------------------------------------------------------------------------
# 6. the review snapshot reads the file once it has existed a week
# ---------------------------------------------------------------------------

class TestSnapshotReadsTheFile:

    def _file(self, tmp_path, first, built):
        path = tmp_path / "voices_metrics.json"
        path.write_text(json.dumps({"generated_at": built, "first_generated_at": first,
                                    "shows": {"age_of_ai": {"grades": [], "survey": None}}}),
                        encoding="utf-8")
        return path

    def test_ready_only_after_a_week_and_only_when_fresh(self, tmp_path):
        rs = _load("review_snapshot_voices_pass", "scripts/review_snapshot.py")
        now = dt.datetime(2026, 11, 10, 12, tzinfo=dt.timezone.utc)
        young = self._file(tmp_path, "2026-11-05T06:00:00+00:00", "2026-11-10T06:00:00+00:00")
        assert rs.voices_metrics_for("age_of_ai", now=now, path=young) is None
        ready = self._file(tmp_path, "2026-11-03T06:00:00+00:00", "2026-11-10T06:00:00+00:00")
        assert rs.voices_metrics_for("age_of_ai", now=now, path=ready) == {"grades": [], "survey": None}
        stale = self._file(tmp_path, "2026-11-01T06:00:00+00:00", "2026-11-05T06:00:00+00:00")
        assert rs.voices_metrics_for("age_of_ai", now=now, path=stale) is None
        assert rs.voices_metrics_for("age_of_ai", now=now, path=tmp_path / "missing.json") is None
        src = (ROOT / "scripts/review_snapshot.py").read_text(encoding="utf-8")
        body = src[src.index("def interview_show_section("):src.index("def build_snapshot(")]
        assert "voices_metrics_for(slug)" in body and "_craft_lines_live(slug, episodes)" in body


# ---------------------------------------------------------------------------
# 7. the Voices workflows commit the credit files
# ---------------------------------------------------------------------------

class TestWorkflowsCommitTheCreditFiles:

    @pytest.mark.parametrize("name", ["nerra_voices_post_interview.yml", "nerra_voices_rehearsal.yml"])
    def test_commit_step_and_write_permission(self, name):
        text = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
        data = yaml.safe_load(text)
        assert data["permissions"]["contents"] == "write"
        steps = [s for job in data["jobs"].values() for s in job["steps"]
                 if str(s.get("uses", "")).endswith("safe-commit-push")]
        assert steps, name
        paths = steps[-1]["with"]["add-paths"]
        assert "digests/age_of_ai/credit_usage_*.json" in paths
        assert "digests/nerra_voices/credit_usage_*.json" in paths
        assert steps[-1].get("if") in ("${{ always() }}", "always()")

    def test_the_post_interview_commit_follows_the_narration_and_never_fails_the_job(self):
        """The file is extended by the narration step, so the commit comes
        after it; the gate-1 fallback stays the job's LAST step (the Oct 22
        2026 guard reads job.status as CUT_FAILED), so a lost push is
        continue-on-error — accounting never changes what Patrick is told."""
        data = yaml.safe_load((ROOT / ".github/workflows/nerra_voices_post_interview.yml")
                              .read_text(encoding="utf-8"))
        steps = data["jobs"]["process"]["steps"]
        commit = next(i for i, s in enumerate(steps)
                      if str(s.get("uses", "")).endswith("safe-commit-push"))
        narrate = next(i for i, s in enumerate(steps) if "narrate.py" in str(s.get("run", "")))
        assert narrate < commit
        assert steps[commit].get("continue-on-error") is True
        assert "--gate1-fallback" in steps[-1]["run"]
        assert commit == len(steps) - 2


# ---------------------------------------------------------------------------
# 8. the credit stop before the slate
# ---------------------------------------------------------------------------

class TestCreditStopBeforeTheSlate:

    def _fire(self):
        import fire_interviews
        return fire_interviews

    def test_the_slot_is_eastern_wall_time_on_the_hourly_catch_all(self):
        f = self._fire()
        # 03:02 ET on Nov 3 2026 (EST, UTC-5) is 08:02 UTC.
        assert f.credit_ping_due(dt.datetime(2026, 11, 3, 8, 2, tzinfo=dt.timezone.utc))
        assert f.credit_ping_due(dt.datetime(2026, 11, 3, 8, 14, tzinfo=dt.timezone.utc))
        assert not f.credit_ping_due(dt.datetime(2026, 11, 3, 8, 15, tzinfo=dt.timezone.utc))
        assert not f.credit_ping_due(dt.datetime(2026, 11, 3, 8, 32, tzinfo=dt.timezone.utc))
        assert not f.credit_ping_due(dt.datetime(2026, 11, 3, 3, 2, tzinfo=dt.timezone.utc))
        # In July (EDT, UTC-4) the same wall time is 07:02 UTC.
        assert f.credit_ping_due(dt.datetime(2026, 7, 3, 7, 2, tzinfo=dt.timezone.utc))
        assert f.FIRST_SHOW_SLOT_EASTERN == "04:00"
        # The slot is the top of the hour: the Worker dispatches the fire tick
        # unconditionally only at minute 0 (its hourly catch-all); a half-hour
        # slot is reached only while an interview is near or by GitHub's late cron.
        assert f.CREDIT_PING_SLOT == (3, 0)
        worker = (ROOT / "workers/voices/src/index.ts").read_text(encoding="utf-8")
        assert "const hourTop = minute === 0;" in worker
        assert "if (hourTop || await fireTickDue(env))" in worker

    def test_a_quota_response_posts_to_the_webhook_and_emails(self, monkeypatch):
        f = self._fire()
        import common
        monkeypatch.setenv("GROK_API_KEY", "k")
        monkeypatch.setenv("NOTIFICATION_WEBHOOK_URL", "https://hooks.example/x")
        monkeypatch.delenv("SLACK_WEBHOOK", raising=False)
        posts = []

        class R:
            status_code = 403
            text = json.dumps({"error": "Your team x has either used all available credits "
                                        "or reached its monthly spending limit."})

            def raise_for_status(self):
                return None

        def post(url, *a, **k):
            posts.append((url, k.get("json")))
            return R()
        monkeypatch.setattr(common.requests, "post", post)
        emails = []
        monkeypatch.setattr(f, "send_email", lambda to, subject, body, **k: emails.append((to, subject)))
        stop = f.check_credit_before_slate(dt.datetime(2026, 11, 3, 8, 1, tzinfo=dt.timezone.utc))
        assert "spending limit" in stop
        urls = [u for u, _ in posts]
        assert "https://api.x.ai/v1/chat/completions" in urls
        assert "https://hooks.example/x" in urls
        webhook_text = [j for u, j in posts if u == "https://hooks.example/x"][0]["text"]
        assert "console.x.ai" in webhook_text and "04:00 ET" in webhook_text
        assert emails and "out of credit" in emails[0][1]

    def test_outside_the_slot_nothing_is_pinged(self, monkeypatch):
        f = self._fire()
        monkeypatch.setenv("GROK_API_KEY", "k")
        monkeypatch.setattr(f.requests, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("pinged")))
        assert f.check_credit_before_slate(dt.datetime(2026, 11, 3, 9, 0, tzinfo=dt.timezone.utc)) == ""

    def test_main_checks_first_and_never_fails_on_it(self):
        src = (ROOT / "pipelines/voices/fire_interviews.py").read_text(encoding="utf-8")
        body = src[src.index("def main() -> int:"):]
        assert body.index("check_credit_before_slate()") < body.index("send_reminders()")
        assert "except Exception:" in body[:body.index("send_reminders()")]
        # The Worker still holds no xAI key: the ping lives here on purpose.
        worker = (ROOT / "workers/voices/src/index.ts").read_text(encoding="utf-8")
        assert "GROK_API_KEY" not in worker


# ---------------------------------------------------------------------------
# 9. the docs carry the contract
# ---------------------------------------------------------------------------

class TestDocs:
    def test_analytics_and_plan(self):
        analytics = (ROOT / "docs/analytics.md").read_text(encoding="utf-8")
        assert "`api/voices_metrics.json`" in analytics
        assert "| `voice_agent` |" in analytics and "| `rehearsal` |" in analytics
        plan = (ROOT / "docs/age_of_ai_plan.md").read_text(encoding="utf-8")
        assert "auto-reload" in plan and "check_credit_before_slate" in plan
        assert "credit_usage_<date>_room_<run id[:8]>.json" in plan
