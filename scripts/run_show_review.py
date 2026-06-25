#!/usr/bin/env python3
"""Grok-powered Show Review Agent — the near-free replacement for the
Claude-Opus `claude-code-action` review job.

The scheduled `show-review.yml` workflow used to spend ~$6-9/run driving
Claude Opus 4.8 through the `/review-show` playbook. The cost was dominated by
cache-reads of the 125 KB `CLAUDE.md` replayed across a long agentic loop. This
script does the same job for ~$0.30/run on Grok-4.3 (xAI; `GROK_API_KEY`,
already configured for the podcast pipeline) by:

  1. Gathering the review context deterministically (reusing
     `scripts/review_snapshot.build_snapshot`, the ledger, CLAUDE.md, prompts,
     and the last ~10 episodes' transcripts/chapters).
  2. Making ONE Grok-4.3 call with the `.claude/commands/review-show.md`
     playbook as the system prompt, requesting a structured JSON analysis.
  3. Writing the review doc + ledger entry + advancing the rotation, then
     opening a DRAFT PR.

The single deliberate difference from the Claude agent: this script does NOT
auto-edit prompt/YAML/audio files. Grok's proposed prompt/audio changes go into
the PR body under "⚠️ A/B-listen required — NOT applied" for the operator to
apply and listen. That *strengthens* the landmine #17 A/B-listen gate (nothing
audio-affecting is auto-committed) at the cost of the Claude agent's autonomous
multi-file root-causing.

Usage:
    python scripts/run_show_review.py tesla
    python scripts/run_show_review.py tesla --dry-run     # no git/PR; prints to stdout
    python scripts/run_show_review.py network             # cross-cutting meta review
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

# engine.generator pulls in heavy CI-only deps (tenacity) and the full fetch
# stack — import it lazily inside run_grok_review so this module loads (and its
# gather/parse/write logic is unit-testable) without those installed.
from engine.tracking import _estimate_grok_cost  # noqa: E402

REVIEW_MODEL = "grok-4.3"

# Context caps so a huge show can't blow past Grok's window or run up cost.
MAX_EPISODES = 10
MAX_TRANSCRIPT_WORDS = 4000      # per transcript
MAX_PRIOR_REVIEW_DOCS = 2        # most-recent prior review docs to include
MAX_PRIOR_REVIEW_CHARS = 8000    # per prior review doc

# ---------------------------------------------------------------------------
# Context gathering
# ---------------------------------------------------------------------------


def _read(path: Path, limit: int | None = None) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if limit is not None and len(text) > limit:
        text = text[:limit] + f"\n…[truncated, {len(text)} chars total]…"
    return text


def _episode_num(path: Path) -> int | None:
    m = re.search(r"[Ee]p(\d+)", path.name)
    return int(m.group(1)) if m else None


def _latest(paths, count: int):
    numbered = [(n, p) for p in paths if (n := _episode_num(p)) is not None]
    numbered.sort()
    return [p for _, p in numbered[-count:]]


def _truncate_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + f"\n…[truncated to {max_words} words]…"


def _claude_md_section(slug: str) -> str:
    """Pull the slug's quality-pass paragraphs + the Known Landmines block
    from CLAUDE.md instead of shipping the whole 125 KB file."""
    text = _read(ROOT / "CLAUDE.md")
    if not text:
        return ""
    chunks: list[str] = []
    # The per-show notes live as bolded "**XX** (Models & Agents) …" bullets and
    # "**<date> quality pass**" paragraphs; grab paragraphs mentioning the slug
    # or its likely display tokens.
    needles = {slug, slug.replace("_", " ")}
    for para in re.split(r"\n\n+", text):
        low = para.lower()
        if any(n in low for n in needles):
            chunks.append(para.strip())
    # Always include the Landmines header region (guardrail context).
    m = re.search(r"## Known Landmines.*?(?=\n## |\Z)", text, re.DOTALL)
    if m:
        chunks.append(m.group(0)[:6000])
    return "\n\n".join(chunks)[:20000]


def gather_show_context(slug: str, episodes: int = MAX_EPISODES) -> str:
    """Pack everything a show review reads into one prompt body."""
    from review_snapshot import build_snapshot

    parts: list[str] = []

    parts.append("## DETERMINISTIC SNAPSHOT\n" + build_snapshot(slug, episodes))

    section = _claude_md_section(slug)
    if section:
        parts.append("## CLAUDE.md — relevant notes + landmines\n" + section)

    ledger = ROOT / "docs" / "reviews" / "ledger" / f"{slug}.yaml"
    if ledger.exists():
        parts.append("## LEDGER (score the pending predictions; honor do_not_retry)\n"
                     + _read(ledger))
    else:
        parts.append("## LEDGER\n(no ledger yet — this is the first recorded review)")

    # Most-recent prior review docs.
    prior = sorted((ROOT / "docs" / "reviews").glob(f"{slug}_review_*.md"))
    prior += sorted((ROOT / "docs").glob(f"{slug}_review_*.md"))
    for doc in prior[-MAX_PRIOR_REVIEW_DOCS:]:
        parts.append(f"## PRIOR REVIEW: {doc.name}\n"
                     + _read(doc, MAX_PRIOR_REVIEW_CHARS))

    # Config + prompts.
    parts.append(f"## shows/{slug}.yaml\n" + _read(ROOT / "shows" / f"{slug}.yaml"))
    for prompt in sorted((ROOT / "shows" / "prompts").glob(f"{slug}_*.txt")):
        parts.append(f"## PROMPT {prompt.name}\n" + _read(prompt, 12000))
    hook = ROOT / "shows" / "hooks" / f"{slug}.py"
    if hook.exists():
        parts.append(f"## HOOK shows/hooks/{slug}.py\n" + _read(hook, 12000))

    # Last N episodes: digests, scripts, transcripts (the "ears"), chapters.
    out_dir = ROOT / "digests" / slug
    if out_dir.exists():
        for path in _latest(out_dir.glob("*_transcript.txt"), episodes):
            parts.append(f"## TRANSCRIPT {path.name}\n"
                         + _truncate_words(_read(path), MAX_TRANSCRIPT_WORDS))
        for path in _latest(out_dir.glob("chapters_ep*.json"), episodes):
            parts.append(f"## CHAPTERS {path.name}\n" + _read(path, 4000))
        # Digests only if no transcripts were found (avoid double-paying tokens).
        if not _latest(out_dir.glob("*_transcript.txt"), episodes):
            for path in _latest(out_dir.glob("*.md"), 3):
                parts.append(f"## DIGEST {path.name}\n"
                             + _truncate_words(_read(path), MAX_TRANSCRIPT_WORDS))

    return "\n\n".join(parts)


def gather_network_context() -> str:
    """Cross-cutting meta review: aggregate every ledger + workflow list."""
    parts: list[str] = []
    section = _claude_md_section("network")
    landmines = re.search(r"## Known Landmines.*?(?=\n## |\Z)",
                          _read(ROOT / "CLAUDE.md"), re.DOTALL)
    if landmines:
        parts.append("## CLAUDE.md — Known Landmines\n" + landmines.group(0)[:8000])
    parts.append("## Workflows\n" + "\n".join(
        f"- {p.name}" for p in sorted((ROOT / ".github" / "workflows").glob("*.yml"))))
    for ledger in sorted((ROOT / "docs" / "reviews" / "ledger").glob("*.yaml")):
        parts.append(f"## LEDGER {ledger.name}\n" + _read(ledger, 6000))
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Grok call
# ---------------------------------------------------------------------------

_OUTPUT_CONTRACT = """\

