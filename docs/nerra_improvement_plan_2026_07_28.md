# Nerra Network — Comprehensive Improvement Plan

**For:** Claude Code sessions working in `Planetterrian/nerranetwork`
**Prepared:** 28 July 2026, from a full log review, live-feed audits, and the incident history of the past week.
**Goal:** the best listener and operator experience possible, working reliably and reproducibly, with costs known and bounded.

---

## How to work in this repo (read first — every landmine here has already fired once)

1. **Absence is never zero.** Apple suppresses metrics it won't disclose; shows with no listening have no row; a missing analytics source means "not measured." Rendering any of these as `0` is the repo's signature bug — it has now been fixed in three separate places (`fetch_apple_stats.py`, `engine/apple_reporter.py`, dashboard). Never reintroduce it.
2. **Generated files do not go in patches or per-show commits.** `*.video.rss`, `network.rss`, `blog.rss`, `blog/index.html` are build output. The show job excludes them (see `scripts/push_show_artifacts.sh`); the nightly's `build_video_feeds.py --all` owns video feeds. Including one in a commit caused the 28 July four-show stranding.
3. **Feeds are churn-suppressed.** A rebuild that differs only by `<lastBuildDate>` must not write. When editing templates, use Jinja whitespace control (`{%- -%}`) — a stray blank line churns all 30 show pages.
4. **`--ours`/`--theirs` invert between rebase and merge.** Tests in `tests/test_push_show_artifacts.py` pin this. Don't touch conflict-resolution code without running them.
5. **Analytics must degrade, never raise.** Every fetcher returns errors as data (`result.error`), keeps yesterday's file rather than writing an empty one, and no-ops cleanly when secrets are unset.
6. **Run the full suite and compare against pristine main.** Baseline has a known failure set (`test_tesla_hook`, `test_lang_dub`, `test_youtube*` — missing-dependency related). New failures are yours; the baseline is not.
7. **feedgen quirks:** it has no `itunes_keywords` setter (inject XML after writing — see `inject_channel_keywords`), and entry `itunes_image` requires URLs ending `.jpg`/`.png` (the gallery bucket writes `.jpeg`, which fails).
8. **libass caption sizes are not pixels.** `FontSize` scales by `1080/288 = 3.75`. FontSize=26 ≈ 98px on screen. Comparison renders exist in the July 2026 history before changing this.
9. **Costs are real.** ~$0.32/episode across 16 daily shows. Every extra LLM retry, image, or render minute multiplies by ~480 runs/month. Weigh additions accordingly.

---

## P0 — Correctness bugs listeners can see

### P0-1. "Nerra" transcribed as "Nara" everywhere Whisper runs
**Where:** `engine/transcripts.py` (~line 107) — `model.transcribe()` is called with no `initial_prompt`, so Whisper has never been told the brand vocabulary. Verified damage: 34 committed transcript files contain "Nara", "Naran Network", "Naranetwork.com". Because SRT captions and YouTube CC tracks derive from these transcripts, the wrong brand name is **burned into published videos** and served via `<podcast:transcript>` on both audio and video feeds.

**Fix, in three layers:**
1. **Prevention** — pass `initial_prompt` to `model.transcribe()` with the show vocabulary: `"Nerra Network, nerranetwork.com, Starship, Starlink, xAI, Grok"` plus per-show terms (pull show name + `keywords:` from the show YAML). faster-whisper biases decoding toward prompt vocabulary; this is the supported mechanism.
2. **Post-pass correction** — a deterministic substitution table applied to segment text *after* transcription, preserving word timings: `Nara Network→Nerra Network`, `Naran Network→Nerra Network`, `Naranetwork→Nerranetwork`, `Nara network`→ etc. Case-preserving, word-boundary anchored so "Naranja" never matches. Put it in `engine/transcripts.py` as `_BRAND_CORRECTIONS`, unit-tested with the real strings found in the committed files.
3. **Backfill** — a one-shot script (`scripts/fix_transcript_brand.py`) that rewrites the 34 affected `*_transcript.json` + `*_transcript.txt` files in place (text fields only — never timestamps), commits them, and reports what changed. The RSS `<podcast:transcript>` URLs point at these files, so the fix is live the moment it's pushed. Do NOT regenerate audio or re-render videos for back catalog — cost is not justified; forward episodes get clean captions automatically.

**Acceptance:** grep for `Nara` across `digests/*/*transcript*` returns only legitimate words; a new episode's transcript contains "Nerra Network"; test pins the correction table against the observed misspellings (`Nara`, `Naran`, `Naranetwork`).

