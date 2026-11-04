# The Oct 24 slate: a retold story is one story told twice (Oct 24 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### The Oct 24 slate: a retold story is one story told twice (Oct 24 2026)

Review [`docs/reviews/slate_review_2026_10_24.md`](docs/reviews/slate_review_2026_10_24.md);
register `slate-2026-10-24`; guards `tests/test_slate_2026_10_24.py`. Every
due show published, 10/10 videos, Nerra Daily complete. Rules that bind:

- **A cluster is retold only when ONE of its stories is told as two items.**
  `retold_clusters` matches items against each member's CORE (the words it
  shares with the lead). The digest's furniture (words in ≥50% of item
  headlines, from 8 titles) and bare numbers never count. A roundup lead
  touching three stories had made them one "retold" story on Tesla Ep644.
- **A retry run only for clusters must lower the count**
  (`_cluster_retry_worse(must_improve=)`). Ep644's retry cut the digest
  1,591 → 1,210 prose words, fixed nothing, and shipped.
- **A prompt-block label states a fact, never an instruction:** the model
  copies labels into the digest, and MIT Ep210 printed "call it an earlier
  hold, never the last one".
- **13F notices are dropped by URL as well** (`marketbeat.com/instant-alerts/filing-`).
- **Parentheses inside a URL the model wrote are encoded**
  (`encode_url_parens_in_text`, first step of `transform_daily_body`).
  17 committed digests carried a link cut at one.

Rejected after measuring: dropping an empty bold item line (it also removed
disclaimers and "Read more" labels on 31 digests). Same day, operator-
directed: the spoken-open experiment was ENDED unscored (n=1 retention curve
per arm) and its four control prompts took `_shared/hook_shape.txt`; Omni
View and MIT had regenerated their digest for an over-long hook on 13 of
16 days while they waited. ⚠️ AUDIO — A/B-listen the first episode of each.
