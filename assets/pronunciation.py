"""
Shared pronunciation module for all podcasts.

Provides comprehensive text-to-speech preparation including:
  - Text cleanup (emojis, markdown, URLs, unicode decorations)
  - Number/currency/date/time expansion to spoken words
  - Acronym and abbreviation handling
  - Unit abbreviation expansion
  - Proper name pronunciation guides
  - Roman numeral conversion

Usage:
    from assets.pronunciation import prepare_text_for_tts

    # Simple usage (applies all fixes):
    tts_ready = prepare_text_for_tts(text)

    # Per-show overrides:
    tts_ready = prepare_text_for_tts(text, extra_acronyms={"DLT": "D L T"})
"""

import re
from typing import Dict, Optional

# Import shared number_to_words from engine
from engine.utils import number_to_words


# ========================== TEXT CLEANUP ==========================

def strip_emojis(text: str) -> str:
    """Remove emoji characters that TTS engines may try to describe or garble."""
    # Unicode emoji ranges (comprehensive)
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"  # enclosed chars
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U0001FA00-\U0001FA6F"  # chess symbols
        "\U0001FA70-\U0001FAFF"  # symbols extended-A
        "\U00002600-\U000026FF"  # misc symbols
        "\U0000FE00-\U0000FE0F"  # variation selectors
        "\U0000200D"             # zero width joiner
        "\U000020E3"             # combining enclosing keycap
        "\U0000FE0F"             # variation selector-16
        "\U000E0020-\U000E007F"  # tags
        "]+",
        flags=re.UNICODE,
    )
    text = emoji_pattern.sub("", text)
    # Clean up keycap sequences like 1️⃣ (digit + VS16 + combining keycap)
    text = re.sub(r"(\d)\uFE0F?\u20E3", r"\1", text)
    return text


def strip_markdown(text: str) -> str:
    """Remove markdown formatting that TTS would read literally."""
    # Remove bold markers: **text** -> text
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    # Remove italic markers: *text* -> text (but not bullet points)
    text = re.sub(r"(?<!\n)\*(?!\s)(.+?)(?<!\s)\*", r"\1", text)
    # Remove heading markers: ### Heading -> Heading
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove horizontal rules (unicode box-drawing and dashes)
    text = re.sub(r"[━─]{3,}", "", text)
    text = re.sub(r"^-{3,}$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\*{3,}$", "", text, flags=re.MULTILINE)
    return text


def strip_urls(text: str) -> str:
    """Remove or replace URLs that TTS would spell out character-by-character."""
    # Remove "Source: URL" lines entirely
    text = re.sub(r"(?i)source/?(?:post)?:\s*https?://\S+", "", text)
    # Remove standalone URLs on their own line
    text = re.sub(r"^\s*https?://\S+\s*$", "", text, flags=re.MULTILINE)
    # Replace inline URLs with empty string (the surrounding context should suffice)
    text = re.sub(r"https?://\S+", "", text)
    # Replace bare domain names (no protocol) with spoken form so TTS
    # doesn't mangle them via acronym expansion (e.g. "chat.openai.com"
    # would otherwise become "chat.Open A I.com").
    text = re.sub(
        r"\b(\w+(?:\.\w+)*\.(?:com|org|net|io|ai|co|dev))\b",
        lambda m: m.group(0).replace(".", " dot "),
        text,
    )
    return text


def strip_unicode_decorations(text: str) -> str:
    """Remove decorative unicode characters that confuse TTS."""
    # Zero-width characters
    text = re.sub(r"[\u200B-\u200F\u2028-\u202F\u2060\uFEFF]", "", text)
    # Box-drawing characters
    text = re.sub(r"[\u2500-\u257F]+", "", text)
    return text


def clean_social_handles(text: str) -> str:
    """Convert @handles to spoken form."""
    # "@teslashortstime" -> "at tesla shorts time"
    def _expand_handle(m: re.Match) -> str:
        handle = m.group(1)
        # Insert spaces before uppercase letters in camelCase handles
        spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", handle)
        # Split known compound words
        for compound, expanded in _HANDLE_EXPANSIONS.items():
            spaced = re.sub(re.escape(compound), expanded, spaced, flags=re.IGNORECASE)
        return f"at {spaced}"

    text = re.sub(r"@(\w+)", _expand_handle, text)
    return text

_HANDLE_EXPANSIONS: Dict[str, str] = {
    "teslashortstime": "tesla shorts time",
    "omniviewnews": "omni view news",
    # @planetterrian X handle — same pronunciation as the show name
    # (see WORD_PRONUNCIATIONS below). Tail is "uhn" not "un" because
    # "UN" is in COMMON_ACRONYMS and gets re-substituted to "U N" by
    # the case-insensitive acronym pass that runs after handle
    # expansion — "uhn" reads identically as the schwa /ən/ but
    # doesn't trigger the acronym match.
    "planetterrian": "plan it tair ee uhn",
}


def clean_text_for_tts(text: str) -> str:
    """Apply all text cleanup steps in the correct order."""
    text = strip_emojis(text)
    text = strip_markdown(text)
    text = strip_urls(text)
    text = strip_unicode_decorations(text)
    text = clean_social_handles(text)
    # Collapse multiple blank lines / excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"  +", " ", text)
    return text.strip()


# ========================== SHARED PRONUNCIATION DICTIONARIES ==========================

