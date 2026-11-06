"""A line the guest marks on the edit's transcript is cut where it is in the
room (Nov 6 2026).

The review page shows the transcript of the EDIT, so the times a click
carries are the edit's; ``apply_windows`` cuts on the room's clock. Blaine
Mathieu marked two lines at 26:59 and 27:06 of his episode, which sit at
29:18 of the room, and the windows as stored would have cut a different
passage of his. The Worker now tags such a window ``clock: "edit"`` and the
assembler moves it onto the room's clock from the clock of the edit the guest
reviewed, writing the result back before anything is cut.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "voices"))

from edit_transcript import (  # noqa: E402
    apply_windows, normalise_windows, windows_marked_on_the_edit, windows_to_room_clock,
)

# Blaine's edit: a 45.6 s introduction (with its gap), then the room from 46.6.
CLOCK = [[46.6, 2087.0, 45.6], [2165.5, 2173.2, 2086.0]]


def test_an_edit_window_lands_where_the_line_is_in_the_room():
    moved = windows_to_room_clock(
        [{"start_sec": 1619, "end_sec": 1626, "line": "[26:59] Blaine: So any emails", "clock": "edit"}],
        CLOCK)
    assert len(moved) == 1
    assert moved[0]["start_sec"] == pytest.approx(1619 - 45.6 + 46.6)
    assert moved[0]["end_sec"] == pytest.approx(1626 - 45.6 + 46.6)
    assert moved[0]["clock"] == "room"
    assert not windows_marked_on_the_edit(moved)


def test_a_room_window_passes_through():
    w = {"start_sec": 100, "end_sec": 110, "line": "x"}
    assert windows_to_room_clock([w], CLOCK) == [w]
    assert not windows_marked_on_the_edit([w])


def test_a_window_across_a_seam_becomes_one_per_stretch_and_narration_is_skipped():
    moved = windows_to_room_clock(
        [{"start_sec": 2080, "end_sec": 2090, "line": "end", "clock": "edit"}], CLOCK)
    assert [(w["start_sec"], w["end_sec"]) for w in moved] == [
        (pytest.approx(2081.0), pytest.approx(2087.0)),
        (pytest.approx(2165.5), pytest.approx(2169.5)),
    ]
    # A window wholly on the introduction has no room time to cut.
    assert windows_to_room_clock(
        [{"start_sec": 5, "end_sec": 20, "line": "intro", "clock": "edit"}], CLOCK) == []


def test_a_scaled_stretch_is_inverted():
    moved = windows_to_room_clock(
        [{"start_sec": 15, "end_sec": 20, "line": "x", "clock": "edit"}], [[100, 120, 10, 0.5]])
    assert (moved[0]["start_sec"], moved[0]["end_sec"]) == (110.0, 120.0)


def test_the_moved_window_cuts_the_room_passage_not_the_edit_time():
    cuts = [{"from": "mix:clean", "start": 46.6, "end": 2087.0}]
    moved = windows_to_room_clock(
        [{"start_sec": 1619, "end_sec": 1626, "line": "l", "clock": "edit"}], CLOCK)
    out, applied = apply_windows(cuts, moved)
    assert applied == 1
    kept = [(c["start"], c["end"]) for c in out if c.get("from")]
    assert kept[0][1] == pytest.approx(1620.0 - 0.35)
    assert kept[1][0] == pytest.approx(1627.0 + 0.35)
    assert normalise_windows(moved)[0]["start_sec"] == pytest.approx(1620.0)


def test_the_assembler_moves_windows_before_it_cuts_and_writes_them_back(monkeypatch):
    import assemble_edit

    writes = []
    monkeypatch.setattr(assemble_edit, "sb_update", lambda t, q, body: writes.append((t, q, body)))
    pkg = {"id": "p1", "guest_redaction_windows": [
        {"start_sec": 1619, "end_sec": 1626, "line": "l", "clock": "edit"}]}
    run = {"grok_session_log": {"tracks": {"edit": {"clock": CLOCK}}}}
    assemble_edit._windows_onto_the_room(pkg, run)
    assert writes and writes[0][0] == "editorial_packages"
    assert pkg["guest_redaction_windows"][0]["clock"] == "room"
    assert pkg["guest_redaction_windows"][0]["start_sec"] == pytest.approx(1620.0)
    # Done once: the next build reads room windows and leaves them alone.
    writes.clear()
    assemble_edit._windows_onto_the_room(pkg, run)
    assert writes == []


def test_the_assembler_refuses_edit_windows_with_no_clock(monkeypatch):
    import assemble_edit

    monkeypatch.setattr(assemble_edit, "sb_update", lambda *a: None)
    pkg = {"id": "p1", "guest_redaction_windows": [
        {"start_sec": 1, "end_sec": 2, "line": "l", "clock": "edit"}]}
    with pytest.raises(SystemExit):
        assemble_edit._windows_onto_the_room(pkg, {"grok_session_log": {}})


def test_the_worker_tags_windows_marked_on_the_edit():
    src = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")
    assert 'clock: "edit"' in src
    assert "_windows_onto_the_room" in (ROOT / "pipelines" / "voices" / "assemble_edit.py").read_text()
