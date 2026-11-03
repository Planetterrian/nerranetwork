# Sep 22 2026, later — the finishing pass on the Age of AI pages

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Sep 22 2026, later — the finishing pass on the same pages** (guards
`tests/test_age_of_ai_finish_2026_09_22.py`; register
`age-of-ai-finish-pass-2026-09-22`). What binds:

- **`engine/brand.py` owns the interview steps** (`MIRA_INTERVIEW_STEPS`,
  `MIRA_INTERVIEW_STEPS_COMPACT`); `generate_html.MIRA_INTERVIEW_STEPS` is
  the same object re-exported. The `mira_steps_list` macro renders them from
  the `mira_steps` / `mira_steps_compact` globals — all eight on `mira.html`,
  the five a prospective guest asks about on a show page that has an
  `apply_page` (Nerra Daily is `strand: mira` and takes no guests, so it
  shows none). A template that types a step title fails CI. Step 7 states
  the seven-day auto-approve; it is not hidden in the short form.
- **A Spotify id in the show YAML is a Spotify chip** (`_spotify_url_for`,
  the `_apple_links_for` rule: registry string wins, the id fills the gap).
  Six shows had the id and `spotify_url: null` and rendered no chip.
- **Interview posts carry a one-line provenance** from
  `brand.interview_provenance(guest, cohost)`: hosted by an AI, who
  co-hosted (from the transcript), reviewed by Patrick, transcript SENT to
  the guest to approve, cut or refuse — never "approved by", because
  silence also publishes. The scoped `creator_credit` renders on the post
  as it does on the show page; the chapter list left the digest body for
  the page's real `blog-chapters` section (the seek script falls back to
  `.nn-iv-player audio`; the `nn-i18n-audio` literal a guard pins is kept);
  the breadcrumb and both JSON-LD blocks name the guest (`about` Person).
- **Interview index cards lead with the person** (`interview_cards` keyed
  by episode into `generate_blog_index_html`; a news index is byte-identical).
- **`.nn-guest-*`, `.nn-creator-*` and `.mira-steps` live in `styles/main.css`**
  — each is rendered on more than one page now.
- **News surfaces changed in CSS text and whitespace only**, verified by
  rendering Tesla, Omni View and Offshore North before and after. That is
  an intended, reviewed diff, not a byte-identical one: the
  `.nav-next-placeholder` fix applies to every show's latest post.
- Pre-existing, left alone: `generate_blog_index` logs "Unrecognized
  summaries shape" for `age_of_ai` — `engine.summaries_io` does not read the
  Voices `{"episodes": [...]}` wrapper. It was on main before this pass.
