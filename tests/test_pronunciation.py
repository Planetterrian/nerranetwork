"""Tests for the shared pronunciation module (assets/pronunciation.py).

Covers text cleanup, number/value converters, dictionary-based fixes,
and the top-level prepare_text_for_tts() entry point.
"""

import sys
from pathlib import Path

# Ensure project root is on the path so `assets` and `engine` can be imported.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from assets.pronunciation import (
    strip_emojis,
    strip_markdown,
    strip_urls,
    strip_unicode_decorations,
    clean_social_handles,
    clean_text_for_tts,
    strip_financial_parentheses,
    replace_canadian_currency,
    replace_signed_currency,
    replace_signed_numbers,
    replace_multiplier_notation,
    replace_versus,
    replace_approximate,
    replace_common_abbreviations,
    replace_price_ranges,
    replace_hashtag_numbers,
    replace_standalone_ampersand,
    replace_currency,
    replace_percentages,
    replace_dates,
    replace_times,
    replace_timezones,
    replace_episode_numbers,
    replace_ordinal_numbers,
    replace_roman_numerals,
    replace_quarter_notation,
    replace_units,
    replace_large_numbers_with_k,
    replace_scientific_designations,
    replace_standalone_large_numbers,
    apply_pronunciation_fixes,
    prepare_text_for_tts,
    _number_to_ordinal,
    _year_to_words,
    COMMON_ACRONYMS,
    WORD_PRONUNCIATIONS,
)


# ===================== Text Cleanup =====================

class TestStripEmojis:
    def test_removes_common_emojis(self):
        assert strip_emojis("Hello 🚗⚡ world") == "Hello  world"

    def test_removes_number_keycaps(self):
        result = strip_emojis("1️⃣ First item")
        # After emoji stripping, the digit should remain
        assert "First item" in result

    def test_preserves_normal_text(self):
        assert strip_emojis("No emojis here") == "No emojis here"


class TestStripMarkdown:
    def test_removes_bold(self):
        assert strip_markdown("This is **bold** text") == "This is bold text"

    def test_removes_headings(self):
        assert strip_markdown("### Heading\nContent").strip() == "Heading\nContent"

    def test_removes_horizontal_rules(self):
        assert "━" not in strip_markdown("━━━━━━━━━━━━━━━━━━━━")

    def test_preserves_content(self):
        assert strip_markdown("Plain text stays") == "Plain text stays"


class TestStripUrls:
    def test_removes_source_url_lines(self):
        text = "Some news.\nSource: https://example.com/article"
        result = strip_urls(text)
        assert "https://" not in result

    def test_removes_source_post_url(self):
        text = "Content\nSource/Post: https://example.com"
        result = strip_urls(text)
        assert "https://" not in result

    def test_removes_inline_urls(self):
        text = "Visit https://tesla.com for details"
        result = strip_urls(text)
        assert "https://" not in result
        assert "Visit" in result

    def test_preserves_non_url_text(self):
        assert strip_urls("No links here") == "No links here"


class TestStripUnicodeDecorations:
    def test_removes_zero_width_chars(self):
        assert strip_unicode_decorations("hello\u200Bworld") == "helloworld"
        assert strip_unicode_decorations("test\u2060data") == "testdata"

    def test_removes_box_drawing(self):
        result = strip_unicode_decorations("─── Section ───")
        assert "─" not in result


class TestCleanSocialHandles:
    def test_known_handles(self):
        result = clean_social_handles("Follow @teslashortstime")
        assert result == "Follow at tesla shorts time"

    def test_camelcase_handles(self):
        result = clean_social_handles("@SomeUser posted")
        assert "at Some User" in result


class TestCleanTextForTts:
    def test_full_cleanup(self):
        text = "🎙️ **Title**\n━━━\nSource: https://example.com\nContent @teslashortstime"
        result = clean_text_for_tts(text)
        assert "🎙" not in result
        assert "**" not in result
        assert "━" not in result
        assert "https://" not in result
        assert "at tesla shorts time" in result


# ===================== Number / Value Converters =====================

class TestNumberToOrdinal:
    def test_first(self):
        assert _number_to_ordinal(1) == "first"

    def test_second(self):
        assert _number_to_ordinal(2) == "second"

    def test_third(self):
        assert _number_to_ordinal(3) == "third"

    def test_eleventh(self):
        assert _number_to_ordinal(11) == "eleventh"

    def test_twentieth(self):
        assert _number_to_ordinal(20) == "twentieth"

    def test_twenty_first(self):
        assert _number_to_ordinal(21) == "twenty-first"

    def test_thirtieth(self):
        assert _number_to_ordinal(30) == "thirtieth"

    def test_fifteenth(self):
        assert _number_to_ordinal(15) == "fifteenth"


