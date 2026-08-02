"""Newsletter publishing via Buttondown API.

Converts markdown digests to email-friendly HTML and sends via the
Buttondown API (``POST /v1/emails``).  Supports per-show tag filtering
so subscribers only receive emails for shows they opted into.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

BUTTONDOWN_API_BASE = "https://api.buttondown.com/v1"

# Buttondown account username — used to build public archive URLs
# (https://buttondown.com/<username>/archive/<slug>/). Matches the
# subscribe-form embed on the homepage; override via env if the
# account ever moves.
BUTTONDOWN_USERNAME = os.getenv("BUTTONDOWN_USERNAME", "patricknovak1")


def convert_digest_to_email_html(markdown_text: str) -> str:
    """Convert a markdown digest to clean, mobile-friendly email HTML.

    Applies minimal inline styling for email client compatibility.
    Does not depend on external CSS — all styles are inline.
    """
    lines = markdown_text.split("\n")
    html_parts = [
        '<!DOCTYPE html>',
        '<html><head><meta charset="utf-8"></head>',
        '<body style="font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', '
        'Roboto, sans-serif; line-height: 1.6; color: #1a1a2e; max-width: 600px; '
        'margin: 0 auto; padding: 16px;">',
    ]

    for line in lines:
        stripped = line.strip()
        if not stripped:
            html_parts.append("<br>")
            continue

        # Headers
        if stripped.startswith("# "):
            html_parts.append(
                f'<h1 style="font-size: 1.4em; margin: 16px 0 8px; color: #1a1a2e;">'
                f'{_md_inline(stripped[2:])}</h1>'
            )
        elif stripped.startswith("## "):
            html_parts.append(
                f'<h2 style="font-size: 1.2em; margin: 14px 0 6px; color: #2d3748;">'
                f'{_md_inline(stripped[3:])}</h2>'
            )
        elif stripped.startswith("### "):
            html_parts.append(
                f'<h3 style="font-size: 1.05em; margin: 12px 0 4px; color: #4a5568;">'
                f'{_md_inline(stripped[4:])}</h3>'
            )
        # Horizontal rules / separators
        elif stripped.startswith("━") or stripped.startswith("---"):
            html_parts.append(
                '<hr style="border: none; border-top: 1px solid #e2e8f0; margin: 16px 0;">'
            )
        # Bullet items
        elif stripped.startswith("- "):
            html_parts.append(
                f'<p style="margin: 4px 0 4px 16px;">• {_md_inline(stripped[2:])}</p>'
            )
        # Numbered items
        elif re.match(r"^\d+\.\s", stripped):
            html_parts.append(
                f'<p style="margin: 4px 0 4px 16px;">{_md_inline(stripped)}</p>'
            )
        else:
            html_parts.append(f'<p style="margin: 4px 0;">{_md_inline(stripped)}</p>')

    # Engagement footer — encourage sharing and listening
    html_parts.append(
        '<hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0 16px;">'
        '<p style="margin: 8px 0; font-size: 0.9em; color: #718096;">'
        'Enjoyed this? Forward it to a friend who would too.'
        '</p>'
        '<p style="margin: 8px 0; font-size: 0.9em; color: #718096;">'
        '<a href="https://nerranetwork.com" style="color: #6B47FF;">Listen on nerranetwork.com</a>'
        ' &middot; '
        '<a href="https://nerranetwork.com/player.html" style="color: #6B47FF;">Open Player</a>'
        ' &middot; '
        '<a href="https://nerranetwork.com#subscribe" style="color: #6B47FF;">Subscribe to more shows</a>'
        '</p>'
        '<p style="margin: 8px 0; font-size: 0.8em; color: #a0aec0;">'
        'Nerra Network &mdash; 15 daily podcasts, ad-free, from Vancouver, Canada.'
        '</p>'
    )

    html_parts.append("</body></html>")
    return "\n".join(html_parts)


def _md_inline(text: str) -> str:
    """Convert inline markdown (bold, italic, links) to HTML."""
    # Bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Italic
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    # Links
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r'<a href="\2" style="color: #2b6cb0;">\1</a>',
        text,
    )
    return text


# ---------------------------------------------------------------------------
# API key validation
# ---------------------------------------------------------------------------


# Where a known sending block is remembered. Buttondown exposes no
# documented endpoint for "can this account send yet", so rather than
# guess at an undocumented schema we record what the send endpoint
# actually told us and let the preflight read it back.
#
# SCOPE, precisely: this file is gitignored runtime state, matching the
# double-send guardrail above, so on GitHub Actions (a fresh clone per
# run) it suppresses within a run but not across runs. The part that
# always works is the message — one actionable warning naming the
# operator fix, instead of a generic `logger.error` at the end of every
# pipeline. The durable fix is configuring the sending domain (or
# turning the newsletter off); this only stops the noise from training
# people to ignore real errors in the meantime.
_SENDING_BLOCKED_MARKER = Path(__file__).resolve().parent.parent / "digests" / "_newsletter_sending_blocked.json"

# The account cannot send until a custom sending domain is verified in
# Buttondown. This is a standing configuration state, not a transient
# fault, so it must not be logged as a fresh error on every run.
_SENDING_DOMAIN_HINTS = ("sending domain", "email_invalid")

# How long a remembered block is trusted. Short enough that the pipeline
# picks the newsletter back up on its own once the operator configures
# the domain, without needing anyone to clear a file.
_SENDING_BLOCK_TTL_DAYS = 7


def _is_sending_domain_error(detail: str) -> bool:
    """True when Buttondown refused because the account cannot send yet."""
    lowered = (detail or "").lower()
    return all(hint in lowered for hint in _SENDING_DOMAIN_HINTS) or (
        "custom sending domain" in lowered
    )


def _remember_sending_block(detail: str) -> None:
    """Persist the sending block so the next run can skip early."""
    try:
        _SENDING_BLOCKED_MARKER.parent.mkdir(parents=True, exist_ok=True)
        _SENDING_BLOCKED_MARKER.write_text(
            json.dumps({
                "blocked_at": datetime.datetime.now(
                    datetime.timezone.utc
                ).isoformat(),
                "detail": (detail or "")[:500],
            }, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:  # never let bookkeeping break the pipeline
        logger.debug("Could not record newsletter sending block: %s", exc)


def clear_sending_block() -> None:
    """Forget a remembered block. Called after any successful send."""
    try:
        _SENDING_BLOCKED_MARKER.unlink(missing_ok=True)
    except Exception as exc:
        logger.debug("Could not clear newsletter sending block: %s", exc)


def sending_block_reason() -> Optional[str]:
    """Return a short reason when sending is known to be blocked, else None.

    Expires after ``_SENDING_BLOCK_TTL_DAYS`` so a fixed configuration is
    picked up automatically rather than staying suppressed forever.
    """
    try:
        if not _SENDING_BLOCKED_MARKER.exists():
            return None
        data = json.loads(_SENDING_BLOCKED_MARKER.read_text(encoding="utf-8"))
        blocked_at = datetime.datetime.fromisoformat(data["blocked_at"])
        age = datetime.datetime.now(datetime.timezone.utc) - blocked_at
        if age > datetime.timedelta(days=_SENDING_BLOCK_TTL_DAYS):
            return None
        return (
            "Buttondown account has no verified custom sending domain "
            "(configure it in Buttondown → Settings → Sending)"
        )
    except Exception:
        return None


def validate_api_key(api_key: str) -> bool:
    """Test if the Buttondown API key is valid by calling GET /v1/emails.

    Returns ``True`` only on a clean ``200``. ``401``/``403`` mean the
    key is bad. Other status codes (``429``, ``5xx``, network errors)
    return ``False`` too — the caller can't safely proceed when
    Buttondown's reachability is unknown, and the previous behavior
    (returning ``True`` on any non-401) created false confidence
    that pre-flight passed when the service was down.
    """
    try:
        resp = requests.get(
            f"{BUTTONDOWN_API_BASE}/emails",
            headers={"Authorization": f"Token {api_key}"},
            timeout=10,
            params={"limit": 1},
        )
    except Exception as e:
        logger.error("Buttondown API key validation failed: %s", e)
        return False

    if resp.status_code == 200:
        logger.info("Buttondown API key validated successfully")
        return True
    if resp.status_code in (401, 403):
        logger.error(
            "Buttondown API key is INVALID or EXPIRED (HTTP %d)",
            resp.status_code,
        )
        return False
    # 429 / 5xx / anything else — we can't confirm the key is good and
    # we shouldn't claim it is. Surface as a soft failure so the
    # newsletter stage skips this run cleanly rather than queuing a
    # send against a potentially-unhealthy Buttondown.
    logger.warning(
        "Buttondown API key check returned HTTP %d — treating as "
        "transient unavailability (validation failed).",
        resp.status_code,
    )
    return False


# ---------------------------------------------------------------------------
# Send
# ---------------------------------------------------------------------------


_VALID_STATUSES = {"about_to_send", "draft", "scheduled"}


# Buttondown tag display-name -> tag identifier (TypeID) cache. Populated
# lazily from GET /v1/tags the first time a name is needed in a process.
_TAG_ID_CACHE: Dict[str, str] = {}

# Every tag name the account actually has, in fetch order. Kept so a
# failed lookup can SHOW the operator what exists instead of asking them
# to go compare by eye — "verify the name matches" is not actionable when
# the list it must match isn't in the log.
_ALL_TAG_NAMES: List[str] = []


def _fold_tag(name: str) -> str:
    """Normalise a tag name for tolerant comparison."""
    return " ".join(str(name or "").split()).casefold()


# Buttondown tag identifiers are TypeIDs. Observed live (Aug 2026) as
# ``sub_tag_…``; the send-filter docs elsewhere in this file describe a
# ``tag_…`` shape. Accept both — the prefix is Buttondown's to change,
# and the value is only ever passed straight back to their API.
_TAG_ID_PREFIXES = ("sub_tag_", "tag_")


def looks_like_tag_id(value: str) -> bool:
    """True when a configured tag is already an identifier.

    Lets a show pin ``newsletter.tag`` to the immutable id instead of
    the display name. Names are resolved through Buttondown's Tags page,
    which is hand-edited — renaming a tag there would otherwise break
    that show's send silently, the same class of failure as the tag
    simply not existing.
    """
    return str(value or "").strip().startswith(_TAG_ID_PREFIXES)


def _resolve_tag_ids(tag_names: List[str], api_key: str) -> Dict[str, str]:
    """Resolve Buttondown tag display names to their tag identifiers.

    Buttondown's email ``filters`` require tag *identifiers* (TypeIDs like
    ``tag_…``); passing a display name returns HTTP 422 ``"Tag filters must
    be valid tag identifiers."`` (this silently blocked every show's
    newsletter network-wide — see send_newsletter). Subscribers still carry
    tag *names* in their ``tags`` array, so we map name -> id via the
    paginated ``GET /v1/tags`` endpoint.

    Best-effort: returns only the names it could resolve; the caller decides
    how to handle misses. Resolved pairs are cached per-process so a run that
    sends several shows only pays for one tag fetch.
    """
    # A tag configured as an identifier needs no lookup — and must not
    # trigger one, or a show pinned to an id would still fail whenever
    # the Tags endpoint is unreachable.
    passthrough = {t: t.strip() for t in tag_names if looks_like_tag_id(t)}
    tag_names = [t for t in tag_names if t not in passthrough]

    need = [t for t in tag_names if t and t not in _TAG_ID_CACHE]
    if need:
        _ALL_TAG_NAMES.clear()
        try:
            url: Optional[str] = f"{BUTTONDOWN_API_BASE}/tags"
            params: Optional[Dict[str, str]] = {"page_size": "100"}
            while url:
                resp = requests.get(
                    url,
                    headers={"Authorization": f"Token {api_key}"},
                    params=params,
                    timeout=15,
                )
                resp.raise_for_status()
                payload = resp.json() or {}
                for tag in (payload.get("results") or []):
                    name = tag.get("name")
                    tid = tag.get("id")
                    if name and tid:
                        _TAG_ID_CACHE[name] = tid
                        _ALL_TAG_NAMES.append(name)
                # The ``next`` URL is fully qualified and already carries
                # the cursor — drop our params so we don't override it.
                url = payload.get("next") or None
                params = None
        except Exception as exc:  # noqa: BLE001 — caller handles empty result
            logger.error(
                "Failed to fetch Buttondown tags for id resolution: %s", exc,
            )
    resolved = {t: _TAG_ID_CACHE[t] for t in tag_names if t in _TAG_ID_CACHE}
    resolved.update(passthrough)
    # Tolerant second pass for the names that missed. Buttondown's Tags
    # page is hand-edited, so a stray trailing space or a case change
    # ("Spacex Daily") silently drops a show's whole send — an exact-match
    # -only lookup turns a typo into an outage. A tolerant hit is used but
    # announced, so the YAML still gets corrected.
    still_missing = [t for t in tag_names if t not in resolved]
    if still_missing and _TAG_ID_CACHE:
        folded = {_fold_tag(name): name for name in _TAG_ID_CACHE}
        for want in still_missing:
            actual = folded.get(_fold_tag(want))
            if actual:
                resolved[want] = _TAG_ID_CACHE[actual]
                logger.warning(
                    "Buttondown tag %r matched %r only after normalising "
                    "case/whitespace — update the show YAML's "
                    "newsletter.tag to the exact name.", want, actual,
                )
    return resolved


def send_newsletter(
    subject: str,
    body: str,
    *,
    api_key: str,
    status: str = "about_to_send",
    tags: Optional[List[str]] = None,
    slug: Optional[str] = None,
) -> Optional[str]:
    """Send a newsletter issue via Buttondown API.

    Parameters
    ----------
    subject:
        Email subject line.
    body:
        Markdown body text (Buttondown renders markdown natively).
    api_key:
        Buttondown API key.
    status:
        One of ``"about_to_send"``, ``"draft"``, or ``"scheduled"``.
    tags:
        Optional list of Buttondown tag names.  When provided, the email
        is sent **only** to subscribers who have any of the listed tags.
        This enables per-show targeting from a single Buttondown account.
    slug:
        Optional ASCII archive slug. Buttondown auto-derives a slug from
        the subject line, which produces percent-escaped junk like
        ``u041f-u0440-u0438-u0432-u0435-u0442-u0420-u0443`` for Russian
        subjects (see spec §4.3). Pass an explicit transliterated slug
        like ``privet-russian-ep018-kosmos-9-russkikh-slov`` to force a
        clean shareable archive URL.

    Returns
    -------
    str or None
        The email ID on success, ``None`` on failure.
    """
    # Strip newlines from subject to prevent email header injection
    subject = subject.replace("\r", "").replace("\n", " ").strip()

    if status not in _VALID_STATUSES:
        logger.error(
            "Newsletter status %r is invalid — must be one of %s. "
            "Refusing to send to avoid wasting an API call on a 400.",
            status, sorted(_VALID_STATUSES),
        )
        return None

    data = {
        "subject": subject,
        "body": body,
        "status": status,
    }
    if slug:
        # Buttondown rejects slugs with non-ASCII characters and
        # silently mangles them to escape-encoded form. Sanitize here
        # too as defense-in-depth (caller should already pass ASCII).
        ascii_slug = "".join(c for c in slug if c.isascii())
        # Conservative shape: lowercase, alphanumerics/hyphens only,
        # collapse runs, trim leading/trailing hyphens, cap at 100.
        import re as _re
        ascii_slug = ascii_slug.lower()
        ascii_slug = _re.sub(r"[^a-z0-9]+", "-", ascii_slug)
        ascii_slug = _re.sub(r"-+", "-", ascii_slug).strip("-")
        if ascii_slug:
            data["slug"] = ascii_slug[:100]

    if tags:
        # Buttondown's email-send filters use a tree structure with
        # ``filters`` (leaf conditions), ``groups`` (nested filter
        # groups), and ``predicate`` ("and"/"or") for the join.
        # Older clients sent ``{operator, predicates}`` and got
        # HTTP 422; the predicate enum is also strict — only "and"
        # or "or" are accepted (not "any"/"all").
        #
        # May 26 2026: Buttondown tightened the ``field`` enum on
        # the leaf condition; ``field: "tag"`` now 422s. Tag
        # membership lives at ``subscriber.tags`` with operator
        # ``contains`` (tags is a list field).
        #
        # May 31 2026: the leaf ``value`` must be the tag's
        # *identifier* (Buttondown TypeID, e.g. ``tag_abc123``), NOT
        # its display name. Passing the name returns HTTP 422
        #   {"detail":[{"value":"Tag filters must be valid tag identifiers."}]}
        # which silently blocked EVERY show's newsletter network-wide
        # (0 successful sends across 90 attempts). Subscribers still
        # carry tag *names* in their ``tags`` array, so resolve
        # name -> id via GET /v1/tags before building the filter.
        tag_id_map = _resolve_tag_ids(tags, api_key)
        resolved_ids = [tag_id_map[t] for t in tags if t in tag_id_map]
        missing = [t for t in tags if t not in tag_id_map]
        if missing:
            known = ", ".join(repr(n) for n in sorted(_ALL_TAG_NAMES)[:40])
            logger.error(
                "Could not resolve Buttondown tag id(s) for %s — those "
                "subscribers will not be targeted. The account has %d tag(s): "
                "[%s]. Either fix newsletter.tag in the show YAML to match "
                "one of those exactly, or create the tag in Buttondown.",
                missing, len(_ALL_TAG_NAMES), known or "none returned",
            )
        if not resolved_ids:
            # Never fall through to an unfiltered ``data`` (that would
            # blast the email to the ENTIRE network's subscriber list).
            logger.error(
                "No tag filters resolved to Buttondown tag IDs (requested "
                "%s). Refusing to send to avoid an unfiltered network-wide "
                "blast.", tags,
            )
            return None
        data["filters"] = {
            "filters": [
                {"field": "subscriber.tags", "operator": "contains", "value": tid}
                for tid in resolved_ids
            ],
            "groups": [],
            "predicate": "or",  # OR semantics across the listed tags
        }

    resp = requests.post(
        f"{BUTTONDOWN_API_BASE}/emails",
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
            # Buttondown's safety gate against accidental mass-sends.
            # The first email POST with status "about_to_send" for a
            # given API key returns HTTP 400 sending_requires_confirmation
            # unless this header is set. We always set it because we
            # mean to send.
            "X-Buttondown-Live-Dangerously": "true",
        },
        json=data,
        timeout=30,
    )

    if resp.status_code in (200, 201):
        result = resp.json()
        email_id = result.get("id", "unknown")
        recipient_count = result.get("secondary_id", result.get("num_recipients", "?"))
        logger.info(
            "Newsletter created: id=%s status=%s tags=%s recipients=%s",
            email_id, status, tags, recipient_count,
        )
        # Zero recipients when tag filters are set is a misconfiguration —
        # the email was accepted but nobody received it. Surface this as a
        # failure so the caller can alert/retry rather than logging "sent".
        if tags and result.get("num_recipients", 1) == 0:
            logger.error(
                "Newsletter %s was created but has 0 recipients — "
                "tag filter %s matched no subscribers. Treating as failure.",
                email_id, tags,
            )
            return None
        # A send that actually landed proves the account can send, so any
        # remembered block is stale — drop it immediately rather than
        # waiting out the TTL.
        clear_sending_block()
        return email_id
    else:
        error_detail = resp.text[:500]
        if resp.status_code == 422 and "tag" in error_detail.lower():
            logger.error(
                "Newsletter send failed with tag filter error (likely invalid Buttondown tag identifier in YAML 'newsletter.tag'). "
                "Current tag value(s): %s. Check your Buttondown Tags page for the exact slug/ID to use. Error: %s",
                tags, error_detail,
            )
        elif _is_sending_domain_error(error_detail):
            # A standing configuration state, not a fault in this run.
            # Logging it as a fresh error every single pipeline (which is
            # what happened until July 28 2026) is how people learn to
            # ignore errors. One clear, actionable warning instead, and
            # remember it so the next run skips before doing the work.
            _remember_sending_block(error_detail)
            logger.warning(
                "Newsletter not sent: the Buttondown account has no verified "
                "custom sending domain. Configure it in Buttondown → Settings "
                "→ Sending, or disable the newsletter for this show. "
                "Suppressing this stage for %d days.",
                _SENDING_BLOCK_TTL_DAYS,
            )
        else:
            logger.error(
                "Newsletter send failed: %s %s",
                resp.status_code, error_detail,
            )
        return None


def _dashboard_stats_for(slug: str) -> List[Dict[str, str]]:
    """Best-effort dashboard stat tiles for the newsletter 'By the numbers'
    block. Import-guarded so a refactor of the dashboard module can never
    break a send."""
    try:
        from engine.newsletter_dashboard import build_dashboard_stats
        return build_dashboard_stats(slug)
    except Exception:  # pragma: no cover — never block a send
        return []


def send_show_newsletter(
    digest_text: str,
    config,
    episode_num: int,
    today_str: str,
    *,
    hook: str = "",
) -> Optional[str]:
    """Send newsletter for a show if newsletter is configured.

    Spec v2 (May 2026) overhaul. The daily caller now matches the
    weekly's quality bar:

      - Subject line uses ``build_subject_line`` for the same
        ``"<hook> · <show> <emoji>"`` shape as weekly, with a 50-char
        hook cap for daily inboxes (§3).
      - Body is post-processed: scaffold scrubbed (``newsletter_sanitizer``),
        body transforms applied (``newsletter_body.transform_daily_body``)
        for box-rule replacement / Tesla price / Russian vocab cards.
      - Wrapper is given an explicit ``issue_number`` so the per-show
        counter renders just above Buttondown's network-wide auto-footer.
      - Buttondown ``slug`` is set explicitly (transliterated for
        Russian shows) so the archive URL reads cleanly (§4.3).
      - Pre-send guards: ``ScaffoldLeakError`` blocks if a known LLM
        label survived scrubbing; ``ContrastError`` blocks if the
        rendered HTML has WCAG AA failures (§7.3).
      - Same-day double-send guardrail (§4.5): tracks the last-send
        timestamp per show in ``digests/<slug>/_newsletter_lastsend.txt``
        and refuses to re-send within 20 hours.

    Returns the email ID on success, ``None`` if not configured / sent
    too recently / blocked by a guard.
    """
    newsletter = getattr(config, "newsletter", None)
    if not newsletter or not newsletter.enabled:
        return None

    api_key = os.getenv(newsletter.api_key_env, "").strip()
    if not api_key:
        logger.info("Newsletter API key not set (%s). Skipping.", newsletter.api_key_env)
        return None

    # Skip before doing the work. Composing, scrubbing, contrast-checking
    # and rendering a newsletter only to have Buttondown reject it for a
    # standing account-configuration reason is wasted pipeline time and a
    # guaranteed error at the end of every run (July 28 2026).
    blocked = sending_block_reason()
    if blocked:
        logger.info("Newsletter skipped — %s", blocked)
        return None

    slug = getattr(config, "slug", "") or ""

    # Same-day double-send guardrail. Spec §4.5 — May 2 saw both
    # Privet Russian Ep 17 AND Ep 18 go out within hours, which kills
    # open rates and triggers unsubs. Refuse to re-send within
    # 20 hours.
    if not _can_send_now(slug, min_hours=20):
        logger.warning(
            "Newsletter send blocked for slug=%s — last send was less "
            "than 20h ago. Operator should investigate the scheduler.",
            slug,
        )
        return None

    # Build subject the same way weeklies do. Hook is hard-capped
    # at 50 chars so the show + emoji never get truncated by Gmail's
    # inbox preview.
    import datetime as _dt
    try:
        _today = _dt.datetime.strptime(today_str, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        _today = _dt.date.today()
    from engine.newsletter_template import (
        build_subject_line,
        wrap_with_branding,
    )
    subject = build_subject_line(
        slug, hook, send_date=_today, hook_max_chars=50, is_daily=True,
    )

    tag = getattr(newsletter, "tag", "") or ""
    tags_list = [tag] if tag else None

    # Body transforms — clean up scaffold + render Tesla price /
    # Russian vocab. Run *before* wrap_with_branding so the wrapper
    # sees clean markdown.
    #
    # Two stages: ``transform_daily_body`` is the canonical (markdown
    # -safe) pass that already ran in ``run_show.py`` on the digest
    # source; we re-run it here as defense-in-depth (idempotent).
    # ``transform_email_body`` is the email-only layer that produces
    # inline HTML (TSLA stock-watch table, styled ``<hr>``, vocab
    # cards) — applying it at the canonical stage would corrupt the
    # blog / RSS / GitHub Pages surfaces, which is why it lives here.
    from engine.newsletter_body import (
        transform_daily_body,
        transform_email_body,
    )
    from engine.newsletter_sanitizer import (
        ScaffoldLeakError,
        assert_clean,
        scrub_scaffold,
    )
    from engine.utils import strip_speech_tags
    # Defense-in-depth: scrub Grok TTS speech tags before subscribers
    # see them. The podcast script keeps these for the TTS path; the
    # email body must never show ``[breath]`` / ``<emphasis>`` / etc.
    body_clean = strip_speech_tags(digest_text or "")
    body_clean = scrub_scaffold(body_clean)
    body_clean = transform_daily_body(body_clean, slug=slug)
    body_clean = transform_email_body(body_clean, slug=slug)

    # Hard tripwire: if any blocklisted label survived scrubbing, the
    # prompt regressed and the operator should fix the prompt before
    # any subscriber sees the leak.
    try:
        assert_clean(body_clean)
    except ScaffoldLeakError as exc:
        logger.error("Newsletter blocked (scaffold leak): %s", exc)
        return None

    # Adjacent shows — pull from network adjacency map.
    adjacent_shows = _adjacent_shows_for(slug, today_str)

    requires_disc = bool(
        getattr(newsletter, "requires_financial_disclaimer", False)
    )

    # Buttondown slug — explicit transliterated form for Russian
    # shows so the archive URL doesn't end up as
    # `archive/u041f-u0440-...`. Computed BEFORE the wrap so the
    # view-in-browser link can point at the issue's archive page
    # (wrap_with_branding always accepted archive_url; it was never
    # passed — June 2026 growth pass).
    bd_slug = _buttondown_slug_for(slug, episode_num, hook)
    archive_url = (
        f"https://buttondown.com/{BUTTONDOWN_USERNAME}/archive/{bd_slug}/"
        if bd_slug else ""
    )

    branded_body = wrap_with_branding(
        slug,
        body_clean,
        daily_label=f"Ep {episode_num}",
        daily_date=_today,
        adjacent_shows=adjacent_shows,
        requires_financial_disclaimer=requires_disc,
        # Surface the show's live dashboard data as a "By the numbers" block
        # under the hero (SpaceX: SPCX/launches/Starlink; Tesla: TSLA/deliveries;
        # Modern Investing: alpha/win-rate/trades). Best-effort + empty for shows
        # with no dashboard mapping, so this is a no-op everywhere else.
        by_the_numbers=_dashboard_stats_for(slug),
        # Daily emails count by episode, not by weeks-since-launch.
        # The latter (compute_issue_number) is for weekly synthesis
        # newsletters; on a daily it produces "Issue #1" for any show
        # that launched within the last 7 days regardless of how many
        # episodes have shipped (Tesla Ep 458 read "Issue #1" on
        # the May 2 daily — bug). Pass the episode number explicitly.
        issue_number=episode_num,
        archive_url=archive_url,
    )

    # Pre-send contrast tripwire (§7.3). Light-mode-only check — the
    # dark-mode <style> block is unit-tested separately.
    #
    # Phase 2.2 of the May 2026 audit flipped this from soft warning
    # to hard block. Pre-req was bumping the network's primary brand
    # color from ``#7C5CFF`` (4.35:1 on white, fails WCAG AA 4.5:1)
    # to ``#6B47FF`` (5.29:1, passes). CTA links and engagement-block
    # buttons all use the brand color, so the bump was the unblocker
    # for hard-blocking.
    from engine.contrast_validator import (
        ContrastError,
        assert_contrast_ok,
    )
    try:
        assert_contrast_ok(branded_body)
    except ContrastError as exc:
        logger.error("Newsletter contrast issues (blocking send): %s", exc)
        return None

    email_id = send_newsletter(
        subject=subject,
        body=branded_body,
        api_key=api_key,
        status=getattr(newsletter, "status", "about_to_send"),
        tags=tags_list,
        slug=bd_slug,
    )

    if email_id:
        _record_send(slug)
    return email_id


# ---------------------------------------------------------------------------
# Per-show send tracking (same-day double-send guardrail)
# ---------------------------------------------------------------------------

_LASTSEND_FILENAME = "_newsletter_lastsend.txt"


def _lastsend_path(slug: str):
    """Return the per-show timestamp file path used by the
    same-day send guardrail. Late-import ``pathlib`` to keep the
    module import cheap on cron runs that don't actually send."""
    from pathlib import Path
    return Path("digests") / slug / _LASTSEND_FILENAME


