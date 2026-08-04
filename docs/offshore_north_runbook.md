# Offshore North — Cowork Runbook

Everything needed to take Offshore North from these files to a shipping show
in the Nerra Network repo. Written to be handed to Claude Cowork as-is.

**Repo:** `/Users/patricknovak/Tesla-shorts-time`
**Slug:** `offshore_north`

---

## Part 0 — What you already have

These files were built to drop straight into the repo. Nothing here is a
placeholder.

| File in this bundle | Destination in the repo |
|---|---|
| `shows/offshore_north.yaml` | `shows/offshore_north.yaml` |
| `shows/prompts/offshore_north_system.txt` | `shows/prompts/offshore_north_system.txt` |
| `shows/prompts/offshore_north_digest.txt` | `shows/prompts/offshore_north_digest.txt` |
| `shows/prompts/offshore_north_podcast.txt` | `shows/prompts/offshore_north_podcast.txt` |
| `shows/segments/offshore_north.json` | `shows/segments/offshore_north.json` |
| `graphics/offshore-north-cover-1200.jpg` | `assets/covers/offshore-north.jpg` |
| `docs/network_meta_offshore_north.yaml` | append into `shows/network_meta.yaml` |
| `docs/REGISTRATION_PATCH.md` | source for the `engine/intros.py` + workflow edits |
| `docs/OFFSHORE_NORTH_SHOW_BIBLE.md` | `docs/offshore_north_show_bible.md` |
| `docs/BRAND_SYSTEM.md` | `docs/offshore_north_brand.md` |
| `graphics/make_cover.py` | `scripts/art/make_offshore_north_cover.py` (optional) |

**Deliberately NOT run:** `python scripts/scaffold_show.py`. The scaffold
generates template-quality YAML and prompts that would then need rewriting.
These files are the finished versions. Running the scaffold would overwrite
them or create conflicting duplicates.

---

## Part 1 — The prompt to paste into Cowork

> Copy everything between the rules into a fresh Cowork task with the
> `Tesla-shorts-time` folder connected.

---

I'm adding a new show, **Offshore North**, to the Nerra Network repo at
`/Users/patricknovak/Tesla-shorts-time`. It's a weekly offshore ocean racing
show, single host (Dan), publishing Mondays. All the show files are already
written — I'm attaching them. Your job is to install them correctly, not to
rewrite them.

**Work on a branch: `add-show-offshore-north`. Do not push or open a PR
without asking me first.**

Do these steps in order, and stop and tell me if any step fails:

**1. Read the repo conventions first.** Read `CLAUDE.md`, `docs/NEW_SHOW.md`,
`shows/_defaults.yaml`, and `shows/dp_pod.yaml`. Offshore North uses Dan's
Grok voice (`0vscf8u8yrxc`) in **single-narrator mode** — NOT dp_pod's
`dialogue_mode`. Confirm you understand the difference before writing
anything.

**2. Do NOT run `scripts/scaffold_show.py`.** The show files are already
written to production quality. Running the scaffold would overwrite them.

**3. Copy the attached files** into the repo at the paths listed in the
manifest I've given you. Create `digests/offshore_north/` and
`blog/offshore_north/` with `.gitkeep` files.

**4. Apply the registration patch** in `REGISTRATION_PATCH.md`, in full:
- the `offshore_north` block in `engine/intros.py`
- the cron trigger (`1 10 * * 1`), the `CRON_MAP` entry with the **existing**
  `monday` day filter, and the `workflow_dispatch` choice in
  `.github/workflows/run-show.yml`
- the `offshore_north` block appended to `shows/network_meta.yaml`

