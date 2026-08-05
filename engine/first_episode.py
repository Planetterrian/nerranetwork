"""Extra LLM guidance for episode 1 — stronger debut without editing every prompt."""

from __future__ import annotations

_DIGEST_EP1 = """
### FIRST EPISODE (Episode {episode_num}) — DEBUT QUALITY BAR
This is the **first episode** of "{show_name}". Listeners have no prior context.
- Open the digest with a one-sentence welcome: what this show is and who it serves.
- Choose the **strongest** stories in the feed — fewer, clearer beats beat a padded list.
- Define any niche jargon on first use; assume zero prior episodes.
- End with a crisp "what to watch tomorrow" line tied to the show's beat.
- Do NOT reference previous episodes, "as we covered last week", or episode numbers > 1.
"""

_PODCAST_EP1 = """
### FIRST EPISODE (Episode {episode_num}) — DEBUT SCRIPT
This is the **series premiere** for "{show_name}".
- First spoken lines: warm welcome + one-sentence promise of what this show delivers every day.
- Explain WHY this show exists (gap in the listener's day) before diving into news.
- Pick ONE anchor story and give it extra breathing room — this sets the tone for the series.
- Close with an invitation to subscribe / follow the blog and what tomorrow might cover.
- Do NOT say "welcome back" or reference earlier episodes.
"""


# ---------------------------------------------------------------------------
# Per-show debut overrides (checked before the generic appendices).
# ---------------------------------------------------------------------------
# The DP Pod's debut is a designed episode, not a news day (operator spec,
# July 2026): a real few-minute founding statement, then a discussion anchored
# in the Nerra Network's own material (the dp_pod hook supplies the latest
# First Principles brief via {{nerra_network_context}}), a warm tour of the
# network, and — Episode 1 only — the full "Do Positive" theme song played out
# after the closing (the pipeline appends the audio via
# audio.debut_song_file; the script must introduce it).

