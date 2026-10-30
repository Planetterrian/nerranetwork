# Slate review: Oct 28-30, 2026

Every show and workflow from Oct 28 12:00 UTC to Oct 30 16:00 UTC: about 600
workflow runs and 57 episodes across 23 shows and three Nerra Daily editions.
I read the metrics for every episode. Four reviewers compared each episode's
script, Whisper transcript, digest and claims ledger, and every finding below
was checked against the committed files before anything was changed. Register
`slate-2026-10-30`; guards `tests/test_slate_2026_10_30.py`.

## 1. The slate

- **Runs.** Every show run succeeded except one (AI Chips, Oct 28, §2.1).
  The two cancelled finalize jobs were superseded, which is normal.
- **Interviews.** The two post-interview runs cancelled at the two-hour limit
  on Oct 28 were Michael Kamins' room. Its `tidy_lines` loop was fixed the same
  day.
- **Video.** 20 of 20 video jobs published.
- **Spoken-text gate.** Passed on every episode, with no tag leaks.
- **Nerra Daily.** Ep070 and Ep071 went out on time (10:35 UTC build, X post
  at 11:00). Ep069 did not (§2.2).

## 2. Workflows: fixed

### 2.1 A finished episode failed on one timeout (AI Chips Ep037)

The Oct 28 run produced, uploaded and published Ep037. Post-run validation
then sent a HEAD request to the new enclosure through OP3's redirect. The
CDN's first fetch of a 23 MB object took longer than the 8 s read timeout, so
the run exited 1. As a result:

- nothing was pushed;
- Nerra Daily built without AI Chips;
- GitHub's fallback cron made the whole episode again at 17:01, at full
  generation cost.

`engine/post_run_validation.py` now retries a transport error or a 5xx twice,
with 8, 20 and 45 s timeouts. A 4xx still fails at once.

### 2.2 Nerra Daily Ep069 spent 81 silent minutes downloading

The build logged its lineup at 10:52:15 and then nothing until the links call
at 12:13. Every other build that week took about six minutes. The edition
published at 12:17 UTC, and its X post went to the 12:30 slot.

The cause: the segment loop downloaded each MP3 with
`requests.get(stream=True, timeout=600)`. That is a read timeout only, so a
CDN that trickles never trips it. There was no log per segment, and the ffmpeg
trims had no timeout either.

`engine/http_download.py` is now the one bounded way to pull a published file
back down, and Nerra Daily and Nerra Personal both use it:

- 20 s connect timeout and 60 s read timeout;
- 300 s wall-clock limit per attempt;
- 3 attempts, and a 4xx is never retried;
- one log line per file with its size and time;
- a `.part` file that only becomes the real file when the download completes.

On top of that:

- The edition's segment loop has a 20-minute budget. After that, each
  remaining download gets one attempt.
- Each trim logs its cut.
- `_run` has a 600 s timeout in both builders.

### 2.3 Google News links lost their query values

The batchexecute reply nests the publisher URL as a JSON string inside JSON,
so an `=` arrives as `=`. The resolver's regex (`[^\\"]+`) stopped at the
first backslash. Every resolved link with a query string lost its values:

- `news.sbs.co.kr/amp/news.amp?news_id`
- `abcnews.com/…/story?id`
- `flatpanelshd.com/news.php?subaction`

That is about one link a day since Sep 23, on the blog, the feed, the
newsletter, the claims ledger and the story catalog. The catalog shows the
truncation happens at fetch.

`engine.url_utils._garturlres_url` now parses each chunk as JSON, with an
escape-aware fallback. Links already published stay as they are; the original
Google News redirect URLs are not kept.

## 3. Content: fixed

### 3.1 Claims labels

- **PDF sources published as "not found".** UC published two true claims
  whose sources are PDFs (the RSPCA breed-law review, an EIA report) as
  `unverified_not_found`, which is the public fabrication label. The real
  reason was "empty or non-text body": the verifier cannot read a PDF. A 2xx
  that returns nothing readable is now `unverified_unreachable`. It is still a
  gate failure, now labelled for what it is.
- **A verified claim flagged by its own duplicate.** Tesla Ep650's V2L fault
  claim appeared twice in the ledger: verified from the fetched copy, and
  unreachable through a reddit 403. The post therefore carried an
  "unverified" badge on a claim that checked out. In flag mode, an unverified
  entry whose claim text matches a verified entry is now dropped, along with
  its failure and its flag. This is the only case in 176 ledgers since
  Oct 20.

### 3.2 The Peptides card lint never passed

`spotlight_card` looked only for **bold** labels, but the prompt asks for "each
opening with its label and a colon" and the model writes them plain. The lint
fired on the complete cards in Ep6 and Ep7 and used up the structural
regeneration both weeks.

A slot is now its label at the start of a line, bold or plain. It still
catches Ep5's genuinely missing regulatory slot.

### 3.3 Prompt rules spoken on air

Three lines aired:

- "Say implied probability once and leave it there: …" (Prediction Markets
  Ep038)
- "The brief record does not give…" (UC Ep156)
- "Then the case on both sides, if the day gives one." (Top World Ep038)

