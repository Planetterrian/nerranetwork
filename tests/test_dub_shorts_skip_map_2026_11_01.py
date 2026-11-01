"""Nov 1 2026: the dub hook Shorts skip the translated map too.

The Oct 30 English splice (engine/short_furniture.py) left the @NerraRU and
@NerraFR hook Shorts reading the translated map, ~10 s of a ~32 s Short
listing OTHER stories. The dub map is found by POSITION: the translation keeps
the English script's lines one for one, so the dub line at the English map's
index is the map, and its edges are located in the dub track's own Whisper
words by their letters (Cyrillic transliterated, accents folded, digits
dropped). Every refusal renders the Short from the dub track as before.

Measured before shipping on the dub openings of Oct 15-Nov 1 (faster-whisper,
the production function, on the published RU/FR tracks of SpaceX, Tesla, FF,
MIT, M&A and FPD): 40 of 41 RU and 57 of 58 FR mapped openings cut (median
10.5 / 10.3 s), 0 cuts on the 73 openings without an English map; the two
misses are openings where Whisper wrote no words over the map. On 65 real
splices, Whisper of the spliced source heard no map text (the one word
flagged in 65 was the next story's own).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "dub_openings_2026_11_01.json"
SPACEX = ROOT / "digests" / "spacex"
TST = ROOT / "digests" / "tesla_shorts_time"

_SHOW_DIR = {"spacex": "spacex", "tesla_shorts_time": "tesla_shorts_time",
             "models_agents": "models_agents"}


def _opening(key: str) -> dict:
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return doc["openings"][key]


def _scripts(key: str):
    from engine.short_furniture import dub_scripts_for
    from engine.utils import strip_speech_tags

    m = re.match(r"(.+)_ep(\d+)_(ru|fr)$", key)
    show, ep, lang = m.group(1), int(m.group(2)), m.group(3)
    tts, dub = dub_scripts_for(ROOT / "digests" / _SHOW_DIR[show], ep, lang)
    return (strip_speech_tags(tts.read_text(encoding="utf-8")),
            strip_speech_tags(dub.read_text(encoding="utf-8")))


def _committed_dubs(lang: str, since: str = "20261001"):
    """``(date, english_tts_text, dub_text)`` for every committed dub script."""
    from engine.utils import strip_speech_tags

    for dub in sorted((ROOT / "digests").glob(f"*/*_2026*.{lang}.txt")):
        m = re.search(r"_(\d{8})\.", dub.name)
        if not m or m.group(1) < since:
            continue
        tts = dub.with_name(dub.name[: -len(f".{lang}.txt")] + "_tts.txt")
        if not tts.exists():
            continue
        yield (m.group(1), dub.name,
               strip_speech_tags(tts.read_text(encoding="utf-8")),
               strip_speech_tags(dub.read_text(encoding="utf-8")))


_TS = re.compile(r"(\d+):(\d+):(\d+)\.(\d+)\s+-->\s+(\d+):(\d+):(\d+)\.(\d+)")


def _vtt_as_words(path: Path) -> dict:
    """A committed segment-level VTT as a word transcript (each cue's words
    spread over the cue by letters). Only the order and rough place of words
    matter to the locator's refusals."""
    segs, cur = [], None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _TS.match(line.strip())
        if m:
            g = [int(x) for x in m.groups()]
            cur = [g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000,
                   g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000, []]
            segs.append(cur)
        elif line.strip() and cur is not None and line.strip() != "WEBVTT":
            cur[2].append(line.strip())
    out = []
    for s, e, txt in segs:
        toks = " ".join(txt).replace("&amp;", "&").split()
        total = sum(len(t) for t in toks) or 1
        t, words = s, []
        for tok in toks:
            d = (e - s) * len(tok) / total
            words.append({"word": tok, "start": round(t, 3), "end": round(t + d * 0.9, 3)})
            t += d
        if words:
            out.append({"start": s, "end": e, "words": words})
    return {"segments": out}