def _can_send_now(slug: str, *, min_hours: float = 20) -> bool:
    """Check whether enough time has elapsed since the last send.

    Conservative — returns True (allow send) on any read error so a
    missing file or permissions issue never blocks production.
    """
    if not slug:
        return True
    path = _lastsend_path(slug)
    try:
        if not path.exists():
            return True
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return True
        import datetime as _dt
        last = _dt.datetime.fromisoformat(raw)
        elapsed = _dt.datetime.now(_dt.timezone.utc) - last.astimezone(
            _dt.timezone.utc
        )
        return elapsed.total_seconds() >= (min_hours * 3600)
    except Exception as exc:  # noqa: BLE001 — never block on file errors
        logger.debug("lastsend read failed for %s: %s", slug, exc)
        return True


def _record_send(slug: str) -> None:
    """Persist this send's timestamp so the next call's guardrail works."""
    if not slug:
        return
    path = _lastsend_path(slug)
    try:
        import datetime as _dt
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            _dt.datetime.now(_dt.timezone.utc).isoformat(),
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("lastsend write failed for %s: %s", slug, exc)


# ---------------------------------------------------------------------------
# Buttondown slug
# ---------------------------------------------------------------------------

def _buttondown_slug_for(
    slug: str, episode_num: int, hook: str
) -> Optional[str]:
    """Return an ASCII slug suitable for Buttondown's archive URL.

    Russian-language shows must transliterate hook + show name so the
    archive URL doesn't end up percent-escaped. English shows get the
    same deterministic ``<show>-ep<num>-<hook>`` shape (June 2026
    growth pass) so the view-in-browser link can be built BEFORE the
    send — previously they returned None (Buttondown auto-derived the
    slug, unpredictable pre-send, so no archive link was ever passed).
    """
    base_map = {
        "finansy_prosto": "finansy-prosto",
        "privet_russian": "privet-russian",
    }
    base = base_map.get(slug, slug.replace("_", "-"))

    # Transliterate hook to ASCII for the slug suffix. We use a tiny
    # in-house Cyrillic→Latin map rather than pulling python-slugify
    # as a dep. Conservative: each Cyrillic letter maps to its
    # GOST 7.79 (BGN/PCGN) Latin equivalent.
    hook_ascii = _transliterate_cyrillic(hook or "")
    import re as _re
    hook_ascii = _re.sub(r"[^a-zA-Z0-9]+", "-", hook_ascii).strip("-").lower()
    if hook_ascii:
        return f"{base}-ep{episode_num:03d}-{hook_ascii[:40].strip('-')}"
    return f"{base}-ep{episode_num:03d}"


