# Directory Audit: `digests/`

> Generated 2026-02-15 as part of the `refactor/engine-extraction` effort.

---

## 1. File Inventory

### 1a. SOURCE CODE (8 files, 545 KB)

| File | Lines | Size | Purpose |
|------|-------|------|---------|
| `digests/tesla_shorts_time.py` | ~4600 | 219 KB | Tesla Shorts Time show runner |
| `digests/omni_view.py` | ~1800 | 86 KB | Omni View show runner |
| `digests/fascinating_frontiers.py` | ~2700 | 120 KB | Fascinating Frontiers show runner |
| `digests/planetterrian.py` | ~2700 | 113 KB | Planetterrian Daily show runner |
| `digests/xai_grok.py` | 112 | 3 KB | Shared xAI/Grok API helper |
| `digests/science_that_changes.py` | ~30 | 1 KB | Legacy/experimental X posting script |
| `digests/verify_account.py` | ~20 | 1 KB | X account verification utility |
| `digests/test_x_api_auth.py` | ~40 | 2 KB | X API authentication test |

### 1b. GENERATED OUTPUT (768 files, 2.22 GB)

#### `digests/` (top-level) -- Tesla Shorts Time + Omni View output

| Pattern | Count | Total Size | Generator |
|---------|-------|------------|-----------|
| `Tesla_Shorts_Time_Pod_Ep*.mp3` | 74 | 1.10 GB | tesla_shorts_time.py |
| `Tesla_Pod_Ep323_*.mp3` | 1 | 5.7 MB | tesla_shorts_time.py (legacy name) |
| `Omni_View_Ep*.mp3` | 24 | 166 MB | omni_view.py |
| `Tesla_Shorts_Time_*.md` | 66 | 589 KB | tesla_shorts_time.py |
| `Tesla_Shorts_Time_*_formatted.md` | 65 | 625 KB | tesla_shorts_time.py |
| `raw_data_*.json` | 66 | 709 KB | tesla_shorts_time.py |
| `raw_data_*.html` | 66 | 868 KB | tesla_shorts_time.py |
| `raw_data_index.html` | 1 | 4 KB | tesla_shorts_time.py |
| `podcast_transcript_*.txt` | 66 | 552 KB | tesla_shorts_time.py |
| `omni_view_transcript_*.txt` | 23 | 224 KB | omni_view.py |
| `credit_usage_*_ep*.json` | 26 | 74 KB | omni_view.py (Tesla has none at top level) |
| `summaries_tesla.json` | 1 | 75 KB | tesla_shorts_time.py |
| `summaries_omni.json` | 1 | 34 KB | omni_view.py |
| `summaries_planet.json` | 1 | 43 KB | planetterrian.py |
| `summaries_space.json` | 1 | 30 KB | fascinating_frontiers.py |
| `Tesla_Shorts_Time_Thumbnail_*.png` | 2 | 6.1 MB | tesla_shorts_time.py |

#### `digests/digests/` -- Legacy Tesla output (path bug)

| Pattern | Count | Total Size | Generator |
|---------|-------|------------|-----------|
| `Tesla_Shorts_Time_Pod_Ep*.mp3` | 6 | 81 MB | tesla_shorts_time.py (early episodes) |
| `Tesla_Shorts_Time_*.md` | 7 | 52 KB | tesla_shorts_time.py |
| `podcast_transcript_*.txt` | 6 | 52 KB | tesla_shorts_time.py |
| `raw_data_index.html` | 1 | 4 KB | tesla_shorts_time.py |

**20 files, 81 MB total.** Created when `digests_dir` was accidentally set to `project_root / "digests" / "digests"` in early script versions.

#### `digests/planetterrian/` -- Planetterrian Daily output

| Pattern | Count | Total Size | Generator |
|---------|-------|------------|-----------|
| `Planetterrian_Daily_Ep*.mp3` | 28 | 122 MB | planetterrian.py |
| `Planetterrian_Daily_*.md` | 30 | 264 KB | planetterrian.py |
| `podcast_transcript_*.txt` | 29 | 234 KB | planetterrian.py |
| `raw_data_*.json` | 30 | 149 KB | planetterrian.py |
| `credit_usage_*.json` | 30 | 81 KB | planetterrian.py |

**147 files, 123 MB total.**

#### `digests/fascinating_frontiers/` -- Fascinating Frontiers output

