# Per-show repositioning + per-episode blog title (Phase 4 partial, May 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Per-show repositioning + per-episode blog title (Phase 4 partial, May 2026)

Editorial repositioning of four shows (prompt + sourcing changes — they change
generated output; per landmine #17, A/B-listen and revert via git if needed):

- **Omni View → "Steel Man".** Digest + podcast now require presenting each
  competing position in its *strongest* form (best supporting reason first),
  not a caricature — the listener shouldn't be able to tell which side the show
  favours.
- **Финансы Просто → women-in-finance-in-Canada.** New high-priority INCLUDE
  category + "Объясни как подруге" topic steer toward spousal RRSP,
  maternity/parental EI, childcare deduction, FHSA, financial independence;
  two women-finance `web_search_queries` added.
- **Привет, Русский! → vocabulary-first.** Theme is chosen FIRST (rotating
  everyday domains); news is optional backdrop only — it's a language course,
  not a news show.
- **Environmental Intelligence → all-province + B2B brief.** Added a scannable
  "Compliance Brief" section (digest + podcast) for forwarding to a team, plus
  four provincial `web_search_queries` (ON/AB/QC/SK-MB-Atlantic) for true
  national coverage (provincial bodies lack reliable RSS, so search not feeds).

- **Per-episode blog title (Phase 2 carry-over).** `engine/blog.py` now uses
  the unique episode **hook** for the blog `<title>`/`<h1>`/BlogPosting
  headline whenever the extracted title is just the show name (digests lead
  with a `# <Show Name>` heading) — previously every post's title was identical,
  killing per-episode SEO. Falls back to the show name only when there's no
  hook. Drift guards: `tests/test_phase4_repositioning.py`.

- **Operator tooling:** `scripts/update_tesla_narrative.py` now takes `--slug`
  (default tesla) for any memory show.
