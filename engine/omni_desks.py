"""The Omni View regional desks — one definition, every surface (Sep 2026).

Plan: docs/new_shows_plan_2026_09_22.md §4.7-4.8. Five daily regional briefs
read by Mira (Europe, Asia Pacific, Africa & the Middle East, Central & South
America, North America) and Omni View Top World News, which ranks the day's
ten stories across all of them.

Every registry that needs a per-desk entry (intros, first-episode briefs,
validation, content tracking, narrative memory, cover specs, the desk hook)
reads THIS module, so a desk is added or changed in one place. The
analytical Omni View (Patrick; Steel Man, Understanding the Issue) is a
different show and is not described here.

Pure data plus small pure helpers: no network, no imports from the
registries that consume it (they import this module, never the reverse).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple


@dataclass(frozen=True)
class Desk:
    slug: str
    name: str                 # "Omni View Europe"
    region: str               # "Europe" — spoken and written
    page: str                 # "omni-view-europe" (slug hyphen rule)
    prefix: str               # episode filename prefix
    accent: str               # registry accent colour (plan §5a)
    glyph_arg: int            # cover globe: which longitude band is lit
    framing: str              # the identity line's one-phrase promise
    # Sub-regions and the words that place a story in one. The hook reads
    # the last ten digests and names the sub-regions none of them reached
    # (plan §4.7: balance is data-side — no roll-call, no quota).
    sub_regions: Tuple[Tuple[str, Tuple[str, ...]], ...]
    # Seeded narrative arcs: (key, display name, status, open questions).
    arcs: Tuple[Tuple[str, str, str, Tuple[str, ...]], ...]
    theme_keywords: Tuple[str, ...] = field(default=())


DESKS: Tuple[Desk, ...] = (
    Desk(
        slug="omni_view_europe", name="Omni View Europe", region="Europe",
        page="omni-view-europe", prefix="Omni_View_Europe", accent="#4F46E5",
        glyph_arg=0, framing="The day in Europe, one region deep.",
        sub_regions=(
            ("the UK and Ireland", ("britain", "british", "uk ", "england", "scotland", "wales",
                                    "northern ireland", "ireland", "irish", "london", "starmer")),
            ("the EU institutions", ("european commission", "european parliament", "brussels",
                                     "eu leaders", "von der leyen", "european council", "ecb")),
            ("France, Germany and the Low Countries", ("france", "french", "paris", "germany",
                                                       "german", "berlin", "netherlands", "dutch",
                                                       "belgium", "luxembourg", "austria", "switzerland")),
            ("southern Europe", ("italy", "italian", "rome", "spain", "spanish", "madrid",
                                 "portugal", "greece", "greek", "malta", "cyprus")),
            ("the Nordic and Baltic states", ("sweden", "norway", "denmark", "finland", "iceland",
                                              "estonia", "latvia", "lithuania", "nordic", "baltic")),
            ("central and eastern Europe", ("poland", "polish", "czech", "slovakia", "hungary",
                                            "romania", "bulgaria", "moldova", "slovenia")),
            ("the Balkans", ("serbia", "croatia", "bosnia", "kosovo", "albania", "montenegro",
                             "north macedonia", "balkan")),
            ("Ukraine, Russia and Belarus", ("ukraine", "ukrainian", "kyiv", "russia", "russian",
                                             "moscow", "kremlin", "belarus")),
            ("Turkey and the Caucasus", ("turkey", "turkish", "ankara", "istanbul", "georgia's",
                                         "tbilisi", "armenia", "azerbaijan")),
        ),
        arcs=(
            ("ukraine_war", "The war in Ukraine", "Fighting, diplomacy and aid in Russia's war on Ukraine.",
             ("Front-line changes", "Talks and aid decisions")),
            ("eu_institutions", "EU institutions", "Commission, Parliament and Council decisions that bind member states.",
             ("Legislation and rulings", "Budget and enlargement")),
            ("uk_politics", "UK politics", "Government, Parliament and the parties in the United Kingdom.",
             ("Legislation and votes", "Party leadership")),
            ("migration", "Migration in Europe", "Arrivals, asylum rules and border policy across Europe.",
             ("Policy changes", "Arrival figures")),
        ),
        theme_keywords=("ukraine", "russia", "eu", "election", "migration", "nato", "energy",
                        "budget", "court", "strike", "protest", "coalition"),
    ),
    Desk(
        slug="omni_view_asia_pacific", name="Omni View Asia Pacific", region="Asia Pacific",
        page="omni-view-asia-pacific", prefix="Omni_View_Asia_Pacific", accent="#0F766E",
        glyph_arg=1, framing="The day across Asia and the Pacific, one region deep.",
        sub_regions=(
            ("China and Hong Kong", ("china", "chinese", "beijing", "xi jinping", "hong kong", "shanghai")),
            ("Taiwan", ("taiwan", "taipei")),
            ("Japan", ("japan", "japanese", "tokyo")),
            ("the Korean peninsula", ("korea", "korean", "seoul", "pyongyang")),
            ("South Asia", ("india", "indian", "delhi", "modi", "pakistan", "bangladesh",
                            "sri lanka", "nepal", "bhutan", "maldives", "afghanistan")),
            ("Southeast Asia", ("indonesia", "philippines", "vietnam", "thailand", "malaysia",
                                "singapore", "myanmar", "cambodia", "laos", "asean")),
            ("Australia and New Zealand", ("australia", "australian", "canberra", "new zealand",
                                           "wellington", "albanese")),
            ("the Pacific islands", ("fiji", "papua new guinea", "samoa", "tonga", "solomon islands",
                                     "vanuatu", "pacific islands", "kiribati")),
            ("Central Asia", ("kazakhstan", "uzbekistan", "kyrgyz", "tajikistan", "turkmenistan", "mongolia")),
        ),
        arcs=(
            ("taiwan_strait", "Taiwan Strait", "Military activity, diplomacy and trade across the Taiwan Strait.",
             ("Military activity", "Diplomatic moves")),
            ("china_economy", "China's economy", "Growth, property, trade and policy in China's economy.",
             ("Stimulus and data releases", "Trade measures")),
            ("india_politics", "Indian politics", "Government, courts and state elections in India.",
             ("Legislation and rulings", "State elections")),
            ("korea_peninsula", "Korean peninsula", "Relations between the two Koreas and their neighbours.",
             ("Missile tests and talks", "Seoul's domestic politics")),
        ),
        theme_keywords=("china", "taiwan", "japan", "india", "korea", "election", "trade",
                        "typhoon", "earthquake", "court", "protest", "economy"),
    ),
    Desk(
        slug="omni_view_africa_mideast", name="Omni View Africa & Middle East",
        region="Africa and the Middle East", page="omni-view-africa-mideast",
        prefix="Omni_View_Africa_Mideast", accent="#B45309", glyph_arg=2,
        framing="The day across Africa and the Middle East, one region deep.",
        sub_regions=(
            ("the Gulf", ("saudi", "riyadh", "uae", "emirates", "dubai", "abu dhabi", "qatar",
                          "doha", "kuwait", "bahrain", "oman", "yemen", "houthi")),
            ("Israel, Palestine and the Levant", ("israel", "israeli", "gaza", "west bank", "palestin",
                                                  "lebanon", "hezbollah", "syria", "jordan")),
            ("Iran and Iraq", ("iran", "iranian", "tehran", "iraq", "baghdad", "kurdistan")),
            ("North Africa", ("egypt", "cairo", "libya", "tunisia", "algeria", "morocco")),
            ("West Africa and the Sahel", ("nigeria", "nigerian", "ghana", "senegal", "mali",
                                           "burkina", "niger", "ivory coast", "sahel", "ecowas")),
            ("East Africa and the Horn", ("kenya", "ethiopia", "somalia", "sudan", "south sudan",
                                          "uganda", "tanzania", "rwanda", "eritrea")),
            ("Central Africa", ("congo", "drc", "kinshasa", "cameroon", "chad",
                                "central african republic", "gabon")),
            ("Southern Africa", ("south africa", "johannesburg", "pretoria", "ramaphosa", "zimbabwe",
                                 "zambia", "mozambique", "angola", "namibia", "botswana", "malawi")),
        ),
        arcs=(
            ("gaza_and_israel", "Gaza and Israel", "The war in Gaza, hostages, ceasefire talks and aid.",
             ("Ceasefire and talks", "Humanitarian access")),
            ("iran", "Iran", "Iran's nuclear programme, sanctions, domestic politics and its neighbours.",
             ("Nuclear talks", "Domestic unrest")),
            ("sudan_and_sahel", "Sudan and the Sahel", "The war in Sudan and armed conflict across the Sahel.",
             ("Front lines and talks", "Displacement and aid")),
            ("gulf_economies", "Gulf economies", "Oil, investment and diversification in the Gulf states.",
             ("Oil output decisions", "Major investments")),
        ),
        theme_keywords=("gaza", "israel", "iran", "sudan", "oil", "election", "coup",
                        "ceasefire", "aid", "drought", "protest", "debt"),
    ),
    Desk(
        slug="omni_view_latam", name="Omni View Central & South America",
        region="Central and South America", page="omni-view-latam",
        prefix="Omni_View_LatAm", accent="#15803D", glyph_arg=3,
        framing="The day across Central and South America and the Caribbean, one region deep.",
        sub_regions=(
            ("Mexico", ("mexico", "mexican", "sheinbaum", "mexico city")),
            ("Central America", ("guatemala", "honduras", "el salvador", "bukele", "nicaragua",
                                 "costa rica", "panama", "belize")),
            ("the Caribbean", ("cuba", "cuban", "haiti", "dominican republic", "jamaica", "puerto rico",
                               "trinidad", "barbados", "bahamas", "caribbean")),
            ("Colombia and Venezuela", ("colombia", "colombian", "bogota", "venezuela", "venezuelan",
                                        "caracas", "maduro")),
            ("the Andes", ("peru", "lima", "ecuador", "quito", "bolivia", "la paz")),
            ("Brazil", ("brazil", "brazilian", "lula", "brasilia", "sao paulo", "rio de janeiro", "amazon")),
            ("the Southern Cone", ("argentina", "buenos aires", "milei", "chile", "santiago",
                                   "uruguay", "paraguay")),
        ),
        arcs=(
            ("venezuela", "Venezuela", "Politics, the economy and migration from Venezuela.",
             ("Government and opposition", "Sanctions and oil")),
            ("argentina_economy", "Argentina's economy", "Inflation, reforms and debt under Argentina's government.",
             ("Inflation readings", "IMF and debt")),
            ("mexico_security", "Security in Mexico", "Cartel violence, policing and security policy in Mexico.",
             ("Security operations", "Justice reforms")),
            ("amazon_and_climate", "The Amazon and climate", "Deforestation, fires and climate policy in the Amazon basin.",
             ("Deforestation figures", "Climate commitments")),
        ),
        theme_keywords=("brazil", "argentina", "mexico", "venezuela", "election", "inflation",
                        "amazon", "migration", "cartel", "protest", "court", "hurricane"),
    ),
    Desk(
        slug="omni_view_north_america", name="Omni View North America", region="North America",
        page="omni-view-north-america", prefix="Omni_View_North_America", accent="#D97706",
        glyph_arg=4, framing="The day in the United States and Canada, one region deep.",
        sub_regions=(
            ("the White House and federal agencies", ("white house", "president", "executive order",
                                                      "cabinet", "pentagon", "federal agency")),
            ("Congress", ("congress", "senate", "house of representatives", "speaker", "senator")),
            ("the US courts", ("supreme court", "federal judge", "appeals court", "ruling", "justice department")),
            ("the US states and cities", ("governor", "state legislature", "california", "texas",
                                          "new york", "florida", "mayor")),
            ("Canada's federal government", ("ottawa", "parliament hill", "prime minister carney",
                                             "house of commons", "canadian government", "carney")),
            ("Canada's provinces", ("ontario", "quebec", "alberta", "british columbia", "manitoba",
                                    "saskatchewan", "nova scotia", "new brunswick", "premier")),
            ("US–Mexico and North American trade", ("usmca", "cusma", "tariff", "border", "mexico",
                                                    "trade deal")),
        ),
        arcs=(
            ("us_executive_and_courts", "US executive and courts", "Executive actions and the court cases that test them.",
             ("Executive orders", "Court rulings")),
            ("canada_federal", "Canada's federal government", "Parliament, the cabinet and federal policy in Canada.",
             ("Legislation and budgets", "Federal–provincial disputes")),
            ("us_mexico_border", "The US–Mexico border", "Border policy, crossings and enforcement between the US and Mexico.",
             ("Policy changes", "Crossing figures")),
            ("trade", "North American trade", "Tariffs and the USMCA/CUSMA agreement between the three countries.",
             ("Tariff decisions", "Review talks")),
        ),
        theme_keywords=("congress", "supreme court", "tariff", "election", "budget", "parliament",
                        "border", "immigration", "wildfire", "strike", "court", "province"),
    ),
)

#: Omni View Top World News — ranks the day's ten across the desks.
WORLD_SLUG = "omni_view_world"
WORLD_NAME = "Omni View Top World News"
WORLD_PAGE = "omni-view-world"

DESK_SLUGS: Tuple[str, ...] = tuple(d.slug for d in DESKS)
ALL_OMNI_MIRA_SLUGS: Tuple[str, ...] = DESK_SLUGS + (WORLD_SLUG,)

#: Omni View's nine anti-tabloid title filters (shows/omni_view.yaml),
#: shared by every desk (plan §4.7 thresholds), plus the desk additions:
#: live blogs and picture galleries are not stories, and obituaries are the
#: Phase 2 lesson. Never bare "deal", "attack" or "royal".
ANTI_TABLOID_PATTERNS: Tuple[str, ...] = (
    r"red carpet",
    r"\bLove Island\b",
    r"\bStrictly Come Dancing\b",
    r"reality TV star",
    r"\broyal\b.*\b(fashion|dress|style|outfit)\b",
    r"wardrobe malfunction",
    r"\bpaparazzi\b",
    r"\bnet worth\b",
    r"steps out (?:in|with)",
    # desk additions
    r"\b(live updates?|as it happened|live blog)\b",
    r"\b(in pictures|photos of the (day|week)|week in pictures)\b",
    r"\b(quiz|crossword|wordle)\b",
    r"\b(obituar(y|ies)|in memoriam)\b",
)


def desk(slug: str) -> Desk:
    for d in DESKS:
        if d.slug == slug:
            return d
    raise KeyError(slug)


def sub_regions_in(text: str, d: Desk) -> List[str]:
    """Sub-regions a text mentions, in the desk's order (word-start match,
    case-insensitive; a term with a trailing space matches only as a word)."""
    low = " " + (text or "").lower() + " "
    hits = []
    for name, terms in d.sub_regions:
        for term in terms:
            if re.search(r"(?<![a-z])" + re.escape(term), low):
                hits.append(name)
                break
    return hits


def under_covered(recent_digests: Sequence[str], d: Desk) -> List[str]:
    """Sub-regions no recent digest reached, in the desk's order."""
    seen = set()
    for text in recent_digests:
        seen.update(sub_regions_in(text, d))
    return [name for name, _ in d.sub_regions if name not in seen]


