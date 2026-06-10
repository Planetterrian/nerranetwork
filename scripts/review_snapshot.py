#!/usr/bin/env python3
"""Deterministic per-show quality snapshot for the Show Review Agent.

Gives a review pass its starting numbers without burning agent turns on
re-deriving them: script-length vs target, cross-episode repeated phrases
(the "boilerplate tic" detector — the manual June 2026 passes found these
by hand-diffing transcripts), chapter-shape problems, per-episode LLM/TTS
cost, and the OP3 download trend.

Usage:
    python scripts/review_snapshot.py tesla
    python scripts/review_snapshot.py modern_investing --episodes 15

Output is markdown on stdout. Read-only; safe to run anywhere.
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

# Words that carry no tic signal on their own.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "for",
    "is", "are", "was", "were", "be", "been", "it", "its", "this", "that",
    "with", "as", "by", "from", "we", "you", "i", "they", "he", "she",
}


def count_words(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z']+", text.lower())


def _stitch_windows(grams: dict[str, int], n: int) -> dict[str, int]:
    """Merge n-grams that are consecutive windows of one longer phrase.

    A 15-word boilerplate sentence shows up as 8 overlapping 8-grams with
    identical document counts; stitching reconstructs the full phrase so the
    report prints one line, not eight.
    """
    by_count: dict[int, list[str]] = {}
    for gram, count in grams.items():
        by_count.setdefault(count, []).append(gram)

    merged: dict[str, int] = {}
    for count, group in by_count.items():
        starts = {tuple(g.split()[: n - 1]): g for g in sorted(group)}
        suffixes = {tuple(g.split()[1:]) for g in group}
        used: set[str] = set()
        for gram in sorted(group):
            if tuple(gram.split()[: n - 1]) in suffixes:
                continue  # not a chain head — some other gram extends into it
            toks = gram.split()
            used.add(gram)
            while True:
                nxt = starts.get(tuple(toks[-(n - 1):]))
                if not nxt or nxt in used:
                    break
                used.add(nxt)
                toks.append(nxt.split()[-1])
            merged[" ".join(toks)] = count
        for gram in group:  # cycles / collisions fall through unmerged
            if gram not in used:
                merged[gram] = count
    return merged


def find_repeated_ngrams(
    texts: list[str],
    min_n: int = 4,
    max_n: int = 8,
    min_fraction: float = 0.6,
    limit: int = 20,
) -> list[tuple[str, int]]:
    """Phrases of >= min_n words appearing in >= min_fraction of texts.

    Returns (phrase, episode_count) sorted by count then length, with
    overlapping windows stitched into maximal phrases and shorter grams
    subsumed by longer kept phrases removed. This is the every-episode-tic
    detector: a phrase the show speaks in 6 of 10 episodes is almost
    certainly template echo, a dead rotation pool, or a prompt boilerplate
    tic.
    """
    if not texts:
        return []
    threshold = max(2, int(len(texts) * min_fraction + 0.999))
    doc_counts: Counter[str] = Counter()
    for text in texts:
        toks = _tokens(text)
        grams: set[str] = set()
        for n in range(min_n, max_n + 1):
            for i in range(len(toks) - n + 1):
                window = toks[i : i + n]
                if all(w in _STOPWORDS for w in window):
                    continue
                grams.add(" ".join(window))
        doc_counts.update(grams)

    kept = {g: c for g, c in doc_counts.items() if c >= threshold}
    max_grams = {g: c for g, c in kept.items() if len(g.split()) == max_n}
    shorter = {g: c for g, c in kept.items() if len(g.split()) < max_n}
    candidates = {**_stitch_windows(max_grams, max_n), **shorter}

    # Longest-first so grams contained in an already-kept longer phrase
    # (at >= the same episode count) are dropped as redundant.
    ordered = sorted(candidates.items(), key=lambda gc: (-gc[1], -len(gc[0]), gc[0]))
    result: list[tuple[str, int]] = []
    for gram, count in ordered:
        if any(gram in longer and count <= lc for longer, lc in result):
            continue
        result.append((gram, count))
        if len(result) >= limit:
            break
    return result


def chapter_issues(chapters: list[dict]) -> list[str]:
    """Listener-visible problems in one episode's chapter list."""
    issues = []
    titles = [str(c.get("title", "")) for c in chapters]
    dupes = [t for t, n in Counter(titles).items() if n > 1 and t]
    if dupes:
        issues.append(f"duplicate chapter titles: {dupes}")
    if titles.count("Introduction") > 1:
        issues.append("multiple 'Introduction' chapters")
    if len(titles) <= 1:
        issues.append(f"only {len(titles)} chapter(s)")
    return issues


def _deep_get(data: dict, dotted: str):
    cur = data
    for key in dotted.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def _config_value(show_cfg: dict, defaults: dict, dotted: str):
    value = _deep_get(show_cfg, dotted)
    return value if value is not None else _deep_get(defaults, dotted)


def _sum_costs(node) -> float:
    """Recursively sum every estimated_cost_usd in a credit-usage JSON."""
    total = 0.0
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "estimated_cost_usd" and isinstance(value, (int, float)):
                total += float(value)
            else:
                total += _sum_costs(value)
    elif isinstance(node, list):
        for item in node:
            total += _sum_costs(item)
    return total


