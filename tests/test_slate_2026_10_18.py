"""Oct 18 2026 slate: what stopped the shows.

1. One UC sentence ("Lark et al.,") failed the book-release corpus guard,
   which ran in every show's smoke step, so every show after UC died.
2. Fascinating Frontiers died on xAI's "model is currently at capacity"
   arriving as an error event INSIDE the stream — the bare ``APIError``,
   which no retry set names.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

openai = pytest.importorskip("openai")

from engine import generator as G  # noqa: E402


def _smoke_command() -> str:
    wf = (ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8")
    step = wf[wf.index("- name: Run smoke tests"):]
    step = step[:step.index("- name:", 10)]
    return step[step.index("python -m pytest"):]


def _committed_corpus_globs(module: Path) -> list[str]:
    """Test functions in ``module`` that glob committed show output.

    The shape that stopped the slate: a test reading a path under the
    repo's ``digests/`` (never ``tmp_path``) through ``.glob(`` — so the
    next commit any show makes is part of the test's input."""
    src = module.read_text(encoding="utf-8")
    defs = list(re.finditer(r"^[ ]*def (test_\w+)\(", src, re.M))
    found = []
    for i, m in enumerate(defs):
        end = defs[i + 1].start() if i + 1 < len(defs) else len(src)
        for line in src[m.start():end].splitlines():
            if ".glob(" in line and '"digests' in line and "tmp_path" not in line:
                found.append(m.group(1))
                break
    return found


# Modules that read every show's (or another show's) committed output by
# construction. They run in Run Tests on push, never in a per-show smoke
# step, where one bad commit from any show stops every later show.
CORPUS_MODULES = (
    "test_book_release_pass.py",   # every book-bound digest (Oct 18 UC "Lark et al.,")
    "test_episode_validity.py",    # every show's latest digest
    "test_rss.py",                 # every committed feed
    "test_dp_pod_show.py",         # DP Pod's committed digests + hook memory
)


class TestSmokeStep:
    def test_no_corpus_scan_of_other_shows_in_the_smoke_step(self):
        command = _smoke_command()
        for module in CORPUS_MODULES:
            assert f"tests/{module}" not in command, module

    def test_no_listed_module_globs_committed_digests_undeselected(self):
        command = _smoke_command()
        modules = sorted(set(re.findall(r"tests/(test_\w+\.py)(?!::)", command)))
        assert modules, "could not parse the smoke step's module list"
        deselected = set(re.findall(r"--deselect tests/(\S+)", command))
        offenders = []
        for name in modules:
            for test in _committed_corpus_globs(ROOT / "tests" / name):
                if not any(d.startswith(f"{name}::") and d.endswith(f"::{test}")
                           for d in deselected):
                    offenders.append(f"{name}::{test}")
        assert not offenders, (
            "these smoke-step tests read committed show output; deselect them "
            f"or drop the module from the smoke step: {offenders}")

    def test_known_corpus_readers_are_deselected(self):
        command = _smoke_command()
        for node in (
            "tests/test_chapters.py::TestChapterTitlesNeverCarryLinks::"
            "test_committed_models_agents_chapters_carry_no_link_fragments",
            "tests/test_review_remediation.py::TestBlogRssRegeneration::"
            "test_collect_posts_from_tesla_digests",
        ):
            assert f"--deselect {node}" in command, node
            module, _, rest = node.partition("::")
            cls, _, test = rest.partition("::")
            src = (ROOT / module).read_text(encoding="utf-8")
            # A rename must not leave a deselect that matches nothing.
            assert f"class {cls}" in src and f"def {test}(" in src, node

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
    # Oct 19 2026: the gate's workflow_run trigger is gone (Actions minutes);
    # the show run itself wakes the gate, and that step runs on a FAILED run
    # too — past the hold, a failed run is the morning's last wake-up.
    wf = (ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8")
    step = wf[wf.index("- name: Wake the Nerra Daily gate"):]
    cond = [ln for ln in step.splitlines() if ln.strip().startswith("if:")][0]
    assert "always()" in cond
    assert "outcome == 'success'" not in cond and "skipped" not in cond
    assert "workflow_run:" not in (ROOT / ".github" / "workflows" / "nerra-daily.yml").read_text(encoding="utf-8")


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
        # Oct 24 2026: a stated maximum loss IS the stop (the outer bound of
        # a band) — 15 of the 18 era digests whose stop went unread had one.
        ("Stop-loss set at the 20-day moving average; maximum acceptable loss capped at 6-8%", {"pct": 8.0}),
        ("Maximum loss capped at eight percent if the stop at the fifty day moving average breaks", {"pct": 8.0}),
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


class TestCheckpointCleanup:
    def test_a_failed_checkpoint_restores_the_tree(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        body = src[src.index("def _checkpoint_publish("):src.index("def _restore_after_checkpoint(")]
        assert "start_new_session=True" in body and "os.killpg" in body
        assert "_restore_after_checkpoint(args.show)" in body
        restore = src[src.index("def _restore_after_checkpoint("):src.index("def _rss_disclosure_for(")]
        assert '"rebase", "--abort"' in restore and '"--soft", "HEAD~1"' in restore
