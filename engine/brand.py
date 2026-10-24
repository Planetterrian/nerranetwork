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

# ---------------------------------------------------------------------------
# The one listener-facing address
# ---------------------------------------------------------------------------
#
# 2026-10-01. The site disagreed with itself: ``editorial.html.j2`` told a
# reader to send corrections to one mailbox, ``faq.html.j2`` and
# ``contact.html.j2`` to another. A reader who finds a factual error is the
# most valuable visitor a trust page ever gets, and three pages naming two
# addresses is how that report ends up unanswered. This is the ONE address a
# listener or reader is given, everywhere (the RSS owner email in
# ``shows/_defaults.yaml`` is a directory-facing field and stays what it is).
CONTACT_EMAIL = "hello@nerranetwork.com"

# The three shows Mira hosts, in the order they should be introduced:
# the free daily anchor, then the two interview shows.
# --- Sponsorship (Oct 11 2026) -------------------------------------------
#
# The network used to promise "ad-free" on every surface — the homepage, the
# FAQ, About, the press kit, every meta description, llms.txt and three
# spoken lines. The operator retired that promise on 2026-10-11 so the network
# can carry sponsors. What replaces it is a promise the network can keep with
# sponsors on the air: what a sponsor can and cannot do. Every page that
# talks about sponsors renders it from here (the ``sponsor_policy`` Jinja
# global); a template that types its own version fails
# ``tests/test_sponsor_ready_2026_10_11.py``.
#
# Oct 18 2026 (operator): ads are coming to the site and the shows, and
# "ad-free" is reserved for subscribers and paid content. No free surface
# says ad-free; when the paid tier is described as ad-free, that copy lives
# here, next to the sponsor policy, and names the paid product it applies to.

# --- The network's promise (Oct 18 2026) ----------------------------------
#
# Operator-directed: the tagline and the one-paragraph promise lead every
# surface that introduces the network — the homepage masthead, the footer,
# the default meta description and the share cards — ahead of any single
# show. They are written here once; a template or card that types its own
# version drifts (the site had three spellings of the tagline).

#: The tagline, as the operator writes it.
NETWORK_TAGLINE = "Feed your curiosity, not your anxiety."
NETWORK_TAGLINE_RU = "Питайте любопытство, а не тревогу."
#: The French front page's tagline (fr/index.html, Oct 19 2026).
NETWORK_TAGLINE_FR = "Nourrissez votre curiosité, pas votre anxiété."

#: The subjects, broadest first — no single show leads the network's promise.
NETWORK_SUBJECTS = "space, AI, markets, world news, science and more"


def network_promise(show_count: int) -> str:
    """The standfirst: what the network is and why to trust it.

    ``show_count`` is the number of PUBLIC shows (members-only desks are not
    free, so they are not counted in a sentence that says "free shows").
    """
    return (f"News and ideas from {int(show_count)} free shows on {NETWORK_SUBJECTS}. "
            "Every story is sourced, every claim is checked against its source, "
            "and you can read the article or hear the episode it came from.")


#: The flagship shows: the network's two biggest audiences (Tesla Shorts Time
#: and SpaceX Daily carry most downloads and views). The promise leads with the
#: network's breadth; the flagships keep a permanent place beside it — their
#: own band on the front page and the large tiles on the network share card
#: (operator, Oct 18 2026: the first pass had reduced them too far). One list,
#: in display order; every surface that features them reads it.
FLAGSHIP_SHOW_SLUGS = ("spacex", "tesla")


def network_promise_visitor() -> str:
    """The promise as a visitor reads it on the front page: count-free.

    The homepage standfirst, the default meta description and the media kit's
    hero all render this one sentence (operator, Oct 18 and Oct 21 2026: the
    press messaging matches the landing page word for word).
    """
    return (f"Free news and ideas on {NETWORK_SUBJECTS}. "
            "Every story is sourced, every claim is checked against its source, "
            "and you can read the article or hear the episode it came from.")


#: A short form for surfaces with one line to spare (cards, meta).
NETWORK_PROMISE_SHORT = ("Every story sourced. Every claim checked against its source. "
                         "Read the article or hear the episode.")


#: Where sponsor enquiries go. One address for now; split it out when there
#: is a second person to read it.
SPONSOR_EMAIL = CONTACT_EMAIL

#: Where press and publicists write (Oct 21 2026, the media kit). The same
#: inbox for the reason above: one address a person actually reads.
PRESS_EMAIL = CONTACT_EMAIL

#: When the network began, as the operator states it (Oct 21 2026): the
#: Nerra Network NAME was established in February and March 2026, and
#: audience measurement, marketing and the channels only began around June
#: 2026 (the first complete OP3 week is 29 June; the YouTube subscriber
#: snapshots start 22 July). Every growth figure the kits print covers months,
#: not years, and the kits say so. Never write "2024" as a founding year: the
#: earlier automated Tesla show predates the network and its name.
NETWORK_ESTABLISHED_YEAR = 2026
NETWORK_FOUNDING_DATE = "2026-02"            # schema.org foundingDate
NETWORK_NAMED_TEXT = "February and March 2026"
MEASUREMENT_STARTED_TEXT = "June 2026"


