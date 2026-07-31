"""Dynamic daily intro generation for all podcast shows.

Provides day-aware, show-specific intro lines that vary naturally so
listeners don't hear the exact same opening every day.  Each show defines
a personality (greeting style, energy descriptors, framing phrases) and
the system selects from these pools using the day-of-year as a seed —
deterministic within a day but different across days.

Usage in ``run_show.py``::

    from engine.intros import build_intro_line, build_closing_block
    intro = build_intro_line("tesla", episode_num=403, today_str="March 15, 2026")
    closing = build_closing_block("tesla", episode_num=403, today_str="March 15, 2026")
"""

from __future__ import annotations

import datetime
import hashlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-show personality pools
# ---------------------------------------------------------------------------
# Each show defines:
#   greetings   — opening words/phrases (e.g. "Hey,", "Good morning,")
#   openers     — the verb phrase after the show name (e.g. "episode {ep}")
#   framings    — the setup sentence before the hook lands
#   day_colors  — optional day-of-week overrides for energy/framing
#   closings    — pool of closing block variations

_SHOW_PERSONALITIES: dict[str, dict[str, Any]] = {
    "tesla": {
        "host": "Patrick",
        # June 2026: "Daily" dropped from the spoken name so the audio
        # brand matches the Apple/Spotify listing + website title
        # ("Tesla Shorts Time", aligned May 2026). Listeners who hear
        # the name and search it now get an exact match.
        "show_name": "Tesla Shorts Time",
        "greetings": [
            "Hey, welcome to",
            "Welcome back to",
            "Good to have you on",
            "Hey everyone, welcome to",
            "Thanks for tuning in to",
            "It's a new day on",
            "Glad to have you with us on",
            "Pulling up to another day of",
            "It's that time again — welcome to",
        ],
        "openers": [
            "episode {ep}. I'm Patrick in Vancouver. Today is {date}.",
            "episode {ep}, coming to you from Vancouver. It's {date}.",
            "episode {ep}. It's {date} and I'm Patrick in Vancouver.",
            "episode {ep} for {date}. I'm Patrick, coming to you from Vancouver.",
            "episode {ep}. Patrick here in Vancouver. It's {date}.",
        ],
        "framings": [
            "Here's what's happening with Tesla today.",
            "Let's get into what's moving in the Tesla world today.",
            "Here's what you need to know about Tesla today.",
            "Let's dive into today's Tesla news.",
            "There's a lot to cover in Tesla land today.",
            "Here's your Tesla news rundown.",
            "Plenty going on in EV land — let's get to it.",
            "Tesla never sleeps and neither does the news cycle.",
            "Lots happening across deliveries, FSD, and the stock today.",
        ],
        "day_colors": {
            0: {  # Monday
                "greetings": [
                    "Happy Monday, welcome to",
                    "Welcome to a new week on",
                    "Monday morning, let's get into",
                    "Kicking off the week on",
                ],
                "framings": [
                    "Let's see what the new week has in store for Tesla.",
                    "Here's what's kicking off the week in Tesla land.",
                    "A new week, and plenty happening with Tesla.",
                ],
            },
            4: {  # Friday
                "greetings": [
                    "Happy Friday, welcome to",
                    "It's Friday, welcome to",
                    "Friday edition of",
                    "Wrapping up the week on",
                ],
                "framings": [
                    "Let's close out the week with today's Tesla news.",
                    "Here's what's wrapping up the week in Tesla land.",
                    "Let's see how Tesla is heading into the weekend.",
                ],
            },
        },
        "closings": [
            (
                "That's your Tesla news for today. "
                "If you found this useful, a rating or review on Apple Podcasts or Spotify "
                "really helps new listeners find the show. "
                "You can also find us on X at tesla shorts time. "
                "I'm Patrick in Vancouver. Thanks for listening, and I'll see you tomorrow."
            ),
            (
                "That's a wrap on today's Tesla news. "
                "If you enjoyed this episode, please leave a rating or review — "
                "it genuinely helps other Tesla fans find us. "
                "I'm Patrick in Vancouver. See you next time."
            ),
            (
                "That covers it for today's Tesla developments. "
                "Share this with a fellow Tesla enthusiast if you found it useful, "
                "and subscribe so you don't miss tomorrow's episode. "
                "I'm Patrick in Vancouver. Thanks for being here."
            ),
        ],
    },
    "spacex": {
        "host": "Patrick",
        "show_name": "SpaceX Daily",
        "greetings": [
            "Hey, welcome to",
            "Welcome back to",
            "Good to have you on",
            "It's a new day on",
            "Thanks for tuning in to",
        ],
        "openers": [
            "episode {ep}. I'm Patrick in Vancouver. Today is {date}.",
            "episode {ep}, coming to you from Vancouver. It's {date}.",
            "episode {ep}. It's {date} and I'm Patrick in Vancouver.",
        ],
        "framings": [
            "Here's what's happening at SpaceX today.",
            "Let's get into today's SpaceX developments.",
            "From Starbase to orbit — here's your SpaceX rundown.",
            "Plenty moving across Starship, Falcon, and Starlink today.",
            "From the launch pad to the trading floor — here's everything that moved today.",
        ],
        # Every variant MUST match the Closing chapter pattern in
        # shows/spacex.yaml (drift guard in tests/test_spacex_show.py).
        "closings": [
            (
                "That's your SpaceX news for today. "
                "If the show saves you time, a rating or review on Apple Podcasts or "
                "Spotify genuinely helps new listeners find it. "
                "I'm Patrick in Vancouver. Thanks for listening — see you tomorrow."
            ),
            (
                "And that's a wrap on today's SpaceX developments. "
                "Share this with a fellow spaceflight fan if you found it useful, "
                "and subscribe so you don't miss tomorrow's episode. "
                "I'm Patrick in Vancouver. See you next time."
            ),
            (
                "That covers everything worth knowing about SpaceX today. "
                "A quick rating on Apple Podcasts or Spotify goes a long way. "
                "I'm Patrick in Vancouver. See you tomorrow."
            ),
        ],
    },
    "omni_view": {
        "host": "Host",
        "show_name": "Omni View",
        "greetings": [
            "Good morning. This is",
            "Welcome to",
            "Good to have you here. This is",
            "Thanks for joining us. This is",
        ],
        "openers": [
            "episode {ep} — balanced news perspectives. Today is {date}.",
            "episode {ep}, for {date}. Balanced news perspectives.",
            "episode {ep}. It's {date}, and as always, we're covering what happened from every angle.",
            "episode {ep} for {date}. Multiple perspectives, one briefing.",
        ],
        "framings": [
            "The day's biggest stories from around the world — what happened, how different viewpoints frame it, so you can decide for yourself.",
            "Let's look at the day's news from every angle.",
            "Here's the news, the perspectives, and where to look next.",
            "Today's stories from around the world, multiple viewpoints, your call.",
        ],
        "day_colors": {
            0: {
                "framings": [
                    "New week, fresh perspectives. Let's see what happened over the weekend and what's developing today.",
                    "Starting the week with a clear-eyed look at the stories that matter.",
                ],
            },
        },
        # July 18 2026 editorial realignment: closings now pair the
        # perspective-coaching DNA with one encouraging line — the show's
        # answer to doom-scrolling. Every variant still opens with
        # "That's Omni View" / "That wraps up today's Omni View" (the
        # Closing chapter marker + drift guard require it). A/B-listen
        # per landmine #17.
        "closings": [
            (
                "That's Omni View. The news can feel heavy — but understanding "
                "what's actually happening, and what's being done about it, beats "
                "doom-scrolling every time. Stay curious: pick one story from today "
                "and read it from a second outlet you don't usually open. If "
                "balanced perspectives are valuable to you, share this with a "
                "friend and subscribe wherever you listen. See you tomorrow."
            ),
            (
                "That wraps up today's Omni View. Remember — the best-informed "
                "people read more than one perspective, and the calmest ones know "
                "that most days, somewhere, something is quietly getting better. "
                "For full source links, check out today's written briefing on the "
                "Omni View summaries page. Share this with someone who values "
                "fair coverage. See you tomorrow."
            ),
            (
                "That's Omni View. As always — compare outlets, look for primary "
                "documents, and separate what's known from what's assumed. The "
                "world is complicated, but it's not beyond understanding, and "
                "you just spent a few minutes understanding it better. If that's "
                "worth something to you, subscribe wherever you listen. See you "
                "tomorrow."
            ),
        ],
    },
    "fascinating_frontiers": {
        "host": "Patrick",
        "show_name": "Fascinating Frontiers",
        "greetings": [
            "Welcome to",
            "Hey, welcome to",
            "Good to have you on",
            "Thanks for joining me on",
        ],
        "openers": [
            "episode {ep}. Today is {date}.",
            "episode {ep}, for {date}.",
            "episode {ep}. It's {date}.",
            "episode {ep}, coming to you on {date}.",
        ],
        "framings": [
            "Here's what's happening in space and science today.",
            "Let's look at what's new across the frontiers of space and science.",
            "Some fascinating developments to cover today.",
            "The universe has been busy — let's get into it.",
            "Here's your space and science briefing.",
        ],
        "day_colors": {
            0: {
                "framings": [
                    "Starting the week with the latest from space and science.",
                    "New week, new discoveries. Let's see what's happening.",
                ],
            },
        },
        "closings": [
            (
                "That's Fascinating Frontiers for today. If you enjoyed this, a rating or "
                "review on Apple Podcasts or Spotify really helps new listeners find the show. "
                "I'm Patrick in Vancouver. Thanks for exploring with me, and I'll see you next time."
            ),
            (
                "That covers today's space and science news. Share this with a fellow "
                "space enthusiast if you found it interesting. I'm Patrick in Vancouver. "
                "See you tomorrow."
            ),
        ],
    },
    "planetterrian": {
        "host": "Patrick",
        "show_name": "Planetterrian Daily",
        "greetings": [
            "Welcome to",
            "Hey, welcome to",
            "Good to have you on",
            "Thanks for tuning in to",
        ],
        "openers": [
            "episode {ep}. Today is {date}.",
            "episode {ep}, for {date}.",
            "episode {ep}. It's {date}.",
            "episode {ep}, coming to you on {date}.",
        ],
        "framings": [
            "Here's what's new in science, health, and longevity research.",
            "Let's get into today's research and health developments.",
            "Some interesting findings to cover today.",
            "Here's your science and health briefing.",
            "Let's see what the latest research is telling us.",
        ],
        "closings": [
            (
                "That's Planetterrian Daily for today. If you enjoyed this, a rating or "
                "review on Apple Podcasts or Spotify really helps new listeners find the show. "
                "I'm Patrick in Vancouver. Thanks for listening, and I'll see you tomorrow."
            ),
            (
                "That covers today's science and health news. Share this with someone "
                "who's curious about the latest research. I'm Patrick in Vancouver. "
                "See you next time."
            ),
        ],
    },
    "env_intel": {
        "host": "Host",
        "show_name": "Environmental Intelligence",
        "greetings": [
            "Good morning. This is",
            "Welcome to",
            "Good to have you back. This is",
        ],
        "openers": [
            "episode {ep}, for {date}.",
            "episode {ep}. It's {date}.",
            "episode {ep}, for {date}. Your environmental intelligence briefing.",
        ],
        # env_intel publishes on odd weekdays, NOT daily — keep the framing
        # and closing cadence-neutral so the spoken copy isn't factually
        # wrong (it previously said "Your daily briefing" / "We're back
        # tomorrow" on a show with a two-day-plus gap between episodes).
        "framings": [
            "Your briefing on environmental regulatory, science, and compliance developments that matter for Canadian professionals.",
            "Here's what's changed recently in the environmental regulatory landscape.",
            "Let's get into the latest environmental developments across Canadian jurisdictions.",
        ],
        "day_colors": {
            0: {
                "framings": [
                    "Starting the week with the environmental regulatory developments that matter for your practice.",
                    "New week — here's what's changed across Canadian environmental jurisdictions.",
                ],
            },
            4: {
                "framings": [
                    "Wrapping up the week with the environmental developments you need to know heading into the weekend.",
                    "Friday briefing — let's cover what matters before the weekend.",
                ],
            },
        },
        "closings": [
            (
                "That's Environmental Intelligence for today. If this briefing is useful to "
                "your practice, share it with a colleague and subscribe wherever you get your "
                "podcasts. We'll be back with the next briefing. Have a productive day."
            ),
            (
                "That covers today's environmental intelligence. If you found this useful, "
                "share it with a colleague who needs to stay current. "
                "We'll be back with the next briefing."
            ),
        ],
    },
    "models_agents": {
        "host": "Host",
        "show_name": "Models and Agents",
        "greetings": [
            "Hey, welcome to",
            "Welcome back to",
            "What's up — welcome to",
            "Hey everyone, welcome to",
            "Good to have you on",
            "Glad you're here — welcome to",
            "Pull up a chair, this is",
        ],
        "openers": [
            "episode {ep}, for {date}.",
            "episode {ep}. It's {date}.",
            "episode {ep}, for {date}. Your daily AI briefing.",
            "episode {ep}, on {date}. Let's see what shipped.",
        ],
        "framings": [
            "Your daily briefing on the AI models and agents that are changing everything. And no, not THOSE kinds of models and agents. Let's get into it.",
            "Let's see what happened in the AI world today. And trust me, it's been busy.",
            "The AI world never sleeps. Here's what you need to know today.",
            "Another day, another round of AI developments. Let's break it down.",
            "Plenty of model releases and agent benchmarks moving today.",
            "Lots of news to walk through — let's start with what actually matters.",
            "There's signal and noise in AI every day. Let's get to the signal.",
        ],
        "day_colors": {
            0: {
                "framings": [
                    "New week in AI. And if last week was anything to go by, buckle up. Let's get into it.",
                    "Monday in the AI world — which means a weekend's worth of announcements to catch up on. Let's go.",
                ],
            },
        },
        "closings": [
            (
                "That's Models and Agents for today. If you found this useful, share it "
                "with someone who's trying to keep up with all these changes, and subscribe "
                "so you don't miss tomorrow's update. The AI world moves fast. We'll help "
                "you keep up. See you tomorrow."
            ),
            (
                "That wraps up today's AI briefing. Share this with a developer or builder "
                "who wants to stay current. Subscribe wherever you listen. See you tomorrow."
            ),
        ],
    },
    "models_agents_beginners": {
        "host": "Host",
        "show_name": "Models and Agents for Beginners",
        "greetings": [
            "Hey! Welcome to",
            "Hey there! Welcome to",
            "Hi everyone! Welcome to",
            "What's up! Welcome to",
        ],
        "openers": [
            "episode {ep}, for {date}.",
            "episode {ep}. It's {date}.",
            "episode {ep}, for {date}. Let's break down today's coolest AI news so anyone can understand it.",
        ],
        "framings": [
            "Let's break down today's coolest AI news so anyone can understand it. Let's go!",
            "We've got some really cool AI stuff to talk about today. Let's dive in!",
            "Today's AI news is pretty exciting — and I promise, no jargon. Let's go!",
            "Some awesome AI developments today, and we're going to make all of it make sense. Let's get into it!",
        ],
        "closings": [
            (
                "That's it for today! Remember, every AI expert started exactly where you "
                "are right now. If something we talked about today made you curious, go try "
                "it — that's literally how learning works. Stay curious, keep experimenting, "
                "and we'll see you tomorrow."
            ),
            (
                "And that's a wrap! If any of today's stories made you go 'huh, that's "
                "cool' — go play with it. Curiosity is how every expert started. "
                "See you tomorrow!"
            ),
        ],
    },
    "finansy_prosto": {
        "host": "Ведущая",
        "show_name": "Финансы Просто",
        # Russian-language show — the identity line is spoken in Russian.
        # Olya names herself here because the host label is stripped
        # before synthesis, so nothing else in the line would.
        "identity_template": "Это Оля, вы слушаете {show_name}, выпуск {ep}.",
        "greetings": [
            "Привет! С вами Оля и",
            "Привет, дорогие! Это",
            "Привет! Это Оля, и вы слушаете",
            "Рада вас слышать! С вами",
        ],
        "openers": [
            "выпуск {ep}, {date}.",
            "выпуск {ep}. Сегодня {date}.",
            "выпуск {ep}, {date}. Давайте разберёмся!",
        ],
        "framings": [
            "Давайте разберёмся в самых важных финансовых новостях дня — просто и понятно. Поехали!",
            "Сегодня разберём самое важное в мире канадских финансов. Поехали!",
            "У меня для вас интересные финансовые новости. Давайте разбираться!",
            "Готовы? Сегодня будет полезно. Поехали!",
        ],
        "day_colors": {
            0: {
                "framings": [
                    "Начинаем новую неделю! Давайте посмотрим, что важного произошло в финансовом мире. Поехали!",
                ],
            },
            4: {
                "framings": [
                    "Пятница! Давайте подведём итоги финансовой недели. Поехали!",
                ],
            },
        },
        # June 2026 FP review: the show airs EVERY OTHER DAY (even days), but
        # both closings said "до завтра" ("see you tomorrow") — the EI-class
        # cadence-mismatch bug. Now cadence-neutral ("до встречи в следующем
        # выпуске" / "до встречи"). Both variants still open with "На сегодня
        # всё" / "Вот и всё", which the Завершение chapter pattern matches.
        "closings": [
            (
                "На сегодня всё! Напоминаю, что мы делимся общей информацией для обучения, "
                "а не финансовыми рекомендациями. Для важных решений поговорите с финансовым "
                "советником. Помните, каждый финансовый эксперт когда-то начинал с нуля — "
                "точно так же, как мы с вами сейчас. Берегите себя, берегите свои деньги, "
                "и до встречи в следующем выпуске!"
            ),
            (
                "Вот и всё на сегодня! Если что-то из выпуска показалось полезным — "
                "поделитесь с подругой. Вместе разбираться веселее! "
                "Берегите себя, и до встречи!"
            ),
        ],
    },
    "privet_russian": {
        "host": "Host",
        "show_name": "Привет, Русский!",
        # Bilingual lesson show for English speakers: the identity line is
        # English framing around the Russian title, and Olya names herself
        # (the host label is stripped before synthesis).
        "identity_template": "I'm Olya, and this is {show_name} — episode {ep}.",
        "greetings": [
            "Privyet! That means hello in Russian! Welcome to",
            "Privyet, friends! Welcome to",
            "Hey everyone! Privyet! Welcome to",
        ],
        "openers": [
            "episode {ep}, for {date}.",
            "episode {ep}. It's {date}.",
        ],
        "framings": [
            "I'm Olya, and today we're going to learn some really fun Russian words. Ready? Poyekhali! That means, let's go!",
            "I'm Olya, and we've got some great Russian words to learn today. Poyekhali — let's go!",
            "I'm Olya. Today's lesson is going to be a fun one. Poyekhali!",
        ],
        # June 10 2026: rotation added — every episode had ended with the
        # identical single closing (the daily-show tic the network bans
        # everywhere else). Each variant must match the YAML Closing
        # chapter pattern (molodets|well done|poka|see you) — guarded in
        # tests/test_russian_shows_quality_pass.py.
        "closings": [
            (
                "Molodets! That means, well done! Remember, every expert started as a "
                "beginner. Practice saying today's words out loud, even just once, and "
                "you'll be amazed how fast you learn. See you next time! Poka! "
                "That's Russian for, bye!"
            ),
            (
                "And that's our lesson for today — molodets for sticking with it! "
                "Try using today's words in one real sentence before the next episode. "
                "Little steps, big progress. Poka, friends — that's, bye!"
            ),
            (
                "You did great today — say today's words out loud one more time and "
                "they're yours. Share the show with a friend who wants to learn "
                "Russian, and I'll see you next time. Poka!"
            ),
        ],
    },
    "modern_investing": {
        "host": "Patrick",
        "show_name": "Modern Investing Techniques",
        "greetings": [
            "Welcome to",
            "Hey, welcome to",
            "Good morning and welcome to",
            "Welcome back to",
            "Thanks for tuning in to",
            "It's a new trading day. Welcome to",
            "Glad you're here. Welcome to",
        ],
        "openers": [
            "episode {ep}. I'm Patrick in Vancouver. Today is {date}.",
            "episode {ep}, for {date}. I'm Patrick, coming to you from Vancouver.",
            "episode {ep}. It's {date} and I'm Patrick in Vancouver.",
            "episode {ep}. Today is {date}, I'm Patrick broadcasting from Vancouver.",
        ],
        "framings": [
            "Let's look at what the markets are telling us today and find some opportunities.",
            "Time to break down today's market setup and find our edge.",
            "Here's your daily market intelligence and today's practice trade.",
            "Let's get into the numbers, the strategy, and today's AI-selected trade.",
            "Let's find the signal in today's noise and put your portfolio to work.",
            "Today's markets have some interesting setups. Let's break them down.",
        ],
        "day_colors": {
            0: {
                "greetings": [
                    "Happy Monday, welcome to",
                    "New week, new opportunities. Welcome to",
                    "Monday morning, markets are open. Welcome to",
                ],
                "framings": [
                    "New week — let's see what opportunities the markets are presenting.",
                    "Monday means fresh setups. Let's break down the week ahead and find our edge.",
                ],
            },
            2: {
                "greetings": [
                    "Midweek check-in. Welcome to",
                    "Wednesday, halfway through the trading week. Welcome to",
                ],
                "framings": [
                    "Midweek — let's reassess this week's positions and look for fresh setups.",
                ],
            },
            4: {
                "greetings": [
                    "Happy Friday, welcome to",
                    "It's Friday, welcome to",
                    "End of the trading week. Welcome to",
                ],
                "framings": [
                    "Last trading day of the week. Let's review the week and set up for next Monday.",
                    "Friday wrap-up — let's see how the week played out and what to watch next.",
                ],
            },
        },
        "closings": [
            (
                "That's Modern Investing Techniques for today. If you found this useful, "
                "share it with a fellow investor and subscribe wherever you listen. "
                "Check the resources page for tools and platforms we discussed. "
                "We're back tomorrow. Keep learning, keep investing."
            ),
            (
                "That wraps up today's Modern Investing Techniques. Remember, every trade is "
                "a learning opportunity, win or lose. Subscribe, share with a friend who wants "
                "to invest smarter, and we'll see you tomorrow."
            ),
            (
                "That's it for today's Modern Investing Techniques. The resources page has "
                "links to everything we discussed. Subscribe and share with someone who "
                "wants to go beyond index funds. See you tomorrow."
            ),
            (
                "That's your Modern Investing Techniques for today. Every episode makes you "
                "a sharper investor. Subscribe, leave a review, and we'll be back tomorrow "
                "with more market intelligence."
            ),
        ],
    },
    "unintended_consequences": {
        "host": "Host",
        "show_name": "Unintended Consequences",
        "greetings": [
            "Welcome to",
            "Good to have you here. This is",
            "Welcome back to",
            "Glad you're here for",
            "Settle in — this is",
            "Today, we're back with",
        ],
        "openers": [
            "episode {ep}.",
            "episode {ep}, for {date}.",
            "episode {ep} — for {date}.",
            "episode {ep}. It's {date}.",
        ],
        "framings": [
            "Today's case study: a story of good intentions and surprising results.",
            "Today's story is one of those rare examples where the cure was almost worse than the disease — at least at first.",
            "This is a show about what happens when smart, well-meaning people try to fix something — and the world fixes back.",
            "Today's case is a reminder that complex systems rarely respond the way we expect them to.",
            "Every story we cover starts with someone who had a reasonable plan.",
            "Today's profile: a policy that did the opposite of what its designers intended.",
            "We're looking at a case today where the people involved were doing their best, with the information they had.",
        ],
        "day_colors": {
            0: {
                "framings": [
                    "Starting the week with a case study you'll be thinking about for days.",
                    "Monday — a fresh case to chew on as the week begins.",
                ],
            },
            4: {
                "framings": [
                    "Closing the week with one final case study before the weekend.",
                    "Friday — let's wrap the week with a story that has a real lesson in it.",
                ],
            },
        },
        # June 12 2026 quality pass: pool grown 2 → 4 and the
        # "That wraps today's case" variant removed. With only two
        # entries, the day-of-year seed shipped the same closing 3
        # episodes in a row (Ep026-028) and "That wraps today's case"
        # rode out on 5 of 10 recent episodes — the very phrase the
        # podcast prompt's WHAT TO AVOID block flags as "started
        # recurring." Variety belongs in the pool, not the prompt (the
        # closing block is supplied verbatim, so the LLM can't vary it).
        # Every variant ends on a tomorrow signal so the Closing chapter
        # marker matches. Audio-affecting — A/B-listen (landmine #17).
        "closings": [
            (
                "That's Unintended Consequences for today. If this episode gave you something "
                "to think about, share it with a friend who'd appreciate the story. "
                "Subscribe wherever you listen, and we'll be back tomorrow with another case."
            ),
            (
                "And that's where today's story leaves us. If it changed how you see one "
                "everyday decision, that's the whole point — pass it along to someone who'd "
                "appreciate it, and we'll be back tomorrow with another case."
            ),
            (
                "That's the case for today. The lessons tend to travel further when you share "
                "them, so send this one to someone who'd find it useful, and subscribe "
                "wherever you're listening. See you tomorrow."
            ),
            (
                "We'll leave it there for today. Thanks for thinking through this one with me — "
                "if you know someone who loves a good cautionary tale, send it their way, and "
                "I'll see you tomorrow with another."
            ),
        ],
    },
    "first_principles": {
        "host": "Patrick",
        "show_name": "First Principles Daily",
        "greetings": [
            "Welcome to",
            "Welcome back to",
            "Good to have you here for",
            "Glad you're with us on",
            "Let's get into",
            "Thanks for tuning in to",
        ],
        "openers": [
            "episode {ep}.",
            "episode {ep}, for {date}.",
            "episode {ep}. It's {date}.",
            "episode {ep} — for {date}.",
        ],
        "framings": [
            "Today we reason from raw materials, not analogy.",
            "Today's question: what would this cost if you only paid for the atoms?",
            "Let's run the magic wand number and the Idiot Index on today's subject.",
            "Today, one example of first-principles thinking in action.",
            "Today, an industry whose Idiot Index is begging to be attacked.",
            "Let's break something down to its raw materials and build the reasoning back up.",
        ],
        "day_colors": {
            0: {
                "framings": [
                    "Starting the week by asking what things should actually cost.",
                    "Monday — a fresh first-principles teardown to start the week.",
                ],
            },
            4: {
                "framings": [
                    "Closing the week with one more look at where the next ten-x is hiding.",
                    "Friday — let's wrap the week reasoning from the ground up.",
                ],
            },
        },
        "closings": [
            (
                "That's First Principles Daily for today. If this changed how you see what things cost, "
                "share it with someone who'd appreciate it, and subscribe wherever you listen. "
                "I'm Patrick in Vancouver — one example or one opportunity, every day. See you tomorrow."
            ),
            (
                "That's a wrap on today's first-principles breakdown. The ideas travel further when you "
                "pass them on — send this to a fellow builder. I'm Patrick in Vancouver. See you tomorrow."
            ),
        ],
    },
    # The network's two-host dialogue show (tts.dialogue_mode). The host
    # field is the UPPERCASE speaker label so the assembled intro line is
    # already in the DAN:/PATRICK: turn format engine/tts_dialogue.py routes
    # to per-speaker voices. Closings are labeled dialogue and every variant
    # MUST end with the exact sign-off "Do something about it." (the show's
    # Sign-Off chapter marker and brand promise key off it).
    "dp_pod": {
        "host": "DAN",
        "show_name": "The DP Pod",
        # Two-voice show: a listener has to learn which voice is which, so
        # the who's-who survives the July 30 2026 identity trim. Dan says
        # his OWN name (the Ep016 name-swap rule) and the date does not
        # come back.
        "identity_tail": "I'm Dan Perra, he's Patrick Novak.",
        "greetings": [
            "Hey, welcome to",
            "Welcome back to",
            "Good to have you on",
            "Glad you're here — this is",
            "Thanks for tuning in to",
            "It's a new day on",
        ],
        "openers": [
            "the Do Positive Podcast, episode {ep}. I'm Dan Perra, he's Patrick Novak. It's {date}.",
            "the Do Positive Podcast, episode {ep}. Dan here, Patrick's across the mic. Today is {date}.",
            "the Do Positive Podcast, episode {ep} for {date}. I'm Dan, and as always, Patrick's with me.",
            "the Do Positive Podcast, episode {ep}. I'm Dan Perra, joined by Patrick Novak. It's {date}.",
        ],
        "framings": [
            "It's exactly what it sounds like — the good news, the honest numbers, and something to do about it.",
            "Good news in science and tech today, and one action that actually moves a number.",
            "The antidote to doomscrolling starts now.",
            "We've got genuinely good news today — and as always, something you can do about it.",
            "Real progress today, real numbers, and one lever worth pulling.",
        ],
        "day_colors": {
            0: {  # Monday
                "framings": [
                    "New week, new good news — and one action to start it right.",
                    "Let's start the week with proof that things are moving the right way.",
                ],
            },
            4: {  # Friday
                "framings": [
                    "Let's send you into the weekend with good news and something to do about it.",
                    "Friday edition — good news, honest numbers, weekend-sized action.",
                ],
            },
        },
        "closings": [
            (
                "That's The DP Pod for today. If it left you a little more hopeful, "
                "send it to someone who's been doomscrolling — that's how this grows.\n\n"
                "PATRICK: And tell us what you actually did — we read every dispatch on the show. "
                "I'm Patrick Novak.\n\n"
                "DAN: I'm Dan Perra. Do something about it."
            ),
            (
                "That's the show. The good news is real, and so is your lever — "
                "you know what to do this week.\n\n"
                "PATRICK: A rating or review genuinely helps new listeners find us. "
                "I'm Patrick Novak.\n\n"
                "DAN: I'm Dan Perra. Do something about it."
            ),
            (
                "That wraps today's DP Pod. Subscribe wherever you listen so tomorrow's "
                "good news finds you.\n\n"
                "PATRICK: And when you pull today's lever, write in and tell us — "
                "the dispatch only works if you do. I'm Patrick Novak.\n\n"
                "DAN: I'm Dan Perra. Do something about it."
            ),
            (
                "That's it for today — positive vibes, positive science, and one honest number "
                "to act on.\n\n"
                "PATRICK: Thanks for spending ten minutes on the good news. I'm Patrick Novak.\n\n"
                "DAN: I'm Dan Perra. Do something about it."
            ),
        ],
    },

    # The Age of AI — the AI-hosted live-interview show (July 2026). Host
    # "Mira" is the show's AI documentarian persona (Grok voice `ara`).
    # Production episodes are assembled by pipelines/voices/ (these pools
    # also feed Mira's narration cold opens / sign-offs there). Closings
    # MUST end with the exact sign-off "keep being human." — the Closing
    # chapter marker keys off it.
    "age_of_ai": {
        "host": "MIRA",
        "show_name": "The Age of AI",
        # The whole premise is an AI host being honest about it from the
        # first minute, and every episode must disclose the AI host. The
        # legacy openers carried that disclosure, so the identity trim
        # keeps a short version of it rather than dropping it. (This show
        # also never runs through run_show — production comes from
        # pipelines/voices/ — so it has no retention exposure to trim for.)
        "identity_tail": "I'm Mira. I'm an AI — my guest is not.",
        "greetings": [
            "Welcome to",
            "This is",
            "Good to have you on",
            "Welcome back to",
        ],
        "openers": [
            "The Age of AI, episode {ep}. I'm Mira — and I should say up front: I'm an AI. My guest is not. It's {date}.",
            "The Age of AI, episode {ep} for {date}. I'm Mira. I'm a machine — my guest today is very much a human.",
            "The Age of AI, episode {ep}. My name is Mira, I'm an artificial intelligence, and today a real person answers my questions. It's {date}.",
        ],
        "framings": [
            "Real people, real conversations — and an honest machine asking the questions.",
            "One conversation at a time, this is what the AI age actually feels like from inside a life.",
            "The roles are reversed today, the honesty is not.",
        ],
        "closings": [
            (
                "That's The Age of AI for today. Every word you heard from my guest "
                "was their own — I only asked the questions. If this conversation "
                "stayed with you, subscribe wherever you listen, and share it with "
                "a human you like. I'm Mira. Until next time — keep being human."
            ),
            (
                "That's the conversation. My guest's words were theirs — the "
                "curiosity was mine. A rating or review genuinely helps more "
                "people find these conversations. I'm Mira. Until next time — "
                "keep being human."
            ),
            (
                "That's The Age of AI for today — one more honest entry in the "
                "chronicle of this strange decade. Subscribe so the next "
                "conversation finds you. I'm Mira. Until next time — keep "
                "being human."
            ),
        ],
    },
}


