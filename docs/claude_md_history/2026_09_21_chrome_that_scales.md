# Sep 21 2026 — chrome that scales, and a way to browse (C2)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Sep 21 2026 — chrome that scales, and a way to browse (C2).** The footer
repeated the show list three times on every one of ~2,100 pages and `/explore.html`
did not exist. Guards: `tests/test_chrome_pass_2026_09_21.py`; experiment
`explore-and-footer-scale-2026-09-21`. What binds:

- **The accordion hides `.nn-footer-col > a` AND `> ul`** — so a grouped list is
  collapse-safe and the Sep 20 note here ("nesting would stop it collapsing") was
  incomplete. The real trap is a direct child of any OTHER kind: a group label
  written as a heading stays visible on a phone above a column whose links have
  all collapsed away. Labels therefore live INSIDE the `<ul>`. Both guards were
  mutation-tested by hoisting the label out.
- **A source-reading guard must strip Jinja comments first.** The corrected
  footer guard passed under that mutation because `before.rfind("<ul")` matched
  the *comment* explaining the rule. A test that reads source as text can be
  satisfied by prose describing the thing it checks — strip `{# … #}`, or assert
  on rendered output.
- **A chrome guard renders its own page; it never reads a committed one.**
  Generated HTML is refreshed by the pipeline, not committed from a working tree,
  so on any checkout the committed `index.html` still carries the PREVIOUS
  chrome. Two guards failed that way and a third passed vacuously before they
  rendered into `tmp_path` (the `output_dir=` idiom `test_topic_hubs` already
  used).
- **`show_groups` is the one strand grouping**, computed once in `base.html.j2`
  and used by the desktop Shows dropdown, the mobile menu, the footer and the
  Blog dropdown. It carries the translation KEY, not the label, so each surface
  names the ungrouped fallback itself. Four copies of a `selectattr` pair is how
  the footer drifts from the nav.
- **Footer: 53 show-derived links per page → 20.** The 18 per-show blog links
  became the hub plus the topics map; the 17 per-show RSS links became one link to
  `how-to-listen.html#feeds`, which **already listed every feed** including the
  per-language ones, `has_feed`-gated — so this was one `id` attribute, not a new
  page. `modern-investing-resources.html` keeps its old footer: it is one of the
  three hand-written pages and no template reaches it.
- **`/explore.html` filters on the CURATED vocabulary** —
  `engine.topic_hubs.TOPIC_HUBS`, not the union of registry `picker_tags.topics`
  (42 values, 28 singletons, both `tech` and `technology`). A hub below the page
  threshold still filters, because a chip is not a link. Audience is not a facet.
  The grid is server-rendered and the chips only add `.is-dimmed`, so with
  JavaScript off the page is the whole catalogue.
- **The show card is one macro** (`_macros.html.j2` `show_card`), used by the
  homepage and by explore. The homepage's rendered card changed in whitespace
  only (verified by normalised comparison); `.show-card-wrap.is-dimmed` and
  `.show-card-audience` moved from the homepage's inline `<style>` to
  `styles/main.css`, since a rule only one of two pages carries is a rendering
  bug waiting to happen. `.nn-section-header h1` is styled now as well as `h2`.
