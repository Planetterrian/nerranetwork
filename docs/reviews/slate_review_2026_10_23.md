# Slate review — Oct 23 2026

Operator ask: review how the shows and workflows did in the last 12 hours
(Oct 23 01:40 to 13:40 UTC) and improve them as needed. Each finding below
was checked against the run's annotations or log, the committed metrics, or
the catalog tables before anything changed.

Register: `slate-2026-10-23`. Guards: `tests/test_slate_2026_10_23.py`.

## 1. What ran

| Item | Result |
|---|---|
| Scheduled show runs | 21 |
| Published | 4: Unintended Consequences Ep151, First Principles Ep139, Collingwood Ep005, and the North America desk (members only) |
| Skipped as designed | Asia Pacific, Europe and LatAm desks (`no_member_demand`) |
| Lost to the xAI billing stop | 11 (see below) |
| Lost in `setup-python` | 5 show runs, plus First Principles' video job |
| Nerra Daily | Held at 06:35 ET. At 06:50 ET it refused to build from 3 segments, under the 4-segment floor (correct) |
| Producer inbox | Every run since 11:30 UTC failed on the same xAI 403 |
| Story catalog | Episodes and items written by every run; 66 articles written, **0 marked aired** |

Runs lost to the billing stop:

- At the pre-flight ping, in 2–3 minutes: SpaceX, Tesla, MAG 7, Modern
  Investing, Prediction Markets, Vancouver.
- After generation, at TTS: AI Chips, Models & Agents, MAB. AI Chips had a
  finished digest and script when the 403 arrived.

Runs lost in `setup-python`: Planetterrian, Fascinating Frontiers, Omni View,
Top World, and Africa & Middle East (that desk skips on member demand later in
the run anyway).

## 2. The xAI account ran out of credit (operator)

At about 09:45 UTC every Grok call began returning 403 "used all available
credits or reached its monthly spending limit". The show runs, the producer
inbox and TTS all stopped. `engine/provider_quota.py` did its job: shows that
had not started stopped at the pre-flight with the billing message, instead of
paying for generation first.

Nothing on the Voices side checked the account. A Nerra Voices interview with
a real guest is booked for **Oct 23 20:45 UTC**, and Mira's live room is a Grok
Voice session on the same account. Fixed for every future booking (§3.4). For
today the fix is console.x.ai → Billing.

## 3. Fixed in code

1. **The mirror is the last resort** (`.github/actions/setup-python`).
   Yesterday's four bounded retries could not help: the Ubuntu mirror served
   nothing for fifteen minutes and every attempt ran out.
   - The .debs one run downloads are now cached per runner image
     (`ImageOS`/`ImageVersion` in the key, `actions/cache/restore` and
     `/save`). Every later run on that image installs them with
     `--no-download`, with no mirror involved.
   - On a cache miss, when apt still cannot finish within ten minutes, ffmpeg
     comes from the pinned, checksum-verified BtbN 8.1.3 build that `test.yml`
     already runs the whole suite on. The guard keeps the two tags equal. Any
     package other than ffmpeg still fails loudly.
   - `setup-ffmpeg` (the Voices workflows) gets the same fallback.
   - Today GitHub's cache also refused restores ("Egress is over the account
     limit"). A refused restore is a miss, so the run takes the mirror path,
     then the static build if needed.
2. **The catalog marks what aired** (`engine/content_lake.py`,
   `engine/catalog.py`, `run_show.py`).
   - Cause: run_show writes the episode to the lake twice, the second time
     once the script exists. The second write deleted and re-inserted every
     item without its story id. The catalog write that followed sent NULL
     story ids, and `article_rows` skipped every item without one, so
     `articles_aired` read 0 on every run.
   - A re-store now keeps the id of an item it did not change, and the run
     re-assigns ids after the second write.
   - "Aired" is now read from the item's URLs alone, so an essay's sources
     count.
   - The day's 31 aired rows were repaired in place.
3. **A query string that names the page is kept**
   (`engine/content_tracker._normalize_url_for_dedup`).
   - The key dropped every query parameter. As a result every PLOS One paper
     (`article?id=`), AEA article (`articles?id=`), YouTube video (`watch?v=`)
     and PIB release (`?PRID=`) shared one key. The tracker's 45-day URL window
     could then drop a different paper as "already covered"; four such
     collisions were found in the committed digests.
   - Identity parameters (`id`, `v`, `p`, `prid`, `doi`, …) are now part of
     the key; tracking parameters (`utm_*`, DW's `maca`) still merge.
4. **Mira checks the account at T-2h** (`pipelines/voices/fire_interviews.py`).
   - The reminder step makes one one-token completion. On a billing stop
     (matched by the same `engine.provider_quota` matcher the shows use),
     Patrick gets a critical Slack alert and an email naming the guest and
     the start time, two hours before the room opens.
   - Any other failure, such as a network error or a bad key, is not an alarm.
5. **The video sweep restarts a job that never rendered** (`scripts/video_job.py`).
   - The sweep still never restarts a handoff with any run, because a failed
     run may have uploaded.
   - The exception: exactly one run that failed or was cancelled before its
     "Render and publish the video" step started cannot have uploaded
     anything, so the sweep starts it once more. First Principles' video, lost
     in setup today, qualifies.
6. **The Cloudflare account is on Workers Paid.** CLAUDE.md, both Worker
   configs, the scheduler README, the Voices handler comment and the Nerra
   Daily doc had said the five-trigger Workers Free limit still applied.
   - Each Worker keeps its one trigger because the handler decides from the
     firing minute, not because a second trigger would be refused.

## 4. Read and not changed

- **AI Chips' publish guard:** it warned that the lead chapter "Top Story" is
  a generic label. That is the Oct 14 fallback: the hook is too long to be a
  title whole and no headline matched. A clipped hook would break the "fits
  whole" rule, so the warning stands as information.
- **MAB's model warning:** "script-stage model override 'grok-4.6'
  unavailable — episode generated on 'grok-4.3'" was the billing stop arriving
  mid-run, not a model problem.
- **Spend after the stop:** a show that dies at TTS on a billing stop loses
  the digest and script it paid for, and the rerun pays again. That is about
  $0.10–0.30 an episode; preserving them for a resume is a larger change.
- **Content of the four episodes:**
  - Every first chapter starts at 0 s.
  - The spoken-text gate passed 4/4.
  - Claims verified: UC 2/4 (2 flagged), FPD 2/2, Collingwood 18/18, North
    America 28/28.
  - The 4.7 scripts copy 3–29% of their digests at 77–84% coverage.

## 5. Operator

- **Now:** console.x.ai → Billing. Add credits or raise the monthly limit
  before the 20:45 UTC interview. Then re-run the eleven failed shows from
  Actions (Run Podcast Show) and the five setup failures. After 06:50 ET the
  Nerra Daily gate will not build today's edition, so dispatch Nerra Daily
  Edition by hand if you want one.
- After this merges, the sweep restarts First Principles' video on its own.
- Producer inbox: the two threads that failed are retried by the next tick
  once credit is back.