def network_history_note() -> str:
    """One sentence for the kits, beside the growth figures."""
    return (f"The Nerra Network name was established in {NETWORK_NAMED_TEXT}, "
            f"and audience measurement, marketing and the channels began in "
            f"{MEASUREMENT_STARTED_TEXT}, so every growth figure here covers "
            "months, not years.")


#: The two co-founders, as their own show states them (Novak + Perra =
#: Nerra; ``shows/network_meta.yaml`` dp_pod.about_host) and as Patrick told
#: it on the record in The Age of AI Ep001. Facts only: nothing here is a
#: claim the press kit cannot source. A photo is sent on request, so none is
#: named.
FOUNDERS = (
    {
        "name": "Patrick Novak",
        "role": "Co-founder and producer",
        "bio": (
            "Patrick Novak is a Vancouver-based entrepreneur, a physical chemist "
            "by training and a published science fiction novelist. The network "
            "began when a daily Tesla podcast he relied on stopped publishing "
            "and he rebuilt it as an automated show; he established the Nerra "
            "Network name in February and March 2026. He "
            "designs the production pipeline, writes the editorial rules the "
            "AI works under, and built Mira, the network's AI host. He "
            "co-hosts The DP Pod."
        ),
        "topics": (
            "Building a news network with AI under rules people write",
            "Designing an AI interviewer that gives guests the final say",
            "Publishing a public record of every claim checked against its source",
            "What automation can and cannot do for a one-person newsroom",
        ),
    },
    {
        "name": "Dan Perra",
        "role": "Co-founder and co-host of The DP Pod",
        "bio": (
            "Dan Perra is a commercial airline pilot and longtime technology "
            "enthusiast. He co-founded the network with Patrick and co-hosts "
            "The DP Pod, their weekly show on good news in science and "
            "technology and one practical action a listener can take."
        ),
        "topics": (),
    },
)

#: Language names the boilerplate prints, keyed by the site's codes
#: (``engine.show_lang.site_languages``).
LANGUAGE_NAMES = {"en": "English", "fr": "French", "ru": "Russian",
                  "es": "Spanish", "zh": "Chinese"}


def _language_list(codes) -> str:
    names = [LANGUAGE_NAMES.get(c, c) for c in codes]
    if not names:
        return "English"
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def network_boilerplate(show_count: int, languages=("en",)) -> dict:
    """The press kit's copy-ready descriptions, short to long.

    ``show_count`` is the PUBLIC count (as :func:`network_promise`);
    ``languages`` the site's language codes. Every sentence states what the
    network does today; a new show or language changes the numbers, never
    the wording. The Mira sentence stays inside the narrow claim
    (:data:`MIRA_FIRST_CLAIM`): the guest decides whether the conversation is
    published, with no superlative.
    """
    n = int(show_count)
    langs = _language_list(languages)
    short = (f"{NETWORK_TAGLINE} Nerra Network makes free news and ideas on "
             f"{NETWORK_SUBJECTS}: {n} free podcasts, made in Vancouver, Canada, "
             "with every claim checked against its source.")
    medium = (
        f"{NETWORK_TAGLINE} Nerra Network makes free news and ideas on "
        f"{NETWORK_SUBJECTS}, published as {n} free shows in {langs} from "
        "Vancouver, Canada. Every story is sourced, every claim is checked "
        "against its source, and you can read the article or hear the episode "
        "it came from. The shows are written and voiced with AI under editorial "
        "rules set by people, and its interview shows are hosted by Mira, an AI "
        "whose guests decide whether their conversation is published at all. "
        f"Established in {NETWORK_ESTABLISHED_YEAR} by Patrick Novak and Dan Perra."
    )
    long = (
        medium + " Its flagship shows follow SpaceX and Tesla every day; Nerra "
        "Daily gathers the morning's shows into one edition by 7 a.m. Eastern, "
        "anchored by Mira. Every episode is free in any podcast app and as a "
        "written article with its sources, most shows publish to YouTube, and "
        "readers can see which claims were verified and which were not on a "
        "public record."
    )
    return {"short": short, "medium": medium, "long": long}

# --- The media kit's growth and marketing copy (Oct 21 2026) ---------------
#
# What the network is building next, stated as work that exists or is
# under way, never as a forecast: the kit's measured momentum (computed from
# the nightly files in generate_html) sits beside these, and a projection
# with no basis is the thing a publicist checks first. ``{apple}``,
# ``{spotify}``, ``{shows}`` and ``{video_words}`` (spelled out, so it never
# reads as a second show count) are filled from the data.

#: (heading, sentence) pairs, in the order the kit prints them.
GROWTH_NEXT = (
    ("Every show in every app",
     "{apple} of {shows} free shows are listed on Apple Podcasts and {spotify} "
     "on Spotify. The newer shows already play in any app by their feeds; "
     "their directory listings are next, starting with Podcast Index."),
    ("Three languages on YouTube",
     "English, Russian and French channels carry the shows as videos and "
     "Shorts. The Russian and French channels add dubbed editions of SpaceX "
     "Daily, Tesla Shorts Time and Fascinating Frontiers, and the Russian "
     "channel also carries the Russian lesson show Привет, Русский!"),
    ("Video in podcast apps",
     "{video_words} shows publish a video feed beside their audio feed, made "
     "for the video players in Apple Podcasts and other apps."),
    ("More conversations",
     "The Age of AI and Nerra Voices add a guest each time a conversation is "
     "recorded and the guest has had their week with the transcript."),
    ("Members",
     "Nerra Personal is a private daily feed of the shows a member picks, in "
     "their order, with Mira addressing them by name."),
    ("Sponsorship",
     "Sponsors are coming to the site and the free shows, labelled every "
     "time and kept apart from the reporting. No sponsor has a say over what "
     "a show covers."),
)


