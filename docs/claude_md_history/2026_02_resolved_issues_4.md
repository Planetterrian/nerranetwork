# Known Landmines — Resolved Issues 4–13 (Feb–May 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

4. **TST/OV output dirs fixed** — `shows/tesla.yaml` and `shows/omni_view.yaml`
   now use `digests/tesla_shorts_time/` and `digests/omni_view/` for
   `output_dir` and `audio_subdir`, matching FF/PT/EI. Legacy scripts already
   pointed to subdirectories. Audio URL construction in both legacy scripts
   also fixed.
5. **Legacy `digests/digests/` path bug cleaned up** — nested directory deleted,
   RSS references removed, SETUP.md corrected. Defensive scanning code remains
   in `tesla_shorts_time.py` in case any legacy files resurface.
6. **58 duplicate `_formatted.md` files deleted** — removed in commit
   `0c10b7f`, code no longer generates them.
7. **`NEWSAPI_KEY` dead secret removed** — not present in active workflow
   (`run-show.yml`), not used in any code. Integration test
   `test_no_newsapi_in_active_workflow()` guards against re-introduction.
8. **Feature flags consistent across shows** — all four legacy scripts
   (TST, FF, PT, OV) support env-overridable `TEST_MODE`, `ENABLE_X_POSTING`,
   `ENABLE_PODCAST`, and `ENABLE_GITHUB_SUMMARIES`. `run_show.py` uses
   CLI flags (`--test`, `--skip-x`, `--skip-podcast`) instead.
9. **ElevenLabs tuning baseline lives in `shows/_defaults.yaml`** — the
   canonical network baseline is now whatever
   [`shows/_defaults.yaml`](shows/_defaults.yaml) declares (today:
   `stability=0.5`, `similarity_boost=0.75`, `style=0.0`, English voice
   `dTrBzPvD2GpAqkk1MUzA`, Russian voice `gedzfqL7OGdPbwm0ynTP`). Per-show
   overrides are allowed; drift is tracked live in the management
   dashboard's *Voice settings consistency* table. Any show row flagged
   with a drift is either intentional (record the reason in the show's
   YAML as a comment) or a regression to investigate. Historical note:
   an earlier baseline had stability `0.65`, similarity boost `0.9`, and
   style `0.85`; that combination is no longer blessed and should not be
   reintroduced without updating `_defaults.yaml`.
10. **Early episodes deleted** — first 20 Tesla, 10 FF, 10 PT, 10 OV episodes
    removed (quality issues). RSS entries removed where applicable.
11. **All 10 shows on Grok TTS (May 2026, full-network migration)** —
    Chatterbox, Kokoro, and Fish Audio were trialled and removed.
    English shows (including Tesla Shorts Time as of the third migration
    wave) all use the operator's custom-trained voice `kdif6sqjcyiq`
    for a single consistent host identity. Russian shows use the
    custom Olya voice (`0b875ae2`). ElevenLabs is no longer used in
    production. Network cost: ~10× cheaper per character on Grok
    ($15/M per the xAI models page, read 2026-10-02 — an earlier version
    of this line said $4.20/M, the promo-era figure; `engine/tracking.py`
    was right all along — vs $150/M for ElevenLabs Flash). Reuses `GROK_API_KEY` /
    `XAI_API_KEY` — no new secret. See landmines #16 and #17.
12. **Summaries JSONs moved** — all summaries live in per-show subdirectories
    (`digests/<show>/summaries_*.json`), not at the `digests/` top level.
13. **LLM default migrated to `grok-4.3` (May 2026)** — released 2026-04-30,
    always-on reasoning, $1.25/$2.50 per 1M tokens (~55% cheaper per
    episode than the previous `grok-4.20-*` defaults). Network default,
    synth model, Tesla / Modern Investing per-show overrides, and the
    tool-use path (`digests/xai_grok.py`, X / web search via the
    Responses API — confirmed grok-4.3 supports `x_search` and
    `web_search` built-in tools) all now run on `grok-4.3`. Refusal
    fallback stays on `grok-4.20-reasoning` so refusals genuinely
    switch model snapshot rather than retrying the same primary.
    Pricing for the historical 4.20 family is retained in
    `engine/tracking.py` so old `credit_usage_*.json` files still cost
    out correctly.
