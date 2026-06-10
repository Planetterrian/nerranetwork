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
_RECENT_EPISODES_NO_RETEACH = 3
_WORDS_PER_EPISODE_CAP = 12


def _path(output_dir: Path) -> Path:
    return Path(output_dir) / VOCAB_FILENAME


def load_vocab(output_dir: Path) -> Dict[str, Any]:
    p = _path(output_dir)
    if not p.exists():
        return {"version": 1, "last_updated": "", "words": {}, "episodes": {}}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load %s (%s) — starting fresh", p.name, exc)
        return {"version": 1, "last_updated": "", "words": {}, "episodes": {}}


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


def record_episode_vocab(output_dir: Path, episode_num: int, text: str) -> List[str]:
    """Mine + persist the episode's vocabulary. Idempotent per episode.

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
    save_vocab(data, output_dir)
    logger.info("Vocab tracker: recorded %d words for Ep%s (%s…)",
                len(taught), episode_num, ", ".join(taught[:5]))
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
            "DIFFERENT theme than they suggest): " + ", ".join(recent_words[:20]) + "."
        )
    if len(lines) == 1:
        return ""
    return "\n".join(lines)
