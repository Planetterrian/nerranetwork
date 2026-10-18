# Members-only limited series

Oct 18 2026, operator-directed. A limited series is a set of long, sourced
episodes on one subject. It is produced once, delivered to every paying
Nerra Personal member, and teased on the free surfaces of the shows it
belongs to. Code: `engine/specials.py`, `scripts/produce_special.py`,
`scripts/release_special.py`; workflow **Members-only series**
(`.github/workflows/produce-special.yml`).

## The two series

| Series | Host | Teaser shows | Episodes |
|---|---|---|---|
| `spacex-tesla-merger`: SpaceX and Tesla: The Merger Question | SpaceX Daily | SpaceX Daily, Tesla Shorts Time | 7 |
| `peptides-deep-dives`: Peptides, One at a Time | Peptides Weekly | Peptides Weekly, Longevity Weekly | 17 |

The merger series has seven parts:
1. the two companies today;
2. how a combination would actually be done;
3. the industrial logic;
4. control, pay and governance;
5. Washington, security and the regulators;
6. the case for;
7. the case against.

The peptides series opens with an episode on how to read peptide evidence and the grey market, then gives one episode per peptide. Every peptide episode answers the same eight questions, so the series reads as one reference work.

Each series is defined in `specials/series/<id>.yaml`, and its editorial rules are in `shows/prompts/specials/<id>_rules.txt`. The briefs are research instructions, never facts to repeat.

## How an episode is made (produce: private)

1. **Research.** Every research question in the episode runs as a web search. Each result is a lead: its page is fetched, and only pages actually read (600+ characters) become numbered sources. Social posts never do. If the episode gets fewer than the series' `min_sources` (merger 12, peptides 10), it does not produce; it is never written from memory.
2. **Dossier.** A sourced research dossier of 2,800–3,800 words with a claims ledger. Every finding cites a source number, and conflicts and open questions are findings.
3. **Claims gate in flag mode.** This follows network policy (publish and mark). Claims verify against the fetched pages first, then over HTTP. `claims.json` records every claim's status.
4. **Blocking lints.** Peptides carries `dose_terms`: a dossier or script that states a dose, route, preparation or protocol gets one regeneration, then the episode fails.
5. **Script.** The script is written only from the dossier: 3,900–5,000 words, about 25–35 minutes. It is spoken by the host show's voice and closes on the network's spoken AI disclosure. A script under 3,300 words fails; there is no expansion retry, because length is a dossier-side lever.
6. **Audio.** TTS, then the spoken-text gate (one re-synthesis), then the host show's music. The MP3 goes to the **private** bucket under `specials/<series>/`.
7. **Trailer.** Once every part exists, a ~90-second trailer is written, voiced and uploaded to the **public** bucket (`specials/<series>/…-trailer.mp3`). No feed points at it yet.

The episode text (sources, dossier, claims, script) is committed under `specials/<series>/<NN-episode>/`, like the gated shows' text. Only the audio is private. `specials/catalog.json` is the record every consumer reads.

Run it from Actions: **Members-only series**, with `action: produce`. Episodes run one at a time and are committed after each, so a timeout keeps what finished and a re-run resumes. `text_only` stops before audio, so you can read the scripts first.

## Release (public, after listening)

Run **Members-only series** with `action: release`. It:
1. marks the series released. From the next Personal builder run, every paying member's feed carries every episode as bonus items. The builder copies each MP3 into the member's own `personal/<token>/` keyspace, so no Worker change is needed;
2. adds the trailer at the top of each teaser show's free feed, as an `itunes:episodeType trailer` item, OP3-prefixed. It survives every later rebuild and never moves the episode numbering;
3. posts the X teaser from each account in `x_env_prefixes`;
4. renders the trailer as a YouTube Short (cover, captions, a members-only end card) on the English channel;
5. rebuilds `specials.html`, the homepage band and the teaser shows' pages.

For 14 days after release, each teaser show's daily emails carry a P.S. about the series.

Nothing appears on any public surface before release: the page, the cards, the P.S. and the member feed items all read `status: released`.

## Cost

Rough cost: about $1–1.50 an episode (research searches, two long model calls, about 30 minutes of TTS). That is about $10 for the merger series and $25 for peptides.
