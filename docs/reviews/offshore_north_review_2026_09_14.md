# Offshore North — editorial review, 14 September 2026

**Scope:** every published episode (Ep001 18 Aug → Ep005 14 Sep 2026), the
operator's twelve-item fix list from the 7 September episode, deep research
on the subjects the show covered this month, and a public campaign
dashboard for the audience.
**Ledger:** `docs/reviews/ledger/offshore_north.yaml` (new).
**Drift guards:** `tests/test_offshore_north_review_2026_09_14.py`.
**PR:** the branch `claude/loving-davinci-t78wuq`.

## 1. What the month sounded like

Five episodes, all shipped, all roughly on length. Structurally the show
worked — chapters latched, the sign-off held, the cold opens were facts.
Editorially it had one defect that produced most of the operator's list:
**the pipeline never read an article.** The digest prompt saw each source's
headline, the feed's one-line teaser and a URL. On a show whose premise is
"read what the campaign actually said and explain it," that produced:

| Episode | What aired | What the source said |
|---|---|---|
| Ep002–005 | EMIRA IV's position "remains unconfirmed" (four weeks running) | 2 Sep, Scott's Notes: "With Emira IV now leaving Canada and heading back to Europe…" — second paragraph of the post the show summarised as "a summary of summer training" |
| Ep004 | "Its news section carried nothing after the seventeenth of August, and its YouTube channel last posted on the thirty-first of August" | Reported *when* three channels changed and *nothing* of what any post said |
| Ep004 | "The standing facts confirm it exceeds eighteen metres" | A writer-only label from the prompt, spoken on air |
| Ep005 | "Boris Herrmann's Team Malizia crossed the line first as The Ocean Race Atlantic began … Herrmann's team posted the result on its own site the day after the finish" | A team-malizia.com headline from the **2 September start**, re-surfaced by Google News on 12 September. The race had **finished on 10 September**: United by the Ocean (Paul Meilhat) won in 7d 23h 39m; Malizia was **fourth** after a collision damaged its port foil ram. The "posted the result the day after the finish" sentence was invented to explain the date |
| Ep003, Ep004 | Plain Sailing = the 50/50 crew rule of the race just narrated; then crew fatigue in the same race | Not evergreen; a second pass over the Fleet item |
| Ep002–005 | Zero uses of Dan's own experience (737 captain, wing foiler) | The prompt said "at most one", the model read it as zero |
| Ep004 | Leading trio "opened a gap of more than four hundred thirty miles" | Standings, stale by publish time |
| Ep004 | Canadian Boat ≈ 80 s of a 6-minute episode; Fleet ≈ 3 min | The spine got the least airtime |

The Ep005 error is the show's stated "one unforgivable error" — a
confidently wrong race result — and it was caused by the same blindness
as the position line: a label was read, the body was not.

## 2. Deep research — what the show should have said this month

Verified 14 September against the linked sources (all now in the standing
facts / field guide / dashboard data):

- **Canada Ocean Racing.** The 2 Sep post is the campaign's richest
  first-person source to date: "learning the language of the boat"
  system by system; 40 years on Lake Huron so the water held few
  surprises, the boat did; a triceps seizure on the grinder traced to a
  shoulder injury and electrolytes; "I haven't yet sailed Emira IV in the
  open ocean's waves and swell … I need to remain humble"; the named
  support team (Amescua, Bucau, Gautier, Bayat, Zaccaria, Roberts,
  Moloney). The show summarised it in one clause. The team's YouTube
  posted the Welland Canal transit on 31 Aug. The team's public tracker
  is a YB Tracking page (canadaoceanracing.com/follow/ → my.yb.tl/emira4);
  its JSON endpoints answered 500 on 14 Sep (between events), so the
  dashboard embeds the team's own page rather than polling it.
- **Route du Rhum 2026.** Scott Shawyer IS entered — "Canada Ocean Racing
  – Be Water Positive" on the IMOCA class entry page and in the 16 April
  selection of **118** skippers (26 IMOCA, 49 Class40, 11 Ocean Fifty, 6
  Ultim, 13+13 Vintage). The field guide said 117; the show never said
  the campaign was on the list.
- **The Ocean Race Atlantic** (2–10 Sep, New York → Lorient, 3,300 nm):
  Meilhat / United by the Ocean won by 8m 56s over Clapcich's 11th Hour
  Racing; DMG MORI third; Malizia fourth (marine-animal collision, port
  foil ram); Embrace the Challenge fifth (3 m mainsail tear repaired at
  sea in 40 knots); MSIG Europe / Colman sixth. Four boats inside 28
  minutes after eight days — the incident-and-consequence story the fix
  list asks for, and the show missed the finish entirely.
- **Défi Azimut** 15–20 Sep, Lorient — this week. Whether EMIRA IV sails
  it is unconfirmed (flagged confirm-before-use).
- **Vendée Arctique** (June): Beccaria's comeback win, Goodchild +1h15,
  Dorange third. **Jérémie Beyou** announced on 10 Sep he is leaving
  Charal after ten years and wants an Ultim (Ep005 had the Ultim half).
- **EMIRA IV spec** (imoca.org): CAN 80, Verdier design, CDK build,
  launched 24 Aug 2021, 18.28 × 5.85 m, 4.50 m draft, ~9 t.
- **Scott's Notes** — the operator's two URLs are one WordPress *page*
  (`/scott-lab-notes/` 301s to `/scott-notes/`); its `/feed/` is the
  comments feed. The posts are the "Scott's Blog" category, whose feed
  serves all four with full `content:encoded` bodies. That feed is now a
  flagged campaign source.

## 3. What shipped

