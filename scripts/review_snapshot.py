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


#: What a number becomes in the repeated-phrase report (any number).
NUMBER_PLACEHOLDER = "#"


def _tokens(text: str) -> list[str]:
    # Unicode-aware word tokens (internal apostrophes kept). The old
    # ``[a-z']+`` pattern was Cyrillic-blind: every Russian word
    # tokenized to nothing, so the tic detector reported "no cross-episode
    # repeated phrases" for Финансы Просто while a template ran 7/8
    # episodes (July 2026 network editorial pass).
    #
    # Aug 15 2026: numbers now tokenize as a ``0`` placeholder instead of
    # vanishing. The digit-blind tokenizer turned Tesla's well-formed
    # closer "TSLA closed at $328.58, up $9.05, 2.8%." into the phantom
    # tic "tsla closed at up", which two reviews filed as a bug and a
    # third ledger prediction chased ("_pick_closing harden") — the
    # closer was never broken. With the placeholder, a phrase repeats
    # across episodes only if its WORDING repeats; changing numbers no
    # longer collapse into a fake invariant.
    #
    # Oct 30 2026: the placeholder is ``#``, never ``0``. As ``0`` it read as
    # a real digit: "This is MAG 7 Daily, episode 24" printed as "this is
    # mag 0 daily episode 0", and two MAG 7 reviews (Oct 13, Oct 25) scored
    # a "mag zero" garble the audio never had.
    return [
        (NUMBER_PLACEHOLDER if t[0].isdigit() else t)
        for t in re.findall(
            r"[^\W\d_]+(?:['’][^\W\d_]+)*|\d[\d.,%]*", text.lower())
    ]


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
    # Orphan-closing class (July 2026): episodes whose FINAL chapter is not
    # a Closing slipped past the old checks — EI Ep049/050/051 ended on
    # promo-collision body chapters and still counted as "clean". The
    # network shape is body → (Tomorrow Teaser →) Closing, so anything
    # else ending the episode is a flag. Accepted Closing synonyms:
    # "Outro", the Russian shows' "Завершение" / "Прощание" (FP/PR title
    # their closings in Russian — the English-only check false-flagged
    # every FP episode), and DP Pod's "Sign-Off".
    if len(titles) > 1 and not re.search(
        r"(?i)\b(closing|outro|sign.?off|завершение|прощание)\b", titles[-1]
    ):
        issues.append(f"final chapter is not a Closing (ends on {titles[-1]!r})")
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


#: The interview shows produce no _tts.txt, chapters or credit files: their
#: episodes come from the Nerra Voices pipeline, and their craft record is
#: Supabase (episode_grades, episode_metrics, show_lessons) plus the digest
#: markdown. Oct 21 2026: both scheduled reviews of these shows had read
#: "0 _tts.txt" as evidence; the snapshot now reads what the shows write.
INTERVIEW_SHOW_SLUGS = ("age_of_ai", "nerra_voices")

#: The audio measures printed per episode, with the §7.7 target beside each.
_AUDIO_METRIC_ROWS = (
    ("overlap_events", "overlap events", "under 1 per 10 min"),
    ("turn_gap_ms_median", "median turn gap (ms)", "400-900"),
    ("mira_turn_sec_median", "her median turn (s)", "12-20"),
    ("self_answered_turns", "self-answered turns", "0"),
    ("echo_open_rate", "echo-open rate", "under 0.10"),
    ("guest_words_per_answer_median", "guest words per answer", "rising"),
    ("guest_words_trend", "guest words trend (last/first third)", "above 1"),
    ("closing_round_complete", "closing round complete", "every room"),
    ("seams", "seams", "0"),
)


def _voices_rows(table: str, query: str) -> list[dict]:
    """Supabase rows when the Voices credentials are in the environment;
    an empty list otherwise (the snapshot must run anywhere)."""
    import os
    if not (os.environ.get("SUPABASE_URL") or os.environ.get("VOICES_SUPABASE_URL")):
        return []
    try:
        voices = ROOT / "pipelines" / "voices"
        if str(voices) not in sys.path:
            sys.path.insert(0, str(voices))
        from common import sb_select  # type: ignore
        return sb_select(table, query) or []
    except Exception:  # noqa: BLE001 — a read-only report never fails on this
        return []


