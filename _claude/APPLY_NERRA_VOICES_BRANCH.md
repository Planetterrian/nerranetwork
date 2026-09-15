# Landing the nerra-voices-producer branch

The branch was built and tested in a clean clone of origin/main
(296466fc). Your Mac clone is on a8322d17f (behind origin), so pull first.

From a terminal in ~/Tesla-shorts-time:

    git checkout main
    git pull --ff-only
    git fetch _claude/nerra-voices-producer.bundle nerra-voices-producer:nerra-voices-producer
    git checkout nerra-voices-producer
    git push -u origin nerra-voices-producer

Then open the PR on GitHub (or `gh pr create --fill`).

If the bundle fetch complains about a missing base commit, `git pull`
did not reach 296466fc; run `git log --oneline -1 origin/main` and try
again once it does. Fallback: `git am _claude/nerra-voices-producer.patch`
on a branch off main.

Before the first real booking (in this order):
1. Apply supabase/migrations/20260905_voices_show_routing.sql to the
   nerra-voices project (Supabase MCP apply_migration).
2. wrangler deploy in workers/voices (new optional vars
   CALCOM_BOOKING_URL_NERRA_VOICES, CALCOM_EVENT_SLUG_AGE_OF_AI,
   CALCOM_EVENT_SLUG_NERRA_VOICES).
3. Cal.com: second event type for Nerra Voices.
4. Producer: docs/nerra_producer.md steps 1-6 (Gmail service account,
   secrets, dry run, PRODUCER_MODE, backlog drain).
