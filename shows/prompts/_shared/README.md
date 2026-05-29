# Shared prompt snippets

Reusable blocks composed into per-show prompts via the include directive
resolved in `engine.generator.load_prompt`:

```
<<include: _shared/accuracy_rules.txt>>
```

Rules:

- The path is resolved **relative to the including prompt file's directory**
  (so from `shows/prompts/<slug>_podcast.txt`, `_shared/foo.txt` points at
  `shows/prompts/_shared/foo.txt`).
- Includes are expanded **before** `{placeholder}` substitution, so an included
  snippet may itself contain `{placeholders}` that the caller fills.
- Includes are recursive (snippets may include other snippets) with cycle and
  depth guards.
- A prompt with **no** include directive is rendered byte-for-byte as before —
  the mechanism is fully opt-in.

These snippets exist so that, as individual shows are revised, duplicated
guidance (accuracy rules, AI-transparency note, etc.) can be centralized
instead of copy-pasted across 40+ prompt files. **Do not bulk-rewrite existing
prompts to use these** without re-running `tests/test_prompt_fidelity.py` and
A/B listening — changing the assembled prompt changes generated output.
