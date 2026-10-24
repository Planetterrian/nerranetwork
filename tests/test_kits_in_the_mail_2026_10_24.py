"""Operator, Oct 24 2026: put the press kit and the sponsorship kit in the
emails, pleasantly, so people can look at them and pass them on (to suggest a
sponsor, or to market an episode).

* Every HTML email Mira sends signs off with both kits, under her name.
* Someone meeting the network (an invitation, a referral invitation, a
  publicist's invitation) gets the "intro" paragraph; a guest who has
  recorded (the thank-you, the publish-day note) gets the "share" one.
* engine.brand owns the addresses and the words; the Worker's copies match.
* Every mention says the interview shows never carry a sponsor.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "pipelines" / "voices"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from engine import brand  # noqa: E402

WORKER = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text(encoding="utf-8")


def _plain(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", "", html).split())


def test_both_paragraphs_name_both_kits_and_the_sponsor_rule():
    for purpose in ("intro", "share"):
        html = brand.kits_html(purpose)
        assert brand.MEDIA_KIT_URL in html and brand.SPONSOR_KIT_URL in html
        assert "never carry a sponsor" in html
        assert "—" not in html
        text = brand.kits_text(purpose)
        assert brand.MEDIA_KIT_URL in text and brand.SPONSOR_KIT_URL in text


def test_every_html_signature_carries_the_kits():
    from common import mira_signature_html
    sig = mira_signature_html()
    assert brand.MEDIA_KIT_URL in sig and brand.SPONSOR_KIT_URL in sig
    assert "Press kit" in sig and "Sponsorship kit" in sig


def test_the_worker_copies_match_engine_brand():
    assert f'MEDIA_KIT_URL = "{brand.MEDIA_KIT_URL}"' in WORKER
    assert f'SPONSOR_KIT_URL = "{brand.SPONSOR_KIT_URL}"' in WORKER
    start = WORKER.index("export const KITS_INTRO_HTML =")
    block = WORKER[start:WORKER.index("</p>`;", start) + len("</p>`")]
    worker_text = _plain("".join(re.findall(r"`([^`]*)`", block))
                         .replace("${MEDIA_KIT_URL}", brand.MEDIA_KIT_URL)
                         .replace("${SPONSOR_KIT_URL}", brand.SPONSOR_KIT_URL))
    assert worker_text == _plain(brand.kits_html("intro"))
    sig = WORKER[WORKER.index("function miraSignature("):]
    sig = sig[:sig.index("\n}\n")]
    assert "${MEDIA_KIT_URL}" in sig and "${SPONSOR_KIT_URL}" in sig


def test_the_invitation_carries_the_intro():
    invite = WORKER[WORKER.index("`You're invited to ${show.name}`"):]
    invite = invite[:invite.index("miraSignature(show)")]
    assert "${KITS_INTRO_HTML}" in invite


def test_the_thank_you_and_the_publish_note_carry_the_share():
    import datetime as dt
    import guest_thanks

    class _Show:
        name = "Nerra Voices"
        slug = "nerra_voices"
    _subject, body = guest_thanks.thank_you_email(_Show(), {"name": "Jane Doe"}, "",
                                                  now=dt.datetime(2026, 10, 24, tzinfo=dt.timezone.utc))
    assert brand.kits_html("share") in body
    assert body.index(brand.kits_html("share")) < body.index("Sincerely")
    src = (ROOT / "pipelines" / "voices" / "publish_episode.py").read_text(encoding="utf-8")
    assert 'kits_html("share", show)' in src


def test_the_referral_and_publicist_invitations_carry_the_intro():
    tpl = (ROOT / "templates" / "email" / "referral_invite.j2").read_text(encoding="utf-8")
    assert "{{ kits_intro }}" in tpl
    from common import show_email_context
    ctx = show_email_context("nerra_voices", "")
    assert str(ctx["kits_intro"]) == brand.kits_html("intro")
    assert str(ctx["kits_share"]) == brand.kits_html("share")
    pub = (ROOT / "templates" / "email" / "producer_guest_invite.j2").read_text(encoding="utf-8")
    assert "{{ kits_text }}" in pub