### P0-2. Blog "Sources" cards are Google News redirects, not publishers
**Where:** `engine/blog.py` — `_extract_source_urls()` captures whatever URL the digest carries. For Google News-fed shows that is `news.google.com/rss/articles/CBMi...` redirect URLs. The rendered card shows the Google favicon, the label "news.google.com", and a link through Google's redirector. The reader never learns the actual publisher; the pages leak PageRank to a redirector; and if Google changes the redirect format the links die.

**Fix:**
1. **Resolve at digest time, not blog time** — in `engine/fetcher.py`, when an article arrives from a Google News feed, resolve the redirect to the publisher URL once (HEAD/GET with redirect-follow, short timeout, cache by URL) and store the final URL in the article record. Then every downstream consumer (digest `Source:` lines, blog cards, YouTube descriptions) inherits the real link.
2. **Blog-side fallback** for existing digests: when a source URL matches `news.google.com/rss/articles/`, attempt resolution at blog build; on failure keep the redirect link but label the card with the *story's* publisher if the digest text names it.
3. **Backfill:** a script that re-resolves sources in existing blog posts' Sources sections (bounded: last ~60 posts; older ones on demand). Respect robots-safe fetching: only follow redirects, never scrape content.
4. **Audit test:** for each of the 5 most recent posts per show, assert every source card's domain ≠ `news.google.com` unless resolution genuinely failed, and every `Source:` URL in the digest appears in the blog's Sources section (the June 2026 regex fix in `blog.py:59-68` shows this has silently broken before).

**Acceptance:** new episode's blog post shows publisher domains + favicons; a validation test fails if >30% of a post's sources are unresolved redirects.

### P0-3. Cost tracking reports half of real spend
**Where:** `engine/tracking.py` has no image accounting; `engine/grok_imagine.py` logs `cost=$0.08` per batch but never reports it. The credit summary said `$0.161` on a run that actually spent ~$0.32. Also the digest tokens land in a bucket labeled "X Thread" even on runs with zero X calls.
**Fix:** add an `Images (grok-imagine)` line to the tracker fed from `grok_imagine.py` (count × unit cost, unit in one constant); rename/split the mislabeled bucket so digest, podcast, outline, and titles report separately; include video render minutes as an informational line (count, not dollars). The per-episode `credit_usage_*.json` schema gains keys — keep old keys for dashboard compatibility.
**Acceptance:** the run-end summary total matches the sum of all logged costs including images; a test feeds synthetic events and asserts the total.

---

## P1 — Money and time waste (no quality change)

### P1-1. One wasted digest generation per run on under-provisioned shows
SpaceX generates at `max_tokens: 4000`, truncates, retries at 6000 — a thrown-away 37s call, every day. **Fix:** audit `metrics_*.json` / logs for shows that hit the truncation retry ≥3 of the last 7 runs and raise their `max_tokens` to the retry ceiling (output tokens bill on production, so headroom on non-truncating runs costs nothing). Then check the expansion retry too: SpaceX did truncate-retry *and then* expansion-retry (3 digest calls). If the word-count target consistently needs expansion, raise the target in the prompt instead of paying for a second pass.

### P1-2. Single-pass video render
The render is 42% of a video show's wall clock (3m27s slideshow + 5m20s composite) and still encodes twice. Build the Ken Burns + xfade + overlays + subtitles as **one** filter graph in `engine/video.py` (the stage-1 output feeds `[0:v]` of stage 2 today; inline it). Expected: ~3.5 min/episode saved × 5 video shows daily, and the last generational loss gone. **Guardrails:** keep the two-stage path as fallback behind a config flag for one week; verify with ffprobe (resolution/fps/chapters/duration) plus extracted-frame comparison; the hybrid b-roll path (`_render_hybrid_slideshow`) must keep working.

### P1-3. Feeds that fail every single run
- Reddit RSS 429s from Actions IPs on every run (`r/SpaceXLounge`, `r/LocalLLaMA`). Replace with old.reddit JSON endpoints w/ proper UA, or drop them; a feed that fails 100% of the time is pure log noise and retry latency.
- Gallery CDN: every library-image fetch 403s on `gallery.nerranetwork.com` and falls back to authenticated R2 (slower; happens up to 16×/render since the blend raise). Fix the bucket/custom-domain public-access config; add a startup probe that warns loudly when the CDN 403s so regressions are seen same-day.

### P1-4. Newsletter false-green
Every run: preflight prints "Buttondown API key validated successfully," then the send fails with `email_invalid: configure a custom sending domain`. Either configure the sending domain in Buttondown (operator task — decide if the newsletter is wanted) or make the preflight check `requires_verification`/sending-domain state and **skip cleanly** with one line instead of failing at the end of every pipeline. A permanent known failure trains people to ignore warnings.

