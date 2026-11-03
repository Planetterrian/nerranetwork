# Provenance — Sep 8 2026: reviewer notes are a gate failure, not a formatting issue (WO-13)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Sep 8 2026 — reviewer notes are a gate failure, not a formatting
issue (WO-13).** Five fact-checker parentheticals shipped inside chapter
bodies of the Volume 1 builds — "(No public source found tying this
specific manifold redesign to the reusability program; keep the
engineering point …)" — and had to be cut from the store EPUBs by hand.
They came from research-fleet general-form rewrites applied to digests
(Aug 24/26), not from `attempt_claim_repair`, which only ever writes
ledger entries (anchor and claim text pinned; `TestWO13ReviewerNoteGate`
proves a note smuggled into the repair JSON never reaches prose).
`engine.claims.find_reviewer_notes` (`REVIEWER_NOTE_PHRASE_RE` + any
>40-char parenthetical mentioning a source being found/traced/supported;
markdown link targets exempt) now fails `run_source_integrity_gate`
(`reviewer_notes`, logged by run_show) and `build_epub` refuses the
volume (`validate_chapter_prose`, names chapter + match). The EPUB also
carries a legacy `toc.ncx` rendered from the same `_nav_entries` as the
nav (Draft2Digital: "ePub3 missing an NCX file"); epubcheck 0/0.