def marketing_posts(site_url: str = "https://nerranetwork.com") -> list:
    """Copy-ready posts for anyone who wants to share the network.

    Built from the tagline and the promise so a post never says more than
    the site does. Each carries a plain link (a person's own post is not a
    published surface of ours, so no campaign tag is added for them).
    """
    root = site_url.rstrip("/")
    return [
        {"key": "post-short", "label": "Short post",
         "where": "X, Threads, Bluesky",
         "text": (f"{NETWORK_TAGLINE} Nerra Network makes free news and ideas "
                  f"on {NETWORK_SUBJECTS}, and every claim is checked against "
                  f"its source. {root}")},
        {"key": "post-long", "label": "Longer post",
         "where": "LinkedIn, Facebook, a newsletter",
         "text": (f"{NETWORK_TAGLINE} Nerra Network makes free news and ideas "
                  f"on {NETWORK_SUBJECTS}. Every story is sourced, every claim "
                  "is checked against its source, and you can read the article "
                  "or hear the episode it came from. Start with Nerra Daily, "
                  "the morning's shows in one episode, or find a show of your "
                  f"own: {root}/start-here.html")},
        {"key": "post-guest", "label": "For a guest sharing their interview",
         "where": "Any platform",
         "text": ("I sat down with Mira, the AI host of The Age of AI on Nerra "
                  "Network, for a live conversation. I had a week with my own "
                  "transcript to approve it, cut from it or refuse it before "
                  "anything was published. Listen here: [your episode link]")},
        {"key": "post-notes", "label": "One line for show notes or a bio",
         "where": "Show notes, a talk bio, a byline",
         "text": f"Nerra Network: {NETWORK_TAGLINE} {root}"},
    ]


#: How the brand files and art may be used. Plain rules a reader can follow.
BRAND_USAGE = {
    "yes": (
        "Use the logos, cover art and share images in coverage, reviews, "
        "guest announcements, show notes and talks about Nerra Network.",
        "Quote an episode or use a short clip, credited to the show, with a "
        "link to its episode page.",
        "Link to nerranetwork.com or to a show's own page.",
    ),
    "no": (
        "Recolour, stretch or redraw the logos, or combine them with another mark.",
        "Suggest that Nerra Network endorses, sponsors or partners with you "
        "unless it does.",
        "Use the art to sell a product, or present Mira as a person.",
    ),
}


#: One sentence, for the places that have room for one (FAQ answers, cards,
#: the press kit).
SPONSOR_POLICY_SUMMARY = (
    "Every episode is free. Sponsors may support the shows; a sponsored "
    "message is always labelled as one, and no sponsor chooses, reviews or "
    "changes what a show covers."
)

#: The rules in full, for the sponsor page and the editorial standards.
SPONSOR_POLICY_RULES = (
    ("Labelled, every time",
     "A sponsored message says it is sponsored, in the audio and in the show "
     "notes. It is never written to sound like the news around it."),
    ("Kept apart from the reporting",
     "A sponsor read sits in its own slot, never inside a story, and a "
     "sponsor's own news is reported the same way as anyone else's or not at "
     "all."),
    ("No say over coverage",
     "Sponsors do not choose, review, preview or change what a show covers. "
     "A sponsor that is in the news is covered like anyone else."),
    ("The same sourcing rules",
     "Claims in a sponsored message must be the sponsor's own and must not "
     "be presented as the show's reporting or its fact-checked claims."),
    ("Every episode stays free",
     "Sponsorship pays for the network; it never puts an episode behind a "
     "paywall."),
    ("Never on an interview",
     "The Age of AI and Nerra Voices carry no sponsor. A guest gives an hour "
     "of their own words, and those words are never sold."),
)


# ---------------------------------------------------------------------------
# The sponsorship kit (Oct 21 2026, operator-directed)
# ---------------------------------------------------------------------------
#
# ``sponsor.html`` is the advertising and sponsorship kit: the audience it
# reaches (the media kit's own numbers), the packages and their rates, the
# terms for the first partners, how a booking runs, and the rules above. The
# rates are the OPERATOR's: edit them here and the page, the producer's
# drafted replies and the guest mail all follow. They are flat monthly fees,
# not a CPM: the network is small and growing, a flat fee prices the
# placement and the category, and a partner who books early keeps the rate
# while the audience grows. The page prints each package's MEASURED reach
# beside its price (a dash when unmeasured) and never a forecast.

#: The public pages a guest, publicist or sponsor is pointed to. The guest
#: mail and the producer's facts read these, never a typed URL.
SITE_URL = "https://nerranetwork.com"
MEDIA_KIT_URL = f"{SITE_URL}/press.html"
SPONSOR_KIT_URL = f"{SITE_URL}/sponsor.html"