---

## P2 — Listener experience & acquisition

### P2-1. Wire the official Apple data into the dashboard
`api/apple_reporter.json` (official, token-auth, accumulating daily history) exists but `management.html` still reads the cookie-scrape file. Add Reporter as the primary Apple source with per-source `provenance` + `fetched_at` badges; cookie data becomes fallback, labeled as such; absent metrics render as "—", never 0. After ~3 weeks of accumulated history, compare sources and retire the cookie path (`appleconnector` dep, 2 secrets, the daily re-auth chore).

### P2-2. Chart-input flywheel (follows, completion)
Apple ranks on listening, follows, completion. Concrete levers already half-built:
- **Badge:** drop Apple's official lockup at `assets/badges/listen-on-apple-podcasts.svg` (download from marketing toolbox — cannot be redrawn); every show page upgrades its text chip automatically (template + tests shipped July 2026).
- **Completion:** the Listener Value Score already flags weak narrative continuity (SpaceX Ep47 scored 4.1/10 with "add why-this-matters framing"). Feed the score's suggestions back into the show's prompt memory automatically when a show scores <5 twice in a week, instead of only logging them.
- **Episode artwork:** confirm per-episode square art (shipped 28 July) is appearing in Apple's episode list for new episodes; it makes the episode rail visually distinct vs. 30 identical tiles.

### P2-3. CC / auto-translation audit
Run `python scripts/check_youtube_caption_scope.py` where the `YOUTUBE_*` secrets live (CI one-off job is fine). If any channel lacks `youtube.force-ssl`, every upload on it has **no CC track and no auto-translation** — a silent, standing reach loss across all videos. Fix = re-consent + replace refresh-token secret.

### P2-4. Transcript & chapters surfacing on the site
Transcripts and chapters are committed and in the feeds, but the site's episode pages don't link them. Add a "Transcript" link + chapter list to blog posts/episode pages (data already on disk at build time — zero new generation cost). Good for accessibility, SEO (long-tail text), and time-on-page.

### P2-5. Search Console reality check
JSON-LD `sameAs` now populated; sitemap exists. One-time operator task: verify nerranetwork.com in Google Search Console, submit the sitemap, and check the blog posts are indexing. Costs nothing; the blog is the acquisition surface and nobody has confirmed Google sees it.

---

## P3 — Operational hygiene

- **Recovery-branch janitor:** the 4 merged `recovery/*` branches (and any future ones) should be auto-deleted after their commits reach main. Add to nightly: for each `recovery/*` branch whose tip is an ancestor of main, delete it; alert if any recovery branch is >24h old and unmerged (that's a stranded episode).
- **Storage prune on schedule:** `scripts/prune_video_r2.py` monthly (Actions cron with existing R2 secrets), keeping the video keyspace at its ~52 GB steady state instead of 318 GB/yr growth.
- **Apple Reporter token rotation:** token expires ~late January 2027. Add expiry date to `docs/analytics.md` + a nightly warning when `apple_reporter.json.fetched_at` goes stale >3 days (dead token is the most likely cause).
- **Repo-root strays:** `_to_delete/`, `recovered_ep519/`, `recovered_spacex_ep12/` — confirm contents recovered, then remove.
- **Ruff lint gate:** red on main since before July 22. Either fix the violations or scope the gate to changed files; a permanently red check trains everyone to ignore CI.
- **Podcast Index duplicate:** stale "Tesla Shorts Time Daily" entry still listed; deduplicate via PI support form.
- **Full-network review cadence:** add a monthly checklist doc (feeds valid via podba.se/validate, apple status per show, OP3 vs Apple vs Spotify sanity, storage growth, cost/episode trend from the now-correct tracker).

---

## Suggested execution order

| Phase | Items | Rationale |
|---|---|---|
| 1 | P0-1, P0-2, P0-3 | Listener-visible wrongness + the numbers you budget with |
| 2 | P1-1, P1-3, P1-4 | Pure waste, low risk, small diffs |
| 3 | P2-1, P2-3, P2-4 | Uses data already generated; biggest UX return |
| 4 | P1-2 | Highest-value but highest-risk change; do alone, verify hard |
| 5 | P2-2, P2-5, P3 | Growth + hygiene, steady drip |

**Definition of done, every phase:** full test suite green vs. baseline; no generated files in the patch; churn-suppression verified (rebuild produces byte-identical unchanged outputs); costs of any new API call quantified in the commit message; and the commit message records *why*, in the style of the existing history — future sessions rely on it.
