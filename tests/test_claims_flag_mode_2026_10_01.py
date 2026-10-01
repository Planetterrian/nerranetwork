"""Drift guards for ``on_failure: flag`` (Oct 1 2026, operator-directed).

The strip/block policy was costing timely news: strip removed TRUE
sentences (SpaceX Ep104's five, MIT Ep187's NASDAQ close, Prediction
Markets' hurricane contract on 10-01) and UC skipped 11 of its last 28
days on its own gate — the model's training data lags the 24-hour cycle,
so "cannot verify against memory" must never drop a sourced, timely story.
Flag mode PUBLISHES with every claim's status visible and VERIFIES AGAIN
afterwards (``scripts/reverify_claims.py``, nightly).

What binds here: flag mode removes nothing but reviewer notes; every
ledger entry carries a closed-vocabulary status; the sidecar keeps every
entry (verified and not) and stays backward compatible; strip and block
still work exactly as before; the YAML defaults are flag; the nightly
re-verification flips an unreachable claim to ``verified_later`` and never
touches a verified one; the workflow whitelist carries the sidecar glob;
the dashboard section is null-honest.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import claims as cl  # noqa: E402
from engine.config import SourceIntegrityConfig, load_config  # noqa: E402
from scripts import generate_dashboard as gd  # noqa: E402
from scripts import reverify_claims as rv  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture: one verified, one unreachable (403), one 404, one uncovered shape,
# one reviewer note.
# ---------------------------------------------------------------------------

DIGEST = (
    "**HOOK:** Four stories today.\n"
    "### Top News\n"
    "1. **Starship pad split**\n"
    "   Starbase will split its final-assembly hall into two lines by December. "
    "The second line adds forty percent capacity, the company said.\n"
    "   Source: https://good.example/pad\n"
    "2. **Raptor test**\n"
    "   Raptor 3 passed three hundred seconds at McGregor on the new stand.\n"
    "   Source: https://blocked.example/raptor\n"
    "3. **Booster**\n"
    "   Booster B1085 flew its twentieth mission from Vandenberg (no public source found for the mission count; keep it general).\n"
    "   Source: https://good.example/booster\n"
    "4. **Gazette**\n"
    "   According to a memo from the agency, the Boca Chica permit was renewed for 2027. "
    "The town council meets again in November.\n"
)
CLAIMS = [
    {"id": "c1", "claim": "Second assembly line adds forty percent capacity",
     "source_url": "https://good.example/pad",
     "supporting_quote": "second line adds forty percent capacity",
     "episode_span": "The second line adds forty percent capacity, the company said."},
    {"id": "c2", "claim": "Raptor 3 passed 300 seconds at McGregor",
     "source_url": "https://blocked.example/raptor",
     "supporting_quote": "passed three hundred seconds",
     "episode_span": "Raptor 3 passed three hundred seconds at McGregor on the new stand."},
    {"id": "c3", "claim": "B1085 twentieth mission",
     "source_url": "https://dead.example/booster",
     "supporting_quote": "Booster B1085 flew its twentieth mission",
     "episode_span": "Booster B1085 flew its twentieth mission from Vandenberg"},
]


def _fetch(url):
    if "blocked.example" in url:
        return 403, ""
    if "dead.example" in url:
        return 404, ""
    if "good.example/pad" in url:
        return 200, "<p>The second line adds forty percent capacity, the company said.</p>"
    if "good.example/booster" in url:
        return 200, "<p>Booster B1085 flew its twentieth mission from Vandenberg</p>"
    return 200, "<p>unrelated page</p>"


def _fetch_raising(url):
    if "blocked.example" in url:
        raise ConnectionError("connection reset")
    return _fetch(url)


# ---------------------------------------------------------------------------
# 1. Flag mode removes nothing, labels everything
# ---------------------------------------------------------------------------

class TestFlagMode:
    def _gate(self, fetch=_fetch):
        gate = cl.run_source_integrity_gate(DIGEST, CLAIMS, fetch=fetch)
        assert not gate.passed
        assert {v["id"] for v in gate.failed_verifications} == {"c2", "c3"}
        assert gate.uncovered_shapes and gate.reviewer_notes
        return gate

    def test_nothing_removed_but_the_reviewer_note(self):
        gate = self._gate()
        res = cl.flag_unverified(DIGEST, gate, CLAIMS, fetch=_fetch)
        # every sentence is still there — including the two unverified ones
        for keep in ("Raptor 3 passed three hundred seconds", "Booster B1085 flew its twentieth mission",
                     "According to a memo from the agency", "town council meets again",
                     "forty percent capacity", "**HOOK:** Four stories today."):
            assert keep in res.text, keep
        # the reviewer note is the one thing gone, its sentence stays
        assert "no public source found" not in res.text
        assert res.removed_notes and len(res.removed_notes) == 1
        assert res.gate.stripped_notes == res.removed_notes
        assert "twentieth mission from Vandenberg." in res.text

    def test_every_entry_present_with_the_right_status(self):
        gate = self._gate()
        res = cl.flag_unverified(DIGEST, gate, CLAIMS, fetch=_fetch)
        by_id = {e["id"]: e for e in res.claims}
        assert by_id["c1"]["status"] == cl.CLAIM_STATUS_VERIFIED
        assert by_id["c2"]["status"] == cl.CLAIM_STATUS_UNREACHABLE
        assert by_id["c3"]["status"] == cl.CLAIM_STATUS_NOT_FOUND
        uncovered = [e for e in res.claims if e["status"] == cl.CLAIM_STATUS_UNCOVERED]
        assert len(uncovered) == 1
        assert uncovered[0]["claim"].startswith("According to a memo from the agency")
        assert uncovered[0]["source_url"] == "" and uncovered[0]["supporting_quote"] == ""
        # the original keys every existing reader uses are untouched
        for k in ("claim", "source_url", "supporting_quote", "episode_span"):
            assert by_id["c2"][k] == CLAIMS[1][k]
        assert by_id["c2"]["status_reason"] == "HTTP 403"

    def test_flagged_sentences_and_counts(self):
        gate = self._gate()
        res = cl.flag_unverified(DIGEST, gate, CLAIMS, fetch=_fetch)
        assert res.flagged_sentences == [
            CLAIMS[1]["episode_span"], CLAIMS[2]["episode_span"],
            "According to a memo from the agency, the Boca Chica permit was renewed for 2027.",
        ]
        assert res.gate.flagged_sentences == res.flagged_sentences
        assert res.gate.flagged_count == 3 and res.gate.verified_count == 1
        assert res.gate.mode == "flag" and res.gate.ledger is res.claims
        # the mechanical verdict is honest: the gate did fail
        assert not res.gate.passed

    def test_transport_failure_is_unreachable(self):
        gate = self._gate(fetch=_fetch_raising)
        res = cl.flag_unverified(DIGEST, gate, CLAIMS, fetch=_fetch_raising)
        by_id = {e["id"]: e for e in res.claims}
        assert by_id["c2"]["status"] == cl.CLAIM_STATUS_UNREACHABLE
        assert by_id["c2"]["status_reason"].startswith("fetch failed")

    def test_quote_mismatch_and_malformed_and_fetched_copy(self):
        text = ("### Top News\n1. **A**\n   The plant added a third shift in August. "
                "Output doubles by winter. The press rose by four percent.\n"
                "   Source: https://good.example/a\n")
        claims = [
            {"id": "c1", "claim": "third shift in August", "source_url": "https://good.example/a",
             "supporting_quote": "a sentence the page does not carry",
             "episode_span": "The plant added a third shift in August."},
            {"id": "c2", "claim": "Output doubles by winter", "source_url": "https://good.example/a"},
            {"id": "c3", "claim": "press rose four percent", "source_url": "https://x.com/acme/status/1",
             "supporting_quote": "The press rose by four percent",
             "episode_span": "The press rose by four percent."},
        ]
        local = {cl.normalize_source_url("https://x.com/acme/status/1"): "The press rose by four percent today"}

        def fetch(url):
            if "good.example/a" in url:
                return 200, "<p>The plant added a third shift in August.</p>"
            raise ConnectionError("x.com never answers requests")

        gate = cl.run_source_integrity_gate(text, claims, fetch=fetch, local_texts=local)
        res = cl.flag_unverified(text, gate, claims, fetch=fetch)
        by_id = {e["id"]: e for e in res.claims}
        assert by_id["c1"]["status"] == cl.CLAIM_STATUS_QUOTE_MISMATCH
        assert by_id["c2"]["status"] == cl.CLAIM_STATUS_MALFORMED
        assert by_id["c3"]["status"] == cl.CLAIM_STATUS_VERIFIED_FROM_FETCHED
        # the malformed entry had no anchor: its sentence is found by content
        assert "Output doubles by winter." in res.flagged_sentences
        assert "third shift" in res.text and "doubles by winter" in res.text

    def test_uncovered_shape_covered_by_item_source_is_not_flagged(self):
        text = ("### Top News\n1. **Memo**\n   According to a memo from the agency, the plant closed in 2019.\n"
                "   Source: https://good.example/pad\n")
        gate = cl.run_source_integrity_gate(text, [], fetch=_fetch)
        assert gate.uncovered_shapes
        res = cl.flag_unverified(text, gate, [], fetch=_fetch)
        assert res.covered_by_item_source == 1 and res.flagged_sentences == []
        assert res.claims == [] and res.gate.flagged_count == 0

    def test_passing_gate_still_labels_every_entry(self):
        text = "### Top News\n1. **A**\n   The second line adds forty percent capacity, the company said.\n"
        gate = cl.run_source_integrity_gate(text, CLAIMS[:1], fetch=_fetch)
        assert gate.passed
        res = cl.flag_unverified(text, gate, CLAIMS[:1], fetch=_fetch)
        assert res.text == text and res.claims[0]["status"] == "verified"
        assert res.gate.passed and res.gate.verified_count == 1 and res.gate.flagged_count == 0

    def test_strip_mode_on_the_same_fixture_still_removes(self):
        """Regression: strip's contract is untouched."""
        gate = self._gate()
        res = cl.strip_unverified(DIGEST, gate, CLAIMS, fetch=_fetch)
        assert "Raptor 3 passed" not in res.text
        assert "twentieth mission" not in res.text
        assert "memo from the agency" not in res.text and "town council" in res.text
        assert [c["id"] for c in res.claims] == ["c1"]
        assert res.gate.passed and res.gate.ledger is None