def _interview_episodes(out_dir: Path, episodes: int) -> list[tuple[int, Path]]:
    return _latest([p for p in out_dir.glob("*_Ep*.md")], episodes)


def _digest_head(path: Path) -> tuple[str, str]:
    """The hook line and the one-line summary of a digest."""
    hook = summary = ""
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not hook and line.startswith("> **"):
            hook = line.strip("> *").strip()
        elif not summary and line.startswith("**What You Need to Know:**"):
            summary = line.split(":**", 1)[-1].strip()
        if hook and summary:
            break
    return hook, summary


def interview_show_section(slug: str, out_dir: Path, episodes: int = 10) -> str:
    """The craft record of an interview show: per-episode grade and audio
    measures, the guest's own rating, and the standing lessons."""
    lines = [f"# Review snapshot: {slug}", "",
             f"Output dir: `{out_dir.relative_to(ROOT) if out_dir.is_relative_to(ROOT) else out_dir}` "
             "· interview show (Nerra Voices pipeline; no _tts.txt, chapters or credit "
             "files are expected — the record is the digest and Supabase)", ""]
    found = _interview_episodes(out_dir, episodes) if out_dir.exists() else []
    lines.append(f"## Published episodes (last {len(found)})")
    if not found:
        lines.append("- (no episode digests committed yet)")
    for num, path in found:
        hook, summary = _digest_head(path)
        lines.append(f"- Ep{num:03d} `{path.name}`: {hook or summary or '(no hook line)'}")
    lines.append("")

    grades = _voices_rows("episode_grades",
                          f"show=eq.{slug}&order=created_at.desc&limit={episodes}")
    lines.append(f"## Grades and audio measures (last {len(grades)} graded rooms)")
    if not grades:
        lines.append("- (no graded rooms read — set SUPABASE_URL / SUPABASE_SERVICE_KEY "
                     "to read episode_grades and episode_metrics)")
    else:
        overall = [g.get("overall") for g in grades if g.get("overall") is not None]
        if overall:
            lines.append(f"- overall grades, newest first: {', '.join(str(o) for o in overall)} "
                         f"(mean {sum(float(o) for o in overall) / len(overall):.1f})")
        for g in grades:
            m = (_voices_rows("episode_metrics",
                              f"interview_id=eq.{g.get('interview_id')}&limit=1") or [{}])[0]
            basis = m.get("metrics_basis") or "unmeasured"
            cells = []
            for key, label, target in _AUDIO_METRIC_ROWS:
                value = m.get(key)
                if value is None:
                    continue
                cells.append(f"{label} {value} (target {target})")
            lines.append(f"- {str(g.get('created_at') or '')[:10]} overall {g.get('overall')} "
                         f"· warmth {g.get('warmth')} · turn-taking {g.get('turn_taking')} "
                         f"· basis {basis}" + (": " + " · ".join(cells) if cells else ""))
    lines.append("")

    surveys = _voices_rows("editorial_packages",
                           "survey_rating=not.is.null&order=survey_answered_at.desc&limit=40"
                           "&select=survey_rating,survey_recommend,interview_id")
    lines.append("## The guest's own rating (24 h survey)")
    if surveys:
        ratings = [int(r["survey_rating"]) for r in surveys if r.get("survey_rating") is not None]
        lines.append(f"- {len(ratings)} answered · mean {sum(ratings) / len(ratings):.2f} · "
                     f"{sum(1 for r in ratings if r >= 4)} rated 4 or 5")
    else:
        lines.append("- (no survey answers read)")
    lines.append("")

    active_rows = _voices_rows("show_lessons",
                               f"status=eq.active&show=in.({slug},network)&order=decided_at.desc&limit=30")
    proposed_rows = _voices_rows("show_lessons",
                                 f"status=eq.proposed&show=in.({slug},network)&order=created_at.desc&limit=30")
    lines.append(f"## Standing lessons ({len(active_rows)} active, {len(proposed_rows)} proposed for the weekly pass)")
    for r in active_rows:
        metric = f" [metric: {r['metric']}]" if r.get("metric") else ""
        lines.append(f"- active ({'all shows' if r.get('show') == 'network' else 'this show'}){metric}: {r.get('lesson')}")
    for r in proposed_rows:
        lines.append(f"- proposed: {r.get('lesson')}")
    if not active_rows and not proposed_rows:
        lines.append("- (none read)")
    lines.append("")
    return "\n".join(lines)