# Common acronyms that should be spelled letter-by-letter.
# Order matters: longer/more specific entries must come first to prevent
# partial matches (e.g. "EVs" before "EV").
COMMON_ACRONYMS: Dict[str, str] = {
    # --- AI and ML ---
    "OpenAI's": "Open A I's",
    "OpenAI": "Open A I",
    "GenAI": "Gen A I",
    "xAI's": "ex A I's",
    "xAI": "ex A I",
    "AIs": "A I's",
    "AI's": "A I's",
    "AI": "A I",
    "ML": "M L",
    "LLM": "L L M",
    "LLMs": "L L M's",
    "GPT": "G P T",
    "AGI": "A G I",
    "NLP": "N L P",
    "RAG": "rag",
    "LoRA": "Laura",
    "RLHF": "R L H F",
    "CUDA": "koo-dah",
    "TPU": "T P U",
    "MCP": "M C P",
    "VLMs": "V L M's",
    "VLM": "V L M",
    "GPQA": "G P Q A",
    "MMLU": "M M L U",
    "NDCG": "N D C G",
    "MRR": "M R R",
    "TF-IDF": "T F I D F",

    # --- Space agencies and missions ---
    "NASA": "nassa",  # phonetic guide — prevents letter-split
    "SpaceX": "Space X",
    "ESA": "E S A",
    "JAXA": "jacksa",  # phonetic guide — word-acronym
    "ISS": "I S S",
    "JWST": "J W S T",
    "HST": "H S T",
    "SLS": "S L S",
    "ULA": "U L A",
    "LRO": "L R O",
    "LEO": "L E O",
    "GEO": "G E O",
    "OSIRIS-REx": "Osiris Rex",
    "DART": "dart",  # phonetic guide — word-acronym
    "PSYCHE": "Sy-key",
    "LOFAR": "low-far",
    "ALMA": "alma",
    "ESCAPADE": "escape-ade",

    # --- Biology and health ---
    "DNA": "D N A",
    "RNA": "R N A",
    "RNAi": "R N A i",
    "CRISPR-Cas9": "crisper Cas nine",
    "CRISPR": "crisper",  # phonetic guide — word-acronym
    "mRNA": "messenger R N A",
    "FDA": "F D A",
    "NIH": "N I H",
    "WHO": "W H O",
    "CDC": "C D C",
    "EMA": "E M A",

    # --- Tesla and EVs ---
    "TSLA": "T S L A",
    "FSD": "F S D",
    "HW3": "H W three",
    "HW4": "H W four",
    "AI5": "A I five",
    "4680": "forty-six eighty",
    "EVs": "E Vs",
    "EV": "E V",
    "BEVs": "B E Vs",
    "BEV": "B E V",
    "PHEVs": "P H E Vs",
    "PHEV": "P H E V",
    "ICE": "I C E",
    "NHTSA": "N H T S A",
    "OTA": "O T A",
    "LFP": "L F P",
    "V2G": "V two G",
    "V2H": "V two H",
    "V2L": "V two L",
    "EPA": "E P A",
    "WLTP": "W L T P",
    "NEDC": "N E D C",
    "MPGe": "M P G e",
    "S3XY": "S three X Y",

    # --- Tech / Business ---
    "CEO": "C E O",
    "CFO": "C F O",
    "CTO": "C T O",
    "COO": "C O O",
    "IPO": "I P O",
    "API": "A P I",
    "APIs": "A P I's",
    "SDK": "S D K",
    "SDKs": "S D K's",
    "IoT": "I o T",
    "LED": "L E D",
    "LEDs": "L E D's",
    "DLT": "D L T",
    "DM": "D M",
    "PR": "P R",
    "R&D": "R and D",
    "Q&A": "Q and A",
    "SEC": "S E C",
    "NYSE": "N Y S E",
    "ETF": "E T F",
    "ETFs": "E T F's",
    "ESG": "E S G",
    "GDP": "G D P",
    "CPI": "C P I",

    # --- Financial / Markets ---
    "P/E": "P to E",
    "EPS": "E P S",
    "EBITDA": "ee-bit-dah",
    "ROI": "R O I",
    "ROE": "R O E",
    "YoY": "year over year",
    "MoM": "month over month",
    "QoQ": "quarter over quarter",
    "ATH": "all-time high",
    "FOMO": "fear of missing out",
    "DCA": "D C A",
    "AUM": "A U M",
    "M&A": "M and A",
    "SPACs": "spacks",
    "SPAC": "spack",
    "GAAP": "gaap",
    "TTM": "T T M",
    "DCF": "D C F",

    # --- Scientific / Environmental ---
    "USSF": "U S S F",
    "PROTAC": "pro-tack",
    "ARPA-H": "arpa H",
    "CAGR": "C A G R",
    "CEPA": "see-pa",
    "CCME": "C C M E",
    "SVE": "S V E",
    "PFAS": "P fas",
    "CSR": "C S R",
    "ESA": "E S A",
    "PD-1": "P D one",
    "PD-L1": "P D L one",

    # --- Government / Regulatory ---
    "FAA": "F A A",
    "FCC": "F C C",
    "DOE": "D O E",
    "DOJ": "D O J",
    "DOT": "D O T",
    "EPA": "E P A",
    "EU": "E U",
    "UK": "U K",
    "US": "U S",
    "USA": "U S A",
    "UN": "U N",
    "NATO": "nay-toe",  # phonetic guide — word-acronym
    "OPEC": "oh-peck",  # phonetic guide — word-acronym

    # --- Vehicle / Manufacturing ---
    "VIN": "V I N",
    "QHD": "Q H D",

    # --- Misc tech ---
    "GPU": "G P U",
    "GPUs": "G P U's",
    "USB": "U S B",
    "HDMI": "H D M I",
    "WiFi": "Wi-Fi",
    "GPS": "G P S",
    "VPN": "V P N",
    "AR": "A R",
    "VR": "V R",
    "XR": "X R",
    "5G": "five G",
    "6G": "six G",
    "4G": "four G",
    "LTE": "L T E",
    "SaaS": "sass",  # lowercase word-form — code must not letter-split
    "PaaS": "pass",  # lowercase word-form
    "IaaS": "eye-as",  # has hyphen — handled correctly
}


