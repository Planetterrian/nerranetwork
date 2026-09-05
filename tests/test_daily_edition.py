"""Drift guards for Nerra Daily (the combined daily edition).

Pins: the EN edition's lineup/registration shape, promo-cut detection
against REAL committed transcripts (the tail-outro trim must keep working
as shows evolve), the splice ffmpeg command contracts, exact chapter
math, and the title rule (engine.titles owns every limit — landmine in
CLAUDE.md's first section).
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest
import yaml

from engine.daily_edition import (
    EDITIONS,
    MIRA_AI_DISCLOSURE,
    SEGMENT_ENCODE_ARGS,
    Segment,
    build_chapters,
    daily_title,
    discover_segments,
    edition,
    expected_slugs,
    fallback_links,
    find_promo_cut,
    hook_from_title,
    mira_piece_cmd,
    parse_links_json,
    sanitize_spoken,
    segment_trim_cmd,
    strip_op3,
)

ROOT = Path(__file__).resolve().parent.parent
SPEC = edition("en")


# ---------------------------------------------------------------------------
# Edition spec + registration surfaces
# ---------------------------------------------------------------------------

class TestEditionSpec:
    def test_en_edition_registered(self):
        assert "en" in EDITIONS

    def test_lineup_is_every_english_run_show_show(self):
        # Operator decision 2026-08-21: EVERY English show, MAB included.
        # A new English show scaffolded into the network must be added to
        # the lineup (or explicitly excluded here with a comment).
        assert set(SPEC.lineup) == {
            "tesla", "models_agents", "spacex", "modern_investing",
            "omni_view", "fascinating_frontiers", "planetterrian",
            "unintended_consequences", "first_principles",
            "models_agents_beginners", "env_intel", "offshore_north",
            "dp_pod",
        }

    def test_lineup_operator_order(self):
        # Operator-set rundown (2026-08-21, after hearing Ep1): SpaceX ->
        # Tesla -> FF -> M&A -> Planetterrian -> Omni View lead; the
        # good-news show stays the deliberate warm close.
        assert SPEC.lineup[:6] == (
            "spacex", "tesla", "fascinating_frontiers", "models_agents",
            "planetterrian", "omni_view",
        )
        assert SPEC.lineup[-1] == "dp_pod"

    def test_no_russian_shows(self):
        assert not {"finansy_prosto", "privet_russian"} & set(SPEC.lineup)

    def test_age_of_ai_never_spliced(self):
        # Operator decision: Mira PLUGS a new interview; the edition never
        # splices the (40+ min) interview audio in.
        assert "age_of_ai" not in SPEC.lineup

    def test_monday_only_subset_of_lineup(self):
        assert SPEC.monday_only <= set(SPEC.lineup)
        assert SPEC.monday_only == {"env_intel", "offshore_north"}

    def test_lineup_shows_have_configs(self):
        for slug in SPEC.lineup:
            assert (ROOT / "shows" / f"{slug}.yaml").exists(), slug

    def test_publish_floor(self):
        assert SPEC.min_segments >= 4

    def test_expected_slugs_weekday_shape(self):
        monday = dt.date(2026, 8, 17)
        thursday = dt.date(2026, 8, 20)
        assert set(expected_slugs(SPEC, monday)) == set(SPEC.lineup)
        assert set(expected_slugs(SPEC, thursday)) == set(SPEC.lineup) - SPEC.monday_only


class TestRegistration:
    def test_network_meta_entry(self):
        meta = yaml.safe_load((ROOT / "shows" / "network_meta.yaml").read_text())
        entry = meta.get("nerra_daily")
        assert entry, "nerra_daily missing from shows/network_meta.yaml"
        assert entry["rss_file"] == SPEC.feed_file
        assert entry["json_path"] == f"{SPEC.digest_dir}/summaries_{SPEC.slug}.json"
        assert entry["show_page"] == SPEC.show_page
        assert entry["json_format"] == "wrapped"
        assert entry["related_show"] == "age_of_ai"

    def test_cover_art_exists(self):
        for name in ("nerra-daily.jpg", "nerra-daily.webp",
                     "nerra-daily-800.webp", "nerra-daily-400.webp"):
            assert (ROOT / "assets" / "covers" / name).exists(), name

    def test_prompt_file_placeholders(self):
        text = (ROOT / SPEC.prompt_file).read_text(encoding="utf-8")
        for ph in ("{date_spoken}", "{segment_count}", "{handoff_count}",
                   "{lineup_block}", "{aoai_block}", "{recent_openers}"):
            assert ph in text, ph
        # De-seed by shape: the prompt must never supply a quotable example
        # sentence for Mira to copy (the three-generations-of-tics lesson).
        assert "for example, say" not in text.lower()

    def test_workflow_exists_and_gated(self):
        wf = (ROOT / ".github" / "workflows" / "nerra-daily.yml").read_text()
        assert "build_daily_edition.py" in wf
        assert "--when-ready" in wf
        assert "workflow_run" in wf          # assembles right after the last show
        assert "group: nerra-daily" in wf    # sweeps never race each other
        assert "safe-commit-push" in wf
        assert "ref: main" in wf             # never the event's stale SHA
        # Fast gate: post-publish triggers must not pay the dep install.
        assert "fastgate" in wf
        assert wf.count("steps.fastgate.outputs.published != 'true'") >= 3

    def test_find_prompt_file(self):
        assert SPEC.daily_find
        text = (ROOT / SPEC.find_prompt_file).read_text(encoding="utf-8")
        for ph in ("{date_spoken}", "{lineup_titles}", "{recent_field_notes}"):
            assert ph in text, ph
        assert "SKIP" in text  # the honest no-item escape hatch

    def test_disclosure_still_spoken(self):
        # The trim removes every per-segment AI disclosure; the edition's
        # own disclosure must therefore never be dropped or hedged away.
        assert "AI" in MIRA_AI_DISCLOSURE
        assert "voice" in MIRA_AI_DISCLOSURE


# ---------------------------------------------------------------------------
# Promo-cut detection — real committed transcripts
# ---------------------------------------------------------------------------

REAL_TRANSCRIPTS = [
    # (path, expected window for the cut on the raw voice track)
    ("digests/tesla_shorts_time/Tesla_Shorts_Time_Pod_Ep578_20260820_transcript.json",
     (485.0, 495.0)),   # promo frame at 492.5
    ("digests/dp_pod/DP_Pod_Ep041_20260820_transcript.json",
     (375.0, 381.0)),   # dialogue show; promo at 379.8
    ("digests/models_agents_beginners/MAB_Ep140_20260820_transcript.json",
     (258.0, 263.0)),   # YouTube lead at 261.1 pulls the cut earlier
    ("digests/offshore_north/Offshore_North_Ep001_20260818_transcript.json",
     (500.0, 507.0)),   # compact promo frame at 506.1
]


class TestPromoCutRealTranscripts:
    @pytest.mark.parametrize("rel_path,window", REAL_TRANSCRIPTS)
    def test_cut_found_in_expected_window(self, rel_path, window):
        path = ROOT / rel_path
        if not path.exists():
            pytest.skip(f"transcript pruned: {rel_path}")
        hit = find_promo_cut(json.loads(path.read_text(encoding="utf-8")))
        assert hit is not None, rel_path
        assert hit["kind"] == "promo"
        lo, hi = window
        assert lo <= hit["raw_seconds"] <= hi, (rel_path, hit)

    def test_offset_is_voice_intro_delay_only(self):
        """Raw-voice-track -> final-MP3 mapping. The mixer shifts voice by
        ``voice_intro_delay`` ONLY (intro music plays UNDER the cold open,
        not before it) — adding intro_duration landed every cut 3 s late
        and leaked the plug's opening words into every edition segment
        (2026-08-21 review; Ep578: final 563.1 s = raw 533.1 s + 30 s
        outro + 0 s shift). Every current show pins delay 0.0."""
        date = dt.date(2026, 8, 20)
        segments, _ = discover_segments(SPEC, ROOT, date)
        if not segments:
            pytest.skip("2026-08-20 summaries entries pruned")
        for seg in segments:
            assert seg.music_intro_offset == 0.0, seg.slug

    def test_all_lineup_shows_cut_on_a_real_day(self):
        """Every English show's committed transcript from one full slate
        must yield a promo cut — a show whose outro shape drifts past the
        matchers ships its plug into the edition silently otherwise."""
        date = dt.date(2026, 8, 20)
        segments, _ = discover_segments(SPEC, ROOT, date)
        if len(segments) < SPEC.min_segments:
            pytest.skip("2026-08-20 summaries entries pruned")
        found = 0
        for seg in segments:
            if not seg.transcript_path:
                continue
            transcript = json.loads(seg.transcript_path.read_text(encoding="utf-8"))
            hit = find_promo_cut(transcript)
            assert hit is not None, f"no promo cut for {seg.slug}"
            found += 1
        assert found >= SPEC.min_segments


class TestPromoCutSynthetic:
    @staticmethod
    def _transcript(segments):
        return {"duration": max(s["end"] for s in segments), "segments": segments}

    @staticmethod
    def _seg(start, end, text):
        words = []
        tokens = text.split()
        step = (end - start) / max(len(tokens), 1)
        for i, tok in enumerate(tokens):
            words.append({"word": tok, "start": start + i * step,
                          "end": start + (i + 1) * step})
        return {"start": start, "end": end, "text": text, "words": words}

    def test_no_promo_returns_none(self):
        t = self._transcript([self._seg(0, 600, "just an episode about batteries " * 20)])
        assert find_promo_cut(t) is None

    def test_first_half_promo_refused(self):
        t = self._transcript([
            self._seg(10, 30, "quick tip from the network try another show"),
            self._seg(30, 600, "the actual episode content " * 30),
        ])
        assert find_promo_cut(t) is None

    def test_disclosure_only_is_mildest_trim(self):
        t = self._transcript([
            self._seg(0, 560, "content " * 50),
            self._seg(560, 570, "this episode used AI voice synthesis of my voice"),
        ])
        hit = find_promo_cut(t)
        assert hit and hit["kind"] == "disclosure"

    def test_network_mention_falls_back_to_segment_start(self):
        t = self._transcript([
            self._seg(0, 550, "content " * 50),
            self._seg(550, 565, "every Nerra Network show is free online"),
        ])
        hit = find_promo_cut(t)
        assert hit and hit["kind"] == "network_mention"
        assert hit["raw_seconds"] <= 550.0

    def test_youtube_lead_pulls_cut_earlier(self):
        t = self._transcript([
            self._seg(0, 540, "content " * 50),
            self._seg(540, 548, "and if you would rather watch than listen find us on YouTube"),
            self._seg(548, 560, "quick tip from the network try another show"),
        ])
        hit = find_promo_cut(t)
        assert hit and hit["kind"] == "promo"
        assert hit["raw_seconds"] < 542.0

    def test_whisper_brand_spellings_all_match(self):
        for brand in ("Nerra", "Nera", "Narra", "Narrow"):
            t = self._transcript([
                self._seg(0, 550, "content " * 50),
                self._seg(550, 562,
                          f"this show comes to you from the {brand} network"),
            ])
            hit = find_promo_cut(t)
            assert hit and hit["kind"] == "promo", brand

    def test_segment_level_fallback_without_word_data(self):
        seg = {"start": 550.0, "end": 562.0,
               "text": "quick tip from the network try another show"}
        t = {"duration": 562.0,
             "segments": [self._seg(0, 550, "content " * 50), seg]}
        hit = find_promo_cut(t)
        assert hit and hit["kind"] == "promo"
        assert 545.0 <= hit["raw_seconds"] <= 550.0


# ---------------------------------------------------------------------------
# ffmpeg command contracts
# ---------------------------------------------------------------------------

class TestSpliceCommands:
    def test_trim_cmd_with_cut(self):
        cmd = segment_trim_cmd(Path("in.mp3"), Path("out.mp3"), 480.0)
        joined = " ".join(cmd)
        assert "-t 480.00" in joined
        assert "afade=t=out" in joined
        for arg in SEGMENT_ENCODE_ARGS:
            assert arg in cmd

    def test_trim_cmd_without_cut_ships_whole(self):
        cmd = segment_trim_cmd(Path("in.mp3"), Path("out.mp3"), None)
        joined = " ".join(cmd)
        assert "-t " not in joined and "afade" not in joined
        for arg in SEGMENT_ENCODE_ARGS:
            assert arg in cmd

    def test_uniform_encode_across_pieces(self):
        # Stream-copy concat joins the pieces byte-level: every piece MUST
        # share sample rate / channels / codec settings.
        seg = segment_trim_cmd(Path("a"), Path("b"), 100.0)
        mira = mira_piece_cmd(Path("c"), Path("d"))
        for arg in SEGMENT_ENCODE_ARGS:
            assert arg in seg and arg in mira

    def test_mira_piece_matches_network_loudness(self):
        joined = " ".join(mira_piece_cmd(Path("c"), Path("d")))
        assert "loudnorm=I=-16:TP=-1.5:LRA=11" in joined  # the -16 LUFS spec
        assert "adelay" in joined and "apad" in joined


# ---------------------------------------------------------------------------
# Chapters + titles + links
# ---------------------------------------------------------------------------

class TestChapters:
    def test_exact_cumulative_boundaries(self):
        data = build_chapters(
            [("Welcome from Mira", 30.0), ("Tesla — hook", 500.5), ("Sign-off", 20.0)],
            "Ep 1: test")
        chs = data["chapters"]
        assert data["version"] == "1.2.0"
        assert [c["startTime"] for c in chs] == [0.0, 30.0, 530.5]
        assert chs[-1]["endTime"] == 550.5


class TestTitles:
    def test_title_owned_by_titles_module(self):
        seg = Segment(
            slug="tesla", show_name="Tesla Shorts Time", episode_num=578,
            episode_title="Ep 578: " + "very long hook " * 30,
            hook="very long hook " * 30, date="2026-08-20", audio_url="",
            content="", digest_dir=Path("."), transcript_path=None,
            music_intro_offset=3.0)
        title = daily_title(12, dt.date(2026, 8, 20), [seg])
        assert len(title) <= 100  # PODCAST_EPISODE_TITLE_MAX
        assert title.startswith("Ep 12: Thursday edition")

    def test_hook_from_title(self):
        assert hook_from_title("Ep 578: The hook text") == "The hook text"
        assert hook_from_title("No label here") == "No label here"

    def test_strip_op3(self):
        assert strip_op3("https://op3.dev/e/https://audio.nerranetwork.com/a.mp3") == \
            "https://audio.nerranetwork.com/a.mp3"
        assert strip_op3("https://audio.nerranetwork.com/a.mp3") == \
            "https://audio.nerranetwork.com/a.mp3"


class TestLinks:
    def _segments(self, n=3):
        return [
            Segment(slug=f"s{i}", show_name=f"Show {i}", episode_num=i,
                    episode_title=f"Ep {i}: hook {i}", hook=f"hook {i}",
                    date="2026-08-20", audio_url="", content="",
                    digest_dir=Path("."), transcript_path=None,
                    music_intro_offset=3.0)
            for i in range(1, n + 1)
        ]

    def test_parse_happy_path_with_fences(self):
        raw = "```json\n" + json.dumps({
            "intro": "Hello.", "handoffs": ["one", "two"], "signoff": "Bye."
        }) + "\n```"
        parsed = parse_links_json(raw, 2)
        assert parsed and parsed["handoffs"] == ["one", "two"]

    def test_parse_rejects_short_handoffs(self):
        raw = json.dumps({"intro": "Hi", "handoffs": ["one"], "signoff": "Bye"})
        assert parse_links_json(raw, 2) is None

    def test_fallback_covers_every_gap_with_real_titles(self):
        segs = self._segments(4)
        links = fallback_links(SPEC, segs, dt.date(2026, 8, 20))
        assert len(links["handoffs"]) == 3
        assert "hook 2" in links["handoffs"][0]
        assert "nerranetwork.com" in links["signoff"]

    def test_sanitize_spoken(self):
        assert sanitize_spoken("**Bold** [link](https://x.com) `code`") == "Bold link code"

    def test_parse_find_text_skip_and_bounds(self):
        from engine.daily_edition import parse_find_text

        assert parse_find_text("SKIP") is None
        assert parse_find_text("") is None
        assert parse_find_text("too short to air") is None
        good = ("According to the European Space Agency, a spacecraft " +
                "measured something remarkable this week. " * 5)
        parsed = parse_find_text(good)
        assert parsed and "European Space Agency" in parsed

    def test_digest_md_carries_field_note(self):
        from engine.daily_edition import build_digest_md

        segs = self._segments(4)
        links = fallback_links(SPEC, segs, dt.date(2026, 8, 21))
        md = build_digest_md(SPEC, ROOT, 2, dt.date(2026, 8, 21), segs,
                             links, None, find_text="A note from Mira.")
        assert "## Mira's field note" in md
        assert "A note from Mira." in md
        md_none = build_digest_md(SPEC, ROOT, 2, dt.date(2026, 8, 21), segs,
                                  links, None, find_text=None)
        assert "field note" not in md_none


# ---------------------------------------------------------------------------
# Blog surface — the rundown must give engine.blog a real hook (2026-08-25)
# ---------------------------------------------------------------------------

class TestBlogSurface:
    """The first four editions' blog posts all titled themselves with the
    italic byline ("Hosted by Mira · Episode N · …") because the rundown
    .md carried no hook line and engine.blog's June-2026 normalization
    replaces a show-name-prefixed H1 with the derived hook. Pins: the
    digest emits the ``> **<hook>**`` blockquote engine.blog matches, the
    handoffs are committed as per-section prose, and metadata extraction
    lands on the per-day hook."""

    def _segments(self, n=4):
        return [
            Segment(slug=f"s{i}", show_name=f"Show {i}", episode_num=i,
                    episode_title=f"Ep {i}: hook {i}", hook=f"hook {i}",
                    date="2026-08-24", audio_url="", content="",
                    digest_dir=Path("."), transcript_path=None,
                    music_intro_offset=0.0)
            for i in range(1, n + 1)
        ]

    def _md(self, links=None):
        from engine.daily_edition import build_digest_md

        segs = self._segments()
        links = links or fallback_links(SPEC, segs, dt.date(2026, 8, 24))
        return build_digest_md(SPEC, ROOT, 4, dt.date(2026, 8, 24), segs,
                               links, None)

    def test_digest_carries_blockquote_hook(self):
        md = self._md()
        assert "> **Monday edition — hook 1**" in md
        # The hook precedes the byline, so _HOOK_PATTERNS win before the
        # fallback scan ever runs.
        assert md.index("> **Monday edition") < md.index("*Hosted by")

    def test_blog_metadata_title_is_the_edition_hook(self):
        from engine.blog import extract_blog_metadata

        meta = extract_blog_metadata(
            self._md(), "nerra_daily", "Nerra_Daily_Ep004_20260824.md")
        assert meta["title"].startswith("Monday edition — hook 1")
        assert "Hosted by" not in meta["title"]

    def test_byline_never_becomes_hook_even_without_blockquote(self):
        # Legacy shape (pre-backfill rundowns): no blockquote hook. The
        # italic byline must be skipped by the hook fallback; the intro
        # prose is an acceptable last resort.
        from engine.blog import extract_blog_metadata

        md = self._md()
        md = "\n".join(l for l in md.splitlines() if not l.startswith("> **"))
        meta = extract_blog_metadata(
            md, "nerra_daily", "Nerra_Daily_Ep004_20260824.md")
        assert not meta["hook"].startswith("Hosted by")
        assert not meta["title"].startswith("Hosted by")

    def test_committed_rundowns_carry_the_hook(self):
        # The four launch rundowns were backfilled; every future rundown
        # gets the hook from build_digest_md. A committed rundown without
        # one regresses the whole blog surface for that day.
        paths = sorted((ROOT / SPEC.digest_dir).glob(
            f"{SPEC.episode_prefix}_Ep*_*.md"))
        assert paths, "no committed rundowns found"
        for p in paths:
            assert "\n> **" in p.read_text(encoding="utf-8"), p.name

    def test_handoffs_committed_as_section_prose(self):
        segs = self._segments()
        links = fallback_links(SPEC, segs, dt.date(2026, 8, 24))
        links["handoffs"] = ["Handoff into two.", "Handoff into three.",
                             "Handoff into four."]
        from engine.daily_edition import build_digest_md

        md = build_digest_md(SPEC, ROOT, 4, dt.date(2026, 8, 24), segs,
                             links, None)
        # Handoff i-1 sits under section i (it is what introduces it);
        # the first section has no handoff (the intro covers it).
        assert "Handoff into two." in md
        assert md.index("### Show 2") < md.index("Handoff into two.")
        assert md.index("Handoff into two.") < md.index("### Show 3")
        assert md.index("### Show 1") < md.index("### Show 2")
        first_section = md[md.index("### Show 1"):md.index("### Show 2")]
        assert "Handoff" not in first_section


# ---------------------------------------------------------------------------
# Edition metrics — the committed per-build record (2026-08-25)
# ---------------------------------------------------------------------------

class TestEditionMetrics:
    """The edition previously committed NO record of what the splice did:
    a trim that stopped matching, a fallback-links day, or an expected
    show missing the build window (Offshore North, Monday 2026-08-24)
    looked identical to a healthy day."""

    def test_metrics_shape(self):
        from engine.daily_edition import build_edition_metrics

        seg = Segment(slug="tesla", show_name="Tesla Shorts Time",
                      episode_num=582, episode_title="Ep 582: t", hook="t",
                      date="2026-08-24", audio_url="", content="",
                      digest_dir=Path("."), transcript_path=None,
                      music_intro_offset=0.0,
                      cut_final_seconds=345.4, cut_kind="promo",
                      duration_seconds=345.4)
        whole = Segment(slug="dp_pod", show_name="The DP Pod",
                        episode_num=45, episode_title="Ep 45: d", hook="d",
                        date="2026-08-24", audio_url="", content="",
                        digest_dir=Path("."), transcript_path=None,
                        music_intro_offset=0.0, duration_seconds=689.9)
        m = build_edition_metrics(
            4, dt.date(2026, 8, 24), 5095.8, [seg, whole],
            links_source="llm", field_note_included=True,
            missing_expected=["offshore_north"], dropped=[])
        assert m["episode_num"] == 4 and m["date"] == "2026-08-24"
        assert m["segment_count"] == 2
        assert m["segments"][0]["cut_kind"] == "promo"
        assert m["segments"][1]["cut_kind"] == "none"
        assert m["segments_shipped_whole"] == 1
        assert m["missing_expected"] == ["offshore_north"]
        assert m["links_source"] == "llm"
        assert m["field_note_included"] is True

    def test_orchestrator_writes_metrics(self):
        # The publish path must write metrics_ep*.json — pinned at the
        # source level so a refactor cannot silently drop the record.
        src = (ROOT / "scripts" / "build_daily_edition.py").read_text(
            encoding="utf-8")
        assert "build_edition_metrics" in src
        assert 'metrics_ep{episode_num:03d}.json' in src


# ---------------------------------------------------------------------------
# Rotation memory — data-side do-not-repeat blocks (2026-08-25)
# ---------------------------------------------------------------------------

class TestRotationMemory:
    """All four launch editions opened "Good morning." and nothing stopped
    Mira's field note from re-finding a recent item: the prompts only ever
    saw one day. The fix is the DP Pod lever-memory pattern — committed
    rundowns are parsed back into do-not-repeat blocks. Instruction-only
    variety asks were violated six days straight on dp_pod; memory must
    stay DATA-side."""

    def test_recent_intro_openers_from_committed_rundowns(self):
        from engine.daily_edition import recent_intro_openers

        from engine.daily_edition import RECENT_MEMORY_EPISODES

        openers = recent_intro_openers(SPEC, ROOT)
        assert openers, "no openers parsed from committed rundowns"
        assert len(openers) <= RECENT_MEMORY_EPISODES
        # Never a heading/byline — always spoken prose.
        for o in openers:
            assert not o.startswith(("#", "*", ">")), o
        # The launch tic this memory exists to break. The rolling window
        # is SUPPOSED to forget it (Ep015 on 2026-09-04 rolled the last
        # "Good morning" launch edition out of the ten-episode window and
        # this assertion, written against the live window, went red on
        # main) — so read the whole committed history for it instead.
        history = recent_intro_openers(SPEC, ROOT, limit=10_000)
        assert any(o.startswith("Good morning") for o in history)

    def test_recent_field_note_topics_from_committed_rundowns(self):
        from engine.daily_edition import recent_field_note_topics

        topics = recent_field_note_topics(SPEC, ROOT)
        # Eps 2-4 carry field notes at minimum.
        assert len(topics) >= 2
        for t in topics:
            assert len(t.split()) <= 28

    def test_links_prompt_injects_opener_memory(self):
        from engine.daily_edition import build_links_prompt

        segs = [
            Segment(slug="s1", show_name="Show 1", episode_num=1,
                    episode_title="Ep 1: hook", hook="hook",
                    date="2026-08-24", audio_url="", content="prose here",
                    digest_dir=Path("."), transcript_path=None,
                    music_intro_offset=0.0)
        ]
        prompt = build_links_prompt(SPEC, ROOT, segs, dt.date(2026, 8, 25), None)
        assert "Recent editions opened with these lines" in prompt
        # Every opener in the live window is shown back — whatever the
        # window holds today (the literal launch tic rolled out of it).
        from engine.daily_edition import recent_intro_openers
        openers = recent_intro_openers(SPEC, ROOT)
        assert openers
        for o in openers:
            assert f"- {o}" in prompt, o

    def test_find_prompt_injects_field_note_memory(self):
        from engine.daily_edition import build_find_prompt

        segs = [
            Segment(slug="s1", show_name="Show 1", episode_num=1,
                    episode_title="Ep 1: hook", hook="hook",
                    date="2026-08-24", audio_url="", content="",
                    digest_dir=Path("."), transcript_path=None,
                    music_intro_offset=0.0)
        ]
        prompt = build_find_prompt(SPEC, ROOT, segs, dt.date(2026, 8, 25))
        assert "recent field notes covered these items" in prompt

    def test_memory_blocks_empty_on_fresh_edition(self, tmp_path):
        # A brand-new edition (no committed rundowns) must render the
        # prompts with EMPTY memory blocks, not crash — copy the prompt
        # files into a bare root and build against it.
        import shutil

        from engine.daily_edition import (
            build_find_prompt, build_links_prompt, recent_intro_openers,
        )

        (tmp_path / "shows" / "prompts").mkdir(parents=True)
        for f in (SPEC.prompt_file, SPEC.find_prompt_file):
            shutil.copy(ROOT / f, tmp_path / f)
        assert recent_intro_openers(SPEC, tmp_path) == []
        segs = [
            Segment(slug="s1", show_name="Show 1", episode_num=1,
                    episode_title="Ep 1: hook", hook="hook",
                    date="2026-08-24", audio_url="", content="",
                    digest_dir=Path("."), transcript_path=None,
                    music_intro_offset=0.0)
        ]
        p1 = build_links_prompt(SPEC, tmp_path, segs, dt.date(2026, 8, 25), None)
        p2 = build_find_prompt(SPEC, tmp_path, segs, dt.date(2026, 8, 25))
        assert "Recent editions opened" not in p1
        assert "recent field notes covered" not in p2


# ---------------------------------------------------------------------------
# Sep 3 2026 review — promo-cut hardening, rotation memory v2, edition
# title, show notes with timestamps, link-shape metrics
# ---------------------------------------------------------------------------

def _seg(i, name=None, hook=None, **kw):
    base = dict(slug=f"s{i}", show_name=name or f"Show {i}", episode_num=i,
                episode_title=f"Ep {i}: {hook or f'hook {i}'}",
                hook=hook or f"hook {i}", date="2026-09-03", audio_url="",
                content="", digest_dir=Path("."), transcript_path=None,
                music_intro_offset=0.0)
    base.update(kw)
    return Segment(**base)


class TestPromoCutHardening:
    """Whisper renders "our sister show SpaceX Daily" as "sister shows"
    and "sisters show" — the singular-only frame regex missed, the weak
    brand-mention fallback matched The DP Pod's in-body Dispatch CTA
    ("hit the dispatch button on the show page at nerranetwork.com"), and
    Nerra Daily Ep10 (2026-08-30) shipped DP Pod Ep52 minus its Dispatch
    invitation, both hosts' sign-off and "Do something about it" (69 s).
    Same failure on DP Pod Ep39 (63 s, pre-launch)."""

    @pytest.mark.parametrize("rel_path, max_tail", [
        ("digests/dp_pod/DP_Pod_Ep052_20260830_transcript.json", 45.0),
        ("digests/dp_pod/DP_Pod_Ep039_20260818_transcript.json", 45.0),
        ("digests/first_principles/First_Principles_Ep075_20260819_transcript.json", 45.0),
    ])
    def test_whisper_plural_sister_show_hits_the_frame(self, rel_path, max_tail):
        path = ROOT / rel_path
        if not path.exists():
            pytest.skip(f"{rel_path} not committed")
        transcript = json.loads(path.read_text(encoding="utf-8"))
        hit = find_promo_cut(transcript)
        assert hit and hit["kind"] == "promo", hit
        tail = float(transcript["duration"]) - hit["raw_seconds"]
        assert tail <= max_tail, f"cut removed {tail:.1f}s — that is content, not the plug"

    def _synthetic(self, words, duration):
        # One transcript segment per sentence; words spaced 0.4 s apart.
        segments, t = [], duration - 0.4 * sum(len(w.split()) for w in words) - 1
        for sentence in words:
            toks = sentence.split()
            wl = [{"word": w, "start": t + 0.4 * k, "end": t + 0.4 * k + 0.3}
                  for k, w in enumerate(toks)]
            segments.append({"start": wl[0]["start"], "end": wl[-1]["end"],
                             "text": sentence, "words": wl})
            t = wl[-1]["end"] + 0.1
        return {"duration": duration, "segments": segments}

    def test_weak_mention_far_from_end_is_treated_as_body(self):
        # Brand mention 90 s before the end (a body CTA), disclosure at the
        # very end: the fallback must NOT cut at the mention.
        body = ["hit the dispatch button on the show page at nerranetwork com"]
        filler = ["and now some more real content " * 30]
        tail = ["this episode used ai voice synthesis of our voices"]
        t = self._synthetic(body + filler + tail, 800.0)
        hit = find_promo_cut(t)
        assert hit and hit["kind"] == "disclosure", hit
        assert 800.0 - hit["raw_seconds"] < 10

    def test_weak_mention_near_end_still_trims(self):
        body = ["real content " * 40]
        tail = ["all our shows are free at nerra network dot com",
                "this episode used ai voice synthesis of my voice"]
        t = self._synthetic(body + tail, 700.0)
        hit = find_promo_cut(t)
        assert hit and hit["kind"] == "network_mention", hit
        assert 700.0 - hit["raw_seconds"] <= 60.0

    @pytest.mark.parametrize("phrase", [
        "one more thing if you liked today s episode our sister show spacex daily is worth a spot",
        "one more thing if you like today s episode our sister shows spacex daily is worth a spot",
        "one more thing if you liked today s episode our sisters show space x daily is worth a spot",
    ])
    def test_sister_show_whisper_variants(self, phrase):
        from engine.daily_edition import _PRIMARY_PROMO_PATTERNS
        assert any(p.search(phrase) for p in _PRIMARY_PROMO_PATTERNS), phrase

    def test_every_recent_lineup_transcript_hits_a_frame(self):
        # Network-wide: every committed transcript from the last ~3 weeks
        # must trim on FRAME evidence. A weak-evidence kind here means a
        # new Whisper spelling or a new promo frame — extend the matcher,
        # never lean on the fallback (it cut real content twice).
        import glob as _glob
        import re as _re
        weak = []
        for slug in SPEC.lineup:
            for p in sorted(_glob.glob(str(ROOT / "digests" / slug / "*_transcript.json"))):
                m = _re.search(r"_(\d{8})_transcript", p)
                if not m or m.group(1) < "20260815":
                    continue
                t = json.loads(Path(p).read_text(encoding="utf-8"))
                hit = find_promo_cut(t)
                if not hit or hit["kind"] != "promo":
                    weak.append((Path(p).name, hit and hit["kind"]))
        assert not weak, weak


class TestRotationMemoryV2:
    """The first memory pass compared raw opening words — and the date is
    the first thing Mira says, so 'Friday, August 28, 2026, opens Nerra
    Daily' and 'Saturday, August 29, 2026 opens Nerra Daily' looked like
    different lines while being one sentence (5/9 post-fix editions). The
    sign-off (7/9 'Across these segments…') and the field-note closer
    (10/13 'It is the kind of X that quietly Y') had no memory at all."""

    def test_normalize_date_tokens_exposes_the_skeleton(self):
        from engine.daily_edition import normalize_date_tokens
        a = normalize_date_tokens("Friday, August 28, 2026, opens Nerra Daily with Mira speaking.")
        b = normalize_date_tokens("Saturday, August 29, 2026 opens Nerra Daily with Mira speaking.")
        assert a == b == "[date] opens Nerra Daily with Mira speaking."
        assert normalize_date_tokens("Monday, August 31, 2026. This is Nerra Daily.") == \
            "[date]. This is Nerra Daily."
        assert normalize_date_tokens("Good morning. This is Mira.") == "Good morning. This is Mira."

    def test_intro_openers_are_date_normalized(self):
        from engine.daily_edition import recent_intro_openers
        openers = recent_intro_openers(SPEC, ROOT)
        assert openers
        import re as _re
        for o in openers:
            assert not _re.search(r"\b2026\b|\bAugust\b|\bSeptember\b", o), o

    def test_signoff_and_closer_memory_from_committed_rundowns(self):
        from engine.daily_edition import (recent_field_note_closers,
                                          recent_signoff_openers)
        signoffs = recent_signoff_openers(SPEC, ROOT)
        assert signoffs and any(s.startswith("Across") for s in signoffs)
        closers = recent_field_note_closers(SPEC, ROOT)
        assert closers and all(c.endswith((".", "!", "?")) for c in closers)

    def test_links_prompt_injects_signoff_memory(self):
        from engine.daily_edition import build_links_prompt
        segs = [_seg(1), _seg(2), _seg(3), _seg(4)]
        prompt = build_links_prompt(SPEC, ROOT, segs, dt.date(2026, 9, 3), None)
        assert "Recent sign-offs opened with these lines" in prompt
        assert "[date] stands for" in prompt
        assert "{recent_signoffs}" not in prompt

    def test_find_prompt_injects_closer_memory(self):
        from engine.daily_edition import build_find_prompt
        segs = [_seg(1), _seg(2), _seg(3), _seg(4)]
        prompt = build_find_prompt(SPEC, ROOT, segs, dt.date(2026, 9, 3))
        assert "ENDED on these sentences" in prompt

    def test_prompts_carry_no_seed_adverb(self):
        # De-seed by shape: "quietly witty" / "quietly delighted" in the two
        # prompts became "quietly" in 10 of 13 field-note closers.
        for rel in (SPEC.prompt_file, SPEC.find_prompt_file):
            text = (ROOT / rel).read_text(encoding="utf-8").lower()
            assert "quietly witty" not in text and "quietly delighted" not in text, rel
        find = (ROOT / SPEC.find_prompt_file).read_text(encoding="utf-8")
        assert "closing sentence must not" in find
        links = (ROOT / SPEC.prompt_file).read_text(encoding="utf-8")
        assert "{recent_signoffs}" in links
        assert '"title"' in links
        assert "At most ONE handoff in three" in links


class TestEditionTitle:
    """Every one of the first 14 editions was titled with SpaceX Daily's
    hook (the lead show), so the all-network product read as a SpaceX show
    in every directory. The links call now also writes a one-line headline
    for the whole day; the lead hook stays the fallback."""

    def test_validate_bounds_and_rejections(self):
        from engine.daily_edition import validate_edition_title as v
        assert v("Starship's Louisiana site, a dementia signal, cheaper grid storage") \
            == "Starship's Louisiana site, a dementia signal, cheaper grid storage"
        assert v("too short") == ""
        assert v("x" * 80) == ""
        assert v("Nerra Daily for Thursday: rockets and rates") == ""
        assert v("Thursday, September 3, 2026: rockets, rates and robots") == ""
        assert v("Wednesday edition of rockets, rates and robots") == ""
        assert v('"**Rockets, rates and a bone scaffold that grows itself.**"') == \
            "Rockets, rates and a bone scaffold that grows itself"

    def test_parse_carries_title_and_survives_without_it(self):
        raw = json.dumps({"title": "Rockets, rates and a scaffold that grows bone",
                          "intro": "Hello.", "handoffs": ["one", "two"], "signoff": "Bye."})
        parsed = parse_links_json(raw, 2)
        assert parsed["title"] == "Rockets, rates and a scaffold that grows bone"
        legacy = parse_links_json(json.dumps({"intro": "Hello.", "handoffs": ["one", "two"],
                                              "signoff": "Bye."}), 2)
        assert legacy and legacy["title"] == ""

    def test_edition_hook_prefers_the_written_headline(self):
        from engine.daily_edition import edition_hook
        segs = [_seg(1, "SpaceX Daily", "FAA clearance for a wider Starship corridor")]
        d = dt.date(2026, 9, 3)
        assert edition_hook(d, segs) == "Thursday edition — FAA clearance for a wider Starship corridor"
        assert edition_hook(d, segs, "Rockets, rates and a scaffold that grows bone") == \
            "Thursday edition — Rockets, rates and a scaffold that grows bone"

    def test_daily_title_with_headline_stays_within_the_limit(self):
        from engine.titles import PODCAST_EPISODE_TITLE_MAX
        segs = [_seg(1, "SpaceX Daily", "lead hook")]
        title = daily_title(14, dt.date(2026, 9, 3), segs, "x" * 72)
        assert title.startswith("Ep 14: Thursday edition — ")
        assert len(title) <= PODCAST_EPISODE_TITLE_MAX

    def test_digest_blockquote_uses_the_headline(self):
        from engine.daily_edition import build_digest_md
        segs = [_seg(i) for i in range(1, 5)]
        links = fallback_links(SPEC, segs, dt.date(2026, 9, 3))
        links["title"] = "Rockets, rates and a scaffold that grows bone"
        md = build_digest_md(SPEC, ROOT, 14, dt.date(2026, 9, 3), segs, links, None)
        assert "> **Thursday edition — Rockets, rates and a scaffold that grows bone**" in md

    def test_orchestrator_passes_the_title_through(self):
        src = (ROOT / "scripts" / "build_daily_edition.py").read_text(encoding="utf-8")
        assert 'links.get("title", "")' in src


class TestShowNotes:
    """A ~2 h, 13-segment episode was published with show notes that were a
    bullet list of hooks — no way to jump to a show from the notes in the
    apps that do not render podcast:chapters — and Mira's field note (the
    edition's only unique text) reached no written surface but the blog."""

    def test_format_timestamp(self):
        from engine.daily_edition import format_timestamp
        assert format_timestamp(0) == "0:00"
        assert format_timestamp(33.2) == "0:33"
        assert format_timestamp(491.2) == "8:11"
        assert format_timestamp(3934.3) == "1:05:34"

    def test_notes_carry_chapter_timestamps_and_field_note(self):
        from engine.daily_edition import feed_description
        segs = [_seg(1, "SpaceX Daily", "lead"), _seg(2, "Tesla Shorts Time", "second")]
        chapters = build_chapters([("Welcome from Mira", 33.2),
                                   ("SpaceX Daily — lead", 458.0),
                                   ("Mira's field note", 23.4),
                                   ("Tesla Shorts Time — second", 384.4),
                                   ("Sign-off", 30.8)], "Ep 14")
        notes = feed_description(SPEC, segs, dt.date(2026, 9, 3), chapters,
                                 "Bats carry two sets of antibody genes.")
        assert "0:00 Welcome from Mira" in notes
        assert "0:33 SpaceX Daily — lead" in notes
        assert "8:11 Mira's field note" in notes
        assert "Mira's field note: Bats carry two sets of antibody genes." in notes
        assert "https://nerranetwork.com" in notes

    def test_notes_without_chapters_keep_the_legacy_bullets(self):
        from engine.daily_edition import feed_description
        segs = [_seg(1, "SpaceX Daily", "lead")]
        notes = feed_description(SPEC, segs, dt.date(2026, 9, 3))
        assert "• SpaceX Daily: lead" in notes
        assert "field note" not in notes

    def test_orchestrator_feeds_chapters_and_host_to_the_feed(self):
        src = (ROOT / "scripts" / "build_daily_edition.py").read_text(encoding="utf-8")
        assert "feed_description(spec, segments, target_date, chapters, find_text)" in src
        assert "person_name=spec.host" in src
        # Chapters are built ONCE and shared by the JSON file and the notes.
        assert src.count("build_chapters(chapter_pieces, title)") == 1


