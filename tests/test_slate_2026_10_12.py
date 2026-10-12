"""Oct 12 2026 slate review — the first full slate after the four review
PRs and the grok-4.6 script-stage moves. Guards for what it found.

Every case below is a defect that shipped on 2026-10-12, replayed from the
committed files where they exist.
"""
from __future__ import annotations

import datetime as dt
import glob
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


# --------------------------------------------------------- stop tokens --
class TestModelSpecialTokens:
    def test_strip_removes_eos_and_keeps_prose(self):
        from engine.utils import strip_model_special_tokens
        assert strip_model_special_tokens(
            "That's Modern Investing Techniques for today.<|eos|>"
        ) == "That's Modern Investing Techniques for today."
        assert strip_model_special_tokens("PATRICK: We'll read it.<|endoftext|>") == \
            "PATRICK: We'll read it."
        prose = "Use a pipe | between fields and <b>bold</b> in markup."
        assert strip_model_special_tokens(prose) == prose

    def test_both_clients_strip_before_returning(self):
        gen = (ROOT / "engine" / "generator.py").read_text(encoding="utf-8")
        assert "strip_model_special_tokens(text)" in gen
        grok = (ROOT / "digests" / "xai_grok.py").read_text(encoding="utf-8")
        assert grok.count("_strip_special_tokens(") >= 3  # def + both return paths

    def test_mit_ep198_closing_is_spoken_once(self):
        """The model wrote the closing's first sentence and stopped; the
        guard appended the whole block, so the sentence aired twice."""
        from engine.pipeline import closing_block_present, trim_partial_closing
        tts = (ROOT / "digests" / "modern_investing"
               / "Modern_Investing_Ep198_20261012_tts.txt").read_text(encoding="utf-8")
        cut = tts.index("That's Modern Investing Techniques for today.<|eos|>")
        script = tts[:cut] + "That's Modern Investing Techniques for today."
        closing = ("Patrick: That's Modern Investing Techniques for today. If you found "
                   "this useful, share it with a fellow investor.")
        assert not closing_block_present(script, closing)
        trimmed = trim_partial_closing(script, closing)
        assert not trimmed.rstrip().endswith("for today.")
        assert trimmed.rstrip().endswith("still lacks.")

    def test_a_real_last_line_is_never_trimmed(self):
        from engine.pipeline import trim_partial_closing
        script = "Story one.\n\nThat is the market today, and it closed higher."
        closing = "Patrick: That's the show for today. Thanks for listening."
        assert trim_partial_closing(script, closing) == script


# ------------------------------------------------------ translation hang --
class TestTranslationTimeout:
    def test_translate_bounds_the_call_and_disables_sdk_retries(self, monkeypatch):
        import digests.xai_grok as xg
        from engine import translate
        seen = {}

        def fake(**kw):
            seen.update(kw)
            return "bonjour", {}
        monkeypatch.setattr(xg, "grok_generate_text", fake)
        monkeypatch.delenv("NERRA_TRANSLATION_TIMEOUT_SECONDS", raising=False)
        assert translate._generate.__wrapped__("p", "grok-4.6", 100) == "bonjour"
        assert seen["timeout_seconds"] == 600.0 and seen["max_retries"] == 0

    def test_timeout_env_override(self, monkeypatch):
        from engine import translate
        monkeypatch.setenv("NERRA_TRANSLATION_TIMEOUT_SECONDS", "420")
        assert translate._translation_timeout_seconds() == 420.0
        monkeypatch.setenv("NERRA_TRANSLATION_TIMEOUT_SECONDS", "nope")
        assert translate._translation_timeout_seconds() == 600.0

    def test_client_receives_max_retries_only_when_given(self):
        from digests.xai_grok import _client_retry_kwargs
        assert _client_retry_kwargs(None) == {}
        assert _client_retry_kwargs(0) == {"max_retries": 0}


