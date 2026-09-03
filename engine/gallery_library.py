"""Render-time reuse of already-generated gallery images + evergreen b-roll.

The network has paid (Grok Imagine credits) for every scene image it has ever
generated — they all live in the public ``nerra-gallery`` R2 bucket and are
indexed by the committed ``site/data/gallery-manifest.json``. This module
lets render-time consumers (Sunday weekly recaps, RU dubs, any show whose
fresh scenes failed to generate) pull *relevant* historical scenes back down
instead of falling back to a static cover — zero new image-generation cost.

Selection is deterministic: candidates are filtered (show / aspect / episode
window / current-episode exclusion), scored by token overlap between the
caller's context text (episode hook, chapter titles) and the image's
``prompt`` + ``caption`` + ``tags``, and tie-broken by recency then
``image_id``. Winners are downloaded into a local cache keyed on
``image_id`` so repeated renders (and the weekly recap re-using a daily's
scenes) never re-fetch bytes.

Everything network-facing is best-effort by contract: a missing manifest, a
dead URL, or a full R2 outage yields fewer (or zero) results — the public
API never raises, matching the gallery-uploader's soft-fail design
(``engine/gallery_uploader.py``).

The evergreen b-roll pool (``select_broll_clips``) is the companion for
*video* clips: a small committed ``broll.json`` per show (written by
``scripts/build_broll_pool.py``) points at curated clips on R2 — e.g. the
recovered Grok Video clips from ``scripts/recover_grok_video.py``. Only the
JSON is committed; the media stays on R2 (landmine #1).
"""

from __future__ import annotations

import json
import logging
import re
import tempfile
import zlib
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import requests

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = PROJECT_ROOT / "site" / "data" / "gallery-manifest.json"

DOWNLOAD_TIMEOUT_SECONDS = 20

# Abort library blending after this many consecutive download failures.
# Without a breaker, a run where every fetch fails (Tesla Ep537 — at the
# time read as a "CDN outage", later understood to be the originals gate
# doing its job before the code knew originals were private) walks every
# historical candidate (~150+ HTTP round-trips) and still returns zero
# paths. Fail fast; the caller already degrades to fresh-only scenes.
_MAX_CONSECUTIVE_DOWNLOAD_FAILURES = 5

# After the public CDN 403s once in-process, skip it for the rest of the
# run and go straight to authenticated R2. Ep537 paid ~8× public-403
# round-trips before each successful R2 fallback; once we know the CDN
# is rejecting GHA egress, further public GETs are pure waste.
_prefer_r2_download = False

# Aspect → the manifest's ``intended_use`` value (see gallery_uploader):
# ``segment_card`` is the 16:9 long-form scene, ``social`` the 9:16 Short.
_ASPECT_TO_USE = {"16:9": "segment_card", "9:16": "social"}

# Words too common in Grok Imagine prompts / hooks to signal relevance —
# without this every "photo, dramatic lighting" boilerplate token matches.
_STOPWORDS = frozenset(
    "a an and are as at be by for from has have in is it its of on or that "
    "the this to was were will with photo image style lighting composition "
    "detailed ultra framing depicting no text words rendered".split()
)

# Local-cache path → manifest entry, populated at download time so
# ``scene_context_map`` can resolve paths even without the manifest.
_PATH_REGISTRY: Dict[Path, dict] = {}


# ---------------------------------------------------------------------------
# Manifest loading + selection
# ---------------------------------------------------------------------------


def load_manifest(path: Optional[Path] = None) -> dict:
    """Load the gallery manifest; ``{}`` on any failure (missing/corrupt)."""
    p = Path(path) if path else DEFAULT_MANIFEST
    if not p.exists():
        # Legitimately absent in unconfigured environments — quiet no-op.
        logger.info("gallery_library: no manifest at %s", p)
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — corrupt = empty library
        # A manifest that EXISTS but does not parse silently no-ops the
        # entire library blend (scene_library_count: 0 on every episode) —
        # e.g. the Jul 16 2026 incident where a `git pull --autostash`
        # conflict committed `<<<<<<<` markers into the JSON. Be loud.
        logger.warning(
            "gallery_library: manifest at %s exists but is UNREADABLE (%s) "
            "— library blend will ship zero scenes", p, exc)
        return {}
    return data if isinstance(data, dict) else {}


def _tokenize(text: str) -> frozenset:
    return frozenset(
        t for t in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(t) > 2 and t not in _STOPWORDS
    )


def _entry_tokens(entry: dict) -> frozenset:
    parts = [entry.get("prompt", ""), entry.get("caption", ""),
             entry.get("episode_title", "")]
    parts.extend(entry.get("tags") or [])
    return _tokenize(" ".join(str(p) for p in parts))


