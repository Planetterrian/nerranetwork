# Landmine 18a — Newsletter dark-mode CSS must stay SCOPED (v3, June 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

18a. **Newsletter dark-mode CSS must stay SCOPED (v3, June 2026)** —
    the iPhone dark-mode bug (subject title, "NERRA NETWORK · date"
    byline, forward line, and unsubscribe footer rendering white-on-
    light = invisible; operator screenshots Jun 9 2026, after several
    failed fixes) was caused by GLOBAL selectors in the dark-mode
    `<style>` block (`h1 { color:#fff }`, universal `p/td/div/span`
    text flips, td-style-attribute background matches). Those rules
    leak onto **Buttondown's own wrapper**, whose backgrounds we cannot
    flip. v3 contract in `engine/newsletter_template.py`:
    `wrap_with_branding` stamps every emitted table/div with the `nn`
    marker class (`_scope_nn`), and every color rule inside the
    `@media (prefers-color-scheme: dark)` block is scoped under `.nn`
    (surface classes like `.surface-white` are ours alone and stay
    class-targeted). Buttondown chrome keeps its native always-readable
    colors; our cards adapt. The `:root/body { color-scheme: light
    dark }` opt-in stays — removing it regresses to Apple Mail's
    auto-transform (washed-out headings, the original May 2026 bug).
    Drift guards: `tests/test_newsletter_template.py::TestDarkModeScoping`
    (no unscoped color selectors, no attribute background selectors,
    every block carries `.nn`).
