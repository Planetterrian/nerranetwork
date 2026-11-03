# Oct 8 2026 — no transcripts on the whole slate, again

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Oct 8 2026 — no transcripts on the whole slate, again** (review:
[`docs/reviews/slate_review_2026_10_08.md`](docs/reviews/slate_review_2026_10_08.md);
register `slate-2026-10-08`; guards `tests/test_transcripts_pyav_2026_10_08.py`,
`tests/test_youtube_session_restart_2026_10_08.py`). Dependabot #1365
rewrote the Sep 30 PyAV ceiling to `>=19.0.1,<20` and was merged in a
batch while `test_pyav_is_pinned_below_19` was red: 0 of 21 episodes had a
transcript, the spoken-text gate ran blind, Nerra Daily Ep049 shipped every
segment uncut, Shorts lost captions and fact cards. **Whisper never decodes
through PyAV now** (`engine.transcripts.load_whisper_audio` — ffmpeg, samples
identical to faster-whisper's decoder); the ceiling stays and Dependabot
ignores `av>=19`. **Never merge a dependency bump on a red `Run Tests`**,
and read the comment above a pin before moving it. Same day: a 404/410 on a
resumable YouTube upload restarts ONCE with a new session (`upload_video` —
Tesla/SpaceX/Omni View lost their long-forms to "410 Gone"), and apt in
`setup-python` abandons a silent mirror connection after 30 s (five runs
died at exit 124 installing ffmpeg). **Same day, an outside review checked
and acted on** (§7 of the review; guards `tests/test_chapters_lead_2026_10_08.py`,
`tests/test_review_followups_2026_10_08.py`): **the lead story gets its own
chapter** (`engine.chapters._lead_story_split` — it sat inside
"Introduction" on 19 of 21 episodes; never on a known_sections_only show,
never where the body opens on another story) and **a spoken sentence is a
chapter title only when it fits whole** (no clipped fragments, no "Segment
N" — an untitled break is not made); `extract_story_headlines` reads
`**Title:** Outlet`; UC chapters its five digest segments. A missing lead
chapter never blocks an episode — chapters are metadata. **A hook may name
only what an item reports** (`hook_supported` lint, Tesla — Ep627 added
"Tesla Megapack" to a story that never mentions it; correction filed).
**Deep-dive essays are exempt from the overlap dedupe** (AI Chips Teardown,
SpaceX Engineering Deep Dive — each was deleted from a digest for citing a
news item's report). Bypass publishers (Nerra Daily, Voices) pass
`episode_page_url` like run_show. Ten site guards used Nerra Voices as "a
show with no episodes" and failed when it published Ep1 — they render
`conftest.unpublished_show` now; never use a real show as a fixture for a
state it will leave.
