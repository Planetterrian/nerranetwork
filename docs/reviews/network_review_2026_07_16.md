# Network pass — 2026-07-16 (audio forensics + YouTube post-policy + listener experience)

Operator request: (1) review/improve the YouTube pipeline, (2) find and fix
the audible hisses and ticks in recent episodes, (3) review latest transcripts
for listener-experience improvements, (4) merge open PRs + cleanup.

## 1. Audio: hisses + ticks — measured root cause and fix

Forensics on downloaded episodes (ffmpeg → PCM → windowed FFT):

- **Hiss:** high-frequency energy DURING SPEECH rose ~2-3 dB between the
  Jul 1-2 and Jul 16 episodes on two independent shows (Tesla 6-10 kHz
  −47.1 → −44.4 dBFS; FF −46.1 → −44.2) while the 1-4 kHz voice core stayed
  flat. The repo's audio chain was unchanged in that window → the drift is
  upstream **Grok TTS output**.
- **Ticks:** rare hard clicks measured in DP Pod Ep012 (216.9 s / 491.9 s —
  the dialogue multi-call path); 0-1 elsewhere.

**Fix (`engine/audio.py`):** `adeclick,afftdn=nr=9:nf=-42:tn=1` inserted into
`_voice_norm_full_cmd` between the band-limits and loudnorm (so makeup gain
can't re-amplify measured noise). Efficacy verified on Tesla Ep543 before
shipping: 1-4 kHz untouched (−28.9 → −28.9), 6-10 kHz restored to the Jul-1
reference (−44.4 → −46.8 vs ref −47.1), 10-14 kHz −56.4 → −61.0. Opt-out:
`audio.voice_denoise: false` (AudioConfig field; restores the exact
pre-change chain, drift-guarded in `tests/test_audio_commands.py`).
**Landmine #17: A/B-listen the first post-merge episode on 2-3 shows.**
Preview: `ffmpeg -i <ep>.mp3 -af "adeclick,afftdn=nr=9:nf=-42:tn=1" out.mp3`.

## 2. YouTube pipeline (post-policy verification, Jul 14-16)

Adaptive policy **working as designed**: hysteresis advancing (MIT D→C, UC
B→C confirmed; RU FF promoted back to A, RU PR to B), C-tier shows skip the
long-form with the Short still shipping 1/1, A-tier keeps long + 2 Shorts
(Tesla ships 2/2; FF/SpaceX often 1/2 because the smart selector finds <2
qualifying windows — a selector-tuning item, not a policy bug).

Defects found + fixed:

- **P0 — committed conflict markers in `site/data/gallery-manifest.json`**
  (Jul 16 18:03 nightly): `safe-commit-push`'s `git pull --rebase
  --autostash || true` swallowed an autostash-pop conflict and committed the
  conflicted file — every Jul-17 render would have parsed `{}` and silently
  killed the gallery blend. Manifest repaired (2,989 images);
  `safe-commit-push` now refuses to commit any staged file containing
  conflict markers (restores from origin/main + `::warning::`). Drift guard:
  `tests/test_safe_commit_push.py`.
- **RU dub titles still legacy-truncated** on all Jul 14-16 uploads: the
  publish step had no `GROK_API_KEY` in its env, so title translation failed
  silently every run. Env fixed + drift-guarded.
- **Blend observability:** `gallery_library` now logs one loud
  `BLEND DEGRADED` line naming the first concrete download failure (the
  Jul 2-10 silent `scene_library_count: 0` class); RU dub scene downloads
  gained the public-CDN-403 → authenticated-R2 fallback.

## 3. Multilingual duplicate-run class (recovery PRs #819-#830)

The 6 recovery PRs were **duplicates, not lost work**: a queued multilingual
run's `github.sha` is frozen at trigger time, so it can miss a sibling run's
just-pushed artifacts (observed 6 s stale), re-translate the episode, and hit
a deterministic add/add rebase conflict 8/8 attempts. Worse, each raced run
also **uploaded a duplicate public RU video to @NerraRU**. Fixed by checking
out `ref: main` in the translate job. All 6 PRs closed with per-PR analysis.

**Operator action — delete these duplicate videos in YouTube Studio
(@NerraRU),** none are referenced by main's records:
`W2p7z0nC8fk`, `AAi_MDhKqCw`, `Z-yrH9wm6Bs`, `qDg_mhuxAvI`, `3yuWWZAP4ts`,
`KUUAX4A62dE`, `HbGd7MDs2I0`, `ewwT6iIUcHU`, `201vAdCW7N4`, `G67ujK_jap4`.

## 4. Listener-experience pass (Jul 3-16, ~160 episodes)

Full findings in the session report. Shipped fixes:

- **SpaceX Ep034 class (P0):** the whole Engineering Deep Dive spoke twice
  verbatim (~90 s). The Jul-2 dedup only covered expansion-retry output; the
  final script now gets the same conservative near-duplicate strip (≥8-word
  sentences, 0.85 similarity) before TTS, with a
  `final_script_dup_sentences_removed` metric.
- **PR Ep060 P0 («Я есть яблоко» glossed "I eat an apple"):** hard grammar
  rules added to both PR prompts (conjugation table for «есть», infinitive
  never means "I eat", fix-the-plan's-errors instruction). Recurrence of the
  Jul-2 Ep043 class on a show whose product is correct Russian.
- **OV "Both sides agree" (escalated into audio, 5×/episode):** the literal
  template was seeded by the digest prompt itself — de-seeded by shape in
  both prompts, banned as a verbatim frame, "sides" require a genuine named
  disagreement.
- **EI bundle:** "There's a nuance here worth understanding" was the
  prompt's own first rotation example (5/6 episodes) — rotation menu
  replaced with shape descriptions + verbatim ban; "Tomorrow, watch for…"
  cadence lie fixed to cadence-neutral teasers; thin-day multi-telling
  capped (one story anchors ≤2 sections).
- **DP Pod:** `$8,000–$15,000` range garble fixed (comma-aware price-range
  patterns in `assets/pronunciation.py`); colon-less mid-turn
  "Source goodnewsnetwork.org" scrub added; daily "No dispatches in the bag
  today" empty-state demoted to at-most-weekly.
- **Weekly-summary segment is a silent no-op** (both July Sundays: metrics
  recorded `True`, zero recap language aired on any show). Now detected —
  honest `weekly_summary_segment_effective` metric + loud warning.
  Structural enforcement (regen) deferred: prompt-level, A/B-gated.
- **MAB orphan Closings (5/14):** two causes — the fixed-length network
  outro tail pushed the real sign-off below the 85 % `where: end` window on
  short scripts (engine fix: end window floored at last 250 words), and the
  "That **is** it for today" no-contraction variant missed the marker
  (pattern widened). All 5 orphan episodes re-parse with Closing.
- **Outro fatigue:** the single ~40-word network cross-promo frame was
  verbatim in 146/176 episodes — now 4 date-deterministic rotating frames
  (one deliberately short), offset per show. **A/B-listen.**
- **PT astronomy leaks:** `^asteroid` → `\basteroids?\b` (mid-title leak)
  and web-search articles now pass through `exclude_title_patterns`
  (they bypassed the RSS-only filter — the Ep116 exoplanet route).
- **Tooling:** snapshot checker accepts «Завершение»/«Прощание»/"Sign-Off"
  as Closings (was English-only → false-flagged every FP episode);
  PR `word_of_day_history` backfilled with 7 pre-tracking WOTDs (closes the
  «хлеб» repeat hole).

Deferred (unchanged rationale): chronic under-length (digest ceiling, four-
show A/B), digest-driven chapter titles, M&A "tracked since episode N-1"
callback residual (1 instance), SpaceX "open questions" memory-echo tic,
FPD "on the order of" plateau, DP monologue-relapse/one-sentence-turn ratio
(prompt-level, needs its own pass), smart-Shorts selector second-window
tuning.
