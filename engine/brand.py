"""One owner for the claims the network makes about itself.

The pattern is the one ``engine/titles.py`` and ``engine/funnel.py`` set: when
a fact has to read the same on every surface, exactly one module states it and
everything else imports. Three generations of this network's bugs came from the
same sentence being retyped in three places until the copies disagreed.

The Mira claim is here because it is the network's sharpest differentiator and
its most contestable sentence. It ships with its BASIS attached — what is
actually unusual, in checkable terms — and with an invitation to correct it.
That is not hedging: a superlative with no basis is exactly the kind of
sentence the AI-disclosure page exists to rule out, and this network's trust
posture is the asset the claim is meant to trade on.

**2026-09-20 — the claim was narrowed, twice over, and this is why.** The first
version claimed the general shape ("the host is an AI, and she does the
interviewing"). Other people already do that, some since 2024, so the claim was
disprovable in one search — on the page a journalist reads. Its basis was worse:
it rested on "Mira places the call herself … over the phone", and that stopped
being how the show works on 2026-09-09, when every interview became a room that
participants join from ``age-of-ai-studio.html``
(``voximplant/scenarios/age_of_ai_interview.js``) with the outbound PSTN leg
demoted to a fallback. So the claim now rests on the one term no other show
appears to offer, is true of both call modes, and is verifiable in this
repository: **the guest decides whether the conversation ships.** Do not widen
it back to "an AI host interviews people" — that sentence is not ours to claim.
"""

from __future__ import annotations

# The three shows Mira hosts, in the order they should be introduced:
# the free daily anchor, then the two interview shows.
MIRA_SHOW_SLUGS = ("nerra_daily", "age_of_ai", "nerra_voices")

MIRA_HOST_NAME = "Mira"

# What Mira is, in one sentence, for a reader who has never heard of her.
MIRA_SHORT_DESCRIPTION = (
    "Mira is the Nerra Network's AI host: she anchors the daily combined "
    "edition, conducts the network's interviews herself with real people on "
    "the record, and reads the personalised editions subscribers build."
)

# Mira is a network-level host, not one show's presenter. This is the fact that
# makes her unusual even where the interview claim below does not apply.
MIRA_NETWORK_ROLE = (
    "One host across three jobs: a daily edition that carries every English "
    "show the network published that day, two interview shows, and a "
    "personalised feed that greets each subscriber by name."
)

# The claim. Explicit, as asked — and pinned to the one term that is actually
# ours: the guest holds the publish button.
MIRA_FIRST_CLAIM = (
    "The Age of AI and Nerra Voices are the first interview shows of their "
    "kind: an AI asks the questions, and the human guest decides whether the "
    "conversation is published at all."
)

# The basis. Every clause is something this pipeline actually does, every one
# is true whether the guest joins from a browser or answers a phone call, and
# the combination is the claim.
MIRA_FIRST_CLAIM_BASIS = (
    "What is unusual is not that the host is an AI — it is the terms. Mira "
    "holds a live, unscripted conversation rather than reading a script at a "
    "recording. She discloses on air that the host is a machine. A human "
    "editor reviews every episode before release, and that review has no "
    "timer that expires into publication. And nothing reaches a feed until the "
    "guest has read their own transcript and approved it: anything they ask to "
    "have removed is cut from the audio before the episode is assembled, and a "
    "takedown stays available afterwards. Plenty of shows use AI to write, "
    "narrate or edit, and some now let it interview. We have not found another "
    "that hands the guest the final say."
)

# The invitation. This is what keeps the claim inside the network's own
# honesty rules — a superlative nobody can challenge is a superlative nobody
# should believe.
MIRA_FIRST_CLAIM_FOOTNOTE = (
    "If you know of an interview show that was already doing this, we would "
    "genuinely like to hear about it — write to hello@nerranetwork.com and "
    "this page will say so."
)


def mira_claim_paragraphs() -> list:
    """The claim, its basis and its footnote, in the order they are read."""
    return [
        MIRA_FIRST_CLAIM,
        MIRA_FIRST_CLAIM_BASIS,
        MIRA_FIRST_CLAIM_FOOTNOTE,
    ]
