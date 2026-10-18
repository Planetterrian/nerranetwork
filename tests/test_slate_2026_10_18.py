"""Oct 18 2026 slate: what stopped the shows.

1. One UC sentence ("Lark et al.,") failed the book-release corpus guard,
   which ran in every show's smoke step, so every show after UC died.
2. Fascinating Frontiers died on xAI's "model is currently at capacity"
   arriving as an error event INSIDE the stream — the bare ``APIError``,
   which no retry set names.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

openai = pytest.importorskip("openai")

from engine import generator as G  # noqa: E402


class TestSmokeStep:
    def test_no_corpus_scan_of_other_shows_in_the_smoke_step(self):
        wf = (ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8")
        step = wf[wf.index("- name: Run smoke tests"):]
        step = step[:step.index("- name:", 10)]
        command = step[step.index("python -m pytest"):]
        assert "test_book_release_pass.py" not in command

    def test_et_al_is_not_a_seam(self):
        sys.path.insert(0, str(ROOT / "tests"))
        import test_book_release_pass as T
        assert {"al", "e.g", "i.e", "inc"} <= T._ABBREVIATIONS


class _FakeStream:
    def __init__(self, exc):
        self._exc = exc

    def __iter__(self):
        raise self._exc

    def close(self):
        pass


class _FakeClient:
    def __init__(self, exc):
        self.chat = type("C", (), {})()
        self.chat.completions = type("X", (), {})()
        self.chat.completions.create = lambda **kw: _FakeStream(exc)


def _event_error(message):
    httpx = G.sdk_httpx()
    req = httpx.Request("POST", "https://api.x.ai/v1/chat/completions")
    return openai.APIError(message, req, body=None)


class TestStreamErrorEvents:
    def _read(self, exc):
        G._stream_completion(_FakeClient(exc), {"model": "m", "messages": []},
                             wall_timeout=60, model="m")

    def test_capacity_event_is_a_rate_limit(self):
        with pytest.raises(openai.RateLimitError):
            self._read(_event_error(
                "The model is currently at capacity due to high demand. "
                "Please try again in a few minutes"))

    def test_other_event_is_a_server_error(self):
        with pytest.raises(openai.InternalServerError):
            self._read(_event_error("internal error"))

    def test_capacity_is_retried_by_the_capacity_backoff(self):
        assert openai.RateLimitError in G._RATE_LIMIT_ERRORS
        assert openai.InternalServerError in G._MODEL_UNAVAILABLE_ERRORS

    def test_status_errors_pass_through_unchanged(self):
        httpx = G.sdk_httpx()
        req = httpx.Request("POST", "https://api.x.ai/v1/chat/completions")
        with pytest.raises(openai.APITimeoutError):
            self._read(openai.APITimeoutError(request=req))


def test_edition_wakes_after_a_failed_show_run():
    wf = (ROOT / ".github" / "workflows" / "nerra-daily.yml").read_text(encoding="utf-8")
    cond = [ln for ln in wf.splitlines() if ln.strip().startswith("if:") and "workflow_run" in ln][0]
    assert '"failure"' in cond and '"success"' in cond


class TestMitStopParser:
    """40 of 45 Practice Investment sections recorded no stop (Oct 18): the
    pattern wanted 'stop-loss' + a '%' sign; the digests spell the number."""

    @pytest.fixture(scope="class")
    def mi(self):
        from shows.hooks import modern_investing
        return modern_investing

    @pytest.mark.parametrize("risk, want", [
        ("Stop-loss set at eight percent below entry to limit drawdown", {"pct": 8.0}),
        ("could compress margins; stop 8% below entry", {"pct": 8.0}),
        ("stop-loss set 8 percent below entry.", {"pct": 8.0}),
        ("Stop loss at one hundred sixteen dollars representing five point three percent downside",
         {"pct": 5.3}),
        ("Stop would trigger on a close below the September low of $58.40", {"price": 58.4}),
        ("Stop-loss set at the 20-day moving average; maximum acceptable loss capped at 6-8%", None),
        ("Maximum loss capped at eight percent if the stop at the fifty day moving average breaks", None),
    ])
    def test_narrated_stops(self, mi, risk, want):
        digest = f"### Practice Investment of the Day\n- **Risk Assessment:** {risk}\n"
        assert mi._extract_stop_loss(digest) == want


def test_clusters_never_chain_through_a_member():
    from engine.story_clusters import cluster_articles
    arts = [
        {"title": "Korea EV insurers loss ratio Tesla sales triple insurance"},
        {"title": "Korea insurers Tesla loss ratio FSD Slovakia first drive"},
        {"title": "FSD Slovakia first drive approved regulators Europe"},
    ]
    groups = cluster_articles(arts, min_shared=3, min_share=0.4)
    for g in groups:
        assert not ({0, 2} <= set(g)), groups


class TestHomepageStaleness:
    """A flagship or the edition from an earlier day is never called
    'this morning's' or 'today's' (Oct 18: SpaceX failed, the edition had
    not built, and the page said both)."""

    def test_no_unconditional_today_copy(self):
        t = (ROOT / "templates" / "network_page.html.j2").read_text(encoding="utf-8")
        assert "this morning's episodes" not in t
        for phrase in ("Play today's", "Today's rundown"):
            for line in [ln for ln in t.splitlines() if phrase in ln]:
                assert "is_today" in line, line

    def test_flagship_card_describes_the_show(self):
        src = (ROOT / "generate_html.py").read_text(encoding="utf-8")
        assert '_sh.get("meta_description")' in src


class TestHookRecurrenceGate:
    """The hook gate spends a whole regeneration; it must not fire on words
    that say nothing about which story it is (M&A 2026-10-18)."""

    def _index(self):
        from engine.story_recurrence import RecurrenceIndex
        eps = [{"date": f"2026-10-0{d}", "headlines": h} for d, h in (
            (3, ["Unitree just dropped a single 6B model that does 64 real robot tasks"]),
            (6, ["SWE-Race: a coding-agent benchmark of 188 real concurrency bugs across models"]),
            (8, ["Solar Roof installs stall as Tesla Energy pivots to Megapack deliveries"]),
            (9, ["Tesla Solar Roof installs stall again while Megapack deliveries climb"]),
        )] + [{"date": "2026-09-2%d" % i, "headlines": [f"filler story number {i} about chips"]}
              for i in range(1, 6)]
        return RecurrenceIndex(eps)

    def test_generic_words_do_not_fire(self):
        hook = ("Local models just matched a frontier coding agent on five real "
                "tasks while running on a single 16 GB card.")
        assert self._index().hook_match(hook) is None

    def test_a_real_retelling_still_fires(self):
        m = self._index().hook_match(
            "Tesla Solar Roof installs stall again as Megapack deliveries take over.")
        assert m and m["times"] >= 2

    def test_run_show_uses_the_hook_gate(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "_recurrence_index.hook_match(_hr_hook)" in src


def test_milestone_never_repeats_the_episode_number():
    from engine.intros import _milestone_note
    for n in (100, 200, 300, 500):
        note = _milestone_note(n) or ""
        assert "hundred" not in note.lower() and str(n) not in note


def test_weekly_segment_phrases_register():
    src = (ROOT / "run_show.py").read_text(encoding="utf-8")
    assert '(?:over )?the (?:past|last) (?:seven days|week)' in src


def test_long_form_has_room_after_audio_first():
    import yaml
    wf = yaml.safe_load((ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8"))
    step = next(s for s in wf["jobs"]["run"]["steps"] if s.get("name") == "Run show pipeline")
    assert int(step["env"]["PIPELINE_TIMEOUT_SECONDS"]) >= 4200
