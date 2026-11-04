# Vancouver Daily News / Collingwood Weekly — the grok-4.7 cohort (Sep 23–24 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

- **Vancouver Daily News / Collingwood Weekly** (Sep 2026, pre-launch) — the
  first run_show shows with an AI host: `host_kind: ai`, Mira on `ara`, NO
  speech wrap (Nerra Daily's Mira has none). Roads and weather arrive as
  sourced hook ARTICLES from `engine/local_conditions.py` (DriveBC boxed to
  Metro Vancouver, Ontario 511, Environment Canada's `/rss/weather/` feed);
  a data-less day is one sentence. **Every new show runs grok-4.7** on its
  writing stages and includes `_shared/interesting_first.txt` (operator
  brief 2026-09-23; plan §9b; the established shows stay on grok-4.3).
  Guards: `tests/test_new_shows_phase2_2026_09_23.py`. **grok-4.7 had
  never completed a call here** (Vancouver/Collingwood Ep1 died in the
  digest stage, 2026-09-23): a pinned model that fails the pre-flight ping
  or the digest call now switches the run to grok-4.3 and records
  `llm_model_pinned` / `llm_model_fallback` — read those before scoring
  the 4.7 experiment (`engine.generator.switch_to_network_default`).
  **Sep 24 2026 — 9 of the cohort's first 24 episodes fell back, and the
  fallback arm is the thin one** (0–3 claims and ~1 comma per 100 words
  against 8–25 claims on a completed 4.7 run): five dropped connections
  at ~260 s on a NON-STREAMING request, three full 600 s timeouts, one
  pre-flight ping run at default effort. Two of the drops hit the
  STRUCTURAL RETRY of a good 4.7 digest and the sticky switch replaced it
  with a 4.3 one (Top World Ep2: 1,548 → 908 words). Now, per
  `docs/model_upgrade_playbook.md` rule 7: the cohort's calls STREAM
  (`llm.stream`; a stall is silence past `NERRA_LLM_STREAM_IDLE_SECONDS`,
  the request timeout a wall between chunks; false = the exact old request
  on every established show), a pinned model gets ONE budget-gated
  same-model retry before the switch (`engine.generator._call_pinned`,
  `llm.pinned_model_retries`; a 5xx never retries), a retry of an existing
  digest runs with `allow_model_switch=False` and keeps the original
  (`PinnedModelUnavailable`), the ping sends the show's effort with two
  attempts on a pin, and Progress Watch is exempt from the overlap dedup on
  the six Mira desks. Dashboard `llm_pinned_fallback_share_7d` (baseline
  0.38) is the readout; `tests/test_grok47_resilience_2026_09_24.py`.
  **Same evening: Top World Ep2 had shipped eleven items and NO Source line**
  (that 4.3 structural retry cited nothing; the claims gate passed on two
  claims; the blog's Sources list was empty; the cohort guard went red on
  main). Repaired FROM THE RECORD by `scripts/backfill_sources_from_desks.py`
  — each item paired with the same story in the desks' digests of the day or
  the show's own content tracker (the URLs the run fetched), the named outlet
  must fit the URL's publisher, a tie is no match, id-only URLs resolve by
  page title with `--resolve`; never from memory — and `items_without_source`
  is on the eight Mira cohort shows too (`tests/test_top_world_sources_2026_09_24.py`).