class TestLinkShapeMetrics:
    def test_handoffs_show_name_led(self):
        from engine.daily_edition import handoffs_show_name_led
        segs = [_seg(1, "SpaceX Daily"), _seg(2, "Tesla Shorts Time"),
                _seg(3, "Omni View")]
        links = {"handoffs": ["Tesla Shorts Time follows with…",
                              "A funding bill signed at the last minute — Omni View…"]}
        assert handoffs_show_name_led(links, segs) == 1

    def test_metrics_carry_link_shape_signals(self):
        from engine.daily_edition import build_edition_metrics
        segs = [_seg(1, "SpaceX Daily"), _seg(2, "Tesla Shorts Time")]
        links = {"intro": "one two three four", "handoffs": ["Tesla Shorts Time follows"],
                 "signoff": "bye", "title": "Rockets and rates"}
        m = build_edition_metrics(14, dt.date(2026, 9, 3), 100.0, segs,
                                  links_source="llm", field_note_included=False,
                                  missing_expected=[], dropped=[], links=links)
        assert m["intro_words"] == 4
        assert m["handoffs_show_name_led"] == 1 and m["handoff_count"] == 1
        assert m["edition_title_source"] == "llm"
        legacy = build_edition_metrics(14, dt.date(2026, 9, 3), 100.0, segs,
                                       links_source="fallback", field_note_included=False,
                                       missing_expected=[], dropped=[])
        assert legacy["edition_title_source"] == "lead_hook"
        src = (ROOT / "scripts" / "build_daily_edition.py").read_text(encoding="utf-8")
        assert "links=links," in src