def _episode_num(path: Path) -> int | None:
    match = re.search(r"[Ee]p(\d+)", path.name)
    return int(match.group(1)) if match else None


def _latest(paths, count: int):
    numbered = [(n, p) for p in paths if (n := _episode_num(p)) is not None]
    numbered.sort()
    return numbered[-count:]


def build_snapshot(slug: str, episodes: int = 10) -> str:
    show_yaml = ROOT / "shows" / f"{slug}.yaml"
    if not show_yaml.exists():
        raise SystemExit(f"unknown show: {slug} (no shows/{slug}.yaml)")
    show_cfg = yaml.safe_load(show_yaml.read_text(encoding="utf-8")) or {}
    defaults = yaml.safe_load(
        (ROOT / "shows" / "_defaults.yaml").read_text(encoding="utf-8")
    ) or {}

    out_dir = ROOT / (_deep_get(show_cfg, "episode.output_dir") or f"digests/{slug}")
    lines = [f"# Review snapshot: {slug}", ""]
    if not out_dir.exists():
        lines.append(f"(no output directory at {out_dir} — nothing produced yet)")
        return "\n".join(lines)

    min_words = _config_value(show_cfg, defaults, "llm.min_podcast_words")
    lines.append(f"Output dir: `{out_dir.relative_to(ROOT)}` · "
                 f"configured `llm.min_podcast_words`: {min_words or 'unset'}")
    lines.append("")

    # --- Script length per episode ---
    tts_files = _latest(out_dir.glob("*_tts.txt"), episodes)
    lines.append(f"## Script length (last {len(tts_files)} `_tts.txt`)")
    for num, path in tts_files:
        words = count_words(path.read_text(encoding="utf-8", errors="replace"))
        flag = ""
        if isinstance(min_words, int) and words < min_words:
            flag = f"  ⚠ below min ({min_words})"
        lines.append(f"- ep{num}: {words} words{flag}")
    if not tts_files:
        lines.append("- (none found)")
    lines.append("")

    # --- Repeated-phrase / tic detector ---
    transcript_files = _latest(out_dir.glob("*_transcript.txt"), episodes)
    texts = [p.read_text(encoding="utf-8", errors="replace") for _, p in transcript_files]
    source = "transcripts"
    if not texts:
        texts = [p.read_text(encoding="utf-8", errors="replace") for _, p in tts_files]
        source = "_tts.txt scripts"
    tics = find_repeated_ngrams(texts)
    lines.append(f"## Repeated phrases across episodes (from {len(texts)} {source})")
    lines.append("Phrases below recur across most episodes. Show intro/outro is "
                 "expected; anything else is likely a boilerplate tic, dead "
                 "rotation pool, or template echo.")
    for phrase, count in tics:
        lines.append(f"- {count}/{len(texts)} episodes: “{phrase}”")
    if not tics:
        lines.append("- (no cross-episode repeated phrases above threshold)")
    lines.append("")

    # --- Chapter shape ---
    chapter_files = _latest(out_dir.glob("chapters_ep*.json"), episodes)
    lines.append(f"## Chapter shape (last {len(chapter_files)} episodes)")
    clean = 0
    for num, path in chapter_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            lines.append(f"- ep{num}: UNPARSEABLE ({exc})")
            continue
        chapters = data.get("chapters", data) if isinstance(data, dict) else data
        problems = chapter_issues(chapters if isinstance(chapters, list) else [])
        if problems:
            lines.append(f"- ep{num}: {'; '.join(problems)}")
        else:
            clean += 1
    lines.append(f"- {clean}/{len(chapter_files)} episodes have clean chapters")
    lines.append("")

    # --- Cost per episode ---
    credit_files = _latest(out_dir.glob("credit_usage_*ep*.json"), episodes)
    costs = []
    for num, path in credit_files:
        try:
            costs.append((num, _sum_costs(json.loads(path.read_text(encoding="utf-8")))))
        except Exception:
            continue
    lines.append(f"## Cost (last {len(costs)} episodes)")
    if costs:
        avg = sum(c for _, c in costs) / len(costs)
        lines.append(f"- avg ${avg:.3f}/episode · "
                     + " · ".join(f"ep{n}: ${c:.3f}" for n, c in costs[-5:]))
    else:
        lines.append("- (no credit-usage files)")
    lines.append("")

    # --- Audience trend (OP3) ---
    lines.append("## Audience (OP3)")
    op3_path = ROOT / "api" / "op3_stats.json"
    stats = None
    if op3_path.exists():
        try:
            stats = (json.loads(op3_path.read_text(encoding="utf-8"))
                     .get("shows", {}).get(slug))
        except Exception:
            stats = None
    if stats:
        lines.append(f"- downloads_7d: {stats.get('downloads_7d')} · "
                     f"downloads_30d: {stats.get('downloads_30d')} · "
                     f"weekly trend: {stats.get('weekly_downloads')}")
    else:
        lines.append("- (no OP3 data for this show)")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug", help="show slug matching shows/<slug>.yaml")
    parser.add_argument("--episodes", type=int, default=10)
    args = parser.parse_args()
    print(build_snapshot(args.slug, args.episodes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