class TestTheDubKeepsTheLines:
    """The positional locator rests on one fact: the translation keeps the
    English script's lines one for one."""

    @pytest.mark.parametrize("lang", ["ru", "fr"])
    def test_every_mapped_dub_has_its_english_line_count(self, lang):
        from engine import story_breaks as sb
        from engine.short_furniture import map_line_range

        mapped = same = 0
        for date, name, en, dub in _committed_dubs(lang, since="20261020"):
            if map_line_range(en) is None:
                continue
            mapped += 1
            same += len(sb.script_lines(en)) == len(sb.script_lines(dub))
        assert mapped >= 40
        assert same == mapped

    def test_the_dub_map_line_is_the_translated_map(self):
        from engine import story_breaks as sb
        from engine.short_furniture import dub_map_line_range

        en, ru = _scripts("spacex_ep144_ru")
        first, after = dub_map_line_range(en, ru)
        line = sb.script_lines(ru)[first]
        assert line.startswith("Дальше — Фалкон девять с Ванденберга")
        assert sb.script_lines(ru)[after].startswith("Илон Маск написал")

    def test_a_different_line_count_is_no_map(self):
        from engine.short_furniture import dub_map_line_range

        en, ru = _scripts("spacex_ep144_ru")
        assert dub_map_line_range(en, ru.replace("\n\n", " ", 1)) is None


