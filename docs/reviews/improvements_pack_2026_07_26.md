# Network improvements pack — 2026-07-26

Implements as much as possible of the ranked listener-experience + acquisition
list from the July 25 feedback session. Companion to PR #878 (EpN / SpaceX
stage / MIT NaN / Mission Control).

## Shipped in this pack (code)

| # | Item | What changed |
|---|------|----------------|
| 1 | Digest depth | PT + UC + MAB opt into `digest_expand_below_target`; PT Science Deep Dive word target + thin-day LENGTHEN (digest + podcast) |
| 2 | YouTube title loop | RU-channel hints + stopword scrub (months/shorts/time); `channel=` wired into title bundle |
| 3 | Multi-platform Shorts | Tesla + SpaceX `multi_platform_enabled: true` (safe-zone + sidecar); IG/TikTok auto-post still **false** |
| 5 | Template de-seeds | FP Russian opener/closer bans; MIT “exact scenario…” tic ban |
| 6 | Cross-show handoffs | BEAT OWNERSHIP bullets on PT / FF / Tesla / SpaceX digests |
| 7 | Reader transcripts | `*_reader.txt` pre-pronunciation; blog prefers it over `_tts.txt` |
| 8 | Smart Shorts | Already network-wide — no change |
| 10 | MIT quote resilience | ^IXIC multi-source: history → fast_info → Yahoo v8 |
| 11 | Continuity budget | Tesla + M&A digests + digest-expansion retry aligned to ≤1 |
| 12 | SpaceX specificity | Beat ownership + named-hardware reminder (stage rule from #878) |
| 13 | Video podcast | FF enabled as third pilot |
| 14 | Gallery CTA | Shorts/IG/TikTok captions link `gallery.html` |
| 15 | Scheduler | Verified SLOTS ↔ CRON_MAP — no drift |
| 16 | Push recovery | `safe-commit-push` recovery hatch; nightly + restock opt in |
| 17 | Mission Control DRY | Covers prefer `rss_image` from dashboard JSON |

⚠️ **A/B-listen required** for prompt/audio-affecting rows: digest expand opt-ins,
PT/FF/Tesla/SpaceX/FP/MIT prompt edits, continuity budget, reader-transcript
path is metadata-only (blog text).

## Remaining — operator / external (cannot be finished by code alone)

### P0 — do these next

1. **A/B-listen the prompt pack**  
   Next episodes of FF, PT, UC, MAB, Tesla, SpaceX, FP (RU), MIT.  
   Revert specific prompt files via git if a show regresses (landmine #17).

2. **Arm IG Reels + TikTok auto-post**  
   - Complete Meta app review + TikTok Content Posting audit.  
   - Set secrets: `IG_ACCESS_TOKEN`, `IG_USER_ID`, `TIKTOK_ACCESS_TOKEN`.  
   - Flip per show: `instagram_enabled: true` / `tiktok_enabled: true` under
     `youtube:` (Tesla/SpaceX already generate local `_social.mp4` + sidecars).  
   - Doc: `docs/social_distribution.md`.

3. **Submit Apple Podcasts video shows**  
   Tesla + SpaceX feeds already exist; FF now builds
   `fascinating_frontiers_podcast.video.rss`.  
   In Apple Podcasts Connect, create a **separate** video show per feed
   (`docs/video_podcasts.md`). Enabling YAML alone does not list on Apple.

4. **Age of AI bootstrap (external)** — follow `docs/age_of_ai_plan.md`:  
   Supabase project + migration → Voximplant scenario + number → Cloudflare
   Worker secrets + deploy → Cal.com event + webhook → GitHub `VOICES_*` /
   `VOXIMPLANT_*` secrets → consent/apology clips on R2 → dry-run call →
   soft launch → phase-8 flip `newsletter` / `youtube` / `x` in
   `shows/age_of_ai.yaml`. Keep topic queue empty.

### P1 — high impact, mostly operator decisions

5. **Confirm X handles + turn on cross-promo where missing**  
   OV / M&A / MIT / FPD need confirmed `@handles` before
   `publishing.x_cross_promo` replies are useful. Set `publishing.x_handle`
   and `x_enabled: true` only when the X app + account are ready.

6. **DP Pod distribution**  
   When Ep1+ quality is locked: flip `newsletter.enabled` and/or
   `youtube.enabled` in `shows/dp_pod.yaml`. Watch EN quota + cadence
   (landmine #20). Do not enable X until a handle exists.

7. **Expand video podcast after Apple accepts FF**  
   Next candidates with daily long-form: MIT, Planetterrian. Same pattern:
   `video_podcast.enabled: true` + Connect submit.

8. **Multi-platform for more shows**  
   After Tesla/SpaceX social assets look good for a week, enable
   `multi_platform_enabled: true` on FF/MIT (still keep auto-post false
   until secrets work).

### P2 — product / editorial follow-through

9. **Digest depth still plateauing?**  
   If PT/UC/MAB still ship under floors after a week of expand-retries,
   raise `min_digest_words` or deepen Cosmic/Science/Engineering deep-dive
   targets further — do **not** loosen podcast invent/pad bans.

10. **Third-gen tic monitoring**  
    Re-run `scripts/review_snapshot.py` on OV/EI/MAB after 7–10 episodes;
    score the July network-review predictions. Apply any remaining proposed
    de-seeds only under A/B.

11. **YouTube Studio “Test & Compare”**  
    Title variants are already stashed — enable the Studio feature so
    thumbnails/titles A/B on the live channel.

12. **Gallery traffic push**  
    Code now links gallery from Shorts/social captions; optionally pin a
    rotating discovery line in long-form descriptions more often via
    `engine/network_promo.py` weighting.

### P3 — ops hygiene

13. **Deploy Cloudflare scheduler worker** if not already live  
    (`workers/scheduler/` — landmine #24). Cron fallback remains.

14. **Regenerate dashboard.json** (nightly) so Mission Control show links +
    `rss_image` covers pick up PR #878 + this pack.

15. **Backfill `*_reader.txt` for recent episodes** (optional)  
    Historical blog posts still use `_tts.txt`. A one-shot script could
    copy pre-garble text from digests if an archive of pre-TTS scripts
    exists; otherwise only new episodes benefit.

## Drift guards

`tests/test_improvements_pack_2026_07_26.py` plus updates in
`test_social_distribution.py`, `test_video_podcast.py`.
