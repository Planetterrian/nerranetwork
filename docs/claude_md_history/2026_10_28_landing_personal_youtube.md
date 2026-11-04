# The front page, Nerra Personal and the video links (Oct 28 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### The front page, Nerra Personal and the video links (Oct 28 2026)

Review [`docs/reviews/landing_personal_youtube_2026_10_28.md`](docs/reviews/landing_personal_youtube_2026_10_28.md);
register `landing-personal-youtube-2026-10-28`; guards
`tests/test_landing_personal_youtube_2026_10_28.py`,
`workers/gallery/test/member_security.test.ts`. Rules that bind:

- **Only a magic-link cookie (`v: 1`) may use a member's paid record.** The
  subscribe form issues the same cookie with no proof the visitor owns the
  address; `mayUseRecord` (`workers/gallery/src/personal.ts`) lets an
  unverified cookie use only a record it created in the same session
  (`created_iat`), and the billing portal needs a verified one. A KV member
  can sign in without a newsletter subscription. Activation writes a welcome
  feed and sends the welcome email. An event for a superseded subscription is
  ignored. The feed answers HEAD and byte ranges. "Today" is the Eastern date
  in the Worker and the builder. Operator: `wrangler deploy` in
  `workers/gallery` before `STRIPE_SECRET_KEY` goes on the Worker.
- **Every blog rebuild links the episode's public videos** from the show's own
  index (`engine.youtube_index.episode_video_links`; a scheduled video is
  never linked, the hook Short wins). The rebuild had passed none, so 0 of
  1,036 flagship posts carried the button.
- **A dub Short opens on its own story and ends on a sentence**
  (`hook=_overlay`, `end_on_sentence` on the dub's words, in `ru_dub` and
  `lang_dub`). **Call `generate_shorts_thumbnail` with keywords**: both dub
  paths passed the output path as the episode number, so no RU or FR Short
  ever got its custom thumbnail.
- **The lead headline comes before its picture** (`lt-lead-head`, front page
  and language hubs); it had started below the fold at 1440x900 and on a
  phone. A story two shows told is one card naming both (`merge_retellings`);
  the Latest list keeps every episode.
- **An event tracking.js sends is in `ENGAGEMENT_EVENTS`**, and the funnel
  reports it null when unread: `episode_play`, `subscribe_click`,
  `play_personal_sample`, `begin_checkout` (every Payment Link carries
  `data-nn-tier`), `watch_on_youtube`.
- **Member copy states what the product does**: xAI receives the member's
  first name, city, subjects and note (privacy policy); Skip repeats and the
  length setting cut whole chapters; a cancelled feed runs to the end of the
  paid period; the members-only desks are badged and never called free.
- **Long-form retention is read at a fixed age**
  (`long_form_avp_en_age7_median`; longs are followed to day 21; a 0% with no
  watch time is unmeasured, never a frozen zero).