class TestYearToWords:
    def test_2026(self):
        assert _year_to_words(2026) == "twenty twenty-six"

    def test_2000(self):
        assert _year_to_words(2000) == "two thousand"

    def test_2001(self):
        assert _year_to_words(2001) == "two thousand one"

    def test_1999(self):
        assert _year_to_words(1999) == "nineteen ninety-nine"

    def test_1564(self):
        # Should be "fifteen sixty-four" not "one thousand five hundred sixty-four"
        result = _year_to_words(1564)
        assert "fifteen" in result
        assert "sixty-four" in result

    def test_1900(self):
        assert _year_to_words(1900) == "nineteen hundred"


class TestReplaceCanadianCurrency:
    """Operator caught (TST Ep471, May 13 2026) Grok TTS reading
    'C$39,490' as 'C thirty-nine dollars four hundred ninety' — the
    leading 'C' got stranded as a syllable and the comma was treated
    as a separator rather than a thousands marker. The transform
    pre-rewrites C$ amounts to a form the downstream currency
    handler reads correctly."""

    def test_canadian_dollars_with_thousands_comma(self):
        result = replace_canadian_currency("Tesla sells the Model 3 for C$39,490 in Canada")
        # No stranded "C" left; comma intact for downstream currency expansion.
        assert "C$" not in result
        assert "39,490 Canadian dollars" in result

    def test_canadian_dollars_with_decimal(self):
        result = replace_canadian_currency("Listed at C$1,250.50 today")
        assert "C$" not in result
        assert "1,250.50 Canadian dollars" in result

    def test_canadian_dollars_small_amount(self):
        result = replace_canadian_currency("Charged C$15 for the part")
        assert "15 Canadian dollars" in result

    def test_cad_prefix_variant(self):
        result = replace_canadian_currency("MSRP CAD$100,000 nationwide")
        assert "100,000 Canadian dollars" in result

    def test_cad_prefix_case_insensitive(self):
        result = replace_canadian_currency("Selling for cad$500 used")
        assert "500 Canadian dollars" in result

    def test_us_dollars_untouched(self):
        """US dollar amounts MUST pass through — only the C$/CAD$
        prefix triggers the transform."""
        result = replace_canadian_currency("Sticker price is $79,990 in California")
        assert "$79,990" in result
        assert "Canadian" not in result

    def test_no_currency_no_op(self):
        """Plain text is returned unchanged."""
        text = "There were no prices mentioned in this sentence."
        assert replace_canadian_currency(text) == text

    def test_runs_in_prepare_text_for_tts_pipeline(self):
        """End-to-end: C$X,XXX through the full TTS pipeline produces
        the correct spoken form (Canadian context preserved, comma
        absorbed by the standard currency handler)."""
        result = prepare_text_for_tts("Tesla sells the Model 3 for C$39,490 in Canada.")
        assert "C$" not in result
        assert "Canadian" in result
        # The downstream replace_currency handles "39,490 Canadian
        # dollars" → "thirty-nine thousand four hundred ninety
        # Canadian dollars" (or similar). Confirm no stranded comma.
        assert ",490" not in result
        assert "thirty-nine thousand" in result


class TestReplaceCurrency:
    def test_dollars_with_cents(self):
        result = replace_currency("Price is $417.44")
        assert "four hundred seventeen dollars and forty-four cents" in result

    def test_whole_dollars(self):
        result = replace_currency("Cost $500")
        assert "five hundred dollars" in result

    def test_large_currency(self):
        result = replace_currency("Worth $3 billion")
        assert "three billion dollars" in result

    def test_euros(self):
        result = replace_currency("Price \u20ac50")
        assert "fifty euros" in result

    def test_pounds(self):
        result = replace_currency("Cost \u00a3100")
        assert "one hundred pounds" in result


class TestReplacePercentages:
    def test_simple_percentage(self):
        result = replace_percentages("Up 30%")
        assert "thirty percent" in result

    def test_positive_sign(self):
        result = replace_percentages("+0.27%")
        assert "plus" in result
        assert "percent" in result

    def test_negative_sign(self):
        result = replace_percentages("-5.5%")
        assert "minus" in result
        assert "percent" in result

    def test_decimal_percentage(self):
        result = replace_percentages("3.59%")
        assert "percent" in result


class TestReplaceDates:
    def test_month_day_year(self):
        result = replace_dates("February 15, 2026")
        assert "fifteenth" in result
        assert "twenty twenty-six" in result

    def test_day_month_year(self):
        result = replace_dates("13 February, 2026")
        assert "thirteenth" in result

    def test_abbreviated_month(self):
        result = replace_dates("Feb 15, 2026")
        assert "fifteenth" in result

    def test_first_day(self):
        result = replace_dates("March 1, 2026")
        assert "first" in result

    def test_historical_year(self):
        result = replace_dates("February 15, 1564")
        assert "fifteen" in result


