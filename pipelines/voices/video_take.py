"""The guest's camera, recorded in the browser (Oct 28 2026).

Patrick wants the interviews on video: YouTube, X and the episode's page.
The Voximplant video recorder had been running on every room since
September, and it was no use for that: Glenn Broder's hour came back as
1080p VP8 at about 16 kbps, with 502 gaps of more than two seconds and most
frames unreadable. So the studio page records the guest's camera itself,
the way it records their microphone (``age-of-ai-studio.html`` section 4b):
720p at 2.5 Mbps with the microphone alongside, in five-second chunks that
stream to the Worker's video lane::

    <prefix>/local/<run>/guest-video/<sid>/00000.webm ... manifest.json

and every finished take is listed on the run row under
``grok_session_log.local_video_takes.guest`` (the audio take's pointer,
``local_guest_url``, is never touched by a video take).

This module turns those takes into files on R2 and works out where each one
sits on the guest leg's clock — the clock the transcript, the EDL and the
edit's ``room → edit`` table all use. The picture is never moved: the take's
own microphone is correlated against the guest's processed track and the
result is stored as ``pieces`` (``video_t = leg_t - delay`` inside
``[from, to)``, in the take's own seconds), which is exactly what
``local_tracks.room_pieces`` measures for an audio leg. The renderer reads
it from ``grok_session_log.tracks.video``.

Everything here is best-effort. No take, or a take that cannot be placed,
means an audio episode, as before.
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

FPS = 30
#: A take shorter than this is a camera that opened and closed again.
MIN_TAKE_SEC = 5.0
#: A placed take must correlate at least this well on its best stretch.
MIN_AGREEMENT = 0.45


def _run(cmd: list, timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run([str(c) for c in cmd], check=True, capture_output=True,
                          text=True, timeout=timeout)


def _duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 0.0


def has_video_frames(path: Path) -> bool:
    """True when the file decodes at least one video frame (the Voximplant
    recordings of Oct 27-28 had a video stream and no packets in it)."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                          "-count_packets", "-show_entries", "stream=nb_read_packets",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return int((out.stdout.strip().splitlines() or ["0"])[0]) > 0
    except ValueError:
        return False


def video_takes(run: dict, role: str = "guest") -> List[dict]:
    """The finished video takes listed on the run, oldest first."""
    log = (run or {}).get("grok_session_log") or {}
    takes = ((log.get("local_video_takes") or {}).get(role)) or []
    good = [t for t in takes if isinstance(t, dict) and t.get("manifest")
            and int(t.get("chunks") or 0) > 0]
    return sorted(good, key=lambda t: str(t.get("started_at") or ""))


_CHUNK_RE = re.compile(r"^(\d{5})\.(webm|mp4)$")


def discover_takes(keys: List[str], read_json: Callable[[str], Any], *,
                   put_json: Optional[Callable[[str, Any], None]] = None) -> List[dict]:
    """The camera takes in R2 under ``<prefix>/local/<run>/guest-video/``,
    for a run whose row lists none.

    Oct 28 2026 (the second test room): the page finished its audio take and
    its camera take at the same moment, both upload-dones rewrote the run's
    log, and the camera take's listing was lost with all 42 chunks safely in
    R2. The Worker appends atomically now; this is the backstop, and it also
    adopts a take whose page never sent upload-done (chunks, no manifest),
    writing the manifest it would have written when ``put_json`` is given."""
    manifests: Dict[str, str] = {}
    chunks: Dict[str, List[Tuple[int, str]]] = {}
    for key in keys or []:
        parts = str(key).split("/")
        if len(parts) < 3:
            continue
        sid, name = parts[-2], parts[-1]
        if name == "manifest.json":
            manifests[sid] = key
            continue
        m = _CHUNK_RE.match(name)
        if m:
            chunks.setdefault(sid, []).append((int(m.group(1)), key))
    takes: List[dict] = []
    for sid in sorted(set(manifests) | set(chunks)):
        if sid in manifests:
            try:
                man = read_json(manifests[sid]) or {}
            except Exception:  # noqa: BLE001 — an unreadable manifest is no take
                continue
            takes.append({"manifest": manifests[sid], "sid": sid, "mime": man.get("mime") or "",
                          "started_at": man.get("started_at"),
                          "duration_ms": man.get("duration_ms") or 0,
                          "chunks": len(man.get("chunks") or []),
                          "missing": len(man.get("missing") or []),
                          "bytes": man.get("bytes"), "discovered": True})
            continue
        if put_json is None:
            continue
        numbered = sorted(chunks[sid])
        have = {n for n, _k in numbered}
        first = numbered[0][1]
        folder, ext = first.rsplit("/", 1)[0], first.rsplit(".", 1)[1]
        # Every expected chunk is listed and the absent ones are named, as the
        # Worker's own manifest does, so usable_chunks stops at the first gap.
        expected = [f"{folder}/{i:05d}.{ext}" for i in range(max(have) + 1)]
        key = folder + "/manifest.json"
        manifest = {"sid": sid, "kind": "video",
                    "mime": "video/mp4" if ext == "mp4" else "video/webm",
                    "started_at": None, "duration_ms": 0, "chunks": expected,
                    "missing": [k for i, k in enumerate(expected) if i not in have],
                    "adopted": "no upload-done from the page; built from the chunks in R2"}
        try:
            put_json(key, manifest)
        except Exception:  # noqa: BLE001
            logger.warning("video take %s: could not write the adopted manifest", sid)
            continue
        takes.append({"manifest": key, "sid": sid, "mime": manifest["mime"], "started_at": None,
                      "duration_ms": 0, "chunks": len(expected),
                      "missing": len(manifest["missing"]), "discovered": True, "adopted": True})
    return takes


