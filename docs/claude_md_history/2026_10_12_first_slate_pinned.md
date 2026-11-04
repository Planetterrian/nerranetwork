# Oct 12 2026 — the first slate on the pinned script arms

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Oct 12 2026 — the first slate on the pinned script arms** (review:
[`docs/reviews/slate_review_2026_10_12.md`](docs/reviews/slate_review_2026_10_12.md);
register `slate-2026-10-12`; guards `tests/test_slate_2026_10_12.py`). 28/28
published, every arm served its own model; the 4.6 scripts write (MIT 6%
digest-verbatim, Tesla 27%) and bring new defects. Rules that bind: **model
control tokens are stripped wherever model text comes back**
(`engine.utils.strip_model_special_tokens`; `<|eos|>` had aired on MIT
Ep198 and DP Pod), and the missing-closing guard drops a half-written
closing before it appends (`trim_partial_closing`). **The translation call
carries its own 600 s timeout with the SDK's retries off**
(`NERRA_TRANSLATION_TIMEOUT_SECONDS`; a silent call outlived the 120-min
multilingual job and cost SpaceX its FR/RU tracks). **A shared Source URL
is a duplicate only when the items share the story** (a roundup page carried
three stories on Africa & Middle East and two aired with no ledger entry).
**A hook titles a lead chapter only whole**; a bold `Title: Outlet` line may
run to 110 chars. **Network plugs read the SPEAKING show's cadence** — no
"family of daily podcasts" on a weekly show. **Привет, Русский! closes in
Russian** (operator-directed; `_RUSSIAN_CLOSING_SHOWS` — the lesson stays
English-taught). Offshore North's record follows the team's 8 Oct post: Scott
will not start the Route du Rhum, and a race EMIRA IV is not in is never her
next milestone. ⚠️ AUDIO: PR close, MAG 7 calendar anchor, Vancouver/
Collingwood Both Sides, UC/FPD one telling per fact, the shared teaser and
outlet-name lines, Prediction Markets' legal-step rule.
