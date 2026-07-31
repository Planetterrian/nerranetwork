"""Vocabulary memory for Привет, Русский! (spaced repetition + theme rotation).

June 10 2026 Russian-shows review: the language-learning show taught each
episode's vocabulary in complete isolation — words never reappeared, and
the "rotating everyday domains" promise broke down (Animals ran three
consecutive episodes) because nothing remembered what had been taught.

This module is the show's equivalent of the narrative-memory engines:

* ``record_episode_vocab`` mines the Cyrillic vocabulary actually taught
  in a digest/lesson plan and persists it (word → first/last episode).
* ``build_review_section`` composes the ``{vocab_review_section}`` prompt
  block: 3-4 previously-taught words due for a quick spoken review
  callback (oldest-seen first — crude spaced repetition), plus the last
  few episodes' vocabulary as a DO-NOT-RETEACH list so themes rotate.

Storage: ``digests/privet_russian/vocab_taught.json``. Empty/missing
state composes to an empty string, so the placeholder is a true no-op
until at least one episode has been recorded.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

VOCAB_FILENAME = "vocab_taught.json"

# Russian function words / glue vocabulary that appear in every lesson's
# example sentences but are never the *taught* word. Mining counts
# frequency, so without this filter "это"/"очень" would outrank the
# actual lesson vocabulary.
_RU_STOPWORDS = {
    "это", "как", "что", "для", "его", "она", "оно", "они", "оны", "вас",
    "нас", "мне", "вам", "там", "тут", "уже", "ещё", "еще", "или", "если",
    "когда", "очень", "просто", "сегодня", "завтра", "вчера", "теперь",
    "потом", "можно", "нужно", "надо", "есть", "был", "была", "было",
    "были", "будет", "тоже", "только", "даже", "перед", "после", "между",
    "через", "слово", "слова", "русский", "русском", "по-русски", "пример",
    "предложение", "значит", "давайте", "пока", "привет", "спасибо",
    "пожалуйста", "хорошо", "день", "выпуск", "урок", "тема",
}

# A taught word becomes "due for review" this many episodes after it was
# last heard. Two episodes ≈ 4 calendar days on the even-day cadence —
# inside the forgetting window without crowding new material.
_REVIEW_GAP_EPISODES = 2
_REVIEW_WORDS_PER_EPISODE = 4
# July 2 2026 review: 3 -> 8. Three episodes was ONE theme-cycle short —
# the show looped Food -> Animals -> Weather 2.3× in 8 episodes and only 27
# of 87 taught word-slots were new, because a theme three episodes back was
# neither in the no-reteach window NOR remembered as a used theme. Eight
# episodes (~16 days on the even-day cadence) clears a full rotation.
_RECENT_EPISODES_NO_RETEACH = 8
# Recent themes surfaced to the prompt as an explicit "do not reuse" list.
# >= the no-reteach window: with themes remembered for fewer episodes
# than words, a theme could return while its words were still banned —
# the July 31 2026 review found a systematic re-teach cycle (ep58/59/60/
# 63 each re-taught 5-7 words from exactly 7-8 episodes back) driven by
# this 6 < 8 mismatch together with the [:24] cap below.
_RECENT_THEMES_WINDOW = _RECENT_EPISODES_NO_RETEACH
_WORDS_PER_EPISODE_CAP = 12


def _path(output_dir: Path) -> Path:
    return Path(output_dir) / VOCAB_FILENAME


def _fresh() -> Dict[str, Any]:
    return {
        "version": 1, "last_updated": "", "words": {}, "episodes": {},
        # July 2 2026: permanent Word-of-the-Day ledger (a word here is
        # never picked as Word of the Day again — «хлеб» was WotD 3× in 12
        # days) + per-episode theme record for the recent-theme rotation.
        "word_of_day_history": [], "themes": {},
    }


def load_vocab(output_dir: Path) -> Dict[str, Any]:
    p = _path(output_dir)
    if not p.exists():
        return _fresh()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load %s (%s) — starting fresh", p.name, exc)
        return _fresh()
    # Back-compat: older files predate the WotD ledger + theme record.
    data.setdefault("word_of_day_history", [])
    data.setdefault("themes", {})
    return data


def save_vocab(data: Dict[str, Any], output_dir: Path) -> None:
    data["last_updated"] = datetime.now().isoformat()
    p = _path(output_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def mine_vocabulary(text: str, cap: int = _WORDS_PER_EPISODE_CAP) -> List[str]:
    """Extract the episode's taught Cyrillic vocabulary from lesson text.

    Heuristic: in a vocabulary-first lesson the taught words are the
    most-repeated Cyrillic tokens (each is said, repeated slowly, and
    used in an example sentence), so frequency ranking after a
    function-word filter recovers them well — verified against Ep32-36
    (космос/звезда/ракета…, яблоко/хлеб/молоко…).
    """
    words = re.findall(r"\b[а-яё]{3,}\b", (text or "").lower())
    counts = Counter(w for w in words if w not in _RU_STOPWORDS)
    return [w for w, c in counts.most_common(cap) if c >= 2]


def extract_word_of_day(text: str) -> str:
    """Return the episode's Word of the Day (lowercased Cyrillic), or ''.

    Handles both the digest's "### Word of the Day" section (the first
    Cyrillic token after the header, tolerating a bold marker or a
    "Russian (Cyrillic):" label) and the inline "word of the day is X"
    phrasing used in lesson prose.
    """
    if not text:
        return ""
    # Section form: "### Word of the Day\n**хлеб**" / "…**Russian (Cyrillic):** Солнце".
    m = re.search(r"word of the day\s*[:\-]?\s*(.*)", text, re.IGNORECASE)
    if m:
        # Search the header match's tail plus the following ~2 lines.
        tail_start = m.start()
        window = text[tail_start:tail_start + 200]
        # Drop a "Russian (Cyrillic):" label so it doesn't shadow the word.
        window = re.sub(r"russian\s*\(cyrillic\)\s*:?", " ", window, flags=re.IGNORECASE)
        cyr = re.search(r"[а-яё]{2,}", window, re.IGNORECASE)
        if cyr:
            return cyr.group(0).lower()
    return ""


def extract_theme(text: str) -> str:
    """Return a short theme label for the episode (from the hook), or ''.

    The hook is the digest's leading blockquote ("> **…**") or a "HOOK:"
    line. The full hook sentence is a good enough "domain" signal for the
    LLM's do-not-reuse list; truncated so the block stays scannable.
    """
    if not text:
        return ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(">") or re.match(r"^\**\s*hook\s*:", line, re.IGNORECASE):
            cleaned = line.lstrip(">").strip()
            cleaned = re.sub(r"[*_`]+", "", cleaned).strip()
            cleaned = re.sub(r"^hook\s*:\s*", "", cleaned, flags=re.IGNORECASE).strip()
            if cleaned:
                return cleaned[:90].rstrip()
        # Only inspect the first non-empty line for a hook.
        break
    return ""


def record_episode_vocab(output_dir: Path, episode_num: int, text: str) -> List[str]:
    """Mine + persist the episode's vocabulary. Idempotent per episode.

    Also records the episode's Word of the Day (into the permanent
    ``word_of_day_history`` ledger) and its theme (into ``themes``) so the
    review block can enforce no-repeat WotD selection and theme rotation.

    Returns the recorded word list.
    """
    data = load_vocab(output_dir)
    episodes = data.setdefault("episodes", {})
    key = str(episode_num)
    if key in episodes:
        logger.info("Vocab tracker already has Ep%s — skipping", episode_num)
        return episodes[key]

    taught = mine_vocabulary(text)
    if not taught:
        logger.info("No vocabulary mined from Ep%s — nothing recorded", episode_num)
        return []

    episodes[key] = taught
    words = data.setdefault("words", {})
    for w in taught:
        entry = words.setdefault(w, {"first_taught": episode_num, "last_heard": episode_num})
        entry["last_heard"] = episode_num

    # Permanent Word-of-the-Day ledger (dedup, order-preserving).
    wotd = extract_word_of_day(text)
    if wotd:
        history = data.setdefault("word_of_day_history", [])
        if wotd not in history:
            history.append(wotd)

    # Per-episode theme record for the recent-theme rotation list.
    theme = extract_theme(text)
    if theme:
        data.setdefault("themes", {})[key] = theme

    save_vocab(data, output_dir)
    logger.info("Vocab tracker: recorded %d words for Ep%s (%s…); WotD=%s theme=%r",
                len(taught), episode_num, ", ".join(taught[:5]), wotd or "—", theme[:40])
    return taught


def build_review_section(output_dir: Path, current_episode: int) -> str:
    """Compose the ``{vocab_review_section}`` prompt block ('' when empty)."""
    data = load_vocab(output_dir)
    words = data.get("words", {})
    episodes = data.get("episodes", {})
    if not words:
        return ""

    due = sorted(
        (
            (w, e) for w, e in words.items()
            if current_episode - int(e.get("last_heard", 0)) >= _REVIEW_GAP_EPISODES
        ),
        key=lambda item: int(item[1].get("last_heard", 0)),
    )
    review_words = [w for w, _ in due[:_REVIEW_WORDS_PER_EPISODE]]

    recent_eps = sorted((int(k) for k in episodes), reverse=True)
    recent_words: List[str] = []
    for ep in recent_eps[:_RECENT_EPISODES_NO_RETEACH]:
        recent_words.extend(episodes[str(ep)])

    # Never repeat a Word of the Day (permanent).
    wotd_history = data.get("word_of_day_history", []) or []

    # Recent themes (most-recent first) to rotate away from.
    themes = data.get("themes", {}) or {}
    recent_themes: List[str] = []
    for ep in recent_eps:
        t = themes.get(str(ep))
        if t:
            recent_themes.append(t)
        if len(recent_themes) >= _RECENT_THEMES_WINDOW:
            break

    lines = ["### VOCABULARY MEMORY (from previous episodes — use, do not read this section aloud)"]
    if review_words:
        lines.append(
            "REVIEW CALLBACKS (spaced repetition): naturally weave SHORT review "
            "moments for 2-3 of these previously taught words into today's lesson "
            "— e.g. 'Remember " + review_words[0] + " from a few lessons ago?' "
            "Then say the word slowly once and give its English meaning again. "
            "Due for review: " + ", ".join(review_words) + "."
        )
    if recent_words:
        lines.append(
            "RECENTLY TAUGHT (do NOT re-teach these as new words, and pick a "
            "DIFFERENT theme than they suggest): "
            # No cap: the old [:24] slice silently truncated the ban list
            # to the newest ~3.5 episodes while the header promised 8 —
            # words from episodes 4-8 back became re-teachable, which is
            # the exact re-teach cycle shipped on Привет, Русский!
            # ep58-63. 8 episodes x ~7 words ~= 56 tokens of prompt: cheap.
            + ", ".join(recent_words) + "."
        )
    if wotd_history:
        lines.append(
            "ALREADY USED AS WORD OF THE DAY (NEVER pick any of these as today's "
            "Word of the Day again — choose a brand-new word): "
            + ", ".join(wotd_history) + "."
        )
    if recent_themes:
        lines.append(
            "RECENT THEMES (do NOT reuse any of these everyday domains — choose a "
            "clearly different theme today): " + "; ".join(recent_themes) + "."
        )
    if len(lines) == 1:
        return ""
    return "\n".join(lines)