| Pattern | Count | Total Size | Generator |
|---------|-------|------------|-----------|
| `Fascinating_Frontiers_Ep*.mp3` | 38 | 725 MB | fascinating_frontiers.py |
| `Fascinating_Frontiers_*.md` | 37 | 307 KB | fascinating_frontiers.py |
| `podcast_transcript_*.txt` | 37 | 597 KB | fascinating_frontiers.py |
| `raw_data_*.json` | 37 | 142 KB | fascinating_frontiers.py |
| `credit_usage_*.json` | 0 | 0 | (not generated yet?) |

**149 files, 726 MB total.**

### 1c. Size Summary

| Category | Files | Size | % of digests/ |
|----------|-------|------|---------------|
| MP3 audio | 171 | 2.17 GB | **97.5%** |
| Markdown digests | 205 | 1.8 MB | 0.08% |
| JSON (raw data + credit + summaries) | 163 | 1.2 MB | 0.05% |
| TXT transcripts | 161 | 1.6 MB | 0.07% |
| HTML (raw data) | 68 | 0.9 MB | 0.04% |
| PNG thumbnails | 2 | 6.1 MB | 0.27% |
| **Total Generated** | **770** | **2.18 GB** | **99.97%** |
| Python source | 8 | 545 KB | 0.02% |
| **Total digests/** | **778** | **2.22 GB** | |

---

## 2. Path Dependencies

These are the systems that reference `digests/` paths. Any directory restructuring must update all of them.

### 2a. RSS Feeds (Podcast Player URLs)

All RSS feeds use `raw.githubusercontent.com` URLs pointing to `digests/` paths on the `main` branch. These are consumed by podcast apps (Apple Podcasts, Spotify, etc.) and breaking them means episodes disappear from listeners' feeds.

| RSS Feed | Enclosure URL Pattern |
|----------|----------------------|
| `podcast.rss` | `https://raw.githubusercontent.com/Planetterrian/nerranetwork/main/digests/Tesla_Shorts_Time_Pod_Ep*.mp3` |
| `podcast.rss` (legacy) | `...main/digests/digests/Tesla_Shorts_Time_Pod_Ep32[4-9].mp3` |
| `planetterrian_podcast.rss` | `...main/digests/planetterrian/Planetterrian_Daily_Ep*.mp3` |
| `fascinating_frontiers_podcast.rss` | `...main/digests/fascinating_frontiers/Fascinating_Frontiers_Ep*.mp3` |
| `omni_view_podcast.rss` | `...main/digests/Omni_View_Ep*.mp3` |

**Impact**: HIGH. Moving MP3s breaks all existing podcast episodes for subscribers.

### 2b. GitHub Actions Workflows (`git add` patterns)

Each workflow hardcodes `git add` globs:

| Workflow | `git add` patterns |
|----------|-------------------|
| `daily-podcast.yml` | `digests/*.md`, `digests/*.mp3`, `digests/*.txt`, `digests/raw_data_*.json`, `digests/raw_data_*.html`, `digests/raw_data_index.html`, `digests/summaries_tesla.json` |
| `planetterrian-daily.yml` | `digests/planetterrian/Planetterrian_Daily_*.md`, `...Ep*.mp3`, `.../podcast_transcript_*.txt`, `.../raw_data_*.json`, `.../raw_data_*.html`, `.../credit_usage_*.json`, `digests/summaries_planet.json` |
| `fascinating-frontiers-daily.yml` | `digests/fascinating_frontiers/Fascinating_Frontiers_*.md`, `...Ep*.mp3`, `.../podcast_transcript_*.txt`, `.../raw_data_*.json`, `.../credit_usage_*.json`, `digests/summaries_space.json` |
| `omni-view-daily.yml` | `digests/Omni_View_*.md`, `digests/Omni_View_Ep*.mp3`, `digests/omni_view_transcript_*.txt`, `digests/raw_data_*.json`, `digests/credit_usage_*.json`, `digests/summaries_omni.json` |

**Impact**: MEDIUM. Must update when paths change, but these only affect the feature branch until merged.

### 2c. Python Script Output Paths

Each script constructs output paths using `project_root / "digests" / ...`:

| Script | `digests_dir` definition | Output subdirectory |
|--------|--------------------------|---------------------|
| `tesla_shorts_time.py` | `project_root / "digests"` | `digests/` (flat, top-level) |
| `omni_view.py` | `project_root / "digests"` | `digests/` (flat, top-level) |
| `planetterrian.py` | `project_root / "digests" / "planetterrian"` | `digests/planetterrian/` |
| `fascinating_frontiers.py` | `project_root / "digests" / "fascinating_frontiers"` | `digests/fascinating_frontiers/` |

**Also constructed in scripts**: RSS feed `<enclosure url="...">` URLs using `https://raw.githubusercontent.com/Planetterrian/nerranetwork/main/digests/...`

### 2d. HTML Pages

| Page | References |
|------|------------|
| `index.html` | `./digests/raw_data_index.html` (link to raw data archive) |
| `planetterrian.html` | No direct `digests/` references |
| `fascinating_frontiers.html` | No direct `digests/` references |
| `omni-view.html` | No direct `digests/` references |

### 2e. Utility Scripts

| Script | References |
|--------|------------|
| `rebuild_rss.py` | `digests_dir.rglob("Tesla_Shorts_Time_Pod_Ep*.mp3")` + markdown lookups in `digests/` and `digests/digests/` |
| `backfill_omni_ep001_audio.py` | `ROOT / "digests" / "summaries_omni.json"`, `ROOT / "digests" / "Omni_View_Ep001_20260123.mp3"` |
| `post_digest.py` | Runs `python digests/tesla_shorts_time.py` etc. via subprocess |

---

## 3. Structural Issues

### 3a. Inconsistent Layout Across Shows

| Show | MP3 location | All output in subdir? |
|------|-------------|----------------------|
| Tesla | `digests/` (top-level, flat) | No -- mixed with source code |
| Omni View | `digests/` (top-level, flat) | No -- mixed with source code |
| Planetterrian | `digests/planetterrian/` | Yes -- clean separation |
| Fascinating Frontiers | `digests/fascinating_frontiers/` | Yes -- clean separation |

Tesla and Omni View dump everything into the same `digests/` directory as the Python source files. Planetterrian and Fascinating Frontiers already use subdirectories.

### 3b. Legacy `digests/digests/` Path Bug

Early Tesla episodes (Ep324-329, Nov 20-25, 2025) were written to `digests/digests/` due to a path construction bug. The RSS feed still references these files at their legacy paths. `rebuild_rss.py` handles both paths. **20 files, 81 MB.**

### 3c. Duplicate `_formatted.md` Files

There are 65 `Tesla_Shorts_Time_*_formatted.md` files that appear to be identical copies of the corresponding `Tesla_Shorts_Time_*.md` files. No other show produces `_formatted.md` variants. **~625 KB of duplication.**

### 3d. Summaries JSONs Live at Wrong Level

All four `summaries_*.json` files live at `digests/` top-level, not in their respective show subdirectories (Planetterrian/FF have subdirs but their summaries don't live there). This is because the GitHub Pages HTML files at repo root reference them as `digests/summaries_*.json`.

---

## 4. Recommended New Structure

### 4a. Separate Source from Output

```
nerranetwork/
├── src/                              # ALL source code (NEW)
│   ├── shows/
│   │   ├── tesla_shorts_time.py
│   │   ├── omni_view.py
│   │   ├── planetterrian.py
│   │   ├── fascinating_frontiers.py
│   │   └── __init__.py
│   ├── engine/                       # Shared modules (NEW, from refactor)
│   │   ├── tts.py
│   │   ├── xai_grok.py
│   │   ├── rss.py
│   │   └── ...
│   └── utils/
│       ├── science_that_changes.py
│       ├── verify_account.py
│       └── test_x_api_auth.py
│
├── output/                           # ALL generated output (NEW)
│   ├── tesla/
│   │   ├── Tesla_Shorts_Time_Pod_Ep*.mp3
│   │   ├── Tesla_Shorts_Time_*.md
│   │   ├── podcast_transcript_*.txt
│   │   ├── raw_data_*.json
│   │   ├── raw_data_*.html
│   │   ├── credit_usage_*.json
│   │   └── summaries_tesla.json
│   ├── planetterrian/
│   │   ├── Planetterrian_Daily_Ep*.mp3
│   │   ├── Planetterrian_Daily_*.md
│   │   ├── podcast_transcript_*.txt
│   │   ├── raw_data_*.json
│   │   ├── credit_usage_*.json
│   │   └── summaries_planet.json
│   ├── frontiers/
│   │   ├── Fascinating_Frontiers_Ep*.mp3
│   │   ├── Fascinating_Frontiers_*.md
│   │   ├── podcast_transcript_*.txt
│   │   ├── raw_data_*.json
│   │   ├── credit_usage_*.json
│   │   └── summaries_space.json
│   └── omni/
│       ├── Omni_View_Ep*.mp3
│       ├── Omni_View_*.md
│       ├── omni_view_transcript_*.txt
│       ├── credit_usage_*.json
│       └── summaries_omni.json
│
├── assets/                           # KEEP (static assets, voice prompts)
├── docs/                             # Documentation
├── .github/workflows/                # Updated to reference new paths
├── *.rss                             # RSS feeds (keep at root)
├── *.html                            # Web players (keep at root)
└── ...
```

### 4b. Migration Constraints

Moving files is tricky because of the RSS feed URLs. Here are the options:

**Option A: Keep `digests/` as the output directory name (least disruption)**

Rename `digests/` to keep it as the output directory but move source code out:

```
src/shows/*.py          # Source code moves here
digests/                # Stays as output-only directory
  tesla/                # (rename from flat layout)
  planetterrian/        # (already exists)
  fascinating_frontiers/ # (already exists)
  omni/                 # (new subdir for Omni View)
```

- RSS feed URLs for Planetterrian and Fascinating Frontiers **stay unchanged**.
- Tesla RSS URLs change from `digests/Tesla_*.mp3` to `digests/tesla/Tesla_*.mp3` -- existing episodes need URL redirects or RSS feed entries updated.
- Omni View URLs change similarly.

**Option B: Symlink bridge**

Move everything to `output/` but create a `digests/` symlink for backward compatibility. GitHub raw file serving respects symlinks in some cases but not reliably.

**Option C: `digests/` stays, just organize it (safest for existing subscribers)**

Keep `digests/` as the output root. Move only source code out. Don't reorganize existing output files -- just ensure **new** episodes go into show-specific subdirectories.

```
src/shows/*.py          # Source code moves here
digests/                # Output only
  Tesla_Shorts_Time_Pod_Ep323-404_*.mp3  # Legacy files STAY
  Omni_View_Ep001-024_*.mp3             # Legacy files STAY
  tesla/                                 # NEW episodes go here
  planetterrian/                         # Already correct
  fascinating_frontiers/                 # Already correct
  omni/                                  # NEW episodes go here
```

RSS feeds would keep old `<enclosure>` entries pointing to legacy paths and new entries using the new subdir paths. This is the safest option for podcast subscribers.

### 4c. Recommended Approach

**Option C** is recommended for the refactoring phase:

1. Move source code to `src/` -- clean separation, no subscriber impact.
2. Keep existing generated files in place -- zero RSS breakage.
3. Configure new episodes to write into show-specific subdirectories under `digests/`.
4. Update workflows to match new script locations and `git add` patterns.
5. After refactor stabilizes, optionally consolidate legacy flat files into subdirs with an RSS migration.

### 4d. Files to Clean Up (No Dependencies)

These can be safely removed -- they have no external references:

| File(s) | Reason |
|---------|--------|
| `digests/digests/` (entire directory) | Legacy path bug. RSS already references these at their paths, but `rebuild_rss.py` can reconstruct. Keep RSS entries, delete duplicates if desired. |
| `Tesla_Shorts_Time_*_formatted.md` (65 files) | Appear to be duplicate copies of the plain `.md` files. No workflow, script, or HTML references them. |
| `Tesla_Shorts_Time_Thumbnail_*.png` (2 files) | Only 2 thumbnails ever generated (Ep338-339). Not referenced by RSS or HTML. |
| `raw_data_index.html` | Referenced by `index.html` but could be regenerated. Low value. |

---

## 5. What Must Update When Source Code Moves

| System | Current Reference | Must Change To |
|--------|-------------------|----------------|
| All 4 workflows | `working-directory: ./digests` + `python3 *.py` | `working-directory: ./src/shows` + `python3 *.py` |
| `post_digest.py` | `python digests/tesla_shorts_time.py` | `python src/shows/tesla_shorts_time.py` |
| Each Python script | `project_root = script_dir.parent` | `project_root = script_dir.parent.parent` (two levels up from `src/shows/`) |
| Each Python script | `digests_dir = project_root / "digests"` | No change (output stays in `digests/`) |
| `rebuild_rss.py` | `digests_dir = project_root / "digests"` | No change (scans output dir) |
| Python `__file__` paths | Scripts derive `env_path`, `project_root`, etc. from `__file__` | Must verify after moving |
