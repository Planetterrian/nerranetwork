# Nerra Network Website Review (October 7, 2026)

A full pass over the public site for quality, experience and visual appeal.
Previous pass: [`website_review_2026_09_03.md`](website_review_2026_09_03.md).

**Method.** The committed site was served locally and 58 representative
pages were rendered in headless Chromium at desktop (1440×900) and phone
(390×844) width, in full-length segments. Each page was measured for:

- horizontal overflow;
- WCAG text contrast (computed against the nearest opaque background);
- text under 12px and tap targets under 24px;
- DOM size, inline styles and transfer size;
- heading outline, empty states and broken local requests.

Five parallel reviews then read the screenshots and the source:

1. homepage and global chrome;
2. show pages;
3. blog and topics;
4. trust, static and member pages;
5. dashboards, player and data.

Four parallel implementation passes and one shared-chrome pass shipped the
fixes. GA4 set the priorities: blog episode pages are 34% of measured
landing sessions (97 of 282) with a 70% bounce rate, and the homepage is
next (79).

Drift guards:

- `tests/test_site_review_2026_10_07_chrome.py`
- `tests/test_site_review_2026_10_07_blog.py`
- `tests/test_site_review_2026_10_07_trust.py`
- `tests/test_site_review_2026_10_07_dashboards.py`
- `tests/test_site_review_2026_10_07_gallery_player.py`

## Headline findings

1. **One stray `}` in `styles/main.css` broke layout on every page.**
   - It closed the phone media query early. Every phone-only rule then
     applied at every width:
     - one-column footer (3,608px tall on `404.html` at 1440px);
     - one-column episode and cross-network grids on desktop;
     - the sticky player's speed control hidden everywhere.
   - The orphan brace swallowed the whole 640–1023px tablet block. At
     tablet width there was no hamburger, and the nav ran off the screen.
   - Fixed. A brace-balance guard now fails CI on the next one.
2. **Every blog article was wider than a phone.**
   - The provenance line was one unbreakable `nowrap` run, so articles laid
     out 505–980px wide at 390px and the menu button was off-screen.
     iOS then shrank the whole article to fit.
   - This hit about 2,200 posts, the site's main landing surface.
3. **About 2,000 episode pages had no way to play the episode.**
   - The only `<audio>` sat inside `{% if translations %}`.
   - Every post with an audio URL now has a player, and the hero
     "Listen" button jumps to it.
4. **Brand colours were used as text and failed contrast on every page
   family.** Examples:
   - Offshore North "LATEST EPISODE" at 1.66:1;
   - Tesla red at 4.06:1;
   - the network purple at 3.6:1.

   A text-safe tint is now derived everywhere a brand colour is used as
   text (`--show-color-text`, `--card-accent-text`, `--nn-purple-text`).
   Low-contrast elements on show pages went from 41–62 per page to 0.
5. **The site still said guests approve before anything publishes.**
   - Gate 2 auto-approves after seven days of silence (Sep 22 rule). The
     stronger claim had survived in many places:
     - the Mira meta description;
     - the claims ledger, FAQ and editorial page;
     - both apply pages and the interview-hub meta;
     - all nine interview posts ("reviewed and approved by <guest>");
     - the producer's guest-reply facts;
     - four guest emails and two Voices Worker pages.
   - All now state the real terms: a week to approve, cut or refuse; then
     it publishes; a takedown stays available. A sweep guard covers
     Python literals, templates and the apply pages.
6. **The heaviest pages loaded data nobody saw.**

   | Page | Before | After | Cause |
   |---|---|---|---|
   | gallery.html | 22.3 MB | 1.1 MB | parsed the full 22 MB manifest before the first card |
   | age-of-ai.html | 22.4 MB | 0.4 MB | a missing per-show slice fell back to the full manifest, then showed "no images" |
   | player.html | 14.0 MB | 0.7 MB | thirty-one 3000px covers at 48px, plus every show's full digests |
   | tesla.html | 3.2 MB on load | 0.8 MB | 2.4 MB of gallery JSON fetched 17,000px above the gallery |

7. **Numbers that misled.**
   - Mission Control's sponsor view put "+62% week-over-week" beside the
     "+7.8%" tile; the 62% compared a partial OP3 week.
   - It counted episodes from credit files, which include dub tracks
     (176, against 144 from RSS).
   - It ranked Age of AI cheapest at "$0.000 per download" because its
     spend is untracked.
   - The MIT approaches table printed 0% win rate and +0.00% alpha, in
     green, for fields the data never carried.
   - The summaries pages printed their own link markup as text, 364 times
     on Tesla's.

## What shipped, by page family

### Global chrome and homepage

