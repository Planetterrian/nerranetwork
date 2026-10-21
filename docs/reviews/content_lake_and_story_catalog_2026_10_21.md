# Content lake and a story catalog — review and recommendation (Oct 21 2026)

**The operator's question:**
- Should the content lake be improved, perhaps by moving it into Supabase?
- Would better story cataloguing help memory, duplication and content creation, so the shows cover every new story and stop repeating ones they have already told?

**How this was answered:**
- Read the code paths behind each finding below.
- Measured against the committed data for Oct 7–21. The measurement scripts were throwaway and were not committed.
- Nothing in the pipeline was changed by this review.

## 1. Verdict in one paragraph

A database would help, but it is not the first fix. The three largest defects are about **what** gets recorded, not **where**:
- The cross-episode tracker records every article the prompt *listed* as "covered", rather than the items that *aired*.
- The lake that CI rebuilds from the repo holds no headlines or links at all.
- Nothing durable records the articles a show fetched and did not use.

Fix the recording first. It is cheap, it uses no new infrastructure, and it changes what reaches the prompts tomorrow. Then build a **story catalog**: stories with ids, the outlets behind each one, and which show aired it, when and with what. The right home for it is a `catalog` schema in the existing Nerra Voices Supabase project. It is the one durable store every show runner can already reach.

## 2. What exists today

**The content lake** (`engine/content_lake.py`):
- One SQLite table, `episodes`, with an FTS index.
- It is gitignored and rebuilt from the committed digests in every CI job (`scripts/backfill_content_lake.py`).
- It is episode-level only: no items, no per-item links, no story ids, no claims, no corrections, no unused articles.
- The rebuild writes `headlines=[]` and `source_urls=[]` (`backfill_content_lake.py:160,254,299`). In CI the lake knows each episode's hook and digest text, and nothing item-shaped.

**Consumers that work:** the Sunday week-in-review segment, the weekly newsletter synthesizer, slow-news segment choice, site search and the topic hubs (through `site/data/search-index.json`), and the dashboard counts.

**The consumer that does not work:**
- The "topics recently covered by other Nerra shows" block (`run_show.py:2484-2515`) filters on `ep.get("headlines")`. The rebuilt lake never has any.
- So **all 23 prompts that carry `{cross_show_context}` read "(No recent cross-network coverage to dedupe against today.)" every day**. The feature has never run in production.

**Memory and repetition** live in six other places, each per show and each matching stories on salient words its own way:
- the ContentTracker JSON (45 days)
- story recurrence
- the hook-recurrence gate
- story clusters
- digest overlap
- Nerra Personal's edition memory

Salient-word story matching is implemented four separate times.

## 3. What was measured

| Question | Finding |
|---|---|
| How much of the prompt airs? | Median items shipped / articles in prompt: Tesla 27%, M&A 29%, AI Chips 25%, MAG 7 20%, SpaceX 18%, Omni View 17%, MAB 6%, MIT 8%. |
| What does the tracker remember as "covered"? | The prompt list. Only 8 of Tesla's, 21 of SpaceX's and 12 of M&A's last 40 "do not repeat" headlines actually aired. |
| How good are the "already covered" notes? | Replayed day by day: 4,910 notes, of which **63–75% cite a headline that never aired**. 2,686 claimed a story ran on 2 or more days when it aired on fewer, and those counts feed the hook gate. |
| What happens to an unused article? | Its URL is blocked from that show's prompts for 45 days (`content_tracker.py:1011`, `url_window = max(day_window, 7, max_days)`). On every show, 0 unused prompt URLs ever came back. |
| Are unused stories covered later? | Oct 7–14: of 4,629 prompt titles that did not air, 7% were covered later by the same show, 11% by another show, **84% never** (title matching, so this is an upper bound). Articles fetched beyond the 60-article prompt cap are stored nowhere, so for them the question cannot be asked. |
| Does a show retell its own stories? | Share of aired headlines matching that show's aired headlines of the previous 7 days: SpaceX 22%, Tesla 16%, MIT 16%, FF 11%, M&A 11%, MAG 7 9%, Omni View 5%, Planetterrian 2%. Some of these are legitimate updates. |
| Do shows duplicate each other? | Rarely. In 15 days, apart from the desks feeding Top World (which is by design): SpaceX+Tesla 3–4 stories, MAG 7+MIT 4, FF+SpaceX 3, FF+Planetterrian 2, AI Chips+MAG 7 2, Omni View+Europe desk 3–4. |
| Size of the corpus | 2,478 digests, 18,558 aired items, 14,599 distinct Source URLs, 6,242 claims-ledger entries. |

**What the measurements say:**
- **The problem is not one show repeating another.** It is three things:
  - a show retelling its own story (up to one aired headline in five);
  - a memory that cannot tell an aired story from one that was only listed;
  - an archive that forgets everything not chosen.