class TestReplaceTimes:
    def test_am_time(self):
        result = replace_times("at 03:08 AM")
        assert "three oh eight A M" in result

    def test_pm_time(self):
        result = replace_times("at 2:30 PM")
        assert "two thirty P M" in result

    def test_midnight(self):
        result = replace_times("00:00")
        assert "twelve" in result

    def test_time_with_periods(self):
        result = replace_times("at 2:59 a.m.")
        assert "two" in result
        assert "fifty-nine" in result

    # --- HH:MM:SS + compact UTC times (SpaceX Ep8 garble, 2026-06-19) ---
    # The digest said "1:50:45 a.m." and "0850:45 UTC"; the seconds-blind
    # matcher shipped "one fifty A M:45 a.m." and "0850:45 U T C" to TTS.

    def test_time_with_seconds_drops_seconds(self):
        # 1:50:45 a.m. must not strand the ":45" — seconds are dropped.
        result = replace_times("at 1:50:45 a.m. Pacific")
        assert "one fifty A M" in result
        assert ":45" not in result
        assert "M:" not in result  # no stranded "A M:45"

    def test_pm_time_with_seconds(self):
        result = replace_times("at 2:30:15 PM")
        assert "two thirty P M" in result
        assert ":15" not in result

    def test_compact_utc_time(self):
        # 0850:45 UTC -> 24-hour spoken, seconds dropped, zone left literal.
        result = replace_times("Liftoff at 0850:45 UTC after checks")
        assert "oh eight fifty UTC" in result
        assert "0850" not in result
        assert ":45" not in result

    def test_compact_utc_time_no_seconds(self):
        result = replace_times("window at 1430 GMT")
        assert "fourteen thirty GMT" in result

    def test_time_without_ampm_keeps_trailing_space(self):
        # The whitespace before an absent AM/PM must NOT be eaten (it used
        # to glue the next word: "two thirty P MUTC").
        result = replace_times("launched at 14:30:00 UTC today")
        assert "P M UTC" in result
        assert "P MUTC" not in result

    def test_large_number_not_a_time(self):
        # A bare count must not be mistaken for a compact time.
        assert replace_times("the 15000 satellites filing") == (
            "the 15000 satellites filing"
        )
        assert replace_times("In 2026 the program") == "In 2026 the program"


class TestReplaceTimezones:
    def test_pst(self):
        assert "Pacific Standard Time" in replace_timezones("3 PM PST")

    def test_est(self):
        assert "Eastern Standard Time" in replace_timezones("8 AM EST")

    def test_utc(self):
        assert "U T C" in replace_timezones("12:00 UTC")


class TestReplaceEpisodeNumbers:
    def test_episode_number(self):
        result = replace_episode_numbers("Episode 39")
        assert "thirty-nine" in result

    def test_episode_large_number(self):
        result = replace_episode_numbers("episode 336")
        assert "three hundred thirty-six" in result


class TestReplaceOrdinalNumbers:
    def test_seventh(self):
        assert replace_ordinal_numbers("7th magnitude") == "seventh magnitude"

    def test_tenth(self):
        assert replace_ordinal_numbers("10th flight") == "tenth flight"

    def test_first(self):
        assert replace_ordinal_numbers("1st place") == "first place"

    def test_twenty_second(self):
        result = replace_ordinal_numbers("22nd item")
        assert "twenty-second" in result


class TestReplaceRomanNumerals:
    def test_phase_three(self):
        result = replace_roman_numerals("Phase III trials")
        assert "Phase three" in result

    def test_part_two(self):
        result = replace_roman_numerals("Part II begins")
        assert "Part two" in result

    def test_no_false_positive(self):
        # "I" alone should not be converted without context
        result = replace_roman_numerals("I went home")
        assert result == "I went home"

    def test_generation_four(self):
        result = replace_roman_numerals("Generation IV reactor")
        assert "Generation four" in result


class TestReplaceQuarterNotation:
    def test_quarter_with_year(self):
        result = replace_quarter_notation("Q2 2026")
        assert "Q two twenty twenty-six" in result

    def test_standalone_quarter(self):
        result = replace_quarter_notation("in Q4")
        assert "Q four" in result


class TestReplaceUnits:
    def test_kilometers(self):
        result = replace_units("500 km away")
        assert "kilometers" in result

    def test_kilowatt_hours(self):
        result = replace_units("100 kWh battery")
        assert "kilowatt hours" in result

    def test_miles_per_hour(self):
        result = replace_units("60 mph speed")
        assert "miles per hour" in result


class TestReplaceLargeNumbersWithK:
    def test_two_point_five_k(self):
        result = replace_large_numbers_with_k("2.5k km")
        assert "two thousand five hundred" in result

    def test_plain_k(self):
        result = replace_large_numbers_with_k("10k followers")
        assert "ten thousand" in result


