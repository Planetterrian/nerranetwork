First post-launch quality pass: format guardrails mostly hold on ep9–18, but every recent script is under the 1300-word floor, Progress Watch still narrates empty days, and coverage swings as low as 51%—fix via digest/coverage substrate and empty-section omission, not podcast word-pressure.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.0958**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| episodes (first 7) with an item whose subject is outside Europe and carries no stated consequence inside it | hit | ep9–18 leads/ATR are Europe-primary or state in-region consequence; no clear off-desk lead in the sampled window |
| Mira claims a body, a home, a trip or an event witnessed (transcript read) | hit | ep9–18 only AI-host self-ID + closing synthesis disclaimer; no body/home/witness claims |
| Both Sides states or implies which side is stronger, or picks a party, government or people | hit | ep10–18 Both Sides segments keep dual strongest-form framing without an endorsed winner |
| Progress Watch carries a promise or announcement of intent instead of a measured result | partial | measured beats exist (ep9 inspections, ep12 Lloyds test, ep15 facility payout, ep17 IP +5.8%) but empty days are still narrated and some Progress lines stay one-sentence thin |
| Across the Region episodes (first 7) carrying an Also Today section on days with >= 8 qualifying articles | hit | ep9–18 transcripts/chapters routinely include an Also Today block when the rundown has short items |
| episodes with a Lead sourced only to x.com | hit | sampled leads credit France 24/Euronews/Guardian/Al Jazeera etc.; no x.com-only lead heard in ep9–18 |
| digest_lints_fired_after_retry non-empty | partial | no lint telemetry in snapshot; clean chapters + stable section shape, but not mechanically proven ≤1/7 |
| desk digest words vs min_digest_words on days with >= 12 full-text articles | miss | 10/10 podcast scripts still under 1300 words; ep16 coverage 51% shows digest/utilization not meeting launch length expectation |
| leads credited to a syndication carrier rather than the wire | hit | ep9–18 leads name primary outlets/wires; Mighty-790-style carrier credit not observed in this window |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/_shared/omni_desk_podcast_body.txt`** (prompt) — ep11/14/18 narrate empty Progress and still burn a chapter span; honesty is keeping silence, not performing the absence (P1.2).
```diff
- Progress Watch section guidance that still allows a spoken ‘no measured progress today’ beat so the chapter hinge can fire
+ If no measured, finished result exists in the digest, omit Progress Watch entirely — do not say that nothing qualifies, that a sign of progress does not appear, or that the day had none. Only speak Progress Watch when reporting a concrete measured result (count, payment, completed test, recorded rate). Never use announcements, pledges, or future intent.
```

**`shows/prompts/_shared/omni_desk_digest_body.txt`** (prompt) — Keeps digest→podcast aligned so the podcast has nothing to apologize for; pairs with existing progress_watch_thin lint.
```diff
- Progress Watch block that can render a thin/empty placeholder after progress_watch_thin considerations
+ Omit the Progress Watch heading entirely when no measured result is available; never write a ‘none today’ stub. progress_watch_thin should only judge substance when the section is present.
```

**`shows/prompts/_shared/omni_desk_podcast_body.txt`** (prompt) — ep16 coverage 51% and ep10 hook cov 22% show under-utilization of digest substrate while scripts still miss 1300 — fix coverage, not podcast expand (P1.1/P1.3).
```diff
- Story-selection guidance that allows dropping digest developed items / Also Today lines without an explicit coverage duty
+ Coverage duty (no word counts, no length targets spoken or aimed): every developed digest item and every Also Today line must appear in the script in some wording; if time is tight, shorten sentences — do not delete a digest story. The cold-open’s concrete fact must be restated in the Lead body.
```

**`shows/prompts/_shared/omni_desk_podcast_body.txt`** (prompt) — ep9 diesel Both Sides ran as a US price story with Europe as afterthought — region rule says consequence-inside-Europe first (P1.4).
```diff
- Both Sides framing without an explicit first-sentence in-region stake requirement
+ Both Sides: first sentence states the stake inside the desk’s region. If the only hinge is incidental (e.g. another capital asking Europe to supply a commodity), choose a different contested question from today’s digest. Give each side its strongest reason; never imply a winner.
```

## Code/metadata-only proposals (no A/B needed)
- **`shows/omni_view_europe.yaml`** (config): Length category rule: digest-substrate only. Scripts are 10/10 under 1300; confirm digests before touching podcast knobs (P1.1).
- **`tests/test_omni_view_europe_quality_pass.py`** (code): Every behavioral fix needs a drift-guard; tolerate today’s in-flight episode shape (Sep 2026 guard lesson).
- **`engine/chapters or desk chapter post-process (wherever Lead headline chapters are assigned for omni desks)`** (code): P1.5 scrubber consistency; chapters-only — no audio rewrite if markers already align to speech.

## Deferred (carried forward)
- Desk-specific music theme (still on OmniView.mp3 bed) — operator commission
- Second Nerra Daily edition assembled from regional desks — operator audience gate
- Re-grade Europe feed list from a Actions runner via check_feeds.py
- YouTube enable for Omni View Europe — plan §7 data decision
- Directory/submission and cross-promo weighting while OP3 first-week median is 0
- Podcast-side expand-below-target or higher min_podcast_words prompt pressure — network length do_not_retry class
- Phonetic respellings for TTS/Whisper name garble — landmine #17

<sub>tokens: 32342 in / 5192 out</sub>