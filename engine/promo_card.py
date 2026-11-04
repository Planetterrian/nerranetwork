"""Brand promo cards for video endings (Aug 2026; rendered from DATA since Nov 3 2026).

The operator asked for the end of every Short and long-form video to point
viewers at nerranetwork.com — the whole network behind the channel — instead
of just hearing a URL.

Until Nov 3 2026 both products composited COMMITTED screenshots of the live
site (``assets/site_screens/``). One capture, on Aug 9, was the only one that
ever ran: every long-form's last six seconds and every Short's end-card strip
showed the Aug 9 homepage — a no-advertising promise, a four-language list
and a show count ten short — for 86 days, through the Oct 18 retirement of
that promise on every free surface (the sponsor guard sweeps text; a PNG
escapes it). The capture workflow's Nov 1 run was green and committed
nothing. A picture of the site ages; the site's own data does not, so the
cards render from it now:

* :func:`generate_outro_card` — a 1920×1080 PNG the long-form render
  overlays across its closing seconds. This show's cover framed in its brand
  colour on the left, a wall of the other free shows' covers on the right
  (``generate_html._public_shows`` in display order, the flagships first),
  the network tagline from ``engine.brand`` as the headline (RU/FR by
  channel), the free-show count on the sub-line, the URL in Nerra cyan and
  (when the ``qrcode`` package is available) a QR to the funnel-tagged show
  page.
* :func:`short_site_panel` — a 832×260 strip of show covers written to a
  temp PNG, which ``engine.publisher.generate_shorts_end_card`` pastes into
  the lower band of the Shorts end card (the "wall of shows" the site opens
  with), so even a 3-second end card flashes the breadth of the network.

Contract: pure best-effort. A missing cover, a missing qrcode package or any
PIL failure skips the element — a card is returned whenever PIL can draw
one; only a missing PIL ships no card. Nothing here touches audio
(render/metadata only, outside the landmine-#17 A/B gate), every string a
viewer reads comes from ``engine.brand`` or ``generate_html``, and every
link handed to callers must already be funnel-tagged — links are built by
``engine.funnel`` (PLACEMENT_OUTRO), never here.
"""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

NERRA_CYAN = (0, 212, 255)
_BG = (11, 15, 26)          # --nn-bg, same as the Shorts end card
_TEXT = (232, 236, 244)
_MUTED = (139, 143, 174)

#: The Shorts end-card strip's canvas. ``engine.publisher.generate_shorts_end_card``
#: pastes the panel at exactly this size (it resizes anything else to it).
SHORT_STRIP_SIZE = (832, 260)
#: Two rows of seven covers fill the strip.
STRIP_COLS, STRIP_ROWS = 7, 2
#: The outro card's wall of OTHER shows: four columns, three rows.
WALL_COLS, WALL_ROWS = 4, 3

# Per-process cache of rendered strips (one Short run renders several
# Shorts; the strip is the same picture for all of them).
_STRIP_CACHE: Dict[str, Path] = {}


def _texts(channel: str) -> Dict[str, str]:
    """Localized outro-card copy. Unknown channels read English.

    The headline is the network tagline from ``engine.brand`` in the
    channel's language — the card never types its own sentence.
    """
    from engine.brand import network_tagline_for

    token = (channel or "en").strip().lower()
    if token == "ru":
        return {
            "headline": network_tagline_for("ru"),
            "sub": "Все шоу · расшифровки · бесплатные рассылки",
            "scan": "Наведите камеру",
        }
    if token == "fr":
        return {
            "headline": network_tagline_for("fr"),
            "sub": "Toutes les émissions · transcriptions · newsletters gratuites",
            "scan": "Scannez pour en savoir plus",
        }
    count = free_show_count()
    shows = f"All {count} free shows" if count else "Every show"
    return {
        "headline": network_tagline_for("en"),
        "sub": f"{shows} · transcripts · free newsletters",
        "scan": "Scan for this show",
    }


def free_show_count() -> int:
    """The network's free-show count, from the one filter the site uses.

    Oct 18 2026: the card said "All 16 shows" on every long-form while the
    network had 26 free shows. ``generate_html._public_shows`` owns the
    number (homepage, meta description, share card); ``0`` when it cannot
    be read, and the card then names no number.
    """
    try:
        from generate_html import _public_show_count_cached

        return int(_public_show_count_cached())
    except Exception:  # noqa: BLE001 — the outro card is best-effort
        return 0


