# Oct 4 2026 — the Sunday slate after the Oct 3 pass

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Oct 4 2026 — the Sunday slate after the Oct 3 pass** (guards
`tests/test_sunday_slate_2026_10_04.py`). Every Oct 3 target was clean on
the 21 Oct 4 episodes (no "go deeper" frame on OV, no UN / NT$ garbles, no
doubled "subreddit", no self-narration, no daily plug for a weekly show,
spoken-text gate 21/21 pass). Three defects the slate exposed, all fixed:
(1) **the weekly newsletter run had hit its 45-minute timeout on four
Sundays running** — synthesis is 3-5 min a show on grok-4.6, the walk was
alphabetical, so Planetterrian, SpaceX, Tesla and UC got no weekly after
Sep 6, ten cohort shows spent ~4 min each writing a weekly their missing
Buttondown tag then refused (a tag exists only once someone subscribes
with it), and the cancelled job never committed the sent markers of the
shows that DID go out (a re-run would have sent them twice). Now
`run_weekly_newsletters.send_preflight` refuses before synthesis exactly
what the send would refuse, `PRIORITY_SHOWS` go first, the run step has a
75-minute cap under a 90-minute job and the commit step is `always()`;
the six Oct 4 sends are recorded from the run log, and the default week is the most recent SUNDAY (`default_week_ending`) — with `date.today()` a catch-up dispatch after midnight UTC keyed its markers on Monday and would have re-sent all six. (2) **The Sunday
week-in-review instruction offered "just after the intro"** — the slot the
cold-open rule forbids (13/19 scripts on Sep 27, 3/19 incl. Tesla on Oct
4); it now goes before the close only (⚠️ AUDIO). (3) **Nerra Daily's
handoffs broke the one-in-three show-name rule on every full edition**
(18/18, 18/19): `handoff_revision_prompt` sends a non-compliant draft back
once and `adopt_revised_handoffs` keeps the revision only when it leads
with fewer names (metrics `handoffs_show_name_led_first_draft`,
`handoffs_revised`; ⚠️ AUDIO). Open for the operator: MIT's four disclaimer
sentences sit between the cold open and the first story every day
(`script_hook_leads_body_pct` 0 on 11/11 episodes — compliance placement);
`grok-47-staged-migration` is read again (`model_trial_report --since
2026-09-27 --timeout-seconds 600`): the 4.7 cohort writes better (11-22
claims, 2-17% digest-verbatim against 1-3 and 46-63% on the 4.3 flagships)
and fell back on 2 of 48 episodes (pre-flight pings, last Sep 30), but its
streamed DIGEST stage FAILS the latency gate — p95 433-814 s against the
600 s request timeout, time-to-first-token ~180-280 s. A flagship digest on
4.7 is therefore NOT the next step. **Oct 5 correction: omni_view's 4.7
script arm never ran** — grok-4.3 served all 14 of its scripts from 09-22
(the 4.7 call timed out, 621 s non-streaming, and fell back) while
`llm_script_model` recorded the configured model; it is back on grok-4.6
(8-17% verbatim at 76-85% coverage on 09-10..21), and the metric now
records the SERVED model plus `llm_script_model_fallback`. Read a model
arm from the credit files' per-call `model`, never from config. **The script call had never been timed** — the trial report
listed `generate_podcast_script` as an LLM stage that nothing recorded (the
Sep 30 "script stage p95 67.6 s" was omni_view's 4.3 DIGEST row); it is
recorded from the next run (`PipelineMetrics.record_stage`), so a
script-stage pin can be gated before it widens.
