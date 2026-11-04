"""One place that decides how long a title may be, and where to cut it.

Every surface the network publishes to enforces its own limit, and each
one truncates differently and silently:

* **YouTube** hard-caps titles at 100 characters. When a podcast RSS item
  is longer, YouTube ingests it anyway and *rewrites* the title, cutting
  mid-word: ``"Ep 133: Virtual reality experiments show how artificial
  light at night changes how coral reef fis..."``. It emails the channel
  owner afterwards saying "no action is required from you". Between June
  and July 2026 that happened on every show in the network, repeatedly.
* **Google Search** renders roughly 60 characters of a ``<title>``.
* **Apple Podcasts** and most players clamp episode titles in the UI.

The failure mode is always the same: something downstream chops a
sentence in the middle of a word and we find out from an email, or not
at all. Fixing it per-surface is how it got this way — ``engine.blog``
sliced ``hook[:100]``, ``engine.video_metadata._truncate`` sliced
``text[:max_len - 3]``, and ``run_show`` built ``f"Ep {n}: {hook}"`` with
no cap at all. Three different bugs, one shape.

So the rule lives here, once. Surfaces import a limit and a function;
they do not implement clipping themselves. A new surface adds its limit
to this module, which is also the place to look when a platform changes
its rules.
"""

from __future__ import annotations

import re

__all__ = [
    "YOUTUBE_TITLE_MAX",
    "PODCAST_EPISODE_TITLE_MAX",
    "WEB_TITLE_LEAD_MAX",
    "WEB_TITLE_SEPARATOR",
    "NEWSLETTER_SUBJECT_MAX",
    "EMAIL_ALSO_LINE_MAX",
    "X_ITEM_TITLE_MAX",
    "ELLIPSIS",
    "clip_words",
    "fit_first_clause",
    "episode_title",
    "fits",
    "web_page_title",
]

# --- Limits -----------------------------------------------------------

#: YouTube rejects/rewrites video titles beyond this. Hard platform cap.
YOUTUBE_TITLE_MAX = 100

#: Podcast RSS ``<item><title>``. Same 100 as YouTube ON PURPOSE: YouTube
#: ingests the podcast feed directly, so the feed is a YouTube surface
#: whether or not we think of it that way. This is the limit that was
#: missing and that YouTube was silently enforcing for us.
PODCAST_EPISODE_TITLE_MAX = 100

#: Lead portion of an HTML ``<title>`` before the show tail.
#: Google renders ~60 characters of a title. Nov 3 2026: every episode
#: page shipped ``<hook>… — Ep653 | Tesla Shorts Time`` (median 88
#: characters, 97.8% over 60), so a search result never showed the show.
#: The tail is now ``" · <Show>"`` with no episode number (the number
#: stays in the page's h1 pill and breadcrumb), and the lead budget is 58
#: so the show name BEGINS inside the displayed window on most results.
#: Built by :func:`web_page_title`; nothing else assembles a page title.
WEB_TITLE_LEAD_MAX = 58

#: What sits between the lead and the show name in a page ``<title>``.
WEB_TITLE_SEPARATOR = " · "

#: Email clients truncate subject lines around here on mobile.
NEWSLETTER_SUBJECT_MAX = 78

#: One "Also on Nerra today" line in the Nerra Daily email (Nov 3 2026):
#: a short headline a reader scans, not the whole spoken hook (63-150
#: characters, median 104, on the Nov 2 send — 48% of a two-show copy's
#: words). The full hook is one click away on the episode page. Clipped
#: through ``clip_words``; a clip that reads as a fragment
#: (``is_fragment_title``) gives way to the digest's own headline.
EMAIL_ALSO_LINE_MAX = 72

#: Anthology-book chapter titles (EPUB table of contents + audiobook
#: chapter markers). Not a platform cap — a readability one: store TOC
#: panes and audiobook-app chapter lists wrap ugly past ~9 words. The
#: full episode hook always survives as the chapter epigraph, so the
#: clip loses nothing.
BOOK_CHAPTER_TITLE_MAX = 72

