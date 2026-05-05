# Nerra Network — Design system

Single source of truth for the website's visual language. Designed dark-first
with the CSS custom properties in `styles/main.css` and `:root` defaults.

## Typography

| Role | Font | Weights |
|------|------|---------|
| Headings | DM Sans | 600, 700 |
| Body / UI | DM Sans | 400, 500 |
| Blog body copy | Source Serif 4 | 400, 600, 700 |
| Code / snippets | SFMono-Regular, Consolas, ui-monospace | — |

Custom properties (set on `:root`):

```css
--font-heading: 'DM Sans', system-ui, sans-serif;
--font-body:    'Source Serif 4', ui-serif, serif;
--font-ui:      'DM Sans', system-ui, sans-serif;
```

## Colour tokens

All colours are defined as CSS custom properties on `:root` in
`styles/main.css`. Never hard-code colours in templates — always reference
a token.

### Core palette

| Token | Value | Usage |
|-------|-------|-------|
| `--nn-purple` | `#6B47FF` | Primary brand accent, gradient anchor |
| `--nn-cyan` | `#00D4FF` | Secondary brand accent, link hover, gradient end |
| `--nn-white` | Near-white | Hero headings, emphasis on dark surfaces |
| `--nn-text` | Light neutral | Body copy |
| `--nn-text-muted` | Mid neutral | Captions, meta, deprioritised text |
| `--nn-border` | Subtle line | Card edges, dividers |
| `--nn-border-hover` | Brighter line | Card hover state |
| `--nn-card` | Dark translucent | Surface for cards, inputs, chips |
| `--nn-surface` | Darker translucent | Pressed/active surface |
| `--show-color` | Per-show brand | Set on `:root` at build time via `<style>:root { --show-color: ... }` |
| `--show-color-dark` | Per-show brand (dark) | Secondary per-show accent |

### Gradient

```
linear-gradient(135deg, #6B47FF 0%, #00D4FF 100%)
```

Used for: hero headings (text-fill), stat-value emphasis, primary CTA accents,
network logo wordmark. Do **not** invert for a text-on-gradient button; use
`--nn-white` on gradient background instead.

### Dark mode / light mode

The site is **dark-first**. Light mode via `prefers-color-scheme: light` is
intentionally not supported — the brand relies on the dark surface + neon
gradient for contrast. If we ever add a light mode it must override every
`--nn-*` token in a `:root` block within `@media (prefers-color-scheme: light)`
and revalidate WCAG contrast on every text/background pair.

### Reduced motion

`@media (prefers-reduced-motion: reduce)` is honoured at two locations in
`main.css` (the hero orbit animation + the ticker). Any new animated element
must be gated behind the same media query.

## Spacing scale

Based on a 4px grid. Use `--sp-*` tokens, never raw pixels.

| Token | Value | Typical use |
|-------|-------|-------------|
| `--sp-1` | 4px | Gap between inline elements |
| `--sp-2` | 8px | Small internal padding |
| `--sp-3` | 12px | Card-internal spacing |
| `--sp-4` | 16px | Default padding, card gap |
| `--sp-5` | 20px | Card padding on mobile |
| `--sp-6` | 24px | Card padding on desktop, section padding |
| `--sp-8` | 32px | Section top-margin |
| `--sp-10` | 40px | Section bottom-margin |
| `--sp-12` | 48px | Hero section padding |
| `--sp-16` | 64px | Page-level hero padding |
| `--sp-20` | 80px | Above-the-fold breathing room |

## Accessibility

- **Minimum tap target:** 44×44 px on every interactive element
  (WCAG 2.5.5). `.nn-filter-btn`, `.nn-speed-btn`, `.nn-summary-link`,
  `.picker-chip`, `.nn-sticky-close` all meet this. Enforce on any new
  control.
- **Focus outline:** keep the browser default `:focus-visible` outline
  unless you explicitly replace it with a `box-shadow` that meets 3:1
  contrast against the surface.
- **Alt text:**
  - Decorative images (logo next to visible brand text): `alt=""`
  - Content images (cover art standalone): `alt="{Show name} cover art"`
- **Skip link:** `<a href="#main-content" class="skip-link">` is rendered
  on every page and becomes visible on first Tab. Do not remove.
- **Form labels:** text inputs need `aria-label` or associated `<label for>`;
  checkboxes must be wrapped in `<label>` or have `for="id"`.
- **Language signal:** `<html lang="{{ page_lang | default('en') }}">`
  — Russian shows must pass `page_lang="ru"` so assistive tech and
  search engines pick the right language.

## Components

### Buttons

- **Primary:** `.nn-btn.nn-btn-primary` — gradient fill, white text.
- **Secondary:** `.nn-btn` — transparent, bordered, `--show-color` hover.
- **Large:** `.nn-btn-lg` — used in hero CTAs.
- **Filter chip:** `.nn-filter-btn` — min 44×44, active state uses `--show-color`.

### Cards

- **Glass card:** `.glass-card` — translucent + backdrop-blur.
- **Show card:** `.show-card` — hover lifts + border colour-morphs to `--show-color`.
- **Summary card:** `.nn-summary-item` — podcast episode card with inline audio.

### Navigation

- **Primary nav:** `.nn-nav` — sticky, blurred backdrop on scroll.
- **Mobile menu:** `.nn-mobile-menu` — full-screen slide-in, toggled by
  `.nn-hamburger` with `aria-expanded`.
- **Footer:** `.nn-footer` — column grid that collapses to stacked on
  `≤ 768px` with click-to-expand headers.

## Adding new components

1. Reuse tokens (`--sp-*`, `--nn-*`). Never hard-code colour or spacing.
2. Meet the 44×44 tap target if interactive.
3. Add `aria-label` to icon-only buttons.
4. Gate any new animation behind `prefers-reduced-motion: reduce`.
5. If the component uses per-show accents, read from `--show-color` with a
   fallback: `color: var(--show-color, var(--nn-purple));`.
6. Test at 320 px (iPhone SE portrait), 768 px (tablet), 1280 px, 1920 px.

## Build pipeline

Pages are generated by `generate_html.py` from Jinja2 templates in
`templates/`. The base template `base.html.j2` wires GA4, consent mode,
skip link, nav, footer, and all meta tags — show pages only override
`block head_extra`, `block content`, and `block og_type` (Jinja2 blocks).

Regenerate everything with:

```bash
python generate_html.py --all
```

Or a single show:

```bash
python generate_html.py --show tesla
```

## Changelog hooks

When you change a token in `:root`, also grep for any template that
hard-codes the old value and update it. The hand-written pages
(`privacy-policy.html`, `terms-of-service.html`, `ai-disclosure.html`,
`modern-investing-resources.html`, `ru/index.html`, `podcasts/index.html`,
`management.html`) are NOT auto-regenerated and must be updated manually.