The self-narration filter now matches all three. Swept against 2,615
committed scripts, the new patterns match only these aired lines; a language
lesson's "Say it once more" is not matched. UC does not run the absence
filter, so its line is covered by the length change in §3.6 and remains a
prompt matter.

### 3.4 Prediction Markets' Friday recap

`engine/board_week.py` had three problems:

- Ep037 wrote the ceasefire row as "…through October 31 — that date at 96.7
  percent", which read as a different outcome from the week's "Yes". The
  recap stopped at Monday's 85.5 while the same episode's Board said 91, down
  from 96.7. "That date" now counts as Yes.
- A leader change (Netanyahu over Eizenkot on Wednesday) was dropped. It is
  now reported as a change of leader, never as a price move.
- "Democrats sweep, a" lost its trailing article, which had split two Kalshi
  markets.

On the Oct 30 data the block now tracks six questions instead of four.

### 3.5 Nerra Daily

- **Opener memory.** All ten of Ep062-071 opened on the spelled date
  ("October thirtieth, twenty twenty-six…"). The memory normalized only
  digits, so it showed ten different strings. Spelled ordinals after a month,
  and spelled years, now collapse to `[date]`.
- **Handoffs.** The links prompt forbids restating the headline the next
  episode opens on. The model did it on 2-8 handoffs per edition (for example,
  Ep071's MAG 7 handoff repeated the senators' deadline). The one-shot
  revision now counts these echoes as well as name-led openings:
  - an echo is 60% of the hook's salient words;
  - a revision is kept only when it breaks fewer rules in total.

  The revision's old wording, "let the show name arrive … at the end", had
  made "…, <Show> examines" the new skeleton: 13 of 13 in Ep069. Both prompts
  now say mid-sentence and ban that ending. New metrics:
  `handoffs_echoing_hook` and `_first_draft`. ⚠️ AUDIO.

### 3.6 UC length and Tesla's Also Today (⚠️ AUDIO)

- **UC.** The UC script prompt asked for 2,200-2,800 words from briefs that
  ship at about 1,150. Ep158 ran 2,559 words:
  - "EFRA" was said 7 times;
  - the RSPCA review was told three times;
  - the 1996 study, the 2014 amendment and the Veterinary Record span were
    each told twice;
  - four perspective-swap walk-throughs.

  The target now holds only when the brief carries that much: the script runs
  at most about 1.5 times the brief, and a short brief makes a short episode.
  The digest-side expansion remains the length lever.
- **Tesla.** The digest includes the shared Also Today run, but its
  required-section list and its "12 is the ceiling" rule never named it, so
  `digest_also_today_items` was 0 on every episode since Oct 19. Two-sentence
  items filled the Top 12 instead. The section list now names Also Today
  after the Top 12, and the validator's Top News span ends there.

## 4. Open items, not fixed here

- **SpaceX Ep145 led with a four-week-old story** (Crew Dragon Grace docking
  after an Oct 1 launch). The source URL is undated, and the page probe found
  no date. A content-date heuristic is the next step, and it needs a sweep
  first.
- **SpaceX Ep145 and Ep146 contradict each other** on whether Falcon flies
  from Vandenberg (a halt "through mid-December", then "a Falcon 9 mission is
  set for Friday"). Ep146 also says "Vandenberg Air Force Base".
- **SpaceX Ep146 shipped without Market Watch** while a quote block was
  supplied. This is one miss in seven.
- **Tesla Ep650's Short Spot aired without its first sentence** ("40 minutes
  to drive two blocks"). The script opens on "those times". The committed
  metrics do not say which stage removed it.
- **Nerra Daily field notes carry no recorded source.** Ep071's altermagnetism
  note says it is "never confirmed" in MnTe; a reviewer recalls a 2024 Nature
  confirmation. The search runs, but its sources are thrown away. This is
  worth a claims pass. Operator: check before correcting.
- **Nerra Daily keeps each show's own rating and follow ask** (7 of 14
  segments in Ep069). Moving the promo cut to the scripted ask would need the
  matcher extended and swept first.
- **Ep070 AI Chips kept about 24 s of network plug.** "Narin Network" had no
  article; this was fixed for later episodes on Oct 29. Ep070 itself is not
  repaired.
- **Content errors to consider for correction:**
  - FPD Ep145 says one square mile in the hook and a quarter square mile in
    the body, 27-ton against 22-ton dynamos, and ten times against four times.
  - MIT Ep215 calls a $56B result against a $64.2B estimate a "beat".
  - MIT Ep216 calls Beth Hammack a Fed governor and treats Oct 28's decision
    as "today".
  - Top World Ep038 says Batanes is "a third the size of greater Toronto"
    (about 3%).
  - Top World Ep037's hook says 300,000 people lose fishing income; the item
    says 37,000.
  - UC Ep158 reads a proportion in the 1996 *Injury* study as a count.
- **Smaller items:**
  - Collingwood's "For the weekend ahead" lists next week's events, and it
    says "the feed's current reading".
  - Vancouver aired an out-of-region Kamloops snow warning that had already
    passed.
  - Omni View closes six of seven stories on an undated "what next".
  - M&A's Model Updates were all arXiv preprints on Ep217.