#: A digest headline used as a podcast chapter title on a show whose chapters
#: are otherwise its fixed section set (``chapters.known_sections_only``;
#: SpaceX, Oct 12 2026). A FIT gate, never a clip: a headline longer than
#: this gets no chapter, because the Aug 27 2026 truncated headline chapters
#: ("SpaceX is hiring for natural gas trading to support energy…") are why
#: that show had turned headline chapters off.
HEADLINE_CHAPTER_TITLE_MAX = 80

# On-screen chapter title card on long-form video (Sep 2026,
# ``engine.video._long_form_chapter_cards_stage``). A card is a FIT
# gate, not a clip: a title longer than this is not shown at all,
# because a cut sentence on screen reads as a broken caption (Tesla
# Ep592 rendered "Several projects pair storage with solar to").
CHAPTER_CARD_MAX = 48

#: Offshore North glossary page (Sep 19 2026): a Plain Sailing archive entry
#: is titled from the segment's FIRST SENTENCE (the digest has no segment
#: title), clipped word-safe to this many characters for the card heading.
PLAIN_SAILING_TITLE_MAX = 90

# Long-form fact-card label (Sep 2026, engine/fact_cards.py): the short
# line under the on-screen figure. Fit gate + dangling-tail rule, never a
# slice.
FACT_CARD_LABEL_MAX = 36

# The spoken open (Sep 22 2026): the digest's **HOOK:** line is read
# aloud word for word as the episode's first sentence. Above this the
# opener is two sentences pretending to be one (opens measured 14-32
# words, 6 of 15 over the prompts' own 120-character ask, and nothing
# in code checked). It is a GATE in run_show's structural regeneration,
# never a truncation: a long hook is regenerated, not sliced.
SPOKEN_HOOK_MAX_CHARS = 150

# Oct 9 2026 — an X post from a bypass publisher (Nerra Daily, the
# interview shows) is the episode title plus one link. X counts any link
# as 23 characters against its 280, so the text portion is capped here
# and clipped with clip_words(); the link is never clipped.
X_POST_MAX = 280
X_TEASER_TEXT_MAX = 200
# Oct 17 2026 — Modern Investing's X teaser carries TWO links (episode
# post + performance page), so its hook budget is 20 characters smaller.
# run_show._build_teaser had sliced hooks itself ([:199] / [:179]),
# cutting mid-word; it now clips through clip_words() with these.
X_TEASER_TWO_LINK_TEXT_MAX = 180

#: The homepage's one-line "Latest" ticker chip (built Oct 17 2026 for the
#: landing test, the homepage since Oct 18). Every other headline on that page
#: is shown whole; the ticker is a single scrolling line, so it clips
#: word-safe here.
LANDING_TICKER_MAX = 90

#: An X post's heading in a digest item (Nov 3 2026). ``engine.fetcher``
#: builds every post into an article dict whose ``title`` becomes the bold
#: ``**Title: Outlet**`` heading of a digest item, and it had sliced the
#: post's text at 100 characters (``desc[:100]``, two sites) — a title
#: slice outside this module — while a post that CAME with a title kept
#: it whole, so Models & Agents Ep222 made an entire 60-word post the item
#: heading. The Oct 12 2026 heading rule lets a bold ``Title: Outlet`` line
#: run to 110 characters; the heading is clipped here, word-safe, and the
#: post's full text stays in ``description`` for the item body.
X_ITEM_TITLE_MAX = 110

#: Share cards (Oct 18 2026, ``engine/share_cards.py``): the hook printed on
#: an episode's 1200x630 link preview. Four lines of the card's floor size
#: hold ~160 characters; every spoken hook is gated at 150, so a real hook
#: is shown whole and this only catches a stray long headline. When a hook
#: still overflows the card in pixels, the renderer shortens it through
#: ``clip_words`` with a smaller limit — never a slice of its own.
SHARE_CARD_HOOK_MAX = 160