class TestFindingTheMapInTheDub:
    @pytest.mark.parametrize("key,lo,hi,story_word", [
        ("spacex_ep144_ru", 12.0, 13.5, "Илон"),
        ("spacex_ep144_fr", 10.0, 11.7, "Elon"),
        ("tesla_shorts_time_ep650_ru", 12.5, 14.0, "По"),
        ("tesla_shorts_time_ep650_fr", 12.0, 13.5, "La"),
    ])
    def test_the_cut_runs_from_the_identity_line_to_the_story(self, key, lo, hi, story_word):
        from engine.short_furniture import dub_map_cut, splice_transcript

        en, dub = _scripts(key)
        tx = _opening(key)
        cut = dub_map_cut(en, dub, tx)
        assert cut is not None
        a, b = cut
        assert lo <= a <= hi and 7.0 <= b - a <= 16.0
        words = [w for s in tx["segments"] for w in s["words"]]
        first_after = next(w for w in words if w["start"] >= b)
        assert first_after["word"].startswith(story_word)
        last_before = [w for w in words if w["end"] <= a][-1]
        assert last_before["word"].rstrip(".,").isdigit()  # "... выпуск 144."
        spliced = splice_transcript(tx, a, b)
        starts = [w["start"] for s in spliced["segments"] for w in s["words"]]
        assert starts == sorted(starts)

    def test_a_number_written_in_digits_does_not_move_the_edge(self):
        """SpaceX Ep137 RU: the next line opens "Пятнадцатый полёт", Whisper
        wrote "15 -й полёт"; the digits carry no letters, and the edge must
        still fall before them, not after the map's last word."""
        from engine.short_furniture import dub_map_cut

        en, ru = _scripts("spacex_ep137_ru")
        tx = _opening("spacex_ep137_ru")
        a, b = dub_map_cut(en, ru, tx)
        words = [w for s in tx["segments"] for w in s["words"]]
        assert [w for w in words if w["end"] <= b][-1]["word"] == "разбор."
        assert next(w for w in words if w["start"] >= b)["word"] == "15"

    @pytest.mark.parametrize("key", ["spacex_ep148_ru", "models_agents_ep220_fr"])
    def test_whisper_hearing_no_map_is_no_cut(self, key):
        """Both openings have a map in the script; Whisper wrote nothing over
        it (a 17-18 s hole in the words while the audio speaks). No position
        reads as the map's opening, so nothing is cut — never a guessed edge
        that could cut the hook's story."""
        from engine.short_furniture import dub_map_cut

        en, dub = _scripts(key)
        assert dub_map_cut(en, dub, _opening(key)) is None

    def test_edges_heard_but_the_body_not_the_map_is_no_cut(self):
        """Both edges found, the words between them something else (Whisper
        looping, a different take): the span check refuses."""
        import copy

        from engine import story_breaks as sb
        from engine.short_furniture import dub_map_cut, dub_map_line_range

        en, ru = _scripts("spacex_ep144_ru")
        tx = copy.deepcopy(_opening("spacex_ep144_ru"))
        assert dub_map_cut(en, ru, tx) is not None
        first, _after = dub_map_line_range(en, ru)
        map_words = len(sb.script_lines(ru)[first].split())
        words = [w for s in tx["segments"] for w in s["words"]]
        start = next(i for i, w in enumerate(words) if w["word"] == "Дальше")
        filler = ["больше", "чем", "все", "остальные", "операторы", "на", "Земле"]
        for j, w in enumerate(words[start + 8:start + map_words - 2]):
            w["word"] = filler[j % len(filler)]
        assert dub_map_cut(en, ru, tx) is None

    @pytest.mark.parametrize("lang", ["ru", "fr"])
    def test_hit_rate_on_the_committed_transcripts(self, lang):
        """Every committed RU/FR VTT since Oct 20 (segment-level, words spread
        over each cue): most mapped openings are found. Measured: RU 39/41,
        FR 57/58."""
        from engine.short_furniture import dub_map_cut, map_line_range

        mapped = found = 0
        for date, name, en, dub in _committed_dubs(lang, since="20261020"):
            vtt = (ROOT / "digests").glob(f"*/{name[:-4]}_transcript.vtt")
            vtt = next(vtt, None)
            if vtt is None or map_line_range(en) is None:
                continue
            mapped += 1
            cut = dub_map_cut(en, dub, _vtt_as_words(vtt))
            if cut:
                found += 1
                assert 1.0 <= cut[1] - cut[0] <= 20.0
        assert mapped >= 40
        assert found >= mapped * 0.9

    @pytest.mark.parametrize("lang", ["ru", "fr"])
    def test_no_cut_before_maps_existed(self, lang):
        """Every committed RU/FR opening before Oct 20 (maps began Oct 20):
        no map, no cut."""
        from engine.short_furniture import dub_map_cut

        checked = 0
        for date, name, en, dub in _committed_dubs(lang, since="20260601"):
            if date >= "20261020":
                continue
            vtt = next((ROOT / "digests").glob(f"*/{name[:-4]}_transcript.vtt"), None)
            if vtt is None:
                continue
            checked += 1
            assert dub_map_cut(en, dub, _vtt_as_words(vtt)) is None, name
        assert checked >= 60

    @pytest.mark.parametrize("lang", ["ru", "fr"])
    def test_no_cut_on_a_mapless_episode_after_oct_20(self, lang):
        from engine.short_furniture import dub_map_cut, map_line_range

        checked = 0
        for date, name, en, dub in _committed_dubs(lang, since="20261020"):
            if map_line_range(en) is not None:
                continue
            vtt = next((ROOT / "digests").glob(f"*/{name[:-4]}_transcript.vtt"), None)
            if vtt is None:
                continue
            checked += 1
            assert dub_map_cut(en, dub, _vtt_as_words(vtt)) is None, name
        assert checked >= 10

    @pytest.mark.parametrize("word,expected", [
        ("Дальше,", "dalshe"), ("épisode", "episode"), ("144.", ""),
        ("Фалкон", "falkon"), ("l'intelligence", "lintelligence"), ("-летняя", "letnyaya"),
    ])
    def test_the_dub_letters(self, word, expected):
        from engine.short_furniture import dub_norm

        assert dub_norm(word) == expected