# ------------------------------------------------- Russian closing on PR --
class TestPrivetClosesInRussian:
    def test_every_closing_is_cyrillic(self):
        from engine.intros import _SHOW_PERSONALITIES
        for c in _SHOW_PERSONALITIES["privet_russian"]["closings"]:
            letters = [ch for ch in c if ch.isalpha()]
            cyr = sum(1 for ch in letters if "Ѐ" <= ch <= "ӿ")
            assert cyr / len(letters) > 0.95, c

    def test_closing_block_cta_and_ask_are_russian(self):
        from engine.intros import build_closing_block, platform_ask_for
        block = build_closing_block("privet_russian", episode_num=74, today_str="",
                                    date=dt.date(2026, 10, 19),
                                    youtube_channel_handle="@NerraRU")
        assert "YouTube, канал NerraRU" in block
        assert "rather watch" not in block
        for d in range(14):
            ask = platform_ask_for("privet_russian", dt.date(2026, 10, 1) + dt.timedelta(d),
                                   is_ru=True)
            if ask:
                assert re.search("[А-Яа-я]", ask)

    def test_lesson_stays_english_taught(self):
        from engine.intros import _RUSSIAN_SPOKEN_SHOWS
        assert "privet_russian" not in _RUSSIAN_SPOKEN_SHOWS

    def test_each_closing_parses_as_the_closing_chapter(self):
        from engine.chapters import parse_chapters
        from engine.config import load_config
        from engine.intros import _SHOW_PERSONALITIES
        ch = load_config(ROOT / "shows" / "privet_russian.yaml").chapters
        tts = (ROOT / "digests" / "privet_russian" / "PR_Ep073_20261012_tts.txt").read_text(
            encoding="utf-8")
        body = tts[:tts.index("You did great today")]
        for closing in _SHOW_PERSONALITIES["privet_russian"]["closings"]:
            chapters = parse_chapters(body + closing, list(ch.section_markers),
                                      show_name="privet_russian")
            assert chapters[-1].title == "Closing", (closing, [c.title for c in chapters])

    def test_closing_marker_does_not_match_inside_words(self):
        import yaml
        cfg = yaml.safe_load((ROOT / "shows" / "privet_russian.yaml").read_text(encoding="utf-8"))
        pat = next(m["pattern"] for m in cfg["chapters"]["section_markers"]
                   if m["title"] == "Closing")
        assert not re.search(pat, "Покажите на карте вокзал.", re.IGNORECASE)


# ------------------------------------------------- spoken source tags --
class TestBracketedSourceTag:
    def test_fp_ep087_line(self):
        import run_show
        out = run_show._strip_source_scaffold_lines(
            "Он также снижает лишнюю ответственность. Source: [kalkine.ca]")
        assert out.strip() == "Он также снижает лишнюю ответственность."
        out = run_show._strip_source_scaffold_lines(
            "The rate held. Source: [Reuters](https://reuters.com/x).")
        assert "Source" not in out and "The rate held." in out

    def test_shipped_scripts_carry_no_bracket_source(self):
        bad = [p for p in glob.glob(str(ROOT / "digests" / "*" / "*_2026101[3-9]_tts.txt"))
               if re.search(r"(?:Source|Источник)\s*:?\s*\[", Path(p).read_text(encoding="utf-8"))]
        assert not bad, bad


# ------------------------------------------------------ cadence words --
def _weekly_show_names():
    import yaml
    from engine.cadence import cadence_adjective, schedule_for_slug
    names = set()
    for p in glob.glob(str(ROOT / "shows" / "*.yaml")):
        slug = Path(p).stem
        if slug.startswith("_"):
            continue
        sched = schedule_for_slug(slug)
        if sched and cadence_adjective(sched) != "daily":
            name = (yaml.safe_load(Path(p).read_text(encoding="utf-8")) or {}).get("name")
            if name:
                names.add(name)
    return names


class TestCadenceWords:
    def test_no_cross_promo_calls_a_weekly_show_daily(self):
        names = _weekly_show_names() | {"Environmental Intelligence"}
        bad = []
        for p in glob.glob(str(ROOT / "shows" / "prompts" / "*.txt")):
            for line in Path(p).read_text(encoding="utf-8").splitlines():
                m = re.search(r'→\s*"([^"]+)"', line)
                if m and re.search(r"\bdaily\b", m.group(1)) and \
                        any(n.split(":")[0] in m.group(1) for n in names):
                    bad.append((Path(p).name, m.group(1)))
        assert not bad, bad

    def test_weekly_show_promo_never_says_daily_family(self):
        from engine.network_promo import build_network_promo
        for d in range(28):
            day = dt.date(2026, 10, 1) + dt.timedelta(d)
            promo = build_network_promo("dp_pod", day) or ""
            assert "family of daily podcasts" not in promo

    def test_daily_show_frame_one_is_unchanged(self):
        from engine.network_promo import build_network_promo
        seen = [build_network_promo("tesla", dt.date(2026, 10, 1) + dt.timedelta(d)) or ""
                for d in range(8)]
        assert any("family of daily podcasts" in p for p in seen)


