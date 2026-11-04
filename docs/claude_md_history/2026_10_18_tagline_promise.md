# The tagline and the promise lead (Oct 18 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### The tagline and the promise lead (Oct 18 2026)

Operator-directed: "Feed your curiosity, not your anxiety." and the promise
("News and ideas from N free shows on space, AI, markets, world news, science
and more. Every story is sourced, every claim is checked against its source,
and you can read the article or hear the episode it came from.") lead the
homepage, every share card and the default meta description, instead of
SpaceX and Tesla. Guards `tests/test_brand_messaging_2026_10_18.py`. Rules
that bind: **`engine/brand.py` owns both sentences** (`NETWORK_TAGLINE`,
`NETWORK_TAGLINE_RU`, `network_promise(n)`, `NETWORK_PROMISE_SHORT`; Jinja
globals `network_tagline` / `network_promise`); a template or card that types
them fails CI. **N is the FREE shows** (`generate_html._public_shows` —
public access and a feed), never `len(NETWORK_SHOWS)` (the card had said 31
beside the homepage's 26). **The front-page lead rotates by subject**
(`engine.landing_test.LEAD_ROTATION`: world news, AI, science, markets,
space, history — one a day by the edition date; the audience ranking picks
within the subject) and the top stories show one per beat before repeating
one (Tesla and SpaceX are one beat). The markets strip is alphabetical. Every
card's footer signs with the tagline (Russian on Russian cards); the network
card's art is the breadth of the network, never two of one beat. The Russian
«без рекламы» is in the sponsor guard now (two RU landers still promised it).
**Same day, operator follow-up: the flagships had been reduced too far.**
`engine.brand.FLAGSHIP_SHOW_SLUGS` (`spacex`, `tesla`) is the one list: the
front page gives them a **Flagship shows band every day** directly under the
lead (`landing_test.assemble(flagships=)` — a flagship runs there and in the
Latest list, never also as the lead, a top story or a section story; the lead
rotation picks from the rest), each card with its own market line
(`newsroom.SHOW_TICKERS`), the next launch on SpaceX, and its dashboard and
story tracker; the markets strip leads with TSLA again; the network share card
draws the two flagships as large tiles over a row of six breadth shows; the
start-here / about / join cards lead with them; the homepage meta names SpaceX
and Tesla first. The tagline and the promise wording are unchanged. The
masthead carries three actions (today's Nerra Daily, Find your show, Listen in
any app).
