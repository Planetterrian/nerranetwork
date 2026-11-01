"""The names a script must keep, read from the digest it is written from.

Nov 1 2026 (operator decision on the Models & Agents review of Oct 31):
three passes asked the script prompt, in prose, to keep the briefing's
names, and each missed the same number (names kept >= 75 % on 3 of 10
episodes). This is the data-side lever instead: the script stage is handed
the list of names the digest actually carries, item by item, so a name is
something to check off rather than an instruction to remember.

Rules that bind:

- The list is DATA from today's digest, never an example: no fixed name,
  no specimen sentence, so nothing in it can be copied tomorrow.
- A title-case headline is not a list of names ("Video Autoencoders That
  Cut World Model Lag" capitalises every word); such lines are skipped and
  the names come from the item bodies, where a capital means a name.
- Pure read of the text. No model call, never raises; "" when the digest
  carries no names, so a show that opts in and has a thin day renders the
  prompt as if the block were absent.
"""

from __future__ import annotations

import re
from typing import List, Set

from engine.script_audit import _ENTITY_STOP

# Opt-in per show (ShowConfig.names_to_keep); the prompt placeholder.
PLACEHOLDER = "names_to_keep_block"
MAX_NAMES = 40
MAX_TOKENS_PER_NAME = 5

_HEADER_RE = re.compile(r"^\s{0,3}#{1,6}\s")
_URL_RE = re.compile(r"\(https?://\S+\)|https?://\S+")
_SOURCE_RE = re.compile(r"\b(?:Source|Sources|Read more)\b:?.*$", re.IGNORECASE)
_DECOR_RE = re.compile(r"[*_`>\[\]]")
_LEAD_RE = re.compile(r"^\s*(?:\d+[.)]|[-•])\s*")
# A bold label that opens a line ("**What You Need to Know:** …").
_LABEL_PREFIX_RE = re.compile(r"^\s*\*\*[^*]{1,60}?:\s*\*\*\s*|^\s*\*\*[^*]{1,60}?\*\*:\s*")
# Units and stray letters that precede a name in "27 B Qwen3.8" or
# "16 GB MLX"; never the start of a name.
_UNIT_TOKENS = frozenset("b k m gb mb tb kb ghz mhz ms kw mw gw w v".split())
_SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'“‘(])")
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)

# A run of capitalised tokens, optionally carrying a version or size
# ("Mistral Large 4", "Qwen3.8-27B", "Claude Opus 5.5").
_CAP = r"(?<![\w.'’\-])(?:[A-Z][\w.'’\-]*\w|[A-Z])"
_NUM = r"\d[\w.\-]*\w|\d"
_RUN_RE = re.compile(rf"(?:{_CAP})(?:\s+(?:of\s+|the\s+|de\s+)?(?:{_CAP}|{_NUM}))*")
# A run that starts with one of these is a sentence word, not a name.
_LEADING_WORDS = frozenset(
    "the this that these those a an our its their his her today yesterday "
    "tomorrow meanwhile also and but so then here there when while after "
    "before if as at in on for with from by".split()
)


def _clean(line: str) -> str:
    line = _LABEL_PREFIX_RE.sub("", line)
    line = _URL_RE.sub("", line)
    line = _SOURCE_RE.sub("", line)
    line = _DECOR_RE.sub("", line)
    return _LEAD_RE.sub("", line).strip()


def _is_title_case(line: str) -> bool:
    """A headline whose content words are all capitalised."""
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'’\-]*", line) if len(w) >= 4]
    if len(words) < 4:
        return False
    caps = sum(1 for w in words if w[0].isupper())
    share = caps / len(words)
    # A sentence dense with names still ends like a sentence; a headline
    # does not. Only an all-capitalised line is a headline either way.
    if line.rstrip().endswith((".", "!", "?")):
        return share >= 0.9
    return share >= 0.7


def _key(tok: str) -> str:
    return re.sub(r"['’]s$", "", tok).lower()


def _is_label(raw: str) -> bool:
    """A bold line on its own: a section label or an item headline."""
    s = raw.strip().rstrip(":")
    return s.startswith("**") and s.endswith("**") and len(s.split()) <= 8


def _split_lines(digest_text: str):
    """(body sentences, headline lines) of the digest."""
    out: List[str] = []
    heads: List[str] = []
    text = _FENCE_RE.sub("", digest_text or "")
    for raw in text.splitlines():
        if not raw.strip() or _HEADER_RE.match(raw):
            continue
        if _is_label(raw):
            heads.append(_clean(raw))
            continue
        line = _clean(raw)
        if not line:
            continue
        if _is_title_case(line):
            heads.append(line)
            continue
        out.extend(s for s in _SENT_RE.split(line) if s.strip())
    return out, heads


