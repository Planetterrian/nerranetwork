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
        "show_name": "Tesla Shorts Time Daily",
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
            "We'll cover what happened, how different viewpoints frame it — so you can decide for yourself.",
            "Let's look at the day's news from every angle.",
            "Here's the news, the perspectives, and the questions worth asking.",
            "Today's stories, multiple viewpoints, your call.",
        ],
        "day_colors": {
            0: {
                "framings": [
                    "New week, fresh perspectives. Let's see what happened over the weekend and what's developing today.",
                    "Starting the week with a clear-eyed look at the stories that matter.",
                ],
            },
        },
        "closings": [
            (
                "That's Omni View. For full source links and more context, check out today's "
                "written briefing on the Omni View summaries page. As always — compare outlets, "
                "look for primary documents, and separate what's known from what's assumed. "
                "If balanced perspectives are valuable to you, share this with a friend and "
                "subscribe wherever you listen. See you tomorrow."
            ),
            (
                "That wraps up today's Omni View. Remember — the best-informed people read "
                "more than one perspective. If this show helps you do that, share it with "
                "someone who values fair coverage. See you tomorrow."
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
            "episode {ep}, for {date}. Your daily environmental intelligence briefing.",
        ],
        "framings": [
            "Your daily briefing on environmental regulatory, science, and compliance developments that matter for Canadian professionals.",
            "Here's what changed overnight in the environmental regulatory landscape.",
            "Let's get into today's environmental developments across Canadian jurisdictions.",
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
                "podcasts. We're back tomorrow. Have a productive day."
            ),
            (
                "That covers today's environmental intelligence. If you found this useful, "
                "share it with a colleague who needs to stay current. "
                "We're back tomorrow morning."
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
        "closings": [
            (
                "На сегодня всё! Напоминаю, что мы делимся общей информацией для обучения, "
                "а не финансовыми рекомендациями. Для важных решений поговорите с финансовым "
                "советником. Помните, каждый финансовый эксперт когда-то начинал с нуля — "
                "точно так же, как мы с вами сейчас. Берегите себя, берегите свои деньги, "
                "и до завтра!"
            ),
            (
                "Вот и всё на сегодня! Если что-то из выпуска показалось полезным — "
                "поделитесь с подругой. Вместе разбираться веселее! "
                "Берегите себя, и до завтра!"
            ),
        ],
    },
    "privet_russian": {
        "host": "Host",
        "show_name": "Привет, Русский!",
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
        "closings": [
            (
                "Molodets! That means, well done! Remember, every expert started as a "
                "beginner. Practice saying today's words out loud, even just once, and "
                "you'll be amazed how fast you learn. See you next time! Poka! "
                "That's Russian for, bye!"
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
        "closings": [
            (
                "That's Unintended Consequences for today. If this episode gave you something "
                "to think about, share it with a friend who'd appreciate the story. "
                "Subscribe wherever you listen, and we'll be back tomorrow with another case."
            ),
            (
                "That wraps today's case. The lessons travel further when you share them — "
                "send this episode to someone who'd find it useful. We'll see you tomorrow."
            ),
        ],
    },
}


# ---------------------------------------------------------------------------
# Milestone detection
# ---------------------------------------------------------------------------

def _milestone_note(episode_num: int) -> str | None:
    """Return a brief milestone acknowledgment for round episode numbers."""
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
    weekday = date.weekday()

    # Select greeting — prefer day-specific if available
    day_overrides = personality.get("day_colors", {}).get(weekday, {})
    greeting_pool = day_overrides.get("greetings", personality["greetings"])
    greeting = _pick(greeting_pool, show_slug, date, salt="greeting")

    # Select opener
    opener_pool = personality["openers"]
    opener = _pick(opener_pool, show_slug, date, salt="opener")
    opener = opener.format(ep=episode_num, date=today_str)

    # Select framing — prefer day-specific if available
    framing_pool = day_overrides.get("framings", personality["framings"])
    framing = _pick(framing_pool, show_slug, date, salt="framing")

    # Assemble
    parts = [f"{host}: {greeting} {show_name}, {opener} {framing}"]

    # Add milestone note if applicable
    milestone = _milestone_note(episode_num)
    if milestone:
        parts.append(f" {milestone}")

    intro = "".join(parts)

    logger.debug("Dynamic intro for %s ep%d: %s", show_slug, episode_num, intro[:80])
    return intro


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

    personality = _SHOW_PERSONALITIES.get(show_slug)
    if not personality:
        logger.warning("No closing personality for show '%s' — using generic.", show_slug)
        base = (
            "Patrick: That's the show for today. Thanks for listening, "
            "and I'll see you tomorrow."
        )
        return _maybe_append_youtube_cta(base, youtube_channel_handle)

    host = personality["host"]
    closing_pool = personality.get("closings", [])
    if not closing_pool:
        return _maybe_append_youtube_cta(
            f"{host}: Thanks for listening. See you tomorrow.",
            youtube_channel_handle,
        )

    closing = _pick(closing_pool, show_slug, date, salt="closing")
    return _maybe_append_youtube_cta(f"{host}: {closing}",
                                     youtube_channel_handle)


def _maybe_append_youtube_cta(closing: str, handle: str) -> str:
    """Append a brief "watch on YouTube" callout when a handle is set.

    Idempotent — won't duplicate the line if it's already present.
    """
    handle = (handle or "").strip()
    if not handle:
        return closing
    if "youtube" in closing.lower() or handle.lower() in closing.lower():
        return closing
    cta = (
        f" And if you'd rather watch than listen, find us on YouTube at "
        f"{handle} — link's in the show notes."
    )
    return closing + cta


def get_show_host(show_slug: str) -> str:
    """Return the host name/label for a show."""
    personality = _SHOW_PERSONALITIES.get(show_slug)
    if personality:
        return personality["host"]
    return "Patrick"