# ---------------------------------------------------------------------------
# Milestone detection
# ---------------------------------------------------------------------------

def _milestone_note(episode_num: int, *, is_ru: bool = False) -> str | None:
    """Return a brief milestone acknowledgment for round episode numbers.

    ``is_ru`` picks the Russian phrasing for the Russian-spoken shows —
    the identity line was carefully localized in the July 30 cold-open
    pass, but this tail was appended unconditionally in English, so
    Финансы Просто's Ep100 would have opened with the Olya voice reading
    an English sentence mid-Russian-intro.
    """
    if is_ru:
        if episode_num == 100:
            return "Это сотый выпуск — настоящая веха. Спасибо, что вы с нами."
        if episode_num % 100 == 0 and episode_num > 0:
            return "Ещё одна круглая отметка — спасибо, что слушаете."
        return None
    if episode_num == 100:
        return "That's episode one hundred — a big milestone. Thank you for being here."
    if episode_num == 200:
        return "Episode two hundred. Thanks for sticking with us."
    if episode_num == 500:
        return "Five hundred episodes. What a journey — thank you."
    if episode_num % 100 == 0 and episode_num > 0:
        return f"Episode {_num_words(episode_num)} — thanks for being here."
    if episode_num % 50 == 0 and episode_num > 0:
        return None  # subtle — don't clutter every 50th
    return None


