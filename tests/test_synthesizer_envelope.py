"""Tests for the JSON-envelope parser in engine.synthesizer.

The weekly synthesizer asks the LLM to return a structured envelope
(``{subject_hook, preheader, by_the_numbers, body_md, p_s}``). These
tests lock in the parser's robustness against the half-dozen ways LLMs
mis-format JSON in practice — extra prose, code fences, missing keys,
or just plain markdown.
"""

from __future__ import annotations

import datetime
import json

from engine.synthesizer import _parse_envelope, _strip_repeated_show_title


SHOW_NAME = "Tesla Shorts Time Daily"
WEEK = datetime.date(2026, 4, 30)


def _envelope_text(**overrides) -> str:
    """Build a JSON envelope as the LLM would emit it."""
    payload = {
        "subject_hook": "Cybercab production begins",
        "preheader": "Cybercab rolls off the line in Texas this week.",
        "by_the_numbers": [
            {"value": "$372", "label": "TSLA close"},
            {"value": "+20%", "label": "Berlin output"},
        ],
        "body_md": "## This Week\n\nLorem ipsum.",
        "p_s": "If you've been on the fence about FSD v14, grab the trial.",
    }
    payload.update(overrides)
    return json.dumps(payload)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_parse_envelope_happy_path():
    out = _parse_envelope(
        _envelope_text(), show_name=SHOW_NAME, week_ending=WEEK
    )
    assert out["subject_hook"] == "Cybercab production begins"
    assert "Cybercab rolls off" in out["preheader"]
    assert len(out["by_the_numbers"]) == 2
    assert out["by_the_numbers"][0] == {"value": "$372", "label": "TSLA close"}
    assert out["body_md"].startswith("## This Week")
    assert "FSD v14" in out["p_s"]


# ---------------------------------------------------------------------------
# Robustness against LLM mis-formatting
# ---------------------------------------------------------------------------

def test_parse_envelope_handles_markdown_code_fences():
    raw = "```json\n" + _envelope_text() + "\n```"
    out = _parse_envelope(raw, show_name=SHOW_NAME, week_ending=WEEK)
    assert out["subject_hook"] == "Cybercab production begins"


def test_parse_envelope_handles_extra_prose_around_json():
    raw = (
        "Sure! Here's the newsletter envelope:\n\n"
        + _envelope_text()
        + "\n\nLet me know if you'd like me to adjust anything."
    )
    out = _parse_envelope(raw, show_name=SHOW_NAME, week_ending=WEEK)
    assert "Cybercab" in out["subject_hook"]


def test_parse_envelope_falls_back_to_raw_markdown_when_no_json():
    raw = "## This week's big picture\n\nNo JSON here, just markdown."
    out = _parse_envelope(raw, show_name=SHOW_NAME, week_ending=WEEK)
    assert out["body_md"].startswith("## This week's big picture")
    # Fallback subject is non-empty so the send still goes out.
    assert out["subject_hook"] != ""
    assert out["preheader"] != ""


def test_parse_envelope_empty_input_returns_empty_envelope():
    out = _parse_envelope("", show_name=SHOW_NAME, week_ending=WEEK)
    assert out["body_md"] == ""
    assert out["subject_hook"] != ""  # fallback, not crash


def test_parse_envelope_strips_show_title_from_body():
    """If the LLM repeats the show title at the top of body_md, the
    parser drops it so the email hero isn't visually duplicated."""
    out = _parse_envelope(
        _envelope_text(
            body_md="# Tesla Shorts Time Daily\n\n## Big picture\n\nx",
        ),
        show_name=SHOW_NAME,
        week_ending=WEEK,
    )
    assert out["body_md"].startswith("## Big picture")


def test_parse_envelope_caps_subject_hook_at_60_chars():
    """The subject composer adds a suffix; we cap the hook to leave
    room for the suffix and stay within client limits."""
    out = _parse_envelope(
        _envelope_text(subject_hook="x" * 200),
        show_name=SHOW_NAME, week_ending=WEEK,
    )
    assert len(out["subject_hook"]) <= 60


def test_parse_envelope_caps_preheader_at_160_chars():
    out = _parse_envelope(
        _envelope_text(preheader="y" * 500),
        show_name=SHOW_NAME, week_ending=WEEK,
    )
    assert len(out["preheader"]) <= 160


def test_parse_envelope_caps_p_s_at_280_chars():
    out = _parse_envelope(
        _envelope_text(p_s="z" * 500),
        show_name=SHOW_NAME, week_ending=WEEK,
    )
    assert len(out["p_s"]) <= 280


def test_parse_envelope_strips_leading_p_s_label_from_p_s():
    """If the LLM adds 'P.S. —' inside the P.S. text, drop it; the
    template renders the label itself."""
    out = _parse_envelope(
        _envelope_text(p_s="P.S. — One more thing!"),
        show_name=SHOW_NAME, week_ending=WEEK,
    )
    assert out["p_s"].startswith("One more thing")


def test_parse_envelope_caps_by_the_numbers_at_3():
    out = _parse_envelope(
        _envelope_text(by_the_numbers=[
            {"value": str(i), "label": f"L{i}"} for i in range(8)
        ]),
        show_name=SHOW_NAME, week_ending=WEEK,
    )
    assert len(out["by_the_numbers"]) == 3


def test_parse_envelope_skips_malformed_stat_items():
    out = _parse_envelope(
        _envelope_text(by_the_numbers=[
            {"value": "$1", "label": ""},        # missing label
            {"value": "", "label": "Empty"},     # missing value
            "not a dict",                         # wrong type
            {"value": "ok", "label": "Real"},    # only this survives
        ]),
        show_name=SHOW_NAME, week_ending=WEEK,
    )
    assert out["by_the_numbers"] == [{"value": "ok", "label": "Real"}]


def test_parse_envelope_handles_invalid_by_the_numbers_type():
    """If the LLM returns a string instead of a list, we get an empty
    list — never a crash."""
    out = _parse_envelope(
        _envelope_text(by_the_numbers="garbage"),
        show_name=SHOW_NAME, week_ending=WEEK,
    )
    assert out["by_the_numbers"] == []


# ---------------------------------------------------------------------------
# _strip_repeated_show_title (also lives in engine.synthesizer)
# ---------------------------------------------------------------------------

def test_strip_repeated_show_title_removes_h1():
    body = "# Tesla Shorts Time Daily\n\n## Big picture"
    out = _strip_repeated_show_title(body, "Tesla Shorts Time Daily")
    assert out.startswith("## Big picture")


def test_strip_repeated_show_title_removes_bold_weekly():
    body = "**Tesla Shorts Time Daily Weekly**\n\nbody"
    out = _strip_repeated_show_title(body, "Tesla Shorts Time Daily")
    assert out.startswith("body")


def test_strip_repeated_show_title_keeps_unrelated_first_line():
    body = "## Some real heading\n\nbody"
    out = _strip_repeated_show_title(body, "Tesla")
    assert out == body


def test_strip_repeated_show_title_handles_blank_body():
    assert _strip_repeated_show_title("", "X") == ""