ELLIPSIS = "…"

# Trailing characters that read as debris once the tail is gone.
_TRAILING = " \t\n.,;:!?-–—‐"

#: Characters we are willing to break a title at, best-first.
_BREAK_CHARS = (" ", "-", "–", "—", "/")


# --- Core -------------------------------------------------------------

def clip_words(text: str, limit: int, *, ellipsis: str = ELLIPSIS) -> str:
    """Clip *text* to at most *limit* characters, never mid-word.

    The returned string — ellipsis included — is guaranteed to be
    ``<= limit``. That guarantee is the point: callers pass a platform
    cap straight in and the result is always safe to publish.

    Cuts at the last boundary that fits — space, hyphen, dash or slash.
    The ONLY case that can still split a word is when the first word
    alone overruns the budget, because then no boundary exists.

    >>> clip_words("a much longer sentence than fits here", 20)
    'a much longer…'
    >>> clip_words("short", 20)
    'short'
    """
    text = (text or "").strip()
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text

    budget = limit - len(ellipsis)
    if budget <= 0:
        return text[:limit]

    cut = text[:budget]
    # Break at the last boundary that fits. Hyphens and slashes count:
    # "1.6-trillion-parameter" reads fine cut to "1.6-trillion", and
    # without them a short first word followed by a long compound
    # ("A 1.6-trillion-parameter model") had no usable space boundary and
    # fell through to a mid-word cut.
    boundary = max(cut.rfind(c) for c in _BREAK_CHARS)
    if boundary > 0:
        cut = cut[:boundary]
    # boundary <= 0 means the first word alone overruns the budget — there
    # is genuinely nowhere to break, so the hard cut stands. That is the
    # only path that can split a word.
    return cut.rstrip(_TRAILING) + ellipsis


# --- A title fitted whole --------------------------------------------

#: Where a sentence breaks into clauses, strongest first. These are tried
#: in this order before a word boundary is looked for.
CLAUSE_SEPARATORS = (" — ", ": ", "; ")

#: Words a sentence can be cut BEFORE and still read as a whole thought:
#: conjunctions, relative pronouns, subordinators and the prepositions that
#: open a trailing phrase. Matched as whole lower-case words. "of" is
#: deliberately absent — "the loss of" cut before "of" is a stub.
CLAUSE_BREAK_WORDS = frozenset({
    "but", "and", "or", "nor", "yet", "so", "while", "whereas", "because",
    "since", "although", "though", "unless", "until", "that", "which", "who",
    "whom", "whose", "where", "when", "whenever", "once", "after", "before",
    "as", "by", "without", "with", "to", "than", "now", "then", "across",
    "into", "from", "for", "in", "on", "at", "over", "under", "within",
    "through", "via", "despite", "amid", "between", "toward", "towards",
    "against", "about", "beyond", "instead",
})

#: Words a clause may never END on: an article, a possessive or a
#: demonstrative leaves the noun it announces behind ("…fights the").
#: Review of Nov 4 2026: a break word that opens a hyphenated compound
#: ("so-called", "on-site", "co-founder") is not a break at all, and the
#: cut in front of it had left exactly this kind of stub.
CLAUSE_STUB_TAIL_WORDS = frozenset({
    "the", "a", "an", "its", "their", "his", "her", "our", "your", "my",
    "this", "these", "those", "every", "each", "very",
})

#: A first clause shorter than this many words is a stub, not a title;
#: :func:`fit_first_clause` falls through to :func:`clip_words` instead.
FIRST_CLAUSE_MIN_WORDS = 5

#: How many words after a comma are read to tell a list comma ("copy,
#: targeting and optimization") from a clause break.
_LIST_COMMA_LOOKAHEAD_WORDS = 3


