"""Oct 8 2026. The grading loop could add a lesson and retire one, and it
could say in prose that Mira broke one again, but a broken rule stayed where
it was: Jason Fishman and Piper Martz were both asked a question twice under
an instruction that says never to. A relapse is now counted on the lesson,
the most-broken come first, and the worst three close her prompt.

Also: the end-of-turn silence the scenario reads off the run row was never
written, so every interview ran on the scenario's 1.1 s default.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V = ROOT / "pipelines" / "voices"
sys.path.insert(0, str(V))
sys.path.insert(0, str(ROOT))


def _rows():
    return [
        {"id": "a", "show": "network", "lesson": "Follow the thread.", "relapses": 0},
        {"id": "b", "show": "network", "lesson": "Do not re-ask.", "relapses": 2,
         "last_relapse_at": "2026-10-05T17:00:00Z"},
        {"id": "c", "show": "network", "lesson": "One sign-off.", "relapses": 1},
        {"id": "d", "show": "age_of_ai", "lesson": "Probe the bet.", "relapses": 3},
        {"id": "e", "show": "network", "lesson": "One short sentence.", "relapses": 1},
    ]


def test_the_most_broken_come_first_and_last(monkeypatch):
    import learning
    monkeypatch.setattr(learning, "standing_lessons", lambda slug: _rows())
    block = learning.lessons_block("age_of_ai")
    order = [line[2:] for line in block.splitlines() if line.startswith("- ")]
    assert order[:2] == ["Probe the bet.", "Do not re-ask."]
    assert order[-1] == "Follow the thread."
    recap = learning.relapse_recap("age_of_ai")
    told = [line[2:] for line in recap.splitlines() if line.startswith("- ")]
    assert told[:2] == ["Probe the bet.", "Do not re-ask."] and len(told) == 3
    assert "Follow the thread." not in recap


def test_nothing_broken_means_no_recap(monkeypatch):
    import learning
    monkeypatch.setattr(learning, "standing_lessons",
                        lambda slug: [{"id": "a", "lesson": "x", "relapses": 0}])
    assert learning.relapse_recap("age_of_ai") == ""


def test_the_grader_sees_the_count(monkeypatch):
    import learning
    monkeypatch.setattr(learning, "standing_lessons", lambda slug: _rows())
    text = learning.lessons_for_prompt("age_of_ai")
    assert "broken again 2x) Do not re-ask." in text


def test_a_relapse_is_counted_once_on_an_active_lesson(monkeypatch):
    import learning
    updates = []
    store = {"b": {"id": "b", "relapses": 2}}
    monkeypatch.setattr(learning, "sb_select",
                        lambda table, q: [store[q.split("id=eq.")[1].split("&")[0]]]
                        if q.split("id=eq.")[1].split("&")[0] in store else [])
    monkeypatch.setattr(learning, "sb_update", lambda table, q, body: updates.append((q, body)))
    n = learning.record_relapses("age_of_ai", [{"id": "b", "evidence": "12:03"}, {"id": "zz"}, "", None])
    assert n == 1 and updates[0][0] == "id=eq.b" and updates[0][1]["relapses"] == 3


def test_the_retro_asks_for_relapses_and_post_production_records_them():
    retro = (V / "prompts" / "editorial_passes" / "09_interview_retro.txt").read_text()
    assert '"relapsed": [{"id":' in retro
    post = (V / "post_interview.py").read_text()
    assert 'record_relapses(show.slug, graded.get("relapsed") or [])' in post


def test_her_prompt_ends_on_what_she_keeps_breaking():
    fire = (V / "fire_interviews.py").read_text()
    assert ") + variety_block(show.slug) + relapse_recap(show.slug)" in fire


def test_the_turn_silence_is_written_on_the_run(monkeypatch):
    import fire_interviews
    monkeypatch.delenv("MIRA_TURN_SILENCE_MS", raising=False)
    assert fire_interviews.turn_detection() == {"silence_duration_ms": 1300}
    monkeypatch.setenv("MIRA_TURN_SILENCE_MS", "9000")
    assert fire_interviews.turn_detection() == {"silence_duration_ms": 2500}
    monkeypatch.setenv("MIRA_TURN_SILENCE_MS", "nonsense")
    assert fire_interviews.turn_detection() == {"silence_duration_ms": 1300}
    assert '"turn_detection": turn_detection(),' in (V / "fire_interviews.py").read_text()
    scenario = (ROOT / "voximplant" / "scenarios" / "age_of_ai_interview.js").read_text()
    assert "Number(tuned.silence_duration_ms) || 1100" in scenario   # reads it off the row


def test_a_published_episode_is_never_queued_again():
    """Oct 8 2026, Viktor Popovic: the produce step finished after Ep1 went
    out and wrote "approved" back over "published"."""
    produce = (V / "produce_episode.py").read_text()
    assert "status=neq.published\",\n              {\"status\": \"approved\"})" in produce
    assert "status=neq.published\",\n              {\"status\": \"approved_by_guest\"})" in produce
    publish = (V / "publish_episode.py").read_text()
    assert 'if interview.get("episode_number"):' in publish
    assert 'if not iid or interview.get("episode_number"):' in publish


def test_a_run_staged_for_an_old_slot_is_staged_again():
    """Oct 8 2026: Jason Shumard's and Priyanka Sharma's runs were staged on
    Oct 6 for Oct 7; both moved, and the old runs would have opened a week
    later with a week-old prompt."""
    fire = (V / "fire_interviews.py").read_text()
    assert '"disconnect_reason": "re-staged: the interview moved"' in fire
    assert 'and _parse(r["scheduled_for"]) != when]' in fire
    assert "if [r for r in active if r not in stale]:" in fire