# Sep 3 2026: a token that appears in more than this share of a show's
# candidate images says nothing about WHICH image fits today's story.
# Measured on the committed manifest: "tesla", "optimus", "cybercab",
# "fsd", "robotaxi" and the style boilerplate ("cinematic",
# "photojournalism", ...) sit in 95-100% of Tesla's 436 library scenes,
# so ``min_overlap=1`` matched EVERY image and the blend kept padding a
# Solar-Roof episode with a pier full of Model S (Ep592, twice). Overlap
# is now counted on SALIENT tokens only — the ones that distinguish one
# story from another.
_COMMON_TOKEN_DF = 0.20
_COMMON_TOKEN_MIN_ENTRIES = 5


def _common_tokens(entries: List[dict]) -> frozenset:
    """Tokens present in more than ``_COMMON_TOKEN_DF`` of *entries*.

    Empty for tiny candidate sets (a handful of images is not a
    document-frequency estimate), so small libraries keep the legacy
    whole-token overlap.
    """
    n = len(entries)
    if n < _COMMON_TOKEN_MIN_ENTRIES:
        return frozenset()
    counts: Dict[str, int] = {}
    for e in entries:
        for t in _entry_tokens(e):
            counts[t] = counts.get(t, 0) + 1
    cutoff = _COMMON_TOKEN_DF * n
    return frozenset(t for t, c in counts.items() if c > cutoff)


def _candidate_entries(
    manifest: dict,
    show_slug: str,
    *,
    intended_use: str,
    exclude_episode_id: Optional[str],
    min_episode_date: Optional[str],
    max_episode_date: Optional[str],
) -> List[dict]:
    out = []
    for entry in manifest.get("images", []) or []:
        if entry.get("show_slug") != show_slug:
            continue
        if entry.get("intended_use") != intended_use:
            continue
        if not entry.get("original_url"):
            continue
        eid = (entry.get("episode_id") or "").lower()
        if exclude_episode_id and eid == exclude_episode_id.lower():
            continue
        # ISO date strings compare correctly lexicographically.
        date = entry.get("episode_date") or ""
        if min_episode_date and date < min_episode_date:
            continue
        if max_episode_date and date > max_episode_date:
            continue
        out.append(entry)
    return out


_RETENTION_PRIOR_PATH = Path(__file__).resolve().parent.parent / "api" / "gallery_retention.json"
_RETENTION_PRIOR_CACHE: dict = {}