SPONSOR_CURRENCY = "USD"

#: How many partners get founding terms. The page says the terms close when
#: these are taken; it never counts down or invents scarcity.
SPONSOR_FOUNDING_PLACES = 3

#: The packages, in the order the page shows them. ``shows`` are the slugs
#: whose measured audience is the package's reach; ``price`` is per month in
#: :data:`SPONSOR_CURRENCY`; ``from_price`` marks a starting rate.
SPONSOR_PACKAGES = (
    {"id": "founding", "name": "Founding partner", "price": 5000,
     "term": "three-month minimum",
     "summary": ("The network's first partners: the two flagship shows, the "
                 "daily edition and your category to yourself."),
     "includes": (
         "Your category kept exclusive across every free show for the term",
         "Nerra Daily opens with your credit, every edition",
         "One labelled message on every episode of SpaceX Daily and Tesla Shorts Time",
         "Named as a founding partner on this page and in the media kit",
         "The founding rate held for twelve months from your first booking",
     ),
     "shows": ("spacex", "tesla", "nerra_daily"), "featured": True},
    {"id": "spacex", "name": "SpaceX Daily", "price": 2500,
     "term": "one-month minimum",
     "summary": ("The network's largest show: the engineering and business "
                 "of SpaceX, every morning."),
     "includes": (
         "The show's only sponsor for the month",
         "One labelled message on every episode",
         "A credit in the show notes and on every episode page",
     ),
     "shows": ("spacex",)},
    {"id": "tesla", "name": "Tesla Shorts Time", "price": 1500,
     "term": "one-month minimum",
     "summary": "Tesla's news, filings and products, every morning.",
     "includes": (
         "The show's only sponsor for the month",
         "One labelled message on every episode",
         "A credit in the show notes and on every episode page",
     ),
     "shows": ("tesla",)},
    {"id": "nerra_daily", "name": "Nerra Daily, presented by you", "price": 1500,
     "term": "one-month minimum",
     "summary": ("The day's shows in one edition, out by 7am Eastern, with "
                 "Mira introducing each one."),
     "includes": (
         "A presenting credit at the open of every edition",
         "One labelled message inside each edition",
         "A credit in the show notes and on the edition's page",
     ),
     "shows": ("nerra_daily",)},
    {"id": "ai", "name": "The AI shows", "price": 1500,
     "term": "one-month minimum",
     "summary": ("Every show on models, agents and the chips and data "
                 "centres behind them."),
     "includes": (
         "One labelled message on every episode of each show",
         "A credit in the show notes and on every episode page",
         "Your category kept exclusive across these shows",
     ),
     "shows": ("models_agents", "models_agents_beginners", "ai_chips")},
    {"id": "space_science", "name": "Space, science and ideas", "price": 1200,
     "term": "one-month minimum",
     "summary": ("The frontier shows: space and astronomy, the life "
                 "sciences, first principles and unintended consequences."),
     "includes": (
         "One labelled message on every episode of each show",
         "A credit in the show notes and on every episode page",
         "Your category kept exclusive across these shows",
     ),
     "shows": ("fascinating_frontiers", "planetterrian", "first_principles",
               "unintended_consequences")},
    {"id": "markets_world", "name": "Markets and the world", "price": 1000,
     "term": "one-month minimum",
     "summary": ("Investing, the largest tech companies, prediction markets "
                 "and the day's world news."),
     "includes": (
         "One labelled message on every episode of each show",
         "A credit in the show notes and on every episode page",
         "Your category kept exclusive across these shows",
     ),
     "shows": ("modern_investing", "mag7", "prediction_markets", "omni_view",
               "omni_view_world")},
    {"id": "single", "name": "Any other free show", "price": 500,
     "from_price": True, "term": "one-month minimum",
     "summary": ("One show to yourself, from the local and weekly shows to "
                 "the Russian-language ones. Ask for the show you want."),
     "includes": (
         "The show's only sponsor for the month",
         "One labelled message on every episode",
         "A credit in the show notes and on every episode page",
     ),
     "shows": ()},
)

#: The kit's opening line, under the tagline and the promise.
SPONSOR_KIT_LEDE = (
    "Put your message beside reporting people trust: labelled, in its own "
    "slot, on free shows listeners choose to feed their curiosity."
)

#: Now booking: what is true before the first message runs.
SPONSOR_KIT_STATUS = (
    "Now booking. The first sponsored messages run in the first month a "
    "partner books, and every one follows the rules on this page."
)

#: Why a sponsor would want this audience, in the network's own terms.
SPONSOR_REASONS = (
    ("An audience that chose curiosity",
     "People come to Nerra to learn what changed in space, AI, markets, "
     "science and the world, on purpose, from shows that publish every "
     "morning."),
    ("A record your message sits beside",
     "Every story is sourced and every claim is checked against its source, "
     "in public. Your message is labelled and kept apart, so it borrows the "
     "trust without spending it."),
    ("In early, at a rate that holds",
     "The audience is growing week on week. A founding partner keeps the "
     "founding rate for a year while it does."),
)