def usable_chunks(manifest: Optional[dict]) -> List[str]:
    """The chunk keys that can be decoded: all of them, or, when one went
    missing, everything before the first gap. A chunk is a byte range of one
    stream, so nothing after a hole can be read (local_tracks says the same
    of the audio take)."""
    if not isinstance(manifest, dict):
        return []
    chunks = list(manifest.get("chunks") or [])
    missing = set(manifest.get("missing") or [])
    out: List[str] = []
    for key in chunks:
        if key in missing:
            break
        out.append(key)
    return out


def _default_read_json(key: str) -> Optional[dict]:
    from common import r2_read_json
    return r2_read_json(key)


def _default_download(key: str, dest: Path) -> Path:
    from common import r2_download
    return r2_download(key, dest)


def assemble_take(manifest_key: str, workdir: Path, *,
                  read_json: Optional[Callable[[str], Any]] = None,
                  download: Optional[Callable[[str, Path], Path]] = None,
                  ) -> Optional[Path]:
    """Manifest → one playable file (``take.mkv`` for WebM, ``take.mp4`` for
    Safari's MP4), or ``None``. The chunks are joined byte for byte and
    remuxed so the file carries a duration and clean timestamps."""
    read_json = read_json or _default_read_json
    download = download or _default_download
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        manifest = read_json(manifest_key)
    except Exception as exc:  # noqa: BLE001 — an unreadable take is no take
        logger.warning("video take %s: manifest unreadable (%s)", manifest_key, exc)
        return None
    keys = usable_chunks(manifest)
    if not keys:
        logger.info("video take %s: no usable chunks", manifest_key)
        return None
    if len(keys) < len((manifest or {}).get("chunks") or []):
        logger.warning("video take %s: using the first %d of %d chunks (a chunk "
                       "went missing)", manifest_key, len(keys),
                       len(manifest.get("chunks") or []))
    mp4 = str(manifest.get("mime") or "").lower().startswith("video/mp4")
    ext = "mp4" if mp4 else "webm"
    joined = workdir / f"joined.{ext}"
    try:
        with joined.open("wb") as out:
            for i, key in enumerate(keys):
                part = download(key, workdir / f"chunk_{i:05d}.{ext}")
                out.write(Path(part).read_bytes())
                Path(part).unlink(missing_ok=True)
        take = workdir / ("take.mp4" if mp4 else "take.mkv")
        _run(["ffmpeg", "-y", "-v", "error", "-fflags", "+genpts", "-i", joined,
              "-map", "0", "-c", "copy", take])
    except Exception as exc:  # noqa: BLE001 — never block post-production
        logger.warning("video take %s: could not be assembled (%s)", manifest_key, exc)
        return None
    if _duration(take) < MIN_TAKE_SEC or not has_video_frames(take):
        logger.info("video take %s: too short or no picture", manifest_key)
        return None
    return take


