#!/usr/bin/env python3
"""Build the committed share cards (and, with --episodes, episode cards on R2).

    python scripts/build_share_cards.py              # network + shows + pages
    python scripts/build_share_cards.py --check      # exit 1 if a card is stale
    python scripts/build_share_cards.py --episodes tesla --limit 20 [--upload]

The committed cards live in ``assets/share/`` and are rewritten only when
their pixels change (``engine.share_cards.save_jpeg``), so a rebuild with
nothing new adds nothing to git history. Copy on a card is derived from the
registry, ``engine.topic_hubs`` and the page list below — never a number that
moves daily (an episode count would rewrite every hub card every night).

``--episodes`` renders episode cards for a show's recent episodes from its
gallery scenes (originals through the R2 gallery bucket when credentials are
set, else the public 800px thumbnail) and, with ``--upload``, puts them on R2
and records them in ``digests/<dir>/share_cards.json``. run_show does the same
for each new episode; this is the backfill.
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import share_cards as S  # noqa: E402
from engine.brand import (  # noqa: E402
    NETWORK_PROMISE_SHORT, NETWORK_SUBJECTS, NETWORK_TAGLINE, network_promise,
)

logger = logging.getLogger("build_share_cards")

# The network card's artwork: the BREADTH of the network, one show per
# subject the promise names (space, AI, markets, world news, science), never
# two of one beat (Oct 18 2026, operator: the card had led on SpaceX and
# Tesla). A slug that leaves the registry drops out; the grid needs nine.
NETWORK_COVER_SLUGS = (
    "nerra_daily", "fascinating_frontiers", "models_agents",
    "omni_view_world", "planetterrian", "modern_investing",
    "unintended_consequences", "ai_chips", "age_of_ai",
    "first_principles", "longevity", "prediction_markets",
)

STRAND_KICKERS = {
    "ai": "AI",
    "markets": "Markets",
    "world": "World news",
    "local": "Local news",
    "health": "Health & science",
    "mira": "Hosted by Mira",
}


def _page_cards(show_count: int) -> dict:
    """key -> (kicker, title, subtitle, cover slugs, accent). Keys are
    ``engine.share_cards.page_key_for_path`` of the page's URL path."""
    n = show_count
    return {
        "mira": ("Meet the host", "Mira",
                 "Nerra's AI host. She anchors the daily edition and interviews real "
                 "people, who get a week to approve, cut or refuse the transcript.",
                 ("nerra_daily", "age_of_ai", "nerra_voices"), "#7C3AED"),
        "join": ("Nerra Personal", "Your shows. Your order. One private daily episode.",
                 "Pick the shows you want and Mira builds your edition every morning.",
                 ("nerra_daily", "spacex", "models_agents", "planetterrian"), "#6B47FF"),
        "explore": ("Explore", "Every show, by subject",
                    "AI, space, markets, science, world and local news, and language "
                    "learning. Every public show is free.",
                    ("models_agents", "spacex", "omni_view_world", "planetterrian"), ""),
        "topics": ("Topics", "Browse by subject",
                         "Every Nerra show grouped by what it covers, with sources named.",
                         ("ai_chips", "fascinating_frontiers", "modern_investing", "longevity"), ""),
        "start-here": ("Start here", "Find your show",
                       f"{n} free shows on {NETWORK_SUBJECTS}.",
                       ("nerra_daily", "fascinating_frontiers", "models_agents", "omni_view_world"), ""),
        "about": ("About", NETWORK_TAGLINE,
                  NETWORK_PROMISE_SHORT + " Made in Vancouver, Canada.",
                  ("nerra_daily", "planetterrian", "modern_investing", "omni_view_world"), ""),
        "faq": ("Questions", "How Nerra works",
                "How the shows use AI, who hosts, when episodes release and how to subscribe.",
                (), ""),
        "how-to-listen": ("How to listen", "Every show, in any podcast app",
                          "Apple Podcasts, Spotify, YouTube or any RSS app. Every feed listed.",
                          (), "#00A3C4"),
        "support": ("Support", "Keep the network free",
                    "See what the network costs to run, and chip in if you want it to keep existing.",
                    (), "#0B7A45"),
        "sponsor": ("Sponsor", "Reach curious listeners",
                    "Measured audience by show, the ways to sponsor, and the rules every sponsor accepts.",
                    (), ""),
        "editorial": ("Editorial process", "How every episode is made",
                      "Sources named, claims checked against them, corrections in public.",
                      (), "#0F766E"),
        "claims": ("Claims & corrections", "Every claim, checked against its source",
                   "What each check found, what it could not confirm, and every correction filed.",
                   (), "#0F766E"),
        "ai-disclosure": ("AI disclosure", "What AI does here, and what people own",
                          "Writing, narration and imagery are automated. Briefs, sources, "
                          "standards and corrections belong to people.",
                          (), ""),
        "gallery": ("Gallery", "Every episode's artwork",
                    "AI-generated scenes from every show, free to reuse under CC BY-SA 4.0.",
                    (), "#00A3C4"),
        "books": ("Books", "Stories from the podcasts",
                  "Anthologies from Unintended Consequences and First Principles, "
                  "as ebook and audiobook.",
                  ("unintended_consequences", "first_principles"), "#B45309"),
        "press": ("Press", "Press & media kit",
                  "Boilerplate, logos, the founder's contact and every show.",
                  (), ""),
        "data": ("Data & dashboards", "Live data behind the shows",
                 "SpaceX launches, Tesla deliveries, the Offshore North campaign and "
                 "the Modern Investing record.",
                 ("spacex", "tesla", "offshore_north", "modern_investing"), ""),
        "player": ("Player", "Every show in one player",
                   "Build a queue across the network and listen in one place.",
                   (), ""),
        "blog": ("The blog", "Every episode, in writing",
                       "Today's stories from every show, with their sources linked.",
                       ("models_agents", "spacex", "omni_view", "fascinating_frontiers"), ""),
        "guest-picks": ("Guest picks", "Books, advice and who to interview next",
                        "Named by every guest on The Age of AI and Nerra Voices.",
                        ("age_of_ai", "nerra_voices"), "#7C3AED"),
        "contact": ("Contact", "Get in touch",
                    "Press, partnerships, corrections, privacy and general feedback.",
                    (), ""),
    }