# Conservative GOST 7.79 / BGN-PCGN Cyrillic-to-Latin transliteration.
_CYRILLIC_MAP = {
    "А": "A", "Б": "B", "В": "V", "Г": "G", "Д": "D", "Е": "E", "Ё": "Yo",
    "Ж": "Zh", "З": "Z", "И": "I", "Й": "Y", "К": "K", "Л": "L",
    "М": "M", "Н": "N", "О": "O", "П": "P", "Р": "R", "С": "S",
    "Т": "T", "У": "U", "Ф": "F", "Х": "Kh", "Ц": "Ts", "Ч": "Ch",
    "Ш": "Sh", "Щ": "Shch", "Ъ": "", "Ы": "Y", "Ь": "", "Э": "E",
    "Ю": "Yu", "Я": "Ya",
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l",
    "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s",
    "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e",
    "ю": "yu", "я": "ya",
}


def _transliterate_cyrillic(text: str) -> str:
    """Cyrillic → ASCII for Buttondown slugs. Keeps non-Cyrillic chars."""
    return "".join(_CYRILLIC_MAP.get(c, c) for c in (text or ""))


# ---------------------------------------------------------------------------
# Adjacent-shows lookup (cross-network module data)
# ---------------------------------------------------------------------------

_RU_SHOW_SLUGS = frozenset({"finansy_prosto", "privet_russian"})


