# The site's languages: an English front page, one hub per language (Oct 18–19 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### The site's languages: an English front page, one hub per language (Oct 18 2026)

Operator: the English landing page carried the two Russian shows and their
headlines; other-language content belongs behind the header's language
selector or on dedicated pages. Guards `tests/test_site_languages_2026_10_18.py`.
Rules that bind: **`engine/show_lang.py` owns the SITE LANGUAGES**
(`site_languages()` — English plus every language a show renders its pages in
or produces an audio track in, derived from the show YAMLs; `es` and `zh` have
neither today and get no row), `language_hub_path()` (`<lang>/index.html`) and
`track_languages()` (the one reading of `multilingual.languages` with the ZH
approval rule — `generate_html._producing_track_languages` and
`_listening_languages` delegate to it). **The English homepage reads English
shows only** (`_english_shows`; stories, grid, picker, Organization JSON-LD),
while the free-show COUNT stays network-wide (`_public_show_count_cached`, 26).
**The chrome lists the shows of the PAGE's language** (`chrome_shows` in
`base.html.j2`, from each show dict's `page_lang`; a language with no native
show falls back to the English list) and links the other languages' hubs from
the header's one Language menu (Site links + the June 2026 episode-audio
radios, both from `site_languages`), the footer and the mobile menu; the footer
newsletter picker offers the chrome's shows. **`<lang>/index.html` is generated
for every non-English site language** (`generate_language_hub_pages`, template
`language_hub.html.j2`, in `--static-pages` and `--all`, both hubs in nightly's
add-paths): `ru/index.html` is no longer hand-written (the Sep 3 "three
hand-written pages" are two now), `fr/index.html` is new — seven shows produce a
French track and @NerraFR had no page on the site. A hub lists the language's
native shows (latest episode), the English shows with a live `<lang>` feed
(`_collect_language_feeds(..., slug)` — the 45-day freshness gate applies), the
RU landers and the language's YouTube channel; **every reader string is
hand-written in `_LANGUAGE_HUB_COPY`** and a language with no copy gets no
page and a `::warning::`. The homepage and every hub emit the SAME hreflang
group (`_site_hreflang_alternates`, en / fr / ru / x-default on canonical URLs;
the EN↔RU show-pair helper is unchanged) and the sitemap lists hubs from the
same vocabulary. The chrome's translation dict is still EN/RU only: the French
hub's body is French and its chrome English (a `fr` dict is the next step if
the hub earns traffic).

**Oct 19 2026 — the hubs are front pages.** Operator: the Russian and French
pages should be the equivalent of the English landing page, tailored to those
audiences. `ru/index.html` and `fr/index.html` now render the English
homepage's news-front layout — **the same stylesheet** (`_landing_styles.html.j2`,
extracted from `network_page.html.j2`; the English render is byte-identical)
and **the same assembler** (`engine.landing_test.assemble`) — over the
stories that exist in the language (`engine/language_front.py`): a native
show's episodes as the English page would run them, and for each English show
with a translated track, every episode that has one — the headline is the
TRANSLATED title/description the multilingual stage wrote beside the track
(`translated_hook`: the description's first complete sentence, since the feed
title is clipped to 100 characters), the audio is the translated MP3, the
picture is the episode's own scene matched on the English hook, the article
link is the English post (which carries the language switcher), and "Also in
this episode" is empty because those headlines exist only in English. Up to
`STORIES_PER_SHOW` (3) episodes a show so a seven-show page has a lead, top
stories and sections; the flagship band keeps one card per flagship. Dates,
the masthead and the subject headings are written in the language
(`MONTHS` / `WEEKDAYS`; `section_headings` in `_LANGUAGE_HUB_COPY`), the
English topic hubs are never linked, and `engine.brand.NETWORK_TAGLINE_FR`
joins the RU tagline. A guard strips the headlines and asserts the Russian
page's own copy carries no English word. Guards:
`TestLanguageFrontPages` in `tests/test_site_languages_2026_10_18.py`.