class TestTheSpliceNeverBlocksARender:
    def test_no_scripts_is_none(self, tmp_path):
        from engine.short_furniture import spliced_dub_short_source

        tj = tmp_path / "t.json"
        tj.write_text(json.dumps(_opening("spacex_ep144_ru")), encoding="utf-8")
        assert spliced_dub_short_source(tmp_path / "a.mp3", tj, tmp_path, 144, "ru",
                                         tmp_path / "w") is None

    def test_unreadable_transcript_is_none(self, tmp_path):
        from engine.short_furniture import spliced_dub_short_source

        tj = tmp_path / "t.json"
        tj.write_text("{not json", encoding="utf-8")
        assert spliced_dub_short_source(tmp_path / "a.mp3", tj, SPACEX, 144, "ru",
                                        tmp_path / "w") is None

    def test_a_failing_ffmpeg_is_none(self, tmp_path, monkeypatch):
        from engine import short_furniture as sf

        tj = tmp_path / "t.json"
        tj.write_text(json.dumps(_opening("spacex_ep144_ru")), encoding="utf-8")

        def boom(*a, **k):
            raise subprocess.CalledProcessError(1, "ffmpeg")

        monkeypatch.setattr(subprocess, "run", boom)
        assert sf.spliced_dub_short_source(tmp_path / "missing.mp3", tj, SPACEX, 144,
                                           "ru", tmp_path / "w") is None

    def test_a_cut_that_raises_is_none(self, monkeypatch):
        from engine import short_furniture as sf

        def boom(*a, **k):
            raise RuntimeError("x")

        monkeypatch.setattr(sf, "dub_map_line_range", boom)
        en, ru = _scripts("spacex_ep144_ru")
        assert sf.dub_map_cut(en, ru, _opening("spacex_ep144_ru")) is None

    def test_a_real_splice_shortens_the_track_by_the_cut(self, tmp_path):
        """End to end on a synthetic track carrying the fixture's timings:
        the spliced audio is shorter by the cut and the spliced transcript
        opens the hook's story where the map was."""
        if not shutil.which("ffmpeg"):
            pytest.skip("ffmpeg not installed")
        from engine.short_furniture import spliced_dub_short_source

        src = tmp_path / "ru.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                        "anoisesrc=d=40:a=0.05", str(src)], check=True)
        tj = tmp_path / "ru_transcript.json"
        tj.write_text(json.dumps(_opening("spacex_ep144_ru"), ensure_ascii=False),
                      encoding="utf-8")
        out = spliced_dub_short_source(src, tj, SPACEX, 144, "ru", tmp_path / "w")
        assert out is not None
        audio, tx, cut_s = out
        assert 10.0 <= cut_s <= 16.0
        dur = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
             "csv=p=0", str(audio)], capture_output=True, text=True, check=True).stdout)
        assert dur == pytest.approx(40.0 - cut_s, abs=0.1)
        words = [w["word"] for s in json.loads(tx.read_text(encoding="utf-8"))["segments"]
                 for w in s["words"]]
        i = words.index("144.")
        assert words[i + 1] == "Илон"
        assert "Сванденберга," not in words

    def test_snapping_to_silence_keeps_the_cut_inside_its_bounds(self):
        from engine.short_furniture import snap_cut_to_silence

        # Whisper's edge 29.98 s; the audio's pause 30.11-30.79 s.
        assert snap_cut_to_silence((13.5, 29.98), [(12.9, 14.1), (30.11, 30.79)]) == (13.5, 30.45)
        # No silence near an edge: it stays.
        assert snap_cut_to_silence((13.5, 29.98), []) == (13.5, 29.98)
        # A snap that would leave a cut outside the 1-20 s band is refused.
        assert snap_cut_to_silence((10.0, 10.9), [(10.4, 10.6)]) == (10.0, 10.9)


