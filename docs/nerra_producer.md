# Nerra Producer

The Producer is the network's back office. It is never on-air: it does not
host, narrate, or appear in any episode. It reads Patrick's inbox, sorts
what arrives, answers the routine part (guest pitches) in Patrick's voice,
and hands everything else to Patrick with a note. It exists so that the two
Mira-hosted interview shows, The Age of AI and Nerra Voices, get a steady
flow of booked guests without Patrick reading every publicist email.

Code: `pipelines/producer/` (`gmail_client.py`, `classify.py`, `policy.py`,
`inbox.py`, `prompts/classify_pitch.txt`). Config:
`shows/_producer_policy.yaml`. Templates: `templates/email/producer_*.j2`.
Workflow: `.github/workflows/nerra_producer_inbox.yml`. Tests:
`tests/test_producer_inbox.py`. Schema: the Producer columns on
`guest_applications` plus the `producer_runs` table in
`supabase/migrations/20260905_voices_show_routing.sql`.

## The inbox job

```
python -m pipelines.producer.inbox [--dry-run] [--limit N]
```

Runs every 30 minutes from GitHub Actions (concurrency group
`nerra-producer-inbox`, so two ticks never overlap). Per run:

1. **List** Gmail threads matching `-label:Producer/Processed newer_than:30d
   in:inbox` (up to `--limit`, default 50).
2. **Duplicate check.** If `guest_applications` already has a row with this
   `email_thread_id`, the thread is labelled processed and skipped without
   an LLM call.
3. **Classify** the latest inbound message (subject, sender, body truncated
   to 3000 chars) with Grok, always `model="grok-latest"` (operator rule:
   never a version-pinned identifier in the Producer). Strict JSON schema,
   validated by `classify.validate_classification`; one strict retry on bad
   output, then the thread is marked confidence 0 so the policy holds it.
   Routing rule: AI / agents / automation / AI-in-industry / AI investing
   substance goes to `age_of_ai`; everything else to `nerra_voices`.
4. **Decide** with `policy.decide` (pure, unit-tested; see below).
5. **Act.**
   * `send`: render `templates/email/producer_guest_invite.j2` for the
     recommended show and reply in-thread (plain text, `From` = the
     delegated user, `In-Reply-To` / `References` set so Gmail threads it).
   * `draft`: hold for Patrick. If there is an invite to draft (a guest
     pitch), it is saved as a Gmail draft on the thread; a Slack note
     (`producer_hold_note.j2`) says why, with the thread link; the thread
     gets the `Producer/Hold` label.
   * `label`: platform notices and newsletters are only labelled.
   * `skip`: duplicates and follow-ups on threads Patrick already answered.
6. **Record.** For anything sent or drafted, one `guest_applications` row:
   `source='email'`, `status='invited'`, `show`, `pitched_show`,
   `publicist_name`, `publicist_email`, `pitch_summary`,
   `producer_classification` (the JSON), `producer_action`
   (`sent`/`drafted`), `producer_acted_at`, `email_thread_id` (unique).
   `pitched_show` is stored only; `cross_show_callouts` rows are created at
   produce time, not here.
7. **Label** the thread `Producer/Processed`.
8. One thread's failure never aborts the run. Errors are collected into the
   `producer_runs` row and the closing Slack summary
   (`Producer inbox: N seen, N invited (age_of_ai X / nerra_voices Y),
   N drafted, N skipped`). The job exits non-zero only when more than half
   of the threads failed.

`--dry-run` reads Gmail and classifies, but never sends, drafts, labels, or
writes to Supabase; every would-be action is logged.

## Policy and hard exclusions

`shows/_producer_policy.yaml`, overridable per field without a code change.

