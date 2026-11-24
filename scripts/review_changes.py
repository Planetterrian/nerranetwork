#!/usr/bin/env python3
"""The review agent's changes: what it may apply, and the merge tier of a PR.

Nov 24 2026 (register ``review-loop-automation-2026-11-24``, items 3 and 6).
Nine Grok review PRs merged that day as records only: the agent wrote every
prompt fix into the PR body, so merging a review changed no show and the same
proposals came back a fortnight later. Two halves live here.

**Apply** (``apply_change``): the agent edits the files it reviewed, in its
own branch, under a closed allowlist — the reviewed show's own prompts
(``shows/prompts/<slug>_*.txt`` or ``shows/prompts/<slug>/``) and its own
YAML (``shows/<slug>.yaml``). Nothing else: never ``_shared/`` or
``_defaults.yaml`` (network-wide), never code, never a workflow. Each change
must name ``old`` text that occurs EXACTLY ONCE, and the edited file must
still load (YAML through ``engine.config.load_config``; a prompt must render
through ``str.format_map`` and every ``<<include:>>`` must exist), or the
file is left as it was and the change stays a proposal with its reason.
Applying is not shipping: the PR is a draft, a rehearsal runs on its branch,
and the merge waits for a listen (landmine #17).

**Tiers** (``tier_for_paths``): every file a review PR touches is one of

* ``A`` record — ``docs/reviews/**`` only. The weekly slate
  (``scripts/review_slate.py``) merges a records-only PR on its own once
  every changed ledger parses.
* ``B`` listen — anything that changes what a listener hears: show prompts,
  show YAML, the audio chain, TTS, pronunciation. Merged by the operator
  after the rehearsal is heard.
* ``C`` operator — everything else (code, workflows, Workers, the site).

A PR's tier is its highest file tier.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]

TIER_RECORD = "A"
TIER_LISTEN = "B"
TIER_OPERATOR = "C"
TIER_ORDER = (TIER_RECORD, TIER_LISTEN, TIER_OPERATOR)
TIER_NAMES = {TIER_RECORD: "record", TIER_LISTEN: "listen", TIER_OPERATOR: "operator"}

RECORD_PREFIXES = ("docs/reviews/",)
#: A path that starts with one of these changes what a listener hears.
LISTEN_PREFIXES = (
    "shows/prompts/",
    "shows/hooks/",
    "assets/pronunciation.py",
    "engine/audio.py",
    "engine/story_breaks.py",
    "engine/story_tags.py",
    "engine/tts",
    "engine/listener_noise.py",
    "engine/utils.py",
)
_SHOW_YAML_RE = re.compile(r"^shows/[^/]+\.yaml$")

# Statuses ``apply_change`` returns. Only ``applied`` edits a file.
APPLIED = "applied"
NOT_ALLOWED = "not_allowed"
FILE_MISSING = "file_missing"
OLD_NOT_FOUND = "old_not_found"
OLD_NOT_UNIQUE = "old_not_unique"
EMPTY = "empty"
INVALID = "invalid_after_edit"

_INCLUDE_RE = re.compile(r"<<include:\s*([^>]+?)\s*>>")


def tier_for_path(path: str) -> str:
    p = path.lstrip("./")
    if p.startswith(RECORD_PREFIXES):
        return TIER_RECORD
    if p.startswith(LISTEN_PREFIXES) or _SHOW_YAML_RE.match(p):
        return TIER_LISTEN
    return TIER_OPERATOR


def tier_for_paths(paths: Iterable[str]) -> str:
    """The PR's tier: its highest file tier. No files reads as operator —
    an empty diff is never merged on its own."""
    tiers = [tier_for_path(p) for p in paths]
    if not tiers:
        return TIER_OPERATOR
    return max(tiers, key=TIER_ORDER.index)


def may_apply(slug: str, path: str) -> bool:
    """The closed allowlist: the reviewed show's own prompts and YAML."""
    p = path.lstrip("./")
    if not slug or slug == "network" or ".." in p:
        return False
    if p == f"shows/{slug}.yaml":
        return True
    if p.startswith(f"shows/prompts/{slug}/") and p.endswith(".txt"):
        return True
    return bool(re.fullmatch(rf"shows/prompts/{re.escape(slug)}_[^/]+\.txt", p))


class _Forgiving(dict):
    def __missing__(self, key):  # noqa: D401 — every placeholder renders ""
        return ""


def _validate(root: Path, rel: str, text: str) -> str:
    """'' when the edited text still loads, else why not."""
    if rel.endswith(".yaml"):
        import yaml
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            return f"YAML does not parse: {str(exc).splitlines()[0]}"
        if not isinstance(data, dict):
            return "YAML is no longer a mapping"
        return ""
    try:
        text.format_map(_Forgiving())
    except (ValueError, IndexError, KeyError) as exc:
        return f"prompt no longer renders: {exc}"
    shared = root / "shows" / "prompts" / "_shared"
    for name in _INCLUDE_RE.findall(text):
        if not (shared / name).exists() and not (root / "shows" / "prompts" / name).exists():
            return f"include {name!r} does not exist"
    return ""


def _validate_config(root: Path, rel: str) -> str:
    """Load the show the way run_show does; a key the dataclass rejects or a
    type it cannot coerce fails here, not at 6 AM."""
    try:
        from engine.config import load_config
        load_config(root / rel)
    except Exception as exc:  # noqa: BLE001 — any load failure refuses the edit
        return f"load_config failed: {type(exc).__name__}: {str(exc)[:200]}"
    return ""


def apply_change(slug: str, change: Dict[str, Any], root: Path = ROOT) -> Dict[str, Any]:
    """Apply one proposed change in place, or say why not. Never partial: the
    file is written only when every check passes, and a YAML that then fails
    ``load_config`` is put back."""
    rel = str(change.get("file") or "").strip().lstrip("./")
    old = str(change.get("old") or "")
    new = str(change.get("new") or "")
    out = {"file": rel, "status": "", "reason": ""}
    if not rel or not old.strip() or old == new:
        out.update(status=EMPTY, reason="no file, no old text, or no change")
        return out
    if not may_apply(slug, rel):
        out.update(status=NOT_ALLOWED,
                   reason="outside the agent's allowlist (its own show's prompts and YAML)")
        return out
    path = root / rel
    if not path.is_file():
        out.update(status=FILE_MISSING, reason="file does not exist")
        return out
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count == 0:
        out.update(status=OLD_NOT_FOUND, reason="the old text is not in the file as written")
        return out
    if count > 1:
        out.update(status=OLD_NOT_UNIQUE, reason=f"the old text occurs {count} times")
        return out
    edited = text.replace(old, new, 1)
    why = _validate(root, rel, edited)
    if why:
        out.update(status=INVALID, reason=why)
        return out
    path.write_text(edited, encoding="utf-8")
    if rel.endswith(".yaml"):
        why = _validate_config(root, rel)
        if why:
            path.write_text(text, encoding="utf-8")
            out.update(status=INVALID, reason=why)
            return out
    out["status"] = APPLIED
    return out


def apply_proposals(slug: str, changes: List[Dict[str, Any]],
                    root: Path = ROOT) -> List[Dict[str, Any]]:
    """One result per proposed change, in order. Changes to the same file
    apply one after another, so a later ``old`` is matched against the file
    as the earlier change left it."""
    return [apply_change(slug, c, root) for c in changes or []]