## YOUR OUTPUT (REQUIRED — read carefully)

You are running as a non-interactive script, NOT an autonomous coding agent.
You CANNOT edit files, run tools, or apply changes. You produce ONE JSON object
and nothing else — no markdown fences, no prose outside the JSON.

Because you cannot apply changes, you must NOT claim anything "shipped". Every
fix you would make is a *proposal* for the operator to apply and (for any
prompt/audio change) A/B-listen before merging. Cite evidence with file:line or
a transcript quote for every finding.

Return exactly this JSON shape:

{
  "summary": "<one sentence: what this pass found>",
  "review_markdown": "<the full review document body in markdown: an Evidence
     section, a Scoring table for the prior predictions, then P0 / P1 / P2
     findings with file:line or transcript-quote citations, then Deferred. Do
     NOT include a top-level H1 title — the script adds it.>",
  "scored_prior_predictions": [
     {"metric": "<the prior prediction's metric>",
      "verdict": "hit|partial|miss",
      "evidence": "<one line of today's evidence>"}
  ],
  "new_predictions": [
     {"metric": "<measurable metric>", "baseline": "<today's value>",
      "expected": "<what should be true at the next review>"}
  ],
  "proposed_changes": [
     {"file": "shows/prompts/<slug>_podcast.txt", "kind": "prompt|config|code",
      "ab_listen_required": true,
      "old": "<exact current text/snippet>", "new": "<proposed replacement>",
      "rationale": "<why>"}
  ],
  "deferred": ["<recommendation not proposed this pass, carried forward>"],
  "do_not_retry_additions": ["<operator-rejected/reverted idea, if any learned>"]
}