def show_wall(exclude_slug: str = "") -> List[Dict[str, str]]:
    """The free shows a card may picture, in the order the site shows them.

    Rows of ``{"slug", "name", "cover", "brand_color"}`` from
    ``generate_html._public_shows`` (the one free-show filter: public access
    and a feed — a members-only desk is never on a card that says "free"),
    sorted by the registry's display order with
    ``engine.brand.FLAGSHIP_SHOW_SLUGS`` first, ``exclude_slug`` left out.
    ``[]`` when the registry cannot be read; a show without a cover path is
    skipped.
    """
    try:
        from engine.brand import FLAGSHIP_SHOW_SLUGS
        from generate_html import _public_shows

        shows = _public_shows()
    except Exception as exc:  # noqa: BLE001 — the card is best-effort
        logger.warning("promo card: show registry unreadable (%s)", exc)
        return []
    exclude = (exclude_slug or "").strip().lower()
    rows = []
    for s in shows:
        slug = str(s.get("slug") or "").strip().lower()
        cover = str(s.get("podcast_image") or "").strip()
        if not slug or not cover or slug == exclude:
            continue
        try:
            order = float(s.get("_order") or 0.0)
        except (TypeError, ValueError):
            order = 0.0
        rows.append({
            "slug": slug,
            "name": str(s.get("name") or slug),
            "cover": cover,
            "brand_color": str(s.get("brand_color") or ""),
            "_order": order,
        })
    rows.sort(key=lambda r: r["_order"])
    flagships = [r for slug in FLAGSHIP_SHOW_SLUGS for r in rows if r["slug"] == slug]
    rest = [r for r in rows if r["slug"] not in FLAGSHIP_SHOW_SLUGS]
    return [{k: v for k, v in r.items() if k != "_order"} for r in flagships + rest]


def show_entry(show_slug: str) -> Optional[Dict[str, str]]:
    """This show's own wall row (cover + brand colour), or ``None``."""
    slug = (show_slug or "").strip().lower()
    if not slug:
        return None
    for row in show_wall():
        if row["slug"] == slug:
            return row
    return None


def _load_font(size: int):
    from engine.publisher import _load_font as loader
    return loader(size)


def _tile(cover_path: str, size: int, radius: int):
    """A cover as a rounded ``size``×``size`` RGBA tile, or ``None``."""
    from engine.share_cards import _cover_fill, _inset, _open, _rounded

    im = _open(cover_path)
    if im is None:
        return None
    return _rounded(_cover_fill(_inset(im), (size, size)), radius)


def _paste_tile(card, tile, x: int, y: int) -> None:
    card.alpha_composite(tile, (x, y))


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