class TestReplaceScientificDesignations:
    def test_comet_designation(self):
        result = replace_scientific_designations("Comet C/2024 E1")
        assert "slash" in result
        assert "Comet" in result

    def test_star_catalog(self):
        result = replace_scientific_designations("HR 8799 system")
        assert "H R" in result


class TestReplaceStandaloneLargeNumbers:
    def test_comma_separated(self):
        result = replace_standalone_large_numbers("500,000 people")
        assert "five hundred thousand" in result

    def test_million(self):
        result = replace_standalone_large_numbers("2,000,000 users")
        assert "two million" in result


# ===================== Dictionary-based Fixes =====================

class TestApplyPronunciationFixes:
    def test_xai_fix(self):
        result = apply_pronunciation_fixes("The xAI company")
        assert "ex A I" in result

    def test_evs_fix(self):
        result = apply_pronunciation_fixes("Electric EVs are growing")
        assert "E Vs" in result

    def test_spacex_fix(self):
        result = apply_pronunciation_fixes("SpaceX launched")
        assert "Space X" in result

    def test_who_word_protected(self):
        result = apply_pronunciation_fixes("who did this")
        assert "who" in result
        assert "W H O" not in result

    def test_ice_word_protected(self):
        result = apply_pronunciation_fixes("The ice is cold")
        assert "ice" in result
        assert "I C E" not in result

    def test_us_pronoun_not_expanded(self):
        """'us' (pronoun) must NOT be expanded to 'U S'."""
        result = apply_pronunciation_fixes("let us know")
        assert "us" in result
        assert "U S" not in result

    def test_US_country_still_expanded(self):
        """'US' (uppercase, country) must still expand to 'U S'."""
        result = apply_pronunciation_fixes("across US cities")
        assert "U S" in result

    def test_led_verb_not_expanded(self):
        """'led' (past tense of lead) must NOT be expanded to 'L E D'."""
        result = apply_pronunciation_fixes("Tesla led the charge in EV sales")
        assert "led" in result
        assert "L E D" not in result

    def test_LED_acronym_still_expanded(self):
        """'LED' (uppercase, light-emitting diode) must still expand."""
        result = apply_pronunciation_fixes("LED headlights")
        assert "L E D" in result

    def test_dot_word_not_expanded(self):
        """'dot' must NOT be expanded to 'D O T'."""
        result = apply_pronunciation_fixes("connecting the dot")
        assert "dot" in result
        assert "D O T" not in result

    def test_DOT_acronym_still_expanded(self):
        """'DOT' (uppercase, Department of Transportation) must still expand."""
        result = apply_pronunciation_fixes("The DOT approved it")
        assert "D O T" in result

    def test_megacharger(self):
        result = apply_pronunciation_fixes("Tesla Megacharger network")
        assert "Mega-charger" in result

    def test_gigacasting(self):
        result = apply_pronunciation_fixes("Tesla's gigacasting technology")
        assert "giga-casting" in result

    def test_ig_metall(self):
        result = apply_pronunciation_fixes("IG Metall union conflict")
        assert "I G Metall" in result

    def test_robotaxi(self):
        result = apply_pronunciation_fixes("Tesla Robotaxi service")
        assert "Robo-taxi" in result

    def test_cybertruck(self):
        result = apply_pronunciation_fixes("The Cybertruck is here")
        assert "Cyber-truck" in result

    def test_planetterrian_passes_through_unchanged(self):
        """Operator caught (PT Ep060, May 11 2026 daily review) the
        respelling ``plan it TAIR ee uhn`` from PR #355 leaking into
        the saved ``_tts.txt`` and the daily-review AI flagging the
        episode as "Incoherent". Worse, Grok TTS rendered the 5
        tokens as 5 separate stressed words rather than as one
        5-syllable word — Whisper transcribed the result as "Planet
        Terra EE and Daily" / "Planet Tier TIA or EUN", confirming
        the respelling didn't even produce the intended audio.

        Both prior respellings failed:
          * ``Planet-terry-an`` (pre-PR-355) — hyphens caused Grok to
            insert "Terry" the personal name.
          * ``plan it TAIR ee uhn`` (PR #355) — 5 separated tokens.

        Without a listen-tested working respelling, the safer state
        is no override here. Grok handles the raw "Planetterrian"
        however it does, but the saved transcript / blog text are
        no longer garbled. A correct respelling will be added via
        ``shows/pronunciation_map.yaml`` (TTS-call time) once tested,
        so a wrong respelling can't leak into reader-facing text.
        """
        result = apply_pronunciation_fixes("Welcome to Planetterrian")
        # No respelling: the canonical name passes through untouched.
        assert "Planetterrian" in result
        # Neither old failed respelling survives.
        assert "Planet-terry-an" not in result
        assert "plan it TAIR ee uhn" not in result

    def test_teslarati(self):
        result = apply_pronunciation_fixes("According to Teslarati")
        assert "Tesla-rah-tee" in result