* `mode`: `auto` (default, Patrick's choice: fully automatic), `draft`
  (never send; every clean pitch becomes a Gmail draft), `off` (do nothing:
  no Gmail reads, no labels, no DB writes). `PRODUCER_MODE` in the
  environment wins over the yaml.
* Hard exclusions, which always produce a hold (draft + Slack note) and
  never a send, in any mode:
  * category `sponsor_or_sales` or `personal_or_business`;
  * `mentions_money_or_legal` true;
  * classifier confidence below `min_confidence` (0.75);
  * sender domain in `never_auto_reply_domains` (apple.com, spotify.com,
    google.com, github.com, voximplant.com, supabase.com, cloudflare.com,
    and a few vendors; subdomains match);
  * the delegated user already replied in the thread (never double-reply).
* `guest_followup` on a thread Patrick already answered: skip, no action.
  On a thread nobody answered: hold.
* `platform_notice` and `newsletter_or_noise`: label processed, no reply.
* `max_sends_per_run` (25): a circuit breaker; anything past it is drafted.
  `PRODUCER_MAX_SENDS` overrides it.
* `show_blurbs`: the one-line description of each interview show used in
  the invite. `pitched_show_names`: slug to display name for the daily
  shows a publicist may have asked for; the invite promises to feature the
  interview on that channel.

Every decision (thread id, action, reason, category, confidence, show) is
logged to stdout and into the `producer_runs.notes` JSON for the run.

## The invite

Plain text, Patrick's voice, no HTML. `Hi <publicist first name>,` (or
`Hi There,` when the sender's name is unknown), the explanation that the
daily shows are automated and take no guests, that Mira is an AI who
interviews live and that guests approve their transcript, the recommended
show with its blurb, the apply URL for that show, an optional line about
the pitched daily channel, and `Sincerely, / Patrick`. Rendered without
autoescaping (`inbox.render_text`), unlike the HTML `voices_*.j2` mails.

## Operator setup

1. **Google Workspace: service account with domain-wide delegation.**
   In a GCP project (any; a dedicated `nerra-producer` project is
   cleanest): enable the **Gmail API**; create a **service account**; on the
   service account, create a **JSON key** and download it. Note the
   service account's **OAuth client ID** (the numeric "Unique ID"). Then in
   the Workspace **Admin console → Security → Access and data control →
   API controls → Domain-wide delegation → Add new**: paste the client ID
   and the scope `https://www.googleapis.com/auth/gmail.modify`. Nothing
   else is needed on the mailbox itself; the account impersonates
   `patrick@planetterrian.com` through the delegation grant.
2. **GitHub secrets.** `GMAIL_SERVICE_ACCOUNT_JSON` = the full contents of
   the downloaded JSON key (paste the file, not a path);
   `GMAIL_DELEGATED_USER` = `patrick@planetterrian.com`. The workflow also
   maps the existing `VOICES_SUPABASE_URL`, `VOICES_SUPABASE_SERVICE_KEY`,
   `GROK_API_KEY`, `SLACK_WEBHOOK` (or `NOTIFICATION_WEBHOOK_URL`).
3. **Dry run first.** Actions → *Nerra Producer inbox* → *Run workflow*
   with `dry_run = true` (and a small `limit`, say 10). Read the log: every
   thread shows its classification, the decision and reason, and the
   `[dry-run] would SEND / DRAFT / label / insert` lines. Nothing is
   touched. Repeat until the decisions look right; tune
   `shows/_producer_policy.yaml` if not.
4. **Set `PRODUCER_MODE`.** A repository **variable** (Settings →
   Secrets and variables → Actions → Variables), not a secret. Start with
   `draft` for a day if you want to read the drafts before anything goes
   out; switch to `auto` when comfortable. `off` stops the job without
   disabling the workflow. The 30-minute cron picks the value up on its
   next tick.
5. **Gmail labels.** The Producer creates two nested labels on first use:
   `Producer/Processed` on every thread it has looked at (this is also the
   idempotency mark; remove it from a thread to have the Producer look
   again), and `Producer/Hold` on threads it held for you. In the Gmail
   sidebar they show as a `Producer` parent with `Processed` and `Hold`
   underneath. Drafts the Producer wrote sit in the normal Drafts folder,
   attached to the original thread.
6. **Draining the backlog.** The cron looks at `newer_than:30d in:inbox`.
   The April–September 2026 pitch pile is older than that, so run the
   workflow once by hand with `inbox_query = newer_than:180d in:inbox`
   (and `limit = 100`). The per-run send cap (`max_sends_per_run`, 25)
   leaves anything past the cap untouched for the next tick, so a big
   backlog drains over a few runs on its own instead of piling up as
   drafts. `PRODUCER_INBOX_QUERY` in the environment does the same for a
   local run.

## Roadmap (not yet built)

* **chase**: nudge invited guests who have not filled the form after N
  days, and applicants who have not booked after triage.
* **gate-1 pre-review**: a first editorial pass on the eight post-interview
  passes before Patrick's gate-1 review, flagging what needs his eye.
* **weekly improvement loop**: a Sunday digest of what the Producer sent,
  held, and got wrong (Patrick's edits to drafts as the training signal),
  with proposed policy and prompt changes.

The `producer_runs.job` column already accepts `chase` and `review`
alongside `inbox` for these.
