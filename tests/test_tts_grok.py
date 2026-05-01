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
    # Audio bytes were written to disk.
    assert out.exists()
    assert out.read_bytes() == b"\xff\xfb\x90"


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


def test_save_usage_uses_elevenlabs_rate_when_provider_unspecified(tmp_path: Path):
    """Existing English shows: provider defaults to ElevenLabs, rate unchanged."""
    tracker = create_tracker("Tesla", 1)
    record_tts_usage(tracker, characters=10_000)  # no provider arg
    save_usage(tracker, tmp_path)

    tts_block = tracker["services"]["tts_api"]
    assert tts_block["provider"] == "elevenlabs"
    expected = (10_000 / 1000) * TTS_PROVIDER_PRICING["elevenlabs"]
    assert tts_block["estimated_cost_usd"] == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Russian show YAML coverage — guard against config drift
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
