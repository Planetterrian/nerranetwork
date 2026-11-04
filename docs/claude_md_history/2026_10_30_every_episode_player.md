# Every episode player is the site's player (Oct 30 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Every episode player is the site's player (Oct 30 2026)

Patrick, on an iPhone: the blog post's listen box was "a whited out box" and
the show pages' players looked missing (register
`site-episode-player-2026-10-30`; guards `tests/test_inline_player_2026_10_30.py`).
Rules that bind:

- **`nn-listen` is the Listen BUTTON's class, and its rules are
  `button.nn-listen`.** The blog box was `<section class="nn-listen">`, so the
  pill rules collapsed it. The box is `.nn-episode-listen` now. Committed
  posts keep the old class, and the scoped rules leave it alone.
- **`nn-player.js` takes over every `audio[controls]`** (`enhanceInline`),
  except inside `noscript`, `.lt-lead-audio` (the Listen pill), the player bar
  and the summaries page's `.nn-sticky-audio`. `data-nn-native` opts an
  element out.
  - The page's one player becomes an episode card: cover, show, title,
    state, play, -15/+30, a scrubber and speed. This applies to
    `data-nn-card`, `#nn-i18n-audio`, `#latest-audio` and the interview
    player.
  - Archive audio becomes a row.
  - Rows play as one queue in page order, through the shared audio element.
  - The native element stays hidden in the HTML (no-JS, the language
    switcher and the chapter links write to it). Its `play` is turned into
    a play through the engine, and a changed `src` re-syncs the card.
  - `data-title` / `data-show` / `data-cover` / `data-nn-title-from` name the
    episode. `CARD_IDS` reads the title on pages built before them.
- **A page script plays a page's audio through `NNPlayer.playElement(el, s)`**
  (the blog chapter links do), so the hidden native element never fetches
  the file a second time. It returns false when there is no card.
- **The players' own text updates are not new content** for the body
  observer, and `inlineSync` writes only on change. A write is a mutation,
  and the observer calls back into it.
- Posts built before Oct 28 do not load `nn-player.js` and keep the native
  control until their show rebuilds them.
- **A deploy reaches a returning visitor on their next page** (later the same
  day: Patrick's iPhone still showed the white bar on Ep071 after the merge).
  `sw.js` serves `styles/` and `assets/js/` NETWORK FIRST (cache only for a
  dead connection, query ignored on the fallback); fonts, covers and icons stay
  stale-while-revalidate. Stale-while-revalidate on scripts meant the first
  page after every deploy ran the previous code. Version `nn-2026-10-30`.
- **The browser's own control never shows before the player replaces it**:
  iOS ignores `color-scheme` on `<audio>`, so `base.html.j2` sets `html.nn-js`
  in the head and `audio[controls]` stays `visibility: hidden` until
  `nn-player.js` adds `nn-ip-ready`; after five seconds without it
  (`nn-ip-off`) the control comes back. "Listen to podcast" (`a[href="#listen"]`)
  plays the card instead of only scrolling to it.