Any change touching a prompt, the spoken script, chapter markers that alter the
audio, or TTS settings MUST have "ab_listen_required": true. Code-only,
metadata-only fixes set it to false. If you propose nothing, return empty lists.
"""


def run_grok_review(slug: str, context: str) -> tuple[dict, dict]:
    from engine.generator import _call_grok  # heavy import deferred to call time

    playbook = _read(ROOT / ".claude" / "commands" / "review-show.md")
    system_prompt = (
        playbook
        + "\n\n---\n\nYou are reviewing target: "
        + slug
        + ".\n"
        + _OUTPUT_CONTRACT
    )
    user_prompt = (
        f"Here is the full review context for `{slug}`. Work through Phase 0-4 "
        f"of the playbook above, then emit the single JSON object specified in "
        f"YOUR OUTPUT.\n\n{context}"
    )
    text, meta = _call_grok(
        user_prompt,
        model=REVIEW_MODEL,
        system_prompt=system_prompt,
        temperature=0.4,
        max_tokens=12000,
        timeout=600.0,
    )
    return _parse_envelope(text), meta


def _parse_envelope(text: str) -> dict:
    """Robust JSON extraction (mirrors engine.synthesizer._parse_envelope)."""
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    candidate = fence.group(1) if fence else text
    parsed = None
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        brace = re.search(r"\{.*\}", candidate, re.DOTALL)
        if brace:
            try:
                parsed = json.loads(brace.group(0))
            except json.JSONDecodeError:
                parsed = None
    if not isinstance(parsed, dict) or "review_markdown" not in parsed:
        # Grok ignored the contract — keep the raw text as the review body so
        # the run still produces a usable (operator-readable) PR.
        return {
            "summary": "Grok did not return the JSON envelope; raw output kept.",
            "review_markdown": text,
            "scored_prior_predictions": [],
            "new_predictions": [],
            "proposed_changes": [],
            "deferred": [],
            "do_not_retry_additions": [],
            "_envelope_ok": False,
        }
    parsed.setdefault("scored_prior_predictions", [])
    parsed.setdefault("new_predictions", [])
    parsed.setdefault("proposed_changes", [])
    parsed.setdefault("deferred", [])
    parsed.setdefault("do_not_retry_additions", [])
    parsed.setdefault("summary", "")
    parsed["_envelope_ok"] = True
    return parsed


# ---------------------------------------------------------------------------
# Artifact writing (safe, deterministic — no audio-affecting edits)
# ---------------------------------------------------------------------------


def write_review_doc(slug: str, result: dict, today: datetime.date) -> Path:
    doc = ROOT / "docs" / "reviews" / f"{slug}_review_{today.strftime('%Y_%m_%d')}.md"
    body = result.get("review_markdown", "").strip()
    header = (
        f"# {slug} — quality review ({today.isoformat()})\n\n"
        f"_Generated by the Grok-4.3 Show Review Agent "
        f"(`scripts/run_show_review.py`). Proposed prompt/audio changes are "
        f"listed in the PR body under \"A/B-listen required\" and are NOT "
        f"applied — the operator applies and listens before merging "
        f"(landmine #17)._\n\n"
    )
    doc.write_text(header + body + "\n", encoding="utf-8")
    return doc


def _yaml_block(obj) -> str:
    """safe_dump with wrapping disabled (width-wrapped plain scalars don't
    round-trip in PyYAML) and proper quoting of any ``: ``-containing string."""
    return yaml.safe_dump(obj, sort_keys=False, allow_unicode=True, width=10**9)


def _indent(text: str, spaces: int) -> str:
    pad = " " * spaces
    return "".join((pad + ln if ln.strip() else ln) + "\n" for ln in text.splitlines())


def update_ledger(slug: str, result: dict, doc: Path, cost: float,
                  today: datetime.date) -> Path:
    """Append a new review entry by TEXT-SPLICE — never reserialize the
    existing file. Three committed ledgers contain unquoted ``: `` inside list
    items (a latent YAML bug that some PyYAML builds reject), and re-dumping a
    loaded ledger can corrupt long plain scalars via line-wrapping. Splicing
    our own (always-validly-quoted) entry sidesteps both."""
    path = ROOT / "docs" / "reviews" / "ledger" / f"{slug}.yaml"
    entry = {
        "date": today.isoformat(),
        "pr": None,
        "doc": str(doc.relative_to(ROOT)),
        "generated_by": REVIEW_MODEL,
        "summary": result.get("summary", "").strip() or "Grok review pass.",
        # Verdicts on the previous entry's pending predictions — kept on the new
        # entry (not mutated in place) so the operator reconciles on merge.
        "scored_prior_predictions": result.get("scored_prior_predictions", []),
        # The Grok script proposes rather than applies, so nothing "shipped".
        "shipped": [],
        "deferred": result.get("deferred", []),
        "predictions": [
            {
                "metric": p.get("metric", ""),
                "baseline": p.get("baseline", ""),
                "expected": p.get("expected", ""),
                "verdict": "pending",
                "evidence": None,
            }
            for p in result.get("new_predictions", [])
        ],
        "proposed_changes_in_pr": [
            {
                "file": c.get("file", ""),
                "kind": c.get("kind", ""),
                "ab_listen_required": bool(c.get("ab_listen_required", True)),
                "rationale": c.get("rationale", ""),
            }
            for c in result.get("proposed_changes", [])
        ],
        "agent_cost_usd": round(cost, 4),
    }
    dnr_items = [
        {"idea": item, "evidence": f"flagged {today.isoformat()} (Grok review)"}
        for item in result.get("do_not_retry_additions", [])
    ]

    if not path.exists():
        data = {"reviews": [entry], "do_not_retry": dnr_items}
        path.write_text(_yaml_block(data), encoding="utf-8")
        return path

    text = path.read_text(encoding="utf-8")
    entry_block = _indent(_yaml_block([entry]), 2)          # nest under reviews:
    dnr_block = _indent(_yaml_block(dnr_items), 2) if dnr_items else ""

    m = re.search(r"(?m)^do_not_retry:.*$", text)
    if m:
        head, dnr_line, tail = text[: m.start()], m.group(0), text[m.end():]
        new_dnr = dnr_line
        if dnr_items:
            if re.match(r"do_not_retry:\s*\[\s*\]\s*$", dnr_line):
                new_dnr = "do_not_retry:\n" + dnr_block.rstrip("\n")
                tail = "\n" + tail.lstrip("\n") if tail.strip() else "\n"
            else:
                # existing block (last top-level key) — append our items to it
                tail = tail.rstrip("\n") + "\n" + dnr_block
        if not head.endswith("\n"):
            head += "\n"
        text = head + entry_block + new_dnr + tail
    else:
        # No do_not_retry key — append entry, then add the key.
        text = text.rstrip("\n") + "\n" + entry_block
        text += "do_not_retry:\n" + dnr_block if dnr_items else "do_not_retry: []\n"

    path.write_text(text, encoding="utf-8")
    return path


def advance_rotation(slug: str, today: datetime.date) -> Path:
    """Set the slug's date in review_state.yaml via line replacement so the
    file's explanatory comments survive."""
    path = ROOT / "docs" / "reviews" / "review_state.yaml"
    text = path.read_text(encoding="utf-8")
    new_text, n = re.subn(
        rf"(?m)^(\s*{re.escape(slug)}:\s*).*$",
        rf"\g<1>{today.isoformat()}",
        text,
    )
    if n:
        path.write_text(new_text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# PR body + git
# ---------------------------------------------------------------------------


def build_pr_body(slug: str, result: dict, cost: float, meta: dict,
                  pytest_summary: str | None) -> str:
    lines: list[str] = []
    lines.append(result.get("summary", "").strip() or f"Grok review pass for {slug}.")
    lines.append("")
    lines.append(f"_Generated on **{REVIEW_MODEL}** by "
                 f"`scripts/run_show_review.py` (replaces the Claude-Opus review "
                 f"agent). Estimated cost: **${cost:.4f}**._")
    lines.append("")

    scored = result.get("scored_prior_predictions", [])
    if scored:
        lines.append("## Scored prior predictions")
        lines.append("| Prediction | Verdict | Evidence |")
        lines.append("|---|---|---|")
        for s in scored:
            lines.append(f"| {_cell(s.get('metric'))} | {_cell(s.get('verdict'))} "
                         f"| {_cell(s.get('evidence'))} |")
        lines.append("")

    changes = result.get("proposed_changes", [])
    ab = [c for c in changes if c.get("ab_listen_required")]
    safe = [c for c in changes if not c.get("ab_listen_required")]

    lines.append("## ⚠️ A/B-listen required — NOT applied (landmine #17)")
    if ab:
        lines.append("These prompt/audio changes are **proposals only**. Apply them "
                     "yourself, render/listen, then merge if they sound right.")
        for c in ab:
            lines.append("")
            lines.append(f"**`{c.get('file','?')}`** ({c.get('kind','?')}) — "
                         f"{c.get('rationale','').strip()}")
            lines.append("```diff")
            for ol in str(c.get("old", "")).splitlines() or [""]:
                lines.append(f"- {ol}")
            for nl in str(c.get("new", "")).splitlines() or [""]:
                lines.append(f"+ {nl}")
            lines.append("```")
    else:
        lines.append("None.")
    lines.append("")

    if safe:
        lines.append("## Code/metadata-only proposals (no A/B needed)")
        for c in safe:
            lines.append(f"- **`{c.get('file','?')}`** ({c.get('kind','?')}): "
                         f"{c.get('rationale','').strip()}")
        lines.append("")

    deferred = result.get("deferred", [])
    if deferred:
        lines.append("## Deferred (carried forward)")
        for d in deferred:
            lines.append(f"- {d}")
        lines.append("")

    if pytest_summary:
        lines.append("## Drift-guard status")
        lines.append("```")
        lines.append(pytest_summary.strip())
        lines.append("```")
        lines.append("")

    usage = meta.get("usage") or {}
    if usage:
        lines.append(f"<sub>tokens: {usage.get('prompt_tokens','?')} in / "
                     f"{usage.get('completion_tokens','?')} out</sub>")
    if not result.get("_envelope_ok", True):
        lines.append("")
        lines.append("> ⚠️ Grok did not return the structured envelope; the review "
                     "doc holds its raw output and the structured sections above "
                     "may be empty. Re-run if needed.")
    return "\n".join(lines)


def _cell(value) -> str:
    return str(value or "").replace("\n", " ").replace("|", "\\|")


def run_show_pytest(slug: str) -> str | None:
    test_file = ROOT / "tests" / f"test_{slug}_quality_pass.py"
    if not test_file.exists():
        return None
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(test_file), "-q", "--no-header"],
            cwd=ROOT, capture_output=True, text=True, timeout=300,
        )
        return (proc.stdout + proc.stderr).strip()[-1500:]
    except Exception as exc:  # noqa: BLE001
        return f"(could not run {test_file.name}: {exc})"


