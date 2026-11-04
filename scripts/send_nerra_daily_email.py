#!/usr/bin/env python3
"""Send the day's Nerra Daily email (Nov 1 2026).

Runs after the edition publishes (``nerra-daily.yml``) and from a fallback
workflow (``nerra-daily-email.yml``). Idempotent: the committed
``digests/nerra_daily/email/<date>.json`` marker means "sent" and a second
run exits quietly. Composition is :mod:`engine.nerra_daily_email`.

Modes:

* ``send`` (default): scheduled for 7:00 AM Eastern through Buttondown when
  it is earlier than that, sent now otherwise; writes the marker.
* ``draft``: a Buttondown DRAFT with the same audience, optionally sent to
  ``--test-to`` (comma-separated) only. No marker; nobody else gets it.
* ``preview``: no API at all. Writes the source and three rendered copies
  (a new reader, a two-show follower, everything) to ``--out``.

Exit status is 0 whenever nothing is wrong with the code: "already sent",
"no edition yet" and "Buttondown key not set" are reported, not failures.
A send that Buttondown refuses exits 1 so the run is red.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import nerra_daily_email as nde  # noqa: E402

logger = logging.getLogger("nerra_daily_email")


def _trial_days() -> int:
    try:
        return max(0, int(os.environ.get("STRIPE_TRIAL_DAYS", "0") or 0))
    except ValueError:
        return 0


def _mask(addresses):
    """Keep test addresses out of public Actions logs."""
    if os.environ.get("GITHUB_ACTIONS") == "true":
        for addr in addresses:
            print(f"::add-mask::{addr}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--date", default="", help="Edition date YYYY-MM-DD (default: today UTC)")
    ap.add_argument("--mode", choices=("send", "draft", "preview"), default="send")
    ap.add_argument("--test-to", default="", help="draft mode: send the draft to these addresses only")
    ap.add_argument("--allow-no-edition", action="store_true",
                    help="send even when the edition did not publish (the fallback run)")
    ap.add_argument("--out", default="", help="preview mode: directory for the HTML files")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    day = (dt.date.fromisoformat(args.date) if args.date
           else dt.datetime.now(dt.timezone.utc).date())
    now = dt.datetime.now(dt.timezone.utc)

    if args.mode == "send" and nde.read_marker(day, ROOT):
        logger.info("Nerra Daily email for %s already sent; nothing to do.", day)
        return 0

    composed = nde.compose(day, root=ROOT, now=now, trial_days=_trial_days(),
                           allow_no_edition=args.allow_no_edition or args.mode != "send")
    if composed is None:
        logger.info("Nerra Daily email for %s: nothing to send yet.", day)
        return 0
    logger.info("Composed %s: %d section(s), subject %r, %d bytes of source",
                day, len(composed.sections), composed.subject, len(composed.body.encode()))

    # Every copy a subscriber can receive must render and stay under the
    # clipping point; a tag typo that hides a section is caught here.
    from engine.contrast_validator import ContrastError, assert_contrast_ok
    tags_all = [s.tag for s in nde.eligible_shows(nde.load_front(ROOT), ROOT)]
    samples = {
        "new_reader": [nde.MEMBER_TAG],
        "two_shows": [nde.MEMBER_TAG] + tags_all[:2],
        "everything": tags_all + [nde.PAID_TAG],
    }
    try:
        rendered = {k: nde.render_for(composed.body, v) for k, v in samples.items()}
        for copy in rendered.values():
            assert_contrast_ok(copy)
    except (ContrastError, ValueError) as exc:
        logger.error("Nerra Daily email blocked before sending: %s", exc)
        return 1
    biggest = max(len(c.encode()) for c in rendered.values())
    budget = nde.size_warning_bytes()
    if biggest > budget:
        logger.warning("::warning::The largest copy is %d bytes against a budget of %d: Gmail "
                       "clips at %d bytes including Buttondown's wrapper, measured at %d "
                       "bytes (%s). Measure the wrapper from a draft sent to a test mailbox "
                       "to tighten the budget.", biggest, budget, nde.GMAIL_CLIP_BYTES,
                       nde.BUTTONDOWN_WRAPPER_BYTES, nde.BUTTONDOWN_WRAPPER_MEASURED)

    if args.mode == "preview":
        out = Path(args.out or ROOT / "outputs" / "nerra_daily_email")
        out.mkdir(parents=True, exist_ok=True)
        (out / "source.html").write_text(composed.body, encoding="utf-8")
        for name, copy in rendered.items():
            (out / f"{name}.html").write_text(copy, encoding="utf-8")
        (out / "meta.json").write_text(json.dumps({
            "subject": composed.subject, "preheader": composed.preheader,
            "sections": composed.sections, "included": composed.included,
            "largest_copy_bytes": biggest, "size_budget_bytes": budget,
        }, indent=2), encoding="utf-8")
        logger.info("Preview written to %s", out)
        return 0

    from engine import newsletter as nl
    api_key = os.environ.get("BUTTONDOWN_API_KEY", "").strip()
    if not api_key:
        logger.warning("BUTTONDOWN_API_KEY is not set; the Nerra Daily email was not sent.")
        return 0
    blocked = nl.sending_block_reason()
    if blocked:
        logger.warning("Nerra Daily email skipped: %s", blocked)
        return 0

    en_tags = tags_all
    ru_tags = nde.russian_tags(ROOT)
    tag_ids = nl.resolve_tag_ids(
        [nde.MEMBER_TAG, nde.GALLERY_TAG, nde.WEEKLY_ONLY_TAG, *en_tags, *ru_tags], api_key)
    tree = nde.audience_filter(tag_ids, en_tags=en_tags, ru_tags=ru_tags, sunday=composed.sunday)
    if tree is None:
        logger.error("No audience tag resolved on Buttondown; refusing to send to the whole list.")
        return 1

    if args.mode == "draft":
        email_id = nl.send_newsletter(
            composed.subject, composed.body, api_key=api_key, status="draft",
            slug=composed.archive_slug + "-draft-" + now.strftime("%H%M"), filters=tree)
        if not email_id:
            return 1
        logger.info("Draft created: %s (open it in Buttondown to preview)", email_id)
        recipients = [a.strip() for a in args.test_to.split(",") if a.strip()]
        if recipients:
            _mask(recipients)
            if not nl.send_draft_to(email_id, recipients, api_key):
                return 1
        return 0

    from engine.release_schedule import newsletter_send_time
    when = newsletter_send_time(nde.EMAIL_SLUG, now)
    email_id = nl.send_newsletter(
        composed.subject, composed.body, api_key=api_key, status="about_to_send",
        slug=composed.archive_slug, publish_date=when, filters=tree)
    if not email_id:
        logger.error("Buttondown did not accept the Nerra Daily email for %s.", day)
        return 1
    nde.write_marker(day, {
        "date": day.isoformat(),
        "email_id": email_id,
        "subject": composed.subject,
        "scheduled_for": when.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if when else "",
        "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "edition_episode": composed.edition_ep,
        "sunday": composed.sunday,
        "sections": composed.sections,
        "included": composed.included,
        "largest_copy_bytes": biggest,
        "size_budget_bytes": budget,
        "archive_url": composed.archive_url,
    }, ROOT)
    logger.info("Nerra Daily email %s %s (%s).", email_id,
                "scheduled" if when else "sent", composed.subject)
    return 0


if __name__ == "__main__":
    sys.exit(main())
