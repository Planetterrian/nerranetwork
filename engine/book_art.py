"""Grok-Imagine art for the anthology books: one editorial illustration
per chapter (embedded in the EPUB and added to the show's image gallery)
and fresh cover art per volume composited under the series' fixed
typography, so volumes share branding while each cover is new.

Model: the series config pins ``grok-imagine-image-quality`` — the
latest released Imagine tier ($0.05/image). Every generated image is
uploaded to the ``nerra-gallery`` bucket through the existing
``gallery_uploader`` with ``intended_use`` values (``book_chapter`` /
``book_cover``) the video scene selector does not match, so book art
enriches the public gallery without ever leaking into episode renders
(the ``thumbnail_variant`` precedent).

Both style guides in the series configs ban text inside the image —
AI-rendered lettering is the tell that cheapens a cover, and the
typography layer here is what keeps the series visually consistent.

Everything is best-effort by contract: no API key, a failed request, or
unconfigured gallery credentials degrade to the typographic cover and a
text-only EPUB rather than blocking the build.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import List, Optional, Tuple

from engine.book_compiler import BookChapter, BookVolume
from engine.grok_imagine import MODEL_COST_USD, _request_one_image

logger = logging.getLogger(__name__)

#: EPUB chapter headers are landscape; covers are generated portrait and
#: composited to KDP's 1600x2560.
CHAPTER_ART_SIZE = "1792x1024"
COVER_ART_SIZE = "1024x1792"

#: Embedded chapter images are re-encoded to JPEG at this width — Amazon
#: charges per-MB delivery on the 70% royalty plan, so a 20-image volume
#: must stay ~2 MB, not 20.
CHAPTER_IMAGE_WIDTH = 1000
CHAPTER_JPEG_QUALITY = 80


def model_cost_usd(model: str) -> float:
    return MODEL_COST_USD.get(model, 0.05)


def chapter_art_prompt(style: str, chapter: BookChapter) -> str:
    """Deterministic prompt: series style guide + this chapter's story."""
    subject = chapter.epigraph or chapter.title
    return (
        f"{style.strip()} Subject of this illustration: {subject}"
    )


def cover_art_prompt(style: str, volume: BookVolume,
                     chapters: List[BookChapter],
                     variant: str = "") -> str:
    """Series cover style + a motif drawn from the volume's stories, so
    each volume's art is new while the style stays constant.

    Deterministic by design — Grok Imagine returns the same image for
    the same prompt, so a re-run reproduces the identical cover.
    *variant* (``cover_variant`` in the volume YAML, or the build
    script's ``--cover-variant``) is the ONLY sanctioned way to re-roll:
    it perturbs the prompt while the committed value keeps the shipped
    cover reproducible.
    """
    motifs = "; ".join(c.title for c in chapters[:6])
    prompt = (
        f"{style.strip()} This volume's stories include: {motifs}. "
        "Choose ONE strong unifying visual metaphor — do not depict a "
        "collage of every story."
    )
    variant = str(variant or "").strip()
    if variant:
        prompt += f" Composition variant {variant}."
    return prompt


def generate_art(prompt: str, *, api_key: str, model: str,
                 size: str) -> Optional[bytes]:
    """One image, or None on any failure (soft by contract)."""
    try:
        return _request_one_image(prompt, api_key=api_key, model=model,
                                  size=size)
    except Exception as exc:  # noqa: BLE001 — art is never build-fatal
        logger.warning("book art generation failed: %s", exc)
        return None


def to_chapter_jpeg(image_bytes: bytes) -> bytes:
    """Normalize generated art to a store-friendly, delivery-fee-friendly
    JPEG for embedding."""
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    if img.width > CHAPTER_IMAGE_WIDTH:
        ratio = CHAPTER_IMAGE_WIDTH / img.width
        img = img.resize((CHAPTER_IMAGE_WIDTH, int(img.height * ratio)))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=CHAPTER_JPEG_QUALITY, optimize=True)
    return out.getvalue()


def upload_book_image_to_gallery(
    image_bytes: bytes,
    volume: BookVolume,
    *,
    prompt: str,
    model: str,
    intended_use: str,
    chapter: Optional[BookChapter] = None,
) -> Optional[str]:
    """Add one book image to the show's public gallery (original +
    thumbnail + sidecar). Returns the public URL or None (soft fail —
    gallery upload never blocks a book build)."""
    try:
        from engine.gallery_uploader import ImageMetadata, upload_image
    except Exception as exc:  # noqa: BLE001
        logger.warning("gallery uploader unavailable: %s", exc)
        return None

    if chapter is not None:
        episode_id = f"{volume.show_slug}_ep{chapter.episode_num:03d}"
        title = chapter.title
        date = chapter.episode_date
        if getattr(volume, "anthology", False) or not volume.volume_number:
            caption = f"Chapter illustration — {volume.title}"
        else:
            caption = (f"Chapter illustration — {volume.title}, "
                       f"Vol. {volume.volume_number}")
        tags = ["book", volume.volume_id, f"ep{chapter.episode_num:03d}"]
    else:
        if getattr(volume, "anthology", False) or not volume.volume_number:
            episode_id = f"{volume.show_slug}_book_collected"
            title = volume.title
        else:
            episode_id = f"{volume.show_slug}_book_vol{volume.volume_number}"
            title = f"{volume.title}, Volume {volume.volume_number}"
        date = volume.built_date_hint
        caption = "Cover art"
        tags = ["book", "cover", volume.volume_id]

    meta = ImageMetadata(
        image_id="",
        show_slug=volume.show_slug,
        show_name=volume.show_name,
        episode_id=episode_id,
        episode_title=title,
        episode_date=date,
        prompt=prompt,
        model=model,
        intended_use=intended_use,
        caption=caption,
        tags=tags,
    )
    try:
        result = upload_image(image_bytes, meta)
    except Exception as exc:  # noqa: BLE001
        logger.warning("gallery upload failed for %s: %s", episode_id, exc)
        return None
    return result.original_url if result else None