def balance_note(recent_digests: Sequence[str], d: Desk) -> str:
    """The digest instruction block the desk hook supplies as hook_context.

    Names under-covered sub-regions as a PREFERENCE among qualifying
    stories, never a quota: a thin day never invents a story to fill a
    sub-region (the DP Pod lever-rotation pattern, data-side)."""
    if not recent_digests:
        return ""
    missing = under_covered(recent_digests, d)
    if not missing:
        return ""
    return (
        "### SUB-REGION BALANCE (instruction — do not include in output)\n"
        f"None of the last {len(recent_digests)} episodes carried a story from: "
        + "; ".join(missing)
        + ". When today's articles include a qualifying story from one of "
        "these, prefer it for Across the Region over a third story from a "
        "place already covered. Never invent or stretch a story to fill a "
        "sub-region, and never say on air that one was missing."
    )


_ITEM_HEAD_RE = re.compile(r"^\*\*(?P<title>[^*\n]{8,}?):\*\*\s*(?P<rest>.*)$")
_SOURCE_URL_RE = re.compile(r"Source:\s*(?:\[[^\]]*\]\()?(?P<url>https?://[^\s)\]]+)")
#: Sections of a desk digest that carry ranked news items.
DESK_ITEM_SECTIONS = ("Lead", "Across the Region", "The Region and the World")


