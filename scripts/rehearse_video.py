#!/usr/bin/env python3
"""Rehearse the video job on an episode that is already published.

Renders exactly what the video job renders (render-video.yml → run_show.py
--video-phase): the Grok Imagine scenes, the long-form, the Shorts, the
thumbnails, the X clip — and publishes NOTHING. Every publishing credential
but R2's is removed from the environment before anything is imported
(YouTube, X, the X queue, Buttondown, the webhook); R2 stays because the
render READS from it (the gallery library's scenes and b-roll), and every S3
call that is not a read is refused at botocore's single API entry point.
Every YouTube write is replaced by a fake that saves the finished file. No feed, blog, X post, commit or
homepage refresh. What it leaves is a folder of MP4s and thumbnails plus a
timing and outcome report, which render-video.yml attaches to the run.

Costs what a real render costs in model calls: the scene briefs, the title
bundle and the Grok Imagine images (about $0.2-0.4 an episode).

    python scripts/rehearse_video.py spacex --date 2026-10-18 --out rehearsal/
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

#: Environment the rehearsal must never see: anything that could publish.
#: GROK_API_KEY (images, scene briefs, titles), PEXELS_API_KEY and the R2
#: credentials (read-only — see block_s3_writes) stay.
DROP_PREFIXES = ("X_", "NERRANETWORK_X_", "PLANETTERRIAN_X_", "YOUTUBE_",
                 "BUTTONDOWN", "PERSONAL_", "INSTAGRAM_", "IG_", "TIKTOK_",
                 "VOICES_SUPABASE", "SHORT_PREVIEW_R2")
DROP_EXACT = ("NOTIFICATION_WEBHOOK_URL", "NERRA_AUDIO_FIRST_PUSH", "NERRA_VIDEO_JOB",
              "GITHUB_TOKEN", "GH_TOKEN")


def scrub_environment(environ=os.environ) -> list:
    dropped = [k for k in list(environ)
               if k.startswith(DROP_PREFIXES) or k in DROP_EXACT]
    for k in dropped:
        environ.pop(k, None)
    return sorted(dropped)


#: The only S3 operations a rehearsal may make.
S3_READ_OPERATIONS = frozenset({"GetObject", "HeadObject", "ListObjects", "ListObjectsV2",
                                "HeadBucket", "GetBucketLocation"})


def block_s3_writes() -> list:
    """Refuse every S3 operation but a read, at botocore's one API entry
    point (upload_file, put_object and multipart uploads all pass through
    it). Returns the list the refused operation names are appended to."""
    import botocore.client
    from botocore.exceptions import ClientError

    blocked: list = []
    original = botocore.client.BaseClient._make_api_call

    def guarded(self, operation_name, api_params):
        if operation_name not in S3_READ_OPERATIONS:
            blocked.append(operation_name)
            raise ClientError({"Error": {"Code": "RehearsalReadOnly",
                                         "Message": "rehearsal: writes are refused"}},
                              operation_name)
        return original(self, operation_name, api_params)

    botocore.client.BaseClient._make_api_call = guarded
    return blocked


def refuse_r2_uploads() -> list:
    """Make engine.storage.upload_to_r2 — the one R2 upload helper — refuse
    at once (returns "", the helper's own failure value). Behind the botocore
    guard; without this every refused upload spent ~8 s in the helper's
    retries, which inflated a rehearsal's video-stage time by 5-7 minutes
    (Oct 18 2026 rehearsal: 39-54 refused uploads per flagship). Install it
    before anything imports the helper by name."""
    import engine.storage as storage

    refused: list = []

    def refuse(local_path, remote_key, **_kw):
        refused.append(str(remote_key))
        return ""

    storage.upload_to_r2 = refuse
    return refused


ROOT = Path(__file__).resolve().parent.parent


def published_handoff(config, digests_dir: Path, day: dt.date) -> dict:
    """The handoff the audio job would have written, rebuilt from what it
    committed: the digest for *day* and its summaries record."""
    stamp = f"{day:%Y%m%d}"
    pat = re.compile(rf"^{re.escape(config.episode.prefix)}_Ep(\d+)_{stamp}\.md$")
    matches = [(int(m.group(1)), p) for p in digests_dir.glob(f"*_{stamp}.md")
               if (m := pat.match(p.name))]
    if not matches:
        raise SystemExit(f"No {config.slug} digest dated {day} in {digests_dir}")
    episode_num, digest_md = max(matches)
    from engine.summaries_io import load_summaries
    _wrapper, records = load_summaries(ROOT / config.publishing.summaries_json)
    record = next((r for r in records
                   if str(r.get("episode_num")) == str(episode_num)), None)
    audio_url = str((record or {}).get("audio_url") or "")
    if not audio_url:
        raise SystemExit(f"No published audio URL for {config.slug} Ep{episode_num}")
    return {"episode_num": episode_num, "digest_md": digest_md.name,
            "mp3": audio_url.rsplit("/", 1)[-1], "audio_url": audio_url,
            "date": day.isoformat()}


class FakeYouTube:
    """Stands in for every engine.youtube write; keeps what would have gone up."""

    def __init__(self, out_dir: Path):
        self.out = out_dir
        self.uploads: list = []

    def upload_video(self, video_path, *, title="", thumbnail_path=None,
                     publish_at=None, **_kw):
        from engine.youtube import UploadResult
        n = len(self.uploads) + 1
        src = Path(video_path)
        dst = self.out / f"{n:02d}_{src.name}"
        shutil.copy2(src, dst)
        thumb = ""
        if thumbnail_path and Path(thumbnail_path).exists():
            tdst = self.out / f"{n:02d}_{Path(thumbnail_path).name}"
            shutil.copy2(thumbnail_path, tdst)
            thumb = tdst.name
        self.uploads.append({"file": dst.name, "title": title, "thumbnail": thumb,
                             "publish_at": publish_at.isoformat() if publish_at else "",
                             **probe(dst)})
        vid = f"REHEARSAL{n:02d}"
        return UploadResult(video_id=vid, watch_url=f"https://www.youtube.com/watch?v={vid}")

    def install(self, module) -> None:
        module.get_channel_credentials_from_env = lambda *a, **k: object()
        module.upload_video = self.upload_video
        module.add_video_to_playlist = lambda *a, **k: True
        module.update_video_title = lambda *a, **k: True
        module.post_video_comment = lambda *a, **k: "rehearsal-comment"
        module.video_has_comment = lambda *a, **k: False
        module.upload_caption_track = lambda *a, **k: True
        module.upload_caption_track_detailed = lambda *a, **k: (True, "rehearsal")


def probe(path: Path) -> dict:
    """Duration, size and frame size of a rendered file (ffprobe)."""
    out = {"bytes": path.stat().st_size}
    try:
        res = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height:format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=60)
        data = json.loads(res.stdout or "{}")
        stream = (data.get("streams") or [{}])[0]
        out.update(width=stream.get("width"), height=stream.get("height"),
                   duration_s=round(float((data.get("format") or {}).get("duration") or 0), 1))
    except Exception:  # noqa: BLE001 — the report says what it could read
        pass
    return out


REPORT_KEYS = (
    "youtube_publish_duration_s", "long_form_render_duration_s", "long_form_render_need_s",
    "long_form_skipped_budget", "long_form_render_budget_s", "youtube_long_form_uploaded",
    "youtube_short_uploaded", "shorts_count_requested", "shorts_count_uploaded",
    "yt_policy_tier", "yt_policy_long_skipped", "yt_policy_shorts", "visual_mode",
    "scene_fresh_count", "scene_library_count", "grok_images_generated",
    "grok_image_cost_usd", "grok_image_px_max", "grok_slideshow_degraded",
    "shorts_fill_modes", "shorts_caption_mode", "youtube_title", "thumbnail_punch_text",
    "short_previews_uploaded", "x_long_url", "render_look_version",
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("show")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default today, UTC)")
    parser.add_argument("--out", default="rehearsal")
    args = parser.parse_args(argv)

    dropped = scrub_environment()
    blocked_writes = block_s3_writes()
    sys.path.insert(0, str(ROOT))
    refused_uploads = refuse_r2_uploads()
    import run_show  # noqa: E402 — after the scrub, so nothing reads a credential
    from engine import youtube as _youtube
    from engine.config import load_config
    from engine.metrics import PipelineMetrics
    from engine.tracking import create_tracker

    day = dt.date.fromisoformat(args.date) if args.date else dt.datetime.now(
        dt.timezone.utc).date()
    out_dir = Path(args.out).resolve() / args.show
    out_dir.mkdir(parents=True, exist_ok=True)
    fake = FakeYouTube(out_dir)
    fake.install(_youtube)

    config = load_config(ROOT / "shows" / f"{args.show}.yaml")
    digests_dir = ROOT / config.episode.output_dir
    handoff = published_handoff(config, digests_dir, day)
    episode_num = handoff["episode_num"]
    digest_md = digests_dir / handoff["digest_md"]
    x_thread = digest_md.read_text(encoding="utf-8")
    final_mp3 = digests_dir / handoff["mp3"]
    t_fetch = time.monotonic()
    if not final_mp3.exists():
        run_show._fetch_episode_mp3(handoff["audio_url"], final_mp3)
    fetch_s = round(time.monotonic() - t_fetch, 1)
    hook = run_show._extract_hook(x_thread) if hasattr(run_show, "_extract_hook") else ""
    metrics = PipelineMetrics(show_slug=config.slug, episode_num=episode_num)
    tracker = create_tracker(config.name, episode_num)
    ns = argparse.Namespace(show=args.show, test=False, dry_run=False, rehearse=False,
                            skip_youtube=False, skip_x=True, skip_newsletter=True,
                            skip_podcast=False, resume_publish=False,
                            resume_youtube=False, video_phase=True, date=day.isoformat(),
                            force_video=False)

    def _noop(*_a, **_k):
        return None

    t0 = time.monotonic()
    error = ""
    try:
        run_show._run_video_stage(
            args=ns, config=config, metrics=metrics, tracker=tracker,
            digests_dir=digests_dir, episode_num=episode_num, extra_context={},
            final_mp3=final_mp3, hook=hook or None, r2_audio_url=handoff["audio_url"],
            summaries_json=out_dir / "summaries_scratch.json",
            today=day, today_str=day.strftime("%B %d, %Y"), x_thread=x_thread,
            _write_blog_post=_noop, _write_rss_feed=_noop,
        )
    except BaseException as exc:  # noqa: BLE001 — the report records it
        error = f"{type(exc).__name__}: {exc}"
    stage_s = round(time.monotonic() - t0, 1)

    c = metrics.counters
    report = {
        "show": config.slug, "episode_num": episode_num, "date": day.isoformat(),
        "mp3_fetch_s": fetch_s, "video_stage_s": stage_s, "error": error,
        "credentials_removed": dropped,
        "s3_writes_refused": blocked_writes,
        "r2_uploads_refused": refused_uploads,
        "image_cost_usd": round(float(c.get("grok_image_cost_usd") or 0.0), 3),
        "metrics": {k: c[k] for k in REPORT_KEYS if k in c},
        "videos": fake.uploads,
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, default=str))
    lines = [f"## {config.name} Ep{episode_num} ({day})", "",
             f"- video stage: {stage_s / 60:.1f} min (MP3 fetch {fetch_s} s)",
             f"- error: {error or 'none'}",
             f"- publishing: nothing ({len(refused_uploads)} R2 uploads and"
             f" {len(blocked_writes)} other S3 writes refused,"
             f" {len(fake.uploads)} YouTube uploads kept as files)",
             f"- long-form rendered: {bool(c.get('youtube_long_form_uploaded'))}"
             f" (render {c.get('long_form_render_duration_s', '—')} s,"
             f" need {c.get('long_form_render_need_s', '—')} s)",
             f"- Shorts: {c.get('shorts_count_uploaded', 0)} of"
             f" {c.get('shorts_count_requested', 0)} (tier {c.get('yt_policy_tier', '—')})",
             f"- scenes: {c.get('grok_images_generated', 0)} fresh images"
             f" (${report['image_cost_usd']}), visual mode {c.get('visual_mode', '—')}",
             "", "| file | duration | size | frame | title |", "|---|---|---|---|---|"]
    for v in fake.uploads:
        lines.append(f"| {v['file']} | {v.get('duration_s', '—')} s |"
                     f" {v['bytes'] / 1e6:.1f} MB | {v.get('width')}x{v.get('height')} |"
                     f" {v['title']} |")
    (out_dir / "report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    final_mp3.unlink(missing_ok=True)
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
