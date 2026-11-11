"""Nov 11 2026 (the Age of AI / Nerra Voices review).

1. How the hour goes is written down where the guest reads it before joining:
   the studio's pre-join card and the two-hour reminder email, both from
   ``engine.brand.MIRA_HOUR_PARTS``. Twenty graded rooms named the spoken
   format speech at the top more than any other fault; the written copy is
   what lets the spoken opening stay short.
2. The publish-day email carries a post in the guest's own words, drafted by
   the social pass, with the episode's link in it.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOICES = ROOT / "pipelines" / "voices"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(VOICES))

from engine import brand  # noqa: E402

STUDIO = (ROOT / "age-of-ai-studio.html").read_text(encoding="utf-8")


def _flat(text: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", text)).split())


class TestTheHourIsWrittenDown:
    def test_the_studio_card_says_what_brand_says(self):
        card = STUDIO[STUDIO.index('id="hourPlan"'):]
        card = _flat(card[:card.index("</ul>")])
        assert brand.MIRA_HOUR_HEADING in card
        for title, detail in brand.MIRA_HOUR_PARTS:
            assert f"{title} — {detail}" in card, title

    def test_the_buttons_it_names_are_the_studios_buttons(self):
        steer = dict(brand.MIRA_HOUR_PARTS)["You steer"]
        for label in ("New subject", "Repeat the question", "Good question", "Let's wrap up"):
            assert label in steer
            assert f">{label}</button>" in STUDIO, label

    def test_a_restart_is_cut_in_code(self):
        import auto_edit
        assert auto_edit.RESTART_RE.search("sorry, can I start again")

    def test_the_transcript_terms_match_the_steps(self):
        steps = dict(brand.MIRA_INTERVIEW_STEPS)["You approve your transcript"]
        part = dict(brand.MIRA_HOUR_PARTS)["You see it before anyone else"]
        assert "a week to approve it, cut from it or refuse it" in part
        assert "a week to approve it, cut anything from it, or refuse it" in steps

    def test_the_pre_join_card_no_longer_repeats_the_pause_line(self):
        assert STUDIO.count("pauses a few seconds after you finish") == 1

    def test_the_two_hour_reminder_carries_it_and_the_nudge_does_not(self):
        import fire_interviews as fi

        class Show:
            name = "The Age of AI"

            def studio_url(self, iid):
                return f"https://nerranetwork.com/age-of-ai-studio.html?i={iid}"

            def __getattr__(self, _):
                return ""

        interview = {"id": "i1", "scheduled_at": "2026-11-12T12:15:00Z", "show": "age_of_ai"}
        app = {"name": "Rania Example", "email": "r@example.com"}
        fi_show = Show()
        try:
            _, body = fi.reminder_email(interview, app, fi_show, "")
        except Exception:  # noqa: BLE001 — a helper needs a real show
            from shows import get_show
            fi_show = get_show("age_of_ai")
            _, body = fi.reminder_email(interview, app, fi_show, "")
        assert brand.MIRA_HOUR_HEADING in body
        _, nudge = fi.reminder_email(interview, app, fi_show, "", soon=True)
        assert brand.MIRA_HOUR_HEADING not in nudge


class TestTheGuestGetsAPostInTheirOwnWords:
    PROMPT = (VOICES / "prompts" / "editorial_passes" / "06_social_copy.txt").read_text(encoding="utf-8")

    def test_the_social_pass_drafts_it_in_the_first_person(self):
        assert '"guest_post"' in self.PROMPT
        assert "in the first person" in self.PROMPT
        assert "never invent an experience, a number or an opinion" in self.PROMPT

    def test_the_validator_wants_the_link_but_not_the_key(self):
        from validators.schema_validators import validate_pass_output
        base = {"twitter": "t {episode_url}", "linkedin": "l {episode_url}", "instagram": "i"}
        validate_pass_output("social_copy", base)
        validate_pass_output("social_copy", {**base, "guest_post": "I talked with Mira. {episode_url}"})
        try:
            validate_pass_output("social_copy", {**base, "guest_post": "I talked with Mira."})
        except ValueError:
            pass
        else:
            raise AssertionError("a guest post without the link passed")

    def test_the_publish_email_carries_it_with_the_link(self):
        import publish_episode as pe
        url = "https://nerranetwork.com/blog/age-of-ai/ep16.html"
        pkg = {"social_copy": {"guest_post": "I sat down with Mira <today>. {episode_url}"}}
        assert pe.guest_post_text(pkg, url) == f"I sat down with Mira <today>. {url}"
        assert pe.guest_post_text({"social_copy": {"guest_post": "no link"}}, url) == ""
        assert pe.guest_post_text({}, url) == ""
        src = (VOICES / "publish_episode.py").read_text(encoding="utf-8")
        body = src[src.index("def published_email"):src.index("def _md_link_html")]
        assert "guest_post_text(pkg, post)" in body
        assert "{e(draft)}" in body
