# Offshore North — show notes and passes (Sep 14 2026 – Oct 30 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

- **ON** (Offshore North) runs via `run_show.py` + `shows/offshore_north.yaml`;
  the network's **weekly offshore ocean-racing show** (Mondays; Dan on
  `0vscf8u8yrxc`, single-narrator, `memory_enabled`). Spine: Canada Ocean
  Racing / Scott Shawyer / EMIRA IV (CAN 80) toward the Route du Rhum
  (1 Nov 2026, entry confirmed) and the Vendée Globe (12 Nov 2028).
  Prompts carry two included files — `offshore_north_standing_facts.txt`
  (authoritative campaign background, reviewed monthly, with a "standing
  corrections" list of errors already aired) and
  `offshore_north_field_guide.txt` (the sport's map). **Sep 14 2026 review**
  (doc: [`docs/reviews/offshore_north_review_2026_09_14.md`](docs/reviews/offshore_north_review_2026_09_14.md);
  ledger `docs/reviews/ledger/offshore_north.yaml`; guards
  `tests/test_offshore_north_review_2026_09_14.py`): **the digest prompt had
  never seen an article** — headline + feed teaser + URL only — so Ep002–005
  aired the boat's position as "unconfirmed" while the team's 2 Sep post
  said it was heading back to Europe, reported WHEN channels changed rather
  than WHAT they said, spoke the writer-only "standing facts" label, and
  Ep005 aired a race START headline (Google-News re-surfaced) as the RESULT
  of a race that had finished with a different winner. Now:
  `engine/article_text.py` + `fetch_full_text: N` (**opt-in per show; 0 =
  every other show byte-identical**) renders each article's FULL TEXT under
  its headline — WordPress `content:encoded` bodies are stored on every
  article as `content_text` with no HTTP, pages are fetched for the rest,
  campaign feeds first; the freshness block carries a "What it said"
  excerpt + URL; Scott's Notes (the skipper's own writing — a WordPress
  PAGE whose `/feed/` is the COMMENTS feed; the `scotts-blog` category feed
  is the real one) is a flagged campaign source. Editorial rules that now
  bind (all landmine-#17 — A/B-listen the first episode): last-known
  position + the DATE of the fix, never "unconfirmed"; the Canadian Boat is
  FIRST and LONGEST; incidents not leaderboards, one sentence max on a
  leader, no roll-calls; never "standing facts/item" on air and the boat's
  pedigree at most once in four weeks; Plain Sailing EVERGREEN (never a
  same-episode race recap); no host-experience line (the Sep 14 rule of
  EXACTLY ONE Dan reference was reversed on Oct 30); a finish inside the
  window outranks a re-surfaced start. Blog footer placeholder is
  cadence-aware (`engine.blog.next_episode_placeholder` — "New episode
  Monday", never "tomorrow" on a weekly show). **Public campaign
  dashboard** `offshore-north-dashboard.html`
  (`generate_offshore_north_dashboard`; curated
  `site/data/offshore_north_dashboard.json` + live
  `api/offshore_north_dashboard.json` from
  `scripts/fetch_offshore_north_dashboard.py`, refreshed nightly and by the
  show hook after each episode; both committing workflows whitelist the
  pair): countdowns, last known position with date + source, the team's
  YB tracker, latest team posts with excerpts, headlines, spec, calendar,
  results, the Route du Rhum IMOCA entry list, qualification ledger,
  lineage, and every source/social the show reads. A new dated position
  fix goes in the curated file's `position_log`; never guess one.
  **Sep 18 2026 round-1 fixes** (operator list on Ep005; guards
  `tests/test_offshore_north_round1_2026_09_18.py`): the campaign's four
  feeds carry `window_hours: 720` (`SourceConfig.window_hours` — a
  per-feed cutoff that may look FURTHER back than the ladder, never less;
  a campaign does not generate news weekly and Ep005 reported the boat
  still in Canada from an empty 7-day window); `stale_article_days: 10`
  drops any article whose PAGE publish date (`engine.article_text.
  extract_published_date`, read during the full-text fetch — OpenGraph
  meta, JSON-LD, `<time>`) or feed date is older than ten days before the
  prompt sees it (`drop_stale_articles`; `window_hours` feeds exempt;
  undated pages kept; metric `articles_dropped_stale`), because Google
  News re-surfaced the 1 Sep race START under a 12 Sep index date and
  Ep005 aired it on the 14th; timestamp sentences ("last updated on…",
  "no new posts inside the window") are banned and the prompt line that
  produced them is gone; the labelled background block is deleted, not
  renamed; a RACE STATE CHECK precedes any race sentence; Plain Sailing
  is a HARD 300-word cap, one point made once, never the lead story's
  subject, and no longer a length lever; class names come from the
  official race site — the 2026 Route du Rhum's six are ULTIM, Ocean
  Fifty, IMOCA, Class40, Vintage Multi, Vintage Mono (formerly Rhum
  Multi / Rhum Mono). Host voice and the incident-driven Fleet rewrite
  are deferred at the operator's direction.
  **Sep 19 2026 resource pass** (§7 of the review doc; guards
  `tests/test_offshore_north_resource_2026_09_19.py`): **the campaign
  record is ONE file** — `site/data/offshore_north_dashboard.json` is
  baked into the dashboard AND rendered by `engine/offshore_north_status.py`
  into a dated CAMPAIGN STATUS block (`{campaign_status}`, hook-supplied,
  defaulted to "" in run_show + `engine.pipeline`) in both prompts: newest
  dated fix + its age, each countdown's NOT STARTED / RUNNING / FINISHED
  state by the clock with EMIRA IV's entry, results on record, the Rhum
  entry count, the countdown as arithmetic. Update the record (dated,
  sourced) and both surfaces follow; never hand-write a date into the
  prompts. A verified ABSENCE (EMIRA IV was not among the 14 at the 48H
  Azimut) is a `position_note`, never a position. The **Plain Sailing
  glossary** (`offshore-north-glossary.html`, `site/data/offshore_north_glossary.json`,
  55 hand-written sourced entries + the aired-explainer archive with
  `#t=` audio deep links, titles via `engine.titles.PLAIN_SAILING_TITLE_MAX`)
  is linked from the show page, the dashboard and every ON blog post
  (`engine.blog.SHOW_RESOURCES`). Dashboard v2 adds an "In the press" rail
  (the show's GN query resolved to publisher URLs), calendar state pills,
  the Défi Azimut result and the Rhum entries' 48H form. (The Sep 19
  probe that found "no JSON endpoint" on the YB tracker read only the
  HTML — see Oct 4 below.)
  **Round 2, same day:** countdowns and results are linked by key
  (`results_key` ↔ `key`) and a FINISHED race with no result entry gets
  "RESULT NOT YET ON RECORD" in the status block and "result pending" on
  the calendar — add the result entry, never a placing from memory. The
  **fleet guide** is parsed nightly from each Rhum entry's imoca.org boat
  page (`imoca_slug` on the entry; `parse_imoca_boat_page`; a failed page
  keeps the last good record, marked `stale`), the **cast** panel is
  twelve one-fact identifiers from the record, the **map** (Leaflet from
  cdnjs + OSM tiles) plots only the dated PLACES a team post named — an
  entry without `lat`/`lon` gets no marker — and the show page carries a
  campaign strip from the same record.
  **Oct 4 2026 — the position is the tracker's, and five operator rules**
  (guards `tests/test_offshore_north_tracker_2026_10_04.py`). The YB
  tracker page is a script app over a public API the page itself calls
  (`app.yb.tl/APIX/Blog/GetEvents` / `GetPositions`, keyword `emira4`);
  `engine/yb_tracker.py` reads it nightly (dashboard fetch) and FRESH in
  the show hook, and the fix is also a hook ARTICLE so the claims gate can
  verify the position sentence. Rules that bind: the base is **Gosport,
  UK (Portsmouth Harbour)**, never Brittany/Lorient (a place is named only
  inside `campaign.tracker.places`, else coordinates); a position always
  carries its date and source; a fix older than **7 days** is "last seen
  <date>", never the present tense (`yb_tracker.STALE_DAYS`); only the
  tracker's dated outings are spoken — never "training solo in Europe";
  the Route du Rhum is **"aiming to start"** until the official entry list
  carries Scott (`rhum_entry` in the record — the Sep 19 "Entry CONFIRMED"
  read the IMOCA class page, not the official list). **Instagram is read,
  never copied** (`engine/instagram_source.py`, Meta Business Discovery):
  captions + permalinks become dated source articles and a dashboard rail;
  pictures reach a reader only as Instagram's own embed, loaded on a click
  (the privacy policy says so); `media_url` is never requested. Secrets
  `INSTAGRAM_GRAPH_TOKEN` / `INSTAGRAM_GRAPH_USER_ID` — deliberately not the
  Shorts publisher's `IG_*` names; unset = a clean no-op.
  **Oct 30 2026 — a listener review of Ep011** (guards
  `tests/test_offshore_north_review_2026_10_30.py`; register
  `offshore-north-review-2026-10-30`). Rules that bind: **Vendée Globe
  qualification is the Notice of Race list** (section 9.1: a SOLO finish
  from Vendée Arctique 2026, Route du Rhum 2026, Retour à la Base 2027, The
  Transat CIC 2028 or New York Vendée 2028, on the same boat, within twice
  the first finisher's time, plus a top-37 Globe Series ranking); a race off
  that list is never a qualifier — Ep011 called the double-handed RORC
  Transatlantic (10 January 2027, Marina Lanzarote, Scott with Alan Roberts
  on EMIRA IV) a "qualifying passage", a claim the team never made.
  **No host-experience lines**: the weekly "Dan's lens" the prompts required
  since Sep 14 is gone from every prompt, and `host_experience_filter`
  (`engine/host_experience.py`) removes one the model writes anyway.
  **Every team item carries its channel and date; a past result names its
  boat** (the 2023 record was the team's earlier IMOCA). **No padding**
  (photos, ceremony colour, a fact told twice), and Plain Sailing reads the
  last eight explainers (`recent_plain_sailing`, hook-supplied) — three
  subjects had aired twice running. A three-word chapter line ("Now, the
  fleet.") now borrows the next lines' opening to find itself in the
  transcript, and the re-synthesis tool times chapters as run_show does.
  Ep011 carries a correction (`where: both`); re-voice it with Actions
  "Re-synthesize Episode". ⚠️ AUDIO — A/B-listen the next episode.