def _registry() -> dict:
    import generate_html as g
    return dict(g.NETWORK_SHOWS)


def _covers(shows: dict, slugs) -> list:
    return S.cover_images(shows[s]["podcast_image"] for s in slugs
                          if s in shows and shows[s].get("podcast_image"))


def _members_only(slug: str) -> bool:
    path = ROOT / "shows" / f"{slug}.yaml"
    if not path.is_file():
        return False
    try:
        import yaml
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return str(((data.get("access") or {}).get("mode")) or "") == "members_only"
    except Exception:  # noqa: BLE001
        return False


def _display_path(show_page: str) -> str:
    p = (show_page or "").strip("/")
    return p[:-5] if p.endswith(".html") else p


def build_committed(check: bool = False) -> list[str]:
    """Render every committed card. Returns the paths that changed (or would)."""
    shows = _registry()
    changed: list[str] = []
    alts: dict[str, str] = {}

    def emit(img, path: Path, alt: str = "") -> None:
        if alt:
            alts[path.relative_to(ROOT).as_posix()] = " ".join(alt.split())
        if check:
            import tempfile
            with tempfile.TemporaryDirectory() as td:
                tmp = Path(td) / "c.jpg"
                S.save_jpeg(img, tmp)
                if not path.is_file() or path.read_bytes() != tmp.read_bytes():
                    changed.append(str(path.relative_to(ROOT)))
            return
        if S.save_jpeg(img, path):
            changed.append(str(path.relative_to(ROOT)))

    # The FREE shows a visitor can hear — the homepage's number, never the
    # registry's (which counts members-only and feedless shows too).
    import generate_html as g
    count = len(g._public_shows())
    network = S.render_network_card(show_count=count,
                                    covers=_covers(shows, NETWORK_COVER_SLUGS)[:9])
    emit(network, S.network_card_path(),
         f"{S.NETWORK_NAME}: {NETWORK_TAGLINE} {network_promise(count)}")
    # The legacy default is still named by hand-written pages and by links the
    # platforms cached: it becomes the network card too (it still carried the
    # no-advertising promise the Oct 11 sponsor policy retired).
    legacy = ROOT / "assets" / "og-preview.png"
    buf = io.BytesIO()
    network.save(buf, "PNG", optimize=True)
    if not legacy.is_file() or legacy.read_bytes() != buf.getvalue():
        if not check:
            legacy.write_bytes(buf.getvalue())
        changed.append(str(legacy.relative_to(ROOT)))

    from engine import show_lang
    from engine import topic_hubs as H
    all_shows = [dict(cfg, slug=slug) for slug, cfg in shows.items()]
    first_hub = {}
    for hub in H.TOPIC_HUBS:  # declaration order: a show's first hub names it
        for m in H.hub_shows(hub, all_shows):
            first_hub.setdefault(m["slug"], hub.get("heading") or "")

    for slug, cfg in sorted(shows.items()):
        if not cfg.get("podcast_image"):
            continue
        covers = _covers(shows, [slug])
        kicker = (STRAND_KICKERS.get(cfg.get("strand") or "")
                  or first_hub.get(slug) or "Podcast")
        if _members_only(slug):
            kicker = "Nerra Personal members"
        emit(S.render_show_card(
            name=cfg.get("name", slug),
            tagline=cfg.get("hero_tagline") or cfg.get("tagline") or "",
            schedule=cfg.get("schedule") or "",
            cover=covers[0] if covers else None,
            brand_color=cfg.get("brand_color") or "",
            kicker=kicker,
            domain_path=_display_path(cfg.get("show_page") or ""),
            lang=show_lang.page_lang(slug),
        ), S.show_card_path(slug),
            f"{cfg.get('name', slug)}, a {S.NETWORK_NAME} podcast: "
            f"{cfg.get('hero_tagline') or cfg.get('tagline') or ''}")

    for key, (kicker, title, sub, slugs, accent) in _page_cards(count).items():
        path = key
        emit(S.render_page_card(kicker=kicker, title=title, subtitle=sub,
                                covers=_covers(shows, slugs), accent_color=accent,
                                domain_path=path),
             S.page_card_path(key), f"{kicker} — {title}. {sub}")

    for hub in H.TOPIC_HUBS:
        members = H.hub_shows(hub, all_shows)
        if not members:
            continue
        names = [m.get("name", "") for m in members]
        sub = ", ".join(names[:3]) + (f" and {len(names) - 3} more" if len(names) > 3 else "")
        emit(S.render_page_card(
            kicker="Topic", title=hub.get("heading") or hub["id"], subtitle=sub,
            covers=_covers(shows, [m["slug"] for m in members][:4]),
            accent_color=(members[0].get("brand_color") or ""),
            domain_path=f"topics/{hub['id']}",
        ), S.page_card_path(S.page_key_for_path(f"topics/{hub['id']}.html")),
            f"{hub.get('heading') or hub['id']} podcasts on {S.NETWORK_NAME}: {sub}")

    manifest = json.dumps({"alt": dict(sorted(alts.items()))}, indent=1,
                          ensure_ascii=False) + "\n"
    current = S.MANIFEST_PATH.read_text(encoding="utf-8") if S.MANIFEST_PATH.is_file() else ""
    if manifest != current:
        if not check:
            S.MANIFEST_PATH.write_text(manifest, encoding="utf-8")
        changed.append(str(S.MANIFEST_PATH.relative_to(ROOT)))
    return changed