def _retention_tag_scores(show_slug: str) -> dict:
    """Per-tag mean-retention map for one show, from the nightly
    ``api/gallery_retention.json`` flywheel report.

    July 31 2026: the flywheel had been a DEAD END — the report was built
    nightly since June and consumed only by a dashboard card, while scene
    ranking stayed pure token-overlap + recency. This closes the loop:
    tags that measurably held viewers get a bounded ranking nudge.
    Fail-open: missing file/show → {} → ranking identical to legacy.
    Cached per process (the manifest loader already sets that precedent).
    """
    if show_slug in _RETENTION_PRIOR_CACHE:
        return _RETENTION_PRIOR_CACHE[show_slug]
    scores: dict = {}
    try:
        import json as _json
        data = _json.loads(_RETENTION_PRIOR_PATH.read_text(encoding="utf-8"))
        summary = ((data.get("shows") or {}).get(show_slug) or {}).get(
            "summary") or {}
        rows = list(summary.get("top_tags") or []) + list(
            summary.get("bottom_tags") or [])
        vals = [float(r.get("mean_retention") or 0.0) for r in rows]
        if rows and vals:
            mid = sorted(vals)[len(vals) // 2]
            for r in rows:
                tag = str(r.get("tag") or "").strip().lower()
                if tag:
                    scores[tag] = float(r.get("mean_retention") or 0.0) - mid
    except Exception:  # noqa: BLE001 — the prior is a nudge, never a gate
        scores = {}
    _RETENTION_PRIOR_CACHE[show_slug] = scores
    return scores


def _retention_score(entry: dict, tag_scores: dict) -> float:
    """Mean centered-retention of the entry's known tags, clipped to
    ±10 points so the prior can shuffle near-ties but never outrank a
    real context-overlap difference (overlap stays the primary key)."""
    if not tag_scores:
        return 0.0
    vals = [tag_scores[t] for t in
            (str(x).strip().lower() for x in entry.get("tags") or [])
            if t in tag_scores]
    if not vals:
        return 0.0
    return max(-10.0, min(10.0, sum(vals) / len(vals)))


def _rank(entries: List[dict], context_text: str,
          show_slug: str = "",
          common: Optional[frozenset] = None) -> List[dict]:
    """Deterministic best-first ordering.

    Primary: SALIENT token overlap with the context (*common* tokens —
    ``_common_tokens`` — are removed from both sides first, so the
    show's own brand words cannot manufacture a match). Secondary (July 31 2026):
    the bounded retention prior — among equal-overlap candidates, images
    whose tags historically held viewers rank first. Ties after that:
    newer ``episode_date`` first, then ``image_id`` — so identical inputs
    always yield identical output regardless of manifest document order.
    Implemented as stable sorts (least- to most-significant key);
    Python's sort is stable even with ``reverse=True``.
    """
    common = common or frozenset()
    ctx = _tokenize(context_text) - common
    tag_scores = _retention_tag_scores(show_slug) if show_slug else {}
    ranked = sorted(entries, key=lambda e: e.get("image_id") or "")
    ranked.sort(key=lambda e: e.get("episode_date") or "", reverse=True)
    if tag_scores:
        ranked.sort(key=lambda e: _retention_score(e, tag_scores),
                    reverse=True)
    if ctx:
        ranked.sort(key=lambda e: len(ctx & (_entry_tokens(e) - common)),
                    reverse=True)
    return ranked


def _default_cache_dir() -> Path:
    return Path(tempfile.gettempdir()) / "gallery_cache"


def _cache_filename(entry: dict) -> str:
    url = entry["original_url"]
    basename = url.rstrip("/").rsplit("/", 1)[-1]
    ext = Path(basename).suffix or ".jpg"
    stem = entry.get("image_id") or Path(basename).stem
    return f"{stem}{ext}"


# The gallery custom domain's WAF rule (Cloudflare zone nerranetwork.com,
# rule "Gallery originals private (403 except .thumb.webp/.json)"):
#   (http.host eq "gallery.nerranetwork.com" and not
#    (ends_with(http.request.uri.path, ".thumb.webp") or
#     ends_with(http.request.uri.path, ".json")))  → Block
# That 403 is the Phase-3 email gate WORKING, not an outage — originals
# are only reachable via the Worker's cookie-gated /api/download (or CI's
# authenticated R2 credentials). See workers/gallery/README.md and
# docs/gallery_storage.md before concluding anything from a gallery 403.
_GALLERY_GATE_HOST = "gallery.nerranetwork.com"
_GALLERY_PUBLIC_SUFFIXES = (".thumb.webp", ".json")


def is_public_media_url(url: str) -> bool:
    """False for a URL no plain unauthenticated GET can read. Two shapes:

    * An S3-API endpoint URL: ``upload_to_r2`` returns the raw
      ``https://<account>.r2.cloudflarestorage.com/<bucket>/<key>``
      endpoint when ``R2_GALLERY_PUBLIC_BASE_URL`` is unset — that
      address requires SigV4 signing, so an unauthenticated GET is
      answered 400, not 403.
    * A gallery ORIGINAL: everything on ``gallery.nerranetwork.com``
      except ``.thumb.webp`` / ``.json`` is 403'd by the zone's WAF rule
      BY DESIGN (the email-gated download funnel — see the rule quoted
      above). The 2026-08-18 near-miss: that 403 was misread as a CDN
      outage and the "fix" on the table was deleting the rule, i.e.
      publishing all ~5.5k originals for free.

    Recognising both lets callers go straight to the authenticated path
    instead of spending a doomed request per object.
    """
    u = (url or "").lower()
    if ".r2.cloudflarestorage.com" in u:
        return False
    try:
        from urllib.parse import urlparse
        parsed = urlparse(u)
    except Exception:  # noqa: BLE001 — unparseable ≈ nothing to special-case
        return True
    if parsed.netloc == _GALLERY_GATE_HOST and not parsed.path.endswith(
            _GALLERY_PUBLIC_SUFFIXES):
        return False
    return True


def _r2_object_key(entry: dict) -> Optional[str]:
    """R2 object key for an authenticated get.

    Prefers an explicit key — ``original_key`` on gallery manifest
    entries, ``key`` on b-roll pool entries — and only then derives one
    from the URL path.
    """
    for field in ("original_key", "key"):
        key = (entry.get(field) or "").strip().lstrip("/")
        if key:
            return key
    url = (entry.get("original_url") or entry.get("url") or "").strip()
    if not url:
        return None
    # https://gallery.nerranetwork.com/tesla/2026-07-08/ep535/abc.jpeg
    # → tesla/2026-07-08/ep535/abc.jpeg
    try:
        from urllib.parse import urlparse
        path = urlparse(url).path.lstrip("/")
        if not path:
            return None
        # An S3-endpoint URL puts the BUCKET in the path
        # (/nerra-gallery/broll/…), but the bucket is passed separately
        # to the client — leaving it in would look up a key that does
        # not exist. (Deliberately NOT is_public_media_url() here: gallery
        # originals are also non-public but their custom-domain path is
        # already the bare object key.)
        if ".r2.cloudflarestorage.com" in url.lower():
            try:
                from engine.gallery_uploader import gallery_config_from_env
                bucket = (gallery_config_from_env().bucket or "").strip("/")
            except Exception:  # noqa: BLE001
                bucket = ""
            if bucket and path.startswith(f"{bucket}/"):
                path = path[len(bucket) + 1:]
        return path or None
    except Exception:  # noqa: BLE001
        return None


def _download_via_r2(entry: dict, dest: Path) -> bool:
    """Authenticated R2 download when the public CDN rejects the GET.

    Reuses the same gallery-bucket credentials the uploader already has
    in CI (``R2_GALLERY_BUCKET`` + shared R2 account keys). Returns True
    on a successful write; False on any miss/misconfig/error (caller
    treats it as another soft failure).
    """
    key = _r2_object_key(entry)
    if not key:
        return False
    try:
        from engine.gallery_uploader import gallery_config_from_env
        cfg = gallery_config_from_env()
        if not cfg.is_configured:
            return False
        import boto3
        from botocore.config import Config as BotoConfig
        s3 = boto3.client(
            "s3",
            endpoint_url=cfg.endpoint_url,
            aws_access_key_id=cfg.access_key,
            aws_secret_access_key=cfg.secret_key,
            config=BotoConfig(
                signature_version="s3v4",
                retries={"max_attempts": 2, "mode": "standard"},
            ),
        )
        s3.download_file(cfg.bucket, key, str(dest))
        return dest.exists() and dest.stat().st_size > 0
    except Exception as exc:  # noqa: BLE001 — soft fallback
        logger.warning(
            "gallery_library: R2 fallback failed for key=%s: %s", key, exc,
        )
        dest.unlink(missing_ok=True)
        return False


def _download_entry(
    entry: dict, cache_dir: Path,
    failures: Optional[List[str]] = None,
) -> Optional[Path]:
    """Fetch one image into the cache (or reuse); None on failure.

    PRIVATE urls (gallery originals behind the WAF gate, S3-endpoint
    urls) go straight to authenticated R2 — the public CDN is not an
    option for them and a 403 there is by design, not a failure (the
    "Ep537 blanket 403" this code originally treated as an outage was
    exactly that gate). Public shapes try the CDN first (fast path),
    fall back to R2 on failure, and flip ``_prefer_r2_download`` after
    the first 401/403 so the rest of the run skips the doomed requests.

    When ``failures`` is given, a short human-readable reason is appended
    on each failed fetch so the caller can report WHY the blend degraded.
    """
    global _prefer_r2_download
    dest = cache_dir / _cache_filename(entry)
    if dest.exists() and dest.stat().st_size > 0:
        _PATH_REGISTRY[dest] = entry
        return dest

    # Gallery ORIGINALS are private BY DESIGN (the WAF email gate — see
    # is_public_media_url). Go straight to authenticated R2: no doomed
    # public round-trip, no loud CDN warning (nothing is wrong), and the
    # run-wide _prefer_r2_download flip stays untouched so genuinely
    # public shapes keep using the CDN fast path.
    if not is_public_media_url(entry.get("original_url") or ""):
        if _download_via_r2(entry, dest):
            _PATH_REGISTRY[dest] = entry
            return dest
        if failures is not None:
            r2_state = ("authenticated R2 fetch failed" if _r2_configured()
                        else "R2 credentials unset")
            failures.append(
                f"private original (gated by design, no public route): "
                f"{r2_state}")
        logger.warning(
            "gallery_library: R2 fetch failed for private original %s "
            "(the public CDN is not an option for originals — WAF gate)",
            entry.get("image_id") or dest.name,
        )
        return None

    if _prefer_r2_download and _download_via_r2(entry, dest):
        _PATH_REGISTRY[dest] = entry
        return dest

    public_err: Optional[Exception] = None
    try:
        resp = requests.get(entry["original_url"],
                            timeout=DOWNLOAD_TIMEOUT_SECONDS)
        resp.raise_for_status()
        if not resp.content:
            raise ValueError("empty response body")
        dest.write_bytes(resp.content)
    except Exception as exc:  # noqa: BLE001 — try R2 before giving up
        public_err = exc
        dest.unlink(missing_ok=True)
        # Flip to R2-first for the rest of this process once the public
        # CDN rejects us (403/401/etc.) — don't keep paying the round-trip.
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (401, 403) or "403" in str(exc) or "401" in str(exc):
            # Announce the FIRST flip loudly. Before July 28 2026 this
            # degradation was only visible as an INFO line per image
            # ("R2 fallback OK"), so a CDN that had been rejecting every
            # public GET for weeks looked like a healthy pipeline —
            # renders just silently paid the slower authenticated path up
            # to 16 times each. RESCOPED 2026-08-18: private originals
            # never reach this path any more (they are 403'd by design —
            # the WAF email gate), so this warning now fires only when a
            # URL that is SUPPOSED to be public goes dark — the real
            # regression signal. It very nearly talked an operator into
            # deleting the gate rule when it fired on originals.
            if not _prefer_r2_download:
                print(
                    "::warning::gallery CDN rejected a PUBLIC-shape read "
                    f"(HTTP {status or 'error'}) — falling back to "
                    "authenticated R2 for the rest of this run. Public "
                    "shapes are .thumb.webp/.json (originals are gated by "
                    "design and never fetched publicly) — if this fired, "
                    "a public shape went dark: check the custom-domain / "
                    "WAF config, but do NOT touch the originals gate rule.",
                    flush=True,
                )
                logger.warning(
                    "gallery_library: public CDN unavailable (%s) — every "
                    "library image this run pays the R2 fallback", public_err,
                )
            _prefer_r2_download = True
        if _download_via_r2(entry, dest):
            logger.info(
                "gallery_library: public CDN failed (%s); R2 fallback OK "
                "for %s", public_err, entry.get("image_id") or dest.name,
            )
            _PATH_REGISTRY[dest] = entry
            return dest
        if failures is not None:
            r2_state = ("R2 fallback also failed" if _r2_configured()
                        else "R2 fallback unavailable (credentials unset)")
            failures.append(f"public CDN: {public_err}; {r2_state}")
        logger.warning(
            "gallery_library: failed to fetch %s: %s",
            entry.get("original_url"), public_err,
        )
        return None
    _PATH_REGISTRY[dest] = entry
    return dest


def _r2_configured() -> bool:
    """Whether the authenticated-R2 fallback has credentials to work with."""
    try:
        from engine.gallery_uploader import gallery_config_from_env
        return bool(gallery_config_from_env().is_configured)
    except Exception:  # noqa: BLE001
        return False


def select_library_scenes(
    show_slug: str,
    *,
    aspect: str,
    exclude_episode_id: Optional[str] = None,
    context_text: str = "",
    limit: int = 8,
    manifest: Optional[dict] = None,
    cache_dir: Optional[Path] = None,
    min_episode_date: Optional[str] = None,
    max_episode_date: Optional[str] = None,
    min_overlap: int = 0,
) -> List[Path]:
    """Pick + download the show's most relevant already-generated scenes.

    ``min_overlap`` (Sep 2026): when > 0 and ``context_text`` is
    non-empty, candidates sharing fewer than that many tokens with the
    context are DROPPED rather than ranked last — the blend used to pad
    a slideshow with off-topic older images whenever nothing relevant
    existed, which read as random pictures over the narration.

    ``aspect`` is ``"16:9"`` (long-form ``segment_card`` images) or
    ``"9:16"`` (Shorts ``social`` images). Candidates from the current
    episode (``exclude_episode_id``) and outside the optional
    ``[min_episode_date, max_episode_date]`` ISO-date window are dropped;
    the rest are ranked by ``context_text`` token overlap against each
    image's prompt/caption/tags with recency as the tiebreak.

    Downloads are cached by ``image_id`` under ``cache_dir`` (default:
    ``gallery_cache/`` in the system temp dir). Failed downloads are
    skipped and the next-best candidate backfills, so the return is
    best-first local Paths, up to ``limit``. A streak of consecutive
    failures aborts early (CDN/R2 outage circuit breaker). Never raises.
    """
    try:
        use = _ASPECT_TO_USE.get(aspect)
        if use is None:
            logger.warning("gallery_library: unknown aspect %r "
                           "(want 16:9 or 9:16)", aspect)
            return []
        data = manifest if manifest is not None else load_manifest()
        entries = _candidate_entries(
            data, show_slug, intended_use=use,
            exclude_episode_id=exclude_episode_id,
            min_episode_date=min_episode_date,
            max_episode_date=max_episode_date)
        if not entries or limit <= 0:
            return []
        cdir = Path(cache_dir) if cache_dir else _default_cache_dir()
        cdir.mkdir(parents=True, exist_ok=True)
        paths: List[Path] = []
        failures: List[str] = []
        consecutive_failures = 0
        common = _common_tokens(entries)
        ctx_tokens = (
            (_tokenize(context_text) - common) if min_overlap > 0 else frozenset()
        )
        for entry in _rank(entries, context_text, show_slug, common=common):
            if len(paths) >= limit:
                break
            if ctx_tokens and len(
                ctx_tokens & (_entry_tokens(entry) - common)
            ) < min_overlap:
                continue   # off-topic — a repeat of a relevant image beats it
            if consecutive_failures >= _MAX_CONSECUTIVE_DOWNLOAD_FAILURES:
                logger.warning(
                    "gallery_library: aborting after %d consecutive "
                    "download failures for %s (CDN/R2 likely unavailable) "
                    "— returning %d of %d requested",
                    consecutive_failures, show_slug, len(paths), limit,
                )
                break
            p = _download_entry(entry, cdir, failures=failures)
            if p is not None:
                paths.append(p)
                consecutive_failures = 0
            else:
                consecutive_failures += 1
        if not paths and failures:
            # The blend selected candidates but shipped ZERO of them — the
            # exact silent-no-op shape that hid the CDN-403 defect for a
            # week (scene_library_count: 0, Jul 2026). One loud line with
            # the first concrete failure reason so run logs always show it.
            logger.warning(
                "gallery_library: BLEND DEGRADED for %s (%s): selected %d "
                "candidate scene(s), downloaded 0 — first failure: %s",
                show_slug, aspect, len(entries), failures[0],
            )
        return paths
    except Exception as exc:  # noqa: BLE001 — library reuse is optional
        logger.warning("gallery_library: scene selection failed for %s: %s",
                       show_slug, exc)
        return []


def collect_week_scenes(
    show_slug: str,
    *,
    aspect: str,
    end_date: str,
    days: int = 7,
    exclude_episode_id: Optional[str] = None,
    manifest: Optional[dict] = None,
    cache_dir: Optional[Path] = None,
    limit: int = 24,
) -> List[Path]:
    """Scenes from the ``days`` ending at ``end_date`` (ISO), newest first.

    The weekly-recap variant of :func:`select_library_scenes`: no context
    scoring — with an empty context the ranking degrades to pure recency,
    which is exactly the "this week's imagery in order" a recap wants.
    """
    try:
        import datetime as _dt
        end = _dt.date.fromisoformat(str(end_date)[:10])
        start = end - _dt.timedelta(days=max(0, days - 1))
    except Exception as exc:  # noqa: BLE001
        logger.warning("gallery_library: bad end_date %r: %s", end_date, exc)
        return []
    return select_library_scenes(
        show_slug,
        aspect=aspect,
        exclude_episode_id=exclude_episode_id,
        context_text="",
        limit=limit,
        manifest=manifest,
        cache_dir=cache_dir,
        min_episode_date=start.isoformat(),
        max_episode_date=end.isoformat(),
    )


def scene_context_map(manifest: dict, paths: Iterable[Path]) -> Dict[Path, str]:
    """Map each local scene Path back to its ``prompt`` + ``caption`` text.

    This is the shape the scene scheduler consumes (``scene_context:
    dict[Path, str]``). Resolution is two-layer: the in-process registry
    written at download time (exact), then a manifest lookup by the
    filename stem (cache files are named by ``image_id``, so a warm cache
    from an earlier process still resolves). Unknown paths map to ``""``.
    """
    by_id: Dict[str, dict] = {}
    try:
        for entry in (manifest or {}).get("images", []) or []:
            iid = entry.get("image_id")
            if iid:
                by_id.setdefault(iid, entry)
    except Exception as exc:  # noqa: BLE001
        logger.warning("gallery_library: bad manifest in scene_context_map: %s",
                       exc)
    out: Dict[Path, str] = {}
    for p in paths:
        p = Path(p)
        entry = _PATH_REGISTRY.get(p) or by_id.get(p.stem) or {}
        parts = [str(entry.get("prompt") or "").strip(),
                 str(entry.get("caption") or "").strip()]
        out[p] = "\n".join(part for part in parts if part)
    return out


# ---------------------------------------------------------------------------
# Evergreen b-roll clips
# ---------------------------------------------------------------------------


def load_broll_entries(digests_dir: Path) -> List[dict]:
    """Entries from ``<digests_dir>/broll.json`` in committed order.

    Accepts both the builder's wrapped form (``{"clips": [...]}``) and a
    bare list. Missing/corrupt file → ``[]``.
    """
    path = Path(digests_dir) / "broll.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("gallery_library: broll.json unreadable at %s: %s",
                       path, exc)
        return []
    clips = data.get("clips") if isinstance(data, dict) else data
    if not isinstance(clips, list):
        return []
    return [c for c in clips if isinstance(c, dict) and c.get("url")]


