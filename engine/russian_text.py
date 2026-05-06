"""Russian-language post-processing for podcast TTS scripts.

The LLM produces partially-Russian scripts that occasionally leave
English month/year/date strings inline ("May sixth, twenty twenty-six"
inside an otherwise-Russian sentence). Grok TTS reads those English
strings literally with the Russian voice, which sounds awful.

This module ships a single helper, ``russify_english_dates(text)``,
that finds English-form dates and replaces them with Russian
equivalents (genitive case, suitable for "сегодня шестое мая…" style
sentences). Operator caught (Финансы Просто Ep32, May 6 2026
production audit) the LLM emitting "May sixth, twenty twenty-six"
inside a Russian sentence.

Scope is deliberately narrow:

  - Only matches English month names (``January`` … ``December``).
    Russian months bypass without change.
  - Handles two ordinal forms: numeric (``May 6``) and worded
    (``May sixth``).
  - Handles two year forms: numeric (``2026``) and worded
    (``twenty twenty-six``).

Pipeline integration: called once on the Russian-show podcast
script just before TTS. Idempotent — running it twice produces
the same output as running once.
"""

from __future__ import annotations

import re
from typing import Dict


_MONTHS_EN_TO_RU: Dict[str, str] = {
    "january": "января",
    "february": "февраля",
    "march": "марта",
    "april": "апреля",
    "may": "мая",
    "june": "июня",
    "july": "июля",
    "august": "августа",
    "september": "сентября",
    "october": "октября",
    "november": "ноября",
    "december": "декабря",
}


_ORDINAL_NUM_TO_RU: Dict[int, str] = {
    1: "первое",  2: "второе",  3: "третье",  4: "четвёртое",
    5: "пятое",   6: "шестое",  7: "седьмое", 8: "восьмое",
    9: "девятое", 10: "десятое",
    11: "одиннадцатое", 12: "двенадцатое", 13: "тринадцатое",
    14: "четырнадцатое", 15: "пятнадцатое", 16: "шестнадцатое",
    17: "семнадцатое", 18: "восемнадцатое", 19: "девятнадцатое",
    20: "двадцатое",
    21: "двадцать первое", 22: "двадцать второе", 23: "двадцать третье",
    24: "двадцать четвёртое", 25: "двадцать пятое", 26: "двадцать шестое",
    27: "двадцать седьмое", 28: "двадцать восьмое", 29: "двадцать девятое",
    30: "тридцатое", 31: "тридцать первое",
}


# Worded English ordinals → number (so we can route through the
# numeric → Russian table above). Covers 1-31.
_ORDINAL_WORD_TO_NUM: Dict[str, int] = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
    "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14,
    "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18,
    "nineteenth": 19, "twentieth": 20,
    "twenty-first": 21, "twenty first": 21,
    "twenty-second": 22, "twenty second": 22,
    "twenty-third": 23, "twenty third": 23,
    "twenty-fourth": 24, "twenty fourth": 24,
    "twenty-fifth": 25, "twenty fifth": 25,
    "twenty-sixth": 26, "twenty sixth": 26,
    "twenty-seventh": 27, "twenty seventh": 27,
    "twenty-eighth": 28, "twenty eighth": 28,
    "twenty-ninth": 29, "twenty ninth": 29,
    "thirtieth": 30,
    "thirty-first": 31, "thirty first": 31,
}


def _russify_year(year: int) -> str:
    """Spell out 2020-2030 in genitive case. Operator's catalogue
    only ships in this window (and historic episodes pre-2020 don't
    show up in TTS scripts). Years outside the table fall back to
    the digits — better than silently corrupting."""
    catalogue: Dict[int, str] = {
        2020: "две тысячи двадцатого года",
        2021: "две тысячи двадцать первого года",
        2022: "две тысячи двадцать второго года",
        2023: "две тысячи двадцать третьего года",
        2024: "две тысячи двадцать четвёртого года",
        2025: "две тысячи двадцать пятого года",
        2026: "две тысячи двадцать шестого года",
        2027: "две тысячи двадцать седьмого года",
        2028: "две тысячи двадцать восьмого года",
        2029: "две тысячи двадцать девятого года",
        2030: "две тысячи тридцатого года",
    }
    return catalogue.get(year, str(year))


_WORDED_YEAR_TO_NUM: Dict[str, int] = {
    "twenty twenty": 2020,
    "twenty twenty-one": 2021, "twenty twenty one": 2021,
    "twenty twenty-two": 2022, "twenty twenty two": 2022,
    "twenty twenty-three": 2023, "twenty twenty three": 2023,
    "twenty twenty-four": 2024, "twenty twenty four": 2024,
    "twenty twenty-five": 2025, "twenty twenty five": 2025,
    "twenty twenty-six": 2026, "twenty twenty six": 2026,
    "twenty twenty-seven": 2027, "twenty twenty seven": 2027,
    "twenty twenty-eight": 2028, "twenty twenty eight": 2028,
    "twenty twenty-nine": 2029, "twenty twenty nine": 2029,
    "twenty thirty": 2030,
}


# ``May 6, 2026`` and ``May 6 2026`` — numeric day, numeric year.
_NUMERIC_DATE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{1,2})(?:st|nd|rd|th)?"
    r",?\s+(\d{4})\b",
    re.IGNORECASE,
)

# ``May sixth, twenty twenty-six`` — worded day, worded year.
_WORDED_DATE_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    r"eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|"
    r"eighteenth|nineteenth|twentieth|"
    r"twenty[\s-](?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth)|"
    r"thirtieth|thirty[\s-]first)"
    r",?\s+"
    r"(twenty\s+(?:twenty|thirty)(?:[\s-](?:one|two|three|four|five|six|seven|eight|nine))?)",
    re.IGNORECASE,
)


def russify_english_dates(text: str) -> str:
    """Replace English-form date expressions with Russian equivalents.

    Idempotent: running this on already-Russified text is a no-op
    (Russian month names don't match the English regex).
    """
    if not text:
        return text

    def _numeric_sub(match: re.Match) -> str:
        month_en = match.group(1).lower()
        day = int(match.group(2))
        year = int(match.group(3))
        ru_month = _MONTHS_EN_TO_RU.get(month_en, match.group(1))
        ru_day = _ORDINAL_NUM_TO_RU.get(day, str(day))
        ru_year = _russify_year(year)
        return f"{ru_day} {ru_month} {ru_year}"

    def _worded_sub(match: re.Match) -> str:
        month_en = match.group(1).lower()
        day_word = match.group(2).lower().strip()
        year_word = match.group(3).lower().strip()
        ru_month = _MONTHS_EN_TO_RU.get(month_en, match.group(1))
        # Normalize ``twenty-first`` and ``twenty first`` to a single
        # form before lookup. The dict has both spellings.
        day_num = _ORDINAL_WORD_TO_NUM.get(day_word)
        if day_num is None:
            return match.group(0)  # punt — unknown ordinal
        year_num = _WORDED_YEAR_TO_NUM.get(year_word)
        if year_num is None:
            return match.group(0)  # punt — unknown year phrasing
        ru_day = _ORDINAL_NUM_TO_RU.get(day_num, str(day_num))
        ru_year = _russify_year(year_num)
        return f"{ru_day} {ru_month} {ru_year}"

    text = _WORDED_DATE_RE.sub(_worded_sub, text)
    text = _NUMERIC_DATE_RE.sub(_numeric_sub, text)
    return text
