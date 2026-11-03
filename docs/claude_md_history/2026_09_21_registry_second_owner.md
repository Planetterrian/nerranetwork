# Sep 21 2026 — the registry grew a second owner for three things (C1)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Sep 21 2026 — the registry grew a second owner for three things, and one
"dead" key was read raw.** Consolidation pass (C1), whose whole acceptance was
a byte-identical `--all`: 1,921 blog posts, 60 root pages, 13 topic hubs, the
four RU pages and `sitemap.xml` all unchanged, with the only 39 differing files
(`api/*.json`, `blog*.rss`) differing solely in their generation timestamps.
Guards: `tests/test_registry_pass_2026_09_21.py`. What binds now:

- **`engine/show_lang.py` owns a show's page language.** The Russian pair was a
  literal tuple repeated SEVEN times — three in `generate_html.py` (summaries
  page, show page, `_count_languages`) and four in `engine/blog.py` (JSON-LD
  `inLanguage`, `_is_ru`, the next-episode placeholder, `page_lang`) — so a
  registry-only show **could not be Russian at all**, and a missed copy renders
  a page in the wrong language with nothing failing. The language is DERIVED
  from `shows/<slug>.yaml`'s `tts.language_code` (the field the operator
  already maintains, the `_newsletter_tag_for_slug` pattern), with an optional
  `page_lang` in `network_meta.yaml` checked first for registry-only shows that
  have no YAML. Verified before it was written: across all 18 shows it returns
  `ru` for exactly `finansy_prosto` and `privet_russian`.
- **`picker_tags` is an ordinary registry key**, not a parallel
  `_SHOW_PICKER_TAGS` dict only the YAML path could write to (a hardcoded show
  could not declare tags, and the tags decide `/topics/` hub membership). The
  twelve blocks were moved programmatically and checked by equality against a
  saved copy, because the failure mode is a transcription slip that empties a
  hub while the page still renders and validates. The hub snapshot guard pins
  hub id → slug SET; a count would pass through exactly that loss.
- **The scaffolded merge is per-key** (`_merge_show_meta`, curated Python value
  wins). It is a **no-op today** — the two sources are disjoint, twelve slugs in
  Python and six in YAML — which is precisely why the footgun went unnoticed:
  `if slug not in NETWORK_SHOWS` silently discarded a YAML entry's thirty-odd
  keys the first time anyone scaffolded over a hardcoded show.
- **`newsletter_tag` in the registry looks dead in one context and is read raw
  in another.** This pass deleted it and nearly shipped that.
  `_newsletter_tag_for_slug` resolves the tag from the show YAML for the
  summaries/show-page context, so `_build_all_shows_list()` shows every show
  correctly tagged with the registry key gone — which reads as proof it is
  unused. The blog path renders from the RAW entry (`generate_blog_posts` does
  `cfg = NETWORK_SHOWS[slug]`; `engine.blog` reads
  `show_config.get("newsletter_tag") or show_config["name"]`), so removing it
  fell back to the Cyrillic display NAME and put a tag Buttondown refuses on
  ~150 Russian blog posts. **Before deleting a registry key, check the raw-entry
  readers as well as the built context** — the full-tree diff is what caught
  this, not the tests.
