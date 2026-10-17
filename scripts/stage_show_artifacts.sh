#!/usr/bin/env bash
# Stage one show run's generated artifacts for commit.
#
# Shared by the workflow's "Commit and push output" step and the audio-first
# checkpoint (scripts/checkpoint_publish.sh, Oct 17 2026), so the two can
# never stage different things. Moved verbatim from run-show.yml; the
# reasons for each path are kept beside it.
#
# Run from the repository root. Never fails: every add is best-effort.

set -u

# Stage all generated output
git add -A digests/ || true
git add '*.rss' || true
git add '*.html' || true
git add -A blog/ || true
git add sitemap.xml || true
# Tesla cached price for the public website widget. Written
# by ``shows/hooks/tesla.py`` every Tesla run, consumed by
# ``tesla.html`` JS so the stock pill doesn't depend on
# Yahoo Finance CORS proxies.  Without committing this, the
# file gets wiped on every fresh runner checkout and the
# website shows "Market data unavailable" between runs
# (operator caught this May 15 2026, TST Ep473).
git add api/tsla.json || true
# Tesla data dashboard (live TSLA market data + price history)
# written by shows/hooks/tesla.py, consumed by tesla-dashboard.html.
git add api/tesla_dashboard.json || true
# SpaceX cached SPCX price — same contract as api/tsla.json
# above. Written by ``shows/hooks/spacex.py`` every SpaceX run,
# consumed by ``spacex.html`` JS so the SPCX pill has a
# reliable same-origin source between runs.
git add api/spcx.json || true
# SpaceX launch-dashboard data (next/previous launch, cadence,
# stats) for spacex-dashboard.html. Same reliability contract.
git add api/spacex_launches.json || true
# Offshore North campaign dashboard data (latest team posts +
# newest dated position fix + headlines) — refreshed by the
# Offshore North run's fetch step below and nightly; the page
# offshore-north-dashboard.html reads it same-origin.
git add api/offshore_north_dashboard.json || true
# MAG 7 Daily's validated regular-session closes (shows/hooks/
# mag7.py). Named *_quotes so it can never collide with the
# per-show public API file api/mag7.json (Sep 22 2026: that
# collision sent MAG 7 Ep1 to a recovery PR).
git add api/mag7_quotes.json || true
# Growing SpaceX metrics time-series (monthly mass-to-orbit,
# satellites, vehicle mix) — accumulates over time to power the
# dashboard's long-run growth charts.
git add site/data/spacex_metrics.json || true
# Topic queues — narrative-mode shows mark topics as produced
# after each successful run. Without committing this, every
# narrative-show run re-picks the same first-unproduced topic
# because the runner sees a stale queue on every fresh
# checkout. (Bug caught May 2026 when UC Ep001 was about to
# ship Cobra Effect twice.)
git add -A shows/topic_queues/ || true
# Deep-dive queues — same persistence requirement as topic_queues.
# A deep-dive run marks its entry produced in shows/deep_dives/<show>.yaml;
# without committing it the entry stays ``when: next`` and the deep dive
# RE-FIRES on the next run (caught May 2026: SpaceX Ep059/Ep060 each
# re-queued because this directory wasn't staged).
git add -A shows/deep_dives/ || true
# Curriculum spotlights (Sep 2026: Peptides Weekly, Longevity
# Weekly) — the hook marks the week's spotlight produced; same
# persistence requirement as topic_queues or the next run re-picks it.
git add -A shows/curricula/ || true

# Exclude MP3 files (hosted on R2, not in git)
git reset HEAD -- '*.mp3' 2>/dev/null || true

# Exclude the regenerable CROSS-SHOW aggregate files. These are
# rebuilt from committed per-show data by the finalize job, which
# owns them exclusively. Committing them here too caused concurrent
# show jobs to collide on these exact files (June 27 2026: Tesla +
# Modern Investing lost the push race, the rebase couldn't auto-merge
# them, and both fell back to recovery branches). Per-show feeds /
# pages (podcast.rss, blog_<show>.rss, <show>.html, blog/<show>/*)
# are NOT aggregates and still commit normally.
#
# IMPORTANT: use `git checkout HEAD --`, NOT `git reset HEAD --`.
# The per-show steps above (Regenerate network RSS / show HTML) have
# already MODIFIED these files in the working tree. `git reset` only
# unstages — it leaves them dirty, which then makes the push-retry
# `git pull --rebase` abort with "cannot pull with rebase: you have
# unstaged changes" and the merge fallback abort with "local changes
# would be overwritten by network.rss". That regression (June 27)
# sent ~7/8 shows to recovery branches on June 28. `git checkout
# HEAD --` reverts index AND working tree to HEAD, leaving a clean
# tree so the rebase can replay onto the latest main.
#
# Restore each aggregate INDIVIDUALLY (July 2026): a single
# multi-path `git checkout HEAD -- a b c` is all-or-nothing — if any
# one path is absent from HEAD, git rejects the whole pathspec, the
# 2>/dev/null hides it, and the tree stays dirty → the exact June 28
# mass-stranding mode above re-triggers.
for aggregate in blog.rss network.rss blog/index.html; do
  git checkout HEAD -- "$aggregate" 2>/dev/null || true
done
