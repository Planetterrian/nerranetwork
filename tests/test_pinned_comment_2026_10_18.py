"""Oct 18 2026: every long-form YouTube comment and description shipped the
raw pinned-comment template ("{show_page_url}", "{show_name}") because the
network template names a field the renderer never supplied and a KeyError
returned the template unchanged."""

import json
import re
from pathlib import Path

import pytest

from engine.config import load_config
from engine.video_metadata import build_pinned_comment_text

ROOT = Path(__file__).resolve().parent.parent
SHOW_YAMLS = sorted(p for p in (ROOT / "shows").glob("*.yaml") if not p.name.startswith("_"))
_FIELD = re.compile(r"\{[a-z_]+\}")


@pytest.mark.parametrize("path", SHOW_YAMLS, ids=lambda p: p.stem)
def test_every_show_renders_its_pinned_comment_with_no_placeholder(path):
    cfg = load_config(path)
    text = build_pinned_comment_text(
        cfg, hook="A hook.", episode_num=7, today_str="October 18, 2026",
        rss_link=cfg.publishing.rss_link or "", audio_url="https://a/b.mp3")
    assert not _FIELD.search(text), text
    if text and "show_name" in (cfg.youtube.pinned_comment_template or ""):
        assert cfg.name in text


def test_unknown_field_renders_empty_not_the_template():
    class Y:
        pinned_comment_template = "Hi {mystery} on {show_name}"

    class C:
        name = "Show"
        youtube = Y()

    assert build_pinned_comment_text(C()) == "Hi  on Show"


def test_no_queued_comment_carries_a_placeholder():
    for f in (ROOT / "digests").glob("*/scheduled_comments.json"):
        for e in json.loads(f.read_text()).get("pending", []):
            assert not _FIELD.search(e.get("text", "")), (f, e["video_id"])
