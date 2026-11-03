# Members-only limited series (Oct 18 2026)

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

### Members-only limited series (Oct 18 2026)

Operator-directed (doc [`docs/specials.md`](docs/specials.md); guards
`tests/test_specials_2026_10_18.py`). **A limited series runs outside run_show**
— the deep-dive path is single-episode, skips the lints, gives the claims gate
no local texts and is blocked by the per-date marker — through
`engine/specials.py` + `scripts/produce_special.py` (private) and
`scripts/release_special.py` (public, only after the operator has listened);
workflow **Members-only series**. Series live in `specials/series/<id>.yaml`
(merger: 7 parts ending on the case for and the case against; peptides: an
opener + 16 peptides, each answering the same eight questions). Rules that
bind: **only pages the run READ are sources** (search summaries and social
posts never are) and an episode under `min_sources` does not produce;
**a script is written only from its sourced dossier**, the claims gate runs in
flag mode, a Peptides-hosted series carries the blocking `dose_terms` lint,
and there is no expansion retry (`MIN_SCRIPT_WORDS` fails short); **audio goes
to the private bucket under `specials/`, never a show's keyspace**; **every
paying member gets every released series** as bonus items the builder copies
into `personal/<token>/` (no Worker change); **a trailer GUID never contains
`ep<digits>`** (`trailer_guid`) so the free feed's numbering never moves;
**nothing public reads a series before `status: released`** — specials.html,
the show/homepage cards and the 14-day newsletter P.S. Episodes close on the
network's spoken AI disclosure (`AI_DISCLOSURE`, kept equal to run_show's).
⚠️ AUDIO — listen to every episode before release.
