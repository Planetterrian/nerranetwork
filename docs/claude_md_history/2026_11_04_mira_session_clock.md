# Mira's recorder loses time at every session change (Nov 4 2026)

Moved verbatim from CLAUDE.md on 2026-11-13; the rules that still bind are summarised there.

### Mira's recorder loses time at every session change (Nov 4 2026)

Guards `tests/test_mira_session_clock_2026_11_04.py`.
**Mira's own track is placed in the pieces her session changes made** (`post_interview.mira_session_changes` from the trace → `local_tracks.align_by_sessions`; a hand-over or a rescue costs her recorder 7–137 s right after it), **and checked in 30 s windows** (`clock_residuals`; the blind search's 150 s check passed tracks four minutes off). The lost seconds are filled from the guest's right channel only with no co-host. `pipelines/voices/retrack_run.py` rebuilds a processed run's tracks, mix and transcript (dry run by default; sends nothing).
