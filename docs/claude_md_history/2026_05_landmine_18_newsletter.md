# Landmine 18 — Newsletter pipeline spec v2 (May 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

18. **Newsletter pipeline spec v2 (May 2026)** — multi-day refinement
    pass on the Buttondown send pipeline addressing contrast bugs,
    LLM scaffold leaks, and daily-vs-weekly template parity. Files:

    - **`engine/newsletter_sanitizer.py`** (new) — regex blocklist of
      known LLM scaffold patterns (`**HOOK:**`, `**Date:**`,
      `ЗАГОЛОВОК:`, `**The Surprising Truth:**`, box-drawing rules
      `━━━`, etc.) plus a hard tripwire (`assert_clean`) that blocks
      send if any pattern survives scrubbing. Run by
      `send_show_newsletter` before the wrapper sees the body.
    - **`engine/url_utils.py`** (new) — strips C0/C1 control chars
      from RSS-scraped URLs (the `?ito\x14` bleed), and resolves
      Google News redirect URLs (`news.google.com/rss/articles/CBMi…`)
      to their canonical publisher form at fetch time. Both ops are
      best-effort; failures pass through unchanged. Wired into
      `engine/fetcher.py`'s per-article loop.
    - **`engine/newsletter_body.py`** (new) — body-text transforms
      applied between scrub and wrap: box-rules → `<hr>`, Tesla
      `**REAL-TIME TSLA price:**` → styled stock-watch block, Russian
      vocabulary list (Привет) → card stack, Omni View "Read more"
      duplicate-URL dedup.
    - **`engine/contrast_validator.py`** (new) — WCAG 2.1 AA tripwire
      that walks rendered HTML, checks every inline `color:` against
      its nearest-ancestor background. Currently a soft warning in
      `send_show_newsletter` (logs but doesn't block) so we can
      calibrate against real renders before flipping to hard-block.
    - **`engine/newsletter_template.py`** — surgical template fixes:
      hero pill is now a `<table>` with `bgcolor` instead of an
      `rgba()` div (Outlook fix); cover `<img>` carries inline
      `color/font-size/font-weight` so alt-text fallback is readable;
      VML wrapper added for Outlook gradient fallback; dark-mode
      `<style>` block expanded with per-brand-color tokens
      (`.brand-text-tesla` / `.brand-text-mit` / etc.) and surface
      classes (`.surface-white` / `.card` / `.preheader`) to win the
      inline-style override war on Outlook iOS / mobile Gmail; light-
      mode `#94a3b8` / `#64748b` muted greys swapped for `#475569`
      where they appeared as primary text (3.0:1 → 6.4:1 on white);
      P.S. block re-styled with dashed top-border separator + italic
      body; cross-network show names are now full-row clickable
      links; new `_build_view_in_browser_html` partial at top of
      body and `_build_issue_counter_html` per-show counter just
      above Buttondown's auto-footer.
    - **`engine/newsletter.py:send_show_newsletter`** — full daily-
      caller overhaul. Subject line uses
      `build_subject_line(hook_max_chars=50, is_daily=True)` for the
      same `<hook> · <show> <emoji>` shape as weekly (replaces the
      broken `f"{config.name}: {hook}"`). Body is scrubbed → body-
      transformed → wrapped with the same hero / featured-episode /
      P.S. / cross-network / reply-share blocks weeklies use.
      Russian shows render the disclaimer and reply/share copy in
      Russian via the localised `_build_financial_disclaimer_html` /
      `_build_reply_share_html` paths. Buttondown ``slug`` is set
      explicitly for Russian shows using a GOST-7.79 Cyrillic→Latin
      transliteration map so archive URLs read as
      ``privet-russian-ep018-kosmos-9-russkikh-slov`` instead of
      ``u041f-u0440-u0438-…``. Same-day double-send guardrail: each
      show writes a `digests/<slug>/_newsletter_lastsend.txt` after
      a successful send; the next call refuses to re-send within
      20 hours (catches the May 2 Привет Ep 17 + Ep 18 double-send).
    - **`shows/prompts/omni_view_digest.txt`** — the "Read more
      (sources)" instruction now explicitly forbids three identical
      URLs under three different descriptions (the May 2 daily
      shipped with `[Daily Mail](https://...)` × 3). The
      `dedup_read_more_sources` body transform is the
      defense-in-depth layer.

    Operator workflow: nothing changes for the daily cron — it still
    calls `send_show_newsletter`. The added safety gates (sanitizer,
    contrast validator, send guardrail) are defensive — they log
    loudly when they fire so the operator can chase the upstream
    cause (a regressed prompt, a fetcher bug, or a scheduler race).
    The `ELEVENLABS_API_KEY` and legacy ElevenLabs settings in
    `_defaults.yaml` remain untouched — separate concern.
