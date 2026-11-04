"""Env Intel: the Practitioner Deep Dive is built from a document the run read
(Nov 3 2026, six-month review, register env-intel-sourced-deep-dive-2026-11-03).

The digest prompt had asked the section for "the wisdom that comes from
experience" and supplied the line it wanted; five of the last six episodes
narrated an invented consulting career in the first person ("The mistake I
see most often is…") to a professional audience, from a host who is not an
environmental consultant and from no source. What binds now:

* the prompt builds the section from a regulation, guideline or method
  document whose FULL TEXT the run read, names it, traces every figure to it
  and ends on its Source line — no first-person experience instruction, no
  bracketed specimen;
* ``engine.host_experience`` mode ``experience`` removes a first-person
  professional-experience claim the model writes anyway, and never an
  opinion, a recommendation or the spoken disclosure; Offshore North's
  ``frames`` mode is byte-identical;
* the ``deep_dive_fetched_source`` lint is on, the Reddit feeds are gone,
  the guidance hosts are preferred, and the script stage runs grok-4.7 at
  low effort, streamed (playbook rules 1, 2, 7) while the digest stays 4.3.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
DIGEST_PROMPT = ROOT / "shows" / "prompts" / "env_intel_digest.txt"
PODCAST_PROMPT = ROOT / "shows" / "prompts" / "env_intel_podcast.txt"
SHOW_YAML = ROOT / "shows" / "env_intel.yaml"
EI = ROOT / "digests" / "env_intel"

_SEPARATOR = "━━━━━━━━━━━━━━━━━━━━"
_FIRST_PERSON = re.compile(r"\b(?:I|I've|I'd|I'm|I'll|my|me|myself)\b")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _deep_dive_section() -> str:
    text = _read(DIGEST_PROMPT)
    start = text.index("### Practitioner Deep Dive")
    end = text.index(_SEPARATOR, start)
    return text[start:end]


def _config():
    from engine.config import load_config

    return load_config(SHOW_YAML)


# ---------------------------------------------------------------------------
# The prompts
# ---------------------------------------------------------------------------

class TestThePromptAsksForNoExperience:
    def test_digest_prompt_carries_no_first_person_experience_instruction(self):
        text = _read(DIGEST_PROMPT)
        for phrase in (
            "YOUR OWN expertise",
            "mistake I see most often",
            "wisdom that comes from experience",
            "experienced practitioner notice",
            "5-year consultant",
            "Field Knowledge Transfer",
            "real-world scenario",
        ):
            assert phrase not in text, phrase

    def test_digest_prompt_carries_no_bracketed_specimen(self):
        section = _deep_dive_section()
        assert "[specific action]" not in section
        assert "[topic]" not in section
        assert "You arrive at a" not in section
        # No quoted example sentence of any kind — de-seed by shape.
        assert '("' not in section and "(Example" not in section

    def test_deep_dive_is_built_from_a_read_document_and_ends_on_its_source(self):
        section = _deep_dive_section()
        assert "FULL TEXT" in section
        assert "LEAVE THIS SECTION OUT" in section
        assert "memory" in section
        assert "first-person" in section
        lines = [ln for ln in section.strip().splitlines() if ln.strip()]
        assert lines[-1].startswith("Source:"), lines[-1]
        assert "{recent_deep_dive_topics}" in section  # the freshness memory stays

    def test_podcast_prompt_carries_no_invented_career(self):
        text = _read(PODCAST_PROMPT)
        for phrase in (
            "15+ years experience",
            "hard-won field knowledge",
            "20-year consultant",
            "experience-based insight",
            "Close with the common mistake",
            "I wish someone had told me",
            "mentoring moment",
        ):
            assert phrase not in text, phrase
        low = text.lower()
        # The lead-in variety rule the June guard pins still stands.
        assert "vary the lead-in" in low
        assert "avoid starting every deep dive" in low
        assert "never for a career" in low

    def test_the_prompts_still_render(self):
        """The placeholders are the ones run_show supplies (the fidelity
        suite renders every show; this pins the two edited prompts)."""
        from engine.generator import load_prompt

        for path in (DIGEST_PROMPT, PODCAST_PROMPT):
            text = load_prompt(str(path))
            names = set(re.findall(r"(?<!\{)\{([a-z_]+)\}(?!\})", text))
            rendered = text.format_map({n: "x" for n in names})
            assert rendered


# ---------------------------------------------------------------------------
# The filter
# ---------------------------------------------------------------------------

class TestTheFilterRemovesTheInventedExperience:
    def test_ep074_sentence_is_removed_and_the_section_keeps_its_shape(self):
        from engine.host_experience import strip_host_experience

        text = _read(EI / "Env_Intel_Ep074_20261026.md")
        assert "The mistake I see most often" in text
        out, n = strip_host_experience(text, mode="experience")
        assert n >= 1
        assert "mistake I see most often" not in out
        assert "### Practitioner Deep Dive" in out
        assert out.count("Source:") == text.count("Source:")
        # The frames mode (Offshore North) never touches it: byte-identical.
        assert strip_host_experience(text, mode="frames") == (text, 0)

    def test_the_committed_archive_loses_only_first_person_claims(self):
        """Replay over every committed Env Intel digest and script: each
        removed sentence speaks in the first person, and the known opinion,
        recommendation and disclosure shapes are never removed."""
        from engine.host_experience import is_experience_sentence

        sent = re.compile(r"(?<=[.!?])\s+(?=\S)")
        removed: list = []
        kept_first_person: list = []
        paths = sorted(EI.glob("Env_Intel_Ep0*.md")) + sorted(EI.glob("Env_Intel_Ep0*_tts.txt"))
        assert len(paths) >= 20
        for path in paths:
            for line in _read(path).split("\n"):
                if line.lstrip().startswith("#") or not line.strip():
                    continue
                for s in sent.split(line.strip()):
                    if is_experience_sentence(s):
                        removed.append(s)
                    elif _FIRST_PERSON.search(s):
                        kept_first_person.append(s)
        assert len(removed) >= 20, len(removed)
        for s in removed:
            assert _FIRST_PERSON.search(s), s
            assert "Phase I" not in s or _FIRST_PERSON.search(s.replace("Phase I", "")), s
        # The disclosure line (the Patrick line stays as is), opinions and
        # recommendations are kept.
        kept = " ".join(kept_first_person)
        assert "synthesis of my voice" in kept
        assert "What I find interesting" in kept
        assert "I'd recommend" in kept

    def test_opinions_recommendations_and_the_disclosure_survive(self):
        from engine.host_experience import strip_host_experience

        text = (
            "This episode used AI voice synthesis of my voice — editorial selection "
            "and analysis are my own.\n\n"
            "What I find interesting here is the timing.\n\n"
            "In my view, this is a further relaxation of procedural accountability.\n\n"
            "I'd recommend submitting feedback before the comment period closes.\n\n"
            "As I mentioned earlier, the watershed consultation closes Friday.\n\n"
            "Consultants running Phase I ESAs in Alberta should read Schedule I first.\n\n"
            "Practitioners, I'd cross-reference this with Species at Risk Act overlays.\n"
        )
        assert strip_host_experience(text, mode="experience") == (text, 0)

    def test_the_first_person_experience_shapes_are_removed(self):
        from engine.host_experience import strip_host_experience

        lines = [
            "In my experience advising on these files, unresolved disputes erode trust.",
            "I've seen teams rely on these records to flag historical spills.",
            "The most common mistake I still see in the field is the assumption that "
            "two samples define the plume.",
            "Here's something I wish someone had told me early in my career.",
            "There is a nuance that I wish more junior practitioners understood.",
            "What this signals is efficiency; I've used similar insights to shave "
            "timelines on EPEA approvals.",
            "This tension surfaces in nearly every major project I see crossing "
            "provincial desks right now.",
            "Clients I work with rarely budget for the second round of sampling.",
            "On my sites the first five-year review is where the plume moves.",
        ]
        for line in lines:
            text = f"The rule sets a threshold.\n\n{line}\n\nSource: [canada.ca](https://www.canada.ca/x)\n"
            out, n = strip_host_experience(text, mode="experience")
            assert n == 1, line
            assert line not in out
            assert "Source: [canada.ca](https://www.canada.ca/x)" in out
            assert "The rule sets a threshold." in out

    def test_a_source_tail_on_the_removed_line_is_kept(self):
        from engine.host_experience import strip_host_experience

        text = ("The mistake I see most often is locking the network to one flow vector. "
                "Source: [gov.bc.ca](https://www2.gov.bc.ca/x)\n")
        out, n = strip_host_experience(text, mode="experience")
        assert n == 1
        assert out.strip() == "Source: [gov.bc.ca](https://www2.gov.bc.ca/x)"

    def test_offshore_north_frames_mode_is_unchanged(self):
        from engine.host_experience import strip_host_experience

        brief = ("Dan's lens: The RORC Transatlantic pairs weather-routing decisions "
                 "with the same pressure systems Dan reads from the flight deck. "
                 "Source: [sail-world.com](https://www.sail-world.com/news/301001/)\n")
        out, n = strip_host_experience(brief)  # the default is frames
        assert n == 1
        assert out.strip() == "Source: [sail-world.com](https://www.sail-world.com/news/301001/)"
        # Dan's frames are not the experience shapes, and vice versa.
        assert strip_host_experience(brief, mode="experience") == (brief, 0)

    def test_an_unknown_mode_raises(self):
        from engine.config import _host_experience_mode
        from engine.host_experience import HOST_EXPERIENCE_MODES, strip_host_experience

        assert HOST_EXPERIENCE_MODES == ("frames", "experience")
        with pytest.raises(ValueError):
            strip_host_experience("Some text.", mode="career")
        with pytest.raises(ValueError):
            _host_experience_mode("career")
        assert _host_experience_mode(None) == "frames"
        assert _host_experience_mode("Experience") == "experience"


# ---------------------------------------------------------------------------
# The show is wired
# ---------------------------------------------------------------------------

class TestTheShowIsWired:
    def test_filter_and_mode(self):
        from engine.config import load_config

        cfg = _config()
        assert cfg.host_experience_filter is True
        assert cfg.host_experience_mode == "experience"
        on = load_config(ROOT / "shows" / "offshore_north.yaml")
        assert on.host_experience_filter is True and on.host_experience_mode == "frames"
        tesla = load_config(ROOT / "shows" / "tesla.yaml")
        assert tesla.host_experience_filter is False and tesla.host_experience_mode == "frames"

    def test_run_show_passes_the_mode_at_both_sites(self):
        src = _read(ROOT / "run_show.py")
        assert src.count('mode=getattr(config, "host_experience_mode", "frames")') == 2
        # The metric keys are the existing ones, never a new name.
        assert 'metrics.record("digest_host_experience_removed", _host_n)' in src
        assert 'metrics.record("script_host_experience_removed", _host_s)' in src

    def test_the_fetched_source_lint_is_on_and_exists(self):
        from engine.digest_lint import CONTEXT_LINTS, LINTS

        cfg = _config()
        assert "deep_dive_fetched_source" in cfg.digest_lints
        assert "deep_dive_fetched_source" in LINTS
        assert "deep_dive_fetched_source" in CONTEXT_LINTS

    def test_the_lint_knows_the_section_and_fires_on_an_unread_document(self):
        """The lint is a closed list of section names; a show that opts in
        with a section missing from it gets a lint that can never fire. The
        real heading carries a topic after the colon, which the section
        parser strips."""
        from engine.digest_lint import (
            DEEP_DIVE_FETCHED_SECTIONS, lint_deep_dive_fetched_source)

        assert "Practitioner Deep Dive" in DEEP_DIVE_FETCHED_SECTIONS
        digest = (
            "### Compliance Brief\n- one line\n\n"
            "### Practitioner Deep Dive: Tier 1 soil guidelines\n"
            "The CCME Canadian Soil Quality Guidelines set a threshold.\n"
            "Source: https://ccme.ca/en/res/guideline.pdf\n\n"
            "### Action Items\n- none\n"
        )
        read = {"url": "https://canada.ca/en/other-page", "source_name": "Canada.ca",
                "full_text": "x" * 2000}
        unread = {"url": "https://ccme.ca/en/res/guideline.pdf", "source_name": "CCME",
                  "full_text": ""}
        finding = lint_deep_dive_fetched_source(digest, {"articles": [read, unread]})
        assert finding is not None and finding.note
        assert "Practitioner Deep Dive" in finding.note
        assert finding.metrics["deep_dive_source_read"] is False
        # Built from the read page: the lint records and does not fire.
        read_doc = dict(read, url="https://ccme.ca/en/res/guideline.pdf")
        ok = lint_deep_dive_fetched_source(digest, {"articles": [read_doc]})
        assert ok is not None and not ok.note
        assert ok.metrics["deep_dive_source_read"] is True

    def test_no_reddit_feed(self):
        raw = yaml.safe_load(_read(SHOW_YAML))
        urls = [str(s.get("url", "")) for s in raw.get("sources") or []]
        assert urls and not any("reddit.com" in u for u in urls)
        assert not any("reddit.com" in s.url for s in _config().sources)

    def test_the_guidance_hosts_are_preferred(self):
        cfg = _config()
        for host in ("ccme.ca", "aer.ca", "canada.ca", "gov.bc.ca", "gazette.gc.ca"):
            assert host in cfg.preferred_domains, host
        # Inside the Sep 24 sourcing pass's cap (test_network_sourcing_pass).
        assert 4 <= len(cfg.preferred_domains) <= 8

    def test_script_arm_is_grok_47_low_effort_streamed_and_the_digest_stays_43(self):
        from engine.generator import _script_reasoning_effort
        from engine.tracking import GROK_PRICING

        cfg = _config()
        assert cfg.llm.podcast_model == "grok-4.7"
        assert cfg.llm.podcast_reasoning_effort == "low"
        assert cfg.llm.stream is True
        assert cfg.llm.model == "grok-4.3"
        assert _script_reasoning_effort(cfg, "grok-4.7") == "low"
        assert "grok-4.7" in GROK_PRICING
        # Playbook rule 4 / the Sep 21 guard: a script pin names its register entry.
        assert "env-intel-sourced-deep-dive-2026-11-03" in _read(SHOW_YAML)

    def test_the_feed_description_no_longer_promises_the_mistake(self):
        desc = _config().publishing.rss_description
        assert "most common mistake" not in desc
        assert "guidance document" in desc
        assert "daily" not in desc.lower()

    def test_the_deep_dive_chapter_falls_back_to_its_digest_section(self):
        cfg = _config()
        marker = next(m for m in cfg.chapters.section_markers
                      if m.title == "Practitioner Deep Dive")
        assert marker.digest_section == "Practitioner Deep Dive"
