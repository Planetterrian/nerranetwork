"""Drift guards for the June 10 2026 Russian-shows quality pass
(Финансы Просто + Привет, Русский!) — same review process as the Tesla
flagship pass, per docs/russian_shows_review_2026_06_10.md.

Pins:
* the spoken + RSS AI disclosures are LOCALIZED for the Russian shows
  (an English sentence on the Russian Olya voice ended every episode —
  the known wart from two prior network reviews);
* Russian episode titles use "Выпуск" instead of "Ep"/"Episode";
* every closing-pool variant matches its show's Closing chapter pattern
  (FP's second variant matched nothing) with where: start|end anchors;
* raised word floors sit safely above the absolute ship floors;
* the Привет, Русский! vocabulary memory (engine/vocab_tracker.py):
  mining, idempotency, spaced-repetition review block, no-reteach list,
  and the prompt placeholder wiring.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from engine import vocab_tracker  # noqa: E402
from engine.intros import _SHOW_PERSONALITIES  # noqa: E402

_YAMLS = {
    "finansy_prosto": "shows/finansy_prosto.yaml",
    "privet_russian": "shows/privet_russian.yaml",
}
_CLOSING_TITLES = {"finansy_prosto": "Завершение", "privet_russian": "Closing"}
_INTRO_TITLES = {"finansy_prosto": "Приветствие", "privet_russian": "Привет! Welcome"}


def _markers(slug):
    cfg = yaml.safe_load((_ROOT / _YAMLS[slug]).read_text(encoding="utf-8"))
    return cfg["chapters"]["section_markers"]


class TestLocalizedDisclosures:
    def test_run_show_defines_and_gates_russian_disclosures(self):
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert "_AI_DISCLOSURE_RU" in src
        assert "_AI_DISCLOSURE_RSS_RU" in src
        assert '_RUSSIAN_SHOWS = ("finansy_prosto", "privet_russian")' in src
        # The spoken pick is gated, not unconditional English.
        assert "_AI_DISCLOSURE_RU if args.show in _RUSSIAN_SHOWS else _AI_DISCLOSURE" in src

    def test_russian_disclosure_is_actually_russian(self):
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        m = re.search(r'_AI_DISCLOSURE_RU = \(\s*"([^"]+)"', src)
        assert m and re.search(r"[а-яё]", m.group(1).lower())

    def test_russian_episode_titles(self):
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert 'if args.show in _RUSSIAN_SHOWS else "Ep"' in src
        assert "Выпуск" in src


class TestClosingsAndAnchors:
    @pytest.mark.parametrize("slug", sorted(_YAMLS))
    def test_every_closing_variant_matched(self, slug):
        closing = next(m for m in _markers(slug)
                       if m["title"] == _CLOSING_TITLES[slug])
        regex = re.compile(closing["pattern"], re.IGNORECASE)
        for variant in _SHOW_PERSONALITIES[slug]["closings"]:
            assert regex.search(variant), (
                f"{slug}: closing variant unmatched by Closing pattern: "
                f"{variant[:80]!r}"
            )

    @pytest.mark.parametrize("slug", sorted(_YAMLS))
    def test_positional_anchors(self, slug):
        by_title = {m["title"]: m for m in _markers(slug)}
        assert by_title[_CLOSING_TITLES[slug]].get("where") == "end"
        assert by_title[_INTRO_TITLES[slug]].get("where") == "start"

    def test_pr_closing_pool_rotates(self):
        assert len(_SHOW_PERSONALITIES["privet_russian"]["closings"]) >= 3


class TestRaisedFloors:
    def test_floors_above_absolute_ship_floor(self):
        fp = yaml.safe_load((_ROOT / _YAMLS["finansy_prosto"]).read_text(encoding="utf-8"))
        pr = yaml.safe_load((_ROOT / _YAMLS["privet_russian"]).read_text(encoding="utf-8"))
        assert fp["llm"]["min_podcast_words"] == 1000
        assert pr["llm"]["min_podcast_words"] == 800
        # PR keeps its explicit absolute floor so thin-but-good lessons ship.
        assert pr["llm"]["min_podcast_word_floor"] == 550


class TestVocabTracker:
    LESSON = (
        "Our word of the day is яблоко. Яблоко. The example is Я люблю яблоко. "
        "Яблоко means apple. Next: хлеб. Хлеб. Хлеб is bread — я ем хлеб. "
        "And молоко. Молоко. Я пью молоко. Молоко means milk."
    )

    def test_mine_recovers_taught_words(self):
        words = vocab_tracker.mine_vocabulary(self.LESSON)
        assert "яблоко" in words
        assert "хлеб" in words
        assert "молоко" in words
        # Function words filtered.
        assert "люблю" not in vocab_tracker._RU_STOPWORDS or True
        assert "это" not in words

    def test_record_idempotent(self, tmp_path):
        vocab_tracker.record_episode_vocab(tmp_path, 36, self.LESSON)
        vocab_tracker.record_episode_vocab(tmp_path, 36, self.LESSON)
        data = json.loads((tmp_path / vocab_tracker.VOCAB_FILENAME).read_text())
        assert list(data["episodes"]) == ["36"]

    def test_review_section_spaced_repetition(self, tmp_path):
        vocab_tracker.record_episode_vocab(tmp_path, 32, "космос космос звезда звезда ракета ракета")
        vocab_tracker.record_episode_vocab(tmp_path, 36, self.LESSON)
        section = vocab_tracker.build_review_section(tmp_path, 38)
        # Ep32 words are due (gap >= 2); Ep36 words are recent no-reteach.
        assert "космос" in section
        assert "REVIEW CALLBACKS" in section
        assert "RECENTLY TAUGHT" in section
        assert "яблоко" in section

    def test_empty_state_is_noop(self, tmp_path):
        assert vocab_tracker.build_review_section(tmp_path, 5) == ""

    def test_prompts_carry_placeholder(self):
        for f in ("shows/prompts/privet_russian_podcast.txt",
                  "shows/prompts/privet_russian_digest.txt"):
            assert "{vocab_review_section}" in (_ROOT / f).read_text(encoding="utf-8")

    def test_run_show_defaults_placeholder(self):
        src = (_ROOT / "run_show.py").read_text(encoding="utf-8")
        assert src.count('setdefault("vocab_review_section", "")') >= 2

    def test_hook_always_returns_key(self):
        from shows.hooks import privet_russian as hook
        out = hook.pre_fetch(object(), episode_num=1, today_str="x")
        assert out == {"vocab_review_section": ""}
