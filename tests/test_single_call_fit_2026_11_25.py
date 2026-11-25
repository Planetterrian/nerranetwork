"""Operator pick 4a (Nov 25 2026): Omni View fits one voice call.

The script ran 14,190 to 19,524 characters on eight straight episodes
against the 14,000 one call takes, so the delivery wrap was dropped every
day. ``engine/single_call_fit.py`` removes whole items from the END of the
spoken Also Today run until the text fits, and leaves alone a script it
cannot bring under the limit.
"""

from pathlib import Path

import yaml

from engine.config import TTSConfig, load_config
from engine.single_call_fit import (
    ANCHOR_PHRASE,
    KEEP_MIN,
    also_today_items,
    find_run,
    fit_single_call,
)

ROOT = Path(__file__).resolve().parents[1]

DIGEST = """## Today's lead story (1)
### 1) Parliament passes the harbour dredging bill
**What happened:** Parliament passed the harbour dredging bill by eleven votes.

### Also Today
**Glacier lake drains in Bhutan: Kuensel**
A glacier lake above Punakha drained overnight and engineers lowered the alarm level. Source: [kuensel](https://example.org/a)

**Tram drivers in Lisbon end their strike: Publico**
Lisbon tram drivers ended a nine-day strike after the operator raised night pay. Source: [publico](https://example.org/b)

**Peru reopens the Machu Picchu rail line: El Comercio**
Peru reopened the Machu Picchu rail line after landslide repairs finished early. Source: [elcomercio](https://example.org/c)

**Kenya's tea auction sets a record: Nation**
Kenya's Mombasa tea auction set a record price for a third week. Source: [nation](https://example.org/d)

**Finland opens an undersea data cable: Yle**
Finland opened an undersea data cable to Estonia built by Cinia. Source: [yle](https://example.org/e)

**Mongolia vaccinates herds against plague: Montsame**
Mongolia began vaccinating livestock herds against plague in Khovd province. Source: [montsame](https://example.org/f)

## Understanding the Issue: How a dredging licence works
A dredging licence is issued by the port authority.
"""

RUN = [
    "In brief, a glacier lake above Punakha in Bhutan drained overnight.",
    "Lisbon tram drivers ended their nine-day strike over night pay.",
    "Peru reopened the Machu Picchu rail line after landslide repairs.",
    "Kenya's Mombasa tea auction set a record price again.",
    "Finland opened an undersea data cable to Estonia, built by Cinia.",
    "Mongolia began vaccinating livestock herds against plague in Khovd.",
]

HEAD = ("Parliament passed the harbour dredging bill by eleven votes.\n\n"
        "The vote followed a year of hearings on silt and shipping lanes.\n\n")
TAIL = ("\n\nTo really understand a dredging licence, start with who issues it. "
        "The port authority does.\n\nThat's the show.")


def _script(per_line=2):
    lines = [" ".join(RUN[i:i + per_line]) for i in range(0, len(RUN), per_line)]
    return HEAD + "\n\n".join(lines) + TAIL


class TestTheRunIsFound:
    def test_digest_items_are_read(self):
        assert len(also_today_items(DIGEST)) == 6

    def test_the_run_is_the_sentences_before_the_deep_dive(self):
        s = _script()
        run = [s[a:b] for a, b in find_run(s, DIGEST)]
        assert run == RUN

    def test_a_story_sentence_is_never_in_the_run(self):
        s = _script()
        run = " ".join(s[a:b] for a, b in find_run(s, DIGEST))
        assert "dredging" not in run and "hearings" not in run

    def test_no_anchor_means_no_run(self):
        assert find_run(_script().replace("To really understand", "To see"), DIGEST) == []

    def test_a_digest_without_the_section_means_no_run(self):
        assert find_run(_script(), DIGEST.split("### Also Today")[0]) == []