**Fix 1 — read the article.** `engine/article_text.py` + `fetch_full_text: N`
(show YAML, default 0 = every other show byte-identical). Feed bodies
(`content:encoded`) are stored on every article as `content_text` (no HTTP,
no prompt change unless a show opts in); for the rest the page is fetched
and the main prose extracted (bs4, `<article>`/`<main>` paragraphs,
size-relative chrome pruning — the first cut reduced an Elementor page to
"Skip to content"). Campaign feeds are opened first, then newest-first, 14
articles at ~2,500 chars each. Rendered as `FULL TEXT:` under the headline
in the digest prompt; metric `articles_full_text` (consumer: the review
snapshot — a zero on this show means the layer went dark).

**Fix 2 — Scott's Notes** category feed, flagged for freshness.

**Fix 3/4 — position + content.** The freshness block now carries a
"What it said" excerpt and URL for each channel's newest post. Digest,
podcast and system prompts require the LAST KNOWN position with the DATE
of that fix and ban "unconfirmed" / "no update" / "position unknown";
they require the content of a post, never its timestamp.

**Fix 5/7 — incidents, not leaderboards.** Fleet priority order (finish of
a followed race → breakages/repairs/retirements and what they mean for one
person alone → boats/business/people); one sentence max on a leader;
roll-calls, mileage gaps and top-fives banned.

**Fix 6 — lead with Canada.** The Canadian Boat is the first and longest
segment (brief 450–650 words; script 500–650; Fleet 300–400).

**Fix 8 — no scaffolding on air.** The `**Standing item:**` label is gone
(now "Background (writer-only label — never spoken)", only if the section
would be under 250 words); the podcast prompt bans the words; the boat's
pedigree is rationed to once in four weeks and only with a this-week hook.

**Fix 9 — evergreen Plain Sailing.** Must survive deleting the week's news;
never a re-telling of a race covered in the same episode.

**Fix 10 — Dan.** "At most ONE" → "REQUIRED: EXACTLY ONE (never zero,
ceiling two)". The brief now carries a writer-only **Dan's lens** line
naming the item and the parallel so the script has a place to put it.

**Fix 11 — URLs.** Already clean in every published digest (the resolver
plus `repair_aggregator_urls` did their job); the Sources spec now also
bans index pages (Ep004 cited `imoca.org/en/news`), and a guard sweeps
every published digest for `news.google.com`.

**Fix 12 — footer.** `engine.blog.next_episode_placeholder` derives the
latest-post nav slot from the registry `schedule`: "New episode Monday" on
Offshore North, "tomorrow" only on daily shows. Regenerated blog verified.

**Race-state rule** (the Ep005 error): a finish inside the window
outranks every earlier report of the same race and is a mandatory Fleet
lead; the body wins over a headline; the standing corrections record the
exact error.

**Standing facts + field guide** refreshed (section 2), including the
"unconfirmed ×4" and "start-as-result" corrections.

**Campaign dashboard** — `offshore-north-dashboard.html`
(`generate_offshore_north_dashboard`, template
`templates/offshore_north_dashboard.html.j2`): live countdown to the
Route du Rhum start (13:02 CET, 1 Nov) with chips for the Défi Azimut,
the race village and the 2028 Vendée Globe; last known position with date
and source (baked log + the newest dated fix from the live feed); the
team's YB tracker embedded; latest campaign posts WITH excerpts and the
latest offshore headlines (`api/offshore_north_dashboard.json` from
`scripts/fetch_offshore_north_dashboard.py`, refreshed nightly and by the
show hook after each episode); boat spec + pedigree; the skipper; the
2028 qualification outline and the campaign's ledger; the season calendar;
recent results; the Route du Rhum IMOCA entry list with the Canadian entry
flagged; the Canadian lineage; latest episodes; and a "Follow the sport"
grid of every source and social channel the show reads (campaign,
organisers, EN press, FR press, teams). Curated facts live in
`site/data/offshore_north_dashboard.json` (dated, sourced). Wired into the
show page button, the data hub, the sitemap, `--all`/`--network`/per-show
builds and both committing workflows.

## 4. Not done / operator items

- **A/B-listen the next episode (21 Sep)** — every prompt change here is
  landmine-#17 territory. The first full-text episode is the calibration
  set: check that the Canadian Boat runs long and first, that one Dan
  reference lands, and that Plain Sailing is evergreen.
- **Défi Azimut is this week**; whether EMIRA IV is on the entry list is
  the one fact the next episode most needs and it was not findable on 14
  Sep. If the team's tracker goes live for the delivery, note the date.
- The YB tracker JSON API (`yb.tl/JSON/emira4/…`) answered 500 during the
  review; if the team's page shows the boat under way, the fetch script
  can be extended to read the newest fix from it (CORS is open on the
  domain). Until then the "last known position" is the newest dated
  campaign post that describes a movement — honest, but coarse.
- X handles remain unverified (`@Canada_Ocean` is linked from the team's
  own /follow/ page; IMOCA is probably `@ImocaGS`). Flip
  `x_fetch_enabled` only after checking each.
- `imoca.org` and `theoceanrace.com` still have no feed; web search is the
  only route and Ep005 shows it did not surface the race finish. A small
  scraper of `imoca.org/en/news` (the page lists dated headlines cleanly)
  would be the next fetch-side lever if the full-text layer does not close
  the gap on its own.

## 5. Predictions (scored by the next review)

See the ledger entry: zero "unconfirmed" position lines; the Canadian Boat
≥ 35% of spoken words and first; ≥ 1 Dan reference per episode; zero
standings roll-calls; zero "standing facts/item" on air; `articles_full_text`
≥ 8 per episode; Plain Sailing not about a same-episode race.