def broll_attributions_for(
    clip_paths: Optional[Sequence] = None,
    *,
    digests_dir: Path,
) -> List[str]:
    """Footage credit lines for the b-roll clips a render actually used.

    Matches the local cached Paths (whose file names are the pool URL
    basenames — see ``select_broll_clips``) back to ``broll.json``
    entries and returns their ``attribution`` strings, deduped, in pool
    order. CC BY-sourced clips (SpaceX YouTube back-catalog) make this
    load-bearing: the license requires the credit wherever the footage
    ships. Entries without an attribution (e.g. the recovered Grok Video
    clips — network-owned) contribute nothing. Never raises.
    """
    try:
        if not clip_paths:
            return []
        used = {Path(p).name for p in clip_paths}
        out: List[str] = []
        for entry in load_broll_entries(Path(digests_dir)):
            name = str(entry.get("url", "")).rstrip("/").rsplit("/", 1)[-1]
            credit = str(entry.get("attribution") or "").strip()
            if name in used and credit and credit not in out:
                out.append(credit)
        return out
    except Exception as exc:  # noqa: BLE001 — credits must never block
        logger.warning("gallery_library: b-roll attribution lookup "
                       "failed: %s", exc)
        return []


# Auto-cut clips are named "<source stem>__MMmSSs", so the source a clip
# came from can be recovered from its label even for pools published
# before ``source`` was recorded explicitly.
_CUT_STAMP_RE = re.compile(r"_+\d+m\d+s$")


