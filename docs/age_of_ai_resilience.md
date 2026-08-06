# The Age of AI — interview resilience playbook

What happens automatically when an interview goes wrong, and what is still
manual. Born from the Aug 5 2026 Dan Perra session (four attempts: three
silent browser joins, one successful phone interview) and the failures the
dry runs surfaced before it. Owner: the nerra-voices Worker + the fire
workflow; nothing here requires operator action unless explicitly marked.

## Failure taxonomy and automated responses

| # | Scenario | Detection | Automatic response |
|---|----------|-----------|--------------------|
| 1 | Fire cron late (GitHub delivers */5 ~hourly) | — | Cloudflare Worker cron fires a `fire-tick` repository_dispatch every 5 minutes, to the minute. GitHub cron stays as fallback; double ticks are idempotent. |
| 2 | Short-notice booking (<12 h, no brief) | Fire step finds `scheduled` interview in window with no brief | Brief generated inline at fire time (same code path as the daily T-1d workflow); guest still gets the prep email, minutes ahead. |
| 3 | PSTN guest doesn't answer | `CallEvents.Failed` → webhook `call_failed` | Retry ladder: interview reset to `briefed`, re-dialed on the next tick within the 30-min grace window. Second strike → `missed` + rebooking email to the guest. |
| 4 | Studio (WebRTC) join fails — silence, refresh, media path | Session ends with `duration < 300 s` | Run reset to `awaiting_guest`; studio reopens instantly; attempt counted; operator informed (FYI only). |
| 5 | Studio join fails twice | Attempt counter ≥ 2 | **Auto phone fallback**: interview flips to `pstn`, run failed-out, next fire tick (≤5 min) has Mira dial the guest's phone. Guest and operator emailed. No manual step. |
| 6 | Guest's mic silent in-call (they hear Mira, she hears nothing) | No `InputAudioBufferSpeechStarted` 35 s after greeting | Mira says she can't hear them and points at the on-screen mic meter; repeats once at 80 s; keeps waiting. Page shows a live in-call meter on the selected device. |
| 7 | Grok connection drops mid-call | WebSocket close/error with guest still on line | Mira's pre-recorded apology plays; call ends cleanly; normal webhook with partial recording. |
| 8 | Zombie webhook (abandoned session's disconnect arriving late) | Short-session guard (#4) catches most | Residual risk: a stale session completing OVER a live one's row. Mitigated by the <300 s guard; full fix is per-session webhook keys (below). |
| 9 | Post-production/publish failures | Workflow failure | Video render is best-effort (audio publishes without it); polish stage is best-effort (unpolished episode beats no episode); publish is always a deliberate dispatch, so a failed run just re-dispatches. |

## Connection drop mid-interview: restart & continue (DESIGNED, NOT YET BUILT)

The remaining gap: a real interview (>5 min) that drops at minute 20 is
currently treated as a completed episode. Design for continuation:

1. **Drop detection.** A webrtc/PSTN session ending without Mira's sign-off
   (scenario sets a `signed_off` flag when her closing-thanks response has
   been generated) and with duration between 300 s and the hard cap is
   marked `interrupted`, not `completed`. Post-production is NOT dispatched.
2. **Reopen.** The run resets to `awaiting_guest` with `part: 2` metadata
   (or re-dials on PSTN). Guest gets an email/SMS: "we got cut off — rejoin
   here / I'll call you back."
3. **Continuation context.** The new session's Mira prompt is compiled with
   an appended block: interview part 2, the drop apologised for, plus the
   part-1 running transcript (the scenario accumulates Mira-side transcript
   deltas and the guest's ASR deltas in-session; the last ~2,000 words ride
   into the part-2 prompt so she continues, not restarts).
4. **Multi-part post-production.** `post_interview` collects ALL of the
   interview's recordings ordered by session start, concatenates before the
   mix, and the polish cut list runs on the joined audio. Editorial sees one
   continuous transcript with a `[connection dropped — resumed]` marker the
   cleanup pass smooths over.
5. **Give-up rule.** If part 2 also drops before 5 minutes, fall to the
   auto-PSTN ladder (#5); if PSTN also fails, `missed` + rebook email.

Estimated build: scenario transcript accumulation + interrupted status +
Worker reopen path + multi-part concat in post. Prioritise before public
launch (phase 8); acceptable risk during soft launch with founder-adjacent
guests.

## Also on the quality roadmap

- **Local browser recording (Riverside model):** guest mic + camera captured
  in-browser at full quality, chunk-uploaded to R2; cures both the
  compressed-call audio ceiling AND the Bluetooth capture conflict class
  (the browser records the same device it captures). The Voximplant
  recording becomes the live/backup track.
- **Per-session webhook keys:** scenario includes its Voximplant session id
  in the webhook; the Worker ignores updates from a session that is not the
  run's CURRENT session — eliminates the zombie-overwrite class (#8) fully.
