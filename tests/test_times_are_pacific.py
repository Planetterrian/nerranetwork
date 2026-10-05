"""Sept 30 2026: Patrick is in Vancouver. Every time in an email or a page
is Pacific Time, with the guest's own clock alongside when we know it."""
import re
from pathlib import Path

from pipelines.voices.common import pacific_time

ROOT = Path(__file__).resolve().parent.parent


def test_pacific_with_the_guests_clock():
    assert pacific_time("2026-10-05T20:45:00Z") == "Monday, October 5 at 1:45 PM Pacific Time"
    assert pacific_time("2026-10-05T20:45:00Z", "America/New_York") == \
        "Monday, October 5 at 1:45 PM Pacific Time (4:45 PM EDT where you are)"
    assert pacific_time("2026-10-05T20:45:00Z", "America/Los_Angeles") == \
        "Monday, October 5 at 1:45 PM Pacific Time"
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
