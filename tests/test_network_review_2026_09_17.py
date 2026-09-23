"""Drift guards for the Sep 17 2026 network review (first slate after the
Sep 12 simplification pass; doc docs/reviews/network_review_2026_09_17.md).

Three findings, each fixed here:

1. Combined generation had reached THREE shows in five days: the
   ``podcast_chain`` exclusion kept every flagship (Tesla, SpaceX, FF, PT,
   MIT, FPD, UC) on the two-pass path. A chained show is now eligible;
   the chain still runs on the fallback script call.
2. Strip mode removed 1-3 TRUE sentences a day on Planetterrian, every
   one an unreachable source (x.com links, paywalled journals that 403
   the runner) — while the fetch stage already held the X post's text or
   the feed body. Claims are now verified against that fetched copy
   first (``build_local_texts`` / ``verify_claim_sources(local_texts=)``).
3. The committed claims sidecar showed the POST-strip ledger ("claims=0,
   passed") and said nothing about what was removed. It now records
   the stripped sentences, notes, removed items and item-source covers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import claims as cl  # noqa: E402
from engine import generator as gen  # noqa: E402
from engine.config import load_config  # noqa: E402


class TestChainedShowsAreEligible:
    def test_every_flagship_now_qualifies(self):
        for slug in ("tesla", "spacex", "fascinating_frontiers", "planetterrian", "modern_investing"):
            cfg = load_config(str(ROOT / "shows" / f"{slug}.yaml"))
            assert cfg.llm.podcast_chain is True, slug
            assert gen.combined_generation_enabled(cfg, {"episode_num": 200}), slug

    def test_exclusions_that_remain(self):
        for slug in ("unintended_consequences", "first_principles"):  # narrative
            cfg = load_config(str(ROOT / "shows" / f"{slug}.yaml"))
            assert not gen.combined_generation_enabled(cfg, {"episode_num": 200}), slug
        for slug in ("omni_view", "models_agents_beginners", "dp_pod"):  # grok-4.6 script stage / dialogue
            cfg = load_config(str(ROOT / "shows" / f"{slug}.yaml"))
            assert not gen.combined_generation_enabled(cfg, {"episode_num": 200}), slug

    def test_bridge_asks_for_spoken_register_and_section_names(self):
        assert "not PART 1 with the markdown removed" in gen._COMBINED_BRIDGE
        assert "name each section once" in gen._COMBINED_BRIDGE


ARTICLES = [
    {"title": "Japan Hits 100K Centenarians Milestone",
     "description": "Turning 100 used to make headlines. Now, Japan has 100K centenarians. One day, dying at 100 will feel too young",
     "url": "https://x.com/davidasinclair/status/2100230524383981702?s=20",
     "source_name": "David Sinclair (X)"},
    {"title": "DNA computer performs first calculations",
     "content_text": "Researchers built the first DNA-based computer capable of performing computations on stored data.",
     "url": "https://www.nature.com/articles/s41586-026-01234-5?utm_source=feed",
     "source_name": "Nature"},
]
CLAIMS = [
    {"id": "c1", "claim": "Japan has 100,000 centenarians",
     "source_url": "https://twitter.com/davidasinclair/status/2100230524383981702",
     "supporting_quote": "Japan has 100K centenarians",
     "episode_span": "Japan now has 100,000 people aged 100 or older."},
    {"id": "c2", "claim": "first DNA-based computer",
     "source_url": "https://nature.com/articles/s41586-026-01234-5/",
     "supporting_quote": "first DNA-based computer capable of performing computations",
     "episode_span": "Researchers built the first DNA-based computer capable of performing computations."},
    {"id": "c3", "claim": "not in any fetched copy",
     "source_url": "https://www.nature.com/articles/s41586-026-01234-5",
     "supporting_quote": "a sentence the feed body never carried",
     "episode_span": "The chip ran at ten petaflops."},
]


def _fetch_403(url):
    return 403, ""


class TestFetchedCopyVerification:
    def test_normalize_source_url(self):
        n = cl.normalize_source_url
        assert n("https://twitter.com/a/status/1?s=20") == n("https://x.com/a/status/1")
        assert n("https://www.nature.com/articles/x/?utm_source=feed&utm_medium=rss") == "nature.com/articles/x"
        assert n("http://Example.COM/path?ref=abc&page=2") == "example.com/path?page=2"
        assert n("") == ""

    def test_build_local_texts_keys_by_normalized_url(self):
        local = cl.build_local_texts(ARTICLES)
        assert "x.com/davidasinclair/status/2100230524383981702" in local
        assert "nature.com/articles/s41586-026-01234-5" in local
        assert "100K centenarians" in local["x.com/davidasinclair/status/2100230524383981702"]

    def test_quote_in_fetched_copy_passes_without_http(self):
        calls = []

        def fetch(url):
            calls.append(url)
            return 403, ""
        local = cl.build_local_texts(ARTICLES)
        res = cl.verify_claim_sources(CLAIMS, fetch=fetch, local_texts=local)
        by = {r["id"]: r for r in res}
        assert by["c1"]["passed"] and by["c1"]["via"] == "fetched_copy"
        assert by["c2"]["passed"] and by["c2"]["via"] == "fetched_copy"
        # c3's quote is not in the copy -> HTTP as before -> unreachable failure
        assert not by["c3"]["passed"] and by["c3"]["unreachable"] and by["c3"]["via"] == "http"
        assert calls == [CLAIMS[2]["source_url"]]

    def test_gate_counts_fetched_copy_verifications_and_strip_records_what_left(self):
        text = ("**HOOK:** Three findings.\n### Top News\n1. **Centenarians**\n"
                "   Japan now has 100,000 people aged 100 or older. The milestone was reported this week.\n"
                "2. **DNA**\n   Researchers built the first DNA-based computer capable of performing computations. "
                "The chip ran at ten petaflops.\n")
        local = cl.build_local_texts(ARTICLES)
        gate = cl.run_source_integrity_gate(text, CLAIMS, fetch=_fetch_403, local_texts=local)
        assert gate.verified_from_fetched == 2 and gate.claims_verified == 2
        assert [v["id"] for v in gate.failed_verifications] == ["c3"] and not gate.passed
        res = cl.strip_unverified(text, gate, CLAIMS, fetch=_fetch_403, local_texts=local)
        assert res.gate.passed and "ten petaflops" not in res.text
        assert "100,000 people" in res.text and "DNA-based computer" in res.text
        # the sidecar now carries the strip record
        rep = res.gate.to_report()
        assert rep["stripped_sentences"] == ["The chip ran at ten petaflops."]
        assert rep["verified_from_fetched"] == 2 and rep["removed_items"] == 0
        payload = json.loads(json.dumps({"gate": rep}))
        assert payload["gate"]["stripped_sentences"]

    def test_without_local_texts_behaviour_is_unchanged(self):
        res = cl.verify_claim_sources(CLAIMS[:1], fetch=_fetch_403)
        assert not res[0]["passed"] and res[0]["unreachable"] and res[0]["via"] == "http"

    def test_run_show_passes_the_fetched_copy_everywhere(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "_si_mod.build_local_texts(" in src
        assert src.count("local_texts=_si_local_texts") == 4  # gate, repair, item coverage, strip
        assert 'metrics.record("source_integrity_verified_from_fetched"' in src