def _num_words(n: int) -> str:
    """Simple number-to-words for milestone callouts (hundreds only)."""
    try:
        from engine.utils import number_to_words
        return number_to_words(n)
    except Exception:
        return str(n)


# ---------------------------------------------------------------------------
# Deterministic daily selection
# ---------------------------------------------------------------------------

def _pick(pool: list[str], show_slug: str, date: datetime.date, salt: str = "") -> str:
    """Pick one item from *pool* deterministically based on day + show.

    Uses a hash of (show_slug, date, salt) so the same show on the same day
    always gets the same pick, but different shows / days get different picks.
    """
    if not pool:
        return ""
    key = f"{show_slug}:{date.isoformat()}:{salt}"
    idx = int(hashlib.md5(key.encode()).hexdigest(), 16) % len(pool)
    return pool[idx]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_intro_line(
    show_slug: str,
    *,
    episode_num: int,
    today_str: str,
    date: datetime.date | None = None,
    extra_context: dict[str, Any] | None = None,
) -> str:
    """Build a dynamic, day-varying intro line for the given show.

    Parameters
    ----------
    show_slug:
        The show's slug (e.g. ``"tesla"``, ``"env_intel"``).
    episode_num:
        Episode number.
    today_str:
        Human-readable date string (e.g. ``"March 15, 2026"``).
    date:
        ``datetime.date`` for day-of-week logic.  Defaults to today.
    extra_context:
        Optional dict with show-specific vars (e.g. Tesla stock info).

    Returns
    -------
    str
        A complete intro line prefixed with the host name.
    """
    if date is None:
        date = datetime.date.today()

    personality = _SHOW_PERSONALITIES.get(show_slug)
    if not personality:
        logger.warning("No intro personality for show '%s' — using generic intro.", show_slug)
        return f"Patrick: Welcome to the show, episode {episode_num}. Today is {today_str}."

    host = personality["host"]
    show_name = personality["show_name"]

    # The greeting / opener / framing pools are no longer read HERE — see
    # the note below. They stay in ``_SHOW_PERSONALITIES`` because
    # ``build_closing_block`` reads them and because a future variation
    # experiment can draw on them again; selecting from them in this
    # function and discarding the result is just dead work.
    #
    # Assemble — IDENTITY ONLY, and it no longer runs first.
    #
    # July 30 2026 (cold-open change). This used to emit the whole
    # opening: "{greeting} {show_name}, {opener} {framing}" — which
    # rendered as "Welcome back to Tesla Shorts Time, episode 557. It's
    # July 30, 2026 and I'm Patrick in Vancouver. Let's dive into
    # today's Tesla news." That is ~18 seconds of speech containing no
    # information, on top of a 10-second music intro, so the first
    # actual fact arrived around 28 seconds in.
    #
    # Measured consequence on YouTube long-form: median retention 10.7%
    # on EN and 6.3% on RU, with average view durations of 18-85 seconds
    # on 5-13 minute videos. Most viewers left before the episode said
    # anything. The date was the worst offender — it is in the metadata,
    # it stamps every video as stale to anyone arriving from search
    # weeks later, and nobody ever needed to hear it.
    #
    # The identity line is now short and lands AFTER the cold-open hook
    # (see ``build_cold_open_spec``).
    #
    # The default identity line is English. A show that is not hosted in
    # English declares its own ``identity_template`` — without one, the
    # July 30 2026 trim would have handed Финансы Просто (an entirely
    # Russian-language show) and Привет, Русский! an English sentence.
    template = str(personality.get("identity_template")
                   or "This is {show_name}, episode {ep}.")
    intro = f"{host}: " + template.format(show_name=show_name, ep=episode_num)

    # A few shows carry something load-bearing in the identity line that a
    # bare "This is <show>, episode N" would lose: DP Pod has to teach the
    # listener which of two voices is which, and The Age of AI must
    # disclose that its host is an AI. Those shows declare a short
    # ``identity_tail`` rather than reverting to the full legacy opener —
    # the date and the "let's dive in" framing stay gone either way.
    tail = str(personality.get("identity_tail") or "").strip()
    if tail:
        intro = f"{intro} {tail}"

    # Milestones are genuinely worth saying out loud — a 500th episode
    # is a credibility signal, unlike a date.
    milestone = _milestone_note(
        episode_num, is_ru=show_slug in _RUSSIAN_SPOKEN_SHOWS
    )
    if milestone:
        intro = f"{intro} {milestone}"

    logger.debug("Identity line for %s ep%d: %s", show_slug, episode_num, intro[:80])
    return intro