# ===================== Full Pipeline (prepare_text_for_tts) =====================

class TestPrepareTextForTts:
    def test_full_tesla_episode_snippet(self):
        """Test with a representative snippet from the latest TST episode."""
        text = (
            "🚗⚡ **Tesla Shorts Time**\n"
            "📅 **Date:** February 15, 2026 at 03:08 AM PST\n"
            "💰 **REAL-TIME TSLA price:** $417.44 +1.11 (+0.27%)\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "1️⃣ **Tesla Nears Closure of Full Self-Driving Purchasing Option**\n"
            "Source: https://www.teslarati.com/article\n"
            "SpaceX-xAI Deal confirmed. Q2 2026 production.\n"
            "S3XY Plaid models covering 2.5k km in Norway.\n"
            "DM us @teslashortstime with your thoughts!"
        )
        result = prepare_text_for_tts(text)

        # Emojis removed
        assert "🚗" not in result
        assert "📅" not in result
        assert "1️⃣" not in result or "1" in result

        # Markdown removed
        assert "**" not in result

        # URLs removed
        assert "https://" not in result

        # Unicode decorations removed
        assert "━" not in result

        # Currency converted
        assert "four hundred seventeen dollars" in result

        # Percentage converted — parens stripped first, then value expanded
        assert "percent" in result
        assert "(" not in result  # financial parens stripped

        # Signed number +1.11 converted (was bare, now "up one point one one")
        assert "up one point one one" in result

        # Date converted
        assert "fifteenth" in result

        # Time converted
        assert "three oh eight" in result

        # Timezone expanded
        assert "Pacific Standard Time" in result

        # xAI handled
        assert "ex A I" in result

        # TSLA spelled out
        assert "T S L A" in result

        # Q2 expanded
        assert "Q two" in result

        # S3XY expanded
        assert "S three X Y" in result

        # 2.5k expanded
        assert "two thousand five hundred" in result

        # Social handle expanded
        assert "at tesla shorts time" in result

    def test_empty_text(self):
        assert prepare_text_for_tts("") == ""

    def test_skip_acronyms(self):
        """TST skips ICE so it reads as 'ice' not 'I C E'."""
        result = prepare_text_for_tts("ICE vehicles vs EVs", skip_acronyms={"ICE"})
        # ICE should NOT be expanded since we skipped it
        assert "I C E" not in result

    def test_extra_acronyms(self):
        result = prepare_text_for_tts(
            "The DLT platform is great",
            extra_acronyms={"DLT": "D L T"},
        )
        assert "D L T" in result

    def test_feature_toggles(self):
        """Can disable individual features."""
        result = prepare_text_for_tts(
            "$500 item",
            do_currency=False,
            do_clean=False,
        )
        assert "$500" in result  # Currency not converted

    def test_fascinating_frontiers_snippet(self):
        """Test with FF-style content including scientific terms."""
        text = (
            "Fascinating Frontiers Episode 39\n"
            "Comet C/2024 E1 approaches!\n"
            "Cassini found water on Enceladus.\n"
            "Phase III of the mission.\n"
            "500,000 km away from Earth.\n"
            "ESA confirmed 7th flyby."
        )
        result = prepare_text_for_tts(text)
        assert "thirty-nine" in result        # Episode number
        assert "slash" in result               # Comet designation
        assert "Kah-see-nee" in result         # Cassini pronunciation
        assert "En-sell-uh-dus" in result      # Enceladus pronunciation
        assert "Phase three" in result         # Roman numeral
        assert "five hundred thousand" in result  # Large number
        assert "kilometers" in result          # Unit expansion
        assert "E S A" in result               # Acronym
        assert "seventh" in result             # Ordinal number

    def test_omni_view_snippet(self):
        """Test with OV-style content including business/politics terms."""
        text = (
            "The CEO announced the IPO.\n"
            "FDA-cleared LED device.\n"
            "EU regulations on AI.\n"
            "$2.5 billion investment.\n"
            "15% growth in Q3 2026."
        )
        result = prepare_text_for_tts(text)
        assert "C E O" in result
        assert "I P O" in result
        assert "F D A" in result
        assert "L E D" in result
        assert "E U" in result
        # AI should be expanded to "A I"
        assert "A I" in result
        assert "billion dollars" in result
        assert "fifteen percent" in result
        assert "Q three" in result

    def test_stock_price_with_change_and_status(self):
        """Full pipeline test: TSLA price line with movement and market status."""
        text = "TSLA: $417.44 +$1.11 (+0.27%) (After-hours)"
        result = prepare_text_for_tts(text)

        # Parentheses stripped
        assert "(" not in result
        assert ")" not in result

        # Market status expanded
        assert "after hours" in result

        # TSLA acronym
        assert "T S L A" in result

        # Signed currency converted
        assert "up" in result
        assert "one dollar" in result

        # Percentage expanded
        assert "percent" in result

        # Base price converted
        assert "four hundred seventeen dollars" in result

    def test_stock_price_down(self):
        """Full pipeline: negative movement."""
        text = "TSLA at $350.25 -$5.75 (-1.62%) (Pre-market)"
        result = prepare_text_for_tts(text)
        assert "down" in result
        assert "five dollars" in result
        assert "pre-market" in result
        assert "(" not in result

    def test_financial_acronyms_in_pipeline(self):
        """Pipeline handles financial acronyms."""
        text = "The P/E ratio is high. EPS grew YoY. EBITDA improved."
        result = prepare_text_for_tts(text)
        assert "P to E" in result
        assert "E P S" in result
        assert "year over year" in result
        assert "ee-bit-dah" in result

    def test_versus_in_pipeline(self):
        """Pipeline converts vs. to versus."""
        text = "Tesla vs. Edison: a battle for the ages."
        result = prepare_text_for_tts(text)
        assert "versus" in result
        assert "vs" not in result

    def test_multiplier_in_pipeline(self):
        """Pipeline converts multiplier notation."""
        text = "That's a 10x improvement over last year."
        result = prepare_text_for_tts(text)
        assert "ten times" in result

    def test_abbreviations_in_pipeline(self):
        """Pipeline expands common abbreviations."""
        text = "Tesla Inc. is investing, e.g. in battery tech, etc."
        result = prepare_text_for_tts(text)
        assert "Incorporated" in result
        assert "for example" in result
        assert "et cetera" in result

    def test_price_range_in_pipeline(self):
        """Pipeline converts price ranges."""
        text = "Analysts expect $350-$400 by year end."
        result = prepare_text_for_tts(text)
        assert "three hundred fifty to four hundred dollars" in result
        assert "$" not in result

    def test_hashtag_number_in_pipeline(self):
        """Pipeline converts hashtag numbers."""
        text = "Model Y is the #1 selling EV."
        result = prepare_text_for_tts(text)
        assert "number one" in result

    def test_approximate_in_pipeline(self):
        """Pipeline converts tilde approximation."""
        text = "~500 Superchargers in the region."
        result = prepare_text_for_tts(text)
        assert "approximately" in result


