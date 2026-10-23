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

## 6. After the re-runs: Nerra Daily Ep064 shipped partial, then rebuilt

The twelve failed shows were re-run at 14:29 UTC after the operator added
credit. Eleven published on the first run. Prediction Markets made its episode,
then failed post-run validation on a single 8-second read timeout fetching the
MP3 it had just uploaded; it published on a second run. Top World ran once the
desks were settled.

Nerra Daily Ep064 went out at 14:48 UTC with 6 of 15 segments. A landing
re-run woke the gate, and past the 06:50 ET hold the gate builds from whatever
has landed. Its queued X post was cancelled before its 15:00 UTC slot. The
partial edition was withdrawn (PR #1537: the summaries entry, the feed item,
the post and the metrics) and rebuilt at 15:07 UTC with all 15 segments, at the
same episode number and R2 key. The feed item has a new GUID, so an app that
fetched the 14:48 version may list the episode twice.

**Fixed:** past the hold, the gate now waits for a missing roster show whose
run started after the hold and has not yet woken the gate. Each such run wakes
the gate when it ends, so the last re-run builds the edition. The 7:00 ET
release is unchanged for morning stragglers. Guards: `TestReRunsWait`.

**Read, not changed:** post-run validation fails a run on one 8-second timeout
reading a just-uploaded enclosure. One retry would have saved a $0.33 re-run;
it stays as is until it recurs.

## 7. How the re-run episodes turned out

Sixteen English episodes published on Oct 23, the re-runs included. Each was
read in full against its script and digest, and every finding below was
checked against the committed files before it was kept. A Whisper mishearing
of a word the script has right is not counted.

**The machinery held on every run.**

- The spoken-text gate passed 16 of 16.
- Every script arm served its own model, with no fallback.
- Every run wrote to the story catalog.
- Today's catalog has 220 of 1,357 articles marked aired. Every run before
  the morning fix had read 0.
- The rebuilt Nerra Daily Ep064 is complete:
  - 15 segments, 138.5 minutes, nothing in `missing_expected`;
  - every segment's promo tail trimmed;
  - no handoff realigned or revised.
- The edition's X post went out at 15:36 UTC, from the 15:30 queue slot.
  The FF and Planetterrian posts went on their slots, and the other five
  were queued for the afternoon.
- All nine video renders committed.
- Seven long-forms are scheduled from 16:00 UTC, and every show has its
  hook Short.
- Three render runs read "cancelled". In each one only the follow-on
  homepage job was cancelled, superseded in its own concurrency group as
  designed.
- Six shows got their translation tracks. Planetterrian and Omni View have
  multilingual switched off.

**Wrong facts on air, corrections filed** (`corrections.yaml`; text amended
with `scripts/apply_corrections.py`; the audio is unchanged until it is
re-synthesized):

| Episode | What aired | What is right |
|---|---|---|
| Omni View Ep214 | The Dow fell 800 points "on Friday" | Thursday, Oct 22. The only source is CNBC's Oct 22 live page |
| Omni View Ep214 | American Express announced a $336M restructuring charge | No source on the Volvo item says so. The sentence is withdrawn |
| Fascinating Frontiers Ep231 | Pressure at the base of the mantle equals the weight of the whole atmosphere | About 1.3 million atmospheres |
| Modern Investing Ep209 | Two TSX closes, 35,569 (−1.1%) and 35,973 (−1%) | 35,569. The arithmetic puts 35,973 as the previous session's close. Both numbers were in the digest |
| SpaceX Ep139 | SPCX "closed higher" | The run was mid-session, so it was trading higher. The verb came from the script model, not the quote line |
| UC Ep151 | India's vultures fell "to one-thousandth" | That is the white-rumped vulture. The other two species fell about 97%, as the episode itself said later |

UC Ep151's 1994 patent-expiry framing is a claim the gate flagged
(`unverified_quote_mismatch`). It aired as fact, which is the Oct 1 policy:
it was published and marked. The public claims record shows the flag.

**Listener-facing, not corrected (P2):**

- **Map sentences.**
  - Vancouver's map ran to four stories.
  - MAG 7's map gave its three stories out of order.
  - Collingwood's map promised "roads" on a day the digest had none.
  - MAB's map named its deep dive on the lead story.
  - Tesla's map named "Counterpoint", a segment its prompt tells the script
    never to announce. The segment aired as the solar-roof story.
- **Calendar and horizon blocks re-told body facts:** MAG 7 (two items),
  AI Chips (three items).
- **Facts told twice:**
  - SpaceX's Grok Bot story;
  - Planetterrian's sleep lead;
  - Collingwood's award;
  - Omni View's sailor toll;
  - UC's 4.7% figure.
- **Self-narration lines:** MAG 7, AI Chips and Omni View, one each.
- **Prediction Markets aired one sentence, "That is a proposal, not a law on
  the books", for a story whose body it never told.** The digest's Cruz-bill
  item was a headline and a Source line with no body. That shape occurred
  once in 470 October digests, so it gets no new gate.

**Not a defect:** the Tesla map's "Counterpoint" was first read as a promised
segment that never aired. The digest has its Short Spot, and the Counterpoint
aired as the solar-roof leak story.
