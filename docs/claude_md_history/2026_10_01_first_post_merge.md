# First post-merge slate, the cohort on every surface, trust surfaces (Oct 1 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### First post-merge slate, the cohort on every surface, trust surfaces (Oct 1 2026)

Operator-directed follow-up to the Sep 30 pass (review:
[`docs/reviews/network_review_2026_10_01.md`](docs/reviews/network_review_2026_10_01.md);
ledger `network` 2026-10-01; register `frame-memory-wired-2026-10-01`,
`story-clusters-2026-10-01`, `platform-ask-2026-10-01`,
`apple-ratings-instrument-2026-10-01`, `vtt-transcripts-2026-10-01`,
`launch-cohort-newsletters-2026-10-01`). Scored on the 20 episodes of 10-01
(all post-merge): transcripts 20/20 (0/19 the day before), undated articles
in the prompt 0 on 18 of 19 news shows, the stale gate fired six times,
claims 164 → 205. What binds:

**A wiring guard renders through the REAL config object.** The Sep 30
frame-memory block read `config.output_dir`, an attribute only its test
double had; the real `ShowConfig` keeps the directory on
`config.episode.output_dir`, so the block rendered `""` on all 17 opted-in
shows for a day while the guard passed. `engine.frame_memory._config_output_dir`
reads the nested field; the guard loads `shows/omni_view.yaml`.

**A lint measures the text that ships.** Top World Ep009 published 8 of 10
items with no Source while `items_without_source` read 0: the model joined
the reader-only `Ranks:` clause and the `Source:` line, the clause read as
an absence sentence by design ("no figure given"), and the absence filter —
which runs AFTER the lint — dropped the one-sentence line, URL included.
`engine/absence_sentences.py` never drops a line that carries a URL or a
Source tail (the citation stays, the clause goes) and treats `Ranks:` as
structure; run_show re-reads the lint after the filters
(`items_without_source_shipped`). Guards: `tests/test_top_world_sources_2026_10_01.py`.

**A story told once per outlet is not a duplicate the overlap dedupe can
see — cluster upstream, annotate, never drop.** Tesla Ep622 carried the
Model 3 refresh as eight items from eight outlets (each a different angle,
vocabulary overlap 0.10–0.38 against the 0.5 threshold) and the script told
it five times. `engine/story_clusters.py` clusters the fetched list on
salient title+teaser tokens with the show's furniture filtered against the
tracker's 45-day headline window, and later members carry an inline
SAME-STORY note (one item, fold the angle, cite both URLs); opt-in
`story_clusters: true` on the 22 news shows; outcome metric
`story_clusters_retold_in_digest`. A script-level repeated-fact stripper was
prototyped and REJECTED: it also removes the hook-then-body restatement
every cold open relies on. **The TTS emoji strip's "enclosed chars" range
spanned Hangul and every CJK block** — non-Latin outlet names vanished from
the spoken text (Ep622 aired "  reported the patent suit…" for 디지털투데이);
the four real enclosed blocks are listed now, and
`engine.article_text.speakable_source_name` lists a non-Latin outlet by its
domain stem in the prompt.

**The thirteen launch-cohort shows were on every generated surface and off
the three a visitor hits first.** The Worker's `SHOW_NEWSLETTER_TAGS`
(`workers/gallery/src/handlers.ts`) had none of them — every cohort show
page offered a signup whose tag the Worker dropped — plus two established
tags it never had (`DP Pod`, `Nerra Voices`); `tests/test_worker_show_tags_2026_10_01.py`
reads the TypeScript against every show YAML. OP3 wrote NOTHING for an
unindexed feed, so the audience headline read `shows_measured: 16` and
Mission Control showed "—"; `fetch_op3_stats` writes `resolved: false`,
every consumer tolerates it, and the card says "not indexed"
(`shows_unindexed`). None of the thirteen has been submitted to a directory:
`docs/podcast_directories.md` carries their rows and the order — Podcast
Index first, because OP3 resolves feeds through it. The cohort newsletters
are ON (operator: `wrangler deploy`). Hubs `prediction-markets` and
`ai-infrastructure` exist, gated by the 12-episode floor.

**Trust surfaces a listener can see** (all metadata/web except the first):
the spoken closing gains ONE follow-or-rate sentence on alternate days where
it carried no ask (`engine/intros.py`, shapes alternate, Russian on FP;
⚠️ AUDIO — A/B-listen); every feed item carries a WebVTT transcript tag
FIRST (Apple reads VTT; the JSON tag stays for legacy readers) and the
channel carries `itunes:type`, a UUIDv5 `podcast:guid` and a branded
`itunes:author` — 1,972 VTTs and 30 feeds backfilled by
`scripts/backfill_transcript_vtt.py`; show notes carry a network-default
rating ask from each show's NEXT episode (`engine/episode_ask.py`
`DEFAULT_ASK_FROM_EPISODE` — older posts regenerate byte-identically);
every newsletter carries a rating line to the show's own Apple/Spotify
pages (none when the registry has none) and the AI-host branch no longer
raises on `share_text`; YouTube descriptions carry the channel subscribe
link, a Sources line and an AI-host disclosure where the host is Mira
(`engine.video_metadata.video_disclosure_for`); the Shorts funnel comment
and the X follow line take their cadence word from the registry schedule
(`engine/cadence.py`); the promo rotation's Age of AI line no longer says
"on the phone" and `TestPromoRotationTruth` sweeps every surface. Apple
ratings are read nightly from the public show pages
(`scripts/fetch_apple_ratings.py` → `api/apple_ratings.json`, null never 0)
so the asks are measurable; baseline 4 ratings across 15 shows.

**Trust surfaces a reader can see.** Every news-show post renders a
collapsed **Verified claims (N)** panel from its committed `*_claims.json`
(one honest line when the ledger is empty — never hidden), a provenance
line from `engine.brand.episode_provenance` ("Written from N sources · M
claims checked against their sources · K unverified sentences removed
before publication · voiced with Grok TTS"; AI-host shows say so) and a
**Report an error** mailto. **Corrections have a mechanism**
(`engine/corrections.py`, `digests/<show_dir>/corrections.yaml`,
`docs/corrections.md`): a dated box on the corrected post, a line in its
show notes, and the "Correction to episode N" line in the NEXT episode's
show notes that the policy page had promised with nothing behind it
(`engine.show_notes.append_show_notes_extras`, wired in run_show). Audio is
never edited silently (landmine #25). **The verification copy on
`ai_disclosure` / `editorial` tells the truth about the gate** (enforced on
every show, one repair pass, unverified sentences removed, narrative shows
hold the episode) and a guard reads `_defaults.yaml` so it cannot drift;
the Age of AI bullet there had re-grown the stronger gate-2 claim the Sep
22 pass retired — it states the seven-day auto-publish. **One
listener-facing address**: `engine.brand.CONTACT_EMAIL` feeds the
editorial, FAQ and contact pages (Jinja global `contact_email`) and every
post; the RSS owner email in `_defaults.yaml` is a different thing. Guards:
`tests/test_web_trust_2026_10_01.py`.
