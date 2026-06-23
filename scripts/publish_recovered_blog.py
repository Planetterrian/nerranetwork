#!/usr/bin/env python3
"""Generate the website/blog artifacts for a recovered episode.

publish_recovered_episode.py added the episodes to the *podcast* RSS, but the
website (nerranetwork.com) and the *blog* RSS (blog.rss / blog_<show>.rss)
render from the per-episode digest ``.md`` files (engine.blog globs
``digests/<show>/*.md``). The recovered episodes never had a committed digest,
so the blog/site/blog-RSS skipped them. This writes a minimal hook-led digest
``.md`` and runs the SAME blog + summaries generators the daily pipeline uses
(run_show steps 12 + 12a): blog post HTML, per-show + network blog index,
blog RSS, and the summaries JSON the show/summaries pages read.

Show notes are intentionally minimal (the original digest is gone) — the hook
+ the audio player. Re-run with a real transcript later to enrich if wanted.

Usage:
    python3 scripts/publish_recovered_blog.py --set tesla_ep519
    python3 scripts/publish_recovered_blog.py --set spacex_ep12 --commit --push
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.publish_recovered_episode import EPISODES  # noqa: E402


def _build_digest_md(show_name: str, hook: str, transcript: str = "") -> str:
    """An honest hook-led digest the blog parser understands.

    Uses the episode transcript (the real spoken content) as the body when
    available — the original LLM digest is lost, so the transcript is the
    most faithful show notes we can offer. Falls back to a short hook-led
    note when no transcript is present.
    """
    lead = (hook[0].lower() + hook[1:]) if hook else ""
    body = transcript.strip()
    if not body:
        body = (
            f"This episode of {show_name} covers {lead} "
            "Press play above for the full episode."
        )
    return f"# {show_name}\n> **{hook}**\n---\n\n{body}\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", dest="ep", choices=sorted(EPISODES), required=True)
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--push", action="store_true")
    args = ap.parse_args()

    spec = EPISODES[args.ep]
    slug = spec["show"]
    ep_num = int(spec["episode"])
    date = datetime.strptime(str(spec["date"]), "%Y%m%d").date()
    hook = spec["hook"]
    audio_url = spec["audio_url"]

    from engine.config import load_config
    config = load_config(f"shows/{slug}.yaml")
    digests_dir = ROOT / config.publishing.audio_subdir
    digests_dir.mkdir(parents=True, exist_ok=True)

    # 1. Write the digest .md the blog generator scans, using the episode
    # transcript as the body when it's present (real spoken content).
    ep_prefix = f"{config.episode.prefix}_Ep{ep_num:03d}_{date:%Y%m%d}"
    transcript = ""
    transcript_txt = digests_dir / f"{ep_prefix}_transcript.txt"
    if transcript_txt.exists():
        transcript = transcript_txt.read_text(encoding="utf-8")
        print(f"Using transcript: {transcript_txt.name} ({len(transcript.split())} words)")
    digest_md = digests_dir / f"{ep_prefix}.md"
    x_thread = _build_digest_md(config.name, hook, transcript)
    digest_md.write_text(x_thread, encoding="utf-8")
    print(f"Wrote digest: {digest_md.relative_to(ROOT)} ({len(x_thread.split())} words)")

    written = [digest_md]
    for tf in (transcript_txt, digests_dir / f"{ep_prefix}_transcript.json"):
        if tf.exists():
            written.append(tf)

    # 2. Summaries JSON (the show/summaries pages read this).
    from engine.publisher import save_summary_to_github_pages
    summaries_json = ROOT / config.publishing.summaries_json
    save_summary_to_github_pages(
        summary_text=x_thread,
        summaries_json_path=summaries_json,
        podcast_name=config.publishing.summaries_podcast_name or slug,
        episode_num=ep_num,
        episode_title=f"Ep {ep_num}: {hook}",
        audio_url=audio_url,
        rss_url=f"{config.publishing.base_url}/{config.publishing.rss_file}",
    )
    written.append(summaries_json)
    print(f"Updated summaries: {summaries_json.relative_to(ROOT)}")

    # 3. Blog post + indexes + blog RSS (mirror run_show step 12a).
    from engine.blog import (
        extract_blog_metadata,
        generate_blog_post_html,
        regenerate_blog_rss_for_show_slug,
    )
    from generate_html import (
        NETWORK_SHOWS,
        _get_jinja_env,
        generate_blog_index,
        generate_network_blog_index,
    )

    env = _get_jinja_env()
    meta = extract_blog_metadata(x_thread, slug, digest_md.name, file_path=digest_md)
    meta["episode_num"] = ep_num
    # The .md carries no audio URL; the daily pipeline's metadata does. Set it
    # so the post embeds the player (bare R2 URL, matching other blog posts).
    meta["audio_url"] = audio_url
    html = generate_blog_post_html(x_thread, meta, NETWORK_SHOWS[slug], env)
    blog_dir = ROOT / "blog" / slug
    blog_dir.mkdir(parents=True, exist_ok=True)
    blog_path = blog_dir / f"ep{ep_num:03d}.html"
    from engine.utils import strip_lone_surrogates
    blog_path.write_text(strip_lone_surrogates(html), encoding="utf-8")
    written.append(blog_path)
    print(f"Wrote blog post: {blog_path.relative_to(ROOT)}")

    generate_blog_index(slug)
    generate_network_blog_index()
    written.append(blog_dir / "index.html")
    written.append(ROOT / "blog" / "index.html")
    print("Regenerated blog index + network index")

    rss = regenerate_blog_rss_for_show_slug(slug, ROOT)
    if rss:
        written.append(rss)
        written.append(ROOT / "blog.rss")
        print(f"Regenerated blog RSS: {rss.name} (+ blog.rss)")

    if args.commit or args.push:
        rels = sorted({str(p.relative_to(ROOT)) for p in written if p.exists()})
        subprocess.run(["git", "add", *rels], cwd=ROOT, check=True)
        subprocess.run(
            ["git", "commit", "-m", f"Add recovered {slug} Ep{ep_num} to blog + website"],
            cwd=ROOT, check=True,
        )
        print("Committed.")
        if args.push:
            subprocess.run(["git", "push"], cwd=ROOT, check=True)
            print("Pushed.")
    else:
        print("\nReview the changes (git status), then re-run with --commit --push.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