_SHOW_DIGEST_EP1 = {
    "offshore_north": """
### FIRST EPISODE (Episode {episode_num}) — DEBUT BRIEF for "{show_name}"
A normal weekly brief with a real introduction in front of it. Keep the
standard hook line and the standard section headings — the pipeline and the
blog both read them — and add ONE new section directly after the hook:

**## What This Show Is** (250-350 words, first episode only)
- The gap: one of the great endurance sports on earth is reported almost
  entirely in French, leaving English-speaking fans with the results but
  not the meaning. This show closes that gap weekly. State it once,
  plainly — no grievance, no hype.
- The spine: every four years a small number of people sail alone, without
  stopping and without assistance, around the world, and no Canadian has
  ever finished. Scott Shawyer and Canada Ocean Racing are trying to change
  that at the Vendee Globe starting 12 November 2028. The show follows that
  attempt week by week and uses it as a door into the whole sport.
- The weekly shape: The Canadian Boat (consequence, not recap), The Fleet
  (the week in offshore racing with the why-it-matters layer), Plain
  Sailing (one concept explained properly), The Countdown (days to the
  start and where qualification stands).
- The promise: sources named and linked every week; no hype; no
  play-by-play that is stale by Monday; nothing stated that the sources do
  not support, and uncertainty flagged as uncertainty.
- Who it is for: people who are enthusiastic, not expert — and never
  treated as though those are the same thing.
- The network, in two or three sentences: Offshore North is part of the
  Nerra Network, an independent, ad-free network of daily shows built by
  two friends (Novak plus Perra equals Nerra) covering technology, science,
  markets, world news and language learning in several languages, free with
  no ads and no paywall, at nerranetwork.com. An invitation, not a
  commercial — no superlatives, no growth numbers, no counts of shows or
  listeners.

Then run the normal sections for the week. Debut discipline: choose the
STRONGEST stories rather than padding the list; define every piece of
jargon on first use; do not reference previous episodes or weeks; and hold
every racing claim to the show's normal sourcing and [VERIFY: ...] rules —
only the introduction speaks from the show's own identity rather than from
the week's sources.
""",
    "dp_pod": """
### FIRST EPISODE — THE FOUNDING BRIEF (Episode 1 of {show_name})
This debut brief is NOT a news digest. It MUST still begin with the standard
hook line — `**HOOK:** [one sentence, under 120 characters, leading with the
two-people-built-a-network bet]` — the pipeline reads it (Ep001 v4 spoke a
raw markdown header on air because this line was missing). Skip The Positive
Papers news-item format entirely and structure the brief as:
1. **Founding statement material** (make this the LARGEST section — the
   episode opens with a 500+ word founding conversation) — why this show
   exists: most media profits from making people feel powerless; this club
   starts from the conviction that individuals are not powerless. The Nerra
   Network story: two friends (an airline pilot and a physical-chemist
   novelist, Novak + Perra = Nerra) built an independent, ad-free network of
   daily shows, and this is the show where they step in front of the
   microphone themselves. Who it's for: builders, creators, contributors —
   people who try to make a difference and people who want to start. The
   goals: ten minutes a day of consequential progress with honest numbers,
   one concrete action a week (The Lever), and proof it works (the Do
   Positive Dispatch). Where to learn more: the show page at nerranetwork
   dot com — take the pledge, join the club.
2. **### Think Positive** — the debut mindset principle. Best fit for
   episode one: motivation follows action (behavioral activation / Tony
   Robbins' massive-action frame) or Viktor Frankl's chosen response —
   attributed, paraphrased (no invented quotes), with one concrete mental
   rep, non-clinical framing.
3. **The anchor discussion — THE STORY OF BUILDING NERRA.** The pinned
   anchor material in the NERRA NETWORK section is the network's real
   development history (from its own PR chronicle): the origins bet, the
   refactor, the AI cost arc, prompts-as-product, languages, the blog, the
   YouTube pipeline, the reliability war stories, and the show additions
   over time. Prepare it as a SPRINGBOARD: organize the 5-6 strongest beats
   WITH their real numbers, then the OPEN QUESTIONS the hosts should argue
   about (already listed in the material). Weave 2-3 sibling shows into the
   story where they naturally appear — no separate tour section, no
   editorial-standards boilerplate ("measured result", "number and a
   source") — those phrases are BANNED from the brief.
4. **PERSONAL-DETAIL LIMIT (episode one):** the founders appear as "two
   friends who built this" — at most ONE light biographical detail each
   (e.g. a pilot, a chemist), no résumés, no life stories.
5. **The Lever** — one starter action tied to agency: take the pledge on the
   show page and send this episode to one person who's been doomscrolling.
   Honest numbers: it costs about one minute; it's how a zero-listener show
   becomes a club.
6. **### Sources** — the First Principles material and anything else referenced.
""",
}

