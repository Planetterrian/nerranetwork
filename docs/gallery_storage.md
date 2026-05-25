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

## Phase 2 — manifest + rendering (shipped)

### Manifest builder

[`scripts/build_gallery_manifest.py`](../scripts/build_gallery_manifest.py)
walks every `*.json` sidecar in the R2 bucket and aggregates them into
[`site/data/gallery-manifest.json`](../site/data/gallery-manifest.json).
The manifest schema is versioned via `schema_version` (currently 1)
and looks like::

    {
      "schema_version": 1,
      "generated_at": "2026-05-24T15:30:00+00:00",
      "image_count": 124,
      "show_counts": {"tesla": 84, "models_agents_beginners": 40},
      "shows": [{"slug": "tesla", "name": "Tesla Shorts Time", "image_count": 84}, ...],
      "images": [
        { ...sidecar fields...,
          "thumbnail_url": "https://gallery.../tesla/.../<id>.thumb.webp",
          "original_url":  "https://gallery.../tesla/.../<id>.jpeg",
          "sidecar_url":   "https://gallery.../tesla/.../<id>.json"
        }, ...
      ]
    }

Images are sorted newest-first by `generated_at` so the default UI
sort matches the manifest's natural order.

The builder is **safe to run anywhere**: if R2 isn't configured it
writes an empty manifest; if a sidecar fails to parse it logs and
skips; if only the timestamp would change it doesn't rewrite the
file. The CI workflow's commit step is therefore a no-op when no new
images have been uploaded.

### CI workflow

[`.github/workflows/build-gallery-manifest.yml`](../.github/workflows/build-gallery-manifest.yml)
runs:

* Nightly at 03:30 UTC.
* After every successful `Run Podcast Show` workflow run.
* On push to `main` affecting gallery code paths.
* `workflow_dispatch` for manual runs.

It commits the regenerated manifest back to `main` (no-op when
unchanged). Reuses the same R2 credentials as the audio pipeline plus
the gallery-specific bucket/base-URL env vars.

### Frontend

* [`templates/_gallery_section.html.j2`](../templates/_gallery_section.html.j2)
  — reusable Jinja2 partial that renders an empty
  `<div data-nn-gallery>` mount point + bootstrap script tags.
* [`templates/gallery_page.html.j2`](../templates/gallery_page.html.j2)
  — network-wide browse page, rendered to `/gallery.html` by
  `generate_gallery_page()` in `generate_html.py`.
* [`assets/js/gallery.js`](../assets/js/gallery.js) — vanilla JS
  (no build step) that fetches the manifest, renders the grid (lazy
  thumbnails via `loading="lazy"`), runs search + show filter + sort
  client-side, and opens a lightbox with prev/next, prompt toggle,
  and a download button.
* CSS additions in [`styles/main.css`](../styles/main.css) use the
  existing design tokens (`--nn-bg`, `--nn-card`, `--show-color`,
  etc.) so per-show embeds pick up the show's brand colour
  automatically.

### Per-show vs network-wide

| Surface | Filter | Controls | Page size |
|---|---|---|---|
| Per-show embed (Tesla, MAB) | Pinned to that show | Search + sort hidden | 24 newest |
| `/gallery` | All shows; multi-select pill row | Search + sort visible | 60 newest |

A show is opted in when its YAML's `youtube.enabled` is true (today:
Tesla Shorts Time + Models & Agents for Beginners — see CLAUDE.md
landmine #20). When a show migrates off YouTube the embed
auto-disables.

### Prompt visibility

Hidden by default; the lightbox shows a "Show prompt" button that
toggles a `<details>` block. Decision recorded in the project spec
under "QUESTIONS TO RAISE BEFORE BUILDING" #3.

### Download gate (Phase 3 stub)

The "Download full size" button in the lightbox opens an email-gate
modal that:

* In Phase 2: marks the visitor as subscribed in `localStorage` on
  email submit, fires a GA4 `gallery_subscribe_stub` event, and
  opens `original_url` in a new tab.
* In Phase 3: will POST to `/api/subscribe` on a Cloudflare Worker
  that calls Buttondown with `tag=gallery-subscriber` and sets a JWT
  cookie, then 302 to a signed R2 URL.

Until Phase 3 ships, original URLs typically resolve to 403 because
the R2 bucket policy keeps originals private. The Phase 2 stub
exists so the UI is complete and reviewable end-to-end now, and so
Phase 3 only has to swap the network calls — not the UX.

## Phase 3 — email-gated downloads (shipped)

### Endpoints (Cloudflare Worker at `api.nerranetwork.com`)