- **Stylesheet:**
  - brace fix, so the tablet nav and hamburger work again;
  - a `[hidden]` reset (Explore's "Clear filters" showed permanently);
  - `audio { color-scheme: dark }`;
  - UI font on the cookie banner;
  - 16px search input on phones (no iOS zoom), with a full-width results
    box;
  - rail scroll padding;
  - dropdown triggers aligned with the plain nav links.
- **Prose links are visible:** underlined and cyan, at `:where()`
  specificity so every component's own link style still wins (WCAG 1.4.1).
- **Homepage:**
  - the hero shows two rows of covers, so the buttons are above the fold
    at 1440×900 (it was five rows ending on an orphan row of three);
  - the in-page "Latest"/"Subscribe" nav items are gone (they pushed
    Subscribe and Join off-screen at 1024–1186px);
  - 🇨🇦 replaces the regional-letters "?" flag;
  - the listening-language count is computed;
  - the Modern Investing card no longer promises "actionable picks" that
    beat index funds.
- **Explore:** "Eighteen shows" is computed.
- **Start Here:**
  - the guest card no longer nests a link (the parser split it into an
    empty box);
  - "alternating days" is replaced (no show runs on alternating days).

### Show pages

- **Summaries pages:**
  - one-pass linkify, so the markup leak is gone;
  - long digests open clamped with a "Show full summary" toggle; Tesla's
    phone page is 21,700px instead of 196,000px;
  - "Latest 30 episodes", not "30 episodes and counting";
  - the subscribe row is styled at last.
- **"Recommended for you":** five shows named a different show from the
  card they recommended. Fixed, with a guard.
- **Story Tracker:** reads `last_mentioned_*`, which the hook writes every
  episode. It had said "Not yet deeply covered" after 122 episodes, and it
  no longer prints a repo path.
- **DP Pod page:** now reads as the weekly show it is, not the daily
  pre-launch page. "ten minutes a day", "the next lever is tomorrow" and
  "Patron doors open with Episode 1" are gone, and the anthem links
  Episode 1.
- **Referrals:**
  - Modern Investing's Wealthsimple block is no longer headed "Vehicle
    Benefits";
  - both referrals now say the show may earn a referral reward, on a page
    that also says no episode carries a sponsor.
- **Listening:**
  - "Listen Now" goes to the latest player;
  - the latest player, archive cards and language tracks route through
    OP3, so plays are counted;
  - an archive card no longer repeats its title as its preview.
- **Modern Investing:** the show page lists the latest 10 trades, with
  "Open"/"Voided" shown honestly and a link to the full record. It had
  printed all 87, with 1,590 inline styles.
- **Other fixes:**
  - SpaceX no longer asks for the same email twice in one screen;
  - Nerra Voices has no empty episode rail;
  - mobile-menu links no longer carry inline close handlers;
  - the "More from" grid reads Russian shows from `engine.show_lang`;
  - Nerra Daily's description names its real rundown.

### Blog and topics

- **Layout:** fits 390px on every post, and the menu button is back on
  screen.
- **Player:** a plain player on every post with audio.
  `engine.blog.episode_audio_url` reads the summaries record, then the
  feed enclosure, and keeps OP3.
- **Headline:**
  - stated once, with the episode number in its pill;
  - the body's duplicate leading hook and show-name heading are dropped;
  - the heading outline runs h2 → h3 with no skipped level.
- **Readability:**
  - 72ch measure;
  - item bodies in full text colour, not muted grey;
  - chapter times and index accents use the text tint.
- **Cross-show recommendations:** "You Might Also Like" appears on posts
  again; it had appeared on zero of 2,243. The pool sorts on ISO dates,
  skips redirect stubs, and stays seeded per post.
- **Index cards:** no longer print the same sentence twice.
- **Network index on phones:**
  - one scrolling chip row;
  - an honest "Filter these posts…" box;
  - `aria-current` on the active page.
- **Topic hubs:**
  - DP Pod is weekly;
  - no typed show counts that contradict the printed one;
  - the cadence guard now reads `engine/topic_hubs.py`.
- **Interview posts:** talking points render markdown, and prev/next
  links show titles.

### Trust, legal, static and member pages

- **AI disclosure:** the host and voice statement is derived from each
  show's YAML `tts` block. It had said every English show uses a clone of
  Patrick's voice and "eighteen shows publish daily".
- **FAQ:** the cadence answer is rendered from the registry, on the page
  and in the FAQPage JSON-LD. It had the four Monday shows on
  "even/odd days".
- **Privacy policy:**
  - a new "If you are a guest" section: what is recorded, the processors
    (Cal.com, Voximplant, xAI, Supabase, Resend, R2, Whisper), and
    retention as documented;
  - section anchors and a contents list.
- **Join:** one consistent count (26) in the hero, stat and Step 1, where
  it had said 31, 26 and 13.
- **How to Listen:** says most shows are in the directories and every
  published show has a feed. On phones the table becomes cards, so the
  RSS column is visible.
- **Sign-in:**
  - the account form has a label and autocomplete, and fails honestly on
    a 4xx/5xx;
  - login has no button nested in a link, and its error has
    `role="alert"`.
- **Claims page:** steps in a `<details>` list, per-status badges, and
  "Verified (fetched copy)".
- **Contact address:** the legal, support and books pages use the single
  `contact_email` (a personal Gmail had been printed on three of them).
- **`ru/index.html`:** Monday cadence (it said «Через день»), no stale
  show count, links to the Russian SpaceX and Tesla pages, and 400px WebP
  covers.
- **Russian SpaceX lander:** the hero no longer sits under the fixed nav.
- **Apply pages:**
  - selects fit a phone;
  - a privacy link sits under the submit button;
  - no white flash on iOS.
- **Books:** cover dimensions and lazy loading, so the layout no longer
  collapses before the images load.

### Dashboards, player, data

- **Mission Control:**
  - week-over-week figure from `audience_headline`;
  - RSS episode count;
  - no "[object Object]" alert;
  - untracked spend shown as "—", not $0;
  - fits 390px and 1440px in all three views;
  - "Levers in flight" escaped and collapsed (the operator page is about
    27k px, down from 54k);
  - `--ink-4` at 5.7:1;
  - operator plumbing hidden from the sponsor and investor views.
- **MIT performance page:**
  - the approaches table states its 10-position window and shows "—" for
    missing fields;
  - charts labelled honestly: trade #, points, and "Sum of trade returns
    (pts)".
- **Tesla and SpaceX dashboards:**
  - curated blocks carry "Operator data as of …";
  - the SpaceX Starship tracker defers to the live launch record when it
    is newer;
  - bar labels are no longer clipped.
- **Offshore North:**
  - the calendar row agrees with the Oct 4 entry-list rule;
  - stale fleet rows show their last good read date.
- **`modern-investing-resources.html`:** fits a phone and passes contrast.
- **Network player:**
  - a compact embedded index with OP3 audio and 400px WebP covers;
  - Age of AI's episodes appear;
  - previews keep their hyphens ("sixpointninebilliondollar" is gone);
  - no chip for a show without episodes;
  - a keyboard-operable seek bar;
  - progress and times kept on phones;
  - one scrolling chip row;
  - the nav contract restored.
- **Gallery:**
  - slim per-show and network indexes from `build_gallery_manifest.py`
    (`--indexes-only` rebuilds them offline);
  - embeds load near the viewport and never fall back to the full
    manifest;
  - a show with no images mounts no gallery;
  - the first page is round-robin across episodes;
  - prompts are fetched on demand, and the "Show prompt" toggle finally
    reveals them.

## Not done here: operator decisions and proposals

- **Homepage length.**
  - The phone homepage is about 44,000px. The show list renders seven
    times, and "Latest Across the Network" and "Latest from the Blog" show
    the same six episodes.
  - Proposed order:
    1. Hero
    2. one Latest rail
    3. Personal
    4. Most Played
    5. Why Nerra
    6. a compact show grid linking to Explore
    7. one newsletter form
  - That roughly halves the page. Section order was operator-set, so this
    is a proposal.
- **Homepage newsletter default.** Every one of the 31 shows is pre-checked
  ("everything's selected by default"), which signs a new reader up for up
  to ~25 emails a day. Recommendation: start unchecked, or pre-check only
  Nerra Daily.
- **Privet's page language.** Privet posts are English lessons rendered
  with `<html lang="ru">` and Russian chrome. A registry guard pins it to
  `ru` on purpose, so this is the operator's call.
- **Book covers.** The store covers are 3.4 MB and 4.9 MB PNGs shown at
  166px. Web-size files need an R2 upload.
- **Curated dashboard data.**
  - `site/data/tesla_metrics.json` ends at 2025 Q1.
  - `site/data/spacex_metrics.json` stops at IFT-9 and 2024. Its
    `starship_flights` list has no `updated_at`.
- **Worker deploy.** `workers/voices` copy changed (the booking pages'
  approval wording). It takes effect after `wrangler deploy`.
- **Mailboxes.** Confirm press@, partners@, tech@ and privacy@ exist; the
  contact page lists them.
- **Sponsor view.** The YouTube-policy and Funnel cards still show in the
  sponsor and investor views. Hide them if you consider them internal.
- **Search scope.**
  - Gallery search no longer covers prompts, which were 6.7 MB of the
    payload.
  - Player search covers titles and previews, not full digests.
  - The player's embedded index refreshes nightly; "Check for new
    episodes" reads `network.rss` for same-day episodes.
- **Finalize commits.** Finalize now commits `site/data/gallery/*.json`,
  slices included. Narrow it to `*.index.json` if commit size matters more
  than prompt freshness.
- **Show-page Russian localisation.** On Финансы Просто, dates, "Ep N:",
  "About …" and the creator block are still English.
- **Story Tracker "last deep coverage".** The memory hook never writes
  `last_major_update_*`. The page now shows "Last on air" instead; a real
  "deep coverage" signal needs a hook change.

## Before and after (58-page render audit, same harness)

See the PR for the measured table. Numbers are from the committed site
before this pass and a local regeneration after it.
