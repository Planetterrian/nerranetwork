"""Pre-fetch hook for The DP Pod (The Do Positive Podcast).

Supplies ``{nerra_network_context}`` to both prompts:

* a compact catalog of the network's shows (so the hosts can describe a
  sibling show correctly),
* **FRESH ON THE NETWORK** — the sibling episodes that actually shipped in
  the last ~3 days (real titles from each show's summaries JSON), so every
  episode's network pointer names a real, current episode instead of a
  generic plug (operator direction, July 2026: follow-up episodes should
  regularly point listeners at network shows/episodes worth their queue),
* the most recent First Principles Daily brief as ready-to-discuss network
  material for thin-news days,
* the founders' notes (the only sanctioned source of personal host material),
* **Think Positive rotation memory** — the thinkers featured in recent
  episodes, mined from this show's own digests, so the mindset segment
  rotates instead of converging on one or two names.

Everything is best-effort: a failure returns a smaller context block, never
blocks the episode.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent.parent

# Compact, hand-curated catalog (digest dir, name, one-phrase pitch). Kept
# static so a registry hiccup can't garble the on-air description of a
# sibling show. Russian-language shows are deliberately absent — the DP
# audience is English-first. Age of AI joins once it has published episodes.
_NETWORK_SHOWS = [
    ("first_principles", "First Principles Daily", "reasons a thing should cost less — the magic wand number and the Idiot Index, one example a day"),
    ("fascinating_frontiers", "Fascinating Frontiers", "the day's space and science wonders, with a cosmic deep dive"),
    ("tesla_shorts_time", "Tesla Shorts Time", "the daily Tesla briefing — deliveries, FSD, energy, and the stock"),
    ("spacex", "SpaceX Daily", "engineering-first coverage of SpaceX as a public company"),
    ("planetterrian", "Planetterrian Daily", "science, longevity, and health research that changes how you live"),
    ("models_agents", "Models & Agents", "the daily AI briefing for people who build with it"),
    ("models_agents_beginners", "Models & Agents for Beginners", "the same AI news, explained from zero"),
    ("omni_view", "Omni View", "world news with every side steel-manned"),
    ("modern_investing", "Modern Investing Techniques", "markets and investing craft with a transparent track record"),
    ("env_intel", "Environmental Intelligence", "Canada's environmental policy and compliance brief"),
    ("unintended_consequences", "Unintended Consequences", "history's best-intentioned decisions and what they actually did"),
]

# Named thinkers the digest prompt licenses for Think Positive — used to
# mine rotation memory from recent digests. Keep in sync with the roster in
# shows/prompts/dp_pod_digest.txt (a superset is fine).
_THINKERS = [
    "Tony Robbins", "Simon Sinek", "Viktor Frankl", "Carol Dweck",
    "James Clear", "Angela Duckworth", "Mihaly Csikszentmihalyi",
    "Martin Seligman", "Stephen Covey", "Marcus Aurelius", "Epictetus",
    "Brené Brown", "Cal Newport", "Adam Grant", "Charlie Munger",
]


def _founders_notes() -> str:
    """Operator-supplied REAL material from Dan and Patrick.

    shows/dp_pod_founders_notes.md is the honest answer to the
    no-invented-memories rule: the model may use anything written there as
    the hosts' genuine stories and opinions. HTML comments are stripped; an
    empty file (or comments only) is a clean no-op.
    """
    try:
        path = _ROOT / "shows" / "dp_pod_founders_notes.md"
        if not path.exists():
            return ""
        text = re.sub(r"<!--.*?-->", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
        text = text.strip()
        if not text:
            return ""
        return (
            "FOUNDERS' NOTES (REAL material supplied by Dan and Patrick — "
            "safe to use as their genuine stories, opinions, and phrases; "
            "still never invent anything beyond it):\n" + text
        )
    except Exception as exc:
        logger.warning("dp_pod hook: founders notes unavailable (non-fatal): %s", exc)
        return ""


def _fresh_network_episodes(max_age_days: int = 3, today: datetime.date | None = None,
                            exclude: frozenset = frozenset()) -> str:
    """Real sibling episodes from the last *max_age_days* days.

    Reads each show's committed ``summaries_*.json`` for its latest entry —
    the on-air network pointer must name an actual current episode, never a
    generic show plug. Returns "" when nothing is fresh (never blocks).

    ``exclude`` drops shows picked in the last two days from the candidate
    list entirely. July 31 2026: the July-18 rotation-memory INSTRUCTION
    shipped and was then violated six days running (Planetterrian Daily
    was the pick in Ep019-024 straight, with the ban text present in the
    prompt each time) — same lesson as the fetch filters: filter the
    INPUT, don't instruct the output. A show the model cannot see fresh
    material for is a show it has no episode to point at.
    """
    today = today or datetime.date.today()
    lines = []
    for dir_name, display, _pitch in _NETWORK_SHOWS:
        if display in exclude:
            continue
        try:
            candidates = sorted((_ROOT / "digests" / dir_name).glob("summaries_*.json"))
            if not candidates:
                continue
            data = json.loads(candidates[-1].read_text(encoding="utf-8"))
            summaries = data.get("summaries") or []
            if not summaries:
                continue
            # Newest entry regardless of file ordering (the pipeline
            # prepends newest-first; be robust to either convention).
            latest = max(summaries, key=lambda e: str(e.get("date", "")))
            ep_date = datetime.date.fromisoformat(str(latest.get("date", ""))[:10])
            age = (today - ep_date).days
            if age < 0 or age > max_age_days:
                continue
            title = str(latest.get("episode_title", "")).strip()
            # "Ep 12: <hook>" → keep the hook part for the pointer.
            title = re.sub(r"^Ep\s*\d+:\s*", "", title)
            if not title:
                continue
            when = "today" if age == 0 else ("yesterday" if age == 1 else f"{age} days ago")
            lines.append(f'- {display} ({when}): "{title[:160]}"')
        except Exception:
            continue
    if not lines:
        return ""
    return (
        "FRESH ON THE NETWORK (real sibling episodes from the last few days "
        "— when you point listeners at a show, point at one of THESE actual "
        "episodes and say what it covers; never invent an episode):\n"
        + "\n".join(lines)
    )


def _recent_think_positive_thinkers(max_digests: int = 8) -> str:
    """Thinkers featured in recent Think Positive segments (rotation memory).

    Mined from this show's own committed digests, newest first. Returns ""
    before enough history exists.
    """
    try:
        md_files = sorted((_ROOT / "digests" / "dp_pod").glob("*.md"), reverse=True)
        seen: list[str] = []
        for md in md_files[:max_digests]:
            text = md.read_text(encoding="utf-8")
            m = re.search(r"###\s*Think Positive\s*\n(.*?)(?:\n[━#]|\Z)", text, re.DOTALL)
            if not m:
                continue
            section = m.group(1)
            for name in _THINKERS:
                if name in section and name not in seen:
                    seen.append(name)
        if not seen:
            return ""
        return (
            "THINK POSITIVE — RECENTLY FEATURED THINKERS (newest first; do "
            "NOT reuse any of these today — rotate to someone the show "
            "hasn't heard from lately): " + ", ".join(seen)
        )
    except Exception as exc:
        logger.warning("dp_pod hook: thinker history unavailable (non-fatal): %s", exc)
        return ""


def _recent_levers(max_digests: int = 15) -> str:
    """Actions aired as The Lever recently (rotation memory).

    Aug 10 2026: the daily action converged into week-long runs of one
    lever — solar assessment ×5 (Ep4–8), air-sealing ×4 (Ep10–13),
    plug-in solar ×3, wetland monitoring ×4, then the heat-pump
    assessment SEVEN episodes straight (Ep24–30). The PREVIOUS LEVER
    Dispatch injection was the only lever the model could see each day,
    so it became an attractor. Same lesson as the Network pick and the
    Think Positive thinkers: supply rotation DATA, not just a rotation
    instruction. Mined from this show's own committed digests, newest
    first. Returns "" before enough history exists.
    """
    try:
        md_files = sorted(
            (_ROOT / "digests" / "dp_pod").glob("DP_Pod_Ep*.md"),
            reverse=True,
        )
        seen: list[str] = []
        for md in md_files[:max_digests]:
            text = md.read_text(encoding="utf-8")
            m = re.search(
                r"###\s*The Lever\s*\n(.*?)(?:\n[━#]|\Z)", text, re.DOTALL,
            )
            if not m:
                continue
            lever = re.sub(r"\s+", " ", m.group(1)).strip()
            lever = re.split(r"\bSource:\s*", lever, maxsplit=1)[0].strip()
            # The first sentence is the action statement.
            first = re.split(r"(?<=[.!?])\s+", lever)[0].strip()
            if len(first) < 20:
                continue
            # Sep 4 2026: exact-string dedup let rephrased repeats through
            # ("...enter your postcode, and check" vs "...and sign up")
            # — collapse near-duplicates so the list shows each action
            # once and the ban covers the variant.
            if not any(_lever_similarity(first, s) >= 0.34 for s in seen):
                seen.append(first)
        if not seen:
            return ""
        block = (
            "RECENT LEVERS (actions this show already aired, newest first "
            "— today's Lever must be a genuinely DIFFERENT action: never "
            "repeat, lightly rephrase, or re-skin any action below (a "
            "different website with the same verb and the same outcome is "
            "the same lever), and change the domain from the newest "
            "entries — if recent levers were home energy, go to transport, "
            "food, citizen science, community, health, or repair/reuse "
            "today):\n"
            + "\n".join(f"- {s}" for s in seen)
        )
        # Sep 4 2026 successor-tic guard. The Aug-10 rotation memory
        # stopped exact repeats, and the Lever promptly converged on a new
        # SHAPE instead: "Open your <website> today, enter ..., write down
        # ..." opened 13 of the 26 renewed episodes and 21 of 26 levers
        # were screen lookups. A show whose sign-off is "do something
        # about it" was telling people to open a browser four days in
        # five. Supply the shape data, not just a shape instruction.
        recent = seen[:6]
        verbs: dict[str, int] = {}
        for s in recent:
            v = re.match(r"([A-Za-z\-]+)", s)
            if v:
                verbs[v.group(1).capitalize()] = verbs.get(v.group(1).capitalize(), 0) + 1
        banned_verbs = sorted(v for v, n in verbs.items() if n >= 2)
        screen = sum(1 for s in recent if _SCREEN_ACTION_RX.search(s))
        if banned_verbs:
            block += (
                "\nBANNED OPENING VERBS today (each opened two or more of "
                "the most recent levers): " + ", ".join(banned_verbs)
                + " — today's action starts with a different verb."
            )
        if len(recent) >= 3 and screen * 2 >= len(recent):
            block += (
                f"\nREAL-WORLD ACTION DUE: {screen} of the last {len(recent)} "
                "levers were screen lookups (open a website, search, note a "
                "number). Today's Lever must be done with hands, feet, voice, "
                "or wallet in the physical world — something a listener could "
                "photograph having done — and any screen step in it must END "
                "in a thing booked, sent, signed up for, planted, fixed, or "
                "bought, never in a note."
            )
        return block
    except Exception as exc:
        logger.warning("dp_pod hook: lever history unavailable (non-fatal): %s", exc)
        return ""


_SCREEN_ACTION_RX = re.compile(
    r"\b(open|website|web site|app\b|portal|download|online|search|"
    r"\.gov|\.org|\.com|browser|log in|login|dashboard)\b", re.IGNORECASE,
)
_LEVER_STOP = frozenset(
    "today your that with this from which into then them they have will "
    "the and for one any each every week this local".split()
)


def _lever_similarity(a: str, b: str) -> float:
    """Jaccard similarity on content words (4+ letters, stop-words out)."""
    ta = set(re.findall(r"[a-z]{4,}", a.lower())) - _LEVER_STOP
    tb = set(re.findall(r"[a-z]{4,}", b.lower())) - _LEVER_STOP
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


# Phrases that belong to the fixed furniture (intro/closing pools, segment
# names, the AI disclosure, the Dispatch channel line) — never "bits".
_BANTER_FIXED = (
    "positive papers", "think positive", "the lever", "positive dispatch",
    "do something about it", "perra", "novak", "dp pod",
    "nerranetwork", "nerra network", "voice", "synthesis", "editorial",
    "selection", "our own", "used ai", "ai voice",
    "do positive", "episode", "email", "dispatch", "show page",
    "started counts", "honest sentences", "genuinely struggling",
    "professional help", "rating or review", "doomscroll", "sister show",
    "next listen", "dot com", "network",
)
_BANTER_STOP = frozenset(
    "the a an and or but if so of to in on at for from with by as is are was "
    "were be been being it its this that these those we you they he she i me "
    "my your our their his her them us do does did done not no yes just like "
    "than then there here what which who how when where why all any some one "
    "two three more most very can could would should will shall may might have "
    "has had get got go going come came say said says see saw make made take "
    "took know knew think thought about into over out up down off only also "
    "still even ever never now today yesterday tomorrow day week time way thing "
    "things something anything nothing everything okay right well because "
    "really actually let's dan patrick".split()
)


def _recent_banter_phrases(max_scripts: int = 6, min_hits: int = 3,
                           cap: int = 12) -> str:
    """Running gags calcifying into catchphrases (rotation memory as data).

    Sep 4 2026: the podcast prompt says "no catchphrases, ever" and then
    supplies its own comedy examples — and the model elected exactly
    those: "checklist" in 23 of the 26 renewed episodes, "steel-man" in
    23, "I'll concede" in 17, "preflight" in 10, "chemist brain" in 8.
    Mined from this show's own recent scripts: 2-3 word content phrases
    appearing in *min_hits* of the last *max_scripts* scripts, excluding
    anything that is part of the prompts or the fixed intro/closing
    furniture (so a phrase the prompt itself asks for is never banned).
    Returns "" when nothing recurs.
    """
    try:
        scripts = sorted(
            (_ROOT / "digests" / "dp_pod").glob("DP_Pod_Ep*_tts.txt"),
            reverse=True,
        )[:max_scripts]
        if len(scripts) < min_hits:
            return ""
        furniture = ""
        for rel in ("shows/prompts/dp_pod_podcast.txt",
                    "shows/prompts/dp_pod_digest.txt", "engine/intros.py"):
            p = _ROOT / rel
            if p.exists():
                furniture += " " + p.read_text(encoding="utf-8").lower()
        furniture = re.sub(r"[^a-z'\- ]+", " ", furniture)
        furniture = re.sub(r"\s+", " ", furniture)
        per_script: list[set] = []
        for sp in scripts:
            t = sp.read_text(encoding="utf-8").lower()
            t = re.sub(r"^(dan|patrick):\s*", "", t, flags=re.MULTILINE)
            t = re.sub(r"\[(?:laugh|sigh|breath|pause|long-pause)\]|</?emphasis>", " ", t)
            words = re.findall(r"[a-z][a-z'\-]+", t)
            grams: set[str] = set()
            for k in (2, 3):
                need = 1 if k == 2 else 2
                for i in range(len(words) - k + 1):
                    g = words[i:i + k]
                    if g[0] in _BANTER_STOP or g[-1] in _BANTER_STOP:
                        continue
                    if sum(1 for x in g if x not in _BANTER_STOP) < need:
                        continue
                    grams.add(" ".join(g))
            per_script.append(grams)
        counts: dict[str, int] = {}
        for grams in per_script:
            for g in grams:
                counts[g] = counts.get(g, 0) + 1
        hits = []
        for g, n in counts.items():
            if n < min_hits:
                continue
            if any(f in g for f in _BANTER_FIXED):
                continue
            if g in furniture:
                continue
            hits.append((n, g))
        hits.sort(key=lambda x: (-x[0], x[1]))
        # Collapse a 2-gram that is contained in a listed 3-gram.
        chosen: list[str] = []
        for _n, g in hits:
            if any(g in c or c in g for c in chosen):
                continue
            chosen.append(g)
            if len(chosen) >= cap:
                break
        if not chosen:
            return ""
        return (
            "RETIRED BITS (phrases and running gags that appeared in "
            f"{min_hits}+ of the last {len(scripts)} episodes — a catchphrase "
            "is a bit that stopped being funny; do NOT use these words or "
            "the gag behind them today, and pick a comedic device the show "
            "has not leaned on this week): " + "; ".join(chosen)
        )
    except Exception as exc:
        logger.warning("dp_pod hook: banter history unavailable (non-fatal): %s", exc)
        return ""


# Markers of REAL founders' material (shows/dp_pod_founders_notes.md). If
# none has aired recently the hosts have been running on generic texture.
_FOUNDERS_MARKERS = tuple(re.compile(p, re.IGNORECASE) for p in (
    r"\byukon\b", r"\bwestjet\b", r"\bcollingwood\b", r"\bvancouver\b",
    r"\bcaro\b", r"\balberta\b", r"\bkayak", r"\bpaddl", r"\bdaughters?\b",
    r"\bmountain bik", r"\bsurfing\b", r"\bfoiling\b", r"\bsailing\b",
    r"\bskiing\b", r"\bmodel (?:3|three|y)\b", r"\bsolar on my\b",
    r"\bmy roof\b", r"\bmy panels\b", r"\bmy own payback\b", r"\bnovelist\b",
    r"\bsci-?fi novel", r"\bincubator\b", r"\bplanetterrian ventures\b",
    r"\bbill saved\b", r"\bavvizo\b", r"\blilwords\b", r"\bspent yeast\b",
    r"\bangel invest", r"\bsubstack\b", r"\bmy (?:old )?lab\b",
    r"\benvironmental lab", r"\bcannabis testing\b", r"\bmy (?:own )?cockpit\b",
))


def _founders_detail_nudge(max_scripts: int = 5) -> str:
    """Data-side nudge when the founders' notes have gone unused.

    Sep 4 2026: the notes' pacing rule ("at most one real detail per host
    per episode, only when it serves") was read as "never" — across the
    26 renewed episodes the Yukon race aired 0 times, WestJet 0, Dan's own
    solar payback once. Two friends with real lives were sounding like
    two archetypes. Nudge only when nothing real has aired in the last
    *max_scripts* episodes; the notes remain the only sanctioned source.
    """
    try:
        notes = _ROOT / "shows" / "dp_pod_founders_notes.md"
        if not notes.exists():
            return ""
        if not re.sub(r"<!--.*?-->", "", notes.read_text(encoding="utf-8"),
                      flags=re.DOTALL).strip():
            return ""
        scripts = sorted(
            (_ROOT / "digests" / "dp_pod").glob("DP_Pod_Ep*_tts.txt"),
            reverse=True,
        )[:max_scripts]
        if len(scripts) < max_scripts:
            return ""
        for sp in scripts:
            t = sp.read_text(encoding="utf-8")
            if any(rx.search(t) for rx in _FOUNDERS_MARKERS):
                return ""
        return (
            f"FOUNDERS' DETAIL DUE: no real host material has aired in the "
            f"last {max_scripts} episodes. Today ONE host brings ONE genuine "
            "detail from the FOUNDERS' NOTES below — a real place, a real "
            "past effort, a real number from their own life — at the moment "
            "a story genuinely calls for it, in one or two turns. Still never "
            "invent a single specific beyond what the notes say."
        )
    except Exception as exc:
        logger.warning("dp_pod hook: founders nudge unavailable (non-fatal): %s", exc)
        return ""


def _previous_lever_for_dispatch(max_lookback: int = 5) -> str:
    """The most recent aired Lever — for honest Dispatch continuity.

    Ep2/Ep4 invented a prior-lever callback that never aired. Inject the
    real prior Lever so the digest can only point at something that
    actually happened. Returns "" before Episode 2.
    """
    try:
        md_files = sorted(
            (_ROOT / "digests" / "dp_pod").glob("DP_Pod_Ep*.md"),
            reverse=True,
        )
        for md in md_files[:max_lookback]:
            text = md.read_text(encoding="utf-8")
            m = re.search(
                r"###\s*The Lever\s*\n(.*?)(?:\n[━#]|\Z)", text, re.DOTALL,
            )
            if not m:
                continue
            lever = re.sub(r"\s+", " ", m.group(1)).strip()
            # Drop trailing Source: lines if present.
            lever = re.split(r"\bSource:\s*", lever, maxsplit=1)[0].strip()
            if len(lever) < 40:
                continue
            ep_m = re.search(r"Ep(\d+)", md.name)
            ep_label = f"Ep{int(ep_m.group(1)):03d}" if ep_m else md.stem
            # Keep the first ~40 words so the digest can quote it briefly.
            words = lever.split()
            short = " ".join(words[:40]) + ("…" if len(words) > 40 else "")
            return (
                "PREVIOUS LEVER (the most recent aired action — for the "
                "Dispatch callback ONLY: when the Dispatch has no listener "
                "mail, point at THIS exact lever and never invent a past "
                "action that did not air. Today's Lever section must NOT "
                f"reuse this action — it is yesterday's): [{ep_label}] {short}"
            )
        return ""
    except Exception as exc:
        logger.warning("dp_pod hook: previous lever unavailable (non-fatal): %s", exc)
        return ""


def _latest_first_principles_brief() -> str:
    """Hook + short excerpt of the newest First Principles Daily digest.

    The operator can PIN discussion-anchor material instead: if
    shows/dp_pod_debut_anchor.md exists with content, it wins over the
    latest FP digest — paste any Nerra material there to hand-pick what
    the hosts discuss.
    """
    try:
        pinned = _ROOT / "shows" / "dp_pod_debut_anchor.md"
        if pinned.exists():
            text = re.sub(
                r"<!--.*?-->", "", pinned.read_text(encoding="utf-8"),
                flags=re.DOTALL,
            ).strip()
            if text:
                words = text.split()
                return (
                    "Pinned Nerra Network anchor material (operator-selected):\n  "
                    + " ".join(words[:900])
                )
        fp_dir = _ROOT / "digests" / "first_principles"
        md_files = sorted(fp_dir.glob("*.md"))
        if not md_files:
            return ""
        text = md_files[-1].read_text(encoding="utf-8")
        hook = ""
        m = re.search(r"\*\*HOOK:\*\*\s*(.+)", text)
        if m:
            hook = m.group(1).strip()
        # First ~120 words of body prose after the hook line as the excerpt.
        body = text[m.end():] if m else text
        body = re.sub(r"[━#*]+", " ", body)
        words = body.split()
        excerpt = " ".join(words[:120])
        parts = ["Most recent First Principles Daily episode:"]
        if hook:
            parts.append(f'  Hook: "{hook}"')
        if excerpt:
            parts.append(f"  Excerpt: {excerpt}…")
        return "\n".join(parts)
    except Exception as exc:
        logger.warning("dp_pod hook: FP brief unavailable (non-fatal): %s", exc)
        return ""


def _recently_picked_shows(days: int = 2) -> frozenset:
    """Display names picked in the *days* newest digests — the hard-ban
    set the candidate list excludes (see _fresh_network_episodes)."""
    try:
        display_names = [name for _d, name, _p in _NETWORK_SHOWS]
        md_files = sorted((_ROOT / "digests" / "dp_pod").glob("*.md"), reverse=True)
        banned = set()
        for md in md_files[:days]:
            m = re.search(r"\*\*Network pick:\*\*\s*(.+)",
                          md.read_text(encoding="utf-8"))
            if not m:
                continue
            for name in display_names:
                if name in m.group(1):
                    banned.add(name)
                    break
        return frozenset(banned)
    except Exception as exc:  # noqa: BLE001 — never block a run
        logger.warning("dp_pod hook: pick ban-set unavailable (non-fatal): %s", exc)
        return frozenset()


def _recent_network_picks(max_digests: int = 6) -> str:
    """Shows recommended in recent Network pick lines (rotation memory).

    July 18 2026 network review: without memory, the daily pick converged —
    Fascinating Frontiers was the pick in 5 of 10 episodes including
    consecutive days, mostly voiced by Dan with the same "If you liked X…"
    frame. The prompt already demands variety; this supplies the data.
    Mined from this show's own committed digests, newest first. Returns ""
    before enough history exists.
    """
    try:
        display_names = [name for _d, name, _p in _NETWORK_SHOWS]
        md_files = sorted((_ROOT / "digests" / "dp_pod").glob("*.md"), reverse=True)
        picks: list[str] = []
        for md in md_files[:max_digests]:
            text = md.read_text(encoding="utf-8")
            m = re.search(r"\*\*Network pick:\*\*\s*(.+)", text)
            if not m:
                continue
            line = m.group(1)
            for name in display_names:
                if name in line:
                    picks.append(name)
                    break
        if not picks:
            return ""
        return (
            "RECENT NETWORK PICKS (newest first — do NOT pick any show from "
            "the last two days again today, and vary the recommending host "
            "and the phrasing; the pointer must never become a fixed "
            "one-show beat): " + ", ".join(picks)
        )
    except Exception as exc:
        logger.warning("dp_pod hook: pick history unavailable (non-fatal): %s", exc)
        return ""


def pre_fetch(config, *, episode_num=None, today_str=None) -> dict:
    catalog = "\n".join(f"- {name} — {pitch}" for _dir, name, pitch in _NETWORK_SHOWS)
    sections = [
        "THE NERRA NETWORK (your sibling shows — the network is ad-free and "
        "these are the club's library; describe them with these pitches, "
        "never read this list aloud):",
        catalog,
    ]
    banned_picks = _recently_picked_shows()
    fresh = _fresh_network_episodes(exclude=banned_picks)
    if fresh:
        sections.append("")
        sections.append(fresh)
    if banned_picks:
        sections.append("")
        sections.append(
            "NETWORK PICK HARD BAN (their fresh episodes are withheld "
            "above on purpose): today's Network pick must NOT be "
            + " or ".join(sorted(banned_picks))
            + " — they were the pick in the last two episodes."
        )
    fp_brief = _latest_first_principles_brief()
    if fp_brief:
        sections.append("")
        sections.append(fp_brief)
    thinkers = _recent_think_positive_thinkers()
    if thinkers:
        sections.append("")
        sections.append(thinkers)
    picks = _recent_network_picks()
    if picks:
        sections.append("")
        sections.append(picks)
    recent_levers = _recent_levers()
    if recent_levers:
        sections.append("")
        sections.append(recent_levers)
    prev_lever = _previous_lever_for_dispatch()
    if prev_lever:
        sections.append("")
        sections.append(prev_lever)
    bits = _recent_banter_phrases()
    if bits:
        sections.append("")
        sections.append(bits)
    nudge = _founders_detail_nudge()
    if nudge:
        sections.append("")
        sections.append(nudge)
    notes = _founders_notes()
    if notes:
        sections.append("")
        sections.append(notes)
    out = {"nerra_network_context": "\n".join(sections)}
    # Narrative memory (July 24 2026): longitudinal progress arcs
    # (clean-energy build-out, health progress, conservation recoveries…)
    # so the hosts can call back to how a story has MOVED since the show
    # last covered it. Gated on config.memory_enabled.
    from engine import show_memory
    out.update(show_memory.memory_pre_fetch(config, "dp_pod"))
    return out


def post_generate(config, *, digest_text="", episode_num=None) -> None:
    """Mine theme history + per-program freshness from today's digest."""
    from engine import show_memory
    show_memory.memory_post_generate(
        config, "dp_pod", digest_text or "", episode_num or 0)
