"""Oct 10 2026 (Patrick). Every show except Tesla Shorts Time posts on
@nerranetwork; Tesla keeps @teslashortstime.

X's API is pay-per-use: a post that contains a URL costs $0.20, a plain post
$0.015, and each uploaded media object another $0.015. So the daily shows
post their own Short as native video with the episode hook and no link
(about $0.03, and native video travels further on X than a link post), Nerra
Daily posts its cover, and only the interview episodes keep their link.
X's automation rules forbid near-identical posts, so every post leads with
the episode's own hook.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.config import load_config  # noqa: E402
from engine import x_media, x_post  # noqa: E402

SKIP = {"_blocked_sources", "_defaults", "_producer_policy", "_trading_policy",
        "network_meta", "pronunciation_map", "scaffold_pending", "translation_overrides"}
SHOWS = sorted(p.stem for p in (ROOT / "shows").glob("*.yaml") if p.stem not in SKIP)
INTERVIEW_SHOWS = {"age_of_ai", "nerra_voices"}
URL = re.compile(r"(?i)https?://|www\.")


def _cfg(slug):
    return load_config(ROOT / "shows" / f"{slug}.yaml")


@pytest.mark.parametrize("slug", SHOWS)
def test_only_tesla_posts_anywhere_but_nerranetwork(slug):
    pub = _cfg(slug).publishing
    if not pub.x_enabled:
        return
    if slug == "tesla":
        assert pub.x_env_prefix == "X_" and pub.x_handle == "@teslashortstime"
        assert pub.x_post_format == "link"
        return
    assert pub.x_env_prefix == "NERRANETWORK_X_", slug
    if slug not in INTERVIEW_SHOWS:
        assert pub.x_post_format == "clip", slug
        assert pub.x_handle == "@nerranetwork", slug


def test_the_shows_that_posted_before_still_post():
    for slug in ("spacex", "models_agents", "modern_investing", "omni_view",
                 "planetterrian", "fascinating_frontiers", "unintended_consequences",
                 "age_of_ai", "nerra_voices", "tesla"):
        assert _cfg(slug).publishing.x_enabled, slug


def test_nobody_posts_on_planetterrian_any_more():
    for slug in SHOWS:
        assert _cfg(slug).publishing.x_env_prefix != "PLANETTERRIAN_X_", slug


# ------------------------------------------------------------- the post --
def test_clip_text_has_no_link_and_fits():
    hook = ("Starship's ninth flight cleared the tower and the booster came home; "
            "here is what changed since the last attempt https://example.com/x " * 4)
    text = x_post.clip_post_text(label="🚀 SpaceX Daily", hook=hook, episode_num=412)
    assert text.startswith("🚀 SpaceX Daily · Ep 412\n\n")
    assert "Starship's ninth flight" in text
    assert not URL.search(text)
    assert len(text) <= x_post.CLIP_TEXT_MAX
    assert text.endswith(x_post.CLIP_CLOSER)
    assert not re.search(r"\b[\w-]+\.(com|net|org|io|ai)\b", x_post.CLIP_CLOSER)


def test_clip_text_without_a_hook_still_reads():
    text = x_post.clip_post_text(label="📰⚖️ Omni View", hook="", episode_num=7)
    assert text == "📰⚖️ Omni View · Ep 7\n\n" + x_post.CLIP_CLOSER


# ----------------------------------------------------------- the upload --
class _Resp:
    def __init__(self, payload=None, status=200):
        self._p, self.status_code, self.text = payload or {}, status, ""

    def json(self):
        return self._p

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(response=self)


class _Session:
    def __init__(self, states=("in_progress", "succeeded"), fail_at=""):
        self.calls, self.states, self.fail_at = [], list(states), fail_at

    def post(self, url, **kw):
        self.calls.append(("POST", url, kw))
        step = url.rsplit("/", 1)[-1]
        if step == self.fail_at:
            return _Resp(status=403)
        if step == "initialize":
            assert kw["json"]["media_category"] in ("tweet_video", "tweet_image")
            return _Resp({"data": {"id": "123", "media_key": "7_123"}})
        if step == "append":
            return _Resp({}, 204)
        return _Resp({"data": {"id": "123", "processing_info": {
            "state": "pending", "check_after_secs": 1}}})

    def get(self, url, **kw):
        self.calls.append(("GET", url, kw))
        assert kw["params"] == {"command": "STATUS", "media_id": "123"}
        return _Resp({"data": {"processing_info": {"state": self.states.pop(0),
                                                   "check_after_secs": 1}}})


CREDS = {"consumer_key": "a", "consumer_secret": "b",
         "access_token": "c", "access_token_secret": "d"}


@pytest.fixture
def clip(tmp_path, monkeypatch):
    monkeypatch.setattr(x_media, "_auth", lambda creds: None)
    monkeypatch.setattr(x_media, "CHUNK_BYTES", 10)
    path = tmp_path / "short.mp4"
    path.write_bytes(b"x" * 25)
    return path


def test_the_v2_chunked_upload(clip):
    s = _Session()
    assert x_media.upload_media(clip, CREDS, session=s, sleep=lambda _: None) == "123"
    steps = [(m, u.replace(x_media.UPLOAD_URL, "")) for m, u, _ in s.calls]
    assert steps == [("POST", "/initialize"), ("POST", "/123/append"), ("POST", "/123/append"),
                     ("POST", "/123/append"), ("POST", "/123/finalize"), ("GET", ""), ("GET", "")]
    indexes = [kw["data"]["segment_index"] for m, u, kw in s.calls if u.endswith("/append")]
    assert indexes == ["0", "1", "2"]
    assert "command" not in str(s.calls[0][2]), "the old command=INIT form is deprecated"


def test_a_failed_upload_returns_none(clip):
    assert x_media.upload_media(clip, CREDS, session=_Session(fail_at="finalize"),
                                sleep=lambda _: None) is None
    assert x_media.upload_media(clip, CREDS, session=_Session(states=("failed",)),
                                sleep=lambda _: None) is None
    assert x_media.upload_media(clip.with_suffix(".txt"), CREDS, session=_Session()) is None


def test_post_media_uses_the_first_media_that_uploads(clip, monkeypatch, tmp_path):
    for k in ("CONSUMER_KEY", "CONSUMER_SECRET", "ACCESS_TOKEN", "ACCESS_TOKEN_SECRET"):
        monkeypatch.setenv(f"NERRANETWORK_X_{k}", "v")
    from engine import publisher
    seen = {}
    monkeypatch.setattr(publisher, "post_to_x",
                        lambda text, **kw: seen.update(kw, text=text) or "https://x.com/i/status/9")
    cover = tmp_path / "cover.jpg"
    cover.write_bytes(b"jpg")
    monkeypatch.setattr(x_media, "upload_media",
                        lambda p, creds, **kw: None if str(p).endswith(".mp4") else "55")
    posted, reason, url, used = x_post.post_media(
        env_prefix="NERRANETWORK_X_", text="hi", media_paths=[str(clip), str(cover)], label="t")
    assert (posted, reason, used) == (True, "", str(cover)) and seen["media_ids"] == ["55"]
    monkeypatch.setattr(x_media, "upload_media", lambda p, creds, **kw: None)
    posted, reason, url, used = x_post.post_media(
        env_prefix="NERRANETWORK_X_", text="hi", media_paths=[str(clip)], label="t")
    assert (posted, reason, used) == (True, "no_media", "") and seen["media_ids"] is None


def test_post_media_skips_without_credentials(monkeypatch):
    for k in ("CONSUMER_KEY", "CONSUMER_SECRET", "ACCESS_TOKEN", "ACCESS_TOKEN_SECRET"):
        monkeypatch.delenv(f"NERRANETWORK_X_{k}", raising=False)
    assert x_post.post_media(env_prefix="NERRANETWORK_X_", text="t", media_paths=[],
                             label="t")[:2] == (False, "no_credentials")


# ------------------------------------------------------------ the wiring --
RUN_SHOW = (ROOT / "run_show.py").read_text(encoding="utf-8")


def test_run_show_posts_the_short_and_no_cross_promo_in_clip_mode():
    clip_branch = RUN_SHOW[RUN_SHOW.index("if _x_clip_mode and all("):
                           RUN_SHOW.index("elif all([consumer_key, consumer_secret")]
    assert "post_media(" in clip_branch and "clip_post_text(" in clip_branch
    assert "_build_cross_promo_reply" not in clip_branch
    assert "Path(_clip).unlink(missing_ok=True)" in clip_branch
    assert 'result["x_clip_path"] = str(_x_clip)' in RUN_SHOW
    assert 'extra_context["x_clip_path"] = youtube_urls["x_clip_path"]' in RUN_SHOW


def test_the_workflows_carry_the_network_keys():
    text = (ROOT / ".github" / "workflows" / "run-show.yml").read_text(encoding="utf-8")
    for k in ("CONSUMER_KEY", "CONSUMER_SECRET", "ACCESS_TOKEN", "ACCESS_TOKEN_SECRET"):
        assert f"NERRANETWORK_X_{k}: ${{{{ secrets.NERRANETWORK_X_{k} }}}}" in text


def test_nerra_daily_posts_its_cover_without_a_link():
    src = (ROOT / "scripts" / "build_daily_edition.py").read_text(encoding="utf-8")
    fn = src[src.index("def post_edition_to_x("):src.index("def main(")]
    assert "post_media(" in fn and "post_teaser(" not in fn and "episode_link(" not in fn
    assert (ROOT / "assets" / "covers" / "nerra-daily.jpg").exists()


# ------------------------------------------- first night (Oct 11 2026) --
def _fn(name):
    src = RUN_SHOW
    i = src.index(f"def {name}(")
    j = src.index("\ndef ", i + 10)
    ns: dict = {"re": re, "Path": Path, "logger": __import__("logging").getLogger("t")}
    exec(src[i:j], ns)
    return ns[name]


class TestTheHookIsFoundWithoutItsLabel:
    """SpaceX Ep125 and Ep127 wrote the hook as a plain first line; the
    podcast title went generic and the X post had no hook."""

    def test_plain_bold_first_line(self):
        f = _fn("_extract_hook")
        digest = ("**SpaceX targets Tuesday for its 35th Dragon cargo flight to the ISS "
                  "while Grok gains direct shopping tools.**\n\n### Top News\n1. x")
        assert f(digest).startswith("SpaceX targets Tuesday")

    def test_plain_line_after_the_title(self):
        f = _fn("_extract_hook")
        digest = ("# SpaceX Daily\n\nSpaceX spectrum purchase opens indoor phone coverage "
                  "for Starlink Mobile against carriers.\n\n### Top News")
        assert f(digest).startswith("SpaceX spectrum purchase")

    def test_never_past_the_first_section(self):
        f = _fn("_extract_hook")
        assert f("### Segment 1\nIn the narrow lanes of colonial Delhi, a bounty went wrong.") is None
        assert f("# Tesla Shorts Time\n**Date:** Feb 24\n\n### Top 10\n1. Headline") is None

    def test_decorative_subtitle_is_skipped(self):
        f = _fn("_extract_hook")
        digest = ("🌍 **Planetterrian Daily** - Science, Longevity & Health\n\n"
                  "A new drainage pathway in the eye carries waste into the lymph system.\n\n### Top")
        assert f(digest).startswith("A new drainage pathway")


class TestXGetsAClipWhenYouTubeDoesNot:
    """Planetterrian, Modern Investing and Unintended Consequences posted their
    cover: the YouTube policy gave them no Short."""

    def test_step_13_renders_a_clip_when_there_is_none(self):
        # Oct 11 2026: rendered in step 13, so shows that are not on YouTube
        # at all (the second wave) get a clip too.
        branch = RUN_SHOW[RUN_SHOW.index("if _x_clip_mode and all("):
                          RUN_SHOW.index("elif all([consumer_key, consumer_secret")]
        assert "_render_x_only_clip(" in branch and "find_transcript_for_episode(" in branch
        i = RUN_SHOW.index('result["yt_policy_shorts_skipped"] = True')
        assert "_render_x_only_clip(" not in RUN_SHOW[i:i + 400]

    def test_the_render(self, tmp_path, monkeypatch):
        import engine.video as video
        seen = {}

        def fake(audio, cover, out, **kw):
            seen.update(kw)
            Path(out).write_bytes(b"mp4")
            return out
        monkeypatch.setattr(video, "build_short_video", fake)
        f = _fn("_render_x_only_clip")
        cfg = _cfg("planetterrian")
        out = f(cfg, final_mp3=tmp_path / "a.mp3", cover_path=tmp_path / "c.jpg",
                work_dir=tmp_path / "w", base_name="P_Ep210", hook="A hook line")
        assert out.endswith("P_Ep210_x_clip.mp4")
        assert seen["end_card"] is False and seen["start_offset"] == float(cfg.audio.voice_intro_delay or 0)

    def test_a_failed_render_falls_back_to_the_cover(self, tmp_path, monkeypatch):
        import engine.video as video
        monkeypatch.setattr(video, "build_short_video",
                            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("ffmpeg")))
        f = _fn("_render_x_only_clip")
        assert f(_cfg("planetterrian"), final_mp3="a.mp3", cover_path="c.jpg",
                 work_dir=tmp_path, base_name="b") == ""


def test_nerra_daily_does_not_say_its_episode_twice():
    src = (ROOT / "scripts" / "build_daily_edition.py").read_text(encoding="utf-8")
    fn = src[src.index("def post_edition_to_x("):src.index("def main(")]
    pattern = re.search(r're\.sub\(r"(.+?)", ""', fn).group(1)
    assert re.sub(pattern, "", "Ep 52: Sunday edition, Dragon cargo") == "Sunday edition, Dragon cargo"
    assert re.sub(pattern, "", "Episode 7 — A title") == "A title"
