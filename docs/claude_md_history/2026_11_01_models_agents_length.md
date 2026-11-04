# Models & Agents: its natural length, and the names from the digest (Nov 1 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Models & Agents: its natural length, and the names from the digest (Nov 1 2026)

Operator decisions on the Oct 31 review (register
`models-agents-length-names-2026-11-01`; guards
`tests/test_models_agents_length_names_2026_11_01.py`). Rules that bind:

- **1,200-1,400 words is the show's natural length** (option C):
  `min_podcast_words` 1200 (the bottom of that range; the YAML floor
  sits at or under the prompt's stated low end) and the prompt says the
  briefing sets the length. **The skip floor stays at 900**, pinned with
  `min_podcast_publish_words`, so the lower target never lowers it.
- **The names are data, not an instruction** (`engine/names_to_keep.py`,
  opt-in `names_to_keep: true`): the two-pass script prompt gets
  `{names_to_keep_block}`, the names today's digest carries as written,
  in order. A title-case headline or a bold label is not a list of names;
  a headline only vouches for a name that opens a sentence. No model
  call; "" on the combined path and on every show that has not opted in.
  Three prose passes had missed names-kept >= 75%. ⚠️ AUDIO: A/B-listen
  the first episode.
- **The section-chapter wiring the review re-filed three times is
  rejected**: replayed over Ep211-221 it replaced a story's headline
  chapter with a section label on every episode (ledger `do_not_retry`).