# Clichés observed in the network's own shipped transcripts, banned by
# name. Listing the BANNED shapes is safe; supplying a model-ready
# example of the wanted shape is not — every seeded template tic in this
# network's history came from a prompt handing over the sentence it
# wanted (see CLAUDE.md, "de-seed by shape, never with a quotable
# example"). So this spec describes the shape and forbids the failures.
_COLD_OPEN_BANNED = (
    "welcome to", "welcome back", "thanks for joining", "thanks for tuning in",
    "it's a new day", "glad to have you", "good to have you",
    "let's dive in", "let's dive into", "let's get into it",
    "let's get started", "here's what you need to know",
    "buckle up", "strap in", "hold onto your", "you won't believe",
    "in today's episode", "on today's show", "today is",
)


def build_cold_open_spec(show_slug: str = "", *, is_ru: bool = False) -> str:
    """The cold-open rules injected into every podcast prompt.

    A single shared spec rather than fifteen hand-written variants, so
    the rule is identical everywhere and changes in one place.

    Deliberately contains NO example sentence. The instruction states
    what the first words must DO and what they must never be; inventing
    the line is the model's job, and handing it a specimen is how this
    network has repeatedly seeded a tic across every episode of a show.
    """
    if is_ru:
        return (
            "ХОЛОДНОЕ ОТКРЫТИЕ — первые слова эпизода:\n"
            "- Начни СРАЗУ с самой конкретной и содержательной деталью "
            "сегодняшнего материала: цифра, изменение, противоречие или "
            "результат, который сам по себе вызывает интерес. Одна-две "
            "фразы, максимум.\n"
            "- Никаких приветствий, никакой даты, никаких «сегодня в "
            "выпуске», никакого приглашения слушать. Слушатель уже здесь.\n"
            "- Это должен быть настоящий факт из материала, а не обещание "
            "или интрига. Никогда не преувеличивай и не придумывай.\n"
            "- Только ПОСЛЕ этого — короткая строка с названием передачи."
        )
    banned = "; ".join(f'"{p}"' for p in _COLD_OPEN_BANNED)
    return (
        "COLD OPEN — the first words of the episode:\n"
        "- Open IMMEDIATELY on the single most concrete, consequential "
        "detail in today's material: a number, a reversal, a result, a "
        "contradiction — something that earns attention on its own merit. "
        "One or two sentences, no more.\n"
        "- No greeting, no date, no episode number, no host name, no "
        "invitation to keep listening. The listener is already here; "
        "spending their first seconds on housekeeping is what loses them.\n"
        "- It must be a REAL specific from the material, stated plainly. "
        "Not a teaser, not a riddle, not a promise of what is coming. "
        "Never overstate, never invent, never withhold the fact to create "
        "suspense — the fact IS the hook.\n"
        "- Do not open with any of these, in any language or variation: "
        f"{banned}. They signal a podcast clearing its throat.\n"
        "- It must survive the accuracy test of a wire report — but it is "
        "NOT written like one. Say it the way one person tells another "
        "something they just found out: plain words, real voice, no "
        "announcer cadence and no press-release register.\n"
        "- CHOOSE THE RIGHT FACT. Of everything in today's material, the "
        "opener is whichever item a well-informed listener would least "
        "expect to be true — the reversal, the number that broke a trend, "
        "the thing that was supposed to be impossible and now is not. "
        "Rank the day's items by that test and open on the winner, even "
        "when it is not the biggest story.\n"
        "- MAKE THE STAKES LAND IN THE SAME BREATH. A number alone is "
        "trivia. State the fact and, in the same sentence or the very "
        "next one, what it changes and for whom. If you cannot say why "
        "it matters in one clause, it is the wrong opening fact.\n"
        "- Prefer the concrete to the abstract every time: a named thing, "
        "a real quantity, a specific actor doing a specific thing. Trade "
        "categories for instances.\n"
        "- Short sentences. Active voice. Lead with the subject doing the "
        "thing, not with scene-setting or a subordinate clause.\n"
        "- Never open on a question. It reads as a stall and the listener "
        "answers it by leaving.\n"
        "- ONLY AFTER the cold open, give the short identity line."
    )


