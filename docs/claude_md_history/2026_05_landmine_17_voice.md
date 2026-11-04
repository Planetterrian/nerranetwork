# Landmine 17 — Full-network voice migration + broadcast-quality audio pipeline (May 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

17. **Full-network voice migration + broadcast-quality audio pipeline
    (third TTS wave, May 2026)** — Tesla Shorts Time joined the rest of
    the network on Grok TTS. Every English show now inherits the
    operator's custom-trained voice `kdif6sqjcyiq` from
    [`shows/_defaults.yaml`](shows/_defaults.yaml); the previous `sal`
    built-in voice was retired and TST's ElevenLabs override
    (`provider: elevenlabs`, voice `dTrBzPvD2GpAqkk1MUzA`) was removed.

    Same migration shipped a broadcast-quality audio pipeline. Cumulative
    changes to the per-episode signal flow:

    - **Grok TTS request:** now requests **WAV at 48 kHz** with
      `text_normalization: true` (`engine/tts.py:grok_speak_chunk`).
      Previously MP3 at 24 kHz with no normalization. The pipeline
      crossfades chunks in WAV and only encodes to MP3 once at the very
      end (one lossy pass instead of two). Server-side text normalization
      handles dates, currencies, and ordinary numbers — the
      `pronunciation_map.yaml` layer remains for proper-noun / acronym
      overrides.
    - **Voice EQ chain** (`engine/audio.py:_voice_norm_full_cmd`) —
      highpass 80 / lowpass 15k / adeclick+afftdn / loudnorm -18 /
      acompressor 4:1 / alimiter. **This entry used to claim the chain
      "gained a 6.5 kHz dip (`equalizer=f=6500:t=q:w=1.5:g=-3`) for
      gentle de-essing". It never did** — `git log -S "6500"` on
      `engine/audio.py` returns nothing, the string has never existed in
      the file. Corrected 2026-07-30. Do not "restore" it: there is
      nothing to restore.
      **De-essing was then measured and deliberately declined.** With a
      live key, 2:34 of real Tesla Ep557 synthesized on the production
      voice and pushed through the chain shows the midrange flat
      (-0.1 dB) while the sibilance band (5.5-8.5 kHz) gains **+5.1 dB**
      and air (8.5-16 kHz) **+5.0 dB** — the 4:1 broadband compressor
      lifts consonants faster than vowels. Four variants (no de-ess /
      static -3 dB / static -5 dB / ffmpeg `deesser`) were rendered and
      **the operator listened: all four sound the same on this voice.**
      So the +5 dB is a measurement, not a defect, and the network ships
      the chain unchanged — adding a stage that buys no audible benefit
      but alters every episode on 15 shows is the landmine-#17 shape.
      Re-open only with listening evidence, not spectra.
    - **Final mix** (`engine/audio.py:_final_mix_cmd`) replaced the
      simple `amix` with sidechain-ducked music + EBU R128 loudnorm
      to **-16 LUFS** (Apple Podcasts / Spotify spec). Music
      automatically pulls down 8 dB when voice is present and rises
      smoothly when voice pauses. The fixed-curve `mix_with_music`
      music timeline still runs upstream to control intro / overlap /
      fadeout / outro volumes; the sidechain ducking adds the
      moment-to-moment dynamic response that makes voice + music feel
      cinematic instead of mechanical.
    - **Final encode** bumped from CBR 192 kbps to VBR `-q:a 0`
      (~245 kbps) for archival-quality spoken-word + music. ~6.5 MB
      per 30-min episode (was ~5 MB).
    - **Speech tags** are now allowed in podcast prompts (every
      `shows/prompts/*_podcast.txt` carries a `DELIVERY` block).
      Allowed: `[breath]`, `[pause]`, `[long-pause]`,
      `<emphasis>...</emphasis>`. Banned: every other Grok tag
      (`[laugh]` / `<whisper>` / `<slow>` / etc. — they sound
      performative). The TTS path keeps tags; every non-TTS consumer
      runs through `engine.utils.strip_speech_tags()` before publishing
      so blog markdown, RSS show notes, X teaser, and YouTube
      descriptions never see them.
    - **Drift guards:** `tests/test_tts_grok.py` now has
      `test_english_shows_resolve_to_custom_voice` (every English show
      including Tesla resolves to `kdif6sqjcyiq`),
      `test_no_show_uses_elevenlabs_in_production` (catches accidental
      rollback flips), and `test_russian_shows_use_grok_tts` (Olya
      voice unchanged).

    `ELEVENLABS_API_KEY` is **kept** in GitHub Secrets / `.env` for
    emergency rollback even though no show currently needs it. The
    legacy ElevenLabs settings in `_defaults.yaml` (model, stability,
    similarity_boost, style, etc.) are also preserved — harmless under
    `provider=grok` and a one-line YAML flip back to ElevenLabs if
    Grok TTS has an outage.

    **May 4 2026 update — speech-tag wrap simplified.** The chunk-
    send wrap was originally `<fast><build-intensity>...</build-intensity></fast>`
    (PR #293). Whisper transcripts of UC Ep001 ("Build intensity." at
    line 3 + "build intended to dig" at line 127) and Tesla Ep461 (line
    112) showed Grok occasionally **speaking** "build intensity" out
    loud instead of consuming the tag — `<build-intensity>` was never
    in Grok's documented tag list. Wrap simplified to `<fast>...</fast>`.

    **May 11 2026 update — chunk wrap dropped entirely, programmatic
    `<emphasis>` injection added.** M&A Ep045 transcript caught Grok
    voicing the opening `<fast>` aloud as "Fast." at section-TTS
    boundaries (twice — at "in its latest release. Fast. The updates…"
    and "make sense for their workloads. Fast. Okay, let's pop the
    hood…"). Verified against xAI docs: `<fast>` is **not** on Grok's
    documented tag list (only `[breath]`, `[pause]`, `[long-pause]`,
    `<emphasis>`, `<whisper>`, `<slow>`, `<soft>` are). The energy
    lift `<fast>` was supposed to provide was paid for in occasional
    audible tag leakage at every chunk boundary multi-section TTS
    creates. Wrap dropped to empty strings in both `engine.config`
    and `shows/_defaults.yaml`.

    Programmatic `<emphasis>` injection was added in the same PR
    (`engine/prosody.py:inject_prosody_tags()` wrapping currency /
    percentages / cashtags at script-save time) — and **paused the
    same day** (see below).

    The DELIVERY prompt block was also dropped from all 12 podcast
    prompts (`shows/prompts/*_podcast.txt`); 56 recent `_tts.txt`
    files showed the LLM was ignoring it (only 10 had any tags at
    all, never reliably). The block was paying prompt-token cost
    for no measurable audio benefit.

    Defense-in-depth: `engine.utils.strip_speech_tags()` is wired
    into RSS show notes (`engine/publisher.py:_markdown_to_rss_html`),
    newsletter body (`engine/newsletter.py:send_show_newsletter`),
    and YouTube metadata (`engine/video_metadata.py:_strip_markdown`)
    so any speech tag that enters the digest body is scrubbed before
    subscribers / readers / YouTube see it. Drift guard
    `test_default_tts_config_has_no_chunk_wrap` blocks accidental
    re-introduction of the chunk wrap.

    **May 11 2026 update (later same day) — pause all TTS
    modifications, run raw Grok TTS.** Operator A/B-listened to
    Planetterrian Ep060 and Fascinating Frontiers (with the phonetic
    respellings for "Planetterrian", "tissue", "neurodegenerative"
    active) against raw audio and concluded **every phonetic
    respelling sounded worse than the original word** on the custom
    voice `kdif6sqjcyiq`. Same call for the just-shipped programmatic
    `<emphasis>` injector — adding any modification risked regressing
    a voice that already handles these tokens naturally.

    Pause decision:
    - `engine/prosody.py` and its tests **deleted**. The
      `inject_prosody_tags()` call in `run_show.py` reverted.
    - Phonetic respellings (`tissue`/`Tissue`/`tissues`/`Tissues`,
      `neurodegenerative` and 3 case/inflection variants) **removed**
      from `shows/pronunciation_map.yaml`. The Planetterrian
      WORD_PRONUNCIATIONS entry was already removed in PR #355.
    - **Kept**: letter-by-letter acronym expansions in
      `shows/pronunciation_map.yaml` (`TSLA` → `T S L A`, `LLM` → `L
      L M`, `TFSA` / `RRSP` / `FHSA` / `RESP`, `HW4` / `HW5` / `AI5`,
      `MCP`). Those are NOT phonetic guesses — they're literal
      letter-spellings, and the operator-verified failure mode
      without them is Grok saying "lum" / "tezz-luh".
    - **Kept**: `<fast>` chunk-wrap removal + DELIVERY-block removal
      + `strip_speech_tags()` defense (those are removals of broken
      modifications + a no-op safety net, not modifications).

    Re-introduce ANY phonetic respelling or programmatic tag
    injection ONLY with A/B listen-test evidence on the custom voice
    that the modified audio is measurably better than raw on at
    least 3 different show contexts. Theory-driven "this should
    sound better" changes have a 100% regression rate on this voice
    so far (Planetterrian, tissue, neurodegenerative, `<fast>` wrap,
    `<build-intensity>` wrap — every one made it worse).

    **May 13 2026 update — `<fast>` wrap re-enabled via single-call
    synthesis.** Operator listened to the May 13 episodes (post-#365
    editorializing reduction + #366 audio retune + #367 streamline)
    and asked for whole-script `<fast>` energy on every podcast
    ("Option B for all podcasts please"). The historical chunk-wrap
    leak (M&A Ep045 voicing "Fast." at section-TTS boundaries) was
    a *multi-call* problem: section-TTS + chunked synthesis meant
    every chunk got its own `<fast>...</fast>` wrap as an
    independent Grok API call, and Grok occasionally voiced the
    opening tag aloud at the boundary between calls.

    Leak-safe implementation (the only safe path):
    - Network default `shows/_defaults.yaml`: `speech_wrap_open:
      "<fast>"`, `speech_wrap_close: "</fast>"`, `use_section_tts:
      false`, `max_chars: 14000`.
    - The four fields are a *coupled set* — flipping any one
      without the others re-introduces the leak.
    - `run_show.py:1714` gates section-TTS on `config.tts.use_section_tts`
      so the network-wide flip is one YAML field.
    - `engine/tts.py:_speak_with_grok` has a May 13 safety guard:
      if a script overflows `max_chars` and splits into multiple
      chunks, it DROPS the wrap (with a loud warning) rather than
      apply it per-chunk. Episode loses the energy lift but ships
      clean audio.

    Trade-off: section-TTS off means **no transition stings between
    chapter markers**. Chapter markers themselves still work in
    podcast apps (Apple, Spotify, Pocket Casts) because they come
    from `chapters.json` not from section-TTS. The brief musical
    stings between chapters are gone — most listeners won't notice;
    one-line revert (`use_section_tts: true` + drop the wrap) if
    desired.

    Drift guards in `tests/test_tts_grok.py`:
    - `test_default_tts_config_dataclass_has_no_chunk_wrap` —
      dataclass default stays empty (backwards compat for callers
      that bypass YAML).
    - `test_network_default_has_fast_wrap_and_single_call` — pins
      the four coupled fields on the loaded Tesla YAML so a partial
      revert (e.g. re-enabling section-TTS without dropping the
      wrap) fails CI.
    - `test_speak_with_grok_drops_wrap_on_multi_chunk` — verifies
      the safety guard fires when a script overflows.
    - `test_speak_with_grok_keeps_wrap_on_single_chunk` — verifies
      the happy path applies the wrap as expected.

    The policy above (no theory-driven tag changes) still stands
    for any FUTURE additions. The May 13 `<fast>` re-enable was an
    *operator override* with explicit awareness of the historical
    risk; it ships as a single coherent infrastructure change
    (single-call synthesis) rather than as a tag-injection retry.
