# nerra-gallery-api

Cloudflare Worker that backs the Nerra Network image gallery's
email-gated download flow (Phase 3 of the gallery project). The
Worker exposes four endpoints under `https://api.nerranetwork.com/api/`
and is consumed by `assets/js/gallery.js` on the static site.

## Endpoints

| Method | Path | Auth | Behaviour |
|---|---|---|---|
| POST | `/api/subscribe` | none | Body `{email}`. Subscribes via Buttondown with tag `gallery-subscriber`, sets a 90-day HttpOnly Secure SameSite=Lax JWT cookie, returns `200 {ok:true}`. |
| GET | `/api/login` | none | `?email=...`. If the address is subscribed in Buttondown, sends a magic-link email via Resend (15-min TTL). Always 200 (no enumeration). |
| GET | `/api/magic` | none | `?token=...`. Verifies the magic-login JWT, issues the 90-day cookie, 302 to `/gallery.html`. |
| GET | `/api/download` | cookie | `?key=<r2_object_key>`. Verifies the cookie, fetches the R2 object via the bound bucket, streams it back with `Content-Disposition: attachment`. |
| GET | `/api/health` | none | Liveness ping. `200 {ok:true}`. |

## Deviation from spec

The project spec called for `/api/download` to issue a short-lived
signed R2 URL and 302 redirect. The Worker **proxies the bytes
through** instead. Each request re-validates the JWT (so revocation
works), signed URLs can't leak / be shared / be cached in browser
history, and there's no SigV4 plumbing or third-party dependency to
maintain. For the gallery's traffic volume the Worker bandwidth cost
is well under the free tier. If we ever hit Worker bandwidth limits
we'll swap to signed URLs — the endpoint contract from the
frontend's perspective is unchanged.

## One-time operator setup

### 1. R2 bucket policy

In the Cloudflare dashboard, R2 → `nerra-gallery` → Settings:

* **Thumbnails (`*.thumb.webp`) and sidecars (`*.json`):** public
  read at `gallery.nerranetwork.com` (already configured in Phase 1).
* **Originals (`*.jpeg`, `*.png`, etc.):** flip to private. The
  Worker proxies them via the binding — they don't need to be
  publicly reachable.

A simple WAF rule that returns 403 for any path on
`gallery.nerranetwork.com` not ending in `.thumb.webp` or `.json`
achieves the split cleanly.

### 2. DNS + custom domain

In the Cloudflare dashboard for the `nerranetwork.com` zone:

1. Add a CNAME: `api` → any target (Cloudflare will rewrite once the
   Worker custom-domain binding takes over). Proxy ON.
2. After deploying the Worker (step 5 below), bind the route
   `api.nerranetwork.com/api/*` to the Worker via
   Workers & Pages → `nerra-gallery-api` → Settings → Domains &
   Routes → "Add Custom Domain".

The `routes` entry in `wrangler.toml` declares the route; deploying
with `wrangler deploy` activates it on the bound zone.

### 3. Resend account + domain verification

1. Sign up at https://resend.com (free tier: 3 000 / month, 100 / day).
2. Add and verify the sending domain (typically `nerranetwork.com`
   or a subdomain like `mail.nerranetwork.com`). Resend walks you
   through the DNS records (SPF + DKIM).
3. Create an API key from the dashboard.

### 4. Worker secrets

From `workers/gallery/`:

```bash
# Strong random secret for HMAC-SHA256 JWT signing (64 random bytes).
openssl rand -base64 64 | wrangler secret put JWT_SECRET

# Existing Buttondown API key — same one the newsletter pipeline uses.
echo "$BUTTONDOWN_API_KEY" | wrangler secret put BUTTONDOWN_API_KEY

# Resend API key from step 3.
echo "$RESEND_API_KEY"     | wrangler secret put RESEND_API_KEY

# A verified Resend sender — e.g. "Nerra Network <gallery@nerranetwork.com>".
echo "Nerra Network <gallery@nerranetwork.com>" | wrangler secret put RESEND_FROM_EMAIL
```

The R2 binding is set declaratively in `wrangler.toml` (not via
`wrangler secret`) — Cloudflare wires it up at deploy time.

### 5. Deploy

```bash
cd workers/gallery
npm install
npm test          # 45 unit tests
npm run typecheck
npm run deploy    # = wrangler deploy
```

`wrangler deploy` reads `wrangler.toml`, uploads the bundled Worker,
and binds the route. First deploy will require `wrangler login`.

### 6. Smoke-test

```bash
# Health
curl https://api.nerranetwork.com/api/health

# Subscribe (sets cookie)
curl -i -c jar -b jar -H 'Origin: https://nerranetwork.com' \
     -H 'Content-Type: application/json' \
     -d '{"email":"you@yourdomain.com"}' \
     https://api.nerranetwork.com/api/subscribe

# Download (uses cookie from previous step)
curl -i -c jar -b jar -H 'Origin: https://nerranetwork.com' \
     'https://api.nerranetwork.com/api/download?key=tesla/2026-05-24/ep001/<id>.jpeg' \
     -o image.jpeg

# Magic-link request
curl -i -H 'Origin: https://nerranetwork.com' \
     'https://api.nerranetwork.com/api/login?email=you@yourdomain.com'
# → check inbox, click link, then re-test /api/download in a browser
```

## Local development

```bash
cd workers/gallery
npm install
npm run dev          # = wrangler dev → http://127.0.0.1:8787
```

`wrangler dev` serves the Worker locally and prompts for any missing
secrets (which it stores in `.dev.vars`). The static gallery JS
already has `localhost:8080` in its CORS allow-list — run the static
site with `python -m http.server 8080` from the repo root and point
the JS at the local Worker by setting `window.NN_GALLERY_API_BASE` in
the page.

## Tests

```bash
npm test          # vitest run (45 tests in 3 files)
npm run typecheck # tsc --noEmit
```

Tests live in `test/`:

* `test/jwt.test.ts` — base64url + sign/verify + tamper / scope / expiry guards.
* `test/buttondown.test.ts` — API client with `fetch` mocked.
* `test/handlers.test.ts` — each endpoint with fake Buttondown / Resend / R2 clients.

The Workers runtime isn't required for these — handlers are pure
functions of `(request, env, deps)` and the R2 binding is faked with
a small in-memory map in `handlers.test.ts`. End-to-end testing
against `wrangler dev` is operator-driven (see step 6 above).