class TestWiring:
    def _src(self, name: str) -> str:
        return (ROOT / "engine" / f"{name}.py").read_text(encoding="utf-8")

    @pytest.mark.parametrize("name", ["ru_dub", "lang_dub"])
    def test_both_dub_paths_render_the_hook_short_from_the_dub_source(self, name):
        src = self._src(name)
        loop = src[src.index("for short_idx, (start_offset, opening_text,"):]
        assert "dub_short_source(" in loop
        after = loop[loop.index("dub_short_source("):]
        after = after[after.index(")") + 1:]
        # Inside the loop every Short reads its own source, never the track.
        assert "_src_audio, cover, short_mp4" in after
        assert "_src_tx, ass_candidate" in after or "_src_tx, cand" in after
        assert "end_on_sentence(\n                        _src_words" in after
        assert "map_cut_s=_map_cut_s" in after
        assert "build_short_video(\n                        audio," not in after

    @pytest.mark.parametrize("name", ["ru_dub", "lang_dub"])
    def test_the_long_form_still_renders_from_the_dub_track(self, name):
        src = self._src(name)
        assert "build_long_form_video(\n                    audio, cover, long_mp4" in src

    def _yt(self, flag):
        return SimpleNamespace(shorts_skip_map=flag)

    def test_only_the_hook_short_with_the_flag_on_is_spliced(self, tmp_path, monkeypatch):
        from engine import short_furniture as sf

        calls = []

        def fake(*a, **k):
            calls.append(a)
            return tmp_path / "s.flac", tmp_path / "s.json", 9.5

        monkeypatch.setattr(sf, "spliced_dub_short_source", fake)
        src = (Path("a.mp3"), Path("t.json"), [{"word": "x"}])
        # Any Short but the first, any window but the hook: the dub track.
        assert sf.dub_short_source(self._yt(True), 1, "qualified", *src, tmp_path, 1,
                                   "ru", tmp_path, {}) == src
        assert sf.dub_short_source(self._yt(True), 0, "legacy_fallback", *src, tmp_path,
                                   1, "ru", tmp_path, {}) == src
        # The flag off: the dub track.
        assert sf.dub_short_source(self._yt(False), 0, "hook_open", *src, tmp_path, 1,
                                   "fr", tmp_path, {}) == src
        # No transcript: the dub track.
        assert sf.dub_short_source(self._yt(True), 0, "hook_open", Path("a.mp3"), None,
                                   [], tmp_path, 1, "ru", tmp_path, {}) == \
            (Path("a.mp3"), None, [])
        assert calls == []
        # The hook Short with the flag on: the spliced source, metric recorded.
        result: dict = {}
        out = sf.dub_short_source(self._yt(True), 0, "hook_open", *src, tmp_path, 1,
                                  "ru", tmp_path, result)
        assert out[0] == tmp_path / "s.flac" and out[1] == tmp_path / "s.json"
        assert result["shorts_map_cut_s"] == 9.5
        assert len(calls) == 1

    def test_a_failed_splice_is_the_dub_track(self, tmp_path, monkeypatch):
        from engine import short_furniture as sf

        monkeypatch.setattr(sf, "spliced_dub_short_source", lambda *a, **k: None)
        src = (Path("a.mp3"), Path("t.json"), [])
        result: dict = {}
        assert sf.dub_short_source(self._yt(True), 0, "hook_open", *src, tmp_path, 1,
                                   "ru", tmp_path, result) == src
        assert "shorts_map_cut_s" not in result

        def boom(*a, **k):
            raise RuntimeError("x")

        monkeypatch.setattr(sf, "spliced_dub_short_source", boom)
        assert sf.dub_short_source(self._yt(True), 0, "hook_open", *src, tmp_path, 1,
                                   "ru", tmp_path, result) == src

    def test_the_dub_shows_inherit_the_switch(self):
        from engine.config import load_config

        for slug in ("spacex", "tesla", "fascinating_frontiers"):
            cfg = load_config(ROOT / "shows" / f"{slug}.yaml")
            assert cfg.youtube.ru_dub_enabled is True
            assert "fr" in cfg.youtube.dub_languages
            assert cfg.youtube.shorts_skip_map is True, slug

    def test_the_index_row_records_the_cut_only_when_set(self, tmp_path):
        from engine.youtube_index import record_video

        idx = tmp_path / "youtube_videos.ru.json"
        assert record_video(video_id="a", show_slug="spacex", episode=1, kind="short",
                            channel="ru", window="hook_open", map_cut_s=10.456,
                            index_path=idx)
        assert record_video(video_id="b", show_slug="spacex", episode=1, kind="short",
                            channel="ru", window="qualified", index_path=idx)
        rows = {r["video_id"]: r for r in json.loads(idx.read_text())["videos"]}
        assert rows["a"]["map_cut_s"] == 10.46
        assert "map_cut_s" not in rows["b"]
