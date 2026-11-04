# Sep 22 2026 — one card to hear it and read it, and a transcript that is not the page

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Sep 22 2026 — one card to hear it and read it, and a transcript that is not
the page.** Every show has a blog now, including the interviews, and no show
page said so where a visitor looks: the Latest Episode card was a player, a
summary at `display:none`, and no route to the article — which sat four
screens down under "Latest from the Blog". Guards:
`tests/test_episode_card_transcript_2026_09_22.py`; experiment
`episode-card-and-transcript-box-2026-09-22`. What binds:

- **A transcript is collapsed, never withheld, and never the page.** An
  interview digest is 90% transcript (730 of Ep006's 785 lines) and it was
  printed OPEN in the article body, with the chapter list stranded on top of
  it. `engine.interviews.interview_transcript_markdown` pulls it out and
  `interview_body_markdown` stops printing it; **it is the ONLY transcript
  those episodes have** — the Voices pipeline bypasses `run_show`, so there is
  no `*_reader.txt` beside the digest and `transcript` had been empty, which
  is why an interview post carried no transcript box, no `#transcript` anchor
  and no JSON-LD `transcript` at all. The box now previews itself
  (`engine.blog.transcript_preview`, a LITERAL prefix cut at a sentence end —
  the interview module forbids reformatting the guest's approved words, and
  that applies to an excerpt of them) and says its word count. The full text
  stays in the HTML: a box that fetched its contents would cost the in-page
  search a reader uses to find a quote, and every crawler's view of what the
  episode said. **The preview lives inside `<summary>`** because a child of a
  closed `<details>` is hidden by the UA and author CSS cannot reliably bring
  it back; it carries `aria-hidden` since the same words are read again three
  lines below and a 400-character button label is not a button label.
- **The combined card renders from the same JSON the script fetches**
  (`engine.summaries_ssr`), so the script's render is an UPDATE, not a
  different card replacing "Loading...". Both cut the summary at
  `CARD_PREVIEW_CHARS`, interpolated into the script from the module — a
  second literal is how the card flickers into different words a moment after
  paint. **The article link is resolved at build time** through
  `_blog_url_for_episode`, which knows a redirect stub is not an article; when
  the feed has moved past the episode the page was built from, the script
  HIDES the link (`data-episode`) rather than deriving a URL it cannot vouch
  for. A show with no feed renders no card — Nerra Voices had a permanent
  "Loading..." above its own "Not published yet" band.
- **The bespoke DP Pod page needs every generic-template change made twice.**
  `show_page_dp_pod.html.j2` does not use `show_page.html.j2`, which is the
  same gap that left its Story Tracker unlinked for two months; it got the
  card in its own idiom.
- **The summary preview leads with the HOOK.** Four shows' cards opened on
  their own emoji branding line and Tesla's opened on a stock quote, because
  the walk started at line one and the "is this a sentence" test searched for
  a full stop ANYWHERE — and `(3.8%)` contains one. A hook is the episode's
  own headline, so everything above it is preamble by definition; the
  terminal-punctuation test now reads the END of the line. The walk exists
  twice, in `engine.summaries_ssr.plain_preview` and in the page script:
  change both or neither.
- **14 more stale "daily" claims**, on three Monday-only shows. The 09-21
  guard read `schedule` and `rss_description`; it did not reach the DP Pod
  page's own prose (8), its registry `meta_description`/`about_text` and
  Offshore North's `related_reason` (3), or env_intel's and Финансы Просто's
  descriptions (6, including the Russian «ежедневный»). The guard now sweeps
  every public string field for every Monday show, stripping show NAMES first
  so "SpaceX Daily" is not a false positive.
