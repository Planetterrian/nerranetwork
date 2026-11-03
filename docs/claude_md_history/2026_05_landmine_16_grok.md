# Landmine 16 — TTS network default flipped to Grok TTS (May 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

16. **TTS network default flipped to Grok TTS (May 2026)** — staged in
    two PRs:
    - **First wave (Russian shows):** Финансы Просто and Привет,
      Русский! switched from ElevenLabs voice `gedzfqL7OGdPbwm0ynTP` to
      Grok TTS with the custom "Olya" voice `0b875ae2` (trained on the
      xAI Console). Validated with one live episode (PR Ep017,
      2026-05-02) before broader rollout.
    - **Second wave (English shows):** Network default in
      [`shows/_defaults.yaml`](shows/_defaults.yaml) flipped to
      `provider: grok`, `voice_id: sal` (Grok built-in named voice),
      `language_code: en`. The 7 non-Tesla English shows (Omni View,
      Fascinating Frontiers, Planetterrian, Env Intel, Models &
      Agents, Models & Agents for Beginners, Modern Investing) now
      inherit those defaults — their `tts:` blocks are intentionally
      empty (`{}`) to make inheritance the contract. Tesla Shorts Time
      explicitly overrides back to `provider: elevenlabs`,
      `voice_id: dTrBzPvD2GpAqkk1MUzA` because voice continuity on the
      network's largest show outweighs the cost delta.

    Implementation details: `engine/tts.py:synthesize()` dispatches on
    the `provider` kwarg; the Grok path posts to
    `https://api.x.ai/v1/tts` and reuses `GROK_API_KEY` /
    `XAI_API_KEY` (no new secret). ElevenLabs-only voice settings
    (`stability`, `similarity_boost`, `style`, `use_speaker_boost`,
    `model`, `speed`) live in [`shows/_defaults.yaml`](shows/_defaults.yaml)
    under a `# ---- Legacy ElevenLabs baseline ----` block — harmless
    when `provider=grok` (Grok path silently ignores them) and a tuned
    starting point if any show flips back to ElevenLabs. Pricing is
    per-provider in [`engine/tracking.py`](engine/tracking.py):
    `TTS_PROVIDER_PRICING`. Three drift guards in
    [`tests/test_tts_grok.py`](tests/test_tts_grok.py) block silent
    regressions: `test_russian_shows_use_grok_tts` (Olya voice on
    Russian shows), `test_english_shows_resolve_to_grok_sal` (sal voice
    on the 7 English shows after deep-merge), and
    `test_tesla_stays_on_elevenlabs` (TST voice continuity).
    `ELEVENLABS_API_KEY` is still required because Tesla uses it; if
    Tesla ever migrates, the env-var requirement disappears
    (`run_show.py:_validate_environment` already gates the check on
    `provider == "elevenlabs"`).
