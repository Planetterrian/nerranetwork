# Oct 11 2026, later — sponsor-ready, and five operator items

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Oct 11 2026, later — sponsor-ready, and five operator items** (register
`sponsor-ready-2026-10-11`, `signup-measurement-2026-10-11`,
`narrative-queue-source-audit-2026-10-11`, `fr-dub-gate-enforce-2026-10-11`;
guards `tests/test_sponsor_ready_2026_10_11.py`). **The network no longer
promises "ad-free" anywhere** (operator: sponsorship comes next); the episode
stays free, which is true. **Oct 18 2026: ads are coming to the site and the
shows, and ad-free is reserved for subscribers and paid content** — no free
surface says ad-free (the approved SEO copy in `docs/seo-titles-final.md` had
put "Ad-Free" in the homepage `<title>` and five show metas, the brand-refresh
banner/share art and the September debut articles carried it; all corrected,
and the guard now reads those sources plus show YAMLs and Worker pages).
Transcripts stay the record of what the audio said. Copy that calls the PAID
tier ad-free lives in `engine.brand` and names the product. **`engine.brand` owns the sponsor policy**
(`SPONSOR_POLICY_SUMMARY` / `_RULES`, the `sponsor_policy` Jinja global):
labelled, kept apart from the reporting, no say over coverage, same sourcing
rules, every episode free. It renders on `sponsor.html` (numbers from
`api/audience_headline.json`, dash = unmeasured), `editorial.html#sponsors`,
the FAQ and the press kit; a template that types a rule fails CI. No ad is
placed yet. Also: the footer/join form fires GA4 `newsletter_signup`; the UC
and FPD queues were audited for sources (cut / fixed with a dated SOURCE
AUDIT note / kept) and a restock brief now needs two non-social search
results (`ground_candidates`); the spoken-text gate ENFORCES on French tracks
only (`CALIBRATED_LANGUAGES`; RU stays shadow until its opening match is
calibrated on Cyrillic); `pipelines/voices/backfill_videos.py` (Actions
"Nerra Voices — backfill YouTube videos", dry run by default) gives the Age of
AI's past episodes their video; Prediction Markets' Friday Week's Board parses
the prose Board again (it was empty on 10-02 and 10-09).