# ===================== New Function Unit Tests =====================

class TestStripFinancialParentheses:
    def test_signed_percentage(self):
        assert strip_financial_parentheses("(+0.27%)") == "+0.27%"

    def test_negative_percentage(self):
        assert strip_financial_parentheses("(-1.62%)") == "-1.62%"

    def test_signed_currency(self):
        assert strip_financial_parentheses("(-$1.11)") == "-$1.11"

    def test_after_hours(self):
        result = strip_financial_parentheses("(After-hours)")
        assert result == "after hours"

    def test_pre_market(self):
        result = strip_financial_parentheses("(Pre-market)")
        assert result == "pre-market"

    def test_unchanged(self):
        result = strip_financial_parentheses("(unchanged)")
        assert result == "unchanged"

    def test_bare_percentage(self):
        assert strip_financial_parentheses("(0.27%)") == "0.27%"

    def test_preserves_normal_parens(self):
        text = "Tesla (the company) is growing"
        assert strip_financial_parentheses(text) == text


class TestReplaceSignedCurrency:
    def test_positive_dollars(self):
        result = replace_signed_currency("+$1.11")
        assert result == "up $1.11"

    def test_negative_dollars(self):
        result = replace_signed_currency("-$2.50")
        assert result == "down $2.50"

    def test_positive_large(self):
        result = replace_signed_currency("+$3 billion")
        assert result == "up $3 billion"

    def test_no_sign(self):
        result = replace_signed_currency("$417.44")
        assert result == "$417.44"  # unchanged, no sign


class TestReplaceSignedNumbers:
    def test_positive_decimal(self):
        result = replace_signed_numbers("+1.11")
        assert "up" in result
        assert "one point one one" in result

    def test_negative_decimal(self):
        result = replace_signed_numbers("-2.50")
        assert "down" in result

    def test_positive_whole(self):
        result = replace_signed_numbers("+3")
        assert "up three" in result

    def test_no_effect_on_percentage(self):
        # Should not match if followed by %
        result = replace_signed_numbers("+0.27%")
        assert "+" in result or "0.27%" in result  # not converted (% follows)

    def test_no_effect_on_currency(self):
        # Should not match currency symbols
        result = replace_signed_numbers("+$5")
        assert "$" in result  # not converted ($ follows +)


