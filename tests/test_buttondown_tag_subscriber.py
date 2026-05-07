"""Tests for the Buttondown subscriber tagging script.

The script lives under ``scripts/`` rather than ``engine/`` so we
import it via the path. We exercise the pure helpers — the HTTP
calls themselves are not tested here (they're guarded by a
``BUTTONDOWN_API_KEY`` env var the test suite never has).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import buttondown_tag_subscriber as bts  # noqa: E402  (path manipulation needed)


# ---------------------------------------------------------------------------
# Tag validity
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tag", [
    "Tesla Shorts Time",
    "Privet Russian",
    "Finansy Prosto",
    "ABC123",
    "a",                     # one char, valid
    "1",                     # one digit, valid
    "Tesla — 2026",          # mixed but has ASCII letters
])
def test_valid_buttondown_tag_accepts_with_ascii_alphanum(tag):
    assert bts._is_valid_buttondown_tag(tag) is True


@pytest.mark.parametrize("tag", [
    "Привет, Русский!",      # all Cyrillic + punctuation
    "Финансы Просто",        # all Cyrillic
    "!!!",                   # punctuation only
    "—",                     # em-dash only
    "",                      # empty
])
def test_valid_buttondown_tag_rejects_no_ascii_alphanum(tag):
    assert bts._is_valid_buttondown_tag(tag) is False


# ---------------------------------------------------------------------------
# YAML tag loader
# ---------------------------------------------------------------------------

def test_load_show_tags_returns_only_ascii_friendly():
    """All shipped show tags should pass Buttondown's validator."""
    tags = bts._load_show_tags()
    assert tags, "expected at least one show tag"
    invalid = {
        slug: tag for slug, tag in tags.items()
        if not bts._is_valid_buttondown_tag(tag)
    }
    assert not invalid, f"these tags would be rejected by Buttondown: {invalid}"


def test_load_show_tags_includes_russian_shows_with_ascii():
    tags = bts._load_show_tags()
    # Russian shows have ASCII transliterations — verify they're set.
    assert tags.get("privet_russian") == "Privet Russian"
    assert tags.get("finansy_prosto") == "Finansy Prosto"


# ---------------------------------------------------------------------------
# Bulk roster (--list-all)
# ---------------------------------------------------------------------------


def _make_subscriber(email, tags, sub_type="regular"):
    return {
        "id": f"sub_{email.replace('@', '_at_')}",
        "email_address": email,
        "type": sub_type,
        "tags": tags,
    }


class TestPrintRoster:
    """``_print_roster`` formats subscribers + tags for terminal display.

    These tests pin the human-readable shape so a future "polish the
    output" change doesn't accidentally drop a column or reorder rows
    in ways that break the operator's mental model. CSV mode is also
    pinned because it's the spreadsheet-import path."""

    def test_table_header_and_rows(self, capsys):
        subs = [
            _make_subscriber("alice@example.com", ["Tesla Shorts Time"]),
            _make_subscriber("bob@example.com", ["Tesla Shorts Time", "Omni View"]),
        ]
        bts._print_roster(subs)
        out = capsys.readouterr().out
        assert "EMAIL" in out and "TYPE" in out and "TAGS" in out
        assert "alice@example.com" in out
        assert "bob@example.com" in out
        # Tags are sorted alphabetically per row.
        assert "Omni View, Tesla Shorts Time" in out
        assert "Total: 2 subscriber(s)." in out

    def test_alphabetical_email_sort(self, capsys):
        subs = [
            _make_subscriber("zebra@example.com", []),
            _make_subscriber("apple@example.com", []),
            _make_subscriber("middle@example.com", []),
        ]
        bts._print_roster(subs)
        out = capsys.readouterr().out
        # Emails appear in alphabetical order.
        a = out.index("apple@")
        m = out.index("middle@")
        z = out.index("zebra@")
        assert a < m < z

    def test_filter_tag_only_shows_matching_subscribers(self, capsys):
        subs = [
            _make_subscriber("a@example.com", ["Tesla Shorts Time"]),
            _make_subscriber("b@example.com", ["Omni View"]),
            _make_subscriber("c@example.com", ["Tesla Shorts Time", "Omni View"]),
        ]
        bts._print_roster(subs, filter_tag="Tesla Shorts Time")
        out = capsys.readouterr().out
        assert "a@example.com" in out
        assert "c@example.com" in out
        assert "b@example.com" not in out
        assert "Total: 2 subscriber(s) tagged 'Tesla Shorts Time'." in out

    def test_filter_tag_with_no_matches_says_so(self, capsys):
        subs = [_make_subscriber("a@example.com", ["Tesla Shorts Time"])]
        bts._print_roster(subs, filter_tag="Nonexistent Tag")
        out = capsys.readouterr().out
        assert "No subscribers tagged 'Nonexistent Tag'." in out

    def test_csv_output_has_header_and_semicolon_separated_tags(self, capsys):
        subs = [
            _make_subscriber("a@example.com", ["Tesla Shorts Time", "Omni View"]),
        ]
        bts._print_roster(subs, csv=True)
        out = capsys.readouterr().out
        lines = out.strip().splitlines()
        assert lines[0] == "email,type,tags"
        # Tags joined with semicolon (so the row stays one CSV column).
        assert lines[1] == "a@example.com,regular,Omni View;Tesla Shorts Time"

    def test_skips_subscribers_without_email(self, capsys):
        """Defensive: Buttondown occasionally returns malformed records
        with no email_address. Skip them silently."""
        subs = [
            {"id": "sub_x", "email_address": "", "type": "regular", "tags": []},
            _make_subscriber("real@example.com", ["Tesla Shorts Time"]),
        ]
        bts._print_roster(subs)
        out = capsys.readouterr().out
        assert "real@example.com" in out
        assert "Total: 1 subscriber(s)." in out

    def test_handles_unsubscribed_type(self, capsys):
        """Buttondown keeps unsubscribed users on file with type=
        unsubscribed. They should appear in the roster so the operator
        can see who churned, but with their (empty) tag list."""
        subs = [
            _make_subscriber("gone@example.com", [], sub_type="unsubscribed"),
        ]
        bts._print_roster(subs)
        out = capsys.readouterr().out
        assert "gone@example.com" in out
        assert "unsubscribed" in out
        assert "(none)" in out


