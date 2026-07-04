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
   whole thing to close the very first episode — stay for it. Then the
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