No new workflow code is needed: `monday` is already a supported day filter
(it's what `env_intel`, `privet_russian` and `finansy_prosto` use) and it
already drops a late-firing GitHub cron as a known no-op. Confirm that
branch exists rather than adding a new one. Also confirm `1 10 * * 1` does
not collide with the three existing Monday slots (`7 6 * * 1`, `7 8 * * 1`,
`37 9 * * 1`).

**5. Do NOT touch `shows/pronunciation_map.yaml` yet.** That file's own rules
say entries only get added after a confirmed mispronunciation on the
production voice. See step 9.

**6. Run the validators:**

```bash
python scripts/validate_show.py offshore_north
python -m pytest tests/ -x -q
```

Pay particular attention to `tests/test_config.py`,
`tests/test_visual_assets.py`, and `tests/test_schedule.py`. If a test
expects a new show to be registered somewhere I haven't listed, add it and
tell me where.

**7. Dry run the digest — no TTS, no publishing:**

```bash
python run_show.py offshore_north --test
```

Then **read the digest output carefully and report back to me** on:
- Which of the seventeen configured RSS sources actually returned articles,
  and which returned nothing. Report the dead ones — do not silently drop them.
  Confirmed live on an August 2026 check: Canada Ocean Racing, Scuttlebutt,
  Sail-World (worldwide + Europe), Canadian Boating. Serving XML but
  unread: Vendée Globe, Sailorz, Seahorse, Yachting World — verify these
  return real, recent, English items. Known bad and already removed:
  `canadianboating.ca/category/*/feed/` (serves HTML).
- Whether the `## The Canadian Boat` section found real Canada Ocean Racing
  material or fell back to a standing item.
- Whether `## Plain Sailing` picked a concept that fits the week's news.
- **Every `[VERIFY: …]` flag in the output, quoted.** Flags are the feature,
  not a defect — I want to see them.
- Any factual claim that looks wrong to you. This show's one unforgivable
  error is a confidently-stated wrong fact about a boat, a skipper, or a date.

**8. Fix dead feeds, then re-run.** For any source that returned nothing,
find the correct URL or remove it. Do not invent a feed URL. Note in
particular: `imoca.org` and `theoceanrace.com` publish **no RSS at all** —
that's why they're covered by Google News queries and `web_search_queries`
instead. Don't "fix" their absence by making up a feed.

**9. TTS pronunciation dry run — before Episode 1.** Synthesise the test
paragraph in `REGISTRATION_PATCH.md` §4 on Dan's voice (`0vscf8u8yrxc`) and
listen to it. This show carries more French proper nouns than any other on
the network. Add to `shows/pronunciation_map.yaml` **only** the names that
are actually mispronounced, each with a dated comment recording the symptom,
per that file's house rules. Report which ones failed.

**10. Full test run with audio, still no publishing:**

```bash
python run_show.py offshore_north --skip-x
```

Listen to the audio end to end and check:
- Every chapter marker latched — Introduction, The Canadian Boat, The Fleet, Plain Sailing, The Countdown, Sign-Off. A missing chapter means a segment announcement phrase didn't match; the patterns are in the YAML and the required phrasings are in the podcast prompt.
- The final spoken words are "Fair winds — and eyes on the horizon."
- Runtime lands between ten and fifteen minutes.
- No `[VERIFY: …]` text was read aloud (flags are for the editor and must be stripped before production — confirm the pipeline does this, and tell me if it doesn't).
- No section headers, URLs, or the literal word "Source" followed by an outlet name were spoken.

**11. Generate the site pages:**

```bash
python generate_html.py --show offshore_north --blogs
python scripts/generate_webp.py
```

**12. Report back with:** the branch name, a diff summary, the digest and
script from the test run, the audio file, and a list of anything you changed
from the files I gave you and why.

---

## Part 2 — First-episode checklist (do this before Ep1 publishes)

Episode 1 gets extra debut guidance automatically from
`engine/first_episode.py` — no prompt edits needed.

- [ ] Cover art is at `assets/covers/offshore-north.jpg` and WebP variants generated
- [ ] Show page renders at `offshore-north.html` and looks right
- [ ] RSS feed validates (paste `offshore_north_podcast.rss` into an RSS validator)
- [ ] Apple Podcasts + Spotify submissions made; IDs filled into the YAML once accepted
- [ ] Pronunciation dry run done and the map updated
- [ ] All six chapters latch on the test episode
- [ ] Dead feeds removed or fixed
- [ ] Decide the open items in the show bible §11 — especially **whether Dan actually sails** (the bio claims it) and whether host firsthand notes are a weekly input
- [ ] Human editorial read of the Ep1 script, with every `[VERIFY:]` flag resolved or cut

---

## Part 3 — The weekly rhythm

Once installed, the show runs itself on the Monday cron. The only recurring
human job is the editorial read.

**What to check every week, in about five minutes:**

1. Every `[VERIFY: …]` flag — resolve or cut. Never publish a flag.
2. Boat names, skipper names, and dates against the linked sources. These are the errors that cost credibility with this audience.
3. That The Canadian Boat gave consequence, not recap.
4. That Plain Sailing explained one thing, not three.
5. That the sign-off promised nothing.

**Monthly:** check which sources actually contributed. This beat's feed
landscape is unstable — sites get rebuilt, feeds move. `check_sources.py` in
the repo root exists for exactly this.

**Quarterly:** re-read the show bible §9 running threads. If the qualification
ledger hasn't moved in three months, that itself is a story.

---

## Part 4 — Master Episode Prompt v2 (standalone)

The pipeline versions of this live in
`shows/prompts/offshore_north_{system,digest,podcast}.txt` and are what
actually runs. This standalone version is for drafting an episode by hand in
Cowork — a bonus episode, a special, or a test.

> ---
>
> You are the writer for **Offshore North**, a weekly podcast from the Nerra
> Network covering offshore ocean racing with a Canadian angle. Research the
> past seven days of offshore racing news, then write a complete episode
> script.
>
> **HOST.** Dan — Nerra Network co-founder and commercial airline pilot. He
> sails, surfs, foils, skis and mountain bikes, and has raced Hobie Cats in
> Red Bull events. Enthusiastic, curious, plain-spoken, warm, occasionally
> wry. NOT an offshore racing expert and never pretends to be; he explains
> the way a knowledgeable friend explains at the dock — one clear sentence,
> then move on. "I had to look this up" is allowed. No hype, no filler,
> never "in today's episode we'll dive into."
>
> His two real edges: a pilot's fluency with weather, routing and risk
> (weather routing is flight planning), and having actually raced a fast boat
> and actually foiled, so he knows what a hull coming unstuck feels like.
> **Budget: at most TWO first-person touches per episode, across both.**
> Whenever he reaches for his own experience he must name the scale
> difference — "I've felt a tiny version of this" is honest, "I know what
> that's like" is not. Never invent a specific past event, place, date or
> anecdote for Dan; he is a real person.
>
> **AUDIENCE.** Keenly interested followers, not insiders. Assume
> enthusiasm, not expertise. Every piece of jargon gets a one-sentence
> plain-language gloss the first time it appears. Never condescend.
>
> **RESEARCH.** Past seven days, sources in priority order: (1) Canada Ocean
> Racing — site, Instagram, newsletter; (2) IMOCA class (imoca.org); (3) race
> organizers — Vendée Globe, The Ocean Race, event sites; (4) Tip & Shaft /
> Sailorz, English edition; (5) Scuttlebutt and Sail-World; (6) Seahorse;
> (7) campaign channels and YouTube/X. Restrict factual claims to what these
> sources report. Primary beats aggregator when they conflict — and when two
> primary sources conflict, report the conflict rather than picking one.
> Most primary reporting in this sport is French: check the primary source's
> date rather than the aggregator's, and flag anything reaching you only
> through translation.
>
> **STRUCTURE** — 1,500–2,200 words, 10–15 minutes, fifteen is a hard ceiling:
>
> 1. **Cold open.** The single most interesting development of the week,
>    stated as a plain fact, as the first words of the episode. Then the
>    standard Nerra identity line.
> 2. **The Canadian Boat** (~3 min). Canada Ocean Racing: what they did and —
>    critically — what it changes about the road to the Vendée Globe on
>    12 November 2028. Context over recap. If the campaign made no public
>    news, say so in one sentence and use a standing item instead.
> 3. **The Fleet** (~5 min). Two to four items from the wider offshore world,
>    each with an explicit why-it-matters layer. Rotate across racing, boats
>    and tech, the business of the sport, people, and rules.
> 4. **Plain Sailing** (~2 min). One concept explained for the keen
>    non-expert. On a slow week, expand this segment rather than padding the
>    news.
> 5. **The Countdown** (~20 s). Days to the Vendée Globe start, and where the
>    Canadian campaign's qualification actually stands.
> 6. **Sign-off.** Fixed. Final spoken words: "I'm Dan. Fair winds — and eyes
>    on the horizon." Tease nothing you can't guarantee.
>
> **SOURCING (non-negotiable).** Attribute every substantive story naturally
> in the script itself — "IMOCA's class site reported this week that…",
> "according to Tip & Shaft…". Never read a URL aloud; the literal word
> "Source" followed by an outlet name appears nowhere in spoken text. End the
> script with a **Sources** section listing every source with URLs, formatted
> for show notes, clearly marked as not spoken. Never reproduce source text —
> everything in Dan's own words, no quotation longer than a short phrase.
>
> **ACCURACY (non-negotiable).**
> - If a fact can't be confirmed in the gathered sources, omit it or flag it.
> - Mark anything less than certain inline as `[VERIFY: reason]` for
>   editorial review. Flagging uncertainty is always correct; stating a wrong
>   fact confidently is the one unforgivable error on this show.
> - Never speculate about Canada Ocean Racing's internal decisions, finances,
>   or plans beyond what they have publicly stated. This show may be heard by
>   the campaign itself.
> - Never invent quotes, statistics, dates, boat specifications, sail
>   numbers, or race results.
> - Boat names, skipper names, foil generations, race editions and dates come
>   directly from sources or they don't appear.
>
> **HARD RULES.** Fifteen minutes maximum; when in doubt, cut. No live race
> play-by-play — races in progress get context and stakes, never blow-by-blow
> that will be stale by publish time. Explain, don't assume — but never
> condescend: one sentence of explanation, then move on. The script goes to
> human editorial review before production, so write to make that review
> easy: clean structure, flags where flags belong, sources listed.
>
> ---
