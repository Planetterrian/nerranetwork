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
1. **Founding statement material** — why this show exists: most media profits
   from making people feel powerless; this club starts from the conviction
   that individuals are not powerless. The goals: ten minutes a day of
   genuinely good news with honest numbers, one concrete action a week (The
   Lever), and proof it works (the Do Positive Dispatch). Where to learn
   more: the show page at nerranetwork dot com — take the pledge, join the
   club. What we hope to inspire: a habit of acting instead of doomscrolling.
2. **The anchor discussion** — take the First Principles Daily material in
   the NERRA NETWORK section and prepare it as the episode's one discussion
   piece: the core idea, its most surprising numbers, and why first-principles
   thinking is itself a "do positive" tool (it turns "that's just how it is"
   into "here's what it should cost").
3. **The network tour** — 3-4 sentences introducing the Nerra Network: an
   independent, ad-free network of daily shows built by the same two people
   hosting this one; pick 3-4 shows from the catalog to name with their
   one-phrase pitch.
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
This is a designed founding episode, not a news day. The shape (~10 minutes
of dialogue; segment names still spoken so chapters latch):
1. **[Cold Open — the founding statement, a real 2-3 minutes]** After the
   supplied intro line, Dan and Patrick talk about WHY they built this show,
   as themselves: the feeds are engineered to make people feel powerless and
   they got tired of it; what the show delivers every day; what the club is
   (the pledge, The Lever, the Dispatch) and where to join — say
   "nerra network dot com" naturally, once; what they hope to inspire. This
   is the most personal segment the show will ever run — write it warm,
   funny, and genuinely theirs.
2. **[The Positive Papers — the anchor discussion]** ONE piece only: the
   First Principles Daily material from the briefing, framed proudly as
   "from our own network." Unpack it the way two friends unpack an idea that
   changed how they see prices and possibility — Dan brings the operator's
   angle, Patrick the mechanism, and they genuinely disagree about how far
   the idea stretches before landing together.
3. **[The network tour — woven in, ~40 seconds]** Coming out of the
   discussion: the Nerra Network is the club's library — name 3-4 sibling
   shows naturally with what each is for. A friend's recommendation, never
   an ad read.
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
