# Where real footage comes from

Survey of royalty-free / public-domain **video** sources for the
network's shows, done August 2026 after the SpaceX pool proved the
b-roll pipeline works end to end. The question behind it: every show
currently renders over Grok-Imagine stills, and real motion is the
biggest remaining lift in perceived production value.

Every licence below was checked against the source's own terms, not a
listicle. Where a source is unusable, the reason is recorded so it
doesn't get re-proposed.

---

## The short answer

| Need | Use |
|---|---|
| Any show, 16:9 | **Pexels video API** — `scripts/fetch_stock_broll.py` |
| Any show, 9:16 (Shorts) | **Pexels video API**, `--orientation portrait` |
| Rockets / launches / ISS | **NASA** — `scripts/fetch_nasa_broll.py` |
| Energy, EVs, grid, solar | **DOE / NREL / EERE** (US gov, public domain) |
| Climate, ocean, weather | **NOAA** (US gov, public domain) |
| Health, labs, biology | **NIH / NLM** (US gov, public domain) |
| Tesla / Grok / Cursor as *products* | See [Brands](#brands-tesla-grok-cursor) — no free footage exists |

**Start with Pexels.** `PEXELS_API_KEY` is already configured (the
still-image pipeline uses it), the video endpoint is included at no
extra cost, and it is the only source that covers all fifteen shows.

---

## Verified source list

### Pexels — ✅ primary, already wired

* **Licence:** free for commercial use. **The API adds an attribution
  obligation the site licence doesn't have** — credit the creator and
  link Pexels. `fetch_stock_broll.py` records
  `Video by <name> on Pexels (<url>)` per clip, which flows to the
  YouTube description automatically.
* **Endpoint:** `GET https://api.pexels.com/v1/videos/search`, with an
  `orientation` parameter — **this is the only source in the survey
  that yields native 9:16 footage**, which the Shorts renders have
  never had.
* **Limits:** 200 requests/hour, 20,000/month. A per-show fetch is
  ~10 requests, so the ceiling is irrelevant.
* **Caveat:** it is stock, and looks it if you pick the obvious clip.
  Mitigated by driving searches from each show's curated
  `image_queries` rather than raw keywords (see landmine #14).

### Pixabay — ✅ good second source

* **Licence:** Content Licence — commercial use fine, **no attribution
  required**, which makes it the cleaner choice where a credit line is
  awkward.
* **Cost:** free API key, separate from Pexels.
* **Caveats:** results must be cached 24 h, no permanent hotlinking, no
  systematic mass download. All three are satisfied by the
  fetch-once-then-publish-to-R2 model this pipeline already uses.
* **Status:** not implemented. A `--provider pixabay` flag on the same
  script is the natural shape if Pexels coverage proves thin.

### US federal agencies — ✅ best quality, narrow topics

Works of the US government are public domain (17 U.S.C. §105).
Attribution isn't legally required; the agencies ask for a courtesy
credit and the fetchers record one.

| Agency | Covers | Shows |
|---|---|---|
| **NASA** | launches, ISS, Earth, planetary | spacex, fascinating_frontiers, planetterrian |
| **DOE / EERE** | grid, batteries, manufacturing | tesla, env_intel, first_principles |
| **NREL** | solar, wind, EV charging | env_intel, dp_pod, tesla |
| **NOAA** | ocean, weather, climate | env_intel, planetterrian, dp_pod |
| **NIH / NLM** | labs, medical imaging | planetterrian, dp_pod |

NASA is implemented (`fetch_nasa_broll.py`, its own JSON API). The
others have galleries rather than clean APIs, so they're a manual
download → `cut_broll_segments.py` → `build_broll_pool.py` path today.
**Check NREL's Image Gallery User Agreement per asset** — it is the one
agency here whose gallery adds terms on top of the public-domain
default.

### Mixkit — ✅ usable, manual

No attribution, commercial use allowed, and the curation is noticeably
less "stocky" than the big libraries. No public API, so it's a manual
download path. Worth it for hero clips.

### Coverr — ⚠️ attribution required on the free tier

Free downloads oblige a credit to the creator or coverr.co (removed by
the paid tier). Usable, but Pexels gives the same obligation with an
API attached.

### Videvo — ⚠️ mixed, check per clip

Three tiers mixed in one search: royalty-free, attribution-required,
and premium. Nothing in the UI stops you conflating them. Only worth
using deliberately, per clip.

### Wikimedia Commons — ❌ avoid for composited video

Much of the SpaceX/Tesla footage there is **CC BY-SA**. Share-alike
attaches to *adaptations*, and cutting a clip into a narrated,
graded, captioned episode is squarely an adaptation — the resulting
episode would arguably have to be released CC BY-SA in full, letting
anyone reuse the network's own work commercially. Not worth it for
b-roll garnish. **CC BY (no SA) and public-domain files on Commons are
fine**; the licence must be checked per file, and the file page's
licence is the authority, not the category.

### SpaceX's own channels — ❌ settled, don't revisit

* Flickr photos went **CC BY-NC** in Dec 2019 (they were CC0
  2015-2019). NC fails a monetized channel.
* **0 of 210** videos on `@SpaceX/videos` carry a CC licence — scanned
  2026-08-01 with `fetch_spacex_broll.py --list-cc`.
* The `@SpaceX/streams` tab needs authentication to scan; unresolved,
  but the main tab result makes a different answer unlikely.
* 2024+ launch streams moved to X, which grants no reuse licence.

`fetch_spacex_broll.py` remains, with a hard per-video CC gate, in case
that ever changes. NASA covers the same subject matter and its
"Isolated Launch Views" are *better* b-roll — no commentary, no overlay
graphics.

---

## Brands: Tesla, Grok, Cursor

There is **no royalty-free footage of a company's product as such**.
Three distinct problems, three different answers.

### Tesla

* No Tesla-licensed footage exists. Tesla's brand guidelines forbid any
  use implying affiliation or endorsement, and say nothing granting
  editorial rights.
* **Nominative use** — showing and naming a product while commenting on
  it — is the ordinary basis on which news and review channels operate.
  Showing a Tesla while discussing Tesla is normal editorial practice;
  what the guidelines forbid is using the marks so as to suggest Tesla
  endorses the show.
* **Practical source:** user-shot Teslas on Pexels/Pixabay (plenty:
  charging, driving, interiors), plus DOE/NREL for charging
  infrastructure and battery manufacturing.
* **Avoid:** Tesla's own ad footage, keynote/event recordings, and
  anything with the wordmark/logo as a design element rather than
  incidentally in shot.

### Grok / Cursor (and software products generally)

Stock libraries have no footage of a software UI, and generic "AI"
b-roll (glowing brains, binary rain) actively cheapens a show.

Ranked options:

1. **Record it yourself.** A screen capture of Grok or Cursor answering
   a real prompt is *your* recording — you own that copyright, and
   showing a product's interface while discussing it is the same
   nominative use as above. It is also the only footage that actually
   matches what the episode is talking about. A handful of 10-second
   captures (a prompt resolving, a diff applying, an agent looping)
   would serve M&A and MAB indefinitely, and they never date as fast
   as the news does.
2. **Brand assets for logos only.** xAI publishes brand guidelines at
   `x.ai/legal/brand-guidelines` — **read them before using the marks**;
   they returned 403 to automated fetching here, so the terms are
   unverified in this document. Cursor/Anysphere has no press page I
   could find; contact them for anything beyond nominative use.
3. **Abstract-but-honest stock:** data centres, server racks, fibre,
   code on screens. Real, non-cheesy, and available on Pexels. This is
   what `models_agents` should use until screen captures exist.

**Do not** lift footage from other creators' review videos, conference
recordings, or company keynotes. That is someone's copyright regardless
of how it's framed.

---

## Per-show starting point

| Show | Best sources |
|---|---|
| tesla | Pexels (EVs, charging, factory robots) + DOE/NREL |
| spacex | **NASA** (done) |
| fascinating_frontiers | NASA + Pexels (observatories, labs) |
| planetterrian | NIH + NOAA + Pexels (labs, nature) |
| models_agents / MAB | **own screen captures** + Pexels (data centres) |
| modern_investing | Pexels (trading floors, city finance districts) |
| env_intel | NREL + NOAA + Pexels (Canadian wilderness, industry) |
| dp_pod | NREL + Pexels (solar installs, volunteers, labs) |
| first_principles | DOE + Pexels (foundries, machining, assembly) |
| unintended_consequences | Pexels (archival-feeling city/industry) |
| omni_view | Pexels (world cities, transport) — avoid anything that reads as a specific news event |
| finansy_prosto / privet_russian | Pexels (home, family, everyday Russia/Canada) |
| dp_pod / age_of_ai | Pexels (studio, conversation, human hands) |

---

## Pipeline

All sources converge on the same three steps:

```bash
# 1. Fetch (per source)
python3 scripts/fetch_stock_broll.py --show tesla --out-dir tesla_stock
python3 scripts/fetch_stock_broll.py --show tesla --orientation portrait \
    --out-dir tesla_stock_9x16
python3 scripts/fetch_nasa_broll.py --query "Isolated Launch Views"

# 2. Cut long sources into accents (skip for stock — already short)
python3 scripts/cut_broll_segments.py nasa_broll/*.mp4 --out-dir cuts

# 3. Publish (attribution carries through from _provenance.json)
python3 scripts/build_broll_pool.py --show tesla tesla_stock/*.mp4
git add digests/tesla/broll.json && git commit && git push
```

Renders then draw a rotating, source-spread slice per episode
(`engine.gallery_library.rotate_for_episode` /
`interleave_by_source`), clamped to 8 s accents
(`engine.video._MAX_BROLL_SEGMENT_S`).

### Known gap

The pool feeds the **long-form** render only. Shorts currently take
their motion from the Grok Imagine A/B path, so `--orientation
portrait` footage has no consumer yet — fetching it is useful for
building the library, but wiring Shorts to the pool is a separate
change.

---

## Rules

1. **Never assume a licence from a listicle.** Every entry above was
   read at source; two "free" sources (SpaceX Flickr, Coverr free tier)
   carry terms that a summary would have missed.
2. **Attribution is cheap; a takedown isn't.** Where a source requires
   credit, the credit is recorded at fetch time, not remembered later.
3. **CC BY-NC and CC BY-SA are both disqualifying** for this network —
   NC because the channels are monetized, SA because episodes are
   adaptations.
4. **Public domain still gets a courtesy credit.** NASA and DOE ask
   for one and it costs a line of description text.
