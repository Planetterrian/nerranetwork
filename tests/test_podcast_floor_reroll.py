"""Publication-floor re-roll (Aug 2026, Tesla Ep564).

When a podcast script is still inside run_show's skip band (< 60% of
``min_podcast_words``, plus the 10% dedup margin) AFTER the expansion
retry, the episode is about to be thrown away entirely — Tesla lost the
whole 2026-08-06 slot this way (954-word first pass, expansion retry
reached only 1119 against the 1200 floor), and the identical 2026-07-31
skip was recovered by a MANUAL workflow rerun that produced a normal
1500-word script from the same digest. ``generate_podcast_script`` now
re-rolls the FULL original prompt once (a fresh sampling draw, not an
expansion of the short draft) before letting the runner skip the day.

These tests pin the safety properties:

* the re-roll fires ONLY inside the publication skip band — a merely
  below-target script never triggers it (it is NOT the banned
  podcast-side length lever from the July 18 playbook ``do_not_retry``);
* the fresh draw wins only when it is longer; a shorter re-roll keeps
  the current draft;
* a re-roll failure (exception / refusal) keeps the current draft.
"""

import random
from types import SimpleNamespace

import pytest

import engine.generator as gen


def _words(n: int, prefix: str = "w") -> str:
    """Build an n-word script whose sentences are seeded-random gibberish
    — textually diverse enough that neither the repetition detector nor
    ``_dedup_expansion_sentences`` (similarity >= 0.85) strips anything.
    The first word is a ``<prefix>marker`` token so tests can assert
    which candidate shipped."""
    rng = random.Random(prefix)
    out = [f"{prefix}marker"]
    sentence_len = rng.randint(9, 15)
    for i in range(1, n):
        word = "".join(
            rng.choice("abcdefghijklmnopqrstuvwxyz")
            for _ in range(rng.randint(3, 10))
        )
        if len(out) % sentence_len == 0:
            word += "."
            sentence_len = rng.randint(9, 15)
        out.append(word)
    return " ".join(out)


def _config(min_words: int = 2000, expand_below_target: bool = False):
    return SimpleNamespace(
        name="Tesla Shorts Time",
        llm=SimpleNamespace(
            model="grok-4.3",
            podcast_prompt_file="x",
            system_prompt_file="",
            podcast_temperature=0.7,
            max_tokens=5000,
            podcast_max_tokens=12000,
            min_podcast_words=min_words,
            podcast_expand_below_target=expand_below_target,
            podcast_chain=False,
        ),
    )


def _run(monkeypatch, responses):
    """Drive generate_podcast_script with a scripted _call_grok.

    ``responses`` maps call index (0-based) -> text to return. Records
    every prompt so tests can assert which retry paths fired.
    """
    calls = []

    def fake_call_grok(prompt, **kwargs):
        idx = len(calls)
        calls.append(prompt)
        return responses[idx], {"finish_reason": "stop"}

    monkeypatch.setattr(gen, "_call_grok", fake_call_grok)
    monkeypatch.setattr(gen, "load_prompt", lambda *a, **k: "PROMPT")
    result = gen.generate_podcast_script(
        {"digest": "Top stories...", "episode_num": 564},
        _config(),
    )
    return result, calls


class TestPublicationFloorReroll:
    # Tesla shape: min_podcast_words=2000 → soft floor 1200 → band 1320.

    def test_reroll_fires_and_recovers_the_episode(self, monkeypatch):
        """Ep564 shape: 950-word first pass, expansion retry lands at
        ~1150 (still in the skip band) — the fresh re-roll's 1500-word
        draw must ship."""
        result, calls = _run(monkeypatch, {
            0: _words(950),
            1: _words(1150, prefix="x"),   # expansion retry — accepted, still thin
            2: _words(1500, prefix="y"),   # fresh re-roll
        })
        assert len(calls) == 3, "publication-floor re-roll did not fire"
        # The re-roll is a FRESH generation: the full original prompt,
        # not an expand-your-own-draft instruction.
        assert calls[2] == calls[0]
        assert "script you just wrote" not in calls[2]
        assert len(result.split()) >= 1400

    def test_shorter_reroll_keeps_current_draft(self, monkeypatch):
        result, calls = _run(monkeypatch, {
            0: _words(950),
            1: _words(1150, prefix="x"),
            2: _words(900, prefix="y"),    # fresh draw came up SHORTER
        })
        assert len(calls) == 3
        assert "xmarker" in result and "ymarker" not in result

    def test_reroll_failure_keeps_current_draft(self, monkeypatch):
        calls = []

        def fake_call_grok(prompt, **kwargs):
            idx = len(calls)
            calls.append(prompt)
            if idx == 2:
                raise RuntimeError("boom")
            return {0: _words(950), 1: _words(1150, prefix="x")}[idx], \
                {"finish_reason": "stop"}

        monkeypatch.setattr(gen, "_call_grok", fake_call_grok)
        monkeypatch.setattr(gen, "load_prompt", lambda *a, **k: "PROMPT")
        result = gen.generate_podcast_script(
            {"digest": "Top stories...", "episode_num": 564}, _config(),
        )
        assert len(calls) == 3
        assert "xmarker" in result

    def test_no_reroll_above_the_skip_band(self, monkeypatch):
        """A below-target but publishable script (1400 words vs the
        2000 target, band 1320) must NOT trigger any extra call — the
        re-roll is a skip-rescue, never a target-chasing length lever
        (July 18 playbook do_not_retry)."""
        result, calls = _run(monkeypatch, {
            0: _words(1400),
        })
        assert len(calls) == 1, (
            "re-roll fired above the publication skip band — this is the "
            "banned podcast-side length-lever shape"
        )

    def test_reroll_only_after_expansion_retry_still_thin(self, monkeypatch):
        """When the expansion retry itself clears the band, no re-roll
        fires (two calls total)."""
        result, calls = _run(monkeypatch, {
            0: _words(950),
            1: _words(1450, prefix="x"),   # expansion retry clears the band
        })
        assert len(calls) == 2
        assert "xmarker" in result
