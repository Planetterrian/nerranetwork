#!/usr/bin/env python3
"""CI validation helper for the 'Validate output' step in run-show.yml.

Validates that an RSS XML file is well-formed (no more, no less — the
broader post-run validation lives in engine/post_run_validation.py and
is used by run_show.py itself).
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: validate_rss_feed.py <rss_path>")
        sys.exit(2)

    rss_path = Path(sys.argv[1])
    if not rss_path.exists():
        print(f"ERROR: RSS file does not exist: {rss_path}")
        sys.exit(1)

    try:
        ET.parse(str(rss_path))
        print(f"RSS valid: {rss_path}")
    except ET.ParseError as exc:
        print(f"ERROR: RSS feed {rss_path} is not valid XML: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
