# Sep 18 2026 — a result key is not a metric, third time; and the MIT loop starves itself

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Sep 18 2026 — a result key is not a metric, third time; and the MIT
loop starves itself** (plan:
[`docs/reviews/youtube_pipeline_plan_2026_09_18.md`](docs/reviews/youtube_pipeline_plan_2026_09_18.md);
guards `tests/test_caption_track_2026_09_18.py`). Omni View Ep179
shipped its long-form with NO captions: `captions.insert` answered one
HTTP 403 while six sibling uploads on the same token succeeded, the
warning blamed a missing `youtube.force-ssl` scope, and
`caption_track_uploaded` had been set on the publish result since July
without ever reaching the `record_youtube_outcomes` allowlist. Now
`engine.youtube.upload_caption_track_detailed` returns `(ok, reason)`,
retries a transient 403/429/5xx ONCE, names a scope refusal only when
the API says `insufficientPermissions`, and both keys are recorded
(`caption_track_refusals_14d` on the register, entry
`caption-track-retry-2026-09-18`). Same pass scored the seven
experiments past readout: the open cliff is a MISS at 0.48 (the render
levers did not move it; the spoken open is what is left), review
catch-up a HIT, the MIT methodology correction retired on schedule but
sent nobody to the performance page, the RU 4th Short holds 55% of the
hook (near miss, n=8, kept), and **MIT declared "no trade today" on 19
of its 23 episodes since Ep152** — the regime block read the young era
record as a COLD STREAK and told the model to raise the bar, so the
rules-based era has 9 closed trades in a month and cannot score a rule.
Fixing that is a prompt-context change (A/B) and is the plan's first
operator item.