def take_audio(take: Path, out_wav: Path) -> Optional[Path]:
    """The take's own microphone, the reference it is placed by."""
    try:
        _run(["ffmpeg", "-y", "-v", "error", "-i", take, "-vn", "-ar", 48000,
              "-ac", 1, "-c:a", "pcm_s16le", out_wav])
    except Exception as exc:  # noqa: BLE001
        logger.warning("video take %s has no usable audio (%s)", take.name, exc)
        return None
    return out_wav if out_wav.exists() and out_wav.stat().st_size > 1000 else None


def place_take(take_wav: Path, reference_wav: Path, workdir: Path
               ) -> Optional[Dict[str, Any]]:
    """Where the take sits on the reference's (the guest leg's) clock:
    ``{"pieces": [{"from", "to", "delay", ...}], "delay_sec", "agreement"}``
    with ``leg_t = video_t + delay`` inside each piece, or ``None``."""
    from audio.local_tracks import room_pieces, whole_file_delay
    workdir = Path(workdir)
    expected, strength = whole_file_delay(take_wav, reference_wav, workdir)
    pieces = room_pieces(take_wav, reference_wav, workdir, expected=expected)
    pieces = [p for p in pieces if float(p.get("agreement") or 0.0) >= MIN_AGREEMENT
              or int(p.get("windows") or 0) >= 2]
    if not pieces:
        logger.warning("video take %s could not be placed (whole-file %+.2fs, "
                       "corr %.2f)", Path(take_wav).name, expected, strength)
        return None
    best = max(pieces, key=lambda p: float(p["to"]) - float(p["from"]))
    return {"pieces": pieces, "delay_sec": float(best["delay"]),
            "agreement": float(best.get("agreement") or 0.0)}


def video_time(takes: List[dict], leg_t: float) -> Optional[Tuple[int, float]]:
    """``(take index, seconds into that take)`` showing moment ``leg_t`` of
    the guest leg, or ``None`` when no take covers it. A later take wins
    (a rejoin replaces the picture from the moment it starts)."""
    for i in range(len(takes) - 1, -1, -1):
        for piece in takes[i].get("pieces") or []:
            vt = float(leg_t) - float(piece["delay"])
            if float(piece["from"]) <= vt < float(piece["to"]):
                return i, vt
    return None


def build_video_track(run: dict, reference_wav: Path, workdir: Path, *,
                      upload: Callable[[Path, str], str],
                      key_for: Callable[[str], str],
                      read_json: Optional[Callable[[str], Any]] = None,
                      download: Optional[Callable[[str, Path], Path]] = None,
                      discover: Optional[Callable[[], List[dict]]] = None,
                      ) -> Optional[Dict[str, Any]]:
    """Every usable take of the guest's camera, on R2 and placed on the
    guest leg's clock: ``{"fps", "takes": [{"url", "sid", "duration_sec",
    "pieces", "delay_sec", "agreement"}]}``, or ``None``.

    ``key_for(name)`` returns the R2 key a file called ``name`` goes to;
    ``upload(path, key)`` puts it there and returns its public URL."""
    takes = video_takes(run)
    if not takes and discover is not None:
        try:
            takes = sorted(discover() or [], key=lambda t: str(t.get("started_at") or ""))
        except Exception:  # noqa: BLE001 — no listing and no R2 means no video
            logger.exception("video takes could not be discovered in R2 (non-fatal)")
            takes = []
        if takes:
            logger.info("video: %d take(s) found in R2 that the run row did not list", len(takes))
    if not takes:
        return None
    placed: List[dict] = []
    for i, take in enumerate(takes):
        sub = Path(workdir) / f"video_take_{i}"
        try:
            path = assemble_take(take["manifest"], sub, read_json=read_json,
                                 download=download)
            if path is None:
                continue
            wav = take_audio(path, sub / "take_audio.wav")
            if wav is None:
                continue
            where = place_take(wav, reference_wav, sub / "align")
            if where is None:
                continue
            sid = str(take.get("sid") or i)
            url = upload(path, key_for(f"guest_video_{sid}{path.suffix}"))
            placed.append({"url": url, "sid": sid, "duration_sec": round(_duration(path), 2),
                           "mime": take.get("mime") or "", **where})
            logger.info("video take %s: %.0fs, placed at %+.2fs (corr %.2f)",
                        sid, placed[-1]["duration_sec"], where["delay_sec"],
                        where["agreement"])
        except Exception:  # noqa: BLE001 — the audio episode is the product
            logger.exception("video take %s failed (non-fatal)", take.get("manifest"))
    if not placed:
        return None
    return {"fps": FPS, "takes": placed}