# ---------------------------------------------------------------------------
# CLI flag wiring (--list-all)
# ---------------------------------------------------------------------------


class TestListAllFlag:

    def test_list_all_skips_email_argument(self, monkeypatch, capsys):
        """--list-all does not take a positional email — the script must
        accept it being omitted."""
        monkeypatch.setenv("BUTTONDOWN_API_KEY", "fake-key")
        monkeypatch.setattr(
            bts, "_list_all_subscribers",
            lambda key: [_make_subscriber("a@example.com", ["Tesla Shorts Time"])],
        )
        rc = bts.main(["--list-all"])
        assert rc == 0
        assert "a@example.com" in capsys.readouterr().out

    def test_list_all_with_show_filter(self, monkeypatch, capsys):
        monkeypatch.setenv("BUTTONDOWN_API_KEY", "fake-key")
        monkeypatch.setattr(
            bts, "_list_all_subscribers",
            lambda key: [
                _make_subscriber("a@example.com", ["Tesla Shorts Time"]),
                _make_subscriber("b@example.com", ["Omni View"]),
            ],
        )
        rc = bts.main(["--list-all", "--show", "tesla"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "a@example.com" in out
        assert "b@example.com" not in out

    def test_list_all_rejects_email_argument(self, monkeypatch, capsys):
        monkeypatch.setenv("BUTTONDOWN_API_KEY", "fake-key")
        rc = bts.main(["user@example.com", "--list-all"])
        assert rc == 2
        err = capsys.readouterr().err
        assert "--list-all takes no email argument" in err

    def test_list_all_rejects_multiple_show_filters(self, monkeypatch, capsys):
        monkeypatch.setenv("BUTTONDOWN_API_KEY", "fake-key")
        rc = bts.main(["--list-all", "--show", "tesla", "--show", "omni_view"])
        assert rc == 2
        err = capsys.readouterr().err
        assert "exactly one show slug" in err

    def test_list_all_rejects_unknown_show(self, monkeypatch, capsys):
        monkeypatch.setenv("BUTTONDOWN_API_KEY", "fake-key")
        rc = bts.main(["--list-all", "--show", "nosuchshow"])
        assert rc == 2
        assert "Unknown show slug" in capsys.readouterr().err

    def test_email_required_when_not_list_all(self, monkeypatch, capsys):
        """Backward-compat — running with no email and no --list-all
        must still error (not silently no-op)."""
        monkeypatch.setenv("BUTTONDOWN_API_KEY", "fake-key")
        rc = bts.main(["--show", "tesla"])
        assert rc == 2
        err = capsys.readouterr().err
        assert "subscriber email is required" in err