def build_snapshot(slug: str, episodes: int = 10) -> str:
    show_yaml = ROOT / "shows" / f"{slug}.yaml"
    if not show_yaml.exists():
        raise SystemExit(f"unknown show: {slug} (no shows/{slug}.yaml)")
    show_cfg = yaml.safe_load(show_yaml.read_text(encoding="utf-8")) or {}
    defaults = yaml.safe_load(
        (ROOT / "shows" / "_defaults.yaml").read_text(encoding="utf-8")
    ) or {}

    out_dir = ROOT / (_deep_get(show_cfg, "episode.output_dir") or f"digests/{slug}")
    if slug in INTERVIEW_SHOW_SLUGS:
        return interview_show_section(slug, out_dir, episodes)
    lines = [f"# Review snapshot: {slug}", ""]
    if not out_dir.exists():
        lines.append(f"(no output directory at {out_dir} — nothing produced yet)")
        return "\n".join(lines)

    min_words = _config_value(show_cfg, defaults, "llm.min_podcast_words")
    lines.append(f"Output dir: `{out_dir.relative_to(ROOT)}` · "
                 f"configured `llm.min_podcast_words`: {min_words or 'unset'}")
    lines.append("")

    # --- Audience headline FIRST (Sep 12 2026): a review starts from the
    # audience, then reads the pipeline. Same builder as the dashboard
    # tile and the daily summary line. Unmeasured = null, never 0.
    lines.append("## Audience headline")
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from scripts.build_audience_headline import build_headline
        _doc = build_headline(ROOT)
        _show = (_doc.get("shows") or {}).get(slug)
        _net = _doc.get("network") or {}
        if _show and _show.get("downloads_30d") is not None:
            _wow = _show.get("wow_pct")
            _fw = (_show.get("first_week") or {}).get("median")
            _yt = _show.get("youtube") or {}
            lines.append(
                f"- RSS downloads: 7d {_show.get('downloads_7d')} · 30d {_show.get('downloads_30d')} · "
                f"last full week {_show.get('prior_week')} → {_show.get('last_week')} "
                f"({'unmeasured' if _wow is None else f'{_wow:+.1f}% WoW'})"
            )
            lines.append(
                f"- First-week downloads per episode (median, eps 7-30 days old): "
                f"{'unmeasured' if _fw is None else _fw} over "
                f"{(_show.get('first_week') or {}).get('episodes', 0)} episode(s)"
            )
            lines.append(
                f"- YouTube retention (views-weighted, last 28d): shorts "
                f"{'—' if _yt.get('short') is None else str(_yt.get('short')) + '%'} · long "
                f"{'—' if _yt.get('long') is None else str(_yt.get('long')) + '%'} · "
                f"{_yt.get('videos', 0)} video(s)"
            )
        else:
            lines.append("- (no RSS audience data for this show)")
        _nw = _net.get("wow_pct")
        lines.append(
            f"- Network: 7d {_net.get('downloads_7d')} · "
            f"{'WoW unmeasured' if _nw is None else f'{_nw:+.1f}% WoW'} · "
            f"newsletter {_net.get('newsletter_subscribers')}"
        )
    except Exception as _ah_exc:  # noqa: BLE001 — the snapshot must always render
        lines.append(f"- (audience headline unavailable: {_ah_exc})")
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
                 "rotation pool, or template echo. `#` stands for any number; "
                 "read the spoken form in the episode's `_tts.txt`.")
    for phrase, count in tics:
        lines.append(f"- {count}/{len(texts)} episodes: “{phrase}”")
    if not tics:
        lines.append("- (no cross-episode repeated phrases above threshold)")
    lines.append("")

    # --- Script density audit (Sep 5 2026 network delivery review) ---
    # The repeated-phrase detector above sees strings that recur ACROSS
    # episodes; the operator's "narrative-driven, redundant" complaint was
    # about repetition and filler WITHIN an episode, and about scripts that
    # read the digest aloud. engine.script_audit measures those; this
    # table is the number a review scores the prompt pass against.
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from engine.script_audit import audit_script as _audit_script
    except Exception:  # noqa: BLE001
        _audit_script = None
    if _audit_script and tts_files:
        lines.append(f"## Script density audit (last {len(tts_files)} `_tts.txt`)")
        lines.append("digest-verbatim = share of the script's 8-word phrases that "
                     "appear word for word in the digest; facts×2 = numeric facts "
                     "spoken more than once; filler = sentences with no fact "
                     "(spectator / underscores / watch-for / announcing shapes).")
        lines.append("copied sections = digest header blocks read aloud (sentence-level); "
                     "hook cov = share of the cold open's words the body speaks (<30% = "
                     "the opener sold a story the episode skipped).")
        lines.append("names kept = share of the digest's named entities the script speaks "
                     "(a paraphrase that swaps names for descriptions drops it).")
        lines.append("coverage = share of the digest's sentences the script tells in any wording "
                     "(a script that copies scores ~90%; one that drops stories scores under 55%).")
        lines.append("commas = commas per 100 words in the script / the digest (a fallback-model "
                     "episode reads 1-2; the cohort's grok-4.7 episodes 5-8; the voice pauses either way).")
        lines.append("| ep | sentences | digest-verbatim | coverage | copied sections | facts×2 | filler | hook restated | hook cov | names kept | commas |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for num, path in tts_files:
            script_text = path.read_text(encoding="utf-8", errors="replace")
            digest_path = path.with_name(path.name.replace("_tts.txt", ".md"))
            digest_text = (digest_path.read_text(encoding="utf-8", errors="replace")
                           if digest_path.exists() else "")
            hook_m = re.search(r"\*\*HOOK:\*\*\s*(.+)", digest_text)
            try:
                a = _audit_script(script_text, digest_text=digest_text,
                                  hook=hook_m.group(1).strip() if hook_m else "")
            except Exception:  # noqa: BLE001
                continue
            ovl = "n/a" if a.digest_overlap_pct is None else f"{a.digest_overlap_pct:.0f}%"
            flag = " ⚠" if a.warnings() else ""
            secs = ", ".join(s.split(" (")[0][:28] for s in a.copied_sections) or "—"
            cov = "n/a" if a.hook_coverage is None else f"{100 * a.hook_coverage:.0f}%"
            ents = "n/a" if a.entity_retention is None else f"{100 * a.entity_retention:.0f}%"
            dcov = "n/a" if a.digest_coverage is None else f"{100 * a.digest_coverage:.0f}%"
            _c = "n/a" if a.commas_per_100w is None else f"{a.commas_per_100w:.1f}"
            _dc = "n/a" if a.digest_commas_per_100w is None else f"{a.digest_commas_per_100w:.1f}"
            lines.append(f"| ep{num} | {a.sentences} | {ovl} | {dcov} | {secs} | {a.repeated_facts} | "
                         f"{a.filler_pct:.0f}% | {a.hook_restated} | {cov} | {ents} | {_c} / {_dc}{flag} |")
        lines.append("")

    # --- Fetch-filter leakage (July 18 2026 network meta-review) ---
    # Fetch-filter predictions (PT astronomy, SpaceX junk titles, FF
    # ephemeris) sat "pending" for weeks because nothing counted them
    # mechanically. Scan the show's recent DIGESTS for lines matching its
    # own exclude_title_patterns: a hit means excluded-class content still
    # reached shipped output (a filter bypass — the Ep116 web-search route
    # class), zero means the filter held.
    patterns = show_cfg.get("exclude_title_patterns") or []
    # Sep 4 2026: defined OUTSIDE the fetch-filter branch — the heading-
    # integrity section below reads it too, and a show with no
    # exclude_title_patterns (dp_pod, the narrative shows) crashed the
    # whole snapshot with UnboundLocalError, which silently took the
    # scheduled review agent's Phase-0 numbers away for those shows.
    digest_files = _latest(
        [p for p in out_dir.glob("*.md")
         if "_transcript" not in p.name and "_tts" not in p.name],
        episodes,
    )
    if patterns:
        compiled = []
        for p in patterns:
            try:
                compiled.append(re.compile(p, re.IGNORECASE))
            except re.error:
                continue
        hits = []
        for num, path in digest_files:
            text = path.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                # The patterns target fetched article TITLES. Digest item
                # lines wrap the title in **bold** and append source/date
                # suffixes ("— Source (2026-07-12)") that false-match some
                # patterns — test the bold title when present, else the line.
                m = re.search(r"\*\*(.+?)\*\*", line)
                probe = m.group(1) if m else line
                # Digest titles often carry a "(YYYY-MM-DD)" date suffix that
                # false-matches id-shaped patterns — strip it before probing.
                probe = re.sub(r"\s*\(\d{4}-\d{2}-\d{2}\)\s*$", "", probe)
                for rx in compiled:
                    if rx.search(probe):
                        hits.append((num, rx.pattern, line.strip()[:90]))
                        break
        lines.append(
            f"## Fetch-filter leakage ({len(patterns)} exclude_title_patterns "
            f"vs last {len(digest_files)} digests)"
        )
        if hits:
            for num, pat, excerpt in hits[:10]:
                lines.append(f"- ep{num}: /{pat}/ matched “{excerpt}”")
            if len(hits) > 10:
                lines.append(f"- (+{len(hits) - 10} more)")
        else:
            lines.append("- 0 hits — excluded-class content absent from shipped digests")
        lines.append("")

    # --- Digest heading integrity ---
    # Aug 15 2026: four consecutive spacex reviews scored the "Title:"
    # junk off the chapters JSONs and called the window clean while the
    # digest .md — the canonical source every reader surface renders —
    # was leaking the FORMATTING template's literal ``**Title: Source
    # Name**`` label on 3 of 10 episodes (and on Ep70 the model replaced
    # every headline with its PUBLISHER). Chapters are a downstream copy;
    # audit the source.
    if digest_files:
        label_hits: list[tuple[int, str]] = []
        publisher_hits: list[tuple[int, str]] = []
        _pub_shape = re.compile(
            r"^[A-Z][\w'&. -]{2,28}(\.(com|org|net|ca|io))?$"
        )
        for num, path in digest_files:
            text = path.read_text(encoding="utf-8", errors="replace")
            for line in text.splitlines():
                m = re.match(
                    r"\s*(?:\d+\.|[-*•])?\s*\*\*\s*(Title|Headline)\s*[:\-—]\s*(.*?)\*\*",
                    line,
                )
                if not m:
                    continue
                label_hits.append((num, line.strip()[:90]))
                # Publisher-as-headline mutation: the "headline" is just a
                # short name / domain with no verb-length content.
                if _pub_shape.match(m.group(2).strip()):
                    publisher_hits.append((num, m.group(2).strip()))
        lines.append(
            f"## Digest heading integrity (last {len(digest_files)} digests)"
        )
        if label_hits:
            eps = sorted({n for n, _ in label_hits})
            lines.append(
                f"- ⚠ leaked 'Title:' heading label in ep{', ep'.join(map(str, eps))} "
                f"({len(label_hits)} headings)"
            )
            for num, excerpt in label_hits[:5]:
                lines.append(f"  - ep{num}: “{excerpt}”")
            if publisher_hits:
                pe = sorted({n for n, _ in publisher_hits})
                lines.append(
                    f"- ⚠⚠ publisher-as-headline mutation in ep{', ep'.join(map(str, pe))} "
                    "(the real headline is GONE — prompt-side failure, "
                    "not repairable by scrubbing)"
                )
        else:
            lines.append("- 0 leaked heading labels")
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
