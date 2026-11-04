"""Sept 30 2026: Patrick is in Vancouver. Every time in an email or a page
is Vancouver time, with the guest's own clock alongside when we know it."""
import re
from pathlib import Path

from pipelines.voices.common import pacific_time

ROOT = Path(__file__).resolve().parent.parent


def test_pacific_with_the_guests_clock():
    assert pacific_time("2026-10-05T20:45:00Z") == "Monday, October 5 at 1:45 PM Vancouver time"
    assert pacific_time("2026-10-05T20:45:00Z", "America/New_York") == \
        "Monday, October 5 at 1:45 PM Vancouver time (4:45 PM EDT where you are)"
    assert pacific_time("2026-10-05T20:45:00Z", "America/Los_Angeles") == \
        "Monday, October 5 at 1:45 PM Vancouver time"
    assert pacific_time("2026-12-05T03:00:00Z", date_only=True) == "Friday, December 4"
    assert pacific_time("not a time") == ""


def test_no_mail_says_utc_any_more():
    for path in ["pipelines/voices/fire_interviews.py", "pipelines/voices/generate_briefs.py",
                 "pipelines/producer/guest_reply.py", "pipelines/producer/digest.py"]:
        src = (ROOT / path).read_text()
        assert not re.search(r'UTC \(the time|\+ " UTC"', src), path
    worker = (ROOT / "workers" / "voices" / "src" / "index.ts").read_text()
    assert "toUTCString" not in worker
    assert "function pacificTime(" in worker and "guest_timezone: attendeeTimeZone(p)" in worker


def test_vancouver_is_not_called_pacific_after_bc_left_dst():
    """Nov 4 2026: B.C. stays on UTC-7 from Nov 1 2026, so in winter it is an
    hour ahead of California. A California guest read "9:30 AM Pacific Time
    (8:30 AM PST where you are)". The label is the city; the guest's own
    clock still follows in brackets."""
    import datetime as _dt
    from zoneinfo import ZoneInfo

    import pytest

    winter = _dt.datetime(2026, 11, 4, 16, 30, tzinfo=_dt.timezone.utc)
    if winter.astimezone(ZoneInfo("America/Vancouver")).utcoffset() != _dt.timedelta(hours=-7):
        pytest.skip("this runtime's tzdata predates 2026c (B.C. permanent UTC-7)")
    assert pacific_time("2026-11-04T16:30:00Z", "America/Los_Angeles") == (
        "Wednesday, November 4 at 9:30 AM Vancouver time (8:30 AM PST where you are)")
    assert pacific_time("2026-11-04T16:30:00Z", "America/Vancouver") == (
        "Wednesday, November 4 at 9:30 AM Vancouver time")


def test_no_surface_calls_the_network_zone_pacific_time():
    for path in ["pipelines/voices/common.py", "workers/voices/src/index.ts",
                 "pipelines/producer/prompts/followup_reply.txt",
                 "templates/contact.html.j2"]:
        src = (ROOT / path).read_text()
        code = "\n".join(l for l in src.splitlines()
                         if not l.lstrip().startswith(("#", "//")))
        assert "Pacific Time" not in code, path
