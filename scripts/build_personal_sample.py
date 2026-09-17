#!/usr/bin/env python3
"""Build the public SAMPLE personal edition for /join.html.

Nobody buys a personalized podcast unheard. This renders a short, honest
excerpt of what a Personal News Network morning sounds like — the same
pipeline as the real per-subscriber build (scripts/build_personal_feeds.py),
for a fictional listener, with each show cut to a ~75-second taste and
faded — and uploads it to the public audio bucket:

    https://audio.nerranetwork.com/personal/sample/<slug>.mp3

Run it whenever the sample should sound current (a month old is fine; the
point is the shape, not the news)::

    python scripts/build_personal_sample.py                 # build + upload
    python scripts/build_personal_sample.py --dry-run --keep ./sample

The excerpt is labelled a sample everywhere it appears; Mira says the
listener's name ("Alex") and city like she would for a member, which is
what makes it a real demonstration rather than a trailer.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from engine.daily_edition import EDITIONS, discover_segments  # noqa: E402
from engine.personal_edition import (  # noqa: E402
    MIRA_PERSONAL_DISCLOSURE,
    PersonalSpec,
    build_markets_line,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s",
                    stream=sys.stdout)
logger = logging.getLogger("nerra_personal_sample")

SAMPLE_SLUG = "vancouver"
SAMPLE_KEY = f"personal/sample/{SAMPLE_SLUG}.mp3"
SAMPLE_URL = f"https://audio.nerranetwork.com/{SAMPLE_KEY}"
#: The fictional listener. Not a real member; no token; nothing stored.
SAMPLE_SPEC = dict(
    token="5a3p1e" + "0" * 26, shows=["spacex", "tesla"], tier="personal_local",
    first_name="Alex", city="Vancouver, BC", cities=["Vancouver, BC"],
    topics=["Metro Vancouver housing"],
)
#: Seconds of each show kept in the sample, then a 3-second fade.
TASTE_SECONDS = 75.0


def taste_cmd(src: Path, out: Path, seconds: float) -> List[str]:
    from engine.daily_edition import SEGMENT_ENCODE_ARGS

    return (["ffmpeg", "-y", "-i", str(src), "-t", f"{seconds:.2f}", "-af",
             f"afade=t=out:st={seconds - 3:.2f}:d=3"]
            + SEGMENT_ENCODE_ARGS + [str(out)])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Build, don't upload")
    parser.add_argument("--keep", default="", help="Copy the MP3 here")
    parser.add_argument("--date", default="", help="Edition date (default today UTC)")
    args = parser.parse_args()

    import build_personal_feeds as bpf  # the real builder's pieces

    target_date = (dt.date.fromisoformat(args.date) if args.date
                   else dt.datetime.now(dt.timezone.utc).date())
    spec = PersonalSpec(**SAMPLE_SPEC)
    all_segments, _ = discover_segments(EDITIONS["en"], ROOT, target_date)
    by_slug = {s.slug: s for s in all_segments}
    cache_root = Path(tempfile.gettempdir()) / f"np_cache_{target_date:%Y%m%d}"
    cache = bpf.build_segment_cache(spec.shows, by_slug, cache_root)
    segments = [by_slug[s] for s in spec.shows if s in by_slug and s in cache]
    if len(segments) < 2:
        logger.error("sample needs both shows published today; have %d", len(segments))
        return 1
    sting = bpf.ensure_sting(cache_root)

    workdir = Path(tempfile.mkdtemp(prefix="np_sample_"))
    try:
        links = bpf.generate_personal_links(spec, segments, target_date)
        local_texts = bpf.generate_local_briefs(spec, target_date)
        topics_text = bpf.generate_topics_brief(spec, target_date)
        markets_text = build_markets_line(ROOT)

        intro = bpf._mira_piece(
            links["intro"] + " This is a sample edition — every real one is built "
            "fresh each morning for one listener.", "intro", workdir)
        pieces: List[Path] = [intro]
        for i, (_city, text) in enumerate(local_texts, 1):
            pieces.append(bpf._mira_piece(text, f"local_{i}", workdir))
        if topics_text:
            pieces.append(bpf._mira_piece(topics_text, "topics", workdir))
        if markets_text:
            pieces.append(bpf._mira_piece(markets_text, "markets", workdir))
        for i, seg in enumerate(segments):
            if i > 0:
                pieces.append(bpf._mira_piece(
                    links["handoffs"][i - 1], f"handoff_{i}", workdir, lead_in=sting))
            taste = workdir / f"taste_{seg.slug}.mp3"
            bpf._run(taste_cmd(cache[seg.slug], taste, TASTE_SECONDS), f"taste {seg.slug}")
            pieces.append(taste)
        signoff = bpf._mira_piece(
            "That's the shape of it. In your own edition every show plays in "
            "full, in your order, with your city and your topics. "
            + MIRA_PERSONAL_DISCLOSURE, "signoff", workdir, lead_in=sting)
        pieces.append(signoff)

        from engine.audio import concatenate_audio

        final = workdir / f"{SAMPLE_SLUG}.mp3"
        concatenate_audio(pieces, final)
        total = bpf._duration(final)
        logger.info("sample: %0.1f min, %d pieces", total / 60, len(pieces))
        if args.keep:
            Path(args.keep).mkdir(parents=True, exist_ok=True)
            shutil.copy2(final, Path(args.keep) / final.name)
        if args.dry_run:
            return 0
        from engine.storage import upload_to_r2

        url = upload_to_r2(
            final, SAMPLE_KEY, bucket="podcast-audio",
            endpoint_url=os.environ["R2_ENDPOINT_URL"],
            access_key=os.environ["R2_ACCESS_KEY_ID"],
            secret_key=os.environ["R2_SECRET_ACCESS_KEY"],
            public_base_url="https://audio.nerranetwork.com")
        logger.info("sample: uploaded → %s", url)
        return 0
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