class TestReplaceMultiplierNotation:
    def test_2x(self):
        assert replace_multiplier_notation("2x growth") == "two times growth"

    def test_10x(self):
        assert replace_multiplier_notation("10x improvement") == "ten times improvement"

    def test_100x(self):
        assert "one hundred times" in replace_multiplier_notation("100x return")

    def test_no_false_positive(self):
        # "x" in normal words should not be affected
        result = replace_multiplier_notation("next year")
        assert result == "next year"


class TestReplaceVersus:
    def test_vs_period(self):
        result = replace_versus("Tesla vs. Edison")
        assert "versus" in result

    def test_vs_no_period(self):
        result = replace_versus("Tesla vs Edison")
        assert "versus" in result

    def test_case_insensitive(self):
        result = replace_versus("BEV Vs ICE")
        assert "versus" in result


class TestReplaceApproximate:
    def test_tilde_number(self):
        result = replace_approximate("~500 units")
        assert "approximately 500 units" == result

    def test_no_tilde(self):
        result = replace_approximate("about 500 units")
        assert result == "about 500 units"


class TestReplaceCommonAbbreviations:
    def test_eg(self):
        result = replace_common_abbreviations("e.g. battery")
        assert "for example" in result

    def test_ie(self):
        result = replace_common_abbreviations("i.e. Tesla")
        assert "that is" in result

    def test_etc(self):
        result = replace_common_abbreviations("cars, trucks, etc.")
        assert "et cetera" in result

    def test_inc(self):
        result = replace_common_abbreviations("Tesla Inc.")
        assert "Incorporated" in result

    def test_with_slash(self):
        result = replace_common_abbreviations("w/ battery")
        assert "with battery" == result


class TestReplacePriceRanges:
    def test_whole_dollar_range(self):
        result = replace_price_ranges("$350-$400")
        assert "three hundred fifty to four hundred dollars" in result

    def test_em_dash_range(self):
        result = replace_price_ranges("$25\u2013$30")
        assert "twenty-five to thirty dollars" in result

    def test_decimal_range(self):
        result = replace_price_ranges("$10.50-$12.75")
        assert "ten dollars" in result
        assert "twelve dollars" in result
        assert "to" in result


class TestReplaceHashtagNumbers:
    def test_number_one(self):
        assert replace_hashtag_numbers("#1 EV") == "number one EV"

    def test_number_ten(self):
        assert replace_hashtag_numbers("#10 spot") == "number ten spot"


class TestReplaceStandaloneAmpersand:
    def test_standalone(self):
        assert replace_standalone_ampersand("science & tech") == "science and tech"

    def test_compound_preserved(self):
        # No spaces around & means it's not standalone
        assert replace_standalone_ampersand("R&D") == "R&D"


# ===========================================================================
# TTS readiness integration tests — verify nothing harmful reaches TTS
# ===========================================================================

class TestTTSReadinessIntegration:
    """End-to-end tests for prepare_text_for_tts ensuring no raw artifacts
    survive to reach ElevenLabs.  These are the problems that caused bad
    podcast audio historically."""

    def test_urls_fully_stripped(self):
        text = (
            "Tesla announced a new battery. "
            "Source: https://www.teslarati.com/tesla-new-battery-tech/ "
            "This is exciting."
        )
        result = prepare_text_for_tts(text)
        assert "https://" not in result
        assert "teslarati.com" not in result
        assert "Source:" not in result.lower() or "source" in result.lower()

    def test_emojis_fully_stripped(self):
        text = "🚀⚡ Tesla stock is up 📊 today! 🎯"
        result = prepare_text_for_tts(text)
        assert "🚀" not in result
        assert "⚡" not in result
        assert "📊" not in result
        assert "🎯" not in result
        assert "stock" in result.lower()

    def test_markdown_stripped(self):
        text = "### Top 10 News\n**Tesla** is *great*.\n━━━━━━━━━━"
        result = prepare_text_for_tts(text)
        assert "###" not in result
        assert "**" not in result
        assert "━" not in result

    def test_tsla_price_fully_spoken(self):
        """The single most reported issue: raw '$411.82' reaching TTS."""
        text = "TSLA is trading at $411.82"
        result = prepare_text_for_tts(text)
        assert "$" not in result
        assert "411" not in result
        assert "dollars" in result
        assert "T S L A" in result or "T.S.L.A" in result

    def test_price_change_notation(self):
        """Raw '▲ $0.57 (0.1%)' should not reach TTS."""
        text = "TSLA $411.82 ▲ $0.57 (0.1%)"
        result = prepare_text_for_tts(text)
        assert "▲" not in result
        assert "$" not in result
        assert "percent" in result

    def test_social_handles_expanded(self):
        text = "Follow us @teslashortstime"
        result = prepare_text_for_tts(text)
        assert "@teslashortstime" not in result
        assert "tesla shorts time" in result.lower()

    def test_dateline_timestamps_converted(self):
        """Raw '22 February, 2026, 11:30 PM PST' should be natural speech."""
        text = "Tesla announced on February 22, 2026 at 11:30 PM PST."
        result = prepare_text_for_tts(text)
        assert "2026" not in result  # year should be words
        assert "PST" not in result   # timezone should be expanded
        assert "twenty" in result    # year as words

    def test_unicode_arrows_stripped(self):
        text = "Stock is ▲ up and ▼ down"
        result = prepare_text_for_tts(text)
        assert "▲" not in result
        assert "▼" not in result

    def test_box_drawing_stripped(self):
        text = "━━━━━━━━━━━━━━━━━━━━\nNews section"
        result = prepare_text_for_tts(text)
        assert "━" not in result
        assert "News section" in result


