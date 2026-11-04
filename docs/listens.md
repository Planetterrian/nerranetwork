# Listens

The record of what a person heard before an audio change reached the slate.
Measurements live in `docs/experiments.yaml` and the review docs; this file is
for the ear. Started Nov 3 2026 (the six-month review, "listen before the
slate"): until then CLAUDE.md carried 47 ⚠️ AUDIO flags and no record of a
listen, and the Oct 13 beat, the Oct 14 swell and the Oct 20 breath tag each
shipped to every show before anyone had heard them on one.

## How to add a line

A change to a value in the `audio:` or `tts:` section of `shows/_defaults.yaml`
fails `tests/test_listen_before_slate_2026_11_03.py` until, in the same PR, the
snapshot is regenerated and this file gains one line in exactly this form:

    <key> — listened by <who> on <date>, episode <show> Ep<N> · snapshot <fingerprint>

`python tests/test_listen_before_slate_2026_11_03.py --write` regenerates
`tests/fixtures/defaults_audio_snapshot.yaml` and prints the fingerprint for the
new values. The episode is the one the listener heard — a rehearsal artifact
(Actions "Run show", `rehearse: true`) or the probe's minute ("Probe audio
chain" with a `script`) counts, named as the episode whose script it voiced.
The guard confirms the line was written; only the listener can confirm the
listening. Playbook: `docs/model_upgrade_playbook.md`, "Audio changes".

Lines for a builder change (`engine/audio.py`), a prompt, or a per-show YAML
value carry no fingerprint; write them in the same shape without the suffix.

## Lines

audio.story_break_cue — listened by the operator on 2026-10-20, episode tesla Ep639 · snapshot dc16550a1771

audio.story_break_seconds — listened by the operator on 2026-10-14, episode tesla Ep633 (the Oct 13 beat: "sounds forced and unnatural"; 1.6–1.7 s of dead air at a story change — the value became the TOTAL pause, 1.0 s)

tts.story_tag_open — listened by the operator on 2026-10-20, episode tesla Ep640 (the Oct 20 slate: the `[breath]` tag "way too prominent" on this voice; off, and every breath-family tag stripped before synthesis; the 14 episodes that aired with it were re-synthesized)

engine/audio.py voice_chain_filters for Mira — listened by the operator on 2026-10-29, episode nerra_daily Ep070 ("hisses and clicks" on Mira's introduction and the first show: the joins, Mira's chain and the room-tone pauses that followed)
