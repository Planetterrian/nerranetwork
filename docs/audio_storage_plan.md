# Audio Storage Plan

> Generated 2026-02-15. Analyzes the 2.2 GB of MP3 files committed to the Git
> repository and recommends a storage strategy.

---

## 1. Current Situation

### 1a. Repository Size

| Metric | Value |
|--------|-------|
| `.git` directory (pack files) | 2.2 GB |
| Working tree (all files) | 4.4 GB |
| MP3 files in working tree | 2.17 GB (171 files) |
| MP3s as % of `.git` | ~100% (MP3s don't delta-compress) |

The `.git/objects/pack` directory is a single 2.2 GB pack file. Since MP3s are
already compressed audio, git's delta compression provides no benefit — each
episode is stored at full size in the pack.

### 1b. MP3 Inventory by Show

| Show | Episodes | Total Size | Avg Size | Growth/Day |
|------|----------|------------|----------|------------|
| Tesla Shorts Time | 75 (+6 legacy) | 1.21 GB | 15.0 MB | ~15 MB |
| Fascinating Frontiers | 38 | 725 MB | 19.1 MB | ~20 MB |
| Omni View | 24 | 166 MB | 6.9 MB | ~7 MB |
| Planetterrian Daily | 28 | 122 MB | 4.3 MB | ~4.5 MB |
| Music (root) | 5 | 22 MB | — | 0 |
| **Total** | **171** | **2.24 GB** | **13.1 MB** | **~47 MB** |

No individual file exceeds 50 MB (GitHub's warning threshold). The largest
episode is 37 MB (Fascinating Frontiers Ep011).

### 1c. Growth Projections

| Timeframe | New Data | Cumulative Repo Size |
|-----------|----------|---------------------|
| Current | — | 2.2 GB |
| 3 months | +4.2 GB | ~6.4 GB |
| 6 months | +8.5 GB | ~10.7 GB |
| 12 months | +16.9 GB | ~19.1 GB |

**At current growth rate, the repo will hit GitHub's 5 GB "strong recommendation"
threshold within 2 months and the 10 GB hard limit within 6 months.**

### 1d. Who Downloads These Files?

The MP3s are served via `raw.githubusercontent.com` URLs embedded in RSS feeds.
The consumers are:

1. **Podcast apps** (Apple Podcasts, Spotify, Overcast, etc.) — fetch MP3s when
   subscribers play or download episodes
2. **RSS validators** — Apple Podcasts Connect, Spotify for Podcasters validate
   feed entries by fetching enclosures
3. **Web players** — the GitHub Pages site links to episodes
4. **`git clone`** — every developer or CI clone downloads ALL 2.2 GB of MP3s
   (past + present) because they're in git history

We have no visibility into actual download traffic since GitHub doesn't expose
raw.githubusercontent.com analytics. But even with zero podcast listeners, every
`git clone` is a 2.2 GB download that will grow to 19 GB within a year.

---

## 2. Options Analysis

### 2a. Git LFS — REJECTED

Git LFS stores large files in a separate backend while keeping pointer files
in the repository.

**Fatal problem: LFS breaks the RSS feed URLs.**

| URL Domain | LFS Behavior |
|------------|-------------|
| `raw.githubusercontent.com/.../*.mp3` | Returns the **130-byte pointer file**, not the audio |
| `media.githubusercontent.com/media/...` | Returns actual content (different URL format) |

Every RSS `<enclosure>` URL currently uses `raw.githubusercontent.com`. Migrating
existing files to LFS would silently break every episode for every subscriber —
podcast apps would download a tiny text file instead of audio.

Additionally:
- GitHub Pages does **not** natively serve LFS files (returns pointer)
- Free tier: 1-10 GB bandwidth/month (varies by billing model) — could be
  exceeded by podcast downloads
- LFS bandwidth counts against the **repo owner's** account

**Verdict: LFS is unsuitable as a primary solution.** It could be used for
*new* files if we also change the URL scheme in RSS feeds, but that defeats
the purpose since we'd need a URL migration anyway.

### 2b. External Object Storage — RECOMMENDED

| Provider | Storage $/GB/mo | Egress $/GB | 5 GB + 150 GB BW | Custom Domain |
|----------|----------------|-------------|-------------------|---------------|
| **Cloudflare R2** | $0.015 | **$0** | **$0** (free tier) | Trivial |
| Backblaze B2 + CF | $0.006 | **$0** (via CF) | ~$0 | Moderate setup |
| AWS S3 | $0.023 | $0.09 | ~$4.80/mo | Complex (CloudFront) |
| DigitalOcean Spaces | flat $5/mo | included (1 TB) | $5.00/mo | Easy |

**Cloudflare R2 is the clear winner:**
- **Free right now**: 10 GB storage + 10M reads/month + zero egress fees
- **$0.76/month at 50 GB**: still essentially free at 12-month scale
- **No egress fees ever**: a viral episode costs $0 in bandwidth
- **Custom domain + HTTPS**: add your domain in Cloudflare dashboard, done
- **S3-compatible API**: easy to script uploads from GitHub Actions

The URL would change from:
```
https://raw.githubusercontent.com/Planetterrian/nerranetwork/main/digests/Tesla_Shorts_Time_Pod_Ep404_20260215.mp3
```
to something like:
```
https://audio.teslashortstime.com/tesla/Tesla_Shorts_Time_Pod_Ep404_20260215.mp3
```

### 2c. GitHub Releases — VIABLE ALTERNATIVE

| Metric | Value |
|--------|-------|
| Max file per release asset | 2 GiB |
| Max assets per release | 1,000 |
| Total release storage | **Unlimited** |
| Bandwidth | **Unlimited, free** |
| URL format | `https://github.com/{owner}/{repo}/releases/download/{tag}/{file}` |
| URL stability | Stable (302 redirects to CDN) |

**Pros:**
- Free, unlimited storage and bandwidth
- Stays within the GitHub ecosystem (no external accounts)
- Stable, permanent URLs
- Upload via `gh release upload` in CI

**Cons:**
- URL includes a redirect (302 → `objects.githubusercontent.com`) — most
  podcast apps handle this fine, but some older clients may not
- No custom domain possible
- GitHub controls the CDN behavior (Content-Type, caching headers)
- Not designed for this use case — could change terms
- Organizational overhead: need a release-per-episode or batch scheme

**Verdict: Good "free forever" fallback if R2 is overkill or undesirable.**

### 2d. Keep As-Is — UNSUSTAINABLE

The repo will hit GitHub's hard 10 GB limit within ~6 months. Even before
that, clones become painfully slow. Every CI run (GitHub Actions) clones the
full repo including all MP3 history.

**Not viable beyond 2-3 months without intervention.**

---

## 3. URL Migration Constraints

Any solution that changes URLs must update these systems:

### 3a. RSS Feeds (HIGHEST RISK)

| Feed | Episodes | Current URL Pattern |
|------|----------|-------------------|
| `podcast.rss` | 79 | `raw.githubusercontent.com/.../digests/Tesla_Shorts_Time_Pod_Ep*.mp3` |
| `podcast.rss` (legacy) | 6 | `raw.githubusercontent.com/.../digests/digests/Tesla_Shorts_Time_Pod_Ep32*.mp3` |
| `omni_view_podcast.rss` | 24 | `raw.githubusercontent.com/.../digests/Omni_View_Ep*.mp3` |
| `planetterrian_podcast.rss` | 28 | `raw.githubusercontent.com/.../digests/planetterrian/Planetterrian_Daily_Ep*.mp3` |
| `fascinating_frontiers_podcast.rss` | 38 | `raw.githubusercontent.com/.../digests/fascinating_frontiers/Fascinating_Frontiers_Ep*.mp3` |
| **Total** | **175** | |

**Risk**: Changing URLs in RSS feeds causes podcast apps to treat episodes as
"new" items if the GUID changes (ours use non-URL GUIDs, so this should be
safe). However, podcast apps that have already cached the old URL will attempt
to re-download from the new URL. If the old URL stops working, previously
downloaded episodes may show as unavailable in some clients.

**Mitigation**: Keep the old files in the repo (or on LFS) during a transition
period so both old and new URLs work simultaneously.

### 3b. Python Scripts (URL Construction)

Each script constructs RSS enclosure URLs:

| Script | Line(s) | Pattern |
|--------|---------|---------|
| `tesla_shorts_time.py` | ~3895-3960, 4383, 4586 | `{base_url}/digests/{mp3_filename}` |
| `omni_view.py` | ~1564, 1763 | `{base_url}/digests/{audio_file.name}` |
| `planetterrian.py` | ~1541, 1695, 2595 | `{base_url}/digests/planetterrian/{mp3_filename}` |
| `fascinating_frontiers.py` | ~2616, 2706 | `{base_url}/digests/fascinating_frontiers/{mp3_filename}` |

`base_url` is `https://raw.githubusercontent.com/Planetterrian/nerranetwork/main`

These must be updated to point to the new storage URL for new episodes.

### 3c. GitHub Actions Workflows

Each workflow has `git add digests/*.mp3` steps. With external storage, MP3s
would be uploaded to R2/Releases instead of git-added. The workflow steps need
to change from:

```yaml
git add digests/*.mp3
```
to:
```yaml
# Upload to R2 bucket
aws s3 cp digests/*.mp3 s3://bucket/show/ --endpoint-url $R2_ENDPOINT
```

### 3d. Utility Scripts

| Script | Impact |
|--------|--------|
| `rebuild_rss.py` | Scans `digests_dir.rglob("*.mp3")` to find episodes — needs to also check R2 or use a manifest |
| `generate_voice_prompt.py` | Takes MP3 path as CLI arg — needs local copy (download from R2) |
| `backfill_omni_ep001_audio.py` | References specific MP3 path — one-time script, probably never runs again |

### 3e. GitHub Pages (index.html)

Only links to `raw_data_index.html`, not directly to MP3s. **No impact.**

---

## 4. Recommendation

### Phase 1: Stop the Bleeding (Immediate)

**Add `.gitattributes` to track new MP3s with LFS — but don't migrate existing
files.** This prevents the repo from growing further while we set up external
storage.

```gitattributes
# Track new MP3 files with LFS (prevents repo growth)
*.mp3 filter=lfs diff=lfs merge=lfs -text
```

Wait — this has a problem. New MP3s tracked by LFS would have
`raw.githubusercontent.com` URLs that return pointer files, breaking RSS.

**Revised Phase 1:** Instead, add MP3s to `.gitignore` and upload them to R2
from the workflow. This way they never enter git at all.

```gitignore
# Audio files are stored on Cloudflare R2, not in git
digests/**/*.mp3
```

But this breaks the existing workflow where scripts write MP3s locally and
workflows `git add` them. We need Phase 2 ready before we can do Phase 1.

**Actual Phase 1: Set up R2 bucket and upload workflow, in parallel with
existing git storage.** New episodes get uploaded to BOTH git and R2. RSS feeds
point to R2 for new episodes. This is a safe, reversible transition.

### Phase 2: Migrate (1-2 weeks)

1. **Create Cloudflare R2 bucket** with a custom domain
   (e.g., `audio.teslashortstime.com`)

2. **Upload all existing MP3s to R2:**
   ```bash
   # One-time bulk upload
   aws s3 sync digests/ s3://podcast-audio/tesla/ \
     --exclude '*' --include '*.mp3' \
     --endpoint-url https://<account>.r2.cloudflarestorage.com
   # Repeat for planetterrian/, fascinating_frontiers/, and Omni View
   ```

3. **Update Python scripts**: Change `base_url` from
   `https://raw.githubusercontent.com/.../main` to
   `https://audio.teslashortstime.com`

4. **Update RSS feeds**: Write a migration script that rewrites all
   `<enclosure url="...">` entries in the four RSS files to use the new
   domain. Keep the same path structure:
   ```
   OLD: https://raw.githubusercontent.com/.../main/digests/Tesla_Shorts_Time_Pod_Ep404_20260215.mp3
   NEW: https://audio.teslashortstime.com/tesla/Tesla_Shorts_Time_Pod_Ep404_20260215.mp3
   ```

5. **Update workflows**: Replace `git add digests/*.mp3` with R2 upload
   using `aws s3 cp` or the `cloudflare/wrangler-action` GitHub Action.
   Add R2 credentials as repository secrets.

6. **Verify**: Validate all RSS feeds with Apple Podcasts Connect validator
   and Spotify's podcast validator.

### Phase 3: Clean Up (After Verification)

1. **Add MP3s to `.gitignore`** so new episodes don't enter git

2. **Keep existing MP3 files in the repo temporarily** (don't delete from
   git history yet) — this ensures old `raw.githubusercontent.com` URLs
   still work as a fallback during the transition

3. **After 30 days with zero issues**: Remove MP3 files from the working
   tree (not from git history — that requires `git filter-repo` which is
   destructive)

4. **Optional (later)**: Use `git filter-repo` to rewrite history and
   remove all MP3s from the pack file. This shrinks the repo from 2.2 GB
   to ~50 MB but is a force-push that invalidates all existing clones.
   Only do this if the repo size is causing real problems.

### Phase 2 Alternative: GitHub Releases (No External Account)

If setting up a Cloudflare account is undesirable, GitHub Releases work:

1. **Create a release per episode** (or batch per day):
   ```bash
   gh release create "tesla-ep404-20260215" \
     digests/Tesla_Shorts_Time_Pod_Ep404_20260215.mp3 \
     --title "Tesla Shorts Time Ep404"
   ```

2. **URL format**: `https://github.com/Planetterrian/nerranetwork/releases/download/tesla-ep404-20260215/Tesla_Shorts_Time_Pod_Ep404_20260215.mp3`

3. Same RSS migration process, just different URL format.

**Trade-off**: Longer, less clean URLs. No custom domain. Dependent on GitHub
not changing release asset serving. But: zero setup cost and zero monthly cost.

---

## 5. Cost Comparison Summary

| Approach | Monthly Cost | Setup Effort | URL Migration | Risk |
|----------|-------------|--------------|---------------|------|
| **Cloudflare R2** | **$0** (now) → $0.76 (year 1) | Medium (1-2 hrs) | Required | Low |
| GitHub Releases | $0 forever | Low (30 min) | Required | Medium (platform risk) |
| Backblaze B2 + CF | $0-0.35 | Medium-High | Required | Low |
| Git LFS | $0-5/mo | Low | **Breaks existing URLs** | **High** |
| Keep as-is | $0 | None | None | **Critical** (hits limit in ~6 mo) |

---

## 6. Decision Matrix

| Criterion | Weight | R2 | Releases | B2+CF | LFS | As-Is |
|-----------|--------|-----|----------|-------|-----|-------|
| Cost | 15% | 5 | 5 | 5 | 3 | 5 |
| URL stability | 25% | 5 | 4 | 5 | 1 | 5 |
| Setup simplicity | 15% | 4 | 5 | 3 | 4 | 5 |
| Scalability | 20% | 5 | 4 | 5 | 3 | 1 |
| Custom domain | 10% | 5 | 1 | 4 | 1 | 1 |
| GitHub ecosystem | 15% | 3 | 5 | 2 | 5 | 5 |
| **Weighted Score** | | **4.6** | **4.2** | **4.1** | **2.8** | **3.4** |

---

## 7. Recommended Plan

**Primary: Cloudflare R2 with custom domain.**

Rationale:
- Free at current scale, under $1/month at 12-month scale
- Zero egress fees protects against surprise costs from viral episodes
- Custom domain gives professional, portable URLs
- S3-compatible API integrates easily with GitHub Actions
- If Cloudflare becomes unacceptable later, the S3-compatible API means
  migrating to B2 or S3 is a config change, not a rewrite

**Fallback: GitHub Releases** if external storage is ruled out.

**Timeline:**
- Week 1: Set up R2 bucket, custom domain, upload existing MP3s
- Week 2: Update scripts + workflows to dual-write (git + R2)
- Week 3: Update RSS feeds to use R2 URLs, validate with podcast platforms
- Week 4: Stop committing MP3s to git, add to .gitignore
- Month 2+: Monitor, then optionally clean git history