# ---------------------------------------------------------------------------
# Cover composition — fixed series typography over per-volume art
# ---------------------------------------------------------------------------

def cover_badge_text(volume: BookVolume) -> str:
    """The cover badge label.

    A numbered volume reads "VOLUME N"; a collected edition (anthology,
    volume_number 0) reads "COLLECTED EDITION" — a badge must never
    render a 0 (WO-11: "VOLUME 0" shipped on both collected covers).
    """
    if getattr(volume, "anthology", False) or not volume.volume_number:
        return "COLLECTED EDITION"
    return f"VOLUME {volume.volume_number}"


def compose_cover(
    volume: BookVolume,
    out_png: Path,
    *,
    art_bytes: Optional[bytes] = None,
    size: Tuple[int, int] = (1600, 2560),
) -> Path:
    """Composite the final cover: Grok art (cover-cropped) under a
    darkening gradient, then the series' fixed typography — title band,
    accent rule, subtitle, author, volume badge. With no art (missing
    key / failed generation) the background falls back to the series
    color, which is exactly the previous typographic cover."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    w, h = size
    if art_bytes:
        try:
            art = Image.open(io.BytesIO(art_bytes)).convert("RGB")
            # Cover-crop to the target aspect, then scale.
            target_ratio = w / h
            ratio = art.width / art.height
            if ratio > target_ratio:
                new_w = int(art.height * target_ratio)
                x0 = (art.width - new_w) // 2
                art = art.crop((x0, 0, x0 + new_w, art.height))
            else:
                new_h = int(art.width / target_ratio)
                y0 = (art.height - new_h) // 2
                art = art.crop((0, y0, art.width, y0 + new_h))
            img = art.resize(size, Image.LANCZOS)
        except Exception as exc:  # noqa: BLE001
            logger.warning("cover art unusable (%s) — typographic fallback",
                           exc)
            img = Image.new("RGB", size, volume.cover_color)
    else:
        img = Image.new("RGB", size, volume.cover_color)

    # Legibility gradients: darken the top (title) and bottom (author)
    # thirds without flattening the art in the middle.
    overlay = Image.new("L", size, 0)
    odraw = ImageDraw.Draw(overlay)
    for y in range(h):
        if y < h * 0.38:
            alpha = int(190 * (1 - y / (h * 0.38)))
        elif y > h * 0.72:
            alpha = int(200 * ((y - h * 0.72) / (h * 0.28)))
        else:
            alpha = 0
        odraw.line([(0, y), (w, y)], fill=alpha)
    overlay = overlay.filter(ImageFilter.GaussianBlur(4))
    img = Image.composite(Image.new("RGB", size, "#0a0f16"), img, overlay)

    draw = ImageDraw.Draw(img)

    def _font(px: int):
        for name in ("DejaVuSerif-Bold.ttf", "DejaVuSerif.ttf",
                     "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(name, px)
            except OSError:
                continue
        return ImageFont.load_default()

    def _wrap(text: str, font, max_w: int) -> List[str]:
        lines, line = [], ""
        for word in text.split():
            trial = f"{line} {word}".strip()
            if draw.textlength(trial, font=font) <= max_w or not line:
                line = trial
            else:
                lines.append(line)
                line = word
        if line:
            lines.append(line)
        return lines

    margin = int(w * 0.09)
    max_text_w = w - 2 * margin

    title_px = 170
    while title_px > 76:
        font = _font(title_px)
        if len(_wrap(volume.title, font, max_text_w)) <= 4:
            break
        title_px -= 12
    font = _font(title_px)
    y = int(h * 0.055)
    for ln in _wrap(volume.title, font, max_text_w):
        draw.text((w // 2, y), ln, font=font, fill="#f5f2ea", anchor="ma")
        y += int(title_px * 1.16)

    y += int(h * 0.012)
    draw.rectangle([w // 2 - 260, y, w // 2 + 260, y + 8],
                   fill=volume.cover_accent)
    y += int(h * 0.028)

    if volume.subtitle:
        sub_font = _font(58)
        for ln in _wrap(volume.subtitle, sub_font, max_text_w):
            draw.text((w // 2, y), ln, font=sub_font, fill="#e3e9ef",
                      anchor="ma")
            y += 74

    # Volume badge — the series-continuity cue. A collected edition has
    # no meaningful number (volume_number 0), and "VOLUME 0" on a front
    # cover is a defect (WO-11): those covers badge as COLLECTED EDITION.
    badge_font = _font(54)
    badge_text = cover_badge_text(volume)
    bw = draw.textlength(badge_text, font=badge_font)
    bx, by = w // 2, int(h * 0.80)
    draw.rounded_rectangle(
        [bx - bw / 2 - 36, by - 14, bx + bw / 2 + 36, by + 74],
        radius=14, outline=volume.cover_accent, width=5)
    draw.text((bx, by), badge_text, font=badge_font,
              fill=volume.cover_accent, anchor="ma")

    author_font = _font(70)
    draw.text((w // 2, int(h * 0.875)), volume.author.upper(),
              font=author_font, fill="#f5f2ea", anchor="ma")
    series_font = _font(42)
    draw.text((w // 2, int(h * 0.935)),
              f"From the {volume.show_name} podcast · Nerra Network",
              font=series_font, fill="#aebccb", anchor="ma")

    out_png = Path(out_png)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png, "PNG")
    return out_png
