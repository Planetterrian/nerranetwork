"""Ask every guest, every time (Oct 21 2026 review, §7.4).

The only post-interview feedback request used to live on the
transcript-approval page, so a guest who approved by email or was
auto-approved at day seven was never asked: one answer in thirteen. This
sends a three-question email from Mira about 24 hours after the room, to
every guest with an address, whether or not they ever open that page, and
keeps nothing but a token until they answer. The page the link opens is the
Voices Worker's ``/voices/survey/<token>``; the answers land on the same
``editorial_packages`` row (``survey_rating`` is the show's headline figure,
the way ``audience_headline`` is for the network).

Runs from the fire tick (``send_due_surveys``), as its own step that never
fails the job.
"""

from __future__ import annotations

import datetime as dt
import os
from typing import Any, Dict, List, Optional

from common import (
    logger, mira_signature_html, new_review_token, sb_select, sb_update,
    send_email, show_for,
)
from address import first_name

#: How long after the room ended the email goes. A guest who has just hung
#: up is still in the hour; a day later they have an opinion.
SURVEY_AFTER = dt.timedelta(hours=24)
#: ... and not after this: a survey three weeks late is a survey about the
#: edit, not the hour.
SURVEY_WINDOW = dt.timedelta(days=14)
SURVEY_BASE = "https://api.nerranetwork.com/voices/survey"
#: Packages that are not an interview anyone sat through.
SKIPPED_STATUSES = {"killed", "archived"}


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def survey_url(token: str) -> str:
    return f"{SURVEY_BASE}/{token}"


def survey_email(app: dict, show, url: str) -> "tuple[str, str]":
    """Subject and body: three questions, one link, Mira's name."""
    name = first_name(app) if app.get("name") else "there"
    subject = f"One minute on how the hour felt — {show.name}"
    html = (
        '<div style="font-family:system-ui,sans-serif;max-width:640px;margin:0 auto;'
        'color:#1a202c;line-height:1.6">'
        f"<p>Hi {name},</p>"
        "<p>Thank you again for yesterday. Three questions, a minute at most, "
        "and the honest answer is the useful one:</p>"
        "<ol>"
        "<li>On a scale of one to five, how did the hour compare with being "
        "interviewed by a human host?</li>"
        "<li>One thing you would change about how I did it.</li>"
        "<li>Would you recommend it to a peer?</li>"
        "</ol>"
        f'<p><a href="{url}" style="color:{show.brand_color}">Answer here</a> '
        "(no sign-in, nothing published; this goes to the producer and to me).</p>"
        "<p>Your episode is on its way to you separately for approval, and nothing "
        "goes out until you have heard it.</p>"
        f"{mira_signature_html(show)}"
        "</div>"
    )
    return subject, html


def due_packages(now: Optional[dt.datetime] = None) -> List[Dict[str, Any]]:
    """Packages whose guest has not been asked, 24 h to 14 d after the room.

    Each row carries ``interview`` and ``app`` once resolved. A closing
    session, a killed or archived package, or a guest with no address is
    skipped; the stamp is never written for those, so a package that gains
    an address later is asked then.
    """
    now = now or _now()
    since = (now - SURVEY_WINDOW).isoformat()
    until = (now - SURVEY_AFTER).isoformat()
    rows = sb_select(
        "editorial_packages",
        f"survey_sent_at=is.null&created_at=gte.{since}&created_at=lte.{until}"
        "&order=created_at.asc&limit=20"
        "&select=id,interview_id,status,created_at") or []
    out = []
    for row in rows:
        if (row.get("status") or "") in SKIPPED_STATUSES:
            continue
        ivs = sb_select("interviews", f"id=eq.{row['interview_id']}&limit=1") or []
        iv = ivs[0] if ivs else {}
        if (iv.get("session_kind") or "interview") != "interview":
            continue
        apps = (sb_select("guest_applications",
                          f"id=eq.{iv.get('application_id')}&limit=1")
                if iv.get("application_id") else []) or []
        app = apps[0] if apps else {}
        if "@" not in str(app.get("email") or ""):
            continue
        out.append({**row, "interview": iv, "app": app})
    return out


def send_due_surveys(now: Optional[dt.datetime] = None, dry_run: bool = False) -> int:
    """Send the survey to every guest who is due one. Returns the count."""
    if (os.environ.get("PRODUCER_MODE") or "").lower() == "off":
        logger.info("PRODUCER_MODE=off: no surveys sent")
        return 0
    sent = 0
    for pkg in due_packages(now):
        iv, app = pkg["interview"], pkg["app"]
        show = show_for(iv, app)
        token = new_review_token()
        subject, html = survey_email(app, show, survey_url(token))
        if dry_run:
            logger.info("[dry run] survey to %s for package %s", app.get("email"), pkg["id"])
            sent += 1
            continue
        # The token is written BEFORE the send (a sent link must open
        # something) and the stamp AFTER it (a stamped package nobody
        # emailed would never be asked again).
        try:
            sb_update("editorial_packages", f"id=eq.{pkg['id']}",
                      {"survey_token": token})
            send_email(app["email"], subject, html, cc_operator=False)
            sb_update("editorial_packages", f"id=eq.{pkg['id']}",
                      {"survey_sent_at": _now().isoformat()})
            sent += 1
            logger.info("survey sent to %s (package %s)", app.get("email"), pkg["id"])
        except Exception:  # noqa: BLE001 — the next tick tries again
            logger.exception("survey for package %s failed (non-fatal)", pkg.get("id"))
    return sent


def survey_headline(show_slug: str, limit: int = 40) -> Dict[str, Any]:
    """The show's headline figure: answered surveys, mean and share ≥ 4."""
    try:
        rows = sb_select(
            "editorial_packages",
            "survey_rating=not.is.null&order=survey_answered_at.desc"
            f"&limit={limit}&select=survey_rating,interview_id") or []
        ivs = {}
        for r in rows:
            got = sb_select("interviews", f"id=eq.{r['interview_id']}&select=id,show&limit=1") or []
            if got:
                ivs[r["interview_id"]] = got[0].get("show") or ""
    except Exception:  # noqa: BLE001
        logger.exception("survey headline unavailable (non-fatal)")
        rows, ivs = [], {}
    ratings = [int(r["survey_rating"]) for r in rows
               if r.get("survey_rating") is not None
               and (ivs.get(r["interview_id"]) or show_slug) == show_slug]
    if not ratings:
        return {"answered": 0, "mean": None, "share_4_plus": None}
    return {"answered": len(ratings),
            "mean": round(sum(ratings) / len(ratings), 2),
            "share_4_plus": round(sum(1 for r in ratings if r >= 4) / len(ratings), 2)}


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    n = send_due_surveys(dry_run=args.dry_run)
    logger.info("%d survey(s) %s", n, "would go" if args.dry_run else "sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