def open_draft_pr(slug: str, files: list[Path], pr_body: str,
                  today: datetime.date) -> None:
    branch = f"agent/review-{slug}-{today.strftime('%Y%m%d')}"
    title = f"[show-review] {slug} quality pass ({today.isoformat()})"
    body_file = ROOT / f".pr_body_{slug}.md"
    body_file.write_text(pr_body, encoding="utf-8")
    try:
        _git("config", "user.name", "github-actions[bot]")
        _git("config", "user.email", "github-actions[bot]@users.noreply.github.com")
        _git("checkout", "-b", branch)
        _git("add", *[str(f.relative_to(ROOT)) for f in files])
        _git("commit", "-m", title)
        _git("push", "-u", "origin", branch)
        proc = subprocess.run(
            ["gh", "pr", "create", "--draft", "--base", "main", "--head", branch,
             "--title", title, "--body-file", str(body_file)],
            cwd=ROOT, capture_output=True, text=True,
        )
        print(proc.stdout.strip() or proc.stderr.strip())
        if proc.returncode != 0:
            print("::warning::gh pr create returned non-zero "
                  "(branch is pushed; open the PR manually if needed)")
    finally:
        body_file.unlink(missing_ok=True)


def _git(*args: str) -> None:
    subprocess.run(["git", *args], cwd=ROOT, check=True,
                   capture_output=True, text=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug", help="show slug, or 'network'")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the review + JSON; write/commit nothing")
    parser.add_argument("--episodes", type=int, default=MAX_EPISODES)
    args = parser.parse_args()
    slug = args.slug

    today = datetime.date.today()
    print(f"[review] gathering context for {slug}…")
    context = (gather_network_context() if slug == "network"
               else gather_show_context(slug, args.episodes))

    print(f"[review] calling {REVIEW_MODEL} ({len(context)} chars of context)…")
    result, meta = run_grok_review(slug, context)
    usage = meta.get("usage") or {}
    cost = _estimate_grok_cost(
        REVIEW_MODEL,
        int(usage.get("prompt_tokens", 0)),
        int(usage.get("completion_tokens", 0)),
    )
    print(f"[review] grok done — ~${cost:.4f} "
          f"({usage.get('prompt_tokens','?')} in / "
          f"{usage.get('completion_tokens','?')} out)")

    if args.dry_run:
        print("\n===== REVIEW MARKDOWN =====\n")
        print(result.get("review_markdown", ""))
        print("\n===== STRUCTURED =====\n")
        print(json.dumps({k: v for k, v in result.items()
                          if k != "review_markdown"}, indent=2))
        return 0

    doc = write_review_doc(slug, result, today)
    ledger = update_ledger(slug, result, doc, cost, today)
    state = advance_rotation(slug, today)
    pytest_summary = run_show_pytest(slug)
    pr_body = build_pr_body(slug, result, cost, meta, pytest_summary)

    print(f"[review] wrote {doc.relative_to(ROOT)}, "
          f"{ledger.relative_to(ROOT)}, {state.relative_to(ROOT)}")
    open_draft_pr(slug, [doc, ledger, state], pr_body, today)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
