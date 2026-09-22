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
# the combination is the claim. Sep 22 2026: "nothing reaches a feed until
# the guest has approved it" came out of this paragraph because it was not
# what the code does — gate 2 auto-approves after seven days of silence
# (workers/voices/src/index.ts, ``gate2Housekeeping``). The guest's final
# say is the week to approve, cut or refuse plus the standing takedown; the
# copy says exactly that, and a guard reads the Worker to keep it honest.
MIRA_FIRST_CLAIM_BASIS = (
    "What is unusual is not that the host is an AI — it is the terms. Mira "
    "holds a live, unscripted conversation rather than reading a script at a "
    "recording. She discloses on air that the host is a machine. A human "
    "editor reviews every episode before release, and that review has no "
    "timer that expires into publication. And the guest gets their own "
    "transcript before anything is assembled, with a week to approve it, cut "
    "anything from it, or refuse it outright: what they cut is removed from the "
    "audio, not bleeped, and a takedown stays available after publication. "
    "Plenty of shows use AI to write, "
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


# ---------------------------------------------------------------------------
# The creator credit
# ---------------------------------------------------------------------------
#
# 2026-09-21. Patrick Novak built this network and he does real, specific work
# on the interview shows, and no surface said so. The credit lives here for the
# same reason the Mira claim does: it is a factual claim about a named person,
# it has to read the same everywhere, and it has exactly one way of going
# wrong.
#
# THE WAY IT GOES WRONG is scope. "Patrick approves every episode before it
# publishes" is TRUE of the interview shows and FALSE of the network. The ~18
# run_show shows have no human gate at all — ``ai-disclosure.html`` says
# plainly that nobody reads every episode before it ships, and an earlier
# version of that page claimed the opposite for five months before it had to
# be removed. So the approval sentence is bound to ``HUMAN_REVIEW_SHOW_SLUGS``
# and ``creator_credit()`` refuses to hand it to anything else.
#
# The second way it goes wrong is the room — in BOTH directions. An earlier
# version of this credit said he "is not in the room while Mira is talking to
# a guest", and a guard pinned the sentence. He co-hosted five of the first
# seven episodes — every one but Ep4 (Ep7 opens with Mira saying so on air;
# Ep6 labels him ``PATRICK:`` in capitals, which is how a case-sensitive
# count once read it as zero). The arrangement is the one in
# Mira's own prompt: she hosts every interview; he joins as co-host only when
# a guest has asked for him. The credit may say that and nothing stronger —
# never that he hosts, never that he is in every room, never that he is in
# none of them. ``tests/test_age_of_ai_pass_2026_09_21.py`` checks the copy
# against the committed transcripts, so it cannot drift back to "never".

NETWORK_CREATOR_NAME = "Patrick Novak"

#: The shows where a human reviews and approves every episode before it
#: publishes. Both run through the Nerra Voices pipeline
#: (``pipelines/voices/``), whose two gates are the reason the sentence is
#: true: gate 1 is Patrick's editorial review, which has no timer that
#: expires into publication, and gate 2 is the guest approving their own
#: transcript. No run_show show has either gate, and none may be added here
#: without one.
HUMAN_REVIEW_SHOW_SLUGS = ("age_of_ai", "nerra_voices")

#: What he is, network-wide. Safe on any page: it claims nothing about how
#: individual episodes are checked.
CREATOR_NETWORK_ROLE = (
    "Patrick Novak created the Nerra Network and runs it from Vancouver. He "
    "chooses what the shows cover, writes the instructions they are made "
    "from, and listens to what comes out. No episode of anything here carries "
    "an ad or a sponsor."
)

#: What he does on a show that has the two gates. Every clause is a step that
#: exists in ``pipelines/voices/``; none of it is true of the daily shows.
CREATOR_REVIEW_ROLE = (
    "On this show he is also the editor. He reads every application himself "
    "and decides whether an interview happens, and he reviews the finished "
    "episode before it is assembled — a gate with no timer, so nothing has "
    "ever published because a review ran late. Mira conducts every interview; "
    "when a guest has asked for him he joins as co-host, and either way he "
    "never answers for the guest afterwards: the guest reads their own "
    "transcript and decides whether it ships."
)

#: The co-host label the transcripts use for him. ``engine.interviews`` reads
#: the speaker labels back out of each committed transcript and reports a
#: co-host only when that label actually has lines — so a page can say
#: "with Patrick Novak" on Ep7 and say nothing on Ep4, the solo episode.
CREATOR_TRANSCRIPT_LABEL = "Patrick"

#: What "he works on Mira" actually means. Deliberately concrete, because the
#: vague version ("he trains Mira", "she learns from his feedback") describes
#: a training loop that does not exist — nothing here fine-tunes a model.
CREATOR_MIRA_ROLE = (
    "Mira is his design. He writes and tunes the instructions she works from "
    "— how she opens, what she chases, when to stop talking — sets the "
    "editorial rules she is held to, and listens to what she did afterwards "
    "to decide what changes next time. No model is retrained; the work is "
    "the brief she is given and the judgement about what to change in it."
)


def creator_credit(slug: str = "") -> list:
    """The creator credit for *slug*, as paragraphs in reading order.

    The network role is always included. The editorial-review paragraph is
    added ONLY for a show in :data:`HUMAN_REVIEW_SHOW_SLUGS`, and the Mira
    paragraph ONLY for a show Mira hosts — so a caller cannot accidentally
    put "he approves every episode" on a page for a show where no human reads
    anything before it ships.

    Passing no slug returns the network-safe paragraph alone. That is the
    correct answer for a generic page, not a degraded one.
    """
    out = [CREATOR_NETWORK_ROLE]
    if slug in HUMAN_REVIEW_SHOW_SLUGS:
        out.append(CREATOR_REVIEW_ROLE)
    if slug in MIRA_SHOW_SLUGS:
        out.append(CREATOR_MIRA_ROLE)
    return out