class TestOnlyTheEndOfTheRunIsCut:
    def test_a_script_that_fits_is_byte_identical(self):
        s = _script()
        r = fit_single_call(s, DIGEST, len(s))
        assert r.outcome == "fits" and r.script is s

    def test_the_last_item_goes_first_and_only_as_many_as_needed(self):
        s = _script()
        r = fit_single_call(s, DIGEST, len(s) - 10)
        assert r.outcome == "trimmed" and r.removed == 1
        assert r.removed_sentences == [RUN[-1]]
        assert RUN[-1] not in r.script
        for kept in RUN[:-1]:
            assert kept in r.script

    def test_everything_outside_the_run_survives_whole(self):
        s = _script()
        r = fit_single_call(s, DIGEST, len(s) - 100)
        assert r.outcome == "trimmed"
        assert r.script.startswith(HEAD)
        assert r.script.endswith(TAIL)
        assert ANCHOR_PHRASE in r.script.lower()
        assert "\n\n\n" not in r.script and "  " not in r.script

    def test_a_removed_sentence_is_removed_whole(self):
        s = _script(per_line=3)
        r = fit_single_call(s, DIGEST, len(s) - 10)
        left = r.script[len(HEAD):-len(TAIL)]
        sentences = [x.strip() + "." for x in left.replace("\n", " ").split(".") if x.strip()]
        assert sentences == RUN[:-1]

    def test_the_run_never_drops_under_its_floor(self):
        s = _script()
        r = fit_single_call(s, DIGEST, len(s) - 120)
        assert r.outcome == "trimmed" and r.removed == 2
        assert len(find_run(r.script, DIGEST)) == KEEP_MIN

    def test_a_script_it_cannot_fit_is_left_exactly_as_it_was(self):
        s = _script()
        r = fit_single_call(s, DIGEST, 50)
        assert r.outcome == "cannot" and r.script is s and r.removed == 0

    def test_a_run_at_the_floor_is_not_touched(self):
        short = HEAD + " ".join(RUN[:KEEP_MIN]) + TAIL
        r = fit_single_call(short, DIGEST, len(short) - 5)
        assert r.outcome == "no_run" and r.script is short

    def test_the_measure_decides_the_fit(self):
        s = _script()
        r = fit_single_call(s, DIGEST, len(s) * 2 - 10, measure=lambda t: len(t) * 2)
        assert r.outcome == "trimmed" and r.chars_after <= len(s) * 2 - 10


class TestTheWiring:
    def test_off_by_default_and_on_for_omni_view_only(self):
        assert TTSConfig().fit_single_call is False
        on = sorted(
            p.stem for p in (ROOT / "shows").glob("*.yaml")
            if not p.stem.startswith("_")
            and ((yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("tts") or {})
            .get("fit_single_call")
        )
        assert on == ["omni_view"]
        assert load_config(ROOT / "shows/omni_view.yaml").tts.fit_single_call is True

    def test_the_fit_runs_before_the_tts_text_is_saved(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        i = src.index("from engine.single_call_fit import fit_single_call")
        assert i < src.index("from engine.story_tags import tag_story_boundaries")
        assert i < src.index('tts_script_path.write_text(')
        block = src[i - 600:i + 1600]
        assert "config.tts.dialogue_mode" in block
        assert "prepare_text_for_tts" in block and "GROK_MAX_CHARS_PER_REQUEST" in block
        assert 'metrics.record("single_call_fit"' in block

    def test_the_stated_ceiling_is_recorded(self):
        cfg = load_config(ROOT / "shows/omni_view.yaml")
        assert cfg.llm.max_podcast_words == 1900
        assert cfg.llm.min_podcast_words < 1900
        prompt = (ROOT / "shows/prompts/omni_view_podcast.txt").read_text(encoding="utf-8")
        assert "CEILING of about 1,900 spoken words" in prompt

    def test_the_run_is_ranked_so_the_end_is_the_least_consequential(self):
        digest = (ROOT / "shows/prompts/omni_view_digest.txt").read_text(encoding="utf-8")
        assert "ALSO TODAY IS RANKED" in digest
        podcast = (ROOT / "shows/prompts/omni_view_podcast.txt").read_text(encoding="utf-8")
        assert "spoken in the briefing's own order" in podcast


class TestReplayOnWhatShipped:
    """Committed episodes roll off; the replay reads whatever is there."""

    def test_a_trimmed_episode_fits_and_loses_only_also_today_sentences(self):
        from engine.tts import prepare_text_for_tts

        d = ROOT / "digests/omni_view"
        seen = 0
        for tts in sorted(d.glob("Omni_View_Ep*_tts.txt")):
            md = tts.with_name(tts.name.replace("_tts.txt", ".md"))
            if not md.exists():
                continue
            script = tts.read_text(encoding="utf-8")
            digest = md.read_text(encoding="utf-8")
            r = fit_single_call(script, digest, 13987,
                                measure=lambda t: len(prepare_text_for_tts(t)))
            if r.outcome != "trimmed":
                assert r.script is script
                continue
            seen += 1
            assert r.chars_after <= 13987
            items = also_today_items(digest)
            for sent in r.removed_sentences:
                words = {w.lower().strip(".,;:’'\"") for w in sent.split()}
                assert any(len(words & it) >= 2 for it in items), sent
                assert ANCHOR_PHRASE not in sent.lower()
            assert len(find_run(r.script, digest)) >= KEEP_MIN
        assert seen >= 0