# ---------------------------------------------------------------------------
# Episode backfill
# ---------------------------------------------------------------------------

def _gallery_scene(slug: str, episode_num: int):
    """The episode's first 16:9 scene from the gallery, as a PIL image."""
    from PIL import Image
    path = ROOT / "site" / "data" / "gallery" / f"{slug}.json"
    try:
        images = json.loads(path.read_text(encoding="utf-8")).get("images") or []
    except (OSError, ValueError):
        return None
    tag = f"ep{episode_num:03d}"
    scenes = sorted((i for i in images
                     if i.get("episode_id") == tag and i.get("intended_use") == "segment_card"
                     and (i.get("width") or 0) > (i.get("height") or 0)),
                    key=lambda i: i.get("generated_at") or "")
    if not scenes:
        return None
    first = scenes[0]
    data = _r2_gallery_bytes(first.get("original_key") or "")
    if data is None:
        import urllib.request
        try:
            req = urllib.request.Request(first.get("thumbnail_url") or "",
                                         headers={"User-Agent": "NerraNetwork-share-cards/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 - our host
                data = r.read()
        except Exception as exc:  # noqa: BLE001
            logger.warning("%s ep%s: no scene (%s)", slug, episode_num, exc)
            return None
    try:
        return Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:  # noqa: BLE001
        return None


def _r2_gallery_bytes(key: str):
    endpoint = os.getenv("R2_ENDPOINT_URL") or os.getenv("R2_ENDPOINT") or ""
    ak, sk = os.getenv("R2_ACCESS_KEY_ID", ""), os.getenv("R2_SECRET_ACCESS_KEY", "")
    if not (key and endpoint and ak and sk):
        return None
    try:
        import boto3
        client = boto3.client("s3", endpoint_url=endpoint, aws_access_key_id=ak,
                              aws_secret_access_key=sk, region_name="auto")
        return client.get_object(Bucket=os.getenv("R2_GALLERY_BUCKET") or "nerra-gallery",
                                 Key=key)["Body"].read()
    except Exception as exc:  # noqa: BLE001
        logger.warning("gallery original %s unavailable: %s", key, exc)
        return None


def _record_hook(rec: dict) -> str:
    """The episode's hook: the digest's ``> **hook**`` line, else its title."""
    import re
    m = re.search(r"^>\s*\*\*(.+?)\*\*\s*$", rec.get("content") or "", re.M)
    if m:
        return m.group(1).strip()
    title = rec.get("hook") or rec.get("episode_title") or rec.get("title") or ""
    return re.sub(r"^Ep(?:isode)?\s*\d+\s*[:—–-]\s*", "", title).strip()


def build_episodes(slug: str, limit: int, upload: bool, out_dir: Path) -> int:
    from engine.config import load_config
    from engine.share_cards import episode_card_for
    config = load_config(ROOT / "shows" / f"{slug}.yaml")
    digest_dir = ROOT / config.episode.output_dir
    summaries = sorted(digest_dir.glob("summaries_*.json"))
    if not summaries:
        logger.warning("%s: no summaries file", slug)
        return 0
    raw = json.loads(summaries[0].read_text(encoding="utf-8"))
    records = raw if isinstance(raw, list) else (raw.get("summaries") or raw.get("episodes") or [])
    records = [r for r in records
               if isinstance(r, dict) and (r.get("episode_num") or r.get("episode"))]
    records.sort(key=lambda r: int(r.get("episode_num") or r.get("episode") or 0), reverse=True)
    done = 0
    for rec in records[:limit]:
        ep = int(rec.get("episode_num") or rec.get("episode") or 0)
        # A scene card is final; an art card is upgraded when a scene exists.
        recorded = S.load_episode_cards(digest_dir).get(str(ep)) or {}
        if upload and recorded.get("source") == "scene":
            continue
        scene = _gallery_scene(slug, ep)
        result = episode_card_for(config, episode_num=ep, hook=_record_hook(rec),
                                  date_str=rec.get("date") or "", scene=scene,
                                  out_dir=out_dir, upload=upload)
        if result:
            done += 1
            print(f"{slug} ep{ep}: {result}")
    return done


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="exit 1 when a committed card is stale")
    ap.add_argument("--episodes", nargs="*", metavar="SLUG",
                    help="render episode cards for these shows ('all' = every public show)")
    ap.add_argument("--limit", type=int, default=14)
    ap.add_argument("--upload", action="store_true", help="upload episode cards to R2 and record them")
    ap.add_argument("--out-dir", default=str(ROOT / "outputs" / "share_cards"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.episodes:
        slugs = args.episodes
        if slugs == ["all"]:
            # Every run_show show with a public page; members-only shows are
            # skipped inside episode_card_for.
            slugs = sorted(s for s in _registry() if (ROOT / "shows" / f"{s}.yaml").is_file())
        total = 0
        for s in slugs:
            try:
                total += build_episodes(s, args.limit, args.upload, Path(args.out_dir))
            except Exception as exc:  # noqa: BLE001 - one show never stops the rest
                print(f"::warning::{s}: episode cards failed: {exc}")
        print(f"{total} episode card(s) {'uploaded' if args.upload else 'rendered'}")
        return 0

    changed = build_committed(check=args.check)
    if args.check:
        if changed:
            print("::warning::share cards are stale — run scripts/build_share_cards.py:\n  "
                  + "\n  ".join(changed))
            return 1
        print("share cards up to date")
        return 0
    print(f"{len(changed)} card(s) written" + (":\n  " + "\n  ".join(changed) if changed else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