def _is_list_comma(text: str, at: int) -> bool:
    """True when the comma at *at* separates list items, not clauses."""
    words = text[at + 1:].split()
    for i, word in enumerate(words[:_LIST_COMMA_LOOKAHEAD_WORDS + 1]):
        if word.strip(",;:").lower() in ("and", "or"):
            return True
        if i < _LIST_COMMA_LOOKAHEAD_WORDS and word.endswith(","):
            return True
    return False


def _closes_a_list(head: str) -> bool:
    """True when *head* ends inside a comma list ("…for copy, targeting"),
    so a cut before the "and" / "or" that follows would leave a list open."""
    tail = head.rsplit(",", 1)
    return len(tail) == 2 and len(tail[1].split()) <= _LIST_COMMA_LOOKAHEAD_WORDS


def _clause_breaks(text: str):
    """Offsets where *text* may be cut: at a clause comma, and before each
    clause-break word (the offset is the whitespace in front of it). A
    conjunction that closes a comma list is not a break."""
    offsets = set()
    for m in re.finditer(r",\s", text):
        if not _is_list_comma(text, m.start()):
            offsets.add(m.start())
    # A whole word only: "so" in "so-called", "on" in "on-site" and "co" in
    # "co-founder" open a compound, not a clause.
    for m in re.finditer(r"\s([A-Za-z]+)(?![\w-])", text):
        word = m.group(1).lower()
        if word not in CLAUSE_BREAK_WORDS:
            continue
        if word in ("and", "or", "nor") and _closes_a_list(text[:m.start()]):
            continue
        offsets.add(m.start())
    return sorted(offsets)


def _whole_clause(head: str, limit: int) -> bool:
    words = head.split()
    tail = words[-1].strip(_TRAILING).lower() if words else ""
    return (bool(head) and len(head) <= limit
            and len(words) >= FIRST_CLAUSE_MIN_WORDS
            and tail not in CLAUSE_BREAK_WORDS
            and tail not in CLAUSE_STUB_TAIL_WORDS)


def fit_first_clause(text: str, limit: int, *, ellipsis: str = ELLIPSIS) -> str:
    """*text* whole when it fits *limit*, else its first clause, else
    :func:`clip_words`.

    Nov 4 2026. Every interview episode's feed title is ``Ep<n>: <guest> —
    <thesis>`` and the thesis is a full sentence of 180-260 characters, so
    six of nineteen titles ended in an ellipsis the moment ``clip_words``
    met the 100-character feed cap. A sentence has a shape a cut can
    follow: the strongest separators first (:data:`CLAUSE_SEPARATORS`, in
    that order, the first whose head fits), then the LONGEST prefix that
    ends right before a clause break — a comma that is not a list comma,
    or a conjunction / relative pronoun / subordinator / trailing-phrase
    preposition (:data:`CLAUSE_BREAK_WORDS`, matched as a whole word, so
    the "so" of "so-called" is never a break). A head under
    :data:`FIRST_CLAUSE_MIN_WORDS` words, or one that ends on an article,
    a possessive or a demonstrative (:data:`CLAUSE_STUB_TAIL_WORDS`), is a
    stub and does not count.
    When no clause fits, the result is ``clip_words(text, limit)`` with its
    ellipsis — the one honest sign that the sentence was cut mid-thought.

    The result is always ``<= limit`` and never splits a word.

    >>> fit_first_clause("A founder builds verified credentials that replace CVs", 50)
    'A founder builds verified credentials'
    >>> fit_first_clause("Short enough already", 50)
    'Short enough already'
    """
    text = (text or "").strip()
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    for sep in CLAUSE_SEPARATORS:
        head, found, _tail = text.partition(sep)
        if found:
            head = head.rstrip(_TRAILING)
            if _whole_clause(head, limit):
                return head
    best = ""
    for at in _clause_breaks(text):
        head = text[:at].rstrip(_TRAILING)
        if _whole_clause(head, limit) and len(head) > len(best):
            best = head
    if best:
        return best
    return clip_words(text, limit, ellipsis=ellipsis)


