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
This debut brief is NOT a news digest. Skip The Positive Papers news-item
format entirely and structure the brief as:
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
2. **The anchor discussion** — take the First Principles Daily material in
   the NERRA NETWORK section and prepare it as a SPRINGBOARD, not a summary
   to recite: 2-3 sentences on the core idea and its single most surprising
   number, then the OPEN QUESTIONS the hosts should argue about — how far
   the pattern stretches, what a builder listening today would do with it,
   where it breaks. The hosts' own analysis is the episode; don't pre-write
   their conclusions.
3. **The network tour material** — at most THREE sibling shows from the
   catalog, one-phrase pitch each. No editorial-standards boilerplate
   ("measured result", "number and a source") — those phrases are BANNED
   from the brief.
4. **The Lever** — one starter action tied to agency: take the pledge on the
   show page and send this episode to one person who's been doomscrolling.
   Honest numbers: it costs about one minute; it's how a zero-listener show
   becomes a club.
5. **### Sources** — the First Principles material and anything else referenced.
""",
}

_SHOW_PODCAST_EP1 = {
    "dp_pod": """
### FIRST EPISODE — THE DEBUT SCRIPT (series premiere of {show_name})
This is a designed founding episode, not a news day. Total target stays
~1,400-1,600 words; the shape (segment names still spoken so chapters latch):

1. **[Cold Open — the founding conversation, 500-650 WORDS, the heart of the
   episode]** After the supplied intro line, Dan and Patrick introduce the
   show AND the Nerra Network, as a real conversation between two old
   friends — volleys, jokes, finishing each other's thoughts, never
   taking turns giving speeches. It must cover, in whatever order feels
   alive:
   - WHY: the feeds are engineered to make people feel powerless and they
     got tired of it — this show is the opposite bet: individuals are not
     powerless, and ten minutes a day can prove it.
   - THE NERRA NETWORK STORY: two friends — an airline pilot and a
     physical-chemist novelist — built an independent, ad-free network of
     daily shows together (Novak plus Perra equals Nerra); this is the show
     where they finally step in front of the microphone themselves.
   - WHO IT'S FOR: builders, creators, contributors — people who try to
     make a difference, and people who want to start. The show reviews the
     most consequential things happening and celebrates the people building
     through them.
   - THE CLUB: the pledge, The Lever, the Dispatch — and where to join
     ("nerra network dot com", said naturally, once).
   - WHAT THEY HOPE TO INSPIRE: a daily habit of acting instead of
     doomscrolling.
2. **[The Positive Papers — the anchor DISCUSSION, not a recap]** ONE piece:
   the First Principles Daily material from the briefing — but the source
   material is a SPRINGBOARD, not the content. Maximum three sentences
   total restating what the source says; everything else is Dan and
   Patrick's OWN analysis from their unique lenses: Dan's operations and
   aviation parallels, what he'd bet on and how it fails; Patrick's
   mechanism reasoning, chemistry parallels, sci-fi extrapolation of where
   this goes in twenty years. What does this idea mean for a builder
   listening right now? Where do they genuinely disagree about how far it
   stretches? Land somewhere better than either started.
3. **[The network tour — 30 seconds MAXIMUM, strict]** Name at most THREE
   sibling shows, EXACTLY ONE conversational sentence each, every sentence
   shaped differently ("if you build with AI, Models and Agents is your
   morning"; "Fascinating Frontiers is our space-nerd fix"). HARD BANS: no
   repeated sentence shapes, no editorial-standards boilerplate ("measured
   result", "number and a source", "evidentiary bar"), no corporate voice.
   It's a friend saying "you'd like this one", not a catalog read.
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
