# Monthly network checklist

A short, deliberately boring pass over the things that fail *silently*.
The pipeline is loud about crashes; everything below is a failure mode
that leaves a green job behind it, which is why it needs a human on a
calendar rather than an alert.

Run it on the first working day of the month. Twenty minutes.

---

## 1. Feed validity

The feeds are the product. A malformed one is invisible to us and fatal
to a subscriber.

- [ ] Spot-check three audio feeds at <https://podba.se/validate/> —
      rotate which three, so all get covered across a quarter.
- [ ] Check the two **video** feeds (`podcast.video.rss`,
      `spacex_podcast.video.rss`). These are newer and less exercised;
      Apple silently refuses an episode whose enclosure `type` isn't
      `video/mp4`.
- [ ] Confirm `<enclosure>` URLs still point at `audio.nerranetwork.com`.
      **Never "fix" a published enclosure URL** — rewriting one
      re-downloads the episode for every subscriber.

## 2. Apple

- [ ] `api/apple_reporter.json` — is it advancing? The nightly
      `check_apple_reporter_freshness.py` warns after 3 days, but the
      annotation is easy to miss in a green run.
- [ ] **Token expiry**: the Reporter access token lasts 180 days. The
      current one dies around **late January 2027**. See
      [`analytics.md`](analytics.md) for the rotation steps.
- [ ] Once ~3 weeks of Reporter history exist, compare it against the
      cookie scrape on the dashboard. If they agree, retire the scrape
      (`appleconnector` dep, 2 secrets, the daily re-auth chore).

## 3. Cross-source sanity

These measure different things and must never be summed. The check is
that they move *together*, not that they match.

- [ ] OP3 downloads vs Apple plays vs Spotify streams — same direction?
      A source that flatlines while the others move is a dead connector,
      not a collapse in listening.
- [ ] Any show reporting **exactly zero** — is that real, or is it
      absence rendered as zero? That bug has been fixed in five places
      now and it keeps coming back. Absence must render as `—`.

## 4. Storage

- [ ] Skim the last `Storage Prune (video R2)` run summary. It runs
      monthly on the 3rd; the report is in the job summary.
- [ ] Is the video keyspace near its ~52 GB steady state? Sustained
      growth means the prune isn't reaching objects — check whether
      `video_assets.json` is over-retaining.
- [ ] Nothing to do if the prune reported "Nothing to prune". That is
      the expected steady state, not a failure.

## 5. Cost

The tracker became trustworthy on 2026-07-28 (it had been reporting
roughly half of real spend). Numbers before that date are undercounts
and are not comparable to later ones.

- [ ] Cost per episode trend from `digests/*/credit_usage_*.json`.
      Roughly $0.32-0.35 is normal.
- [ ] Any **"(truncated, discarded)"** line that is consistently
      non-zero for a show → its `llm.max_tokens` is set below what its
      prompt needs, and it is paying for a whole generation twice.
- [ ] Image spend — a jump means a show started generating more scenes
      than intended.

## 6. Stranded work

- [ ] Any `recovery/*` branch still open? The nightly janitor deletes
      merged ones and warns about the rest. An unmerged one is a
      **generated, paid-for episode that never published**.
- [ ] Any open draft PR from the review agent that has gone stale.

## 7. Quick greps that have caught real bugs

```bash
# Brand garbles in published transcripts (P0-1 class)
grep -rliE '\bnaran?\b[[:space:]-]{1,3}networks?' digests/*/*_transcript.txt

# Aggregator links that never got a publisher name (P0-2 class)
grep -rc 'news.google.com' digests/*/[A-Z]*.md | sort -t: -k2 -rn | head

# Feed freshness — anything not updated in a week
ls -lt *.rss | head -20
```

---

## What this list is not

It is not a quality review. Editorial quality has its own recurring
process (`docs/reviews/`, the scheduled review agent). This is
infrastructure only: is the thing we built still doing what it says.
