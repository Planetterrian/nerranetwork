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
"""

from __future__ import annotations

# The three shows Mira hosts, in the order they should be introduced:
# the free daily anchor, then the two interview shows.
MIRA_SHOW_SLUGS = ("nerra_daily", "age_of_ai", "nerra_voices")

MIRA_HOST_NAME = "Mira"

# What Mira is, in one sentence, for a reader who has never heard of her.
MIRA_SHORT_DESCRIPTION = (
    "Mira is the Nerra Network's AI host: she anchors the daily combined "
    "edition and conducts the network's interviews herself, on the record, "
    "with real people."
)

# The claim. Stated plainly, as asked — with the basis in the next sentence so
# a reader can check it rather than take it.
MIRA_FIRST_CLAIM = (
    "The Age of AI and Nerra Voices are the first interview shows of their "
    "kind: the host is an AI, and she does the interviewing."
)

# The basis. Every clause here is something the pipeline actually does, and
# the combination is what no other show appears to put together.
MIRA_FIRST_CLAIM_BASIS = (
    "What makes them unusual is the combination, not the AI: Mira places the "
    "call herself, conducts a live unscripted conversation over the phone, "
    "discloses on air that the host is a machine, and nothing publishes until "
    "the human guest has read and approved their own transcript. Plenty of "
    "shows use AI to write, narrate or edit. We have not found another that "
    "hands it the interviewer's chair under those terms."
)

# The invitation. This is what keeps the claim inside the network's own
# honesty rules — a superlative nobody can challenge is a superlative nobody
# should believe.
MIRA_FIRST_CLAIM_FOOTNOTE = (
    "If you know of an earlier one, we would genuinely like to hear about it "
    "— write to hello@nerranetwork.com and this page will say so."
)


def mira_claim_paragraphs() -> list:
    """The claim, its basis and its footnote, in the order they are read."""
    return [
        MIRA_FIRST_CLAIM,
        MIRA_FIRST_CLAIM_BASIS,
        MIRA_FIRST_CLAIM_FOOTNOTE,
    ]