def _body_sentences(digest_text: str) -> List[str]:
    return _split_lines(digest_text)[0]


def _name_vocabulary(sentences: List[str]) -> Set[str]:
    """Tokens capitalised somewhere other than at a sentence's start."""
    vocab: Set[str] = set()
    for sent in sentences:
        toks = re.findall(rf"{_CAP}", sent)
        for i, tok in enumerate(toks):
            if i == 0 and sent.lstrip().startswith(tok):
                continue
            key = _key(tok)
            if len(key) >= 2 and key not in _ENTITY_STOP:
                vocab.add(key)
    return vocab


def names_to_keep(digest_text: str, *, max_names: int = MAX_NAMES) -> List[str]:
    """The digest's names, as written, in order of first appearance."""
    try:
        sentences, heads = _split_lines(digest_text)
        vocab = _name_vocabulary(sentences)
        # Words the digest also writes in lower case are ordinary words
        # ("Space", "Labs", "World"), never a one-word name on their own.
        lower_words = set(re.findall(r"\b[a-z][a-z'’\-]+\b", " ".join(sentences)))
        # A word an item's headline capitalises and the body never writes
        # in lower case is a name even where it only opens a sentence
        # ("Kyutai released CADRE" under "Kyutai CADRE: …").
        vocab |= {
            _key(t) for h in heads for t in re.findall(_CAP, h)
            if _key(t) not in lower_words and _key(t) not in _ENTITY_STOP
            and _key(t) not in _LEADING_WORDS and len(_key(t)) >= 3
        }
        seen: dict = {}
        for sent in sentences:
            for m in _RUN_RE.finditer(sent):
                toks = m.group(0).split()
                at_start = sent.lstrip().startswith(m.group(0))
                # Trim the sentence's own first word and ordinary words off
                # both ends; a number stays only when it follows a name.
                while toks and (
                    _key(toks[0]) in _LEADING_WORDS
                    or (_key(toks[0]) in _ENTITY_STOP
                        and not (_key(toks[0]) == "new" and not at_start
                                 and len(toks) > 1))
                    or _key(toks[0]) in _UNIT_TOKENS
                    or (at_start and _key(toks[0]) in lower_words)
                    or (at_start and len(toks[0]) == 1)
                ):
                    toks.pop(0)
                    at_start = False
                while toks and toks[-1].lower() in ("of", "the", "de"):
                    toks.pop()
                while toks and not toks[-1][0].isdigit() and _key(toks[-1]) not in vocab:
                    toks.pop()
                if not toks or len(toks) > MAX_TOKENS_PER_NAME:
                    continue
                name = re.sub(r"['’]s$", "", " ".join(toks)).strip(" .,;:")
                if (len(name) < 2 or _key(name) in _ENTITY_STOP
                        or not re.search(r"[A-Za-z]{2}", name)):
                    continue
                if len(toks) == 1:
                    tok = toks[0]
                    # An everyday word, or a short all-capitals term with no
                    # digit (CPU, API, RL), is not a name on its own.
                    if _key(tok) in lower_words:
                        continue
                    bare = re.sub(r"s$", "", tok)
                    if bare.isupper() and len(bare) <= 4 and not re.search(r"\d", bare):
                        continue
                    # A compound adjective ("AI-assisted", "MIT-licensed").
                    if "-" in tok and re.fullmatch(r"[a-z]{4,}", tok.rsplit("-", 1)[-1]):
                        continue
                seen.setdefault(name.lower(), name)
        names = list(seen.values())
        # Drop a name that is wholly part of a longer one ("Mistral" when
        # "Mistral Large 4" is on the list).
        lowered = [n.lower() for n in names]
        kept = [
            n for n, low in zip(names, lowered)
            if not any(
                other != low and re.search(rf"(?:^|\s){re.escape(low)}(?:\s|$)", other)
                for other in lowered
            )
        ]
        return kept[:max_names]
    except Exception:  # noqa: BLE001 — a writer aid never costs an episode
        return []


def build_names_block(digest_text: str) -> str:
    """The writer-only block for the podcast prompt; "" when no names."""
    names = names_to_keep(digest_text)
    if not names:
        return ""
    return (
        "NAMES TO KEEP (for you, the writer; never read this list aloud or "
        "mention it): these are the names in today's briefing. When you tell "
        "a story, say its names as the briefing writes them, in place of any "
        "description of them, and spell out the numbers in a name the way the "
        "delivery rules say. A story you leave out takes its names with it; "
        "never add a name to a story that does not carry it.\n"
        + ", ".join(names)
    )
