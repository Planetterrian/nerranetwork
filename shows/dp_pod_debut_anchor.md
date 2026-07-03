<!--
DEBUT ANCHOR — pinned discussion material for The DP Pod Episode 1.
The story of how the Nerra Network got built, distilled from the repo's
own development history (the PR chronicle in CLAUDE.md). Every number
below is real. Delete this file after the debut ships and daily episodes
will anchor on the latest First Principles material instead.
-->

THE STORY OF BUILDING NERRA (real development history, for the hosts to
review and analyze — not to recite):

ORIGINS. In 2025 two friends asked a simple question: could two people run
an entire podcast network — not one show, a network — by building an AI
pipeline instead of hiring a studio? It started as a handful of standalone
scripts, one per show, thousands of lines each, held together by cron jobs.

THE REFACTOR. The scripts kept duplicating each other, so the whole thing
was rebuilt as one unified pipeline: a single runner, a per-show config
file, and a shared engine. Adding a show went from "write two thousand
lines" to "write a config and some prompts." Today one pipeline runs
fourteen daily shows, guarded by more than three and a half thousand
automated tests that run before every single episode publishes.

THE AI ARC. Every episode: fetch dozens of real sources, draft a sourced
digest, write the script, synthesize the voices, mix to broadcast loudness.
The economics only work because of two migrations: the language model moved
to a newer generation that cut per-episode cost roughly in half, and the
voices moved from a premium provider to custom-trained voices at roughly
one thirty-sixth the price per character — about four dollars per million
characters instead of a hundred and fifty. That one migration is why a
fourteen-show daily network is affordable for two people.

PROMPTS ARE THE PRODUCT. The hardest lessons were editorial. Give the model
one example phrase and it will repeat it verbatim in every episode — a
failure mode the team named seeded-template convergence, with the rule
"de-seed by shape, never with a quotable example." Every show now gets
recurring quality reviews: a review agent audits one show twice a week,
writes predictions into a ledger, and the next review scores those
predictions as hits or misses. The reviewer itself was migrated from an
expensive model to a cheap one — about thirty cents a run instead of six to
nine dollars. And one iron rule survived everything: no change that alters
the audio ships without a human actually listening first.

LANGUAGES. The network went multilingual early: two Russian-language shows
(financial literacy, and Russian language learning) with their own custom
Russian voice. Then every English episode started getting automatically
translated and re-voiced into French, Russian, Spanish, and Chinese — for
about eighteen cents an episode — each language with its own subscribable
feed, plus a Russian-dubbed YouTube channel.

THE BLOG. Every episode publishes a blog post with the full transcript and
chapters. Early on, every post had the identical title — the show's name —
which killed search visibility; now each post is titled by the episode's
hook.

THE YOUTUBE PIPELINE. Full videos and Shorts are auto-produced: AI-generated
imagery, TikTok-style per-word captions timed from the speech recognition,
a heuristic that scans the transcript to start each Short at the most
engaging beat, thumbnails that auto-shrink text to fit, auto hashtags. The
constraint saga: YouTube allows ten thousand API units a day and one upload
costs sixteen hundred, which forced brutal choices about which shows got
video — until a quota increase to two hundred thousand let all fourteen
shows publish, roughly two dozen uploads a day. Retention data now feeds
back into how titles get written.

RELIABILITY. GitHub's schedulers fired hours late, so an external
dispatcher now triggers each show to the minute, with duplicate guards so
a late backup trigger can't double-publish, and automatic recovery pull
requests when a push fails mid-publish. A management dashboard tracks every
known landmine in the system — the running list of past mistakes and how
each was fixed.

THE SHOWS, OVER TIME. Ten shows at the first network review. Then two
narrative shows driven by topic queues instead of news (First Principles
Daily — the magic-wand number and the Idiot Index — and Unintended
Consequences). Then SpaceX Daily, launched the day of the IPO. And now the
fourteenth: this one — the first two-voice dialogue show, and the first
where the builders step in front of the microphone.

OPEN QUESTIONS FOR THE HOSTS TO ARGUE:
- What does it mean that two people can now do what took a media company?
- Where does human judgment stay load-bearing? (The listen-gates, the
  editorial standards, the review ledger — which of these could you NOT
  automate?)
- What breaks first at fifty shows?
- Is AI-made media honest enough — and does full disclosure plus
  no-fabrication rules actually earn trust?
- What should a builder listening today take from the cost curves?
