# SpaceX Daily — quality review (2026-06-18)

Second scheduled review. Five more episodes have shipped since the
2026-06-13 pass (Ep3 weekly-recap, Ep4–7 normal dailies), so the deferred
levers now have real n.

Evidence: `scripts/review_snapshot.py spacex` (ep lengths, repeated-phrase
detector, cost, OP3), `shows/spacex.yaml`, all four prompts,
`shows/hooks/spacex.py`, `engine/chapters.py`, the last 7 `_tts.txt` scripts
+ Whisper transcripts + `chapters_ep00*.json`, the digests, the trackers,
`spacex_podcast.rss`, and `tests/test_spacex_show.py`. OP3 now shows
**31 downloads / 7d** (first real audience signal).

## Scoring the 2026-06-13 predictions

- **Theme history no source-label tokens — HIT.** Top recurring themes are
  now all real (`data center` 8, `starship`/`starlink`/`falcon`/`launch` 5,
  `elon musk` 4, `full flow`/`flow staged` 3). No `google`/`news`/`com`/
  `gov`/`reddit` token in the top 30.
- **`tf` → tons-force, 0 letter-spellings — HIT.** `tf` appears only in the
  pre-fix Ep2 `_tts.txt`; no `T F` in any Ep3–7 transcript.

## P0 — listener-facing bug shipping today

### Weekly-recap episodes ship with NO Closing chapter (orphan-closing) — SHIPPED FIX
`digests/spacex/chapters_ep003.json` (the **committed** chapters the podcast
app shows) is `['Introduction', 'The Engineering Angle', 'Tomorrow Teaser',
'Market Watch']` — **no Closing**. Ep3's sign-off is
`"…And that's a wrap on today's SpaceX developments. S P C X closed at one
hundred sixty dollars… See you next time."` The code-supplied closing block
(`shows/hooks/spacex.py:_price_sentence`) appends the SPCX price into the
sign-off, and the **Market Watch** marker
(`S ?P ?C ?X (closed|is at|is trading|opened)`) matches that price phrase.
Market Watch was listed **before** Closing, so under first-marker-per-line the
sign-off was titled **Market Watch** and the real Closing was orphaned.

Daily episodes escaped it only because their *real* Market Watch segment
consumes that marker first (once-per-title) — but weekly recaps have no
separate Market Watch segment, so the price-only sign-off was the marker's
sole match. This is the exact orphan-closing class fixed on EI/OV/MAB/FP/UC,
and precisely the risk the 2026-06-13 review flagged as the blocker on the
price-twice item.

**Fix:** reorder the `Closing` marker **before** `Market Watch` in
`shows/spacex.yaml` so Closing (pinned `where: end`) wins the sign-off line.
Verified across all 7 committed scripts: Ep3 gains its Closing chapter; every
daily keeps **both** Market Watch and Closing — zero regression. Metadata-only
(chapters.json), **no audio change**. Drift guards:
`TestClosingBeforeMarketWatch` (3 tests).

## P1 — quality ceiling (documented; not shipped this pass)

### Engineering Deep Dive under-delivers its own spec → chronic under-length
4 of the last 5 normal episodes ship under the 1300-word floor (Ep3 956,
Ep4 851, Ep5 999, Ep6 1117; Ep7 1364). Root cause is the digest ceiling — the
podcast tracks the digest, and digests run 736–1243w. The lever is the
**Engineering Deep Dive**, the prompt's own "flagship section" and stated
"length lever," explicitly licensed to use the model's own engineering
knowledge (so it is NOT digest-source-capped). But it under-delivers its own
spec: the digest prompt asks for "3 paragraphs of 4–6 sentences each"
(~250–360w), while the actual deep dives run **Ep4 181w, Ep5 147w, Ep6 140w,
Ep7 276w** — roughly half, on 3 of 4.

**Deferred, not shipped:** expanding the deep dive is the network-wide
length lever that `CLAUDE.md` keeps deferred **pending the operator's
four-show length A/B** (FF June-16 note). That reason still holds, so per the
playbook it stays deferred — but the new evidence (the deep dive is short
against its *own* per-section spec, not just the global target) makes this the
single highest-value lever the moment the A/B settles. Recommended attack:
give the deep-dive section an explicit word floor (~280–340w) in both the
digest and podcast prompts; A/B-listen.

### SPCX price number spoken twice every episode — chapter blocker now cleared
Still 7/7 (Ep7: "a quick market note: SPCX is at $191.82" in Market Watch
**and** "SPCX is trading at $191.82" in the closing). The 2026-06-13 review
deferred the fix because dropping the Market Watch price risked the
orphan-closing regression. **This pass's P0 reorder removes that blocker** —
with Closing now ahead of Market Watch, the sign-off keeps its Closing chapter
regardless of the price phrase. So a future pass can safely make the Market
Watch note **qualitative** (direction + why, no repeated number), leaving the
single precise quote to the closing. Not shipped here: the reorder just
landed; observe Ep8+ to confirm chapters stay clean before touching the
audio prompt. Audio-affecting when done → A/B.

## P2 / monitor

- **Tomorrow-teaser frame "Watch for the [first/next] <test> to <purpose>"**
  is now 5/7 (refueling test, hot-fire, earnings, static-fire ×2). Content
  varies, but the frame is hardening into a template. Monitor; if it becomes
  a dead rotation, rotate the teaser opener in the podcast prompt (low-risk,
  no chapter dependency).

## Resolved / not findings (verified)

- **Hook jargon (Idiot Index unglossed)** did **not** recur — Ep4–7 hooks
  lead with concrete engineering claims (Raptor 3 shutdowns, Shotwell's
  target, orbital refueling).
- **"from an engineering standpoint" (6/7) and "on the AI front" (5/7)** are
  **REQUIRED chapter-marker anchors** by design (podcast prompt lines 88, 91,
  "vary everything after it") — not tics. Left unchanged (cf. MAB "pop the
  hood").
- **"i'm patrick and vancouver" (5/7)** is a Whisper mishear — the `_tts.txt`
  correctly says "I'm Patrick **in** Vancouver". No bug.
- **AI & Compute chapter lumping** (2026-06-13 deferred) did **not** recur —
  chapters are clean Ep4–7.

## Hard guardrails honored
No R2/RSS-enclosure changes, no MP3s, no `min_articles_skip` default change,
no TTS-coupled-field flips, no voice/provider changes, no phonetic
respellings, no posting/sending/uploading/paid APIs. The shipped fix is
metadata-only (chapter marker order) — no audio change, no A/B required.

## Tests
`tests/test_spacex_show.py` (49, incl. 3 new), `test_network_quality_pass.py`,
`test_chapters.py`, `test_prompt_fidelity.py`, `test_episode_validity.py` —
all pass (208).
