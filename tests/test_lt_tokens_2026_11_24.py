"""Nov 24 2026: the landing tokens reach join.html and the account save bar.

join.html styles 70 rules with ``--lt-*`` custom properties and has no
``.lt-page`` ancestor, so every one was undefined on the paid page.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_tokens_are_defined_on_lt_tokens():
    css = _read("templates/_landing_styles.html.j2")
    assert ".lt-page, .lt-tokens {" in css
    block = css.split(".lt-page, .lt-tokens {", 1)[1].split("}", 1)[0]
    assert "--lt-cyan" in block and "--lt-head" in block
    # The front page's padding stays on .lt-page alone.
    assert "padding-top" not in block


def test_join_template_and_page_carry_the_tokens():
    assert 'class="jn lt-tokens"' in _read("templates/join_page.html.j2")
    page = _read("join.html")
    assert 'class="jn lt-tokens"' in page
    assert ".lt-page, .lt-tokens {" in page


def test_account_save_bar_carries_the_tokens():
    assert 'class="nn-savebar lt-tokens"' in _read("templates/account_page.html.j2")
    page = _read("account.html")
    assert 'class="nn-savebar lt-tokens"' in page
    assert ".lt-page, .lt-tokens {" in page


def test_nerra_daily_picker_offers_only_shows_the_email_carries():
    import generate_html
    from engine.nerra_daily_email import email_show_tags

    picks = generate_html._email_pick_shows()
    assert picks and {p["slug"] for p in picks} <= set(email_show_tags())
    assert all(p["newsletter_tag"] for p in picks)
    assert "nerra_daily" not in {p["slug"] for p in picks}
