Saturday single-story edition is not shipping (Ep019/Ep025 ran full Tens), scripts remain ~900–1500 words against a 1750/12-minute promise that the 5+5 format cannot carry, Ep023 Both Sides placed Albania’s Edi Rama story in Toronto, and Progress Watch absence was spoken on Ep018 against an explicit skip rule.

_Generated on **grok-4.5** by `scripts/run_show_review.py` (replaces the Claude-Opus review agent). Estimated cost: **$0.1146**._

## Scored prior predictions
| Prediction | Verdict | Evidence |
|---|---|---|
| Mira claims a body, a home, a trip or an event witnessed (transcript read) | hit | Ep018–027: only the stock AI-host identity line; no body/home/witness claims in transcripts |
| Both Sides states or implies which side is stronger, or picks a party, government or people | hit | Sampled Both Sides (Ep018 diesel, Ep021 Brazil work-week, Ep025 Canada tariffs) attribute both cases and withhold a winner |
| Progress Watch carries a promise or announcement of intent instead of a measured result | hit | Present PW items are measured (EAEU tariff cut, Pope recovery labs, PH solar imports $407M, China 4.5% GDP); not intent-only |
| episodes (first 7) with an item whose subject is outside the world and carries no stated consequence inside it | partial | Ep1–7 digests not in bundle; Ep018–027 selection is consequence-ranked world news only |
| Top World episodes whose articles_from_hook is 0 on a day at least three desks published | partial | No hook-article / desks_live metrics in bundle; hook code path still injects publisher URLs from desks |
| desks_live_at_publish on a weekday | partial | Metric not present in provided episode artifacts; cannot confirm 5-of-7 after members-only desk move |
| episodes whose claims verified against a publisher URL (not a sibling digest) | partial | No claims ledgers in bundle; items_without_source lint configured network-side after Ep2 |
| Saturday edition validates as one story of >= 1,800 chars | miss | Ep019 (Sat 2026-10-11) and Ep025 (Sat 2026-10-17) both shipped multi-item Tens, not single-story The Story |
| script words | partial | Ep2–8 absent; Ep018–027 median ~1260 clears old ≥1200 target but 9/10 miss the current 1750 floor |
| episodes recording llm_model_fallback | partial | No credit-usage / model-arm fields in bundle for Ep3–9 |
| structural retries that changed the model arm | partial | No run logs in bundle; resilience change described as shipped in ledger only |
| claims on a completed 4.7 episode | partial | No per-episode claims counts or llm_model fields in bundle |
| published cohort digests with zero Source lines | hit | items_without_source lint on show; no zero-source symptom in Ep018–027 set; Ep2 was the repaired baseline incident |

## ⚠️ A/B-listen required — NOT applied (landmine #17)
These prompt/audio changes are **proposals only**. Apply them yourself, render/listen, then merge if they sound right.

**`shows/prompts/omni_view_world_podcast.txt`** (prompt) — Ep023 shipped Albania/Edi Rama under 'Toronto'/'Eddie Rahma'. Shape rule + verbatim place discipline; no phonetic respelling (landmine #17). A/B-listen required.
```diff
- [Both Sides] A second story, not a second pass. Its first sentence contains "the case on both sides" once, inside a natural sentence (podcast-app chapters key on it). The strongest case each way, each attributed by name, then the next step. Skip the segment when its story is one already told today, or when the briefing names no person or body on one of the two sides. Never say which side is stronger.
+ [Both Sides] A second story, not a second pass. Its first sentence contains "the case on both sides" once, inside a natural sentence (podcast-app chapters key on it), and names the same country and city the briefing uses for that dispute — never a substitute city (if the briefing says Tirana or Albania, do not say Toronto). The strongest case each way, each attributed by name, then the next step. Skip the segment when its story is one already told today, or when the briefing names no person or body on one of the two sides. Never say which side is stronger.
```

## Code/metadata-only proposals (no A/B needed)
- **`engine/digest_lint.py`** (code): Ep019 and Ep025 prove the model ignores Saturday edition_note; meta-review favors deterministic fetch/lint fixes over more prompt pressure. No audio change until a Saturday regen passes the lint.
- **`shows/omni_view_world.yaml`** (config): Opt the show into the new Saturday structural lint so a multi-item Saturday cannot publish.
- **`tests/test_omni_view_world_quality_pass.py`** (code): Every behavioral fix needs a drift-guard; runway rule avoids red main on same-day shape.
- **`engine/chapters.py`** (code): Ep023/Ep025 app chapters expose a section label the podcast prompt forbids speaking; metadata-only, no TTS field changes.

## Deferred (carried forward)
- Operator decision: keep 5-developed+5-one-line format and lower min_podcast_words + RSS 'twelve minutes' to match median ~1200–1400, OR deepen items 6–10 / cut to 8 stories and only then keep 1750/12 min — do not ship another podcast-side length lever
- 8-story vs 10-story cut after 4 weeks of first-week download data (ledger carry-forward)
- Re-grade world feeds from a runner (check_feeds.py omni_view_world)
- YouTube enable is a data decision (plan §7; youtube.enabled still false)
- Surface desks_live_at_publish on the management dashboard now that desks are members-only
- Any prompt-only 'write longer' / podcast_expand_below_target / word-floor pressure (network do_not_retry from length meta-review)

<sub>tokens: 40344 in / 5658 out</sub>