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

        openers = recent_intro_openers(SPEC, ROOT)
        assert openers, "no openers parsed from committed rundowns"
        # The launch tic this memory exists to break:
        assert any(o.startswith("Good morning") for o in openers)
        # Never a heading/byline — always spoken prose.
        for o in openers:
            assert not o.startswith(("#", "*", ">")), o

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
        assert "Good morning" in prompt

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
