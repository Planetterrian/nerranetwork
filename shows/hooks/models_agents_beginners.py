"""Models & Agents for Beginners — pronunciation hook for the Grok custom voice.

MAB runs on the network's shared Grok TTS custom voice (its ``tts: {}`` block
inherits the default — see landmines #11 / #17). The earlier Fish-Audio /
Chatterbox premise of this hook is obsolete.

**Key principle (Grok voice):** keep acronym *letter-spellings* (AI→"A I",
GPT-4→"G P T four") and genuinely-foreign / hard proper-name guides. Do NOT add
phonetic respellings of common English words — the Grok voice says them
natively, and because this hook runs at script-save time the respelling also
leaks into the saved _tts.txt → blog/RSS transcript. Network-wide proper-name
respellings now live in ``shows/pronunciation_map.yaml`` (audio-only); don't
duplicate them here.
"""

from __future__ import annotations


def pronunciation_overrides() -> dict:
    """Return MAB-specific overrides layered on the shared pipeline.

    Called by ``run_show.py:_apply_pronunciation()`` to customize the shared
    ``prepare_text_for_tts()`` pipeline (merged over COMMON_ACRONYMS /
    WORD_PRONUNCIATIONS).
    """
    return {
        # Acronym letter-spellings + model-version names not in the shared
        # COMMON_ACRONYMS, or where the beginner show wants AI always spelled
        # out. These are letter expansions, not phonetic guesses.
        "extra_acronyms": {
            # AI compound forms — ensure "AI" is always spelled out
            "AI-powered": "A I powered",
            "AI-driven": "A I driven",
            "AI-based": "A I based",
            "AI-generated": "A I generated",
            "AI-first": "A I first",
            "AI-native": "A I native",
            "AI-enabled": "A I enabled",
            "AI-ready": "A I ready",
            "AI-augmented": "A I augmented",

            # Org/product compound names with AI
            "OpenAI's": "Open A I's",
            "OpenAI": "Open A I",
            "GenAI": "Jen A I",
            "xAI's": "ex A I's",
            "xAI": "ex A I",
            "CrewAI": "Crew A I",
            "CrewAI's": "Crew A I's",
            "AutoGPT": "Auto G P T",
            "AutoGen": "Auto-Jen",
            "ChatGPT": "Chat G P T",
            "ChatGPT's": "Chat G P T's",

            # Model version names
            "GPT-4o": "G P T four oh",
            "GPT-4": "G P T four",
            "GPT-5": "G P T five",
            "GPT-3.5": "G P T three point five",
            "GPT-3": "G P T three",
            "GPT-2": "G P T two",

            # Acronyms that need a phonetic / letter hint on the voice
            "SOTA": "so-tah",
            "LoRA": "laura",
            "LoRAs": "lauras",
            "QLoRA": "cue-laura",
            "GGUF": "gee-guff",
            "ONNX": "onyx",
            "VRAM": "vee-ram",
            "FP16": "F P sixteen",
            "FP32": "F P thirty-two",
            "INT8": "int eight",
            "INT4": "int four",

            # Benchmark names
            "GSM8K": "G S M eight K",
            "GSM8k": "G S M eight K",
            "HellaSwag": "Hella-Swag",
            "HumanEval": "Human Eval",

            # Common spoken-word fixes
            "i.e.": "that is",
            "e.g.": "for example",
            "etc.": "et cetera",
            "vs.": "versus",
            "vs": "versus",
            "w/": "with",
            "w/o": "without",
        },

        # Genuinely-foreign / hard proper names the Grok voice mangles raw.
        # NOTE: do NOT add common English words or camelCase brand compounds
        # here (DeepSeek, LangChain, PyTorch, multimodal, dataset, …) — the Grok
        # voice says them natively and the respelling leaks into the transcript.
        # Network-wide names (Karpathy, Amodei, Mistral, Altman, …) are handled
        # by shows/pronunciation_map.yaml — don't duplicate them here.
        "extra_words": {
            # AI researcher names (non-English, genuinely need help on the voice)
            "Andrej": "On-dray",
            "Sutskever": "Suts-kever",
            "Hassabis": "Ha-sah-bis",
            "LeCun": "Luh-Kuhn",
            "Vaswani": "Vaz-wah-nee",
            "Bengio": "Ben-jee-oh",

            # ``NVIDIA`` stays pinned to itself for MAB only: the shared
            # WORD_PRONUNCIATIONS still maps NVIDIA→"En-vidia"; whether MAB
            # should instead match the network's "Nvidia" is an audio decision
            # left for a listen-test, so the identity override is kept for now.
            "NVIDIA": "NVIDIA",
            "Nvidia": "Nvidia",
            "Nvidia's": "Nvidia's",

            # Model / org names (non-English or product-specific pronunciations)
            "Mixtral": "Mix-tral",
            "Groq": "Grock",
            "Groq's": "Grock's",
            "Phi-3": "Fie three",
            "Phi-4": "Fie four",
            "Midjourney": "Mid-journey",
            "Midjourney's": "Mid-journey's",
            "Sakana": "Sah-kah-nah",
            "Sakana's": "Sah-kah-nah's",
            "Gradio": "Grah-dee-oh",
            "arXiv": "archive",
            "ArXiv": "archive",
        },
    }
