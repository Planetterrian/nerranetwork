"""Newsletter publishing via Buttondown API.

Converts markdown digests to email-friendly HTML and sends via the
Buttondown API (``POST /v1/emails``).  Supports per-show tag filtering
so subscribers only receive emails for shows they opted into.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

BUTTONDOWN_API_BASE = "https://api.buttondown.com/v1"


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
        '<a href="https://nerranetwork.com" style="color: #7C5CFF;">Listen on nerranetwork.com</a>'
        ' &middot; '
        '<a href="https://nerranetwork.com/player.html" style="color: #7C5CFF;">Open Player</a>'
        ' &middot; '
        '<a href="https://nerranetwork.com#subscribe" style="color: #7C5CFF;">Subscribe to more shows</a>'
        '</p>'
        '<p style="margin: 8px 0; font-size: 0.8em; color: #a0aec0;">'
        'Nerra Network &mdash; 11 daily podcasts, ad-free, from Vancouver, Canada.'
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
        data["filters"] = {
            "filters": [
                {"field": "tag", "operator": "equals", "value": t}
                for t in tags
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
        return email_id
    else:
        logger.error(
            "Newsletter send failed: %s %s",
            resp.status_code, resp.text[:500],
        )
        return None


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
    body_clean = scrub_scaffold(digest_text or "")
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

    branded_body = wrap_with_branding(
        slug,
        body_clean,
        daily_label=f"Ep {episode_num}",
        daily_date=_today,
        adjacent_shows=adjacent_shows,
        requires_financial_disclaimer=requires_disc,
        # Daily emails count by episode, not by weeks-since-launch.
        # The latter (compute_issue_number) is for weekly synthesis
        # newsletters; on a daily it produces "Issue #1" for any show
        # that launched within the last 7 days regardless of how many
        # episodes have shipped (Tesla Ep 458 read "Issue #1" on
        # the May 2 daily — bug). Pass the episode number explicitly.
        issue_number=episode_num,
    )

    # Pre-send contrast tripwire (§7.3). Light-mode-only check — the
    # dark-mode <style> block is unit-tested separately.
    from engine.contrast_validator import (
        ContrastError,
        assert_contrast_ok,
    )
    try:
        assert_contrast_ok(branded_body)
    except ContrastError as exc:
        # Don't hard-block on contrast for now — log loudly so
        # operator sees it, but ship the email. Contrast failures
        # are quality bugs, not safety bugs; an LLM scaffold leak
        # IS a safety bug. Once the validator has been calibrated
        # against a few real renders we can flip this to return None.
        logger.warning("Newsletter contrast issues (sending anyway): %s", exc)

    # Buttondown slug — explicit transliterated form for Russian
    # shows so the archive URL doesn't end up as
    # `archive/u041f-u0440-...`.
    bd_slug = _buttondown_slug_for(slug, episode_num, hook)

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
    archive URL doesn't end up percent-escaped. English shows can let
    Buttondown auto-derive (return None).
    """
    if slug not in ("finansy_prosto", "privet_russian"):
        return None
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

def _adjacent_shows_for(
    slug: str, today_str: str,
) -> Optional[List[Dict[str, str]]]:
    """Read the network adjacency map and return up to 2 sister shows
    with their most recent hook + listen URL.

    Best-effort: reads ``shows/_defaults.yaml``'s
    ``newsletter.network_adjacencies`` map. Returns None if the lookup
    fails or finds nothing.
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
        sister_slugs = list(adj_map.get(slug) or [])[:2]
        if not sister_slugs:
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
