"""Piper Martz's review note (Oct 24 2026): "the company name Aampe is
pronounced amp, not am-pee". Mira said it wrong in the introduction, and the
close read her site as two invented words because the script had a stray
space in it. The script keeps the real spelling (the transcript of the edit is
read from it); what Mira is asked to say goes through a lexicon first."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))
sys.path.insert(0, str(ROOT))

import narrate  # noqa: E402


def test_the_shared_lexicon_says_aampe_as_amp():
    words = narrate.lexicon({})
    assert words["Aampe"] == "Amp"
    assert not any(k.startswith("_") for k in words)


def test_spoken_replaces_whole_words_only():
    w = {"Aampe": "Amp"}
    assert narrate.spoken("stacks at Aampe before", w) == "stacks at Amp before"
    assert narrate.spoken("Aampe's agents", w) == "Amp's agents"
    assert narrate.spoken("Aampeish", w) == "Aampeish"
    assert narrate.spoken("see aampe.io or x.Aampe", w) == "see aampe.io or x.Aampe"
    assert narrate.spoken("Aampe.io, at Aampe.", w) == "Aampe.io, at Amp."


def test_a_specs_own_pronunciation_wins_and_longest_goes_first():
    spec = {"pronunciations": {"tablestakesmedia.com": "table stakes media dot com",
                               "Aampe": "Ahmp"}}
    w = narrate.lexicon(spec)
    assert w["Aampe"] == "Ahmp"
    assert narrate.spoken("her work at tablestakesmedia.com.", w) == \
        "her work at table stakes media dot com."


def test_mira_is_asked_to_say_it_right_but_the_script_keeps_the_spelling(
        monkeypatch, tmp_path):
    said = []
    monkeypatch.setattr(narrate, "_record_take",
                        lambda slug, seg, n, para, voice: said.append((seg, para)) or "u")

    class _Resp:
        content = b"x"
    monkeypatch.setattr(narrate.requests, "get", lambda url, timeout=0: _Resp())
    monkeypatch.setattr(narrate, "_trim", lambda part: part)
    monkeypatch.setattr(narrate, "_take_shortfall", lambda part, text: 1.0)
    monkeypatch.setattr(narrate, "_check_not_truncated", lambda part, text: None)
    monkeypatch.setattr(narrate, "_stitch", lambda parts, out, *level: parts[0])
    monkeypatch.setattr(narrate, "r2_upload", lambda path, key: key)
    (tmp_path / "lex.json").write_text(json.dumps({"Aampe": "Amp"}))
    monkeypatch.setattr(narrate, "PRONUNCIATIONS_PATH", tmp_path / "lex.json")
    spec = {"show": "age_of_ai", "segments": [
        {"id": "lead", "text": "Not this one."},
        {"id": "intro", "text": "She ran agents at Aampe."}]}
    (tmp_path / "p.json").write_text(json.dumps(spec))
    monkeypatch.setattr(narrate, "NARRATION_DIR", tmp_path)
    monkeypatch.setenv("NARRATION_ENGINE", "agent")
    monkeypatch.setenv("NARRATION_SEGMENTS", "intro")
    out = narrate.narrate("p")
    assert said == [("intro", "She ran agents at Amp.")]
    assert list(out) == ["intro"]
    assert "Aampe" in (tmp_path / "p.json").read_text()


def test_pipers_narration_spells_it_right_and_her_edit_reads_from_it():
    spec = json.loads((ROOT / "pipelines/voices/narration/"
                       "piper_martz_2026_10_05_v2.json").read_text())
    text = " ".join(s["text"] for s in spec["segments"])
    assert "Aampe" in text and "tablestakesmedia.com" in text
    assert "tablesta kesmedia" not in text
    edl = json.loads((ROOT / "pipelines/voices/edl/"
                      "piper_martz_2026_10_05.json").read_text())
    assert edl["narration"] == "piper_martz_2026_10_05_v2"
