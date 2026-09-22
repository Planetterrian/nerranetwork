"""Long-form fact cards (Sep 9 2026) — engine/fact_cards.py.

Spoken figures become timed on-screen cards driven by the Whisper word
transcript. Render-only, best-effort, per-show YAML gate.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from engine import fact_cards as fc

ROOT = Path(__file__).resolve().parents[1]


def _w(tokens, start=10.0, step=0.5):
    """Whisper-shaped word dicts from a token list."""
    out = []
    t = start
    for tok in tokens:
        out.append({"word": tok, "start": round(t, 2), "end": round(t + step, 2)})
        t += step
    return out


class TestFigureMerging:
    def test_split_dollar_figure_is_rejoined(self):
        words = _w(["TSLA", "closed", "at", "$368", ".16,", "up", "4%."])
        cards = fc.extract_fact_cards(words, open_skip_s=0)
        figs = [c.figure for c in cards]
        assert "$368.16" in figs

    def test_thousands_separator_token_is_rejoined(self):
        words = _w(["shipped", "4", ",000", "units", "in", "August."])
        cards = fc.extract_fact_cards(words, open_skip_s=0)
        assert cards and cards[0].figure == "4,000 units"   # count noun rides along (Sep 22 2026)

    def test_unit_words_attach_and_percent_normalises(self):
        words = _w(["raised", "$450", "million", "in", "a", "round."])
        cards = fc.extract_fact_cards(words, open_skip_s=0)
        assert cards[0].figure == "$450 million"
        words = _w(["margins", "rose", "12", "percent", "this", "quarter."])
        cards = fc.extract_fact_cards(words, open_skip_s=0)
        assert cards[0].figure == "12%"

    def test_tokens_with_letters_are_never_figures(self):
        words = _w(["Falcon", "9", "booster", "B1081", "flew", "in", "the", "1990s."])
        cards = fc.extract_fact_cards(words, open_skip_s=0)
        assert cards == []


class TestSelection:
    def test_episode_number_and_years_are_never_cards(self):
        words = _w(["This", "is", "episode", "600.", "Back", "in", "2021,", "it", "began."])
        assert fc.extract_fact_cards(words, open_skip_s=0) == []

    def test_opening_window_and_chapter_clearance(self):
        words = _w(["$5", "billion", "now."], start=2.0) + _w(
            ["$6", "billion", "later."], start=100.0) + _w(
            ["$7", "billion", "after."], start=200.0)
        cards = fc.extract_fact_cards(words, chapter_starts=[98.0])
        assert [c.figure for c in cards] == ["$7 billion"]

    def test_money_and_percent_outrank_bare_numbers_and_gap_holds(self):
        words = (_w(["about", "500", "cars."], start=50.0)
                 + _w(["worth", "$9", "billion."], start=60.0)
                 + _w(["another", "700", "cars."], start=150.0))
        cards = fc.extract_fact_cards(words, max_cards=2)
        assert [c.figure for c in cards] == ["$9 billion", "700"]

    def test_max_cards_respected_and_sorted_by_time(self):
        words = []
        for i in range(12):
            words += _w([f"${i + 1}", "million", "here."], start=20.0 + 50 * i)
        cards = fc.extract_fact_cards(words)
        assert len(cards) == fc.MAX_CARDS
        assert [c.start for c in cards] == sorted(c.start for c in cards)


class TestLabels:
    def test_label_never_ends_on_a_dangling_word_and_fits(self):
        from engine.titles import FACT_CARD_LABEL_MAX, fits
        words = _w(["$280", "million", "contract", "for", "the", "Space",
                    "Development", "Agency", "tranche", "program", "in", "orbit."])
        cards = fc.extract_fact_cards(words, open_skip_s=0)
        lab = cards[0].label
        assert fits(lab, FACT_CARD_LABEL_MAX)
        assert not lab.lower().endswith((" for", " the", " in", " of"))
        assert lab[0].isupper()

    def test_label_falls_back_to_words_before_a_sentence_final_figure(self):
        words = _w(["Starship", "reached", "a", "record", "altitude", "of", "150."])
        cards = fc.extract_fact_cards(words, open_skip_s=0)
        assert cards and cards[0].label  # the "before" path produced text
        assert "150" not in cards[0].label

    def test_split_figures_inside_labels_are_rejoined(self):
        words = _w(["$368", ".16,", "up", "$14", ".08", "or", "4%."])
        cards = fc.extract_fact_cards(words, open_skip_s=0)
        assert "$14.08" in cards[0].label


class TestCountNouns:
    """Sep 22 2026: a small count with a unit noun is a fact worth a card."""

    def test_small_count_with_unit_noun_cards(self):
        words = _w(["Falcon", "delivered", "9", "satellites", "to", "orbit", "today."])
        cards = fc.extract_fact_cards(words, open_skip_s=0)
        assert [c.figure for c in cards] == ["9 satellites"]
        assert cards[0].score == 2

    def test_unit_noun_ranks_below_money(self):
        words = (_w(["it", "adds", "1", "gigawatt", "of", "capacity."], start=20.0)
                 + _w(["worth", "$3", "billion", "in", "orders."], start=30.0))
        cards = fc.extract_fact_cards(words, max_cards=1)
        assert [c.figure for c in cards] == ["$3 billion"]

    def test_bare_small_number_still_never_cards(self):
        words = _w(["about", "9", "cars", "were", "seen."])
        assert fc.extract_fact_cards(words, open_skip_s=0) == []

    def test_label_does_not_repeat_the_noun(self):
        words = _w(["it", "flew", "5", "missions", "for", "the", "Space", "Force", "in", "spring."])
        cards = fc.extract_fact_cards(words, open_skip_s=0)
        assert cards[0].figure == "5 missions"
        assert not cards[0].label.lower().startswith("missions")

    def test_year_before_a_count_noun_is_not_a_count(self):
        words = _w(["back", "in", "2021", "launches", "resumed", "quickly."])
        assert fc.extract_fact_cards(words, open_skip_s=0) == []

    def test_designation_after_a_capitalised_word_is_not_a_count(self):
        for toks in (["Falcon", "9", "booster", "B1081", "flew."],
                     ["three", "Raptor", "3", "engines", "fired."],
                     ["the", "Model", "3", "units", "shipped."]):
            assert fc.extract_fact_cards(_w(toks), open_skip_s=0) == [], toks

    def test_spelled_out_numbers_stay_out_of_scope(self):
        words = _w(["it", "flew", "five", "missions", "last", "year."])
        assert fc.extract_fact_cards(words, open_skip_s=0) == []


class TestRenderStage:
    CARDS = [(3.0, "$1", "too early"), (45.0, "$9 billion", "Backlog value"),
             (120.0, "946", "Megawatts of capacity")]

    def test_cards_render_on_both_long_form_paths(self):
        from engine.video import (_long_form_filter_graph,
                                  _single_pass_long_form_filter_graph)
        g2 = _long_form_filter_graph(hook="Hook line", fact_cards=self.CARDS)
        g1 = _single_pass_long_form_filter_graph(
            3, scene_durations=[100.0, 200.0, 100.0], hook="Hook line",
            fact_cards=self.CARDS)
        for g in (g2, g1):
            assert "946" in g and "Megawatts of capacity" in g
            assert "too early" not in g
            assert g.count("[fact") >= 2
            assert "0x00D4FF" in g
            assert g.endswith("[v]") and g.count("[v]") == 1
            assert g.index("Hook") < g.index("946")

    def test_cards_chain_after_chapter_cards_and_before_subtitles(self):
        from engine.video import _long_form_filter_graph
        g = _long_form_filter_graph(
            hook="Hook line", chapter_cards=[(40.0, "The Counterpoint")],
            fact_cards=self.CARDS, subtitles_path="/tmp/x.srt")
        assert g.index("The Counterpoint") < g.index("946") < g.index("subtitles=")

    def test_no_cards_is_byte_identical_legacy(self):
        from engine.video import _long_form_filter_graph
        assert (_long_form_filter_graph(hook="Hook line")
                == _long_form_filter_graph(hook="Hook line", fact_cards=[]))

    def test_over_long_label_is_dropped_not_clipped(self):
        from engine.video import _long_form_fact_cards_stage
        long_label = "a label that is far longer than the thirty-six character limit"
        frag, _ = _long_form_fact_cards_stage("[x]", [(45.0, "$9", long_label)])
        assert "$9" in frag and "thirty-six" not in frag


class TestWiring:
    def test_run_show_gates_on_yaml_and_records_count(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'getattr(config.youtube, "fact_cards_enabled", False)' in src
        assert "fact_cards_for_episode(" in src
        assert "fact_cards=_fact_cards" in src
        assert 'result["fact_cards_rendered"]' in src

    def test_metric_is_on_the_allowlist(self):
        src = (ROOT / "engine" / "pipeline.py").read_text(encoding="utf-8")
        assert 'metrics.record("fact_cards_rendered"' in src

    def test_knob_default_off_and_experiment_shows_on(self):
        from engine.config import YouTubeConfig
        assert YouTubeConfig().fact_cards_enabled is False
        defaults = yaml.safe_load((ROOT / "shows" / "_defaults.yaml").read_text(encoding="utf-8"))
        assert defaults["youtube"]["fact_cards_enabled"] is False
        for slug in ("tesla", "spacex", "fascinating_frontiers"):
            data = yaml.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))
            assert data["youtube"]["fact_cards_enabled"] is True, slug
        for slug in ("models_agents", "models_agents_beginners", "omni_view"):
            data = yaml.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))
            assert "fact_cards_enabled" not in (data.get("youtube") or {}), slug

    def test_real_transcript_produces_sane_cards(self):
        """A committed Tesla transcript: the split "$368" ".16," is one
        figure and the episode number never becomes a card."""
        t = ROOT / "digests/tesla_shorts_time/Tesla_Shorts_Time_Pod_Ep600_20260909_transcript.json"
        c = ROOT / "digests/tesla_shorts_time/chapters_ep600.json"
        if not t.exists():
            return
        cards = fc.fact_cards_for_episode(t, c if c.exists() else None) or []
        figs = [f for _, f, _ in cards]
        assert "$368.16" in figs
        assert "600" not in figs
        assert all(re.search(r"\d", f) for f in figs)


class TestSubscribeCTA:
    """Sep 9 2026: the Shorts end card asks for the subscribe on every
    channel; nothing on the render path still says WATCH FULL EPISODE."""

    def test_defaults_ask_for_the_subscribe(self):
        from engine.config import YouTubeConfig
        cfg = YouTubeConfig()
        assert "SUBSCRIBE" in cfg.shorts_end_card_main_text
        defaults = yaml.safe_load((ROOT / "shows" / "_defaults.yaml").read_text(encoding="utf-8"))
        assert "SUBSCRIBE" in defaults["youtube"]["shorts_end_card_main_text"]

    def test_dub_paths_are_localized_subscribe_asks(self):
        from engine import lang_dub, ru_dub
        assert "ПОДПИШИСЬ" in ru_dub._RU_END_CARD_MAIN
        fr = lang_dub.DUB_LANGUAGES["fr"] if hasattr(lang_dub, "DUB_LANGUAGES") else None
        src = (ROOT / "engine" / "lang_dub.py").read_text(encoding="utf-8")
        assert "ABONNEZ-VOUS" in src
        if fr is not None:
            assert "ABONNEZ" in fr.end_card_main

    def test_no_surface_still_says_watch_full_episode(self):
        for rel in ("engine/video.py", "engine/publisher.py", "run_show.py",
                    "engine/ru_dub.py", "engine/lang_dub.py",
                    "shows/_defaults.yaml", "shows/finansy_prosto.yaml",
                    "shows/privet_russian.yaml"):
            src = (ROOT / rel).read_text(encoding="utf-8")
            code = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
            assert "WATCH FULL EPISODE" not in code, rel
            assert "СМОТРЕТЬ ПОЛНЫЙ ВЫПУСК" not in code, rel


# ---------------------------------------------------------------------------
# Shorts fact cards (Sep 22 2026) — clip-relative window + vertical stage
# ---------------------------------------------------------------------------

def _transcript(tmp_path, words):
    import json
    p = tmp_path / "ep_transcript.json"
    p.write_text(json.dumps({"segments": [{"words": words}]}), encoding="utf-8")
    return p


class TestWindow:
    def test_cards_are_clip_relative_and_inside_the_window(self, tmp_path):
        # Voice timeline: the clip starts at 100 s; "$9 billion" is spoken
        # at 112 s (=12 s into the clip); "$4 million" at 90 s is outside.
        words = (_w(["raised", "$4", "million", "early."], start=90.0)
                 + _w(["backlog", "of", "$9", "billion", "now."], start=112.0)
                 + _w(["and", "77%", "of", "orders", "shipped."], start=160.0))
        t = _transcript(tmp_path, words)
        cards = fc.fact_cards_for_window(t, 100.0, 35.0)
        assert cards is not None
        starts = [s for s, _, _ in cards]
        figs = [f for _, f, _ in cards]
        assert "$9 billion" in figs and "$4 million" not in figs
        assert all(fc.SHORT_OPEN_SKIP_S <= s for s in starts)
        assert all(s + fc.FACT_CARD_SECONDS <= 35.0 - fc.SHORT_TAIL_CLEAR_S
                   for s in starts)
        assert abs(starts[figs.index("$9 billion")] - 13.0) < 0.01

    def test_open_and_tail_are_clear_and_max_two(self, tmp_path):
        words = (_w(["$1", "billion", "open."], start=101.0)      # 1 s in
                 + _w(["$2", "billion", "next."], start=110.0)    # 10 s
                 + _w(["$3", "billion", "then."], start=120.0)    # 20 s
                 + _w(["$4", "billion", "late."], start=131.0))   # 31 s
        t = _transcript(tmp_path, words)
        cards = fc.fact_cards_for_window(t, 100.0, 35.0)
        figs = [f for _, f, _ in cards]
        assert "$1 billion" not in figs   # under the hook band
        assert "$4 billion" not in figs   # would run into the end card
        assert len(cards) <= fc.SHORT_MAX_CARDS

    def test_no_transcript_or_no_words_is_none(self, tmp_path):
        assert fc.fact_cards_for_window(tmp_path / "missing.json", 0.0, 35.0) is None
        t = _transcript(tmp_path, [])
        assert fc.fact_cards_for_window(t, 0.0, 35.0) is None
        t = _transcript(tmp_path, _w(["$9", "billion."], start=500.0))
        assert fc.fact_cards_for_window(t, 0.0, 35.0) is None

    def test_zero_duration_is_none_and_never_raises(self, tmp_path):
        t = _transcript(tmp_path, _w(["$9", "billion."]))
        assert fc.fact_cards_for_window(t, 0.0, 0.0) is None
        assert fc.fact_cards_for_window(object(), 0.0, 35.0) is None


class TestShortRenderStage:
    CARDS = [(2.0, "$1", "under the hook"), (12.0, "$9 billion", "Backlog value"),
             (24.0, "946", "Megawatts of capacity"), (33.0, "77%", "in the end card")]

    def test_none_and_empty_are_byte_identical(self):
        from engine.video import _short_form_filter_graph
        base = _short_form_filter_graph(hook="Hook line", subtitles_path="/tmp/x.ass")
        assert base == _short_form_filter_graph(
            hook="Hook line", subtitles_path="/tmp/x.ass", fact_cards=None)
        assert base == _short_form_filter_graph(
            hook="Hook line", subtitles_path="/tmp/x.ass", fact_cards=[])
        # The four hook pins survive untouched.
        assert r"alpha='clip(t/0.25,0,1)*clip((3-t)/0.4,0,1)'" in base
        assert r"enable='between(t,0,3.05)'" in base

    def test_cards_sit_after_hook_and_before_end_card(self):
        from engine.video import _short_form_filter_graph
        g = _short_form_filter_graph(
            hook="Hook line", fact_cards=self.CARDS, end_card=True,
            end_card_duration=3.0, total_duration=35.0,
            end_card_image_input_label="[4:v]", subtitles_path="/tmp/x.ass",
        )
        assert "Backlog value" in g and "Megawatts" in g
        assert "under the hook" not in g          # < 3.5 s
        assert "in the end card" not in g         # 33 + 4 > 32
        assert g.index("Hook") < g.index("Backlog") < g.index("fade=t=in")
        assert g.index("fade=t=in") < g.index("subtitles=")
        assert g.endswith("[v]") and g.count("[v]") == 1
        assert "[hooked]" in g

    def test_hook_and_cards_without_subs_or_end_card_terminates_once(self):
        from engine.video import _short_form_filter_graph
        g = _short_form_filter_graph(hook="Hook line", fact_cards=self.CARDS)
        assert g.endswith("[v]") and g.count("[v]") == 1
        assert "[hooked]" in g and "null[v]" in g
        g2 = _short_form_filter_graph(fact_cards=self.CARDS)
        assert g2.endswith("[v]") and g2.count("[v]") == 1

    def test_vertical_geometry(self):
        from engine.video import _short_form_fact_cards_stage
        frag, label = _short_form_fact_cards_stage("[x]", self.CARDS)
        assert label == "[sfact2]"   # three usable cards without an end card
        assert "fontsize=96:fontcolor=0x00D4FF" in frag
        assert "x=(w-text_w)/2:y=h*0.62-70" in frag
        assert "y=h*0.62+60" in frag and "fontsize=40:fontcolor=white" in frag
        assert "y=h-300" not in frag   # not the long-form corner geometry

    def test_cmd_and_builder_thread_the_cards(self, tmp_path, monkeypatch):
        from engine import video
        cmd = video._short_form_cmd("a.mp3", "bg.jpg", "brand.png", "out.mp4",
                                    fact_cards=self.CARDS)
        graph = cmd[cmd.index("-filter_complex") + 1]
        assert "Backlog value" in graph
        captured = {}
        monkeypatch.setattr(video, "_run_ffmpeg",
                            lambda c, **k: captured.setdefault("cmd", c))
        audio = tmp_path / "a.mp3"; audio.write_bytes(b"x")
        cover = tmp_path / "c.jpg"; cover.write_bytes(b"x")
        video.build_short_video(audio, cover, tmp_path / "s.mp4",
                                duration=35.0, fact_cards=self.CARDS)
        g = captured["cmd"][captured["cmd"].index("-filter_complex") + 1]
        assert "Backlog value" in g


class TestShortWiring:
    def test_run_show_en_only_gate_and_metric(self):
        src = (ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "fact_cards_for_window(" in src
        assert "fact_cards=_short_fact_cards" in src
        assert 'result["shorts_fact_cards_rendered"]' in src
        block = src[src.index("Shorts fact cards + punch frame"):
                    src.index("fact_cards=_short_fact_cards")]
        assert '_yt_channel == "en"' in block
        assert '"shorts_fact_cards"' in block
        # The dub renderers are the control arm: untouched.
        for mod in ("ru_dub", "lang_dub"):
            dub = (ROOT / "engine" / f"{mod}.py").read_text(encoding="utf-8")
            assert "fact_cards_for_window" not in dub
            assert "punch_text=" not in dub

    def test_metrics_on_the_allowlist(self):
        src = (ROOT / "engine" / "pipeline.py").read_text(encoding="utf-8")
        assert 'metrics.record("shorts_fact_cards_rendered"' in src
        assert 'metrics.record("shorts_punch_frame_rendered"' in src

    def test_knobs_default_off_and_arm_shows_on(self):
        from engine.config import YouTubeConfig
        cfg = YouTubeConfig()
        assert cfg.shorts_fact_cards is False and cfg.shorts_punch_frame is False
        defaults = yaml.safe_load((ROOT / "shows" / "_defaults.yaml").read_text(encoding="utf-8"))
        assert defaults["youtube"]["shorts_fact_cards"] is False
        assert defaults["youtube"]["shorts_punch_frame"] is False
        for slug in ("tesla", "spacex", "fascinating_frontiers"):
            data = yaml.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))
            assert data["youtube"]["shorts_fact_cards"] is True, slug
            assert data["youtube"]["shorts_punch_frame"] is True, slug
        for slug in ("models_agents", "omni_view", "finansy_prosto"):
            data = yaml.safe_load((ROOT / "shows" / f"{slug}.yaml").read_text(encoding="utf-8"))
            yt = data.get("youtube") or {}
            assert "shorts_fact_cards" not in yt and "shorts_punch_frame" not in yt, slug