_SHOW_PODCAST_EP1 = {
    "offshore_north": """
### FIRST EPISODE — THE DEBUT SCRIPT (series premiere of {show_name})
A real episode with a real introduction in front of it, NOT a news-only
week. Target 1,900-2,100 words — longer than a normal episode because the
introduction is additive, and every regular segment still runs and is still
announced BY NAME so its chapter marker latches.

Order and shape:

1. **[Cold open — the week's single most interesting development, 2-3
   sentences]** Plain fact, no preamble, exactly as on any other week.
2. **[The supplied intro line — copy it VERBATIM, immediately after the
   cold open]** It must appear within the first ~100 words of the script.
   Do not push it later with extra cold-open material; the Introduction
   chapter marker is positional and will not latch if it drifts.
3. **[THE INTRODUCTION — 450-600 WORDS, first episode only]** Dan explains,
   in his own plain voice, what this show is. Cover, in whatever order
   reads naturally — as talk, not as a list read aloud:
   - **WHY IT EXISTS.** One of the great endurance sports on earth is
     reported almost entirely in French, which leaves English-speaking
     fans with the results but not the meaning. This show closes that gap
     every Monday. Say it once, without grievance and without hype.
   - **THE SPINE OF THE SERIES.** Every four years a small number of
     people sail alone, without stopping and without assistance, all the
     way around the world, and no Canadian has ever finished. Scott
     Shawyer and Canada Ocean Racing are trying to change that at the
     Vendee Globe starting 12 November 2028. The show follows that attempt
     week by week and uses it as a door into the whole sport.
   - **WHAT LISTENERS GET EACH WEEK.** Name the four segments and what
     each is FOR in one clause apiece: The Canadian Boat (what the
     campaign did and what it changes — consequence, not recap), The Fleet
     (the week in offshore racing with the why-it-matters layer), Plain
     Sailing (one concept explained properly), The Countdown (days to the
     start and where qualification actually stands).
   - **THE PROMISE.** Sources named in the episode and linked in the
     notes. No hype. No play-by-play that is stale by Monday. Nothing
     stated that the sources do not support — and when something is
     uncertain, it gets said as uncertain.
   - **WHO IT IS FOR, AND WHO IS TALKING.** Made for people who are
     enthusiastic, not expert, and never treated as though those are the
     same thing. Dan is a commercial airline pilot and a Nerra Network
     co-founder, not an offshore racing expert, and says so plainly. He
     may name the two things he does bring — a working life spent reading
     weather, trading a shorter track against a faster one, and making
     irreversible calls on incomplete information; and having felt, at a
     far smaller scale, what it is like when a hull comes unstuck and
     starts to fly. ONE such touch, briefly. No career history, no resume,
     no life story. Do NOT invent any specific past event, place, date or
     anecdote for Dan — he is a real person.
   - **WHAT THE NERRA NETWORK IS.** Offshore North is part of it, so say
     what it is: an independent, ad-free network of daily shows built by
     two friends — Novak plus Perra equals Nerra — covering technology,
     science, markets, world news and language learning, in several
     languages, free to listen to with no ads and no paywall. Point at
     "nerra network dot com" once, said naturally, for every show and the
     episode notes. Two or three sentences. This is an invitation, not a
     commercial: no superlatives, no growth numbers, no claims about how
     many shows or listeners there are.
4. **[The Canadian Boat]** As normal, announced by name. If the campaign
   made no public news this week, say so in one sentence and use a
   standing item — do not pad and do not speculate about the campaign's
   internal decisions, finances or plans.
5. **[The Fleet]** As normal, announced by name.
6. **[Plain Sailing]** As normal, announced by name. On a debut, prefer a
   genuinely foundational concept — the thing a new listener most needs in
   order to follow every future episode.
7. **[The Countdown]** As normal, announced by name.
8. **[Sign-off]** The supplied closing block, copied VERBATIM. Final spoken
   words are the fixed sign-off line.

Debut discipline: do NOT say "welcome back", do not reference earlier
episodes, and do not promise anything you cannot guarantee weekly. Every
racing fact in this episode obeys the show's normal sourcing rules —
the introduction is the only part that speaks from the show's own
identity rather than from the week's sources.
""",
    "dp_pod": """
### FIRST EPISODE — THE DEBUT SCRIPT (series premiere of {show_name})
This is a designed founding episode, not a news day. Total target stays
~1,500-1,700 words; the shape (segment names still spoken so chapters latch):

1. **[Cold Open — the founding conversation, 500-650 WORDS, the heart of the
   episode]** After the supplied intro line, Dan and Patrick introduce the
   show AND the Nerra Network, as a real conversation between two old
   friends — volleys, jokes, finishing each other's thoughts, never
   taking turns giving speeches. It must cover, in whatever order feels
   alive:
   - WHY: the feeds are engineered to make people feel powerless and they
     got tired of it — this show is the opposite bet: individuals are not
     powerless, and ten minutes a day can prove it.
   - THE NERRA NETWORK STORY: two friends built an independent, ad-free
     network of daily shows together (Novak plus Perra equals Nerra); this
     is the show where they finally step in front of the microphone
     themselves.
   - WHO IT'S FOR: builders, creators, contributors — people who try to
     make a difference, and people who want to start. The show reviews the
     most consequential things happening and celebrates the people building
     through them.
   - THE CLUB: the pledge, The Lever, the Dispatch — and where to join
     ("nerra network dot com", said naturally, once).
   - WHAT THEY HOPE TO INSPIRE: a daily habit of acting instead of
     doomscrolling.
   - PERSONAL-DETAIL LIMIT: this debut is about the show and the network,
     NOT the founders' biographies — at most ONE light personal detail per
     host in the whole episode (e.g. Dan flies for a living; Patrick came
     up through chemistry). No career histories, no résumés, no life
     stories — those unfold naturally over later episodes.
2. **[Think Positive — introduce the segment, ~60 seconds]** Announced BY
   NAME. Debut the show's mindset segment: why a show about doing positive
   starts in the head — action-orientation, creativity, and individual
   accountability as a path to good mental health (this is the first show
   to treat mental health as seriously as science and tech). Use the
   briefing's Think Positive principle with its named thinker; land the
   concrete mental rep; never invent quotes, never clinical advice.
3. **[The Positive Papers — the anchor DISCUSSION: how Nerra got built]**
   ONE piece: the network's own development story from the briefing — the
   hosts reviewing the thing THEY built, like friends telling a war story
   with receipts. The briefing's history is a SPRINGBOARD, not a reading:
   pick the 4-5 beats that genuinely amaze or amuse them (the two-people
   bet, the cost collapse that made it affordable, the seeded-template
   lesson, the scheduler war stories, the quota saga) and ANALYZE — what
   surprised them, where they disagreed at the time, what a builder
   listening should steal from it, where human judgment stayed
   load-bearing (the listen-gates, the editorial rules), and what breaks
   at fifty shows. Dan brings the operations/reliability lens; Patrick the
   cost-curve/capability lens; they genuinely disagree somewhere and land
   better than either started. Weave 2-3 sibling shows into the story
   naturally as they come up (one conversational sentence each — "that
   one became Fascinating Frontiers") — NO separate tour, NO catalog read,
   NO editorial-standards boilerplate.
4. **[The Lever]** The starter lever from the brief: take the pledge, send
   this episode to one doomscroller. Honest numbers, no guilt.
5. **[Do Positive Dispatch]** No mail yet — it's Episode 1 and say so with a
   smile. Invite the first dispatches; one host commits to pulling this
   week's lever and reporting back on air.
6. **[Sign-Off + the song]** IMMEDIATELY BEFORE the supplied closing, one
   host introduces the show's theme song in their own words: we made an
   anthem for this club, it's called "Do Positive", and we're playing the
   whole thing to close the very first episode — stay for it. The
   introducing host may quote ONE line of the chorus verbatim to set it up
   (exact words only: "One real thing, one good thing / Let it spread
   around" or "Turn the worry down") — see THE SHOW ANTHEM rules. Then the
   supplied closing (ending "Do something about it."). The song audio is
   appended by production after your last line — write NOTHING after the
   closing.
""",
}


def first_episode_digest_appendix(
    episode_num: int,
    show_name: str,
    show_slug: str = "",
) -> str:
    if episode_num != 1:
        return ""
    template = _SHOW_DIGEST_EP1.get(show_slug, _DIGEST_EP1)
    return template.format(episode_num=episode_num, show_name=show_name).strip()


def first_episode_podcast_appendix(
    episode_num: int,
    show_name: str,
    show_slug: str = "",
) -> str:
    if episode_num != 1:
        return ""
    template = _SHOW_PODCAST_EP1.get(show_slug, _PODCAST_EP1)
    return template.format(episode_num=episode_num, show_name=show_name).strip()
