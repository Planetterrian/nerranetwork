## Checklist

- [ ] Migrations in this PR are NOT applied to prod; Patrick's go required (quote + timestamp)

## Changes audio or a prompt?

A change to `shows/_defaults.yaml`'s `audio:` / `tts:`, to `engine/audio.py`'s
chain or mix builders, to `engine/story_breaks.py`, to the TTS request, or to
a podcast prompt is listened to before it reaches the slate
(`docs/model_upgrade_playbook.md`, "Audio changes"; `docs/listens.md`).

- Rehearsal artifact (Actions "Run show" with `rehearse: true`, or "Probe audio chain" with a `script`): <link>
- Listened by/when: ___
- Trial show(s) (the value in that show's YAML first): ___