# ---------------------------------------------------------------------------
# 2. The sidecar keeps every entry, backward compatibly
# ---------------------------------------------------------------------------

class TestSidecar:
    def test_flag_sidecar_keeps_every_entry_and_is_version_2(self, tmp_path):
        gate = cl.run_source_integrity_gate(DIGEST, CLAIMS, fetch=_fetch)
        res = cl.flag_unverified(DIGEST, gate, CLAIMS, fetch=_fetch)
        digest = tmp_path / "Show_Ep001_20261001.md"
        digest.write_text(res.text, encoding="utf-8")
        path = cl.save_ledger(digest, res.gate)
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["version"] == 1
        g = payload["gate"]
        assert g["policy_version"] == 2 and g["mode"] == "flag"
        assert g["flagged_count"] == 3 and g["verified_count"] == 1
        assert isinstance(g["flagged_sentences"], list) and len(g["flagged_sentences"]) == 3
        assert all(isinstance(s, str) for s in g["flagged_sentences"])
        # legacy keys every reader uses are still there
        for k in ("claims_total", "claims_verified", "stripped_sentences", "failed_verifications"):
            assert k in g
        assert g["claims_total"] == 3 and g["claims_verified"] == 1
        statuses = sorted(e["status"] for e in payload["claims"])
        assert statuses == sorted([cl.CLAIM_STATUS_VERIFIED, cl.CLAIM_STATUS_UNREACHABLE,
                                   cl.CLAIM_STATUS_NOT_FOUND, cl.CLAIM_STATUS_UNCOVERED])
        # readers of verified claims never see an unverified one
        assert [c["id"] for c in cl.load_ledger(digest)] == ["c1"]
        assert len(cl.load_ledger(digest, verified_only=False)) == 4

    def test_strip_sidecar_shape_unchanged(self, tmp_path):
        gate = cl.run_source_integrity_gate(DIGEST, CLAIMS, fetch=_fetch)
        res = cl.strip_unverified(DIGEST, gate, CLAIMS, fetch=_fetch)
        digest = tmp_path / "Show_Ep002_20261001.md"
        digest.write_text(res.text, encoding="utf-8")
        payload = json.loads(cl.save_ledger(digest, res.gate).read_text(encoding="utf-8"))
        assert [c["id"] for c in payload["claims"]] == ["c1"]
        assert "status" not in payload["claims"][0]
        assert payload["gate"]["policy_version"] == 2 and payload["gate"]["flagged_count"] == 0
        assert payload["gate"]["verified_count"] == payload["gate"]["claims_verified"]


