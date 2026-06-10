# Nerra Network Website Review (June 10, 2026)

Full review of the public site (homepage, show pages, blog system, SEO
infrastructure, trust/conversion surfaces, performance, accessibility,
Russian pages). Implemented fixes are marked ✅; the rest are prioritized
recommendations. Drift guards: `tests/test_website_quality_pass.py`.

## What's already strong (verified)

Global client-side search (666 episodes + 287 gallery images, 12h cache,
loading/error/empty states), per-show JSON-LD + breadcrumbs + dual
BlogPosting/PodcastEpisode schema, GA4 with Consent Mode v2 + event tracking
+ UTM coverage, OP3-wrapped audio, deliberate robots.txt AI-crawler policy,
hreflang on en/ru pages, webp srcsets with lazy loading (84/85 images),
management.html correctly noindexed, blog prev/next episode navigation
(already in `blog_post.html.j2:786` — an audit claim to the contrary was
wrong).

## Implemented in this pass ✅

1. **og:image default was a relative URL** (`templates/base.html.j2:16,24`
   defaulted to `path_prefix ~ 'assets/og-preview.png'`). Social platforms
   require absolute URLs — every page that didn't explicitly pass
   `og_image` (about, FAQ, contact, press, …) had broken share previews.
   Default is now the absolute `https://nerranetwork.com/...`.
2. **404 page was indexable** — `templates/404.html.j2` had no robots meta.
   Now `noindex`.
3. **Gallery was reachable from nowhere** — 287 CC BY-SA images with
   licensing metadata had zero inbound links from nav/footer. Footer About
   column now links `gallery.html` (localized "Галерея" on ru pages).
4. **Newsletter social proof hidden until 100 subscribers**
   (`generate_html.py:MIN_SOCIAL_PROOF_SUBSCRIBERS`) — the badge was
   invisible through the entire early-growth phase. Lowered to 50.

Changes are source-only (templates + generator); the nightly site regen
propagates them, per the Phase-2 convention.

## Checked and rejected

- **"48 empty alt texts on nav covers"** — each cover sits inside a link
  whose visible text is the show name; empty alt is the *correct* WCAG
  treatment (avoids duplicate screen-reader announcements).
- **"Search lacks a loading state"** — `assets/js/search.js` already ships
  loading/error/empty states (`isLoading`, line 21).
- **"Blog posts lack next-episode navigation"** — `blog_post.html.j2:786-797`
  renders prev/next cards with `rel` attributes.
- **"podcast:funding missing from feeds"** — the injection shipped June 10;
  feeds gain the tags on each show's next rebuild (first runs are today).

## Recommended next (not implemented — effort/risk)

| Priority | Item | Why deferred |
|---|---|---|
| P1 | Blog index pagination (Tesla's index is 2,100+ lines, grows daily; add 20/page + rel next/prev) | Template + generator math; needs careful URL design so existing deep links keep working |
| P1 | Extract the ~150 lines of inline hero CSS (`index.html` head) into `styles/main.css` | Render-blocking ~8KB; pure refactor but touches the homepage hero — verify on real devices |
| P1 | Homepage gallery rail (3–4 featured images linking to /gallery.html) | Design choice — operator taste; the footer link unblocks discovery meanwhile |
| P2 | Russian localization of about/faq/contact (+hreflang) | Translation quality needs the operator; machine-translating brand pages is worse than English |
| P2 | Inline-style cleanup on index.html (101 `style=` attrs → classes) | Maintainability, not user-facing; bundle saving ~2-3KB |
| P2 | Muted-text contrast audit (WCAG AA) | Needs visual measurement against the real palette, not grep |
| P2 | Per-episode OG images | Deliberately deferred repo-wide (landmine #1, repo size) — revisit via R2 like the gallery |

## Operator items
- After tonight's regen, spot-check a share preview of about.html
  (Twitter/FB card validator) to confirm the og fix landed.
- Decide on the homepage gallery rail + Russian brand-page translations.
