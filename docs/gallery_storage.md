# Nerra Gallery — Storage Layer (Phase 1)

This document covers the Cloudflare R2 bucket layout, access policy, and
metadata schema that back the network's image gallery.

The gallery surface (per-show galleries, network-wide browse page,
email-gated downloads) is added in later phases. Phase 1 ships only
the **durable storage + sidecar metadata + upload helper + pipeline
hook** — without any of those, later phases have nothing to read.

## Bucket

* **Name:** `nerra-gallery` (override with the env var
  `R2_GALLERY_BUCKET` if you need a separate dev bucket).
* **Account:** same Cloudflare R2 account that hosts the audio bucket
  (`podcast-audio`). Credentials are reused — no new R2 token is
  provisioned.
* **Region:** `auto` (Cloudflare R2 default).

The gallery bucket is **separate from the audio bucket** so that:

* The audio bucket's path conventions (URLs published in every RSS
  enclosure since 2025) can never collide with gallery objects.
* Gallery-specific lifecycle rules, CORS, and public-access policies
  can be tuned in isolation.

## Access policy

| Object class | Access |
|---|---|
| `*.thumb.webp` | **Public read** (custom domain `gallery.nerranetwork.com`) |
| `*.jpeg` / `*.png` / originals | **Private** — Worker-issued signed URLs only |
| `*.json` sidecars | **Public read** (consumed client-side by the gallery JS) |

Thumbnails carry a subtle bottom-right watermark
("nerranetwork.com") so they remain useful for preview but discourage
casual scraping in lieu of an email-gated download. Originals are
clean. See `engine.gallery_uploader._apply_watermark` for the exact
rendering.

The network-wide manifest (`/site/data/gallery-manifest.json`) is
**built in Phase 2**, not Phase 1.

## Path layout

```
{show-slug}/{YYYY-MM-DD}/{episode-id}/{image-id}.{ext}
{show-slug}/{YYYY-MM-DD}/{episode-id}/{image-id}.thumb.webp
{show-slug}/{YYYY-MM-DD}/{episode-id}/{image-id}.json
```

* `show-slug` matches the show's `slug` field in its YAML config
  (`tesla`, `models_agents_beginners`, etc.).
* `episode-id` is `ep{episode_num:03d}` (matches the existing
  `scenes_ep<NNN>` convention).
* `image-id` is the first 12 hex characters of the SHA-256 of the
  original image bytes — content-addressed, so re-runs against the
  same bytes are idempotent (same key, same object).

## Sidecar metadata schema

Every uploaded image gets a JSON sidecar at the same prefix. The
schema is pinned by the `ImageMetadata` dataclass in
`engine/gallery_uploader.py`:

```json
{
  "image_id": "string (12 hex chars)",
  "show_slug": "string",
  "show_name": "string",
  "episode_id": "string (e.g. ep042)",
  "episode_title": "string",
  "episode_date": "YYYY-MM-DD",
  "prompt": "string (empty for backfilled / non-AI images)",
  "model": "string (Grok Imagine model identifier)",
  "generated_at": "RFC 3339 UTC timestamp",
  "intended_use": "thumbnail | segment_card | social | other",
  "width": 0,
  "height": 0,
  "format": "jpeg | png | webp",
  "file_size": 0,
  "caption": "string",
  "tags": ["string", "..."],
  "license": "CC BY-SA 4.0",
  "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
  "attribution": "Nerra Network",
  "youtube_video_id": "string (optional)"
}
```

The license is **CC BY-SA 4.0** by default (attribution to Nerra
Network, derivatives must use the same license). Per-image overrides
are allowed via the `ImageMetadata.license` / `license_url` fields if
a specific image needs different terms.

## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `R2_GALLERY_BUCKET` | Gallery bucket name | `nerra-gallery` |
| `R2_GALLERY_PUBLIC_BASE_URL` | Public URL prefix for thumbnails / sidecars (e.g. `https://gallery.nerranetwork.com`) | empty → falls back to the R2 endpoint URL |
| `R2_ENDPOINT_URL` | Shared R2 endpoint (existing — reused from audio) | — |
| `R2_ACCESS_KEY_ID` | Shared R2 access key (existing) | — |
| `R2_SECRET_ACCESS_KEY` | Shared R2 secret key (existing) | — |

When any of `R2_GALLERY_BUCKET`, `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`,
or `R2_SECRET_ACCESS_KEY` is unset, the upload helper silently
returns `None` and the pipeline continues as if the gallery feature
isn't installed. **Phase 1 is operationally a no-op in
unconfigured environments.**

## Pipeline integration

`engine/gallery_uploader.py` exposes:

* `gallery_config_from_env()` — load `GalleryConfig` from env vars.
* `upload_image(image_bytes, metadata, *, gallery_config=None)` —
  upload original + thumbnail + sidecar; returns an `UploadResult`
  on success or `None` on any soft failure.
* `make_thumbnail(image_bytes, *, max_edge=800, watermark=True)` —
  re-encode + downscale + watermark; useful for backfill scripts.
* `compute_image_id(image_bytes)` — content-hash stem.

The pipeline hook lives at the tail of `_run_grok_path` inside
`run_show.py:_publish_youtube`. Every Grok-Imagine scene whose
filename matches `grok_NN.jpeg` is uploaded with its corresponding
prompt index, and the call is wrapped so a gallery failure can never
block the YouTube publish path.

## Backfill

`scripts/backfill_gallery.py` covers the two currently
YouTube-enabled shows (Tesla Shorts Time, Models & Agents for
Beginners). **There is nothing to backfill from on-repo state** —
historical scene directories `digests/<show>/youtube_tmp/scenes_ep*/`
are in `.gitignore` (line 63) and were reclaimed when each CI
container ended.

The script:

1. Scans the repo for any surviving `scenes_ep<NNN>/` directories
   (typically zero).
2. Accepts `--from-dir <path>` so an operator who has externally
   staged an archive of CI work directories can point the script at
   it.
3. Reconstructs metadata from `summaries_*.json` (episode number from
   the directory name → title + date from the matching summary row).
   `prompt` is left blank because prompts were never persisted
   alongside historical images.
4. Defaults to dry-run; pass `--execute` to actually upload.

Run examples:

```bash
# Honest no-op against the current repo:
python scripts/backfill_gallery.py

# Scan an external archive:
python scripts/backfill_gallery.py --from-dir /tmp/old_ci_runs --execute

# Limit to one show:
python scripts/backfill_gallery.py --shows tesla --execute
```

## Roadmap

| Phase | Status | Scope |
|---|---|---|
| 1 | **Shipped (this PR)** | R2 layout + uploader + sidecar + pipeline hook + backfill |
| 2 | TODO | `/site/data/gallery-manifest.json` rebuilder, Jinja2 gallery components, per-show + network-wide pages |
| 3 | TODO | Cloudflare Worker, JWT cookie, Buttondown gate, magic-link login |