# ---------------------------------------------------------------------------
# 3. YAML defaults and the config vocabulary
# ---------------------------------------------------------------------------

class TestDefaults:
    def test_network_default_is_flag(self):
        defaults = yaml.safe_load((ROOT / "shows/_defaults.yaml").read_text(encoding="utf-8"))
        assert defaults["source_integrity"] == {"enabled": True, "enforce": True, "on_failure": "flag"}

    @pytest.mark.parametrize("slug", ["unintended_consequences", "first_principles", "tesla", "spacex"])
    def test_shows_resolve_to_flag(self, slug):
        si = load_config(ROOT / "shows" / f"{slug}.yaml").source_integrity
        assert si.enabled and si.enforce and si.on_failure == "flag", slug

    def test_narrative_yaml_comment_is_dated(self):
        for slug in ("unintended_consequences", "first_principles"):
            src = (ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8")
            assert "2026-10-01" in src and "11 of its" in src, slug

    def test_config_accepts_flag_and_rejects_unknown(self):
        assert SourceIntegrityConfig(on_failure="flag").on_failure == "flag"
        assert SourceIntegrityConfig(on_failure="Strip").on_failure == "strip"
        assert SourceIntegrityConfig().on_failure == "block"
        with pytest.raises(ValueError):
            SourceIntegrityConfig(on_failure="warn")

    def test_run_show_wires_flag_mode(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "_si_mod.flag_unverified(" in src
        assert 'metrics.record("source_integrity_flagged_sentences"' in src
        assert 'metrics.record("source_integrity_flagged_claims"' in src
        assert 'metrics.record("source_integrity_mode"' in src
        assert "if not _si_gate.passed and not _si_flagged:" in src
        assert "::warning::Source-integrity flag for" in src
        # strip and block paths are untouched
        assert 'and _si_on_failure == "strip"' in src
        assert '"source_integrity_failed",' in src
        # the script-stage lint never aborts a flag-mode episode
        assert '_si_on_failure != "flag"' in src


# ---------------------------------------------------------------------------
# 4. Nightly re-verification
# ---------------------------------------------------------------------------

def _flag_sidecar(tmp_path: Path, name: str = "Show_Ep010_20261001") -> Path:
    gate = cl.run_source_integrity_gate(DIGEST, CLAIMS, fetch=_fetch)
    res = cl.flag_unverified(DIGEST, gate, CLAIMS, fetch=_fetch)
    digest = tmp_path / f"{name}.md"
    digest.write_text(res.text, encoding="utf-8")
    return cl.save_ledger(digest, res.gate)


class TestReverify:
    def _fetch_now_answers(self, url):
        # the 403 host answers now; the 404 is still a 404
        if "blocked.example" in url:
            return 200, "<p>Raptor 3 passed three hundred seconds at McGregor.</p>"
        return _fetch(url)

    def test_unreachable_flips_to_verified_later_404_stays(self, tmp_path):
        path = _flag_sidecar(tmp_path)
        before = json.loads(path.read_text(encoding="utf-8"))
        new, stats = cl.reverify_ledger_payload(before, fetch=self._fetch_now_answers, today="2026-10-02")
        by_id = {e["id"]: e for e in new["claims"]}
        assert by_id["c2"]["status"] == cl.CLAIM_STATUS_VERIFIED_LATER
        assert by_id["c2"]["first_status"] == cl.CLAIM_STATUS_UNREACHABLE
        assert by_id["c2"]["verified_at"] == "2026-10-02"
        assert by_id["c3"]["status"] == cl.CLAIM_STATUS_NOT_FOUND
        assert by_id["c3"]["last_reverify_reason"] == "HTTP 404"
        assert by_id["c1"]["status"] == cl.CLAIM_STATUS_VERIFIED and "first_status" not in by_id["c1"]
        assert [e for e in new["claims"] if e["status"] == cl.CLAIM_STATUS_UNCOVERED]
        assert stats == {"candidates": 2, "verified_later": 1, "still_unverified": 1, "changed": True}
        g = new["gate"]
        assert g["verified_count"] == 2 and g["flagged_count"] == 2 and g["verified_later_count"] == 1
        assert CLAIMS[1]["episode_span"] not in g["flagged_sentences"]
        assert CLAIMS[2]["episode_span"] in g["flagged_sentences"]
        # publish-time record untouched; input not mutated
        assert g["claims_verified"] == 1 and before["claims"][1]["status"] == cl.CLAIM_STATUS_UNREACHABLE

    def test_never_downgrades_and_is_idempotent(self, tmp_path):
        path = _flag_sidecar(tmp_path)
        payload = json.loads(path.read_text(encoding="utf-8"))

        def everything_dies(url):
            raise ConnectionError("down")

        once, s1 = cl.reverify_ledger_payload(payload, fetch=everything_dies, today="2026-10-02")
        assert {e["id"]: e["status"] for e in once["claims"]}["c1"] == cl.CLAIM_STATUS_VERIFIED
        assert s1["verified_later"] == 0
        # a verified_later claim is never re-checked or downgraded either
        good, _ = cl.reverify_ledger_payload(payload, fetch=self._fetch_now_answers, today="2026-10-02")
        again, s2 = cl.reverify_ledger_payload(good, fetch=everything_dies, today="2026-10-03")
        assert {e["id"]: e["status"] for e in again["claims"]}["c2"] == cl.CLAIM_STATUS_VERIFIED_LATER
        assert again["claims"][1]["first_status"] == cl.CLAIM_STATUS_UNREACHABLE
        assert s2["candidates"] == 1  # only the 404 is still re-checkable

    def test_script_dry_run_then_apply(self, tmp_path):
        import datetime as _dt
        show_dir = tmp_path / "digests" / "showx"
        show_dir.mkdir(parents=True)
        path = _flag_sidecar(show_dir)
        old = show_dir / "Show_Ep001_20260801_claims.json"
        old.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        today = _dt.date(2026, 10, 2)
        dry = rv.run(tmp_path, 7, apply=False, fetch=self._fetch_now_answers, today=today)
        assert dry["totals"]["files_in_window"] == 1  # the August sidecar is outside the window
        assert dry["totals"]["verified_later"] == 1 and dry["totals"]["written"] == 0
        assert json.loads(path.read_text(encoding="utf-8"))["claims"][1]["status"] == cl.CLAIM_STATUS_UNREACHABLE
        applied = rv.run(tmp_path, 7, apply=True, fetch=self._fetch_now_answers, today=today)
        assert applied["totals"]["written"] == 1
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["claims"][1]["status"] == cl.CLAIM_STATUS_VERIFIED_LATER
        assert payload["gate"]["reverified_at"] == "2026-10-02"
        # idempotent: a second apply changes nothing
        again = rv.run(tmp_path, 7, apply=True, fetch=self._fetch_now_answers, today=today)
        assert again["totals"]["written"] == 0 or payload == json.loads(path.read_text(encoding="utf-8"))

    def test_bad_sidecar_never_raises(self, tmp_path):
        show_dir = tmp_path / "digests" / "showx"
        show_dir.mkdir(parents=True)
        (show_dir / "Show_Ep003_20261001_claims.json").write_text("{not json", encoding="utf-8")
        import datetime as _dt
        rep = rv.run(tmp_path, 7, apply=True, fetch=_fetch, today=_dt.date(2026, 10, 2))
        assert rep["totals"]["errors"] == 1 and rep["totals"]["written"] == 0

    def test_paced_fetch_waits_between_same_host_calls(self):
        sleeps: list = []
        clock = {"t": 100.0}
        calls: list = []

        def fetch(url):
            calls.append(url)
            return 200, "ok"

        paced = rv.make_paced_fetch(fetch, pacing_seconds=1.0,
                                    sleep=lambda s: sleeps.append(s), clock=lambda: clock["t"])
        paced("https://a.example/1")
        paced("https://a.example/2")       # same host, no time passed → waits
        paced("https://b.example/1")       # other host → no wait
        paced("https://a.example/1")       # cached → no fetch, no wait
        assert len(calls) == 3 and sleeps == [1.0]

    def test_workflow_runs_it_and_whitelists_the_sidecars(self):
        src = (ROOT / ".github/workflows/nightly-maintenance.yml").read_text(encoding="utf-8")
        assert "python scripts/reverify_claims.py --apply --days 7" in src
        block = src[src.index("add-paths: |"):]
        assert "digests/**/*_claims.json" in block.split("\n\n")[0]
        # it runs after the audience fetches and before the commit
        assert src.index("fetch_apple_ratings.py") < src.index("reverify_claims.py") < src.index("add-paths: |")


# ---------------------------------------------------------------------------
# 5. Dashboard section
# ---------------------------------------------------------------------------

class TestDashboardSection:
    def test_unconfigured_without_any_sidecar(self, tmp_path):
        assert gd.build_claims_section(tmp_path) == {"configured": False}

    def test_shape_with_fixture(self, tmp_path):
        import datetime as _dt
        today = _dt.date(2026, 10, 2)
        d1 = tmp_path / "digests" / "showa"
        d2 = tmp_path / "digests" / "showb"
        d1.mkdir(parents=True)
        d2.mkdir(parents=True)
        # a flag-mode sidecar in the 7d window, with one verified_later
        p = _flag_sidecar(d1, "A_Ep010_20261001")
        payload = json.loads(p.read_text(encoding="utf-8"))
        payload["claims"][1]["status"] = cl.CLAIM_STATUS_VERIFIED_LATER
        payload["claims"][1]["first_status"] = cl.CLAIM_STATUS_UNREACHABLE
        p.write_text(json.dumps(payload), encoding="utf-8")
        # a legacy strip-mode sidecar 20 days old (30d window only)
        gate = cl.run_source_integrity_gate(DIGEST, CLAIMS, fetch=_fetch)
        res = cl.strip_unverified(DIGEST, gate, CLAIMS, fetch=_fetch)
        digest = d2 / "B_Ep005_20260912.md"
        digest.write_text(res.text, encoding="utf-8")
        cl.save_ledger(digest, res.gate)
        # a sidecar outside both windows
        far = d2 / "B_Ep001_20260701_claims.json"
        far.write_text(json.dumps(payload), encoding="utf-8")

        sec = gd.build_claims_section(tmp_path, today=today)
        assert sec["configured"] is True and "error" not in sec
        w7, w30 = sec["window_7d"], sec["window_30d"]
        assert w7["sidecars"] == 1 and w30["sidecars"] == 2
        # flag sidecar: 4 entries (3 claims + 1 uncovered), 2 verified after the later flip
        assert w7["claims_total"] == 4 and w7["verified"] == 2 and w7["verified_share"] == 0.5
        assert w7["flagged"] == 2 and w7["verified_later"] == 1
        assert w7["flagged_by_reason"] == {"unreachable": 0, "not_found": 1, "quote_mismatch": 0,
                                           "uncovered": 1, "malformed": 0}
        assert w7["by_mode"] == {"flag": 1}
        # legacy strip sidecar: reasons from pre_strip, 1 verified of 3 (+1 uncovered)
        b = w30["per_show"]["showb"]
        assert b["claims_total"] == 4 and b["verified"] == 1
        assert b["flagged_by_reason"]["unreachable"] == 1 and b["flagged_by_reason"]["not_found"] == 1
        assert b["flagged_by_reason"]["uncovered"] == 1
        assert w30["by_mode"] == {"flag": 1, "strip": 1}
        assert set(w30["per_show"]) == {"showa", "showb"}

    def test_null_never_zero_in_an_empty_window(self, tmp_path):
        import datetime as _dt
        d = tmp_path / "digests" / "showa"
        d.mkdir(parents=True)
        _flag_sidecar(d, "A_Ep010_20260910")
        sec = gd.build_claims_section(tmp_path, today=_dt.date(2026, 10, 2))
        w7 = sec["window_7d"]
        assert w7["sidecars"] == 0 and w7["claims_total"] is None and w7["verified_share"] is None
        assert w7["flagged_by_reason"]["unreachable"] is None and w7["per_show"] == {}
        assert sec["window_30d"]["sidecars"] == 1

    def test_wired_into_the_dashboard_and_the_page(self):
        src = (ROOT / "scripts" / "generate_dashboard.py").read_text(encoding="utf-8")
        assert '"claims": build_claims_section(root)' in src
        html = (ROOT / "management.html").read_text(encoding="utf-8")
        assert "data.claims" in html and 'sectionCard("Claim ledger"' in html
        assert "fmtOrDash(w7.claims_total)" in html
        doc = (ROOT / "docs" / "analytics.md").read_text(encoding="utf-8")
        assert "reverify_claims.py" in doc and "verified_later" in doc