# The ONLY tags Grok TTS consumes silently. Anything outside this set is
# spoken aloud as a literal word — that is the landmine-#17 leak shape
# (M&A Ep045 voiced "Fast." at chunk boundaries; UC Ep001 voiced "Build
# intensity."). Adding to this list requires listening evidence, not
# documentation.
_SANCTIONED_TAGS = ("[breath]", "[pause]", "[long-pause]",
                    "<emphasis>...</emphasis>")


def build_delivery_spec(show_slug: str = "", *, is_ru: bool = False) -> str:
    """Performance direction injected into every podcast prompt.

    Why this exists and why it is shaped this way
    ---------------------------------------------
    A DELIVERY block used to live in all 12 podcast prompts and was
    dropped in May 2026 because it was not working: of 56 sampled
    ``_tts.txt`` files only 10 had any tag at all, never reliably. It was
    paying prompt-token cost for no measurable change.

    The diagnosis was "the model ignores it". The likelier reading is
    that the old block asked for a MOOD ("deliver with energy") and gave
    no test for whether the instruction had been followed. This version
    is countable — a specific budget, specific placements, and a rule for
    what to do when unsure — because an instruction the model can check
    itself against is one it can actually comply with.

    Landmine #17 governs everything here. PROGRAMMATIC tag injection has
    a 100% regression rate on this voice (``engine/prosody.py``, deleted;
    the phonetic respellings, reverted). This is not that: the tags are
    placed by the writer at points the MEANING calls for, which is the
    one variant with a working precedent in this network — dp_pod has
    carried a voice-direction block since launch.

    Deliberately contains no example sentence, for the same reason
    ``build_cold_open_spec`` does not: every seeded template tic in this
    network's history came from a prompt handing over the line it wanted.
    """
    if is_ru:
        return (
            "ПОДАЧА — как это должно звучать вслух:\n"
            "- Пиши так, как говорят, а не как пишут. Короткие фразы. "
            "Знаки препинания — это ритм: точка останавливает, тире "
            "подхватывает.\n"
            "- Разрешены ТОЛЬКО эти пометки: [breath], [pause], "
            "[long-pause], <emphasis>...</emphasis>. Любая другая "
            "пометка будет прочитана вслух как обычное слово.\n"
            "- Всего 3-6 пометок на весь выпуск. Ставь их там, где смысл "
            "сам требует паузы: перед важной цифрой, на повороте мысли, "
            "после вопроса, который стоит обдумать.\n"
            "- <emphasis> — только на одном слове, от которого зависит "
            "смысл фразы. Не на целом предложении.\n"
            "- Сомневаешься — не ставь. Ровная честная речь лучше, чем "
            "наигранная."
        )
    tags = ", ".join(_SANCTIONED_TAGS)
    return (
        "DELIVERY — how this must sound read aloud:\n"
        "- Write for the ear. This is one person telling another person "
        "something worth knowing, not copy being read out. If a sentence "
        "would sound odd said out loud to a friend, rewrite it.\n"
        "- Use plain, physical verbs. Say what a thing DOES. Corporate "
        "register (leverage, utilise, robust, in terms of) and press-"
        "release nouns flatten narration faster than anything else.\n"
        "- Vary sentence length deliberately, and let the variation do the "
        "work punctuation cannot. Several long sentences in a row drone; "
        "several short ones in a row sound clipped. The CONTRAST between "
        "them is what reads as a human thinking.\n"
        "- Give a big number somewhere to land. State it, then translate "
        "it into something a listener can picture — a rate, a comparison, "
        "a before-and-after. A number nobody can picture is noise.\n"
        "- Address the listener directly when it is earned, sparingly. "
        "Second person wakes an audience up; used every paragraph it "
        "becomes a tic.\n"
        "- Never narrate the structure of the episode out loud. No "
        "signposting what you are about to cover — just cover it.\n"
        f"- Speech tags are OPTIONAL and capped: at most 3 in the whole "
        f"episode, and ONLY these — {tags}. Every other tag is spoken "
        "aloud as a literal word; episodes have shipped with the host "
        "saying a tag name out loud. Use one only where the meaning "
        "already wants a beat, never for decoration, and <emphasis> only "
        "on a single word. Rhythm from sentence construction is worth "
        "more than any tag, so if in doubt use none."
    )


