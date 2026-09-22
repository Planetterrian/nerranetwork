"""Who the guest hears from (Sept 22 2026).

Patrick's instruction on Sept 21: correspondence goes out from
mira@nerranetwork.com, copied to both of his addresses, with Mira running the
process end to end. The pipeline already did that. The Worker — which owns
every piece of guest mail between the booking and the publish — did not
entirely: the guest's own review invitation, the day-four reminder and the
rebook note went to the guest and to nobody else, and its idea of "copy
Patrick" was one address rather than two.

The gap that made this visible was a different one. Meridan Zerner's episode
ran short and Sameer Ranjan's ended mid-thought, and both needed a paragraph
no template covers, so both were written by hand out of Patrick's Gmail — the
one thing the process is meant to remove. A note written at gate 1 now travels
in Mira's mail instead.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKER = (ROOT / "workers" / "voices" / "src"
          / "index.ts").read_text(encoding="utf-8")
COMMON = (ROOT / "pipelines" / "voices"
          / "common.py").read_text(encoding="utf-8")


def _tsfn(name: str, src: str = WORKER) -> str:
    start = src.index(f"function {name}(")
    return src[start:src.index("\n}\n", start) + 3]


class TestBothOfPatricksAddresses:
    def test_the_worker_has_the_same_cc_list_as_the_pipeline(self):
        assert "function operatorCc(" in WORKER
        assert 'env.OPERATOR_CC ?? "patrick@planetterrian.com"' in WORKER
        assert 'OPERATOR_CC = [a.strip() for a in (' in COMMON

    def test_it_is_the_operator_address_plus_the_extras(self):
        body = _tsfn("operatorCc")
        assert "operatorEmail(env), ...extra" in body

    def test_it_does_not_copy_the_same_person_twice(self):
        body = _tsfn("operatorCc")
        assert "seen.has(k)" in body

    def test_cc_operator_means_every_address(self):
        body = _tsfn("email")
        assert "for (const addr of operatorCc(env))" in body
        # Never copy someone on their own mail.
        assert "addr.toLowerCase() !== to.toLowerCase()" in body


class TestTheGuestMailPatrickSeesToo:
    """Guest-facing mail the Worker sends with nobody copied is mail Patrick
    finds out about from the guest's reply."""

    def _call(self, subject_fragment: str) -> str:
        at = WORKER.index(subject_fragment)
        # From the email( that precedes it to the end of that statement.
        start = WORKER.rindex("await email(env,", 0, at)
        return WORKER[start:WORKER.index(");", at)]

    def test_the_review_invitation(self):
        assert " ".join(self._call("episode is ready for you").split()).endswith("`, true")

    def test_the_day_four_reminder(self):
        assert " ".join(self._call("transcript awaits").split()).endswith("`, true")

    def test_the_rebook_note(self):
        assert " ".join(self._call("rebook your ${show.shortLabel} interview").split()).endswith("`, true")

    def test_no_guest_mail_is_sent_with_nobody_copied(self):
        # Every email(env, <a guest address>, ...) either copies the operator
        # or is itself addressed to him.
        for match in re.finditer(r"await email\(env, (\w[\w\[\].?]*)", WORKER):
            target = match.group(1)
            if "operatorEmail" in target:
                continue
            stmt = WORKER[match.start():WORKER.index(");", match.start())]
            flat = " ".join(stmt.split())
            assert flat.endswith(", true") or ", true," in flat, \
                f"guest mail to {target} copies nobody:\n{stmt[:200]}"


class TestAWordFromPatrick:
    def test_gate_one_can_say_something_to_the_guest(self):
        assert 'const note = String(body.note_to_guest ?? "").trim();' in WORKER
        assert 'id="to_guest"' in WORKER
        assert "note_to_guest: document.getElementById('to_guest').value" in WORKER

    def test_it_goes_above_the_standard_text_not_instead_of_it(self):
        at = WORKER.index("${noteHtml}")
        after = WORKER[at:at + 400]
        assert "Thank you for the time you gave us" in after

    def test_an_empty_note_adds_nothing(self):
        assert 'noteHtml = note\n' in WORKER
        assert '      : "";' in WORKER

    def test_the_guests_own_words_are_escaped(self):
        block = WORKER[WORKER.index("const noteHtml"):WORKER.index("${noteHtml}")]
        assert "esc(para.trim())" in block

    def test_paragraphs_survive(self):
        block = WORKER[WORKER.index("const noteHtml"):WORKER.index("${noteHtml}")]
        assert "split(/\\n{2,}/)" in block
        assert 'replace(/\\n/g, "<br>")' in block

    def test_the_editorial_notes_stay_private(self):
        # Two boxes, two destinations: "notes" is kept on the package,
        # "note_to_guest" is the only one that leaves the building.
        assert "patrick_notes: body.notes ?? null" in WORKER
        assert "nobody else sees them" in WORKER
