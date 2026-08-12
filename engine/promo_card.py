"""Site-showcase promo cards for video endings (Aug 2026, operator-directed).

The operator asked for the end of every Short and long-form video to
actually SHOW nerranetwork.com — the show's page and the whole-network
page — so viewers see there is a site with every show, transcripts and
free newsletters behind the channel, instead of just hearing a URL.

Two products, both composited from COMMITTED screenshots of the live
site (``assets/site_screens/`` — refreshed by
``scripts/capture_site_screens.py``, never fetched at render time):

* :func:`generate_outro_card` — a 1920×1080 PNG the long-form render
  overlays across its closing seconds (``engine.video`` fades it in the
  same way the Shorts end card works). Framed screenshots of the show
  page + the network home page, a localized headline, the URL in Nerra
  cyan, and (when the ``qrcode`` package is available) a scannable QR
  to the funnel-tagged show page.
* :func:`short_site_panel` — the crop of the network home page's show
  grid that ``engine.publisher.generate_shorts_end_card`` pastes into
  the lower band of the Shorts end card, so even a 3-second end card
  flashes the "wall of shows" the site opens with.

Contract: pure best-effort. Missing screenshots, a missing qrcode
package, or any PIL failure returns ``None`` / skips the element — the
video ships exactly as it does today. Nothing here touches audio
(render/metadata only, outside the landmine-#17 A/B gate), and every
link handed to callers must already be funnel-tagged — links are built
by ``engine.funnel`` (PLACEMENT_OUTRO), never here.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCREENS_DIR = PROJECT_ROOT / "assets" / "site_screens"

# All crops below are expressed against this reference width; any
# committed screenshot is normalized to it first, so a future recapture
# at a different resolution cannot silently shift the crops.
_REF_WIDTH = 1280

NERRA_CYAN = (0, 212, 255)
_BG = (11, 15, 26)          # --nn-bg, same as the Shorts end card
_TEXT = (232, 236, 244)
_MUTED = (139, 143, 174)


def _texts(channel: str) -> Dict[str, str]:
    """Localized outro-card copy. Unknown channels read English."""
    token = (channel or "en").strip().lower()
    if token == "ru":
        return {
            "headline": "ВСЯ СЕТЬ NERRA — НА ОДНОМ САЙТЕ",
            "sub": "Все шоу · расшифровки · бесплатные рассылки",
            "scan": "Наведите камеру",
        }
    if token == "fr":
        return {
            "headline": "DÉCOUVREZ TOUT LE RÉSEAU",
            "sub": "Toutes les émissions · transcriptions · newsletters gratuites",
            "scan": "Scannez pour en savoir plus",
        }
    return {
        "headline": "KEEP EXPLORING THE NETWORK",
        "sub": "All 16 shows · transcripts · free newsletters",
        "scan": "Scan for this show",
    }


def site_screenshot_for(show_slug: str, channel: str = "en") -> Optional[Path]:
    """The best committed screenshot for one show on one channel.

    Priority: a channel-specific lander (``ru_spacex.png`` — the RU
    funnel page exists precisely to convert that audience) → the show's
    English page (``show_<slug>.png``) → ``None``. Callers fall back to
    :func:`network_screenshot` themselves, so a show without its own
    page card still gets the network showcase.
    """
    slug = (show_slug or "").strip().lower()
    if not slug:
        return None
    token = (channel or "en").strip().lower()
    candidates = []
    if token and token != "en":
        candidates.append(SCREENS_DIR / f"{token}_{slug}.png")
    candidates.append(SCREENS_DIR / f"show_{slug}.png")
    for path in candidates:
        if path.exists():
            return path
    return None


def network_screenshot() -> Optional[Path]:
    path = SCREENS_DIR / "network_home.png"
    return path if path.exists() else None


def _load_font(size: int):
    from engine.publisher import _load_font as loader
    return loader(size)


def _normalized(path: Path):
    """Open a screenshot and scale it to the reference width."""
    from PIL import Image

    im = Image.open(path).convert("RGB")
    if im.width != _REF_WIDTH:
        im = im.resize(
            (_REF_WIDTH, int(round(im.height * _REF_WIDTH / im.width))),
            Image.LANCZOS,
        )
    return im


def _framed_crop(path: Path, crop_box, target_w: int, target_h: int):
    """Crop a normalized screenshot and scale it to the card slot."""
    from PIL import Image

    im = _normalized(path)
    left, top, right, bottom = crop_box
    bottom = min(bottom, im.height)
    im = im.crop((left, top, right, bottom))
    return im.resize((target_w, target_h), Image.LANCZOS)


def _paste_framed(card, im, x: int, y: int, frame: int = 4) -> None:
    from PIL import ImageDraw

    card.paste(im, (x, y))
    ImageDraw.Draw(card).rectangle(
        (x - frame, y - frame, x + im.width + frame, y + im.height + frame),
        outline=(255, 255, 255), width=frame,
    )


def _qr_image(link_url: str, size: int = 200):
    """Best-effort QR render; ``None`` when qrcode isn't installed."""
    try:
        import qrcode
        from PIL import Image
    except ImportError:
        return None
    try:
        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(link_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        return img.convert("RGB").resize((size, size), Image.NEAREST)
    except Exception as exc:  # noqa: BLE001 — the card ships without a QR
        logger.warning("promo card: QR render failed (%s)", exc)
        return None


def generate_outro_card(
    output_path: Path,
    *,
    show_slug: str,
    show_name: str = "",
    channel: str = "en",
    link_url: str = "",
    size: tuple = (1920, 1080),
) -> Optional[Path]:
    """Render the long-form outro card PNG. ``None`` = ship no outro.

    ``link_url`` must arrive already funnel-tagged (built by
    ``engine.funnel.episode_link`` with ``PLACEMENT_OUTRO``) — this
    module only draws it into the QR; it never builds campaign URLs.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        logger.warning("promo card: PIL unavailable — no outro card")
        return None

    show_shot = site_screenshot_for(show_slug, channel)
    net_shot = network_screenshot()
    if show_shot is None and net_shot is None:
        logger.info(
            "promo card: no committed site screenshots — no outro card "
            "(run scripts/capture_site_screens.py to enable)")
        return None

    width, height = size
    t = _texts(channel)
    card = Image.new("RGB", (width, height), _BG)
    draw = ImageDraw.Draw(card)

    # Headline across the top.
    head_font = _load_font(66)
    head = t["headline"]
    hw = head_font.getbbox(head)[2]
    if hw > width - 160:  # long localized headline — shrink once
        head_font = _load_font(52)
        hw = head_font.getbbox(head)[2]
    draw.text(((width - hw) // 2 + 3, 63), head, font=head_font, fill=(0, 0, 0))
    draw.text(((width - hw) // 2, 60), head, font=head_font, fill=_TEXT)

    # Framed screenshots. Two-up when both exist; one centered otherwise.
    # Crop the top 992px of the 1280-wide page (nav + hero + the start of
    # the show grid / episode list) — the part that reads as "a real
    # website" at TV distance.
    slot_h = 600
    crop = (0, 0, _REF_WIDTH, 992)
    shots = [s for s in (show_shot, net_shot) if s is not None]
    try:
        if len(shots) == 2:
            slot_w = 776  # 776/600 ≈ 1280/992
            gap = 80
            x0 = (width - (2 * slot_w + gap)) // 2
            for i, shot in enumerate(shots):
                im = _framed_crop(shot, crop, slot_w, slot_h)
                _paste_framed(card, im, x0 + i * (slot_w + gap), 190)
        else:
            slot_w = 776
            im = _framed_crop(shots[0], crop, slot_w, slot_h)
            _paste_framed(card, im, (width - slot_w) // 2, 190)
    except Exception as exc:  # noqa: BLE001 — screenshots are the card
        logger.warning("promo card: screenshot composite failed (%s)", exc)
        return None

    # URL in Nerra cyan + localized sub-line.
    url_font = _load_font(72)
    url_text = "nerranetwork.com"
    uw = url_font.getbbox(url_text)[2]
    draw.text(((width - uw) // 2 + 3, 873), url_text, font=url_font,
              fill=(0, 0, 0))
    draw.text(((width - uw) // 2, 870), url_text, font=url_font,
              fill=NERRA_CYAN)

    sub_font = _load_font(40)
    sub = t["sub"]
    sw = sub_font.getbbox(sub)[2]
    draw.text(((width - sw) // 2, 985), sub, font=sub_font, fill=_MUTED)

    # QR to the funnel-tagged show link, bottom-right (long-form is
    # watched on TVs/desktops where a phone-scan is the natural bridge).
    # Geometry (Aug 2026 fix): the old 200 px block at y=760 overlapped
    # the right screenshot's framed bottom corner (screenshots end at
    # y≈794), and the localized scan label was centred on the QR's own
    # 200 px width — the French label is 413 px wide and rendered 46 px
    # off the right edge of the frame.
    if link_url:
        qsize = 180
        qr = _qr_image(link_url, size=qsize)
        if qr is not None:
            qx, qy = width - qsize - 60, 840  # clears the shots at y≈794
            card.paste(qr, (qx, qy))
            scan_font = _load_font(26)
            scan = t["scan"]
            scw = scan_font.getbbox(scan)[2]
            sx = qx + (qsize - scw) // 2
            # Clamp inside the frame — long localized labels shift left
            # rather than clipping off-screen.
            sx = max(20, min(sx, width - 40 - scw))
            draw.text((sx, qy + qsize + 10), scan,
                      font=scan_font, fill=_MUTED)

    card.save(output_path, format="PNG", optimize=True)
    return Path(output_path)


def short_site_panel(show_slug: str = "", channel: str = "en") -> Optional[Path]:
    """The screenshot the Shorts end card should paste as its site strip.

    The network home page's show grid is the panel by default — the
    Shorts ask is "see the whole network", and sixteen cover tiles in a
    row communicate that faster than any one show page. A channel
    lander (``ru_<slug>``) wins when it exists, because that page was
    built to convert exactly this audience.
    """
    token = (channel or "en").strip().lower()
    if token and token != "en" and show_slug:
        lander = SCREENS_DIR / f"{token}_{(show_slug or '').strip().lower()}.png"
        if lander.exists():
            return lander
    return network_screenshot()


def render_short_site_strip(
    source: Path,
    target_w: int,
    target_h: int,
):
    """Crop the show-grid band out of a screenshot for the Shorts card.

    Returns a PIL image sized ``target_w × target_h`` or raises — the
    caller (``generate_shorts_end_card``) wraps this in its own
    best-effort handling. For the network home page the band at
    y 540–940 (reference width) is the cover-tile wall; for a lander it
    is the hero + subscribe block, which still reads as "a real page".
    """
    band = (0, 540, _REF_WIDTH, 940)
    return _framed_crop(source, band, target_w, target_h)