class TestRegistryCopy:
    def test_description_long_matches_the_real_rundown(self):
        # The show page said "flagships first: Tesla Shorts Time, Models &
        # Agents, SpaceX Daily…" — the pre-Ep1 order. The operator's fixed
        # rundown leads with SpaceX Daily; the copy must name the lead
        # show before any other lineup show.
        meta = yaml.safe_load((ROOT / "shows" / "network_meta.yaml").read_text())
        text = meta["nerra_daily"]["description_long"]
        lead = text.find("SpaceX Daily")
        assert lead >= 0
        for other in ("Tesla Shorts Time", "Models & Agents", "Modern Investing"):
            assert text.find(other) > lead, other
        assert "field note" in text


class TestSkipAwareGate:
    """On 2026-08-30 and 2026-09-03 the edition built at 12:41 / 12:09 UTC
    against ~08:13 on a complete day, because the ready gate waited until
    the force hour for a UC episode that had committed a skip marker at
    07:25. A show that told the network it skipped is not "missing"."""

    @staticmethod
    def _root(tmp_path, date):
        import dataclasses
        root = tmp_path
        (root / "shows").mkdir()
        for slug in ("spacex", "unintended_consequences", "tesla"):
            d = root / "digests" / slug
            d.mkdir(parents=True)
            (root / "shows" / f"{slug}.yaml").write_text("x: 1")
        (root / "digests" / "spacex" / "summaries_spacex.json").write_text(json.dumps({
            "summaries": [{"date": date.isoformat(), "episode_num": 90,
                           "episode_title": "Ep 90: lead", "audio_url":
                           "https://audio.nerranetwork.com/spacex/x.mp3",
                           "content": ""}]}))
        (root / "digests" / "unintended_consequences" / f".skip_{date:%Y%m%d}.json").write_text(
            json.dumps({"date": date.isoformat(), "show": "unintended_consequences",
                        "reason": "source_integrity_failed", "detail": "…"}))
        spec = dataclasses.replace(SPEC, lineup=("spacex", "unintended_consequences", "tesla"),
                                   monday_only=frozenset())

        class _Cfg:
            def __init__(self, slug):
                self.name = slug
                self.publishing = type("P", (), {
                    "summaries_json": f"digests/{slug}/summaries_{slug}.json"})()
                self.audio = type("A", (), {"voice_intro_delay": 0.0})()

        def loader(path):
            return _Cfg(Path(path).stem)

        return root, spec, loader

    def test_skipped_show_is_not_missing(self, tmp_path):
        from engine.daily_edition import discover_lineup
        date = dt.date(2026, 9, 3)
        root, spec, loader = self._root(tmp_path, date)
        lineup = discover_lineup(spec, root, date, config_loader=loader)
        assert [s.slug for s in lineup.segments] == ["spacex"]
        assert lineup.missing == ["tesla"]
        assert lineup.skipped == [{"slug": "unintended_consequences",
                                   "reason": "source_integrity_failed"}]
        # The two-tuple wrapper keeps its shape and excludes the skip.
        segments, missing = discover_segments(spec, root, date, config_loader=loader)
        assert missing == ["tesla"]

    def test_marker_for_another_date_is_ignored(self, tmp_path):
        from engine.daily_edition import discover_lineup
        root, spec, loader = self._root(tmp_path, dt.date(2026, 9, 2))
        lineup = discover_lineup(spec, root, dt.date(2026, 9, 3), config_loader=loader)
        assert "unintended_consequences" in lineup.missing
        assert lineup.skipped == []

    def test_published_after_skip_still_splices(self, tmp_path):
        # UC 2026-09-03: gate-blocked 07:25, the late cron republished at
        # 13:25 — an entry dated today wins over the marker.
        from engine.daily_edition import discover_lineup
        date = dt.date(2026, 9, 3)
        root, spec, loader = self._root(tmp_path, date)
        (root / "digests" / "unintended_consequences" /
         "summaries_unintended_consequences.json").write_text(json.dumps({
            "summaries": [{"date": date.isoformat(), "episode_num": 105,
                           "episode_title": "Ep 105: t", "audio_url":
                           "https://audio.nerranetwork.com/uc/x.mp3"}]}))
        lineup = discover_lineup(spec, root, date, config_loader=loader)
        assert [s.slug for s in lineup.segments] == ["spacex", "unintended_consequences"]
        assert lineup.skipped == []

    def test_metrics_and_gate_carry_the_skip(self):
        from engine.daily_edition import build_edition_metrics
        m = build_edition_metrics(15, dt.date(2026, 9, 4), 100.0, [],
                                  links_source="llm", field_note_included=False,
                                  missing_expected=[], dropped=[],
                                  skipped_today=[{"slug": "unintended_consequences",
                                                  "reason": "source_integrity_failed"}])
        assert m["skipped_today"][0]["slug"] == "unintended_consequences"
        src = (ROOT / "scripts" / "build_daily_edition.py").read_text(encoding="utf-8")
        assert src.count("discover_lineup(spec, ROOT, target_date)") == 2
        assert "skipped_today=skipped" in src
        # run-show.yml commits the marker on EVERY graceful skip, not only
        # gate blocks — the gate's evidence depends on that step's guard.
        wf = (ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8")
        assert "steps.pipeline.outputs.skipped == 'true'" in wf
        assert '[ -f "$SKIP_MARKER" ] && git add -f "$SKIP_MARKER"' in wf
