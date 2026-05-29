#!/usr/bin/env python3
"""CI validation helper for the 'Validate output' step in run-show.yml.

Checks the generated digest markdown for:
- LLM refusal language (common when the model declines to write the script)
- Suspiciously short content (catches thin generations before they reach RSS/X/YouTube)

This is intentionally a small standalone script so it can be invoked from
GitHub Actions matrix jobs without importing the full engine package.
"""

import re
import pathlib
import sys
from datetime import datetime


REFUSAL_RE = re.compile(
    r'(?i)\bI\s+(?:cannot|can[\x27\u2019]t)\s+(?:create|generate|produce|write)\b'
)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: validate_digest_content.py <output_dir> [today_YYYYMMDD]")
        sys.exit(2)

    output_dir = pathlib.Path(sys.argv[1])
    today = sys.argv[2] if len(sys.argv) > 2 else datetime.now().strftime("%Y%m%d")

    md_files = sorted(output_dir.glob(f"*{today}*.md"))
    if not md_files:
        # No digest for today is already warned about earlier in the step; not a hard failure here
        print(f"No digest markdown found for {today} in {output_dir}")
        sys.exit(0)

    for f in md_files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")[:2000]
        except Exception as exc:
            print(f"ERROR: Could not read {f.name}: {exc}")
            sys.exit(1)

        if REFUSAL_RE.search(text):
            print(f"ERROR: Digest {f.name} contains LLM refusal text")
            sys.exit(1)

        stripped_len = len(text.strip())
        if stripped_len < 200:
            print(f"ERROR: Digest {f.name} is suspiciously short ({stripped_len} chars)")
            sys.exit(1)

    print(f"Digest content validated ({len(md_files)} file(s))")


if __name__ == "__main__":
    main()
