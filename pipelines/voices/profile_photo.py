#!/usr/bin/env python3
"""The guest's public profile photo, for their episode page (Oct 25 2026).

Patrick asked that every application name at least one public profile (an X
account, a LinkedIn profile, or the guest's page on their company's site) and
that the episode post carry the photo from it beside the links. This finds
that photo, makes a square JPEG of it, keeps it on the network's own R2 (a
profile picture URL on someone else's CDN changes or expires; LinkedIn's
carry an expiry in the URL itself) and records it on the application:

    guest_applications.profile_photo_url     the copy on R2
    guest_applications.profile_photo_source  the page it came from

Where it looks, best likeness first:

1. LinkedIn: the page's og:image, the same field a link preview reads, used
   only when it is the person's own display photo. LinkedIn often refuses
   pages to servers, which costs nothing but the try.
2. The company profile page: the image whose alt text or file name carries
   the guest's name (the headshot on a team page), else the page's og:image
   when the page itself is about them.
3. X: the account's picture from the X API (the network's credentials), or
   from unavatar.io when those are not set.

It runs when an application is screened, so Patrick sees the photo in the
assessment email and on the triage page before he approves, and again at
publish when nothing was found earlier. A photo set by hand is never
replaced. Nothing here can stop a screen or a publish.

    python pipelines/voices/profile_photo.py <application id>              # find one if missing
    python pipelines/voices/profile_photo.py <application id> --force      # look again
    python pipelines/voices/profile_photo.py <application id> --url <img>  # use this image
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import logging
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests  # noqa: E402

from common import public_profiles, r2_upload, sb_select, sb_update, x_handle  # noqa: E402

logger = logging.getLogger("nerra.voices.profile_photo")

PHOTO_SIDE = 400          # pixels, square
MIN_SIDE = 96             # anything smaller is an icon, not a photo
MAX_BYTES = 8 * 1024 * 1024
TIMEOUT = 20
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 "
              "(KHTML, like Gecko) Version/18.0 Safari/605.1.15")
_SKIP_IMG = re.compile(r"logo|icon|sprite|favicon|badge|banner|placeholder|avatar-default|\.svg",
                       re.I)
_NAME_NOISE = {"dr", "dr.", "doctor", "prof", "prof.", "mr", "mrs", "ms", "phd", "md", "jr",
               "sr", "ii", "iii"}


def _get(url: str, *, ua: str = BROWSER_UA, accept: str = "") -> Optional[requests.Response]:
    try:
        resp = requests.get(url, timeout=TIMEOUT, allow_redirects=True,
                            headers={"User-Agent": ua,
                                     "Accept": accept or "text/html,application/xhtml+xml,*/*;q=0.8",
                                     "Accept-Language": "en"})
    except requests.RequestException as exc:
        logger.info("photo: %s unreachable (%s)", url, exc)
        return None
    if resp.status_code >= 400:
        logger.info("photo: %s answered %s", url, resp.status_code)
        return None
    return resp


def name_tokens(name: str) -> List[str]:
    """"Dr. Piper Martz, PhD" → ["piper", "martz"]."""
    bare = re.split(r"\s*,\s*", str(name or "").strip())[0]
    words = [w.strip(".'\"()").lower() for w in bare.split()]
    return [w for w in words if w and w not in _NAME_NOISE]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")


def names_person(text: str, name: str) -> bool:
    """Whether ``text`` (alt text, a file name, a page title) names the guest:
    the surname, and the first name too unless the text is very short."""
    tokens = name_tokens(name)
    if not tokens:
        return False
    hay = f"-{_slug(text)}-"
    last, first = tokens[-1], tokens[0]
    if f"-{_slug(last)}-" not in hay:
        return False
    return len(tokens) == 1 or f"-{_slug(first)}-" in hay


def _meta(soup, *keys: str) -> str:
    for key in keys:
        tag = (soup.find("meta", attrs={"property": key})
               or soup.find("meta", attrs={"name": key}))
        if tag and tag.get("content"):
            return str(tag["content"]).strip()
    return ""


def _soup(html: str):
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, "html.parser")


def _img_src(img, base: str) -> str:
    """The largest candidate an <img> offers, absolute."""
    srcset = img.get("srcset") or img.get("data-srcset") or ""
    best, best_w = "", 0
    for part in srcset.split(","):
        bits = part.strip().split()
        if not bits:
            continue
        width = int(re.sub(r"\D", "", bits[1]) or 0) if len(bits) > 1 and bits[1].endswith("w") else 1
        if width >= best_w:
            best, best_w = bits[0], width
    src = best or img.get("data-src") or img.get("data-lazy-src") or img.get("src") or ""
    src = src.strip()
    if not src or src.startswith("data:"):
        return ""
    return urljoin(base, src)


def from_linkedin(url: str, name: str) -> Optional[str]:
    resp = _get(url)
    if resp is None:
        return None
    image = _meta(_soup(resp.text), "og:image", "twitter:image")
    host = urlparse(image).netloc.lower()
    # The display photo lives on media.licdn.com under profile-displayphoto
    # (or the framed variant). Anything else is LinkedIn's own artwork.
    if host.endswith("licdn.com") and re.search(r"profile-(?:display|framed)photo", image):
        return image
    return None


def from_company_page(url: str, name: str) -> Optional[str]:
    resp = _get(url)
    if resp is None or "html" not in resp.headers.get("Content-Type", "html"):
        return None
    soup = _soup(resp.text)
    base = resp.url or url
    for img in soup.find_all("img"):
        src = _img_src(img, base)
        if not src or _SKIP_IMG.search(src):
            continue
        label = " ".join(str(img.get(k) or "") for k in ("alt", "title", "aria-label"))
        filename = urlparse(src).path.rsplit("/", 1)[-1]
        if names_person(label, name) or names_person(filename, name):
            return src
    # A page that is itself about the person: its share image is theirs.
    title = _meta(soup, "og:title", "twitter:title") or (soup.title.string if soup.title else "")
    image = _meta(soup, "og:image", "twitter:image")
    if image and names_person(title or "", name) and not _SKIP_IMG.search(image):
        return urljoin(base, image)
    return None


def from_x(handle: str) -> Optional[str]:
    if not handle:
        return None
    try:
        from engine.x_post import NETWORK_X_ENV_PREFIX, x_credentials
        creds = x_credentials(NETWORK_X_ENV_PREFIX)
    except Exception:  # noqa: BLE001 — the fallback below needs none
        creds = {}
    if creds:
        try:
            import tweepy
            client = tweepy.Client(**creds)
            user = client.get_user(username=handle, user_fields=["profile_image_url"],
                                   user_auth=True)
            image = getattr(getattr(user, "data", None), "profile_image_url", "") or ""
            if image and "default_profile_images" not in image:
                # The API hands back the 48px "_normal" size; the same file
                # exists at 400x400.
                return re.sub(r"_normal(\.\w+)$", r"_400x400\1", image)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.info("photo: X lookup for @%s failed (%s)", handle, exc)
    url = f"https://unavatar.io/x/{handle}?fallback=false"
    resp = _get(url, accept="image/*")
    if resp is not None and resp.headers.get("Content-Type", "").startswith("image/"):
        return url
    return None


def candidates(app: Dict[str, Any]) -> List[Tuple[str, str]]:
    """``[(image_url, source_page)]`` in the order worth trying."""
    profiles = public_profiles(app)
    name = app.get("name") or ""
    found: List[Tuple[str, str]] = []
    steps = (("linkedin", lambda u: from_linkedin(u, name)),
             ("company_profile", lambda u: from_company_page(u, name)),
             ("x", lambda u: from_x(x_handle(app))))
    for key, finder in steps:
        page = profiles.get(key)
        if not page:
            continue
        try:
            image = finder(page)
        except Exception:  # noqa: BLE001 — one odd page must not stop the next
            logger.exception("photo: looking at %s failed", page)
            image = None
        if image:
            found.append((image, page))
    return found


def square_jpeg(data: bytes, side: int = PHOTO_SIDE) -> bytes:
    """A centred square crop (biased up, where faces are), as JPEG."""
    from PIL import Image, ImageOps
    with Image.open(io.BytesIO(data)) as img:
        img = ImageOps.exif_transpose(img)
        if min(img.size) < MIN_SIDE:
            raise ValueError(f"image is {img.size[0]}x{img.size[1]}, too small for a photo")
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            flat = Image.new("RGB", img.size, (255, 255, 255))
            flat.paste(img, mask=img.split()[-1])
            img = flat
        else:
            img = img.convert("RGB")
        w, h = img.size
        crop = min(w, h)
        left = (w - crop) // 2
        top = int((h - crop) * 0.25)
        img = img.crop((left, top, left + crop, top + crop))
        # Never enlarged: a 200px LinkedIn photo stays 200px rather than
        # going soft at 400. The page shows it at 104px.
        target = min(side, crop)
        img = img.resize((target, target), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, "JPEG", quality=86, optimize=True, progressive=True)
        return out.getvalue()


def download_image(url: str) -> bytes:
    resp = _get(url, accept="image/avif,image/webp,image/*;q=0.9,*/*;q=0.5")
    if resp is None:
        raise ValueError(f"could not fetch {url}")
    kind = resp.headers.get("Content-Type", "")
    if not kind.startswith("image/") or "svg" in kind:
        raise ValueError(f"{url} is {kind or 'not an image'}")
    if len(resp.content) > MAX_BYTES:
        raise ValueError(f"{url} is {len(resp.content)} bytes")
    return resp.content


def store_photo(app: Dict[str, Any], *, force: bool = False,
                image_url: str = "") -> Optional[str]:
    """Find, square, upload and record the guest's photo. Returns its URL.

    A photo already on the row stays unless ``force`` or ``image_url``."""
    if app.get("profile_photo_url") and not (force or image_url):
        return app["profile_photo_url"]
    tries = [(image_url, "set by hand")] if image_url else candidates(app)
    for image, source in tries:
        try:
            jpeg = square_jpeg(download_image(image))
        except Exception as exc:  # noqa: BLE001 — try the next source
            logger.info("photo: %s not usable (%s)", image, exc)
            continue
        digest = hashlib.sha256(jpeg).hexdigest()[:10]
        key = f"voices/guests/{app['id']}/photo-{digest}.jpg"
        with tempfile.TemporaryDirectory(prefix="guest_photo_") as tmp:
            local = Path(tmp) / "photo.jpg"
            local.write_bytes(jpeg)
            url = r2_upload(local, key, content_type="image/jpeg")
        sb_update("guest_applications", f"id=eq.{app['id']}", {
            "profile_photo_url": url,
            "profile_photo_source": source,
            "profile_photo_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        })
        app["profile_photo_url"] = url
        app["profile_photo_source"] = source
        logger.info("photo for %s: %s (from %s)", app.get("name"), url, source)
        return url
    logger.info("photo: none found for %s", app.get("name"))
    return None


def ensure_photo(app: Dict[str, Any]) -> Optional[str]:
    """``store_photo`` that never raises: a missing photo costs a picture,
    never a screen or a publish."""
    try:
        return store_photo(app)
    except Exception:  # noqa: BLE001
        logger.exception("photo: could not store one for %s (non-fatal)", app.get("id"))
        return app.get("profile_photo_url") or None


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("application_id")
    parser.add_argument("--force", action="store_true", help="look again even if one is stored")
    parser.add_argument("--url", default="", help="use this image instead of looking")
    args = parser.parse_args(argv[1:])
    rows = sb_select("guest_applications", f"id=eq.{args.application_id}")
    if not rows:
        logger.error("no application %s", args.application_id)
        return 1
    url = store_photo(rows[0], force=args.force, image_url=args.url)
    print(url or "no photo found")
    return 0 if url else 2


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main(sys.argv))
