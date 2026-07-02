"""Drift guards for the July 2026 network-wide editorial pass fixes.

Covers (each verified against shipped episodes by review agents):
1. Comma-blind currency/ordinal normalization (assets/pronunciation.py) —
   the shipped-input regressions live in tests/test_pronunciation.py; here
   we pin the end-to-end prepare_text_for_tts path.
2. Missing-closing guard fuzzy signature match (engine/pipeline.py) — the
   literal check double-appended the closing on 5 of 15 MAB episodes.
3. Expansion-retry paraphrase-duplication dedup (engine/generator.py) —
   M&A Ep087 shipped verbatim doubled sentences in audio.
4. "Source:" scaffold line scrub in the script-save path (run_show.py) —
   FP Ep059 voiced "Сорс MoneySense…".
6. Phonetic-garble restore additions (engine/utils.py).
7. Review-snapshot blind spots (scripts/review_snapshot.py) — Cyrillic-blind
   tic detector; final-chapter-not-Closing shape check.
8. Spoken-URL tripwire (run_show.py) — MAB Ep081 read a Reddit permalink
   letter-by-letter on air.
"""

import importlib.util
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _load_script(name):
    spec = importlib.util.spec_from_file_location(
        name, PROJECT_ROOT / "scripts" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# 1. Comma-grouped currency/ordinals through the full TTS-prep path
# ---------------------------------------------------------------------------

class TestCommaNormalizationEndToEnd:
    def test_tesla_hook_price_and_milestone(self):
        from assets.pronunciation import prepare_text_for_tts

        out = prepare_text_for_tts(
            "Tesla cut the Model Y to $59,990 and delivered its 1,000th "
            "Cybertruck, with a cheaper trim under $20,000 planned."
        )
        assert "fifty-nine thousand nine hundred ninety dollars" in out
        assert "twenty thousand dollars" in out
        assert "one thousandth" in out
        # None of the shipped garble shapes may survive.
        assert "dollars,990" not in out
        assert "dollars,000" not in out
        assert "zeroth" not in out

    def test_spacex_landing_milestone(self):
        from assets.pronunciation import prepare_text_for_tts

        out = prepare_text_for_tts("Falcon 9 notched its 1,500th landing.")
        assert "one thousand five hundredth" in out
        assert "1," not in out


# ---------------------------------------------------------------------------
# 2. Missing-closing guard: fuzzy signature match (engine/pipeline.py)
# ---------------------------------------------------------------------------

class TestClosingGuardFuzzyMatch:
    """The June-10 guard compared the closing's first-5-words signature
    LITERALLY, so the LLM's de-contracted "And that is a wrap!" missed and
    the guard appended the ENTIRE closing again — 5 of 15 MAB episodes
    shipped the closing spoken twice (Ep075/076/077/079/084)."""

    CLOSING = (
        "And that's a wrap! If you enjoyed today's episode, subscribe "
        "wherever you get your podcasts and share it with a friend."
    )
    BODY = (
        "Today we looked at three model releases and what they mean for "
        "developers building agents. " * 10
    )

    def test_exact_closing_is_present(self):
        from engine.pipeline import closing_block_present

        script = self.BODY + "\n\n" + self.CLOSING
        assert closing_block_present(script, self.CLOSING) is True

    def test_decontracted_closing_is_present_not_appended(self):
        from engine.pipeline import closing_block_present

        # The MAB double-closing class: LLM expands "that's" → "that is".
        script = self.BODY + (
            "\n\nAnd that is a wrap! If you enjoyed today's episode, "
            "subscribe wherever you get your podcasts and share it with "
            "a friend."
        )
        assert closing_block_present(script, self.CLOSING) is True

    def test_punctuation_variant_is_present(self):
        from engine.pipeline import closing_block_present

        script = self.BODY + (
            "\n\nAnd that's a wrap — if you enjoyed today's episode, "
            "subscribe wherever you get your podcasts, and share it with "
            "a friend!"
        )
        assert closing_block_present(script, self.CLOSING) is True

    def test_recontracted_closing_is_present(self):
        from engine.pipeline import closing_block_present

        # Reverse drift: supplied closing de-contracted, LLM contracts it.
        closing = "And that is a wrap! If you enjoyed today's episode, share it."
        script = self.BODY + "\n\nAnd that's a wrap! If you enjoyed today's episode, share it."
        assert closing_block_present(script, closing) is True

    def test_host_prefix_on_closing_is_ignored(self):
        from engine.pipeline import closing_block_present

        script = self.BODY + "\n\n" + self.CLOSING
        assert closing_block_present(script, "Host: " + self.CLOSING) is True

    def test_genuinely_absent_closing_triggers_append(self):
        from engine.pipeline import closing_block_present

        # PT Ep084 class: episode ends mid-teaser with no sign-off.
        script = self.BODY + "\n\nTomorrow we dig into the new benchmark suite."
        assert closing_block_present(script, self.CLOSING) is False

    def test_similar_words_but_different_closing_is_absent(self):
        from engine.pipeline import closing_block_present

        script = self.BODY + "\n\nThanks for listening and see you next time."
        assert closing_block_present(script, self.CLOSING) is False

    def test_empty_inputs(self):
        from engine.pipeline import closing_block_present

        assert closing_block_present("", self.CLOSING) is False
        assert closing_block_present(self.BODY, "") is False


# ---------------------------------------------------------------------------
# 3. Expansion-retry paraphrase-duplication dedup (engine/generator.py)
# ---------------------------------------------------------------------------

_DISTINCT_SENTENCES = [
    "Sui deployed Seal MPC on mainnet, bringing threshold encryption to decentralized apps.",
    "Meanwhile the robotics lab in Zurich published a dexterity benchmark using cheap hobby servos.",
    "A separate filing shows the chip startup raised forty million dollars at a flat valuation.",
    "Regulators in Brussels opened a consultation on synthetic media labeling for election ads.",
    "The open-weights release ships with a permissive license and a sixteen-language tokenizer.",
    "Battery researchers at Dalhousie reported a dry-electrode cathode that survives long cycling.",
    "One hospital network cut transcription costs by piping visits through an on-premise model.",
    "The maintainers of the popular inference server merged speculative decoding support overnight.",
]


class TestExpansionRetryDedup:
    def test_doubled_sentences_are_stripped(self):
        from engine.generator import _dedup_expansion_sentences

        original = " ".join(_DISTINCT_SENTENCES)
        # M&A Ep087 class: the "expansion" re-states what it already wrote.
        expanded = original + " " + original
        deduped, removed = _dedup_expansion_sentences(expanded)
        assert removed == len(_DISTINCT_SENTENCES)
        assert deduped.count("Sui deployed Seal MPC on mainnet") == 1

    def test_near_paraphrase_is_stripped(self):
        from engine.generator import _dedup_expansion_sentences

        expanded = (
            "Sui deployed Seal MPC on mainnet, bringing threshold encryption "
            "to decentralized apps. "
            + _DISTINCT_SENTENCES[1] + " "
            + "Sui has deployed Seal MPC on mainnet, bringing threshold "
            "encryption to decentralized applications."
        )
        deduped, removed = _dedup_expansion_sentences(expanded)
        assert removed == 1
        assert deduped.count("Seal MPC") == 1

    def test_legit_expansion_passes_through_untouched(self):
        from engine.generator import _dedup_expansion_sentences

        expanded = "\n\n".join(_DISTINCT_SENTENCES)
        deduped, removed = _dedup_expansion_sentences(expanded)
        assert removed == 0
        assert deduped == expanded  # order + paragraph structure preserved

    def test_short_rhetorical_beats_survive(self):
        from engine.generator import _dedup_expansion_sentences

        expanded = (
            _DISTINCT_SENTENCES[0] + " Not bad, right? "
            + _DISTINCT_SENTENCES[1] + " Not bad, right?"
        )
        deduped, removed = _dedup_expansion_sentences(expanded)
        assert removed == 0
        assert deduped.count("Not bad, right?") == 2

    def test_degenerate_expansion_falls_back_to_original(self, monkeypatch):
        """End-to-end: an expansion that only re-states the original must
        NOT be accepted — the original script ships instead."""
        from types import SimpleNamespace
        from engine import generator as gen

        original = " ".join(_DISTINCT_SENTENCES)  # ~110 words, well below target
        calls = []

        def fake_call_grok(prompt, **kwargs):
            calls.append(prompt)
            if len(calls) == 1:
                return original, {"finish_reason": "stop"}
            # Paraphrase-padding: the same script, stated twice.
            return original + " " + original, {"finish_reason": "stop"}

        monkeypatch.setattr(gen, "_call_grok", fake_call_grok)
        monkeypatch.setattr(gen, "load_prompt", lambda *a, **k: "PROMPT")

        config = SimpleNamespace(
            name="Models & Agents",
            llm=SimpleNamespace(
                model="grok-4.3", podcast_prompt_file="x",
                system_prompt_file="", podcast_temperature=0.7,
                max_tokens=5000, podcast_max_tokens=10000,
                min_podcast_words=1500, podcast_expand_below_target=True,
                podcast_chain=False,
            ),
        )
        result = gen.generate_podcast_script(
            {"digest": "Top stories...", "episode_num": 87}, config,
        )
        assert len(calls) >= 2, "expansion retry did not fire"
        # The doubled restatement must never ship.
        assert result.count("Sui deployed Seal MPC on mainnet") == 1
        # And the original (not a truncated dedup residue) was kept.
        assert len(result.split()) <= len(original.split()) + 5


# ---------------------------------------------------------------------------
# 4. "Source:" scaffold lines never reach TTS (run_show.py)
# ---------------------------------------------------------------------------

class TestSourceScaffoldScrub:
    def test_source_label_lines_dropped(self):
        from run_show import _strip_source_scaffold_lines

        script = (
            "Great story about mortgage renewals today.\n"
            "Source: MoneySense\n"
            "Sources: Reuters, AP\n"
            "**Source:** The Globe and Mail\n"
            "- Source: BNN Bloomberg\n"
            "Источник: РБК\n"
            "Источники: Ведомости, Коммерсант\n"
            "More prose follows here."
        )
        out = _strip_source_scaffold_lines(script)
        assert "MoneySense" not in out
        assert "Reuters" not in out
        assert "Globe and Mail" not in out
        assert "BNN Bloomberg" not in out
        assert "РБК" not in out
        assert "Ведомости" not in out
        assert "Great story about mortgage renewals today." in out
        assert "More prose follows here." in out

    def test_prose_mentioning_sources_is_kept(self):
        from run_show import _strip_source_scaffold_lines

        script = (
            "The source: a leaked memo — is worth naming.\n"
            "Analysts trace the source of the rally to short covering.\n"
            "According to three sources, the deal closed Friday."
        )
        # Only lines BEGINNING with the bare label are scaffold; the first
        # line here starts with "The", so all three survive.
        assert _strip_source_scaffold_lines(script) == script


# ---------------------------------------------------------------------------
# 6. Phonetic-garble restore additions (engine/utils.py)
# ---------------------------------------------------------------------------

class TestJulyGarbleAdditions:
    def test_new_garbles_restored(self):
        from engine.utils import fix_phonetic_garbles

        assert fix_phonetic_garbles("Mee-stral shipped a new model.") == (
            "Mistral shipped a new model."
        )
        assert fix_phonetic_garbles("as Kar-pathy noted on stream") == (
            "as Karpathy noted on stream"
        )
        assert fix_phonetic_garbles("Mid-journey's new render mode") == (
            "Midjourney's new render mode"
        )
        assert fix_phonetic_garbles("a deal with Notpower for storage") == (
            "a deal with NatPower for storage"
        )

    def test_case_insensitive(self):
        from engine.utils import fix_phonetic_garbles

        assert fix_phonetic_garbles("MEE-STRAL and KAR-PATHY") == (
            "Mistral and Karpathy"
        )

    def test_correct_spellings_untouched(self):
        from engine.utils import fix_phonetic_garbles

        text = "Mistral, Karpathy, Midjourney, and NatPower are all fine."
        assert fix_phonetic_garbles(text) == text


# ---------------------------------------------------------------------------
# 7. Review-snapshot blind spots (scripts/review_snapshot.py)
# ---------------------------------------------------------------------------

class TestSnapshotCyrillicTicDetector:
    def test_russian_template_phrase_detected(self):
        snap = _load_script("review_snapshot")
        template = (
            "Спасибо, что провели это время со мной, и до новой встречи "
            "в следующем выпуске подкаста."
        )
        fillers = [
            "Сегодня мы обсуждали ипотеку и ставки по кредитам.",
            "Сегодня мы говорили про детский вычет и налоги.",
            "Сегодня разобрали страхование жизни и полисы.",
            "Сегодня тема выпуска пенсионные накопления и взносы.",
            "Сегодня речь шла о бюджете семьи и планировании.",
            "Сегодня новый разговор об инвестициях и фондах.",
            "Сегодня выпуск о сбережениях и подушке безопасности.",
            "Сегодня подробно о кредитных картах и кэшбэке.",
        ]
        texts = [f"{filler} {template}" for filler in fillers]
        phrases = [p for p, _ in snap.find_repeated_ngrams(texts)]
        assert any("спасибо" in p or "до новой встречи" in p for p in phrases), (
            f"Cyrillic template not detected; got: {phrases}"
        )

    def test_tokenizer_is_unicode_aware(self):
        snap = _load_script("review_snapshot")
        toks = snap._tokens("Спасибо, что слушали — that's all folks!")
        assert "спасибо" in toks
        assert "слушали" in toks
        assert "that's" in toks


class TestSnapshotFinalChapterCheck:
    def test_final_non_closing_chapter_flagged(self):
        snap = _load_script("review_snapshot")
        chapters = [
            {"title": "Introduction"},
            {"title": "Compliance Brief"},
            {"title": "Week Ahead"},  # EI Ep049-051 class: no Closing at all
        ]
        issues = " ".join(snap.chapter_issues(chapters))
        assert "final chapter is not a Closing" in issues

    def test_closing_last_is_clean(self):
        snap = _load_script("review_snapshot")
        chapters = [
            {"title": "Introduction"},
            {"title": "Compliance Brief"},
            {"title": "Tomorrow Teaser"},
            {"title": "Closing"},
        ]
        assert snap.chapter_issues(chapters) == []

    def test_outro_accepted_as_closing_synonym(self):
        snap = _load_script("review_snapshot")
        chapters = [{"title": "Introduction"}, {"title": "Outro"}]
        assert snap.chapter_issues(chapters) == []


# ---------------------------------------------------------------------------
# 8. Spoken-URL tripwire (run_show.py)
# ---------------------------------------------------------------------------

class TestSpokenUrlTripwire:
    def test_reddit_permalink_detected(self):
        from run_show import _count_spoken_urls

        # MAB Ep081 class: a full permalink in spoken form.
        assert _count_spoken_urls(
            "the thread is at reddit dot com/r/LocalLLaMA/comments/abc123"
        ) == 1
        assert _count_spoken_urls(
            "head to reddit dot com slash r slash LocalLLaMA for details"
        ) == 1

    def test_bare_spoken_domains_detected(self):
        from run_show import _count_spoken_urls

        text = "compare huggingface dot co — sorry, huggingface dot com and github dot io"
        assert _count_spoken_urls(text) == 2

    def test_network_cta_domain_excluded(self):
        from run_show import _count_spoken_urls

        assert _count_spoken_urls(
            "Find every show, free, at nerranetwork dot com."
        ) == 0
        assert _count_spoken_urls(
            "Find every show, free, at nerra network dot com."
        ) == 0

    def test_plain_prose_clean(self):
        from run_show import _count_spoken_urls

        assert _count_spoken_urls(
            "Connect the dots: communities online drive adoption."
        ) == 0
