# Site-showcase video endings (Aug 2026, operator-directed)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Site-showcase video endings (Aug 2026, operator-directed)

Every long-form video now ends on a 1920×1080 **outro card** built from
real nerranetwork.com screenshots (the show's page + the network home
page, framed side by side), the URL in Nerra cyan, a localized (en/ru/fr)
newsletter line, and a QR to the funnel-tagged show page
(`utm_content=outro` — new `PLACEMENT_OUTRO` in `engine/funnel.py`'s
closed vocabulary). Shorts end cards paste the home page's show-grid
band as a framed strip above a cyan URL footer. Module:
[`engine/promo_card.py`](engine/promo_card.py); overlay threaded through
BOTH long-form command builders in `engine/video.py` (two-pass +
single-pass; no-outro args are byte-identical legacy, pixel-verified on
real renders). Screenshots are **committed** at `assets/site_screens/`
(the render never hits the network) and refreshed by
`scripts/capture_site_screens.py` — a show without its own `show_<slug>`
shot falls back to the network-home card, and a channel lander
(`ru_spacex.png`) wins for that channel's dubs. `qrcode` is in
requirements but optional at runtime (card ships without a QR). Config:
`youtube.outro_card_enabled` / `outro_card_duration_seconds` /
`shorts_end_card_site_panel` (defaults on in `_defaults.yaml`).
Render/metadata only — outside landmine #17; best-effort everywhere
(any failure ships the legacy ending). Registered as the
`site-outro-cards` experiment (readout 2026-08-23). Drift guards:
`tests/test_site_showcase.py`.
