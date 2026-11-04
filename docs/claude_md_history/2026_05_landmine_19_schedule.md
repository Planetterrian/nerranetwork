# Landmine 19 — Schedule overhaul + weekly-summary segment (May 2026; restructured July 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

19. **Schedule overhaul + weekly-summary segment (May 2026; restructured
    July 2026)** — 7 shows moved to daily cadence (Omni View,
    Planetterrian, Fascinating Frontiers, Models & Agents, MAB, Modern
    Investing, Tesla; SpaceX joined later). Cron times shifted +1h across
    the board to widen the per-slot window; last show now finishes ~12 UTC
    (~8 AM ET). **July 2026 restructure:** the full Sunday weekly-recap
    mode was RETIRED. Sunday is no longer a special episode — every daily
    show runs a NORMAL daily episode every day, and shows with
    `weekly_summary_segment: true` (was `weekly_recap_on_sunday`) simply
    include ONE short "week in review" *segment* on Sunday. Mechanically:
    `_resolve_weekly_summary` in `run_show.py` gates on Sunday + the flag
    + not-a-deep-dive; when true, the daily digest generates as usual and
    `engine.weekly_recap.build_weekly_summary_segment` synthesises a
    compact host-instruction block from the past 7 days in the content
    lake. That block is appended to the **podcast-only** copy of the digest
    (`clean_digest`, after cleanup) — NOT to the published `x_thread` — so
    the host weaves a brief recap into the episode while zero instruction
    text reaches the blog / RSS / newsletter. A thin content lake (<2
    episodes in window) returns `None` → a plain daily episode with no
    segment. The retired full-recap machinery (digest short-circuit,
    daily-validator skip, and the recap "republish from clean narrative"
    step) is gone; the video recap-scene-reuse path in `_publish_youtube`
    remains as a dormant default-off capability. Prompt/audio-affecting on
    Sunday → A/B-listen per landmine #17. Modern Investing additionally has
    a Saturday "weekend mode" instruction in its podcast prompt covering
    international markets, crypto, lessons learned, and what to prepare for
    in the coming weeks. Drift guards in `tests/test_schedule.py` +
    `tests/test_weekly_summary_segment.py` pin: cron consistency, the daily
    shows carrying the weekly-summary flag, alt-cadence/narrative shows NOT
    carrying it, the segment shape/append point, and that the retired
    full-recap machinery does not return. The legacy `weekly_recap_on_sunday`
    YAML key is still read as a back-compat fallback in `engine/config.py`.