# Proper names and terms that TTS commonly mispronounces
WORD_PRONUNCIATIONS: Dict[str, str] = {
    # --- Network / brand names ---
    # "Nerra" / "Nerra Network" respellings moved to
    # shows/pronunciation_map.yaml (audio-only) on 2026-06-24. This layer leaks
    # into the saved _tts.txt → blog/RSS transcript, so the respelling was
    # showing up as written text; the YAML map applies at synthesis time only,
    # keeping the transcript on the clean brand while normalizing every spoken
    # form ("Nerra Network", the "nerranetwork" URL compound, the YouTube
    # handle) to one pronunciation. See that file for the entries.

    # --- Show names ---
    # ``Planetterrian`` respelling removed (May 11 2026). Two prior
    # attempts both failed in production audio:
    #
    #   * ``Planet-terry-an`` (legacy) — hyphens parsed as word breaks;
    #     Grok inserted "Terry" the personal name in the middle.
    #   * ``plan it TAIR ee uhn`` (PR #355) — Grok read the 5 tokens
    #     as 5 separate stressed words. Whisper transcribed the audio
    #     as "Planet Terra EE and" / "Planet Tier TIA or EUN" —
    #     inconsistent across one episode and clearly not a smooth
    #     5-syllable word.
    #
    # Without a listen-tested working respelling, the safer state is
    # no override here. Grok handles the raw "Planetterrian" however
    # it does, but the saved transcript / blog text show the canonical
    # spelling instead of garbled respellings. Next attempt should be
    # made via ``shows/pronunciation_map.yaml`` (TTS-call time) not
    # this dict (script-save time), so a wrong respelling doesn't leak
    # into reader-facing text.

    # --- Tesla product names ---
    # Hyphenated respellings (Cybertruck → "Cyber-truck", Robotaxi →
    # "Robo-taxi", Gigafactory → "Giga-factory", Supercharger, Autopilot,
    # Megapack, Powerwall, gigacasting, …) removed 2026-06-25. They are common
    # English compounds the Grok custom voice says natively, and because this
    # layer leaks into the saved _tts.txt → blog/RSS, the hyphenated forms were
    # shipping verbatim in published transcripts ("Cyber-truck", "Robo-taxi").
    # Per landmine #17 this changes shipped audio → A/B-listened before merge.
    # If a specific compound ever regresses on the voice, re-add it to
    # shows/pronunciation_map.yaml (audio-only) — NOT here — so the respelling
    # never re-enters the transcript.

    # --- Tesla model names ---
    "Model 3": "Model Three",
    "Model Y": "Model Why",

    # --- Organizations / unions ---
    # ``IG Metall`` / ``IF Metall`` letter-prefix respellings MOVED to
    # shows/pronunciation_map.yaml on 2026-06-25 (audio-only) so "I G Metall"
    # stops leaking into the saved transcript; the audio is unchanged.

    # --- Company / brand names ---
    # Foreign / hard-to-say brand, mission and person names that used to live
    # here were MOVED to shows/pronunciation_map.yaml on 2026-06-25. That layer
    # is applied at synthesis time only, so the audio is byte-for-byte identical
    # (Grok still receives the respelling) while the saved _tts.txt / blog / RSS
    # now read the canonical spelling instead of "Mee-stral" / "Kah-see-nee" /
    # "Mee-lay" etc. Moved: Mistral, AstraZeneca, Alnylam, Roscosmos, Hachette,
    # SoFi, NOIRLab, Afeela, DSPy, HarmfulQA, TheoremQA, VideoQA, MedQuAD,
    # Cassini, Oberth, Karpathy, Milei, Zelensky(+yy/yj), Altman, Amodei.
    #
    # ``NVIDIA`` stays (its garble revert lands on the different token "Nvidia";
    # moving it would change the audio). ``Lifespan.io`` stays (strip_urls
    # rewrites the .io domain before this map runs, so it needs the script-save
    # layer). The English-compound brand names that REMAIN below are removed in
    # the companion A/B commit — the Grok voice says them natively.
    "CleanTechnica": "Clean Technica",
    "BrewDog": "Brew Dog",
    "Lifespan.io": "Life-span dot i o",
    "LangChain": "Lang Chain",
    "PyTorch": "Pie Torch",
    "NVIDIA": "En-vidia",
    "DeepSeek": "Deep Seek",
    "MiniMax": "Mini Max",
    "TradingView": "Trading View",
    "JailbreakBench": "Jailbreak Bench",
    "GeoChallenge": "Geo Challenge",

    # --- Scientific names ---
    # ``Cassini`` / ``Oberth`` MOVED to shows/pronunciation_map.yaml on
    # 2026-06-25 (audio-only). The plain-English science words that REMAIN
    # below are removed in the companion A/B commit — the Grok voice says them
    # natively.
    "xenotransplantation": "zeno-transplantation",
    "inflammaging": "inflamma-aging",
    "epigenetic": "epi-genetic",
    "epigenetics": "epi-genetics",

    # ``tissue`` / ``neurodegenerative`` and related respellings used to
    # live here (PR #355). Operator caught (May 11 2026 daily review)
    # that ``assets.pronunciation.prepare_text_for_tts`` runs at the
    # script-save boundary, so the respellings were leaking into the
    # saved ``_tts.txt`` — readers (and the daily review AI) saw
    # "newro-de-JEN-er-uh-tiv" instead of "neurodegenerative". Moved
    # to ``shows/pronunciation_map.yaml`` which is applied at TTS-call
    # time inside ``engine.tts.prepare_text_for_tts`` — saved text is
    # untouched, only the audio reflects the override.

    # --- AI model names ---
    # ``Qwen`` ("Chwen") and ``Llama`` ("Lah-mah") respellings removed
    # 2026-06-25 — both are reverted by the garble-repair layer immediately
    # after this map runs (dead round-trips).

    # --- People ---
    # All person-name respellings (Karpathy, Milei, Zelensky(+yy/yj), Altman,
    # Amodei) MOVED to shows/pronunciation_map.yaml on 2026-06-25 (audio-only)
    # — same audio, clean transcript.

    # Note: Common words like "who", "ice", "us", "led", "dot" are now
    # protected by case-sensitive acronym matching (_CASE_SENSITIVE_ACRONYMS)
    # rather than identity entries here.
}


# Unit abbreviations to expand for natural speech
UNIT_ABBREVIATIONS: Dict[str, str] = {
    "km": "kilometers",
    "mi": "miles",
    "kg": "kilograms",
    "lb": "pounds",
    "lbs": "pounds",
    "ft": "feet",
    "m": "meters",
    "cm": "centimeters",
    "mm": "millimeters",
    "nm": "nanometers",
    "kW": "kilowatts",
    "kWh": "kilowatt hours",
    "MW": "megawatts",
    "MWh": "megawatt hours",
    "GW": "gigawatts",
    "GWh": "gigawatt hours",
    "GHz": "gigahertz",
    "MHz": "megahertz",
    "Hz": "hertz",
    "mph": "miles per hour",
    "kph": "kilometers per hour",
    "mpg": "miles per gallon",
    "psi": "P S I",
    "dB": "decibels",
}

# Timezone abbreviations to expand
TIMEZONE_EXPANSIONS: Dict[str, str] = {
    "PST": "Pacific Standard Time",
    "PDT": "Pacific Daylight Time",
    "EST": "Eastern Standard Time",
    "EDT": "Eastern Daylight Time",
    "CST": "Central Standard Time",
    "CDT": "Central Daylight Time",
    "MST": "Mountain Standard Time",
    "MDT": "Mountain Daylight Time",
    "UTC": "U T C",
    "GMT": "Greenwich Mean Time",
    "BST": "British Summer Time",
    "CET": "Central European Time",
    "CEST": "Central European Summer Time",
    "JST": "Japan Standard Time",
    "AEST": "Australian Eastern Standard Time",
    "IST": "Indian Standard Time",
}

# Month abbreviations for date matching
MONTH_ABBREVIATIONS: Dict[str, str] = {
    "Jan": "January",
    "Feb": "February",
    "Mar": "March",
    "Apr": "April",
    "Jun": "June",
    "Jul": "July",
    "Aug": "August",
    "Sep": "September",
    "Sept": "September",
    "Oct": "October",
    "Nov": "November",
    "Dec": "December",
}

# Roman numerals mapping
ROMAN_NUMERALS: Dict[str, int] = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
    "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
    "XI": 11, "XII": 12, "XIII": 13, "XIV": 14, "XV": 15,
    "XVI": 16, "XVII": 17, "XVIII": 18, "XIX": 19, "XX": 20,
}


# ========================== FINANCIAL / STRUCTURAL CLEANUPS ==========================

def strip_financial_parentheses(text: str) -> str:
    """Remove parentheses around financial values and market status indicators.

    Prevents TTS from reading parentheses literally or inserting awkward pauses.
    Must run early, before value converters, so the inner content can be
    processed by downstream handlers.

    Examples:
        '(+0.27%)'      → '+0.27%'
        '(-$1.11)'      → '-$1.11'
        '(After-hours)'  → 'after hours'
        '(Pre-market)'   → 'pre-market'
        '(unchanged)'    → 'unchanged'
    """
    # Market status indicators in parens
    text = re.sub(r"\(After[- ]?hours?\)", "after hours", text, flags=re.IGNORECASE)
    text = re.sub(r"\(Pre[- ]?market\)", "pre-market", text, flags=re.IGNORECASE)
    text = re.sub(r"\(unchanged\)", "unchanged", text, flags=re.IGNORECASE)

    # Signed values in parens: (+0.27%), (-$1.11), (+$0.50), etc.
    text = re.sub(r"\(([+\-][$€£]?\d+\.?\d*%?)\)", r"\1", text)

    # Bare percentage in parens: (0.27%)
    text = re.sub(r"\((\d+\.?\d*%)\)", r"\1", text)

    return text