def desk_items(digest_md: str) -> List[Dict[str, str]]:
    """The news items of a committed desk digest: headline, outlet, the
    desk's own summary and the ORIGINAL publisher URL.

    Only the Lead, Across the Region and The Region and the World sections
    are read (Both Sides and Progress Watch are the desk's own framing).
    An item without a publisher URL is dropped: Top World verifies against
    the publisher, never against a sibling digest.
    """
    items: List[Dict[str, str]] = []
    section = ""
    block: List[str] = []

    def flush():
        if not block or section not in DESK_ITEM_SECTIONS:
            return
        text = " ".join(block)
        m = _ITEM_HEAD_RE.match(block[0])
        u = _SOURCE_URL_RE.search(text)
        if not m or not u:
            return
        rest = m.group("rest").strip()
        outlet, _, body = rest.partition(". ")
        body_all = (body + " " + " ".join(block[1:])).strip()
        body_all = _SOURCE_URL_RE.sub("", body_all)
        body_all = re.sub(r"\s*Source:\s*$", "", body_all).strip(" >")
        items.append({
            "section": section,
            "title": m.group("title").strip(),
            "outlet": outlet.strip().rstrip("."),
            "summary": re.sub(r"\s+", " ", body_all)[:420],
            "url": u.group("url").rstrip(".,"),
        })

    for raw in (digest_md or "").splitlines():
        line = raw.strip()
        if line.startswith("### "):
            flush()
            block = []
            section = line[4:].split(":")[0].strip()
            continue
        if line.startswith("**") and _ITEM_HEAD_RE.match(line):
            flush()
            block = [line]
            continue
        if block and line:
            block.append(line.lstrip("> ").strip())
    flush()
    return items
