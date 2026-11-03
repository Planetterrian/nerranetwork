# Landmine 14 — YouTube slideshow imagery is curated, not derived from keywords

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

14. **YouTube slideshow imagery is curated, not derived from `keywords:`**
    — early Tesla videos (e.g. Ep456) shipped with topless / fashion-model
    photos because `engine/visual_assets.py:_select_keywords()` was passing
    raw show keywords (`model 3`, `model y`, `model s`) to Pexels with no
    topic context. Pexels treats `model` as a person who poses, not a car.
    Fix landed May 2026: every show's `youtube:` block now declares
    `image_queries:` (curated, disambiguated phrases) and optionally
    `image_query_prefix:` (auto-prepended to any `keywords:` fallback).
    A safety filter (`image_safe_skip_terms`, default list in
    [`engine/config.py`](engine/config.py)) drops Pexels results whose
    URL slug contains people-only / off-topic substrings. The filter
    count is recorded as the `pexels_photos_filtered` metric — a spike
    means a show's queries need tightening. The
    `test_every_show_yaml_has_image_queries` test in
    [`tests/test_visual_assets.py`](tests/test_visual_assets.py) blocks
    any new show from going live without curated phrases.