def replace_canadian_currency(text: str) -> str:
    """Convert ``C$X,XXX`` Canadian-dollar amounts to spoken form.

    Grok TTS's text_normalization treats ``$X,XXX`` as a USD amount
    and emits "X dollars XXX" — the comma is read as a separator
    instead of a thousands marker. With a leading "C", the "C" is
    left stranded as a one-letter syllable, producing the audible
    bug operator caught on TST Ep471 (May 13 2026):

        Markdown:  ``C$39,490``
        Audio:     "C thirty-nine dollars four hundred ninety"

    This transform pre-rewrites ``C$N,NNN`` and ``C$N,NNN.NN`` to
    ``N,NNN Canadian dollars`` (with the comma intact) so the
    downstream :func:`replace_currency` converter handles the
    whole thing as a normal currency amount.

    Must run BEFORE :func:`replace_currency` so the "C" prefix is
    consumed before standard ``$`` handling.

    Examples:
        'C$39,490'    → '39,490 Canadian dollars'
        'C$1,250.50'  → '1,250.50 Canadian dollars'
        'C$15'        → '15 Canadian dollars'
        'CAD$100'     → '100 Canadian dollars'
    """
    def _canadian(m: re.Match) -> str:
        amount = m.group(1)
        return f"{amount} Canadian dollars"

    # CAD$ / Cad$ / C$ — case-insensitive on the prefix. The trailing
    # amount captures integers, comma-thousands, and optional decimal.
    text = re.sub(
        r"\b(?:CAD\$|C\$)(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)",
        _canadian,
        text,
        flags=re.IGNORECASE,
    )
    return text


def replace_signed_currency(text: str) -> str:
    """Convert signed currency amounts to natural spoken form.

    Must run BEFORE replace_currency() so the sign word is placed first,
    then the bare $-amount is handled by the standard currency converter.

    Examples:
        '+$1.11'      → 'up one dollar and eleven cents'   (after replace_currency)
        '-$2.50'      → 'down two dollars and fifty cents'
        '+$3 billion' → 'up three billion dollars'
    """
    def _signed(m: re.Match) -> str:
        sign = m.group(1)
        rest = m.group(2)
        direction = "up" if sign == "+" else "down"
        return f"{direction} {rest}"

    # Negative lookbehind (?<!\d) prevents matching range separators:
    # "$350-$400" should NOT convert the "-$400" part.
    text = re.sub(
        r"(?<!\d)([+\-])([$€£]\d+\.?\d*(?:\s*(?:trillion|billion|million|thousand))?)",
        _signed,
        text,
        flags=re.IGNORECASE,
    )
    return text


def replace_signed_numbers(text: str) -> str:
    """Convert bare signed decimal numbers to spoken form.

    Catches +/- numbers that were NOT already handled by currency or
    percentage converters.  Runs AFTER both of those.

    Examples:
        '+1.11'  → 'up one point one one'
        '-2.50'  → 'down two point five'
        '+0.5'   → 'up zero point five'
    """
    def _signed_num(m: re.Match) -> str:
        sign = m.group(1)
        num_str = m.group(2)
        direction = "up" if sign == "+" else "down"
        try:
            words = number_to_words(float(num_str))
            return f"{direction} {words}"
        except ValueError:
            return m.group(0)

    # Match +/- followed by a decimal number, not followed by % and not
    # part of a longer word.  The \d in the negative lookahead prevents
    # backtracking from consuming only part of the number (e.g. matching
    # "+0.2" instead of "+0.27" in "+0.27%").
    # (?<!\d) prevents matching the hyphen in ranges like "10-20" or "0.1-0.5".
    text = re.sub(r"(?<![a-zA-Z\d])([+\-])(\d+\.\d+)(?!\d|\s*%|[a-zA-Z])", _signed_num, text)
    # Also handle whole signed numbers like "+3" or "-5" when standalone
    text = re.sub(r"(?<![a-zA-Z$€£\d])([+\-])(\d+)(?!\d|\.\d|\s*%|[a-zA-Z])", _signed_num, text)
    return text


def replace_multiplier_notation(text: str) -> str:
    """Convert multiplier 'x' notation to spoken form.

    Examples:
        '2x growth'     → 'two times growth'
        '10x improvement' → 'ten times improvement'
        '100x'          → 'one hundred times'
    """
    def _mult(m: re.Match) -> str:
        num_str = m.group(1)
        try:
            return f"{number_to_words(int(num_str))} times"
        except ValueError:
            return m.group(0)

    text = re.sub(r"\b(\d+)x\b", _mult, text)
    return text


def replace_versus(text: str) -> str:
    """Convert 'vs.' and 'vs' abbreviation to 'versus'."""
    text = re.sub(r"\bvs\.(?:\s)", lambda m: "versus " , text, flags=re.IGNORECASE)
    text = re.sub(r"\bvs\.\b", "versus", text, flags=re.IGNORECASE)
    text = re.sub(r"\bvs\b", "versus", text, flags=re.IGNORECASE)
    return text


def replace_approximate(text: str) -> str:
    """Convert '~' (tilde) prefix to 'approximately' for natural speech.

    Example: '~500 km' → 'approximately 500 km'
    """
    text = re.sub(r"~(\d)", r"approximately \1", text)
    return text


def replace_common_abbreviations(text: str) -> str:
    """Expand common abbreviations that TTS would read literally or mangle.

    Examples:
        'e.g.' → 'for example'
        'i.e.' → 'that is'
        'etc.' → 'et cetera'
        'w/'   → 'with'
        'Inc.' → 'Incorporated'
    """
    # Order matters: longer patterns first to avoid partial matches
    abbrevs = [
        (r"\be\.g\.", "for example"),
        (r"\bi\.e\.", "that is"),
        (r"\betc\.", "et cetera"),
        (r"\bw/(?!\w)", "with"),
        (r"\bb/w\b", "between"),
        (r"\bInc\.", "Incorporated"),
        (r"\bCorp\.", "Corporation"),
        (r"\bLtd\.", "Limited"),
    ]
    for pattern, expansion in abbrevs:
        text = re.sub(pattern, expansion, text, flags=re.IGNORECASE)
    return text


def replace_price_ranges(text: str) -> str:
    """Convert price ranges to natural spoken form.

    Examples:
        '$350-$400'  → 'three hundred fifty to four hundred dollars'
        '$25–$30'    → 'twenty-five to thirty dollars'
    """
    # Decimal ranges: $350.50-$400.75
    def _range_decimal(m: re.Match) -> str:
        symbol = m.group(1)
        low_w, low_d = m.group(2), m.group(3)
        high_w, high_d = m.group(4), m.group(5)
        currency = {"$": "dollars", "€": "euros", "£": "pounds"}.get(symbol, "dollars")
        try:
            low_words = number_to_words(int(low_w))
            high_words = number_to_words(int(high_w))
            low_cents = number_to_words(int(low_d))
            high_cents = number_to_words(int(high_d))
            sub = {"$": "cents", "€": "cents", "£": "pence"}.get(symbol, "cents")
            return (f"{low_words} {currency} and {low_cents} {sub} "
                    f"to {high_words} {currency} and {high_cents} {sub}")
        except ValueError:
            return m.group(0)

    text = re.sub(
        r"([$€£])(\d+)\.(\d{1,2})\s*[-–—]\s*\1(\d+)\.(\d{1,2})",
        _range_decimal,
        text,
    )

    # Whole-number ranges: $350-$400
    def _range_whole(m: re.Match) -> str:
        symbol = m.group(1)
        low, high = m.group(2), m.group(3)
        currency = {"$": "dollars", "€": "euros", "£": "pounds"}.get(symbol, "dollars")
        try:
            return f"{number_to_words(int(low))} to {number_to_words(int(high))} {currency}"
        except ValueError:
            return m.group(0)

    text = re.sub(r"([$€£])(\d+)\s*[-–—]\s*\1(\d+)", _range_whole, text)
    return text