#: What every booking carries, whatever the package.
SPONSOR_TERMS = (
    ("Written with you",
     "We write each message from your facts, in the show's own voice, and "
     "you approve the facts before it runs. You approve your message; you "
     "never see or approve the show around it."),
    ("Voiced by the show's host",
     "The hosts are AI voices, and every episode says so. Your message is "
     "read in the same voice, labelled as sponsored, in its own slot."),
    ("Measured the same way",
     "At the end of each month you get the downloads and views of the "
     "episodes that carried your message, from the same sources as the "
     "numbers on this page."),
    ("An episode for an episode",
     "If a booked episode does not publish, your message runs on the next "
     "one. You never pay for an episode that did not go out."),
)

#: How a booking runs, in order.
SPONSOR_STEPS = (
    ("Write to us", "Tell us the shows or package, the month and your category."),
    ("We confirm", "We confirm the dates are open and the category is yours."),
    ("We write the message", "A draft from your facts, for you to approve."),
    ("It runs", "Labelled, on every episode of the term."),
    ("You get the numbers", "Downloads and views of every episode that carried it."),
)


def sponsor_packages() -> list:
    """The packages for templates and mail, prices formatted once."""
    out = []
    for pkg in SPONSOR_PACKAGES:
        row = dict(pkg)
        row["includes"] = list(pkg["includes"])
        row["shows"] = list(pkg["shows"])
        price = f"${pkg['price']:,}"
        row["price_text"] = (f"From {price}" if pkg.get("from_price") else price)
        row["unit"] = "a month"
        out.append(row)
    return out


def sponsor_kit() -> dict:
    """Everything the kit page says that is not a measured number."""
    return {
        "packages": sponsor_packages(),
        "terms": [{"title": t, "body": b} for t, b in SPONSOR_TERMS],
        "steps": [{"title": t, "body": b} for t, b in SPONSOR_STEPS],
        "founding_places": SPONSOR_FOUNDING_PLACES,
        "lede": SPONSOR_KIT_LEDE,
        "status": SPONSOR_KIT_STATUS,
        "reasons": [{"title": t, "body": b} for t, b in SPONSOR_REASONS],
        "currency": SPONSOR_CURRENCY,
        "email": SPONSOR_EMAIL,
        "url": SPONSOR_KIT_URL,
        "media_kit_url": MEDIA_KIT_URL,
    }


#: One line for guest mail and the producer: where a guest, a publicist or a
#: would-be sponsor finds the network's materials. Plain text; the HTML mail
#: wraps the two URLs itself.
def kits_sentence() -> str:
    return (f"The network's media kit, with the audience numbers, logos and "
            f"the boilerplate, is at {MEDIA_KIT_URL}, and the sponsorship kit "
            f"is at {SPONSOR_KIT_URL}.")


#: The two kits in guest mail (Oct 24 2026, operator: put the press kit and
#: the sponsorship kit in the emails, pleasantly, so people can look at them
#: and pass them on, to suggest a sponsor or to market an episode). Two
#: moments: "intro" for someone meeting the network (an invitation), "share"
#: for a guest who has recorded (the thank-you and the publish-day note).
#: Every message says the interview shows never carry a sponsor. The Worker's
#: invitation carries a copy of "intro" (KITS_INTRO_HTML in
#: workers/voices/src/index.ts); tests keep the two in step.
KITS_COPY = {
    "intro": ("If you'd like to know more about the network first, the {press} has a "
              "short description, our logos and our audience numbers. And if anyone "
              "you know would like to reach the people who listen, the {sponsor} is "
              "the thing to pass along; the interview shows themselves never carry a "
              "sponsor."),
    "share": ("If you'd like to tell people about our conversation, the {press} has "
              "what you need: a description of the network ready to paste, our logos "
              "and our audience numbers. And if you know a company that would like to "
              "reach the people who listen, the {sponsor} is worth passing along. The "
              "interview shows themselves never carry a sponsor; sponsors appear on the "
              "network's other shows."),
}


def kits_html(purpose: str = "share", color: str = "") -> str:
    """The kits as one paragraph of HTML mail, the two names linked."""
    import html as _h
    style = f' style="color:{_h.escape(color)}"' if color else ""
    return "<p>" + _h.escape(KITS_COPY[purpose], quote=False).format(
        press=f'<a href="{MEDIA_KIT_URL}"{style}>press kit</a>',
        sponsor=f'<a href="{SPONSOR_KIT_URL}"{style}>sponsorship kit</a>') + "</p>"


def kits_text(purpose: str = "intro") -> str:
    """The kits as plain text, each name followed by its address."""
    return KITS_COPY[purpose].format(press=f"press kit ({MEDIA_KIT_URL})",
                                     sponsor=f"sponsorship kit ({SPONSOR_KIT_URL})")


def kits_signature_html() -> str:
    """The line under Mira's name in every HTML email: the two kits, quietly."""
    return (f'<a href="{MEDIA_KIT_URL}" style="color:#4a5568">Press kit</a> · '
            f'<a href="{SPONSOR_KIT_URL}" style="color:#4a5568">Sponsorship kit</a>')


MIRA_SHOW_SLUGS = ("nerra_daily", "age_of_ai", "nerra_voices")