def broll_source_key(entry: dict) -> str:
    """Which source video a pool clip was cut from.

    Prefers the explicit ``source`` field; falls back to stripping the
    auto-cut timestamp suffix off the label so pools published before
    that field existed still group correctly; finally the url, which
    makes every clip its own group (i.e. no grouping).
    """
    explicit = str(entry.get("source") or "").strip()
    if explicit:
        return explicit
    label = str(entry.get("label") or "").strip()
    if label:
        return _CUT_STAMP_RE.sub("", label) or label
    return str(entry.get("url") or "")


def interleave_by_source(entries: List[dict]) -> List[dict]:
    """Round-robin the pool across source videos.

    Auto-cutting yields runs of clips from one source, so a contiguous
    slice of the pool was three moments from the SAME launch — same
    rocket, same pad, same light. Measured on the first real pool: 5 of
    7 consecutive episodes drew all three clips from one source.
    Round-robining means each episode's slice spans different launches
    while the operator's relative ordering within a source is kept.
    """
    groups: Dict[str, List[dict]] = {}
    for entry in entries:
        groups.setdefault(broll_source_key(entry), []).append(entry)
    if len(groups) < 2:
        return list(entries)
    # Proportional spread, not naive round-robin: with unequal group
    # sizes (one launch yielding 10 clips and the others 5) round-robin
    # exhausts the small groups first and leaves a long single-source
    # tail — exactly the clustering this is meant to remove. Placing
    # each clip at its fractional position within its own group spreads
    # the big group evenly across the whole pool instead.
    placed = [
        ((i + 0.5) / len(group), key, entry)
        for key, group in groups.items()
        for i, entry in enumerate(group)
    ]
    placed.sort(key=lambda t: (t[0], t[1]))
    return [entry for _pos, _key, entry in placed]