#: A Short title shorter than this many words is a fragment, not a headline.
FRAGMENT_TITLE_MIN_WORDS = 4
#: ...or shorter than this many characters (the #Shorts tag excluded).
FRAGMENT_TITLE_MIN_CHARS = 25

_HASHTAG_TAIL_RE = re.compile(r"(?:\s*#\w+)+\s*$")


def is_fragment_title(text: str) -> bool:
    """True when *text* reads as a transcript slice rather than a headline.

    Oct 3 2026: the dub channels titled their non-hook Shorts from a single
    Whisper segment, and 81 of 314 RU filled Shorts since August shipped as
    «в 2026 года», «2026 года», «Подсказки в 60-70% случаев». A headline
    starts with a capital (or a digit) and carries at least
    ``FRAGMENT_TITLE_MIN_WORDS`` words and ``FRAGMENT_TITLE_MIN_CHARS``
    characters. Language-agnostic on purpose (Latin and Cyrillic both have
    case); a script without case only meets the length tests. This judges
    shape, never length limits — clipping stays with ``clip_words``.
    """
    body = _HASHTAG_TAIL_RE.sub("", (text or "")).strip().strip("…").strip()
    if not body:
        return True
    if body[0].isalpha() and body[0].islower():
        return True
    if len(body.split()) < FRAGMENT_TITLE_MIN_WORDS:
        return True
    return len(body) < FRAGMENT_TITLE_MIN_CHARS


def fits(text: str, limit: int) -> bool:
    """True when *text* needs no clipping for *limit*."""
    return len((text or "").strip()) <= limit


def web_page_title(lead: str, show_name: str, *, limit: int = WEB_TITLE_LEAD_MAX) -> str:
    """The HTML ``<title>`` of an episode page: ``"<lead> · <Show>"``.

    *lead* is the episode's headline (or, for an interview, the guest's
    name and identifier), clipped to *limit* through :func:`clip_words`
    so it ends on a word; *show_name* follows whole, never clipped — it is
    the part that tells a searcher which show this is. No episode number:
    the page's h1 pill and breadcrumb carry it, and in a ~60-character
    search result it only displaced the show.

    An empty lead gives the show name alone, and a lead that IS the show
    name (the no-hook fallback) is not doubled.

    >>> web_page_title("Tesla registrations in Sweden rose 248 percent", "Tesla Shorts Time")
    'Tesla registrations in Sweden rose 248 percent · Tesla Shorts Time'
    """
    lead_text = clip_words(lead, limit)
    show = (show_name or "").strip()
    if not lead_text:
        return show
    if not show:
        return lead_text
    if lead_text.casefold() == show.casefold():
        return show
    return f"{lead_text}{WEB_TITLE_SEPARATOR}{show}"


def episode_title(
    hook: str,
    episode_num,
    *,
    prefix: str = "Ep",
    limit: int = PODCAST_EPISODE_TITLE_MAX,
    fallback: str = "",
) -> str:
    """Build ``"Ep 133: <hook>"`` guaranteed to fit *limit*.

    The episode label is never sacrificed — it is how listeners and the
    feed itself identify the episode — so the hook absorbs the clipping.
    Falls back to *fallback* (typically ``"<Show> - Episode N - <date>"``)
    when there is no hook, and that fallback is clipped too rather than
    trusted.

    *prefix* is a parameter because the Russian shows label episodes
    ``"Выпуск"``; the arithmetic has to use the real prefix length, not
    an assumed English one.
    """
    label = f"{prefix} {episode_num}:"
    hook = (hook or "").strip()

    if not hook:
        return clip_words(fallback, limit) if fallback else clip_words(label.rstrip(":"), limit)

    room = limit - len(label) - 1  # the space after the colon
    if room <= 0:
        # Pathological limit; keep the identifier, drop the hook.
        return clip_words(label.rstrip(":"), limit)

    return f"{label} {clip_words(hook, room)}"
