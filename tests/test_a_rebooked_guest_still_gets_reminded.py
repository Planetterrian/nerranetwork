"""Oct 5 2026 (Jon Cheney): rebooked onto his old row, he kept the old brief
and stayed `scheduled`, so the T-2h reminder never went."""
from pathlib import Path

SRC = (Path(__file__).resolve().parents[1] / "pipelines" / "voices" / "generate_briefs.py").read_text(encoding="utf-8")


def test_an_existing_brief_marks_the_row_briefed():
    i = SRC.index("if existing:")
    block = SRC[i:i + 700]
    assert 'interview.get("status") == "scheduled"' in block
    assert '{"status": "briefed"}' in block
