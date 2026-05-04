"""Tests for the Grok TTS code path (xAI /v1/tts).

The HTTP layer is mocked end-to-end so the suite never hits the network.
We verify the request shape sent to xAI, the dispatch from `synthesize()`
based on `provider`, and the per-character pricing in the tracking layer.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from engine import tts
from engine.tracking import (
    GROK_TTS_COST_PER_1K_CHARS,
    TTS_PROVIDER_PRICING,
    create_tracker,
    record_tts_usage,
    save_usage,
)


# ---------------------------------------------------------------------------
# Helper — fake the requests.post context manager pattern used by the module
# ---------------------------------------------------------------------------

def _make_fake_post(status_code: int = 200, body_bytes: bytes = b"\xff\xfb\x90"):
    """Return a `requests.post` replacement returning `body_bytes` as MP3."""
    captured: dict = {}

    class _FakeResponse:
        def __init__(self):
            self.status_code = status_code
            self.text = "" if status_code < 400 else "fake-error-body"

        def iter_content(self, chunk_size=8192):
            yield body_bytes

        def raise_for_status(self):
            if self.status_code >= 400:
                raise tts.requests.HTTPError(f"{self.status_code}")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_post(url, *, json=None, headers=None, stream=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["stream"] = stream
        captured["timeout"] = timeout
        return _FakeResponse()

    return fake_post, captured


# ---------------------------------------------------------------------------
# grok_speak_chunk: request shape + endpoint
# ---------------------------------------------------------------------------

def test_grok_speak_chunk_posts_to_xai_endpoint(tmp_path: Path, monkeypatch):
    fake_post, captured = _make_fake_post()
    monkeypatch.setattr(tts.requests, "post", fake_post)

    out = tmp_path / "out.mp3"
    tts.grok_speak_chunk(
        "Привет, как дела?",
        voice_id="0b875ae2",
        out_path=out,
        api_key="secret-xai-key",
        language_code="ru",
    )

    assert captured["url"] == "https://api.x.ai/v1/tts"
    assert captured["headers"]["Authorization"] == "Bearer secret-xai-key"
    assert captured["headers"]["Content-Type"] == "application/json"
    body = captured["json"]
    assert body["voice_id"] == "0b875ae2"
    assert body["language"] == "ru"
    assert body["text"] == "Привет, как дела?"
    # Default output_format is WAV/48 kHz (May 2026 audio-quality upgrade);
    # text_normalization is on by default so Grok handles numbers/dates/
    # currency server-side.
    assert body["output_format"]["codec"] == "wav"
    assert body["output_format"]["sample_rate"] == 48000
    assert body["text_normalization"] is True
    # Audio bytes were written to disk.
    assert out.exists()
    assert out.read_bytes() == b"\xff\xfb\x90"


def test_grok_speak_chunk_request_overrides(tmp_path: Path, monkeypatch):
    """Caller can override output codec/sample_rate and text_normalization
    if a future show needs MP3 streaming or wants raw text passthrough."""
    fake_post, captured = _make_fake_post()
    monkeypatch.setattr(tts.requests, "post", fake_post)

    tts.grok_speak_chunk(
        "Hello",
        voice_id="kdif6sqjcyiq",
        out_path=tmp_path / "o.wav",
        api_key="k",
        output_codec="mp3",
        output_sample_rate=24000,
        text_normalization=False,
    )
    body = captured["json"]
    assert body["output_format"] == {"codec": "mp3", "sample_rate": 24000}
    assert body["text_normalization"] is False


def test_grok_speak_chunk_defaults_language_to_auto(tmp_path: Path, monkeypatch):
    fake_post, captured = _make_fake_post()
    monkeypatch.setattr(tts.requests, "post", fake_post)

    tts.grok_speak_chunk(
        "Hello world",
        voice_id="eve",
        out_path=tmp_path / "o.mp3",
        api_key="k",
        language_code="",
    )
    assert captured["json"]["language"] == "auto"


def test_grok_speak_chunk_rejects_empty_text(tmp_path: Path):
    with pytest.raises(ValueError, match="empty"):
        tts.grok_speak_chunk(
            "   ",
            voice_id="0b875ae2",
            out_path=tmp_path / "o.mp3",
            api_key="k",
        )


def test_grok_speak_chunk_rejects_oversize_text(tmp_path: Path):
    """Caller is responsible for chunking under the 15k cap."""
    with pytest.raises(ValueError, match="exceeds Grok's"):
        tts.grok_speak_chunk(
            "x" * 20000,
            voice_id="0b875ae2",
            out_path=tmp_path / "o.mp3",
            api_key="k",
        )


def test_grok_speak_chunk_raises_on_401(tmp_path: Path, monkeypatch):
    fake_post, _ = _make_fake_post(status_code=401)
    monkeypatch.setattr(tts.requests, "post", fake_post)

    with pytest.raises(tts.GrokTTSClientError) as exc_info:
        tts.grok_speak_chunk(
            "test", voice_id="x", out_path=tmp_path / "o.mp3", api_key="bad",
        )
    assert exc_info.value.status_code == 401


def test_grok_speak_chunk_raises_on_4xx(tmp_path: Path, monkeypatch):
    fake_post, _ = _make_fake_post(status_code=422)
    monkeypatch.setattr(tts.requests, "post", fake_post)

    with pytest.raises(tts.GrokTTSClientError):
        tts.grok_speak_chunk(
            "test", voice_id="x", out_path=tmp_path / "o.mp3", api_key="k",
        )


# ---------------------------------------------------------------------------
# synthesize() dispatch on provider
# ---------------------------------------------------------------------------

def test_synthesize_dispatches_to_grok_when_provider_grok(tmp_path: Path, monkeypatch):
    """`synthesize(provider='grok')` must NOT call the ElevenLabs path."""
    eleven_called = MagicMock()
    grok_called = MagicMock()

    monkeypatch.setattr(tts, "speak", eleven_called)
    monkeypatch.setattr(tts, "_speak_with_grok", grok_called)

    out = tmp_path / "out.mp3"
    tts.synthesize(
        "Привет, мир.",
        voice_id="0b875ae2",
        output_path=out,
        api_key="xai-key",
        provider="grok",
        language_code="ru",
    )

    grok_called.assert_called_once()
    eleven_called.assert_not_called()
    # Provider got the right kwargs; no ElevenLabs voice settings leaked through.
    _args, kwargs = grok_called.call_args
    assert kwargs["api_key"] == "xai-key"
    assert kwargs["language_code"] == "ru"
    assert "stability" not in kwargs
    assert "similarity_boost" not in kwargs
    assert "style" not in kwargs
    assert "model_id" not in kwargs


def test_synthesize_defaults_to_elevenlabs(tmp_path: Path, monkeypatch):
    """No `provider` arg → ElevenLabs path runs (no behaviour change for English shows)."""
    eleven_called = MagicMock()
    grok_called = MagicMock()

    monkeypatch.setattr(tts, "speak", eleven_called)
    monkeypatch.setattr(tts, "_speak_with_grok", grok_called)

    tts.synthesize(
        "Hello",
        voice_id="dTrBzPvD2GpAqkk1MUzA",
        output_path=tmp_path / "o.mp3",
        api_key="elevenlabs-key",
    )

    eleven_called.assert_called_once()
    grok_called.assert_not_called()


def test_synthesize_grok_translates_empty_language_to_auto(tmp_path: Path, monkeypatch):
    grok_called = MagicMock()
    monkeypatch.setattr(tts, "_speak_with_grok", grok_called)

    tts.synthesize(
        "Привет",
        voice_id="0b875ae2",
        output_path=tmp_path / "o.mp3",
        api_key="k",
        provider="grok",
        language_code="",
    )

    _, kwargs = grok_called.call_args
    assert kwargs["language_code"] == "auto"


# ---------------------------------------------------------------------------
# synthesize_sections() dispatch
# ---------------------------------------------------------------------------

def test_synthesize_sections_dispatches_to_grok_path(tmp_path: Path, monkeypatch):
    grok_called = MagicMock()
    eleven_called = MagicMock()
    monkeypatch.setattr(tts, "_speak_with_grok", grok_called)
    monkeypatch.setattr(tts, "speak", eleven_called)

    tts.synthesize_sections(
        ["Привет.", "Как дела?"],
        voice_id="0b875ae2",
        output_dir=tmp_path,
        api_key="k",
        provider="grok",
        language_code="ru",
    )

    assert grok_called.call_count == 2  # one per section
    eleven_called.assert_not_called()


# ---------------------------------------------------------------------------
# Pricing — Grok TTS is in the per-provider map, ~36× cheaper than ElevenLabs
# ---------------------------------------------------------------------------

def test_grok_tts_pricing_is_per_provider_map():
    assert "grok" in TTS_PROVIDER_PRICING
    assert TTS_PROVIDER_PRICING["grok"] == GROK_TTS_COST_PER_1K_CHARS


def test_grok_tts_is_substantially_cheaper_than_elevenlabs():
    """Whole point of the migration — Grok must be at least 10× cheaper."""
    el = TTS_PROVIDER_PRICING["elevenlabs"]
    grok = TTS_PROVIDER_PRICING["grok"]
    assert grok < el / 10, (
        f"Grok TTS at ${grok}/1K vs ElevenLabs at ${el}/1K — "
        "expected at least 10× savings; got "
        f"{el / grok:.1f}× ratio."
    )


def test_save_usage_uses_grok_rate_when_provider_grok(tmp_path: Path):
    """End-to-end: tracker recorded provider=grok → cost computed at Grok rate."""
    tracker = create_tracker("Финансы Просто", 30)
    record_tts_usage(tracker, characters=10_000, provider="grok")
    save_usage(tracker, tmp_path)

    tts_block = tracker["services"]["tts_api"]
    assert tts_block["provider"] == "grok"
    expected = (10_000 / 1000) * GROK_TTS_COST_PER_1K_CHARS
    assert tts_block["estimated_cost_usd"] == pytest.approx(expected)
    # Sanity: this is much less than what ElevenLabs would have charged.
    elevenlabs_equiv = (10_000 / 1000) * TTS_PROVIDER_PRICING["elevenlabs"]
    assert tts_block["estimated_cost_usd"] < elevenlabs_equiv / 10


def test_save_usage_uses_elevenlabs_rate_when_provider_elevenlabs(tmp_path: Path):
    """Tesla Shorts Time stays on ElevenLabs and is charged at that rate."""
    tracker = create_tracker("Tesla Shorts Time", 460)
    record_tts_usage(tracker, characters=10_000, provider="elevenlabs")
    save_usage(tracker, tmp_path)

    tts_block = tracker["services"]["tts_api"]
    assert tts_block["provider"] == "elevenlabs"
    expected = (10_000 / 1000) * TTS_PROVIDER_PRICING["elevenlabs"]
    assert tts_block["estimated_cost_usd"] == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Show-YAML coverage — drift guards for the May 2026 TTS layout
# ---------------------------------------------------------------------------

def test_russian_shows_use_grok_tts():
    """Both Russian shows must be on Grok TTS with the Olya custom voice ID.

    This guards against accidental rollback to the old ElevenLabs voice
    (`gedzfqL7OGdPbwm0ynTP`), which was ~36× more expensive per character.
    """
    import yaml as _yaml
    shows_dir = Path(__file__).resolve().parent.parent / "shows"
    for slug in ("finansy_prosto", "privet_russian"):
        data = _yaml.safe_load(
            (shows_dir / f"{slug}.yaml").read_text(encoding="utf-8")
        ) or {}
        tts_block = data.get("tts") or {}
        assert tts_block.get("provider") == "grok", (
            f"{slug}.yaml: tts.provider must be 'grok' "
            f"(got {tts_block.get('provider')!r})"
        )
        assert tts_block.get("voice_id") == "0b875ae2", (
            f"{slug}.yaml: tts.voice_id must be the Olya Grok ID 0b875ae2 "
            f"(got {tts_block.get('voice_id')!r})"
        )
        assert tts_block.get("language_code") == "ru", (
            f"{slug}.yaml: tts.language_code must be 'ru' "
            f"(got {tts_block.get('language_code')!r})"
        )


def test_english_shows_resolve_to_custom_voice():
    """Every English show — including Tesla Shorts Time — must resolve to
    Grok TTS with the operator's custom-trained voice ``kdif6sqjcyiq``
    after deep-merging _defaults.yaml.

    This is the result of the May 2026 full-network migration: a single
    consistent host identity across every English show. Inheritance is
    the contract here — per-show YAMLs intentionally leave the ``tts:``
    block empty so the network default carries them. An override silently
    puts a show on a different voice and breaks listener-side continuity.
    """
    from engine.config import load_config
    shows_dir = Path(__file__).resolve().parent.parent / "shows"
    english_grok_shows = (
        "tesla",  # was the lone ElevenLabs holdout; migrated May 2026
        "omni_view",
        "fascinating_frontiers",
        "planetterrian",
        "env_intel",
        "models_agents",
        "models_agents_beginners",
        "modern_investing",
        "unintended_consequences",  # added May 2026 — narrative show
    )
    for slug in english_grok_shows:
        cfg = load_config(shows_dir / f"{slug}.yaml")
        assert cfg.tts.provider == "grok", (
            f"{slug}.yaml: post-merge tts.provider must be 'grok' "
            f"(got {cfg.tts.provider!r}); check shows/_defaults.yaml didn't "
            "regress and the show YAML didn't add an override."
        )
        assert cfg.tts.voice_id == "kdif6sqjcyiq", (
            f"{slug}.yaml: post-merge tts.voice_id must be 'kdif6sqjcyiq' "
            f"(got {cfg.tts.voice_id!r}); the network adopted the operator's "
            "custom-trained voice for every English show in May 2026 — "
            "per-show overrides need a documented reason."
        )
        assert cfg.tts.language_code == "en", (
            f"{slug}.yaml: post-merge tts.language_code must be 'en' "
            f"(got {cfg.tts.language_code!r})"
        )


def test_no_show_uses_elevenlabs_in_production():
    """No production show should be configured for ElevenLabs after the
    May 2026 full-network migration. The legacy fields in
    `shows/_defaults.yaml` exist only for emergency rollback — if any
    show silently falls back to provider=elevenlabs the cost
    (~$150/M chars) and the voice mismatch would surprise listeners.
    """
    from engine.config import load_config
    shows_dir = Path(__file__).resolve().parent.parent / "shows"
    all_shows = (
        "tesla", "omni_view", "fascinating_frontiers", "planetterrian",
        "env_intel", "models_agents", "models_agents_beginners",
        "modern_investing", "finansy_prosto", "privet_russian",
        "unintended_consequences",
    )
    for slug in all_shows:
        cfg = load_config(shows_dir / f"{slug}.yaml")
        assert cfg.tts.provider != "elevenlabs", (
            f"{slug}.yaml resolves to provider='elevenlabs' — emergency "
            "rollback flip detected. Either (a) the operator manually "
            "rolled back this show and forgot to update this guard, or "
            "(b) shows/_defaults.yaml regressed."
        )


# ---------------------------------------------------------------------------
# Spec v2 follow-up: bumped timeout + section-fallback resilience
# ---------------------------------------------------------------------------

def test_grok_tts_timeout_default_is_300_seconds():
    """The default request timeout is 300s — bumped from 120 in May 2026
    after a Grok-side slow response burned through tenacity retries and
    killed a 20-minute Tesla run."""
    from engine.tts import GROK_TTS_TIMEOUT_SECONDS, grok_speak_chunk
    import inspect
    assert GROK_TTS_TIMEOUT_SECONDS == 300
    sig = inspect.signature(grok_speak_chunk)
    assert sig.parameters["timeout"].default == GROK_TTS_TIMEOUT_SECONDS


def test_synthesize_sections_falls_back_on_timeout(tmp_path: Path, monkeypatch):
    """If a section TTS call raises (e.g. tenacity exhausted retries on
    a Grok read timeout), the function falls back to single-pass
    synthesis of the joined text instead of failing the whole episode.
    """
    from engine import tts as _tts

    calls = {"per_section": 0, "fallback": 0}

    def _fake_speak_with_grok(text, voice_id, filename, **kwargs):
        # First call (section #1) succeeds, second (section #2) times out,
        # then the fallback succeeds.
        if calls["per_section"] == 0 and calls["fallback"] == 0:
            calls["per_section"] += 1
            Path(filename).write_bytes(b"\xff\xfb\x90")
            return
        if calls["per_section"] == 1 and calls["fallback"] == 0:
            calls["per_section"] += 1
            raise RuntimeError("simulated read timeout after retries")
        # Fallback call.
        calls["fallback"] += 1
        Path(filename).write_bytes(b"\xff\xfb\x90")

    monkeypatch.setattr(_tts, "_speak_with_grok", _fake_speak_with_grok)

    out_dir = tmp_path / "sections"
    result = _tts.synthesize_sections(
        ["Section A text.", "Section B text.", "Section C text."],
        voice_id="kdif6sqjcyiq",
        output_dir=out_dir,
        api_key="k",
        provider="grok",
        section_prefix="ep001",
    )

    # Section #1 was rendered, section #2 raised, fallback ran once.
    assert calls["per_section"] == 2
    assert calls["fallback"] == 1
    # Result contains exactly one file (the fallback) — caller's
    # `concatenate_with_stings` handles 1-element lists by passing
    # the file through with no transition stings.
    assert len(result) == 1
    assert result[0].name.endswith("_fallback.mp3")
    assert result[0].exists()


def test_synthesize_sections_succeeds_when_all_sections_synth(tmp_path: Path, monkeypatch):
    """Happy path: every section succeeds, no fallback needed."""
    from engine import tts as _tts

    def _fake_speak_with_grok(text, voice_id, filename, **kwargs):
        Path(filename).write_bytes(b"\xff\xfb\x90")

    monkeypatch.setattr(_tts, "_speak_with_grok", _fake_speak_with_grok)

    out_dir = tmp_path / "sections"
    result = _tts.synthesize_sections(
        ["A", "B", "C"],
        voice_id="kdif6sqjcyiq",
        output_dir=out_dir,
        api_key="k",
        provider="grok",
        section_prefix="ep002",
    )

    assert len(result) == 3
    assert all(p.exists() for p in result)
    # No fallback file generated.
    assert not (out_dir / "ep002_fallback.mp3").exists()


# ---------------------------------------------------------------------------
# Speech-tag wrap — <fast><build-intensity>...</...></...>
# ---------------------------------------------------------------------------

def test_grok_path_wraps_text_with_speech_tags(tmp_path: Path, monkeypatch):
    """When ``speech_wrap_open`` / ``close`` are set, every chunk sent
    to ``grok_speak_chunk`` must arrive wrapped. The kdif6sqjcyiq clone
    A/B'd cleaner with ``<fast><build-intensity>`` than bare text — this
    drift guard catches any regression that drops the wrap."""
    captured_texts: list = []

    def fake_chunk(text, *args, **kwargs):
        captured_texts.append(text)
        # Touch the output path so the surrounding pipeline doesn't
        # bail looking for a non-existent file.
        out = args[1] if len(args) > 1 else kwargs.get("out_path")
        if out:
            Path(out).write_bytes(b"\xff\xfb\x90")

    monkeypatch.setattr(tts, "grok_speak_chunk", fake_chunk)
    # Stub ffmpeg so the encode steps don't actually run.
    monkeypatch.setattr(tts.subprocess, "run", MagicMock())

    tts.synthesize(
        "Tesla just opened a new Supercharger corridor.",
        voice_id="kdif6sqjcyiq",
        output_path=tmp_path / "o.mp3",
        api_key="k",
        provider="grok",
        language_code="en",
        speech_wrap_open="<fast><build-intensity>",
        speech_wrap_close="</build-intensity></fast>",
    )

    assert captured_texts, "grok_speak_chunk was never called"
    sent = captured_texts[0]
    assert sent.startswith("<fast><build-intensity>"), sent
    assert sent.endswith("</build-intensity></fast>"), sent
    assert "Tesla just opened a new Supercharger corridor." in sent


def test_grok_path_wrap_is_empty_string_safe(tmp_path: Path, monkeypatch):
    """No wrap configured = bare text, byte-identical to pre-wrap behavior."""
    captured_texts: list = []

    def fake_chunk(text, *args, **kwargs):
        captured_texts.append(text)
        out = args[1] if len(args) > 1 else kwargs.get("out_path")
        if out:
            Path(out).write_bytes(b"\xff\xfb\x90")

    monkeypatch.setattr(tts, "grok_speak_chunk", fake_chunk)
    monkeypatch.setattr(tts.subprocess, "run", MagicMock())

    tts.synthesize(
        "Bare sentence.",
        voice_id="kdif6sqjcyiq",
        output_path=tmp_path / "o.mp3",
        api_key="k",
        provider="grok",
        # No speech_wrap_* args at all (defaults to "").
    )

    sent = captured_texts[0]
    assert "<fast>" not in sent
    assert "<build-intensity>" not in sent
    assert sent == "Bare sentence."


def test_default_tts_config_has_fast_build_intensity_wrap():
    """The network default is ``<fast><build-intensity>...</...></...>`` — the
    operator's A/B verdict on cloned voices. Drift guard so a quiet
    config change doesn't silently revert this for every show."""
    from engine.config import TTSConfig
    cfg = TTSConfig()
    assert cfg.speech_wrap_open == "<fast><build-intensity>"
    assert cfg.speech_wrap_close == "</build-intensity></fast>"


def test_synthesize_sections_passes_wrap_through(tmp_path: Path, monkeypatch):
    """``synthesize_sections`` is the multi-section entry point used by
    shows that emit transition stings between sections. The wrap kwargs
    must reach ``_speak_with_grok`` for each section."""
    grok_called = MagicMock()
    monkeypatch.setattr(tts, "_speak_with_grok", grok_called)

    tts.synthesize_sections(
        ["First section.", "Second section."],
        voice_id="kdif6sqjcyiq",
        output_dir=tmp_path,
        api_key="k",
        provider="grok",
        language_code="en",
        speech_wrap_open="<fast><build-intensity>",
        speech_wrap_close="</build-intensity></fast>",
    )

    assert grok_called.call_count == 2
    for call in grok_called.call_args_list:
        _, kwargs = call
        assert kwargs["speech_wrap_open"] == "<fast><build-intensity>"
        assert kwargs["speech_wrap_close"] == "</build-intensity></fast>"