def _fit_font(text: str, start: int, floor: int, max_width: int):
    """Shrink a font from ``start`` until ``text`` fits ``max_width``."""
    size = start
    font = _load_font(size)
    while font.getbbox(text)[2] > max_width and size > floor:
        size -= 2
        font = _load_font(size)
    return font


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

    Composed from data (Nov 3 2026): this show's cover framed in its brand
    colour, a wall of the other free shows' covers, the tagline, the
    free-show count, the URL and the QR. A missing cover drops only its
    tile — the card never falls back to a picture of the site and never
    returns ``None`` while PIL can draw.

    ``link_url`` must arrive already funnel-tagged (built by
    ``engine.funnel.episode_link`` with ``PLACEMENT_OUTRO``) — this
    module only draws it into the QR; it never builds campaign URLs.
    """
    try:
        from PIL import Image, ImageDraw
        from engine.share_cards import _hex
    except ImportError:
        logger.warning("promo card: PIL unavailable — no outro card")
        return None

    width, height = size
    t = _texts(channel)
    card = Image.new("RGBA", (width, height), _BG + (255,))
    draw = ImageDraw.Draw(card)

    # Headline across the top: the tagline in the channel's language.
    head = t["headline"]
    head_font = _fit_font(head, 66, 44, width - 160)
    hw = head_font.getbbox(head)[2]
    draw.text(((width - hw) // 2 + 3, 63), head, font=head_font, fill=(0, 0, 0))
    draw.text(((width - hw) // 2, 60), head, font=head_font, fill=_TEXT)

    # The pictures: this show, large, framed in its colour; the others as a
    # wall. Geometry in the 600 px band under the headline (y 205-789), so
    # the URL at y=870 and the QR at y=840 stay clear of it.
    band_y = 205
    margin = 160
    tile_px = 548
    wall_px, wall_gap = 184, 16
    wall_w = WALL_COLS * wall_px + (WALL_COLS - 1) * wall_gap
    try:
        me = show_entry(show_slug)
        my_tile = _tile(me["cover"], tile_px, 28) if me else None
        others = show_wall(exclude_slug=show_slug)
        wall_tiles = []
        for row in others:
            if len(wall_tiles) >= WALL_COLS * WALL_ROWS:
                break
            tile = _tile(row["cover"], wall_px, 18)
            if tile is not None:
                wall_tiles.append(tile)

        if my_tile is not None:
            x0 = margin + 40
            frame = _hex((me or {}).get("brand_color", ""))
            draw.rounded_rectangle(
                (x0 - 10, band_y - 10, x0 + tile_px + 10, band_y + tile_px + 10),
                radius=36, outline=frame, width=8)
            _paste_tile(card, my_tile, x0, band_y)
            label = (show_name or (me or {}).get("name") or "").strip()
            if label:
                name_font = _fit_font(label, 34, 22, tile_px)
                lw = name_font.getbbox(label)[2]
                draw.text((x0 + (tile_px - lw) // 2, band_y + tile_px + 16),
                          label, font=name_font, fill=_TEXT)
            wall_x0 = width - margin - wall_w
        else:
            wall_x0 = (width - wall_w) // 2

        for i, tile in enumerate(wall_tiles):
            col, row_i = i % WALL_COLS, i // WALL_COLS
            _paste_tile(card, tile,
                        wall_x0 + col * (wall_px + wall_gap),
                        band_y + row_i * (wall_px + wall_gap))
    except Exception as exc:  # noqa: BLE001 — the pictures are optional
        logger.warning("promo card: cover composite failed (%s)", exc)

    # URL in Nerra cyan + localized sub-line.
    url_font = _load_font(72)
    url_text = "nerranetwork.com"
    uw = url_font.getbbox(url_text)[2]
    draw.text(((width - uw) // 2 + 3, 873), url_text, font=url_font,
              fill=(0, 0, 0))
    draw.text(((width - uw) // 2, 870), url_text, font=url_font,
              fill=NERRA_CYAN)

    sub = t["sub"]
    sub_font = _fit_font(sub, 40, 28, width - 2 * margin)
    sw = sub_font.getbbox(sub)[2]
    draw.text(((width - sw) // 2, 985), sub, font=sub_font, fill=_MUTED)

    # QR to the funnel-tagged show link, bottom-right (long-form is
    # watched on TVs/desktops where a phone-scan is the natural bridge).
    # The 180 px block at y=840 clears the wall, which ends at y=789.
    if link_url:
        qsize = 180
        qr = _qr_image(link_url, size=qsize)
        if qr is not None:
            qx, qy = width - qsize - 60, 840
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

    card.convert("RGB").save(output_path, format="PNG", optimize=True)
    return Path(output_path)


def render_short_cover_strip(
    covers: List[str],
    target_w: int = SHORT_STRIP_SIZE[0],
    target_h: int = SHORT_STRIP_SIZE[1],
):
    """The Shorts end card's wall of shows: a PIL image of cover tiles.

    Two rows of seven rounded tiles on the card's dark background; a cover
    that cannot be opened is skipped and the next one fills its slot.
    Returns an RGB image ``target_w × target_h`` (empty background when no
    cover opens).
    """
    from PIL import Image

    strip = Image.new("RGBA", (target_w, target_h), _BG + (255,))
    gap = 10
    tile_px = min(
        (target_w - (STRIP_COLS - 1) * gap) // STRIP_COLS,
        (target_h - (STRIP_ROWS - 1) * gap) // STRIP_ROWS,
    )
    grid_w = STRIP_COLS * tile_px + (STRIP_COLS - 1) * gap
    grid_h = STRIP_ROWS * tile_px + (STRIP_ROWS - 1) * gap
    x0, y0 = (target_w - grid_w) // 2, (target_h - grid_h) // 2
    placed = 0
    for cover in covers:
        if placed >= STRIP_COLS * STRIP_ROWS:
            break
        tile = _tile(cover, tile_px, 14)
        if tile is None:
            continue
        col, row = placed % STRIP_COLS, placed // STRIP_COLS
        _paste_tile(strip, tile, x0 + col * (tile_px + gap), y0 + row * (tile_px + gap))
        placed += 1
    return strip.convert("RGB")


def short_site_panel(show_slug: str = "", channel: str = "en") -> Optional[Path]:
    """The PNG the Shorts end card pastes as its site strip.

    A cover strip of the OTHER free shows (flagships first, display order),
    rendered once per process into a temp PNG at :data:`SHORT_STRIP_SIZE`.
    ``channel`` is kept for the callers' signatures (run_show, ru_dub,
    lang_dub); the covers are the same in every language. ``None`` when no
    show registry or no PIL — the card then ships without a strip.
    """
    slug = (show_slug or "").strip().lower()
    cached = _STRIP_CACHE.get(slug)
    if cached is not None and cached.exists():
        return cached
    covers = [row["cover"] for row in show_wall(exclude_slug=slug)]
    if not covers:
        return None
    try:
        strip = render_short_cover_strip(covers)
        fd, name = tempfile.mkstemp(
            prefix=f"nerra_short_strip_{slug or 'network'}_", suffix=".png")
        import os

        os.close(fd)
        out = Path(name)
        strip.save(out, format="PNG", optimize=True)
    except Exception as exc:  # noqa: BLE001 — never block the end card
        logger.warning("promo card: cover strip failed (%s)", exc)
        return None
    _STRIP_CACHE[slug] = out
    return out