#: The news shows Mira reads (Sep 2026 launch cohort). Deliberately NOT in
#: MIRA_SHOW_SLUGS: that tuple is the claim-bearing trio (the first-of-its-kind
#: basis rests on the interview shows), and the strand "mira" in the chrome
#: stays those three. These are listed on /mira.html under their own heading
#: — before this the page never said she reads the news at all.
MIRA_NEWS_SHOW_SLUGS = (
    "omni_view_world", "omni_view_north_america", "omni_view_europe",
    "omni_view_asia_pacific", "omni_view_africa_mideast", "omni_view_latam",
    "vancouver", "collingwood",
)

MIRA_NEWS_ROLE = (
    "Mira also reads the news: five regional desks and a ranked world edition "
    "every day, a Vancouver daily and a Collingwood weekly — each one written "
    "from named publishers, every source listed on the episode page, and the "
    "AI host disclosed in the first minute."
)

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
    f"genuinely like to hear about it — write to {CONTACT_EMAIL} and "
    "this page will say so."
)


# Oct 7 2026: "nothing publishes until the guest approves" had survived on
# seven surfaces after the Sep 22 pass corrected the basis above (this meta
# description, the claims-ledger rows, the FAQ, the editorial page, both
# apply forms). Gate 2 is a week to approve, cut or refuse, then auto-approve.
#: The mira.html meta description (was a literal in generate_html.py
#: carrying the overclaim). Kept short: it is what a search result shows.
MIRA_PAGE_DESCRIPTION = (
    "Mira is the Nerra Network's AI host. She anchors the daily combined "
    "edition and interviews real people live — and each guest gets a week "
    "to approve, cut from or refuse their own transcript."
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


def interview_provenance(guest_name: str = "", cohost_name: str = "") -> list:
    """The one-line provenance an interview post prints under its player.

    Short phrases, each a fact the pipeline can vouch for on EVERY episode:
    who hosted (an AI, disclosed), who co-hosted when someone did (read from
    the transcript, never assumed), who reviewed it (gate 1), and what the
    guest was given (gate 2 as built — sent to approve, cut or refuse; it
    does not say "approved by", because seven days of silence also
    publishes). The credit paragraphs carry the same facts at length.
    """
    parts = [f"Hosted by {MIRA_HOST_NAME}, an AI"]
    if cohost_name:
        parts.append(f"{cohost_name} co-hosted")
    parts.append(f"Reviewed before release by {NETWORK_CREATOR_NAME}")
    if guest_name:
        parts.append(
            f"Transcript sent to {guest_name} to approve, cut or refuse "
            "before publication"
        )
    return parts


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


# ---------------------------------------------------------------------------
# How an interview runs — the steps a guest is walked through
# ---------------------------------------------------------------------------
#
# Moved here from generate_html.py on 2026-09-22. Two of these steps are
# claims about a human deciding something (gate 1, the review with no timer)
# and about what the guest can do (gate 2, a week to approve, cut or refuse);
# they render on /mira.html AND on the interview show pages, so they need
# one owner the way the claim and the credit do. Sources: docs/age_of_ai_plan.md
# and voximplant/scenarios/age_of_ai_interview.js. Step 7 says what gate 2
# actually does — the seven-day auto-approve is stated, not hidden.
MIRA_INTERVIEW_STEPS = [
    ("You apply", "A short form: who you are and what you would talk about. "
                  "No media training, no pitch deck, no AI angle required."),
    ("A human reads it", "Patrick triages every application himself. This is "
                         "the step that decides whether an interview happens."),
    ("You pick a time", "A booking link, your calendar, your timezone."),
    ("You get a prep brief", "The day before, an emailed brief: the themes "
                             "Mira means to explore and the ground she will "
                             "cover, so nothing in the conversation is a "
                             "surprise."),
    ("You talk to Mira", "Open the studio link, pick a microphone, join — or "
                         "take a call on your phone if you would rather. "
                         "Mira hears you and answers in real time. It is a "
                         "conversation, not a questionnaire, and it runs "
                         "under an hour."),
    ("A human edits it", "Patrick reviews the episode before anything is "
                         "assembled. This gate has no timer: nothing "
                         "publishes because a review was slow."),
    ("You approve your transcript", "You read what you said, and you have a "
                                    "week to approve it, cut anything from "
                                    "it, or refuse it. What you cut is "
                                    "removed from the audio before the "
                                    "episode is built — not bleeped, cut. "
                                    "After seven days without a reply the "
                                    "episode goes ahead as sent, and you can "
                                    "ask for a takedown at any time."),
    ("It publishes", "Mira records the narration around your words, and the "
                     "episode goes to the feeds, the site and the archive "
                     "with the AI host disclosed on air."),
]

#: The steps a show page shows beside the Hosted-by-Mira band — the ones a
#: prospective guest asks about first (apply, the human read, the
#: conversation, the human edit, the transcript). The full list is on
#: /mira.html. Indexes into :data:`MIRA_INTERVIEW_STEPS`.
MIRA_INTERVIEW_STEPS_COMPACT = (0, 1, 4, 5, 6)


# ---------------------------------------------------------------------------
# Episode provenance — the one line under a news post's AI badge
# ---------------------------------------------------------------------------
#
# 2026-10-01. The AI badge said "Made with AI — transparently" and then said
# nothing. What a reader deciding whether to trust an AI-made news show wants
# is the specific record of THIS episode: how many sources it was written
# from, how many claims were checked against those sources, and whether
# anything was removed because it could not be. All three numbers exist per
# episode (the Sources section and the committed ``*_claims.json`` sidecar),
# so the line is rendered from them — never typed, never rounded up. A zero
# clause is omitted rather than written as "0 claims checked", EXCEPT the
# sources clause, which is the one a reader must always be able to see.

#: What voices every run_show episode. The TTS request has no model
#: parameter (CLAUDE.md, LLM usage review), so there is no version to name.
VOICE_PROVENANCE = "voiced with Grok TTS"

#: The AI-host shows (``publishing.host_kind: ai`` — Mira) say so in the same
#: line; the disclosure the episode speaks on air is the same fact.
AI_HOST_PROVENANCE = "hosted by an AI"


def _plural(n: int, singular: str, plural: str = "") -> str:
    return f"{n:,} {singular if n == 1 else (plural or singular + 's')}"


def episode_provenance_parts(
    sources_count: int,
    claims_verified: int = 0,
    stripped: int = 0,
    host_kind: str = "human",
    flagged: int = 0,
) -> list:
    """The provenance phrases for one episode, in reading order.

    ``sources_count`` is the number of distinct source cards the post
    renders; ``claims_verified`` and ``stripped`` come from the claims
    sidecar's ``gate`` block (``claims_verified``, ``len(stripped_sentences)``).
    Zero claims and zero stripped sentences are omitted — the sentence must
    not pad itself — but the sources clause is always present, and an
    episode with no listed source says so in words rather than vanishing.
    """
    n_src = max(int(sources_count or 0), 0)
    n_claims = max(int(claims_verified or 0), 0)
    n_strip = max(int(stripped or 0), 0)
    parts = []
    if n_src:
        parts.append(f"Written from {_plural(n_src, 'source')}")
    else:
        parts.append("No sources listed for this episode")
    if n_claims:
        parts.append(f"{_plural(n_claims, 'claim')} checked against "
                     f"{'its source' if n_claims == 1 else 'their sources'}")
    if n_strip:
        parts.append(f"{_plural(n_strip, 'unverified sentence')} removed "
                     "before publication")
    # Oct 1 2026, flag mode: what the gate could not confirm is published
    # and marked, and the line says how many — the panel below carries each
    # one's status. Zero is omitted like the other counts.
    n_flag = max(int(flagged or 0), 0)
    if n_flag:
        parts.append(f"{_plural(n_flag, 'claim')} published and marked "
                     "not yet verified")
    if (host_kind or "human").strip().lower() == "ai":
        parts.append(f"{AI_HOST_PROVENANCE}, {VOICE_PROVENANCE}")
    else:
        parts.append(VOICE_PROVENANCE)
    return parts


def episode_provenance(
    sources_count: int,
    claims_verified: int = 0,
    stripped: int = 0,
    host_kind: str = "human",
    flagged: int = 0,
) -> str:
    """:func:`episode_provenance_parts` joined into one line, e.g.
    ``Written from 14 sources · 6 claims checked against their sources ·
    1 unverified sentence removed before publication · voiced with Grok TTS``.
    """
    return " · ".join(
        episode_provenance_parts(sources_count, claims_verified, stripped,
                                 host_kind, flagged)
    )


# ---------------------------------------------------------------------------
# The claims-and-corrections process — the one owner of the policy copy
# ---------------------------------------------------------------------------
#
# 2026-10-01, operator-directed. The source-integrity gate's default moved
# from "strip" (remove every sentence the check cannot vouch for) to "flag"
# (publish the sentence, mark it, re-check it nightly). The reason is the
# calendar: a language model's training data ends months before today, so
# a story newer than the model is exactly the one it cannot have learned —
# it is verified against its source, never against memory — and when that
# source is unreachable from our servers (a regulator that 403s a cloud
# runner, a journal behind a wall) the old gate read "cannot fetch" as
# "fabricated" and deleted a true, timely sentence. A listener is better
# served by the sentence with its status beside it than by a clean ledger
# with the news missing.
#
# These steps render on /claims.html, on every claims/<slug>.html, and are
# the text the AI-disclosure and editorial pages summarise. They are owned
# here for the reason every other paragraph in this module is: a policy
# retyped in three templates is a policy that disagrees with itself inside
# a month. ``tests/test_claims_pages_2026_10_01.py`` reads
# ``shows/_defaults.yaml`` and fails if the copy says one thing and the
# configured ``on_failure`` says another.

#: How many nights an unverified claim is re-checked before it is left as
#: it stands (the nightly re-verification job's window).
CLAIMS_RECHECK_DAYS = 7

CLAIMS_PROCESS_STEPS = (
    ("Every episode starts with a ledger",
     "When a show's digest is written, the model also writes a claims ledger: "
     "each factual sentence it asserts, the URL it took it from, and the "
     "passage in that source that supports it. The ledger is extracted before "
     "any published surface sees the text."),
    ("Each claim is checked by a machine, not trusted",
     "Before the episode is saved, every entry is checked mechanically: first "
     "against the copy of the source the pipeline fetched that morning, then "
     "against the live page. The supporting quote has to actually appear in "
     "the source. A sentence written in the shape of a citation with no ledger "
     "entry behind it is caught by the same check — that shape is the "
     "signature of a fabricated reference."),
    ("A claim the check cannot confirm is published and marked, not removed",
     "Sometimes the source cannot be reached from our servers, sometimes the "
     "page has moved, and sometimes the model paraphrased where it should have "
     "quoted. None of those means the sentence is false. A story newer than the "
     "model's training data is verified against its source, never against "
     "memory, and a true, timely story is worth more to a listener than a "
     "clean ledger. So the sentence ships, and its status is shown beside it "
     "— on the episode page, and on this ledger — in plain words that say "
     "what the check could and could not do."),
    ("Unverified claims are re-checked every night for a week",
     f"For {CLAIMS_RECHECK_DAYS} nights after publication a job re-runs the "
     "check on every marked claim that names a source. A claim that passes later is "
     "upgraded on the ledger with the date it was confirmed and the status it "
     "carried first. A claim that never passes stays marked; nothing is "
     "quietly deleted and nothing is quietly promoted."),
    ("Corrections are filed in the open",
     "When a published sentence turns out to be wrong, a dated correction is "
     "filed in the show's corrections record. From there it reaches the top of "
     "the episode's page, that episode's show notes, the next episode's show "
     "notes, and this ledger. Audio is never edited silently: either the "
     "episode is re-synthesized and replaced in full, or the error is noted "
     "and the audio left as aired."),
    ("Anyone can report an error",
     f"Write to {CONTACT_EMAIL} with the episode and the sentence. Every "
     "episode page carries a Report an error link that fills in both. A person "
     "reads every report and checks it against the sources."),
    ("What we do not claim",
     "No human reads every episode before it ships. The checks above are "
     "automated and the record of them is public; that record, not a promise "
     "of review, is what we ask you to judge the shows on."),
)

#: Every status a ledger entry can carry → (listener-facing label, one-line
#: meaning). The keys are the closed vocabulary ``engine.claims`` writes into
#: the committed sidecar (``policy_version: 2``); a sidecar older than that
#: carries no status and every entry in it is read as ``verified``, because
#: only verified entries were committed before. ``correction`` is not a
#: claim status — it is the badge the corrections record renders with, kept
#: here so every surface colours it the same way.
CLAIMS_STATUS_LABELS = {
    "verified": (
        "Verified",
        "The source was fetched and the supporting quote was found in it.",
    ),
    # Its own label (Oct 7 2026): two statuses both reading "Verified" made
    # the legend show the same badge twice with different meanings.
    "verified_from_fetched": (
        "Verified (fetched copy)",
        "The supporting quote was found in the copy of the source fetched for "
        "the episode.",
    ),
    "verified_later": (
        "Verified later",
        "The claim did not pass when the episode was published; a nightly "
        "re-check later found the quote in the source.",
    ),
    "unverified_unreachable": (
        "Published, not yet verified",
        "The source could not be fetched from our servers (a block, a rate "
        "limit or a server error), so the claim could not be checked. It is "
        "re-checked nightly for a week.",
    ),
    "unverified_not_found": (
        "Published, source not found",
        "The source URL answered 'not found'. The sentence stands as "
        "published; treat it with care.",
    ),
    "unverified_quote_mismatch": (
        "Published, quote not matched",
        "The source was reached but the supporting passage was not found in "
        "it, usually because the quote was paraphrased rather than copied.",
    ),
    "unverified_uncovered": (
        "Published, no source entry",
        "The sentence reads like a citation but no ledger entry names a source "
        "for it, so there is nothing to re-check it against.",
    ),
    "malformed": (
        "Published, ledger entry unusable",
        "The ledger entry for this claim was incomplete, so it could not be "
        "checked and is not re-checked.",
    ),
    "correction": (
        "Correction",
        "A published sentence was wrong and a dated correction has been filed.",
    ),
}

#: The statuses that count as verified on a ledger total.
CLAIMS_VERIFIED_STATUSES = ("verified", "verified_from_fetched", "verified_later")


def claims_status_label(status: str) -> str:
    """The listener-facing label for *status* (unknown → the raw status)."""
    entry = CLAIMS_STATUS_LABELS.get(str(status or "").strip().lower())
    return entry[0] if entry else str(status or "").replace("_", " ")


def claims_status_meaning(status: str) -> str:
    entry = CLAIMS_STATUS_LABELS.get(str(status or "").strip().lower())
    return entry[1] if entry else ""


def claims_process_steps() -> list:
    """The steps as ``[(title, text), ...]`` in reading order."""
    return list(CLAIMS_PROCESS_STEPS)


def sponsor_policy() -> dict:
    """The sponsorship rules for templates (``sponsor_policy`` Jinja global)."""
    return {
        "summary": SPONSOR_POLICY_SUMMARY,
        "rules": [{"title": t, "body": b} for t, b in SPONSOR_POLICY_RULES],
        "email": SPONSOR_EMAIL,
    }