# --------------------------------------------------------- chapters --
class TestLeadChapterTitles:
    def test_desk_lead_headlines_are_read(self):
        from engine.grok_imagine import extract_story_headlines
        md = (ROOT / "digests" / "omni_view_asia_pacific"
              / "Omni_View_Asia_Pacific_Ep020_20261012.md").read_text(encoding="utf-8")
        heads = extract_story_headlines(md, max_count=12)
        assert any(h.startswith("16 people drowned to death in Bihar") for h in heads)

    def test_hook_is_never_clipped_into_a_title(self):
        from engine.chapters import parse_chapters
        from engine.config import load_config
        from engine.grok_imagine import extract_story_headlines
        for show in ("omni_view_asia_pacific", "omni_view_latam", "omni_view_world"):
            cfg = load_config(ROOT / "shows" / f"{show}.yaml")
            md = next(p for p in glob.glob(str(ROOT / "digests" / show / "*_20261012.md")))
            tts = md.replace(".md", "_tts.txt")
            d = Path(md).read_text(encoding="utf-8")
            hook = re.search(r"(?m)^>\s*\*\*(.+?)\*\*", d).group(1)
            titles = [c.title for c in parse_chapters(
                Path(tts).read_text(encoding="utf-8"), cfg.chapters.section_markers,
                show_name=cfg.name, story_headlines=extract_story_headlines(d, 12),
                digest_text=d)]
            for t in titles:
                assert not (hook.startswith(t) and len(t) < len(hook)), (show, t)

    def test_env_intel_science_is_not_a_topic_word(self):
        from engine.chapters import parse_chapters
        from engine.config import load_config
        cfg = load_config(ROOT / "shows" / "env_intel.yaml")
        tts = (ROOT / "digests" / "env_intel" / "Env_Intel_Ep072_20261012_tts.txt").read_text(
            encoding="utf-8")
        d = (ROOT / "digests" / "env_intel" / "Env_Intel_Ep072_20261012.md").read_text(
            encoding="utf-8")
        titles = [c.title for c in parse_chapters(tts, cfg.chapters.section_markers,
                                                  show_name=cfg.name, digest_text=d)]
        assert "Science & Technical" not in titles

    def test_mag7_calendar_anchor_is_required(self):
        text = (ROOT / "shows" / "prompts" / "mag7_podcast.txt").read_text(encoding="utf-8")
        assert 'contains the words "on the calendar"' in text


# --------------------------------------------- shared-URL dedupe --
class TestSharedRoundupUrl:
    U = "https://www.thenationalnews.com/podcasts/trending-middle-east/2026/10/12/x/"

    def _digest(self):
        return f"""# Desk

### Lead
**Airport attacked again in Riyadh: The National**
One person was killed and 11 injured in another attack on Riyadh's King Khalid International Airport, a day after a Houthi-claimed strike killed 13. Source: [x]({self.U})

### Also Today
**Migrants dead off Djibouti: The National**
At least 139 migrants are dead after a boat capsized off the coast of Djibouti, the International Organization for Migration said, with dozens still missing. Source: [x]({self.U})

**Riyadh airport closed after second strike: The National**
King Khalid International Airport in Riyadh will remain closed for 24 hours after another attack killed one person and injured 11, a day after the Houthi strike. Source: [x]({self.U})
"""

    def test_different_stories_on_one_url_both_stay(self):
        from engine.digest_overlap import dedupe_cross_section_items
        r = dedupe_cross_section_items(self._digest())
        assert "Djibouti" in r.text
        assert [d.title for d in r.removed] == ["Riyadh airport closed after second strike"]


# ---------------------------------------------- self-narration --
class TestSelfNarration:
    @pytest.mark.parametrize("s", [
        "The published note gives the job figure, the president's name, and the sequence after the ban.",
        "That is the paper’s characterization, not a finding from an electoral authority.",
        "What the report establishes on the page is a damages order.",
        "On the progress file, the Jamaica Observer reports that residents are due to gain.",
        "The Observer heads the item as a big deal.",
        "It does not publish a score in the material here.",
        "Progress Watch: the day had none.",
    ])
    def test_aired_lines_match(self, s):
        from engine.absence_sentences import is_self_narration_sentence
        assert is_self_narration_sentence(s)

    @pytest.mark.parametrize("s", [
        "The arithmetic looked favorable on the page.",
        "Lebanon's needs were not addressed in that text.",
        "A persuasive request can override the written note.",
        "Defects in the material limit the yield.",
    ])
    def test_prose_does_not(self, s):
        from engine.absence_sentences import is_self_narration_sentence
        assert not is_self_narration_sentence(s)


# --------------------------------------------------- prompts --
class TestPromptShapes:
    def test_vancouver_both_sides_is_optional(self):
        from engine.validation import vancouver_validation_config
        rule = next(r for r in vancouver_validation_config().sections if r.name == "Both Sides")
        assert rule.optional
        for f in ("vancouver_digest.txt", "vancouver_podcast.txt",
                  "collingwood_digest.txt", "collingwood_podcast.txt"):
            assert "fact both" not in (ROOT / "shows" / "prompts" / f).read_text(encoding="utf-8")

    @pytest.mark.parametrize("name", ["unintended_consequences_podcast.txt",
                                      "first_principles_podcast.txt"])
    def test_narrative_one_telling_rule(self, name):
        text = (ROOT / "shows" / "prompts" / name).read_text(encoding="utf-8")
        assert "ONE TELLING PER FACT" in text

    def test_teaser_and_outlet_rules_in_shared_snippet(self):
        text = (ROOT / "shows" / "prompts" / "_shared" / "content_discipline.txt").read_text(
            encoding="utf-8")
        assert "never carries a fact held back from a story already told" in text
        assert "never its web address" in text


# ------------------------------------------------- Offshore North --
class TestRhumWithdrawal:
    def test_a_race_the_boat_is_not_in_is_never_the_next_milestone(self):
        from engine.offshore_north_status import campaign_status_from_files
        out = campaign_status_from_files(now=dt.datetime(2026, 10, 19, 9, tzinfo=dt.timezone.utc))
        assert "Next milestone on record: Route du Rhum" not in out
        assert "will not start" in out
