"""Nerra Daily email, Nov 6 2026: the Buttondown review.

* A deck never opens on an item head's list of outlets (Tesla Ep657's card
  printed ten publisher names before the first fact).
* A deck never ends a sentence on an abbreviation ("… on the morning of
  Oct." — Fascinating Frontiers Ep245).
* An "Also on Nerra today" line prints whole when a whole line exists.
* A new reader is not told what they failed to do.
* The welcome email: Patrick's sign-off, every site link measured, no
  template condition, and a pill that names it.
* No signup button says "Check your email" (nothing sends one).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import landing_test as lt  # noqa: E402
from engine import nerra_daily_email as nde  # noqa: E402
from engine import nerra_welcome_email as welcome  # noqa: E402
from engine.funnel import parse_campaign_id  # noqa: E402
from engine.titles import EMAIL_ALSO_LINE_MAX  # noqa: E402

TESLA_DIGEST = """# Tesla Shorts Time

> **Tesla is freeing Texas factory space for Cybercab output by winding down Cybertruck production around mid-2027.**

### Top News

1. **Tesla to wind down Cybertruck production at Texas Gigafactory around mid-2027:** The Verge, Business Insider, Forbes, New York Post, Social News XYZ, Torque News, Motor1.com
   Tesla CEO Elon Musk said the company will wind down Cybertruck production at Gigafactory Texas around the middle of next year. The Austin plant is the only facility equipped for it. Source: [theverge.com](https://www.theverge.com/x)
"""
TESLA_HOOK = ("Tesla is freeing Texas factory space for Cybercab output by winding down "
              "Cybertruck production around mid-2027.")

FF_DIGEST = """# Fascinating Frontiers

> **A Canadian observer tracked the Moon swallowing Jupiter by hand with an 8-inch Dobsonian.**

### Top Stories

1. **A Canadian observer tracked the Moon swallowing Jupiter by hand:** Astronomy
   Katelyn Beecroft in London, Ontario captured the event on the morning of Oct. 6, 2026. The waning crescent Moon passed in front of Jupiter. Source: [astronomy.com](https://www.astronomy.com/x)
"""
FF_HOOK = "A Canadian observer tracked the Moon swallowing Jupiter by hand with an 8-inch Dobsonian."


class TestTheDeck:
    def test_an_outlet_list_on_the_head_never_opens_the_deck(self):
        deck = lt.story_deck(TESLA_DIGEST, TESLA_HOOK)
        assert deck.startswith("Tesla CEO Elon Musk said")
        assert "Business Insider" not in deck

    def test_prose_on_the_head_line_is_kept(self):
        assert not lt._is_outlet_list("the company said on Thursday that output will rise, sharply.")
        assert not lt._is_outlet_list("Reuters, AP")
        assert lt._is_outlet_list("The Verge, Business Insider, Forbes, New York Post")

    def test_an_abbreviation_never_ends_a_sentence(self):
        deck = lt.story_deck(FF_DIGEST, FF_HOOK)
        assert "morning of Oct. 6, 2026." in deck
        assert not deck.rstrip().endswith("Oct.")

    def test_initials_and_real_ends_still_split(self):
        assert lt._deck_sentences("The U.S. Army said so. Then it left.") == [
            "The U.S. Army said so.", "Then it left."]


class TestAlsoLines:
    def test_a_hook_that_fits_prints_whole(self):
        hook = "x " * 40
        hook = hook.strip()
        assert len(hook) <= EMAIL_ALSO_LINE_MAX
        assert nde.also_headline({"hook": hook}) == hook

    def test_the_digests_matching_headline_beats_a_cut(self):
        hook = ("Sixty-seven Israeli lawmakers recommended Gadi Eisenkot to form the next government, "
                "outnumbering the 46 who backed Benjamin Netanyahu in the Knesset count.")
        assert len(hook) > EMAIL_ALSO_LINE_MAX
        story = {"hook": hook, "headlines": ["Eurozone retail sales fell in September",
                                             "Israeli lawmakers recommend Eisenkot over Netanyahu to form government"]}
        assert nde.also_headline(story) == "Israeli lawmakers recommend Eisenkot over Netanyahu to form government"

    def test_no_line_passes_the_limit(self):
        hook = "word " * 60
        assert len(nde.also_headline({"hook": hook.strip()})) <= EMAIL_ALSO_LINE_MAX + 1


class TestNewReaderCopy:
    def test_the_default_note_does_not_scold(self):
        src = (ROOT / "engine" / "nerra_daily_email.py").read_text(encoding="utf-8")
        assert "You don't follow any" not in src
        assert "this email carries the ones you pick" in src


class TestWelcomeEmail:
    def test_patricks_voice(self):
        w = welcome.compose_welcome()
        assert "Hi There," in w.body
        assert "Sincerely,</p>" in w.body and "Patrick</p>" in w.body
        text = re.sub(r"<[^>]+>", " ", w.body)
        # Plain prose: no em dash in what Patrick wrote (the shared footer is not his).
        mine = text.split("Hi There,", 1)[1].split("Patrick", 1)[0]
        assert "—" not in mine
        for word in ("Best,", "Cheers", "Regards", "Hello "):
            assert word not in mine

    def test_every_site_link_is_measured(self):
        w = welcome.compose_welcome()
        assert w.links
        for link in w.links:
            assert "utm_source=newsletter" in link and "utm_medium=email" in link
            campaign = re.search(r"utm_campaign=([^&]+)", link).group(1)
            parsed = parse_campaign_id(campaign)
            assert parsed is not None and parsed.variant == welcome.WELCOME_VARIANT
            assert link.split("?")[0] in w.body or link.replace("&", "&amp;") in w.body

    def test_no_template_condition_and_a_named_pill(self):
        w = welcome.compose_welcome()
        assert "{%" not in w.body
        assert ">Welcome</td>" in w.body
        assert "Weekly digest" not in w.body and "WEEKLY DIGEST" not in w.body
        assert w.subject == "Welcome to Nerra Daily"
        assert w.preheader and w.preheader in w.body


class TestSignupButtons:
    def test_no_signup_button_says_check_your_email(self):
        for path in list((ROOT / "templates").glob("*.j2")) + list((ROOT / "assets" / "js").glob("*.js")):
            assert "Check your email" not in path.read_text(encoding="utf-8"), path
