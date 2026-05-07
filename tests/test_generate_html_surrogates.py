"""Drift guard for the lone-surrogate scrubber in ``generate_html``.

Operator caught (UC + Tesla blog generation, May 7 2026) the daily site
rebuild aborting with::

    UnicodeEncodeError: 'utf-8' codec can't encode characters in position
    73685-73686: surrogates not allowed

at ``generate_html.py:1850`` (``out_path.write_text(html, encoding="utf-8")``).
A single LLM-emitted lone UTF-16 surrogate killed the whole blog
regeneration — losing every other show's blog post in the same run.

The fix scrubs lone surrogates (U+D800–U+DFFF) at every HTML/XML write
boundary in ``generate_html``. These tests pin that the scrubber exists
and is correct; if the regex is removed or weakened, daily builds break
silently the next time an LLM emits a malformed surrogate.
"""

from __future__ import annotations


class TestStripLoneSurrogates:

    def test_helper_exists(self):
        from generate_html import _strip_lone_surrogates
        assert callable(_strip_lone_surrogates)

    def test_strips_high_surrogate(self):
        from generate_html import _strip_lone_surrogates
        # U+D83D in isolation — a high surrogate without a paired low
        # surrogate. Common when an LLM truncates an emoji code unit.
        bad = "Hello \ud83d world"
        assert _strip_lone_surrogates(bad) == "Hello  world"

    def test_strips_low_surrogate(self):
        from generate_html import _strip_lone_surrogates
        bad = "Quote \udc00 mark"
        assert _strip_lone_surrogates(bad) == "Quote  mark"

    def test_preserves_legitimate_emoji(self):
        """A properly-paired emoji (U+D83D U+DE80 = 🚀) is a SINGLE
        non-BMP code point in Python strings; the regex matches actual
        surrogate code points, not the encoded form, so emoji survive."""
        from generate_html import _strip_lone_surrogates
        text = "Tesla 🚀 launches in three cities."
        assert _strip_lone_surrogates(text) == text

    def test_preserves_cyrillic(self):
        from generate_html import _strip_lone_surrogates
        text = "Финансы Просто, выпуск 32, шестое мая."
        assert _strip_lone_surrogates(text) == text

    def test_empty_input(self):
        from generate_html import _strip_lone_surrogates
        assert _strip_lone_surrogates("") == ""

    def test_idempotent(self):
        from generate_html import _strip_lone_surrogates
        bad = "a\ud800b🚭c"  # lone D800, then a paired emoji
        once = _strip_lone_surrogates(bad)
        twice = _strip_lone_surrogates(once)
        assert once == twice

    def test_round_trips_through_utf8(self):
        """The scrubbed output must encode cleanly to UTF-8 — that's the
        whole point of the helper. Pre-fix, ``write_text`` raised
        ``UnicodeEncodeError`` on this exact input."""
        from generate_html import _strip_lone_surrogates
        bad = "<html>contents 𐀀 plus lone \ud83d end</html>"
        # ``"𐀀"`` is a high+low surrogate PAIR, but Python
        # strings are UCS-4 so this is two separate surrogate code points
        # (NOT a single non-BMP code point). The scrubber strips both.
        scrubbed = _strip_lone_surrogates(bad)
        # Must encode without raising.
        scrubbed.encode("utf-8")
        # No surrogate code points survive.
        for ch in scrubbed:
            assert not (0xD800 <= ord(ch) <= 0xDFFF)