def _adjacent_shows_for(
    slug: str, today_str: str,
) -> Optional[List[Dict[str, str]]]:
    """Read the network adjacency map and return up to 2 sister shows
    with their most recent hook + listen URL.

    Best-effort: reads ``shows/_defaults.yaml``'s
    ``newsletter.network_adjacencies`` map. Returns None if the lookup
    fails or finds nothing.

    Language filtering (May 2026 audit): Russian-language shows
    (Финансы Просто, Привет Русский!) only ever recommend each other
    — never an English show their subscribers can't consume.
    Conversely English shows skip Russian sisters. This drops the
    ``finansy_prosto → modern_investing`` adjacency from the map's
    behaviour without forcing the operator to maintain two separate
    YAML maps.
    """
    try:
        import yaml as _yaml
        from pathlib import Path
        defaults_path = Path("shows") / "_defaults.yaml"
        if not defaults_path.exists():
            return None
        data = _yaml.safe_load(defaults_path.read_text(encoding="utf-8")) or {}
        nl = data.get("newsletter") or {}
        adj_map = (nl.get("network_adjacencies") or {})
        sister_slugs = list(adj_map.get(slug) or [])[:6]  # take more, filter
        if not sister_slugs:
            return None
        # Language filter: Russian shows recommend Russian shows only,
        # English shows recommend English shows only.
        is_ru = slug in _RU_SHOW_SLUGS
        sister_slugs = [
            s for s in sister_slugs
            if (s in _RU_SHOW_SLUGS) == is_ru and s != slug
        ][:2]
        if not sister_slugs:
            # Fall back to the other Russian show for FP/PR if the YAML
            # map doesn't have a same-language sister.
            if is_ru:
                fallback = "privet_russian" if slug == "finansy_prosto" else "finansy_prosto"
                sister_slugs = [fallback]
            else:
                return None
        out: List[Dict[str, str]] = []
        for sister_slug in sister_slugs:
            sister = _last_episode_for_show(sister_slug)
            if sister:
                out.append(sister)
        return out or None
    except Exception as exc:  # noqa: BLE001
        logger.debug("adjacent shows lookup failed for %s: %s", slug, exc)
        return None


def _last_episode_for_show(slug: str) -> Optional[Dict[str, str]]:
    """Return the most recent episode's hook + URL for use in the
    cross-network module. Reads the show's ``summaries_*.json`` file.
    """
    try:
        import json as _json
        from pathlib import Path
        digests_dir = Path("digests") / slug
        # Find any summaries_*.json file in the show's directory.
        candidates = sorted(digests_dir.glob("summaries_*.json"))
        if not candidates:
            return None
        data = _json.loads(candidates[0].read_text(encoding="utf-8")) or {}
        eps = data.get("episodes") or []
        if not eps:
            return None
        # Episodes are in reverse-chronological order in our summaries.
        latest = eps[0]
        # Load the show YAML for name + emoji so we render correctly.
        from engine.newsletter_template import _load_show_branding
        sister = _load_show_branding(slug)
        return {
            "name": sister.get("short_label") or sister.get("name") or slug,
            "slug": slug,
            "emoji": sister.get("emoji") or "",
            "hook": (latest.get("hook") or "")[:140],
            "url": sister.get("show_page") or "",
        }
    except Exception as exc:  # noqa: BLE001
        logger.debug("last-ep lookup failed for %s: %s", slug, exc)
        return None
