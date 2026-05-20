"""Tests for episode-1 LLM appendix injection."""

from engine.first_episode import first_episode_digest_appendix


def test_debut_mentions_show_name():
    text = first_episode_digest_appendix(1, "My New Show")
    assert "My New Show" in text
    assert "first episode" in text.lower() or "FIRST EPISODE" in text
