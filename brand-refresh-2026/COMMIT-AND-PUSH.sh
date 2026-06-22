#!/usr/bin/env bash
# Brand refresh — finish the commit + push from YOUR machine.
# (The Cowork sandbox couldn't do this: it can't delete .git/index.lock and has no SSH key.)
# All edits + asset copies are ALREADY in your working tree on branch `brand/refresh-2026`.
set -e
cd "$(git rev-parse --show-toplevel)"

# 0. Make sure you're on the branch the work is on
git switch brand/refresh-2026

# 1. Clear the stale lock the sandbox left behind (safe: no git process is running)
rm -f .git/index.lock

# 2. Stage exactly the brand-refresh changes (not .claude/settings.local.json)
git add generate_html.py \
        templates/network_page.html.j2 templates/base.html.j2 templates/press.html.j2 \
        assets/nerra-logo-icon.svg assets/nerra-favicon.svg \
        assets/nerra-logo-horizontal.svg assets/nerra-logo-horizontal-light.svg \
        assets/nerra-logo-stacked.svg assets/nerra-mark-mono.svg assets/og-preview.png \
        brand-refresh-2026

# 3. Commit
git commit -m "Brand refresh: refreshed mark + OG image, count-agnostic copy, 4 languages

- Header/JSON-LD logo + favicon -> refreshed constellation mark
- assets/og-preview.png -> new 1200x630 share card
- Homepage hero/stats/footer/about + page meta: remove exact show count
- Languages corrected to 4 (English, French, Russian, Chinese)
- Add full brand system to /brand-refresh-2026/ (board, guidelines, SVGs, PNGs)"

# 4. Your local clone is ~a week behind origin. Fold this onto current main.
#    Expect ONE likely conflict: the homepage 'Multilingual' card text already
#    changed on origin — keep the wording that lists English/French/Russian/Chinese.
git fetch origin
git rebase origin/main   # resolve conflicts if prompted, then: git rebase --continue

# 5. (Recommended) regenerate the static HTML so the live pages reflect the edits.
#    Use whatever your pipeline uses; typically:
# python generate_html.py
#    Then: git add -A && git commit -m "Regenerate site for brand refresh"
#    (If you skip this, the nightly 'Update shared pages' job will regenerate after merge.)

# 6. Push the branch and open a PR
git push -u origin brand/refresh-2026
echo "Now open the PR on GitHub (compare brand/refresh-2026 -> main) and merge when happy."