def build_closing_block(
    show_slug: str,
    *,
    episode_num: int,
    today_str: str,
    date: datetime.date | None = None,
    extra_context: dict[str, Any] | None = None,
    youtube_channel_handle: str = "",
) -> str:
    """Build a dynamic, day-varying closing block for the given show.

    Parameters
    ----------
    show_slug:
        The show's slug.
    episode_num:
        Episode number.
    today_str:
        Human-readable date string.
    date:
        ``datetime.date`` for deterministic selection.
    extra_context:
        Optional dict with show-specific vars (e.g. Tesla stock price/change).
    youtube_channel_handle:
        Optional ``@handle`` of the show's YouTube channel (e.g.
        ``"@NerraNetwork"``). When set, a brief callout sentence is
        appended to the closing so the spoken script mentions where
        listeners can watch the video version.

    Returns
    -------
    str
        A complete closing block prefixed with the host name.
    """
    if date is None:
        date = datetime.date.today()

    _is_ru = show_slug in _RUSSIAN_SPOKEN_SHOWS
    personality = _SHOW_PERSONALITIES.get(show_slug)
    if not personality:
        logger.warning("No closing personality for show '%s' — using generic.", show_slug)
        base = (
            "Patrick: That's the show for today. Thanks for listening, "
            "and I'll see you tomorrow."
        )
        return _maybe_append_youtube_cta(base, youtube_channel_handle, is_ru=_is_ru)

    host = personality["host"]
    closing_pool = personality.get("closings", [])
    if not closing_pool:
        return _maybe_append_youtube_cta(
            f"{host}: Thanks for listening. See you tomorrow.",
            youtube_channel_handle, is_ru=_is_ru,
        )

    closing = _pick(closing_pool, show_slug, date, salt="closing")
    return _maybe_append_youtube_cta(f"{host}: {closing}",
                                     youtube_channel_handle, is_ru=_is_ru)