| Method | Path | Behaviour |
|---|---|---|
| POST | `/api/subscribe` | Body `{email}`. Subscribes via Buttondown with tag `gallery-subscriber`, sets a 90-day HttpOnly Secure SameSite=Lax JWT cookie, returns `200 {ok:true}`. Already-subscribed addresses are treated as success (so re-subscribing still issues the cookie). |
| GET | `/api/login?email=...` | If the address is subscribed, sends a magic-link email via Resend (15-min TTL). **Always returns 200** regardless of whether the address exists — the response is identical on hit vs miss so the endpoint can't be used to enumerate subscribers. |
| GET | `/api/magic?token=...` | Verifies the magic-login JWT (HS256 + exp + scope), issues the 90-day cookie, 302 to `/gallery.html`. |
| GET | `/api/download?key=<r2_object_key>` | Verifies the cookie. Validates the key is well-formed (no traversal / no absolute paths). Fetches the R2 object via the bound bucket and streams it back with `Content-Disposition: attachment`. |
| GET | `/api/health` | Liveness ping. |

### Authentication model

Two JWT scopes, both signed with HMAC-SHA256 using the `JWT_SECRET`
the operator provisions once:

| Scope | TTL | Carrier |
|---|---|---|
| `gallery-subscriber` | 90 days | Cookie `nn_gallery=<jwt>` (HttpOnly, Secure, SameSite=Lax) |
| `magic-login` | 15 minutes | URL query parameter on the emailed magic link |

The cookie is set by `/api/subscribe` and `/api/magic` and consumed
by `/api/download`. There is no logout endpoint — Phase 3 ships a
single-cookie subscriber model; the operator can revoke
network-wide by rotating `JWT_SECRET` (all outstanding cookies
become invalid on the next download attempt).

### Download path — spec deviation

The project spec called for `/api/download` to issue a **short-lived
signed R2 URL and 302 redirect**. The Worker **proxies the bytes
through** instead. Rationale:

* Re-validates the JWT on every request, so revocation actually works
  (signed URLs would remain valid for their full TTL even after the
  visitor's cookie expires).
* No signed URLs in browser history or share sheets — originals can't
  leak via copy-paste of a working URL.
* No SigV4 plumbing or third-party dependency in the Worker.

For the gallery's traffic volume the Worker bandwidth cost is well
under the free tier. If we hit Worker bandwidth limits we'll swap to
signed URLs — the endpoint contract from the frontend's perspective
is unchanged.

### Frontend integration

[`assets/js/gallery.js`](../assets/js/gallery.js) calls the Worker
endpoints with `fetch(..., { credentials: 'include' })`. The base
URL defaults to `https://api.nerranetwork.com` and is overridable
via `window.NN_GALLERY_API_BASE` (used by `wrangler dev` against the
local static site).

The lightbox displays the watermarked 800-px thumbnail; the "Download
full size" button fetches the original via `/api/download` and uses
a programmatic `<a download>` click to trigger the browser save
dialog. If the response is 401 (no cookie / expired cookie), the
gate modal opens.

The gate modal has two modes, toggleable via a single link:

* **Subscribe & download** (default): POSTs to `/api/subscribe`,
  then retries the download.
* **Sign in instead**: GETs `/api/login?email=...`, shows the
  enumeration-safe success message.

### Worker layout

```
workers/gallery/
├── README.md            # Operator deploy + smoke-test guide
├── package.json
├── tsconfig.json
├── vitest.config.ts
├── wrangler.toml        # Worker config + R2 binding + route
├── src/
│   ├── index.ts         # Router (4 endpoints + /health)
│   ├── handlers.ts      # Endpoint logic (pure functions of (req, env, deps))
│   ├── jwt.ts           # HS256 sign/verify, hand-rolled, no deps
│   ├── buttondown.ts    # Buttondown API client
│   ├── resend.ts        # Resend API client
│   ├── magic-email.ts   # HTML + plain-text magic-link email
│   ├── cors.ts          # Origin allow-list + CORS headers
│   └── types.ts         # Env + DI shape
└── test/                # 45 vitest tests across the 3 modules
```

### Operator deployment

See [`workers/gallery/README.md`](../workers/gallery/README.md) for
the step-by-step deploy guide. Summary:

1. Tighten R2 bucket policy: originals private, thumbnails + sidecars
   public.
2. Add a CNAME `api.nerranetwork.com` in the Cloudflare zone.
3. Create a Resend account + verify the sending domain + grab an
   API key.
4. From `workers/gallery/`: `wrangler secret put` four secrets
   (`JWT_SECRET`, `BUTTONDOWN_API_KEY`, `RESEND_API_KEY`,
   `RESEND_FROM_EMAIL`).
5. `npm install && npm test && npm run deploy`.
6. Bind the custom domain `api.nerranetwork.com` to the Worker in
   the Cloudflare dashboard.

## Roadmap

| Phase | Status | Scope |
|---|---|---|
| 1 | **Shipped** | R2 layout + uploader + sidecar + pipeline hook + backfill |
| 2 | **Shipped** | Manifest builder + nightly workflow + Jinja2 gallery components + per-show + `/gallery` page + email-gate UI stub |
| 3 | **Shipped (this PR)** | Cloudflare Worker (subscribe / login / magic / download), JWT cookie, Buttondown subscription, magic-link email via Resend, frontend wired to real endpoints |