def replace_slashes(text: str) -> str:
    """Convert slashes between words to spaces for natural speech.

    Handles single-letter pairs (A/B → A B), uppercase trading pairs
    (XRP/USD → XRP USD), and regulation numbers (153/04 → 153 oh-four).
    Skips URLs (already stripped), w/ (handled elsewhere), and entries
    already in the acronym dictionary (P/E).

    Examples:
        'A/B testing' → 'A B testing'
        'XRP/USD'     → 'XRP USD'
    """
    # Single-letter pairs: A/B → A B
    text = re.sub(r"\b([A-Za-z])/([A-Za-z])\b", r"\1 \2", text)
    # Uppercase word pairs (trading pairs, comparisons): XRP/USD → XRP USD
    text = re.sub(r"\b([A-Z]{2,})/([A-Z]{2,})\b", r"\1 \2", text)
    return text


def replace_hashtag_numbers(text: str) -> str:
    """Convert '#1', '#2' etc. to 'number one', 'number two'.

    Only converts when # is followed by a small number (rankings).
    """
    def _hash(m: re.Match) -> str:
        num = m.group(1)
        try:
            return f"number {number_to_words(int(num))}"
        except ValueError:
            return m.group(0)

    text = re.sub(r"#(\d{1,3})\b", _hash, text)
    return text


def replace_standalone_ampersand(text: str) -> str:
    """Convert standalone '&' to 'and' for natural speech.

    Skips compound forms like 'R&D' or 'Q&A' (no spaces around &)
    which are handled by the acronym dictionary.
    """
    text = re.sub(r" & ", " and ", text)
    return text


# ========================== NUMBER / VALUE CONVERTERS ==========================