class TestRunShowPronunciationPipeline:
    """Verify that run_show.py's _apply_pronunciation actually calls
    prepare_text_for_tts and produces clean output for all shows."""

    def _apply(self, text: str, show_slug: str) -> str:
        """Import and call the actual _apply_pronunciation from run_show."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "run_show", PROJECT_ROOT / "run_show.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod._apply_pronunciation(text, show_slug)

    def test_tesla_pronunciation_strips_urls(self):
        result = self._apply("Check https://example.com for details.", "tesla")
        assert "https://" not in result

    def test_tesla_pronunciation_converts_currency(self):
        result = self._apply("TSLA is at $411.82 today.", "tesla")
        assert "$" not in result
        assert "dollars" in result

    def test_tesla_preserves_ice_as_word(self):
        """Tesla hook skips ICE acronym — 'ice' should stay as 'ice'."""
        result = self._apply("The ice cream truck drove by.", "tesla")
        assert "ice" in result.lower()
        assert "I C E" not in result

    def test_ff_pronunciation_works_without_hook(self):
        """FF has no hook — should still get full pronunciation pipeline."""
        result = self._apply("NASA found $5.2 billion in savings.", "fascinating_frontiers")
        assert "dollars" in result
        assert "$" not in result

    def test_ei_pronunciation_works_without_hook(self):
        result = self._apply("The EPA issued https://epa.gov/notice.", "env_intel")
        assert "https://" not in result

    def test_nonexistent_show_still_gets_pronunciation(self):
        """Even a show with no hook should get full prepare_text_for_tts."""
        result = self._apply("Cost is $100.50 per unit.", "some_future_show")
        assert "$" not in result
        assert "dollars" in result


class TestTeslaIntroFormatting:
    """Verify the Tesla intro/closing lines are pre-formatted for natural TTS.

    June 2026: the dead ``_pick_intro`` hook helper was deleted — the live
    intro path is ``engine.intros.build_intro_line`` (day-varying pool) and
    the closing rotates through ``_CLOSING_VARIANTS`` in the hook. These
    tests pin the same contracts against the live paths.
    """

    def test_intro_has_no_stock_price(self):
        """Intro should NOT contain stock price — it's reserved for the closing only."""
        import datetime
        from engine.intros import build_intro_line
        for day in range(1, 8):  # every weekday variant in the pool
            intro = build_intro_line(
                "tesla", episode_num=506, today_str="June 10, 2026",
                date=datetime.date(2026, 6, day),
            )
            assert "$" not in intro
            assert "▲" not in intro
            assert "dollars" not in intro
            assert "trading" not in intro.lower()

    def test_intro_has_show_name_and_speaker(self):
        import datetime
        from engine.intros import build_intro_line
        intro = build_intro_line(
            "tesla", episode_num=506, today_str="June 10, 2026",
            date=datetime.date(2026, 6, 10),
        )
        assert "Tesla Shorts Time" in intro
        assert intro.startswith("Patrick:")

    def test_no_closing_variant_has_at_handle(self):
        from shows.hooks.tesla import _CLOSING_VARIANTS
        for variant in _CLOSING_VARIANTS:
            rendered = variant.format(price_sentence="")
            assert "@teslashortstime" not in rendered
        # The spoken X mention stays in TTS-friendly form in at least one variant.
        assert any(
            "tesla shorts time" in v.lower() for v in _CLOSING_VARIANTS
        )

    def test_closing_has_stock_price(self):
        import datetime
        from shows.hooks.tesla import _pick_closing, _CLOSING_VARIANTS
        context = {"price": "350.00", "change_str": "▲ $2.50 (0.7%)"}
        for i in range(len(_CLOSING_VARIANTS)):
            closing = _pick_closing(
                context, date=datetime.date(2026, 6, 10 + i),
            )
            assert "three hundred fifty dollars" in closing
            assert "up" in closing

    def test_closing_has_sign_off(self):
        from shows.hooks.tesla import _pick_closing
        context = {"price": "350.00", "change_str": "▼ $1.00 (0.3%)"}
        closing = _pick_closing(context)
        assert "Patrick" in closing
        assert "tomorrow" in closing.lower()
