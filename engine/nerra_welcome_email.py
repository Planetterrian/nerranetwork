"""The Nerra Daily welcome email (Nov 6 2026).

Until now a new subscriber heard nothing until the next 7:00 AM Eastern
edition, which for a footer signup at 8 AM was a day of silence and then an
email they might not recognise. Buttondown had no welcome email on this
account (operator check, Nov 6 2026).

This module only COMPOSES the email: subject, preheader and a body in the
same branding wrapper as Nerra Daily, every site link through
:func:`engine.funnel.newsletter_link` (show ``nerra_daily``, episode 0,
variant ``welcome``). Where it is sent from is the operator's decision
(a Buttondown automation on subscriber confirmation, or the account Worker)
and is not wired here. Deterministic; no model call; no template condition,
so the copy reads the same in Buttondown's automation editor and in the
archive.

The voice is Patrick's: "Hi There," for a reader whose name we do not
have, plain prose, no em dashes, signed "Sincerely," / "Patrick".
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import List

from engine.nerra_daily_email import EMAIL_SLUG, SITE

#: The campaign variant every welcome-email link carries.
WELCOME_VARIANT = "welcome"

WELCOME_SUBJECT = "Welcome to Nerra Daily"
WELCOME_PREHEADER = ("Your first edition arrives at 7 AM Eastern. "
                     "Here is how to make it yours.")

_P = ('<p style="margin:0 0 14px;font-size:16px;line-height:1.6;'
      'color:#1f2937;">')
_LINK = "color:#2563eb;text-decoration:underline;"
_STEP = ('<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
         'border="0" class="card" style="background:#f8fafc;border-radius:10px;'
         'margin:0 0 12px;"><tr><td class="card" style="padding:14px 16px;'
         'border:1px solid #eef0f3;border-left:4px solid #6B47FF;border-radius:10px;">')


@dataclass
class Welcome:
    subject: str
    preheader: str
    body: str
    links: List[str]


def _esc(text: str) -> str:
    return html.escape(text or "", quote=True)


def _link(path: str) -> str:
    from engine.funnel import newsletter_link
    return newsletter_link(f"{SITE}/{path}", EMAIL_SLUG, 0, variant=WELCOME_VARIANT)


def _a(href: str, text: str, *, bold: bool = False) -> str:
    weight = "font-weight:600;" if bold else ""
    return f'<a href="{_esc(href)}" style="{_LINK}{weight}">{_esc(text)}</a>'


def _step(title: str, text_html: str) -> str:
    return (_STEP + '<p style="margin:0 0 4px;font-size:16px;font-weight:700;'
            f'color:#0f172a;">{_esc(title)}</p>'
            '<p style="margin:0;font-size:15px;line-height:1.55;color:#334155;">'
            f"{text_html}</p></td></tr></table>")


def compose_welcome() -> Welcome:
    """The welcome email, ready for Buttondown (one raw-HTML block per line,
    like :func:`engine.nerra_daily_email.compose`)."""
    from engine.brand import NETWORK_TAGLINE
    from engine.newsletter_template import wrap_with_branding

    choose = _link("account.html#customize")
    sunday = _link("account.html#email")
    listen = _link("nerra-daily.html")
    claims = _link("claims.html")
    disclosure = _link("ai-disclosure.html")
    personal = _link("join.html")

    lines = [
        _P + "Hi There,</p>",
        _P + "Thank you for subscribing to Nerra Daily. Every morning at 7 AM Eastern "
        "you will get one email with the shows you follow: the lead story from each, "
        "a sentence or two on it, and a link to listen, read or watch. "
        f"{_esc(NETWORK_TAGLINE)}</p>",
        _P + "Three things are worth a minute today.</p>",
        _step("1. Choose your shows",
              "Pick the shows you want and the email carries those first. Sign in on "
              + _a(choose, "My Nerra") + " with this email address; there is no password."),
        _step("2. Choose how often",
              "Every morning, or one Sunday edition with the week in review. You can "
              "switch on " + _a(sunday, "My Nerra") + " at any time."),
        _step("3. Keep it out of Promotions",
              "Add this address to your contacts, or move this email to your main inbox, "
              "so tomorrow's edition lands where you will see it."),
        _P + "If you would rather listen, " + _a(listen, "Nerra Daily is also a podcast", bold=True)
        + ": the whole morning across the network in one episode, in any podcast app.</p>",
        _P + "A word on how this is made. The shows are written and voiced with AI, every "
        "story links to its source, and every claim is checked against that source in "
        "the open: " + _a(claims, "the claims record") + " shows what was verified and what "
        "was not, and " + _a(disclosure, "the AI disclosure") + " explains the rest.</p>",
        _P + "If you want your shows as your own private daily episode, introduced by "
        "Mira, our AI host, " + _a(personal, "Nerra Personal") + " does that. No need to "
        "decide now.</p>",
        _P + "Reply to this email and tell me what you would like more of. I read every reply.</p>",
        _P + "Sincerely,</p>",
        _P + "Patrick</p>",
    ]
    body = "\n".join(lines)
    wrapped = wrap_with_branding(
        EMAIL_SLUG,
        body,
        preheader=WELCOME_PREHEADER,
        show_reply_share=False,
        hero="compact",
        masthead_lead_html=('<p style="margin:6px 0 2px;font-size:13px;line-height:1.5;'
                            'color:#ffffff;">One email each morning at 7 AM Eastern, '
                            'with the shows you choose</p>'),
        pill_text="Welcome",
    )
    links = [choose, sunday, listen, claims, disclosure, personal]
    return Welcome(subject=WELCOME_SUBJECT, preheader=WELCOME_PREHEADER,
                   body=wrapped, links=links)


def main(argv=None) -> int:
    """``python -m engine.nerra_welcome_email OUT.html`` writes the email for
    review (and for pasting into a Buttondown automation)."""
    import argparse
    from pathlib import Path

    ap = argparse.ArgumentParser(description="Write the Nerra Daily welcome email")
    ap.add_argument("out", help="output .html path")
    args = ap.parse_args(argv)
    w = compose_welcome()
    Path(args.out).write_text(w.body, encoding="utf-8")
    print(f"subject: {w.subject}\npreheader: {w.preheader}\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
