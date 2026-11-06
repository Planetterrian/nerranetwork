# Landmine #21 — `min_articles_skip` is tuned per-show (May 2026)

Moved verbatim from CLAUDE.md on 2026-11-06 to keep it under its size cap.

21. **`min_articles_skip` is tuned per-show, not per-network (May 2026)**
    — `engine/config.py` defaults `min_articles_skip` to `3` (a show
    skips that day's run if fewer than 3 fresh articles survive
    fetch + dedup). The default is a deliberately weak floor; every
    show that needs a different threshold pins it explicitly in its
    YAML. Current pinned values:

    | Show | `min_articles_skip` | Rationale |
    |---|---|---|
    | `tesla` | 6 | Largest property; six-segment digest needs density. |
    | `omni_view` | 4 | World-news scan; below 4 the digest reads thin. |
    | `fascinating_frontiers` | 4 | Space/science; needs multiple beats. |
    | `models_agents` | 4 | AI news firehose; sub-4 means a quiet day → skip. |
    | `finansy_prosto` | 4 | Russian financial news scarcity → wait for a real day. |
    | `modern_investing` | (default 3) | Markets always produce 3+ stories on a weekday. |
    | `env_intel` | 2 | Alt-cadence (odd weekdays); 2 substantive stories enough. |
    | `models_agents_beginners` | 2 | Re-uses M&A pool; lower bar OK because tone is explanatory. |
    | `planetterrian` | 2 | Science/longevity/health show (NOT local news — that description was stale); primary-research days can be thin, so 2 is the realistic floor. |
    | `privet_russian` | 1 | Bilingual lesson show; one solid theme is sufficient. |
    | `unintended_consequences` | 0 | Narrative show — articles aren't the input, topic queue is. |
    | `first_principles` | 0 | Narrative show — topic queue is the input (alternates concrete example / opportunity area). |

    **Landmine:** changing the default from `3` would silently
    re-tune four shows (the ones currently pinned at `4` would still
    pass; the ones below `3` rely on the explicit override winning).
    Always change the per-show YAML, not the default. The
    `unintended_consequences` value of `0` is load-bearing — that
    show pulls from `shows/topic_queues/unintended_consequences.yaml`
    and never fetches news; raising it would block every episode.
