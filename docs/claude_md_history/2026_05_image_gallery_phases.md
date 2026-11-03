# Image gallery (Phases 1 + 2 + 3 — May 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Image gallery (Phases 1 + 2 + 3 — May 2026)

Every Grok-Imagine scene generated for the YouTube long-form / Shorts
slideshow is uploaded to a separate R2 bucket (`nerra-gallery`) with a
JSON sidecar and a watermarked WebP thumbnail.

**Phase 1 — storage.** Module:
[`engine/gallery_uploader.py`](engine/gallery_uploader.py). The hook
into `run_show.py:_publish_youtube` is purely additive — gallery
upload failure cannot block YouTube publish. New env vars:
`R2_GALLERY_BUCKET` (default `nerra-gallery`),
`R2_GALLERY_PUBLIC_BASE_URL` (optional). License default: **CC BY-SA
4.0** with attribution to Nerra Network. Backfill:
[`scripts/backfill_gallery.py`](scripts/backfill_gallery.py) — note
historical scene dirs are in `.gitignore` so there is nothing to
backfill from on-repo state without an external archive.

**Phase 2 — manifest + rendering.** A workflow
([`.github/workflows/build-gallery-manifest.yml`](.github/workflows/build-gallery-manifest.yml))
runs nightly + after every successful `Run Podcast Show` and rebuilds
[`site/data/gallery-manifest.json`](site/data/gallery-manifest.json)
from the R2 sidecars via
[`scripts/build_gallery_manifest.py`](scripts/build_gallery_manifest.py).
The frontend is **vanilla JS** ([`assets/js/gallery.js`](assets/js/gallery.js))
— no build step — hydrating the mount point declared in
[`templates/_gallery_section.html.j2`](templates/_gallery_section.html.j2).
The network-wide page is
[`templates/gallery_page.html.j2`](templates/gallery_page.html.j2)
rendered to `/gallery.html` by `generate_gallery_page()` in
`generate_html.py`. Per-show galleries are embedded on each show page
when `gallery_enabled` is true (any show with `youtube.enabled: true`
AND `image_provider: grok`; as of June 14 2026 that's Tesla, SpaceX,
Fascinating Frontiers, Modern Investing + the two RU shows — MAB's
YouTube is paused so its gallery auto-hides — see landmine #20).
Prompt visibility is a per-image **toggle** (hidden by default in the
lightbox).

**Phase 3 — email-gated downloads.** Cloudflare Worker at
`api.nerranetwork.com` ([`workers/gallery/`](workers/gallery/)) with
four endpoints: `POST /api/subscribe` (Buttondown subscribe + 90-day
JWT cookie), `GET /api/login` (magic-link email via Resend, always
200 so the address can't be enumerated), `GET /api/magic` (consume
the magic JWT, set cookie, 302 to /gallery), `GET /api/download`
(verify cookie, stream the R2 object via the bucket binding with
`Content-Disposition: attachment`). JWT is HS256, hand-rolled in
[`workers/gallery/src/jwt.ts`](workers/gallery/src/jwt.ts) — no
third-party dep on the Worker. The download endpoint **proxies bytes
through the Worker** instead of issuing signed R2 URLs (revocation
works, no shareable URLs, no SigV4 plumbing — documented deviation
from the spec). Frontend [`assets/js/gallery.js`](assets/js/gallery.js)
calls these endpoints with `credentials:'include'`; gate modal
supports both "Subscribe & download" and "Already subscribed? Sign
in instead" paths. New secrets (set via `wrangler secret put` once):
`JWT_SECRET`, `BUTTONDOWN_API_KEY`, `RESEND_API_KEY`,
`RESEND_FROM_EMAIL`. The Worker doesn't need new R2 credentials —
the bucket is wired declaratively as `GALLERY_BUCKET` in
[`workers/gallery/wrangler.toml`](workers/gallery/wrangler.toml).

Layout, schema, env vars, deployment steps, and the operator
checklist live in
[`docs/gallery_storage.md`](docs/gallery_storage.md) and
[`workers/gallery/README.md`](workers/gallery/README.md).
Unconfigured environments (env vars unset) are a clean no-op: the
manifest builder writes an empty manifest, the frontend renders a
friendly empty state, and the gate modal surfaces a network error if
the Worker hostname isn't reachable yet.
