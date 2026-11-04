# Oct 9 2026 — the runner upgrade, taken whole

Moved verbatim from CLAUDE.md on 2026-11-03; the rules that still bind are summarised there.

**Oct 9 2026 — the runner upgrade, taken whole (operator-directed).**
GitHub moves `ubuntu-latest` to Ubuntu 26 from Oct 19; rather than let the
label move under the network, **every job pins `runs-on: ubuntu-26.04`**
(apt ffmpeg 8.0 — was 6.1), every `setup-python` call and the composite's
default run **Python 3.14**, every action is on its current major, and the
requirements floors are the releases of that date (`av` keeps its `<19`
ceiling; the PyAV guard pins the ceiling and lets the floor move). Read
before trusting: an ffmpeg **9-dev** snapshot aborted inside the Voices
`anlmdn` clean-track chain while the 8.x release line passed the same
tests, so a future bump of the runner's ffmpeg is a render-smoke question,
not a label edit. **The scheduler Worker holds ONE cron trigger** —
`1,7,16,31,37,46,50 6-17 * * *` — because the Cloudflare account was then on
Workers Free (five triggers per account, Voices held three) and the Oct 8
deploy with a second trigger was refused with code 10072 after the script
had uploaded: the show slots kept firing and the 8am edition dispatch never
went live. **The account is on Workers Paid now** (operator, Oct 23 2026),
so a second trigger would deploy; one stays because the handler decides
from the exact firing minute and no job needs another. Since Oct 17 the one
trigger is `*/5 * * * *`. Guards: `tests/test_scheduling_punctuality.py`,
`tests/test_transcripts_pyav_2026_10_08.py`.