def rotate_for_episode(entries: List[dict], episode_seed: Optional[str],
                       limit: int, *, stride: Optional[int] = None) -> List[dict]:
    """Rotate a pool so consecutive episodes draw different clips.

    The pool was consumed in fixed committed order, so EVERY episode of
    a show got the same first ``limit`` clips no matter how large the
    pool grew — the daily long-forms shared one identical set of
    accents. Rotating by a stable hash of the episode id walks the whole
    pool across successive episodes while staying deterministic (a
    re-run of the same episode renders the same video, which the
    idempotent-publish path depends on).

    Order within the returned slice is preserved from the pool, so the
    operator's curation still decides sequencing.
    """
    if not entries:
        return []
    if not episode_seed:
        return entries[:limit]
    # Spread each episode's slice across sources before rotating (the
    # no-seed path above keeps the exact committed order).
    entries = interleave_by_source(entries)
    seed = str(episode_seed)
    # Stride by the episode NUMBER when the seed carries one ("…ep053"),
    # so consecutive episodes get DISJOINT slices and the pool is walked
    # in order. A plain hash of the whole seed collides often enough to
    # repeat a set every few days (measured: 7 distinct sets across 10
    # episodes of a 12-clip pool), which is the very thing this exists
    # to prevent. The non-numeric part still feeds the offset so two
    # shows don't march in lockstep.
    digits = re.findall(r"\d+", seed)
    show_part = re.sub(r"\d+", "", seed)
    show_offset = zlib.crc32(show_part.encode("utf-8"))
    # The per-episode step. ``stride`` exists because a caller that wants
    # the FULL rotated pool back (select_broll_clips, so a failed
    # download can backfill from the remainder) passes limit=len(entries)
    # — and with the step derived from that limit, index * len % len == 0
    # cancelled the episode number entirely. Production shipped the SAME
    # clips on every episode from Ep055 until this fix while the direct
    # unit tests (which pass the slice width as limit) stayed green. The
    # stride must be the SLICE WIDTH the consumer will take, never the
    # pool size.
    step = int(stride) if stride else max(1, limit)
    if digits:
        index = int(digits[-1])
        offset = (index * max(1, step) + show_offset) % len(entries)
    else:
        offset = show_offset % len(entries)
    rotated = entries[offset:] + entries[:offset]
    return rotated[:limit]


