# Network sourcing pass (2026-09-24)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

- **Network sourcing pass (2026-09-24; guards
  `tests/test_network_sourcing_pass_2026_09_24.py`; register
  `network-sourcing-pass-2026-09-24`). ⚠️ The digest INPUT changed on ten
  shows — A/B-listen the first post-merge episode of each.** The launch
  cohort's sourcing floor, ported to every established news show, after the
  audit found the flagships recording 0 claims on 7 of their last 10
  episodes each and `fetch_full_text: 0` on 14 of 15 shows (the digest
  prompt had headline + teaser only — the Offshore North finding, network
  wide). Now: `fetch_full_text` 8–12 on tesla, spacex, models_agents, MAB,
  FF, planetterrian, omni_view, env_intel, modern_investing, finansy_prosto;
  `preferred_domains` (primary publishers: regulators, journals, the labs'
  and companies' own newsrooms, the wires) on each; `x_posts_as_sources:
  secondary` where the show does not own the story (**Tesla and SpaceX stay
  legacy — their own posts are primary**); the `x_only_lead` lint where a
  `LEAD_SECTIONS` header exists (replay: 1 firing in 60 digests).
  `evidence_rung` is deliberately NOT on FF / planetterrian: its rung
  vocabulary is biomedical and it fired on 15–19 items per six digests of
  astronomy and paleontology. The narrative shows, the Russian lesson show
  and the hook_shape arm/control experiment are untouched (guarded).
  **Listeners:** `engine/show_notes.py` appends a linked `Sources:` line
  (publisher domains, publishers before social posts, max 8) to every
  episode's RSS description — the feed copy had every Source line scrubbed
  while the blog listed them (metric `show_notes_sources`). **Readers:**
  `script_commas_per_100w` / `digest_commas_per_100w` in `engine.script_audit`
  and a snapshot column. **Members:** `PERSONAL_EXTRA_SHOW_SLUGS` widens the
  Nerra Personal vocabulary to the 13-show cohort (Worker list mirrored;
  `personal_edition_spec()` is what the builder discovers on; the Nerra
  Daily lineup is unchanged). Feed hygiene from `check_feeds.py` over the
  established shows: CNBC's two feeds (403 on every UA) moved to CNBC's
  search endpoint, Space.com's two dead RSS URLs became one Google News site
  query, two zero-item Google News queries simplified; the reddit 429s, NPR
  403s and news.gov.bc.ca TLS failures are this container's egress and were
  left for a runner read. Operator: `wrangler deploy` in `workers/gallery`
  for the Personal picker.