- **The 45-day URL block** quietly suppresses a story a show passed over once, even when it develops into the day's news.
- **The inflated day counts** make the hook gate and the "ALREADY-COVERED" notes treat stories that never aired as stale.

## 4. Recommendation

### Phase 0 — record the right thing (no new infrastructure)

1. **The tracker records what aired.** Pass the shipped items' titles and Source URLs, taken from the final digest after the overlap dedupe, to `record_episode`, instead of the prompt list. A separate short "listed, not aired" list may stay for the title-similarity check, but it must never feed the "already covered" notes, the "DO NOT repeat" list or the hook gate's day count.
2. **An unused URL is not blocked for 45 days.** The long URL window exists so an *aired* page cannot re-air: the 2013 Teslarati page that aired three times. A URL that was listed and not aired is blocked for a few days at most, so a story that develops can come back.
3. **The rebuilt lake carries item titles and Source URLs.** The backfill parses them from each committed digest with the same item readers the lints use (`engine.digest_lint.items`). The cross-show block then works on the next run. Its wording should say *covered by another show, from that show's angle*, never "avoid", because a Tesla listener still needs the merger story SpaceX led with. ⚠️ AUDIO: it changes the prompt input on 23 shows, so A/B-listen it.
4. **One salient-word matcher.** Recurrence, clusters, overlap and Personal each tokenise and weight differently: 0.05 against 0.30 document-frequency cut-offs. Consolidate before a catalog depends on them.

The first three are a small change and a large one in effect. Every "already covered" note and every hook-gate decision on every news show changes from tomorrow, so they ship with a readout: recurrence notes per episode, hook-gate firings, and the retell share in the table above.

### Phase 1 — a story catalog

**Where:** a new `catalog` schema in the **existing Nerra Voices Supabase project** (`nerra-voices`, ca-central-1, Postgres 17).
- The show runners already hold its credentials: `run-show.yml` passes `VOICES_SUPABASE_URL` and `VOICES_SUPABASE_SERVICE_KEY`.
- `pg_trgm` and `vector` (pgvector 0.8) are available to enable.
- A separate schema keeps the news data apart from the guest tables, which hold personal data, and lets the catalog move to its own project later with a dump and restore.
- A new project would add a monthly compute charge and a second set of secrets, for no capability the schema lacks.

**Tables:**

| Table | One row per | Key fields |
|---|---|---|
| `articles` | canonical URL | title, outlet, published date + `date_source`, first_seen, shows that fetched it |
| `stories` | story | first_seen, last_seen, working title, salient tokens, optional embedding |
| `story_articles` | article in a story | story_id, url |
| `aired_items` | item that aired | show, episode, date, section, title, Source URL(s), story_id, claims verified / flagged |
| `corrections_index` | correction | show, episode, story_id |

**Rules that keep it safe:**
- **The committed digests stay the record.** The catalog can be rebuilt from them for aired items. The one new thing it holds is fetched-but-unused articles, and losing those loses a measurement, never an episode.
- **A run never waits on it.** Writes happen after publish. Reads before the prompt use a short timeout and fall back to the Phase 0 tracker. This is the same fail-open shape as `engine/x_queue.py`.
- **Unused articles expire** after 90 days. Aired items are kept.
- **Size:** about 3,000 fetched articles a day across the network is about 1M rows a year at roughly 300 bytes, before expiry. Aired items are about 100k rows a year. That is well inside the project's limits. Embeddings stay off until salient-word matching is shown to miss real rewordings, and they would need an embedding provider: the network's LLM provider is not one of the in-repo options today.

### Phase 2 — what the catalog makes possible

- **"Update, never retell" on every show.** The note under an article says "this show aired this story on Oct 18 (Ep639); since then these sources are new: …", and it fires only when the story actually aired. This is the Fort Bend fix, made precise.
- **A missed-stories readout.** Each morning: the story clusters carried by three or more outlets that no show aired. That answers "are we covering the news" with evidence rather than a quota. It belongs on the dashboard before any prompt is changed in response.
- **Cross-show awareness.** A show sees that a sibling led with the same story today and takes its own angle: Tesla on the merger's effect on Tesla, rather than SpaceX's telling.
- **Corrections that follow the story.** A correction filed on one show flags every other episode that aired the same story id, for review rather than automatic amendment.
- **Nerra Personal and Nerra Daily** read story ids instead of re-matching headlines, so "you heard this on Tuesday" and the cross-show repeat notes become exact.
- **Story pages for the site.** One evergreen page per developing story, with the timeline of every episode that told it. These are the searchable landing pages the dated posts cannot be: the `/topics/` reasoning, applied one level down.

## 5. Decisions for the operator

1. **Phase 0.** Change what the tracker records, and shorten the unused-URL block. This changes prompt input on every news show, so A/B-listen it.
2. **Phase 1 location.** A `catalog` schema in `nerra-voices` (recommended), or a separate project.
3. **The cross-show block.** Re-enable it with "another show's angle" wording, or remove it. It has never run, so removing it changes no shipped audio.
