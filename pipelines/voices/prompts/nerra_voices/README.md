# Nerra Voices — per-show prompt overrides

This directory is the `prompt_dir` for Nerra Voices (`shows/nerra_voices.yaml`
→ `voices.prompt_dir: nerra_voices`). It is **intentionally empty apart from
this README**: every Mira-hosted show runs on the shared prompts one level
up (`pipelines/voices/prompts/*.txt` and `editorial_passes/*.txt`), which
are show-generic and read the show's identity from tokens:

| token                  | source (`pipelines/voices/shows.py` → `VoiceShow`) |
|------------------------|----------------------------------------------------|
| `{{show_name}}`        | `name` ("Nerra Voices")                             |
| `{{show_short_label}}` | `voices.short_label`                                |
| `{{show_slug}}`        | `slug`                                              |
| `{{show_premise}}`     | `voices.premise`                                    |
| `{{opening_line}}`     | `voices.opening_line`                               |
| `{{closing_question}}` | `voices.closing_question`                           |

`common.load_prompt(template, show=...)` fills those automatically for every
template, then applies the caller's own substitutions.

## How an override works

`VoiceShow.prompt_path(template)` looks for
`pipelines/voices/prompts/<prompt_dir>/<template>` first and falls back to
the shared file. So to give Nerra Voices its own version of a prompt, copy
the shared file here under the **same relative name** and edit it:

```
pipelines/voices/prompts/nerra_voices/question_generation.txt
pipelines/voices/prompts/nerra_voices/editorial_passes/03_episode_notes.txt
```

Nothing else changes: the pipeline scripts call `load_prompt(...)` with the
same template name for every show.

## Rules

* Prefer changing the yaml `voices:` block (premise / opening / closing) or
  the shared prompt over adding an override — an override forks the prompt
  and stops receiving fixes made to the shared one.
* Keep every `{{token}}` the shared prompt uses; `load_prompt` does literal
  replacement, so an unpassed token ships verbatim into the LLM prompt.
* `tests/test_nerra_voices_pipeline.py` guards the token contract and that
  the shared prompts carry no hardcoded show name.
