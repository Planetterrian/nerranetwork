"""My Nerra (account.html) as the member's own front page (Oct 28 2026).

The page is static and personalizes in the browser from
``api/personal_front.json``, which every homepage build writes from the
homepage's own story data. These guards pin the data contract, that every
workflow which rebuilds the homepage also commits the file, and the page
rules the redesign depends on.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

import generate_html as gh
from engine import landing_test as lt
from engine.personal_edition import PERSONAL_SHOW_SLUGS

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates" / "account_page.html.j2"


def _src() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def payload():
    return gh.personal_front_payload(
        gh._build_all_shows_list(), gallery_root=ROOT / "site" / "data" / "gallery",
        now=datetime(2026, 10, 28, 18, 0, tzinfo=timezone.utc))


class TestRecentRecords:
    def test_newest_first_by_episode_number(self, tmp_path):
        p = tmp_path / "s.json"
        p.write_text(json.dumps({"summaries": [
            {"episode_num": "5"}, {"episode_num": "9"}, {"episode_num": "7"}]}))
        assert [r["episode_num"] for r in lt.recent_records(p, 3)] == ["9", "7", "5"]
        assert lt.recent_records(p, 1)[0] == lt.latest_record(p)

    def test_agrees_with_latest_record_on_every_show(self):
        for slug, cfg in gh.NETWORK_SHOWS.items():
            jp = cfg.get("json_path")
            if not jp or not (ROOT / jp).is_file():
                continue
            recent = lt.recent_records(ROOT / jp, 1)
            assert (recent[0] if recent else None) == lt.latest_record(ROOT / jp), slug

    def test_missing_or_broken_file_is_empty(self, tmp_path):
        assert lt.recent_records(tmp_path / "nope.json") == []
        bad = tmp_path / "bad.json"
        bad.write_text("{")
        assert lt.recent_records(bad) == []


class TestPersonalFrontPayload:
    def test_every_personal_show_is_listed(self, payload):
        for slug in PERSONAL_SHOW_SLUGS:
            assert slug in payload["shows"], slug

    def test_members_only_shows_carry_no_episodes(self, payload):
        gated = [s for s, e in payload["shows"].items() if e["members_only"]]
        assert gated, "the regional desks are members-only today"
        for slug in gated:
            assert payload["shows"][slug]["stories"] == [], slug

    def test_stories_are_whole_and_newest_first(self, payload):
        spacex = payload["shows"]["spacex"]["stories"]
        assert 1 <= len(spacex) <= gh.PERSONAL_FRONT_PER_SHOW
        nums = [s["episode_num"] for s in spacex]
        assert nums == sorted(nums, reverse=True)
        lead = spacex[0]
        # The full hook, never the clipped feed title.
        assert lead["hook"] and not lead["hook"].endswith("…")
        assert not lead["hook"].startswith("Ep ")
        for key in ("post_url", "audio_url", "stamp", "headlines", "duration_s", "show_page"):
            assert key in lead, key
        assert lead["audio_url"].startswith("https://")
        assert isinstance(lead["headlines"], list)
        assert lead["hook"] not in lead["headlines"]

    def test_no_member_digest_text_reaches_the_file(self, payload):
        """A members-only show's digests live in members/; no public file reads
        them (CLAUDE.md, gated shows)."""
        text = json.dumps(payload)
        assert "/members/" not in text

    def test_is_json_and_small(self, payload):
        raw = json.dumps(payload, separators=(",", ":"))
        assert len(raw) < 300_000, len(raw)
        json.loads(raw)

    def test_writer_never_raises(self, tmp_path):
        assert gh.write_personal_front(None, gallery_root=tmp_path, now=datetime.now(timezone.utc),
                                       output_dir=tmp_path) is None


class TestTheFileIsWrittenAndCommitted:
    def test_the_homepage_build_writes_it(self):
        body = gh.generate_network_page.__code__.co_names
        assert "write_personal_front" in body

    @pytest.mark.parametrize("wf", ["nerra-daily.yml", "nightly-maintenance.yml", "render-video.yml"])
    def test_each_homepage_commit_includes_it(self, wf):
        assert "api/personal_front.json" in (ROOT / ".github" / "workflows" / wf).read_text()

    def test_finalize_commits_every_api_json(self):
        text = (ROOT / ".github" / "workflows" / "run-show.yml").read_text()
        assert "git add api/*.json" in text and "generate_html.py --homepage" in text


class TestThePage:
    def test_reads_the_front_file_and_never_the_clipped_feed_titles(self):
        src = _src()
        assert "api/personal_front.json" in src
        assert "api/episodes.json" not in src

    def test_drift_guarded_ids_kept(self):
        src = _src()
        for marker in ("nn-feed-cancelled", "nn-starter-note", "nn-city-nudge", "nn-tier-badge",
                       "nn-addons", "nn-addon-upsell", "nn-editions-list", "nn-library-card",
                       "nn-build-btn", "nn-portal-btn", "nn-ends-note", "nn-switch-portal",
                       "nn-today-stats", "nn-tomorrow-list"):
            assert marker in src, marker

    def test_no_button_inside_a_link(self):
        assert not re.search(r"<a\b[^>]*>\s*<button", _src())

    def test_topics_open_to_every_account(self):
        """The Worker stores topics whatever the plan; the page follows them
        for everyone and says Mira researches them on PNN."""
        src = _src()
        assert "inp.disabled = i >= lim.topics" not in src
        assert "inp.disabled = false" in src

    def test_story_text_is_escaped_and_urls_checked(self):
        src = _src()
        assert "function safeUrl" in src and "function esc" in src
        # Every story headline reaches the page through esc() or highlight(),
        # which escapes each piece.
        assert "esc(s.hook)" in src
        assert "out += on ? '<mark>' + esc(tok) + '</mark>' : esc(tok);" in src

    def test_plays_are_reported_like_tracking_js(self):
        """Since the site player (assets/js/nn-player.js) plays My Nerra's
        episodes, it reports them, with tracking.js's parameters; the page
        marks the sample so it reports its own event."""
        player = (ROOT / "assets" / "js" / "nn-player.js").read_text()
        assert "track('episode_play', { src:" in player
        assert "track('play_personal_sample', { placement: it.sample" in player
        assert "sample: 'account'" in _src()
        assert "track('episode_play'" not in _src(), "the page must not report a play twice"
        tracking = (ROOT / "assets" / "js" / "tracking.js").read_text()
        assert "track('episode_play', {" in tracking and "src:" in tracking

    def test_no_dangling_greeting_dash(self):
        src = _src()
        assert "' —';" not in src

    def test_rendered_script_parses(self, tmp_path):
        node = shutil.which("node")
        if not node:
            pytest.skip("node not installed")
        out = gh.generate_account_page(output_dir=tmp_path)
        html = Path(out).read_text(encoding="utf-8")
        script = re.search(r"<script>\s*(var NN = \(function[\s\S]*?)</script>", html).group(1)
        js = tmp_path / "nn.js"
        js.write_text(script, encoding="utf-8")
        res = subprocess.run([node, "--check", str(js)], capture_output=True, text=True)
        assert res.returncode == 0, res.stderr

    def test_shows_carry_their_colour(self):
        rows = gh._personal_shows_list()
        assert rows and all(r["brand_color"].startswith("#") for r in rows)