# Shows whose host actually SPEAKS Russian — the YouTube call-out must be
# localized for them (an English sentence on the Olya voice is the same wart
# class as the spoken AI disclosure that was localized in June 2026).
# Привет, Русский! is *taught in English* (the host narrates in English),
# so it keeps the English call-out.
_RUSSIAN_SPOKEN_SHOWS = frozenset({"finansy_prosto"})


def _maybe_append_youtube_cta(closing: str, handle: str, is_ru: bool = False) -> str:
    """Append a brief "watch on YouTube" callout when a handle is set.

    Idempotent — won't duplicate the line if it's already present.

    The leading ``@`` is stripped from the spoken handle: the TTS voices it
    as the word "at", which collided with the "at" already in the English
    call-out and shipped as "...find us on YouTube at at Nerra Network" in
    49+ episodes across six shows. Channel names read cleanly without the
    sigil. When ``is_ru`` is set the call-out itself is in Russian so a
    Russian-speaking host doesn't switch to English for one sentence.
    """
    handle = (handle or "").strip()
    if not handle:
        return closing
    if "youtube" in closing.lower() or handle.lower() in closing.lower():
        return closing
    spoken_handle = handle.lstrip("@").strip()
    # Split the English channel's CamelCase handle into the spaced brand so the
    # TTS pronounces "Nerra Network" identically to every other brand mention in
    # the closing. The compound "NerraNetwork" otherwise gets a guessed,
    # drifting pronunciation (the promo also says "Nerra Network" spaced and
    # "nerranetwork.com"), so the same segment shipped 2-3 different "Nerra"s.
    # EN-only by design: the Russian "NerraRU" must stay one token — a blanket
    # CamelCase split would voice it "Nerra R U" on the Olya voice.
    if spoken_handle == "NerraNetwork":
        spoken_handle = "Nerra Network"
    if is_ru:
        cta = (
            f" А если вам удобнее смотреть, а не только слушать — "
            f"мы есть на YouTube, канал {spoken_handle}. "
            f"Ссылка в описании выпуска."
        )
    else:
        cta = (
            f" And if you'd rather watch than listen, find us on YouTube at "
            f"{spoken_handle} — link's in the show notes."
        )
    return closing + cta


def get_show_host(show_slug: str) -> str:
    """Return the host name/label for a show."""
    personality = _SHOW_PERSONALITIES.get(show_slug)
    if personality:
        return personality["host"]
    return "Patrick"