def select_broll_clips(
    show_slug: str,
    *,
    digests_dir: Path,
    limit: int = 3,
    cache_dir: Optional[Path] = None,
    episode_seed: Optional[str] = None,
) -> List[Path]:
    """Download up to ``limit`` curated evergreen clips for a show.

    Reads the committed ``broll.json`` pool (see
    ``scripts/build_broll_pool.py``). With an ``episode_seed`` the pool
    is rotated per episode (see :func:`rotate_for_episode`) so a growing
    pool actually produces varied videos; without one the legacy
    committed order is preserved exactly.

    Best-effort: a failed download is skipped (the next entry backfills);
    a missing pool file is a clean ``[]``. Never raises.
    """
    try:
        entries = load_broll_entries(Path(digests_dir))
        if not entries or limit <= 0:
            return []
        # Rotate first, then walk — so a download failure inside the
        # rotated slice backfills from the rest of the pool. The stride
        # is the CALLER's slice width (see rotate_for_episode: deriving
        # it from this full-pool limit cancelled the rotation and shipped
        # identical clips every episode).
        entries = rotate_for_episode(entries, episode_seed, len(entries),
                                     stride=limit)
        cdir = (Path(cache_dir) if cache_dir
                else _default_cache_dir() / "broll" / show_slug)
        cdir.mkdir(parents=True, exist_ok=True)
        paths: List[Path] = []
        for entry in entries:
            if len(paths) >= limit:
                break
            url = str(entry["url"])
            dest = cdir / (url.rstrip("/").rsplit("/", 1)[-1] or "clip.mp4")
            if dest.exists() and dest.stat().st_size > 0:
                paths.append(dest)
                continue
            # Same public-then-authenticated ladder the image path uses.
            # Ep054 shipped with broll=0 because this did a bare GET
            # against an S3-endpoint URL and took all 25 400s as "no
            # clips available" — while the images beside it recovered
            # through R2 on the very same run.
            if not is_public_media_url(url) or _prefer_r2_download:
                if _download_via_r2(entry, dest):
                    paths.append(dest)
                    continue
                # A PRIVATE url has no public route to fall through to —
                # an S3-endpoint GET answers 400 and a gated gallery path
                # answers 403 either way. Report honestly and move on
                # rather than spending the doomed round-trip.
                if not is_public_media_url(url):
                    logger.warning(
                        "gallery_library: R2 fetch failed for private "
                        "b-roll %s (%s; no public route exists for it)",
                        dest.name,
                        "R2 error" if _r2_configured()
                        else "R2 credentials unset")
                    continue
            public_err: Optional[Exception] = None
            try:
                resp = requests.get(url, timeout=DOWNLOAD_TIMEOUT_SECONDS)
                resp.raise_for_status()
                if not resp.content:
                    raise ValueError("empty response body")
                dest.write_bytes(resp.content)
                paths.append(dest)
                continue
            except Exception as exc:  # noqa: BLE001 — try R2 before giving up
                public_err = exc
                dest.unlink(missing_ok=True)
            if _download_via_r2(entry, dest):
                logger.info("gallery_library: b-roll public fetch failed "
                            "(%s); R2 fallback OK for %s",
                            public_err, dest.name)
                paths.append(dest)
                continue
            logger.warning(
                "gallery_library: failed to fetch b-roll %s: %s (%s)",
                url, public_err,
                "R2 fallback also failed" if _r2_configured()
                else "R2 fallback unavailable (credentials unset)")
        if entries and not paths:
            # Every clip failed. Silent-empty here reads downstream as
            # "the operator published no pool", which is a different
            # thing and hid a whole-pool outage for a full episode.
            print("::warning::b-roll pool for "
                  f"{show_slug} has {len(entries)} clip(s) but NONE could be "
                  "fetched — the episode renders on stills only. Check R2 "
                  "credentials and the pool's URLs.", flush=True)
        return paths
    except Exception as exc:  # noqa: BLE001 — b-roll is optional garnish
        logger.warning("gallery_library: b-roll selection failed for %s: %s",
                       show_slug, exc)
        return []
