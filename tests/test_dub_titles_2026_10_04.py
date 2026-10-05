"""Oct 4 2026 — dub Short titles: whole hooks, and no blind retitles.

Operator dry run of the RU retitle (Actions run 37142855470) rejected all
68 proposals: each was the episode headline plus «— ещё момент», trimmed
mid-phrase, identical across sibling Shorts, and none came from the
Short's own words. The same read found the LIVE hook Short cut mid-phrase
by a 70-character budget («…в бизнес совместного», FF Ep212).
"""
from __future__ import annotations

import pytest

from engine import lang_dub, ru_dub
from scripts import retitle_youtube_videos as rt

FF_212 = ("Starlink Communities превращает один комплект в бизнес "
          "совместного доступа")


class TestHookShortShipsWhole:
    def test_ff_ep212_hook_is_not_cut(self):
        title = ru_dub._ru_short_title(FF_212)
        assert title == FF_212 + " #Shorts"
        assert len(title) <= 100

    def test_episode_prefix_still_dropped(self):
        assert ru_dub._ru_short_title("Эп. 212: " + FF_212) == FF_212 + " #Shorts"

    def test_a_headline_over_the_cap_is_still_trimmed(self):
        long = "Эп. 5: " + "Патент " * 30
        title = ru_dub._ru_short_title(long)
        assert len(title) <= 100 and title.endswith(" #Shorts")
        assert len(title) < 92  # the 70-char budget, not the cap

    def test_fallback_keeps_room_for_its_tail(self):
        title = ru_dub._ru_second_short_title(FF_212)
        assert title.endswith(ru_dub.RU_SECOND_SHORT_TAIL + " #Shorts")
        assert len(title) <= 100

    @pytest.mark.parametrize("code", sorted(lang_dub.DUB_LANGUAGES))
    def test_language_dubs_match(self, code):
        lang = lang_dub.DUB_LANGUAGES[code]
        head = "Le premier vol orbital de Starship a placé vingt-six satellites Starlink"
        assert lang_dub._short_title(head, lang) == head + " #Shorts"
        fallback = lang_dub._second_short_title(head, lang)
        assert len(fallback) <= 100 and fallback.endswith(" #Shorts")


class TestDubRetitleIsReportOnly:
    def test_a_fragment_is_reported_without_a_title(self):
        rec = {"video_id": "x", "kind": "short", "window": "filled",
               "title": "в 2026 года #Shorts", "hook": FF_212}
        out = rt._dub_proposal(rec, "ru")
        assert out is not None and out["new_title"] is None
        assert out["reason"]

    def test_hook_shorts_and_complete_titles_are_left_alone(self):
        assert rt._dub_proposal({"video_id": "x", "kind": "short",
                                 "window": "hook_open",
                                 "title": "в 2026 года #Shorts"}, "ru") is None
        assert rt._dub_proposal({"video_id": "x", "kind": "short",
                                 "window": "filled",
                                 "title": FF_212 + " #Shorts"}, "ru") is None

    @pytest.mark.parametrize("channel", ["ru", "fr"])
    def test_apply_on_committed_data_changes_no_dub_video(self, channel):
        proposals = rt.plan(None, False, channel=channel)
        assert not [p for p in proposals if p.get("new_title")]

    def test_no_tail_title_can_be_proposed(self):
        import inspect
        src = inspect.getsource(rt._dub_proposal)
        assert "_second_short_title" not in src
