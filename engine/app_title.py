"""The podcast-app title, asked for once more when the digest left it out.

Nov 25 2026. Tesla's and SpaceX's digest prompts include
``_shared/app_title.txt``: a ``**TITLE:**`` line, a 60-character headline
for podcast apps, distinct from the spoken hook. The model leaves the line
out most days (18 of Tesla's 22 feed titles to Nov 24 were the clipped
hook, a consequence sentence cut by the 100-character feed limit).

When a show's digest prompt asks for the line and the digest has none,
:func:`followup_app_title` makes ONE small call that writes it from the
digest's own opening. It can only ever improve on the hook fallback:

* any error, an empty answer, or an answer that fails the fit gate returns
  ``None`` and the caller keeps the hook, exactly as before;
* the answer is never clipped (``engine.titles`` owns every limit; the
  gate is ``APP_TITLE_FOLLOWUP_MAX``);
* the title changes display surfaces only (feed item title, chapters,
  summaries). The spoken hook and the script are untouched.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Optional

from engine.titles import APP_TITLE_FOLLOWUP_MAX

logger = logging.getLogger(__name__)

_INCLUDE_MARK = "_shared/app_title.txt"
_REPO_ROOT = Path(__file__).resolve().parent.parent
_RULE_PATH = _REPO_ROOT / "shows" / "prompts" / "_shared" / "app_title.txt"
#: Characters of the digest handed to the call: the hook and the lead story.
DIGEST_EXCERPT_CHARS = 2400
MIN_TITLE_CHARS = 12
FOLLOWUP_TIMEOUT_S = 60.0
#: Seconds the rest of the episode must still have for the call to be made.
MIN_BUDGET_S = 600.0


def wants_app_title(config: Any) -> bool:
    """True when the show's digest prompt asks for the ``**TITLE:**`` line."""
    try:
        name = str(getattr(getattr(config, "llm", None), "digest_prompt_file", "") or "")
        if not name:
            return False
        path = Path(name)
        if not path.is_absolute():
            path = _REPO_ROOT / path
        text = path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001 - an unreadable prompt asks for nothing
        return False
    return _INCLUDE_MARK in text or bool(re.search(r"(?m)^\*\*TITLE:\*\*", text))


def clean_candidate(text: str) -> str:
    """The model's answer as one title line (no label, quotes or full stop)."""
    line = next((ln.strip() for ln in (text or "").splitlines() if ln.strip()), "")
    line = re.sub(r"^\*{0,2}TITLE:?\*{0,2}\s*", "", line, flags=re.IGNORECASE)
    line = line.strip().strip("*").strip()
    line = re.sub(r"^[\[\"'\u201c\u2018]+|[\]\"'\u201d\u2019]+$", "", line).strip()
    return line.rstrip(".").strip()


def title_fits(title: str, hook: str = "") -> bool:
    """The fit gate: a headline of a sane length that is not the hook again."""
    if not title or "\n" in title:
        return False
    if not (MIN_TITLE_CHARS <= len(title) <= APP_TITLE_FOLLOWUP_MAX):
        return False
    if not re.search(r"[A-Za-z\u0400-\u04FF]", title):
        return False
    if re.match(r"(?i)^(ep(isode)?\s*\d+|here is|here's|title\b|sure\b)", title):
        return False
    norm = lambda t: re.sub(r"\W+", " ", t or "").strip().lower()  # noqa: E731
    return norm(title) != norm(hook)


def build_prompt(digest: str, hook: str) -> str:
    rule = _RULE_PATH.read_text(encoding="utf-8").strip()
    excerpt = (digest or "").strip()[:DIGEST_EXCERPT_CHARS]
    return (
        "Below is the opening of today's episode brief. It is missing one "
        "line, the episode title podcast apps show. Write that one line and "
        "nothing else.\n\nThe rule for the line:\n" + rule + "\n\n"
        "The spoken hook, which the title must NOT restate:\n" + (hook or "(none)") + "\n\n"
        "The brief:\n" + excerpt + "\n\n"
        "Answer with the title text only, on one line, with no label."
    )


def followup_app_title(config: Any, digest: str, hook: str, *,
                       tracker: Optional[dict] = None,
                       budget_left_s: Optional[float] = None,
                       call: Any = None) -> Optional[str]:
    """One small call for a missing app title; ``None`` keeps the hook."""
    if not (digest or "").strip() or not wants_app_title(config):
        return None
    if budget_left_s is not None and budget_left_s < MIN_BUDGET_S:
        logger.info("App title follow-up skipped: %.0fs of pipeline budget left", budget_left_s)
        return None
    try:
        if call is None:
            from engine.generator import _call_grok as call
        model = str(getattr(getattr(config, "llm", None), "model", "") or "grok-4.3")
        text, meta = call(build_prompt(digest, hook), model=model, temperature=0.4,
                          max_tokens=400, timeout=FOLLOWUP_TIMEOUT_S)
        from engine.tracking import record_llm_usage_from_meta
        record_llm_usage_from_meta(tracker, "app_title_followup", meta)
    except Exception as exc:  # noqa: BLE001 - the hook stands, as it did before
        logger.warning("App title follow-up failed (%s): keeping the hook as the title", exc)
        return None
    title = clean_candidate(text)
    if not title_fits(title, hook):
        logger.warning("App title follow-up answer did not fit (%d chars): keeping the hook",
                       len(title))
        return None
    return title
