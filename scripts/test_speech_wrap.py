#!/usr/bin/env python3
"""Test the ``<fast><build-intensity>`` speech-tag wrap on a single
sentence so you can compare against bare text on the same clone.

Outputs two MP3s side-by-side so you can A/B them in any audio player:

  /tmp/speech_wrap_test/bare.mp3       (no wrap)
  /tmp/speech_wrap_test/wrapped.mp3    (<fast><build-intensity>...</...></...>)

Usage:
    python scripts/test_speech_wrap.py
    python scripts/test_speech_wrap.py "your custom sentence here"

Requires GROK_API_KEY (or XAI_API_KEY) in the environment / .env.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow importing engine/* from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from engine.tts import synthesize


DEFAULT_SENTENCE = (
    "Tesla just opened a new Supercharger corridor connecting Vancouver to "
    "Calgary, adding twelve stations along the Trans-Canada Highway."
)


def main() -> int:
    load_dotenv()
    api_key = os.environ.get("GROK_API_KEY") or os.environ.get("XAI_API_KEY")
    if not api_key:
        print("ERROR: set GROK_API_KEY or XAI_API_KEY", file=sys.stderr)
        return 1

    sentence = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SENTENCE
    voice_id = os.environ.get("TEST_VOICE_ID", "kdif6sqjcyiq")

    out_dir = Path("/tmp/speech_wrap_test")
    out_dir.mkdir(parents=True, exist_ok=True)

    bare = out_dir / "bare.mp3"
    wrapped = out_dir / "wrapped.mp3"

    print(f"Voice: {voice_id}")
    print(f"Sentence: {sentence!r}")
    print()
    print(f"Synthesizing bare → {bare}")
    synthesize(
        sentence, voice_id, bare,
        api_key=api_key, provider="grok", language_code="en",
    )
    print(f"Synthesizing wrapped → {wrapped}")
    synthesize(
        sentence, voice_id, wrapped,
        api_key=api_key, provider="grok", language_code="en",
        speech_wrap_open="<fast><build-intensity>",
        speech_wrap_close="</build-intensity></fast>",
    )
    print()
    print("Done. A/B compare:")
    print(f"  open {bare}")
    print(f"  open {wrapped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