def _number_to_ordinal(n: int) -> str:
    """Convert integer to ordinal word form (1 -> 'first', 22 -> 'twenty-second')."""
    special = {
        1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
        6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth",
        11: "eleventh", 12: "twelfth", 13: "thirteenth", 14: "fourteenth",
        15: "fifteenth", 16: "sixteenth", 17: "seventeenth", 18: "eighteenth",
        19: "nineteenth", 20: "twentieth", 30: "thirtieth",
    }
    if n in special:
        return special[n]
    if n < 100:
        tens_digit = (n // 10) * 10
        ones_digit = n % 10
        if ones_digit == 0:
            return number_to_words(n) + "th"
        tens_word = number_to_words(tens_digit)
        ones_ordinal = special.get(ones_digit, number_to_words(ones_digit) + "th")
        return f"{tens_word}-{ones_ordinal}"
    # For larger numbers, just append "th" to the cardinal
    words = number_to_words(n)
    if words.endswith("y"):
        return words[:-1] + "ieth"
    return words + "th"


def _year_to_words(year: int) -> str:
    """Convert a year number to natural spoken form.

    2026 -> 'twenty twenty-six'
    2000 -> 'two thousand'
    2001 -> 'two thousand one'
    1999 -> 'nineteen ninety-nine'
    1564 -> 'fifteen sixty-four'
    """
    if year == 2000:
        return "two thousand"
    if 2001 <= year <= 2009:
        return "two thousand " + number_to_words(year - 2000)
    if 2010 <= year <= 2099:
        first = year // 100  # 20
        last = year % 100     # 26
        return f"{number_to_words(first)} {number_to_words(last)}"
    if 1000 <= year <= 1999:
        first = year // 100
        last = year % 100
        if last == 0:
            return f"{number_to_words(first)} hundred"
        return f"{number_to_words(first)} {number_to_words(last)}"
    return number_to_words(year)


def replace_currency(text: str) -> str:
    """Convert currency values to spoken form."""
    # Large currency first: "$3 Trillion", "$2.5 Billion", etc.
    def _large_currency(m: re.Match) -> str:
        symbol = m.group(1)
        num_str = m.group(2)
        unit = m.group(3).lower()
        currency = {"$": "dollars", "\u20ac": "euros", "\u00a3": "pounds"}.get(symbol, "dollars")
        try:
            words = number_to_words(float(num_str))
            return f"{words} {unit} {currency}"
        except ValueError:
            return m.group(0)

    text = re.sub(
        r"([$\u20ac\u00a3])(\d+\.?\d*)\s*(trillion|billion|million)\b",
        _large_currency,
        text,
        flags=re.IGNORECASE,
    )

    # Regular currency with cents: "$417.44" -> "four hundred seventeen dollars and forty-four cents"
    def _currency_with_cents(m: re.Match) -> str:
        symbol = m.group(1)
        whole = m.group(2)
        frac = m.group(3)
        currency = {"$": "dollars", "\u20ac": "euros", "\u00a3": "pounds"}.get(symbol, "dollars")
        sub_unit = {"$": "cents", "\u20ac": "cents", "\u00a3": "pence"}.get(symbol, "cents")
        try:
            whole_n = int(whole)
            frac_n = int(frac)
            if whole_n == 0:
                return f"{number_to_words(frac_n)} {sub_unit}"
            if frac_n == 0:
                return f"{number_to_words(whole_n)} {currency}"
            return f"{number_to_words(whole_n)} {currency} and {number_to_words(frac_n)} {sub_unit}"
        except ValueError:
            return m.group(0)

    text = re.sub(r"([$\u20ac\u00a3])(\d+)\.(\d{1,2})\b", _currency_with_cents, text)

    # Whole currency: "$500" -> "five hundred dollars"
    def _currency_whole(m: re.Match) -> str:
        symbol = m.group(1)
        num_str = m.group(2)
        currency = {"$": "dollars", "\u20ac": "euros", "\u00a3": "pounds"}.get(symbol, "dollars")
        try:
            return f"{number_to_words(int(num_str))} {currency}"
        except ValueError:
            return m.group(0)

    text = re.sub(r"([$\u20ac\u00a3])(\d+)\b", _currency_whole, text)
    return text


def replace_percentages(text: str) -> str:
    """Convert percentages to spoken form: '+3.59%' -> 'plus three point five nine percent'.

    A digit lookbehind prevents misinterpreting the hyphen in ranges like
    ``0.1-0.5%`` as a negative sign.
    """
    # First, handle percentage ranges: "0.1-0.5%" → "zero point one to zero point five percent"
    def _pct_range(m: re.Match) -> str:
        low_str, high_str = m.group(1), m.group(2)
        try:
            low = number_to_words(float(low_str))
            high = number_to_words(float(high_str))
            return f"{low} to {high} percent"
        except ValueError:
            return m.group(0)

    text = re.sub(r"(\d+\.?\d*)\s*[-–—]\s*(\d+\.?\d*)\s*%", _pct_range, text)

    # Then handle single percentages (with optional sign)
    def _pct(m: re.Match) -> str:
        sign = m.group(1) or ""
        num_str = m.group(2)
        try:
            words = number_to_words(abs(float(num_str)))
            prefix = {"+" : "plus ", "-": "minus "}.get(sign, "")
            return f"{prefix}{words} percent"
        except ValueError:
            return m.group(0)

    # Negative lookbehind (?<!\d) prevents matching the hyphen in
    # number ranges like "0.1-0.5%" (already handled above).
    text = re.sub(r"(?<!\d)([+\-]?)(\d+\.?\d*)\s*%", _pct, text)
    return text


def replace_dates(text: str) -> str:
    """Convert dates to natural spoken form.

    Handles: 'February 15, 2026', '15 February, 2026', 'Feb 15, 2026'
    """
    # Expand abbreviated months first
    for abbr, full in MONTH_ABBREVIATIONS.items():
        text = re.sub(rf"\b{abbr}\b", full, text)

    def _date(m: re.Match) -> str:
        month = m.group(1)
        day = m.group(2)
        year = m.group(3)
        try:
            day_n = int(day)
            year_n = int(year)
            return f"{month} {_number_to_ordinal(day_n)}, {_year_to_words(year_n)}"
        except ValueError:
            return m.group(0)

    # "Month DD, YYYY"
    text = re.sub(
        r"(\b(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\b)\s+(\d{1,2}),\s*(\d{4})",
        _date,
        text,
        flags=re.IGNORECASE,
    )

    # "DD Month, YYYY" -> rearrange to "Month DDth, YYYY"
    def _date_swapped(m: re.Match) -> str:
        day = m.group(1)
        month = m.group(2)
        year = m.group(3)
        try:
            day_n = int(day)
            year_n = int(year)
            return f"{month} {_number_to_ordinal(day_n)}, {_year_to_words(year_n)}"
        except ValueError:
            return m.group(0)

    text = re.sub(
        r"(\d{1,2})\s+(\b(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\b),?\s*(\d{4})",
        _date_swapped,
        text,
        flags=re.IGNORECASE,
    )

    return text


def replace_times(text: str) -> str:
    """Convert clock times to spoken form: '03:08 AM' -> 'three oh eight A M'.

    Handles HH:MM and HH:MM:SS (seconds are dropped — no podcast host reads
    them aloud), plus compact 24-hour "military"/UTC times like
    ``0850:45 UTC`` (SpaceX launch reporting). Without the seconds-tolerant
    pattern, ``1:50:45 a.m.`` matched only ``1:50`` and shipped the garble
    "one fifty A M:45 a.m." (SpaceX Ep8, 2026-06-19).
    """

    def _mil_time(m: re.Match) -> str:
        """Compact 24-hour UTC/GMT times: '0850:45 UTC' -> 'oh eight fifty UTC'.

        Runs BEFORE the HH:MM matcher (which would otherwise match the
        trailing '50:45' inside '0850:45' and bail out as hour>12). The
        timezone token is left literal for replace_timezones() to expand.
        Seconds are dropped; 24-hour spoken form is correct for UTC (no AM/PM).
        """
        hh, mm = m.group(1), m.group(2)
        zone = m.group(3)
        try:
            hour, minute = int(hh), int(mm)
        except ValueError:
            return m.group(0)
        if not (1 <= hour <= 23) or minute > 59:
            # 00xx (midnight UTC) is rare in launch reporting and reads
            # awkwardly in 24-hour spoken form — leave it untouched.
            return m.group(0)
        hour_word = (
            "oh " + number_to_words(hour) if hour <= 9 else number_to_words(hour)
        )
        if minute == 0:
            min_word = "hundred"
        elif minute <= 9:
            min_word = "oh " + number_to_words(minute)
        else:
            min_word = number_to_words(minute)
        return f"{hour_word} {min_word} {zone}"

    text = re.sub(
        r"\b(\d{2})(\d{2})(?::\d{2})?\s+(UTC|GMT)\b",
        _mil_time,
        text,
    )

    def _time(m: re.Match) -> str:
        hour_str = m.group(1)
        minute_str = m.group(2)
        am_pm_raw = (m.group(3) or "").strip()
        try:
            hour = int(hour_str)
            minute = int(minute_str)
            # Normalize am/pm
            am_pm = am_pm_raw.upper().replace(".", "").strip()
            if am_pm not in ("AM", "PM"):
                # 24-hour format
                if hour >= 13:
                    hour -= 12
                    am_pm = "P M"
                elif hour == 12:
                    am_pm = "P M"
                elif hour == 0:
                    hour = 12
                    am_pm = "A M"
                else:
                    am_pm = "A M"
            else:
                am_pm = am_pm[0] + " " + am_pm[1]  # "AM" -> "A M"

            if hour < 1 or hour > 12:
                return m.group(0)

            hour_word = number_to_words(hour)
            if minute == 0:
                return f"{hour_word} {am_pm}"
            elif 1 <= minute <= 9:
                return f"{hour_word} oh {number_to_words(minute)} {am_pm}"
            else:
                return f"{hour_word} {number_to_words(minute)} {am_pm}"
        except (ValueError, AttributeError):
            return m.group(0)

    text = re.sub(
        r"(\d{1,2}):(\d{2})(?::\d{2})?(?:\s*(AM|PM|am|pm|A\.M\.|P\.M\.|a\.m\.|p\.m\.))?",
        _time,
        text,
    )
    return text


def replace_timezones(text: str) -> str:
    """Expand timezone abbreviations to full names."""
    for tz, expansion in TIMEZONE_EXPANSIONS.items():
        text = re.sub(rf"\b{re.escape(tz)}\b", expansion, text)
    return text


def replace_episode_numbers(text: str) -> str:
    """Convert 'episode 39' to 'episode thirty-nine'."""
    def _ep(m: re.Match) -> str:
        prefix = m.group(1)
        num = m.group(2)
        try:
            return f"{prefix}{number_to_words(int(num))}"
        except ValueError:
            return m.group(0)

    text = re.sub(r"(episode\s+)(\d+)", _ep, text, flags=re.IGNORECASE)
    return text


def replace_ordinal_numbers(text: str) -> str:
    """Convert '7th' to 'seventh', '10th' to 'tenth', etc."""
    def _ordinal(m: re.Match) -> str:
        num_str = m.group(1)
        try:
            return _number_to_ordinal(int(num_str))
        except ValueError:
            return m.group(0)

    text = re.sub(r"\b(\d+)(?:st|nd|rd|th)\b", _ordinal, text)
    return text


def replace_roman_numerals(text: str) -> str:
    """Convert Roman numerals in context: 'Phase III' -> 'Phase three'."""
    # Only convert when preceded by a context word to avoid false positives
    context_words = r"(?:Phase|Part|Chapter|Section|Act|Type|Class|Mark|Version|Vol|Volume|Title|Book|Level|Stage|Grade|Tier|Step|Round|Series|Season|Episode|Generation|Gen)"

    def _roman(m: re.Match) -> str:
        prefix = m.group(1)
        numeral = m.group(2).upper()
        val = ROMAN_NUMERALS.get(numeral)
        if val is not None:
            return f"{prefix}{number_to_words(val)}"
        return m.group(0)

    text = re.sub(
        rf"({context_words}\s+)(I{{1,4}}V?|VI{{0,4}}|IX|X{{1,3}}I{{0,4}}V?)\b",
        _roman,
        text,
        flags=re.IGNORECASE,
    )
    return text


def replace_quarter_notation(text: str) -> str:
    """Convert 'Q2 2026' to 'Q two twenty twenty-six'."""
    def _quarter(m: re.Match) -> str:
        q_num = m.group(1)
        year = m.group(2)
        try:
            q_word = number_to_words(int(q_num))
            y_word = _year_to_words(int(year))
            return f"Q {q_word} {y_word}"
        except ValueError:
            return m.group(0)

    text = re.sub(r"\bQ([1-4])\s+(\d{4})\b", _quarter, text)
    # Standalone Q-notation without year
    text = re.sub(r"\bQ([1-4])\b", lambda m: f"Q {number_to_words(int(m.group(1)))}", text)
    return text


def replace_units(text: str) -> str:
    """Expand unit abbreviations: '500 km' -> '500 kilometers'.

    Also handles cases where numbers have already been converted to words,
    e.g. 'five hundred thousand km' -> 'five hundred thousand kilometers'.
    """
    for abbr, expansion in UNIT_ABBREVIATIONS.items():
        # Match unit after a digit-form number (with optional comma separators)
        text = re.sub(
            rf"(\d[\d,]*\.?\d*)\s*(?<!\w){re.escape(abbr)}(?!\w)",
            rf"\1 {expansion}",
            text,
        )
        # Also match unit after a word-form number (e.g. "five hundred thousand km")
        text = re.sub(
            rf"(\w)\s+{re.escape(abbr)}(?!\w)",
            rf"\1 {expansion}",
            text,
        )
    return text


def replace_large_numbers_with_k(text: str) -> str:
    """Convert '2.5k' to '2,500' or words, and 'k km' style issues."""
    def _k_number(m: re.Match) -> str:
        num_str = m.group(1)
        try:
            val = float(num_str) * 1000
            if val == int(val):
                return number_to_words(int(val))
            return number_to_words(val)
        except ValueError:
            return m.group(0)

    # "2.5k" -> "two thousand five hundred"
    text = re.sub(r"(\d+\.?\d*)k\b", _k_number, text, flags=re.IGNORECASE)
    return text


def replace_scientific_designations(text: str) -> str:
    """Handle scientific object designations like 'C/2024 E1', '3I/ATLAS', 'HR 8799'."""
    # Comet designations: "C/2024 E1" -> "C slash twenty twenty-four E one"
    def _comet(m: re.Match) -> str:
        prefix = m.group(1)
        year = m.group(2)
        suffix = m.group(3)
        try:
            year_words = _year_to_words(int(year))
            # Spell out the suffix letter-by-letter then number
            letter = suffix[0]
            num = suffix[1:].strip() if len(suffix) > 1 else ""
            num_word = number_to_words(int(num)) if num else ""
            return f"{prefix} slash {year_words} {letter} {num_word}".strip()
        except ValueError:
            return m.group(0)

    text = re.sub(r"\b(\d*[A-Z])/(\d{4})\s+([A-Z]\d*)\b", _comet, text)

    # Interstellar objects: "3I/ATLAS" -> "three I ATLAS"
    def _interstellar(m: re.Match) -> str:
        num = m.group(1)
        designation = m.group(2)
        name = m.group(3)
        try:
            return f"{number_to_words(int(num))} {designation} {name}"
        except ValueError:
            return m.group(0)

    text = re.sub(r"\b(\d+)(I)/([A-Z]+)\b", _interstellar, text)

    # Star catalog numbers: "HR 8799" -> "H R eighty-seven ninety-nine"
    text = re.sub(r"\bHR\s+(\d+)\b", lambda m: f"H R {number_to_words(int(m.group(1)))}", text)

    return text


def replace_number_ranges(text: str) -> str:
    """Convert plain number ranges to spoken form.

    Examples:
        '10-20 dollars'  → 'ten to twenty dollars'
        '250–300'        → 'two hundred fifty to three hundred'
        '50-100'         → 'fifty to one hundred'

    Only matches when both sides are plain numbers (no currency symbol,
    which is handled by ``replace_price_ranges``).
    """
    def _num_range(m: re.Match) -> str:
        low_str, high_str = m.group(1), m.group(2)
        try:
            low_val = float(low_str) if "." in low_str else int(low_str)
            high_val = float(high_str) if "." in high_str else int(high_str)
            # Only convert ranges where high > low (not subtraction)
            if high_val > low_val:
                return f"{number_to_words(low_val)} to {number_to_words(high_val)}"
        except ValueError:
            pass
        return m.group(0)

    # Match digit-hyphen-digit ranges that aren't preceded by a currency
    # symbol (those are handled by replace_price_ranges).
    text = re.sub(
        r"(?<![$€£])(\d+\.?\d*)\s*[-–—]\s*(\d+\.?\d*)(?!\s*%)",
        _num_range,
        text,
    )
    return text


def replace_standalone_large_numbers(text: str) -> str:
    """Convert large standalone numbers to words for natural speech.

    Handles comma-separated numbers: '500,000' -> 'five hundred thousand'
    Only converts numbers that aren't part of other patterns (dates, prices, etc.).
    """
    def _large_num(m: re.Match) -> str:
        num_str = m.group(0).replace(",", "")
        try:
            val = int(num_str)
            if val > 999999:
                # Very large numbers: use millions/billions
                if val >= 1_000_000_000:
                    billions = val / 1_000_000_000
                    if billions == int(billions):
                        return f"{number_to_words(int(billions))} billion"
                    return f"{number_to_words(round(billions, 1))} billion"
                if val >= 1_000_000:
                    millions = val / 1_000_000
                    if millions == int(millions):
                        return f"{number_to_words(int(millions))} million"
                    return f"{number_to_words(round(millions, 1))} million"
            return number_to_words(val)
        except ValueError:
            return m.group(0)

    # Match numbers with commas (like 500,000) or large plain numbers
    text = re.sub(r"\b\d{1,3}(?:,\d{3})+\b", _large_num, text)
    return text


# ========================== MAIN PRONUNCIATION FIX FUNCTIONS ==========================

def apply_pronunciation_fixes(
    text: str,
    acronyms: Optional[Dict[str, str]] = None,
    hockey_terms: Optional[Dict[str, str]] = None,
    player_names: Optional[Dict[str, str]] = None,
    oilers_player_names: Optional[Dict[str, str]] = None,
    word_pronunciations: Optional[Dict[str, str]] = None,
    use_zwj: bool = False,
) -> str:
    """
    Apply dictionary-based pronunciation fixes to text.

    This is the original function preserved for backward compatibility.
    New code should prefer ``prepare_text_for_tts()`` which calls this
    internally along with all the other cleanup/expansion steps.
    """
    if acronyms is None:
        acronyms = COMMON_ACRONYMS
    if hockey_terms is None:
        hockey_terms = {}
    if player_names is None:
        player_names = {}
    if oilers_player_names is None:
        oilers_player_names = {}
    if word_pronunciations is None:
        word_pronunciations = WORD_PRONUNCIATIONS

    all_player_names = {**player_names, **oilers_player_names}
    ZWJ = "\u2060" if use_zwj else " "

    # Fix acronyms (whole words only)
    # Acronyms whose uppercase form collides with a common lowercase English
    # word must be matched case-sensitively so "us", "led", "dot", "ice",
    # "who", "dart", "psyche", etc. are not mangled.
    _CASE_SENSITIVE_ACRONYMS = {
        "WHO", "US", "LED", "DOT", "DOE", "COO", "SEC",
        "ICE", "DART", "PSYCHE",
    }
    for acronym, spelled in acronyms.items():
        if acronym in _CASE_SENSITIVE_ACRONYMS:
            pattern = rf"(?<!\w){re.escape(acronym)}(?!\w)"
            flags = 0
        else:
            pattern = rf"(?<!\w){re.escape(acronym)}(?!\w)"
            flags = re.IGNORECASE

        if " " in spelled or "-" in spelled or "." in spelled:
            # Already formatted with separators — use verbatim
            replacement = spelled
        elif spelled == acronym:
            # Identity mapping — TTS handles this word naturally, skip
            continue
        elif not spelled.isupper():
            # Mixed/lowercase = word pronunciation (e.g., "nassa", "sass") — use verbatim
            replacement = spelled
        elif use_zwj:
            replacement = ZWJ.join(list(spelled))
        else:
            replacement = " ".join(list(spelled))
        text = re.sub(pattern, replacement, text, flags=flags)

    # Fix hockey terms (phrases)
    for term, phrase in hockey_terms.items():
        pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
        text = re.sub(pattern, phrase, text, flags=re.IGNORECASE)

    # Fix player names
    for name, pronunciation in all_player_names.items():
        pattern = rf"(?<!\w){re.escape(name)}(?!\w)"
        text = re.sub(pattern, pronunciation, text, flags=re.IGNORECASE)

    # Fix word pronunciations
    for word, pronunciation in word_pronunciations.items():
        pattern = rf"(?<!\w){re.escape(word)}(?!\w)"
        text = re.sub(pattern, pronunciation, text, flags=re.IGNORECASE)

    return text


def prepare_text_for_tts(
    text: str,
    *,
    # Dictionary overrides
    extra_acronyms: Optional[Dict[str, str]] = None,
    skip_acronyms: Optional[set] = None,
    extra_words: Optional[Dict[str, str]] = None,
    # Feature toggles
    do_clean: bool = True,
    do_currency: bool = True,
    do_percentages: bool = True,
    do_dates: bool = True,
    do_times: bool = True,
    do_timezones: bool = True,
    do_episodes: bool = True,
    do_ordinals: bool = True,
    do_roman: bool = True,
    do_quarters: bool = True,
    do_units: bool = True,
    do_large_numbers: bool = True,
    do_k_numbers: bool = True,
    do_scientific: bool = True,
    do_acronyms: bool = True,
) -> str:
    """Prepare raw script text for TTS synthesis.

    This is the recommended single entry point. It applies all cleanup
    and pronunciation fixes in the correct order so that each show script
    only needs one call.

    Processing order:
      1. Text cleanup (emojis, markdown, URLs, unicode, handles)
      2. Structural fixes (parens, abbreviations, ampersands, versus, approx)
      3. Financial notation (signed currency, price ranges, hashtags)
      4. Number/value expansion (k-numbers, currency, percentages, dates, ...)
      5. Leftover signed numbers (bare +/- that survived earlier passes)
      6. Multiplier notation (2x, 10x)
      7. Dictionary-based pronunciation fixes (acronyms, proper names)
      8. Final whitespace cleanup

    Args:
        text: Raw episode script text (may contain markdown, emojis, URLs).
        extra_acronyms: Additional acronyms to add to the defaults.
        skip_acronyms: Acronym keys to remove from the defaults (e.g. {"ICE"}).
        extra_words: Additional word pronunciations to add to the defaults.
        do_*: Toggle individual processing steps on/off.

    Returns:
        Text ready to send to ElevenLabs TTS.
    """
    if not text:
        return text

    # ── 1. Text cleanup (remove artifacts TTS shouldn't see) ──
    if do_clean:
        text = clean_text_for_tts(text)

    # ── 2. Structural fixes (before value conversion) ──
    # Strip parentheses around financial values so handlers can process them
    text = strip_financial_parentheses(text)
    # Expand common abbreviations (e.g., i.e., etc., Inc., w/)
    text = replace_common_abbreviations(text)
    # Standalone & → "and" (compound forms like R&D handled by acronym dict)
    text = replace_standalone_ampersand(text)
    # vs. / vs → "versus"
    text = replace_versus(text)
    # ~ prefix → "approximately"
    text = replace_approximate(text)
    # #1, #2 → "number one", "number two"
    text = replace_hashtag_numbers(text)

    # ── 3. Financial notation (before standard currency handler) ──
    # Canadian dollar prefix FIRST — converts "C$39,490" to
    # "39,490 Canadian dollars" so the downstream USD handler
    # doesn't mis-parse it and strand the "C" syllable.
    # See replace_canadian_currency() docstring for the operator-
    # caught bug this prevents (TST Ep471, May 13 2026).
    if do_currency:
        text = replace_canadian_currency(text)
    # Signed currency next: +$1.11 → "up $1.11", -$5.75 → "down $5.75"
    # Must run BEFORE price ranges so "-$5.75" isn't misread as a range endpoint.
    if do_currency:
        text = replace_signed_currency(text)
    # Price ranges: $350-$400 → "three fifty to four hundred dollars"
    if do_currency:
        text = replace_price_ranges(text)
    # Plain number ranges: 10-20 → "ten to twenty" (after price ranges,
    # before signed numbers so hyphens aren't misread as negatives)
    text = replace_number_ranges(text)

    # ── 4. Number/value expansions ──
    # Order matters: currency before percentages, large numbers before units.
    if do_k_numbers:
        text = replace_large_numbers_with_k(text)

    if do_currency:
        text = replace_currency(text)

    if do_percentages:
        text = replace_percentages(text)

    # ── 5. Leftover signed numbers (bare +1.11 / -2.50 not caught above) ──
    text = replace_signed_numbers(text)

    if do_dates:
        text = replace_dates(text)

    if do_times:
        text = replace_times(text)

    if do_timezones:
        text = replace_timezones(text)

    if do_episodes:
        text = replace_episode_numbers(text)

    if do_quarters:
        text = replace_quarter_notation(text)

    if do_roman:
        text = replace_roman_numerals(text)

    if do_ordinals:
        text = replace_ordinal_numbers(text)

    if do_scientific:
        text = replace_scientific_designations(text)

    if do_large_numbers:
        text = replace_standalone_large_numbers(text)

    if do_units:
        text = replace_units(text)

    # ── 6. Multiplier notation (after numbers are expanded) ──
    text = replace_multiplier_notation(text)

    # ── 7. Dictionary-based pronunciation fixes ──
    if do_acronyms:
        acronyms = dict(COMMON_ACRONYMS)
        if extra_acronyms:
            acronyms.update(extra_acronyms)
        if skip_acronyms:
            for key in skip_acronyms:
                acronyms.pop(key, None)

        words = dict(WORD_PRONUNCIATIONS)
        if extra_words:
            words.update(extra_words)

        text = apply_pronunciation_fixes(
            text,
            acronyms=acronyms,
            word_pronunciations=words,
        )

    # ── 8. Post-acronym cleanup ──
    # Slashes to spaces (after acronyms so P/E → "P to E" is preserved)
    text = replace_slashes(text)
    # Expanded acronyms followed by hyphens: "A I-powered" → "A I powered"
    # Matches spaced-letter expansions (A I, E V, M L, etc.) before a hyphen.
    text = re.sub(r"([A-Z](?: [A-Z])+)-(\w)", r"\1 \2", text)

    # ── 9. Final whitespace cleanup ──
    text = re.sub(r"  +", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
