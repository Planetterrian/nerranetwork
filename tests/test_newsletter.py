"""Tests for engine.newsletter – markdown-to-email conversion and Buttondown API.

Covers header conversion, inline formatting, HTML structure, send_newsletter,
and send_show_newsletter with mocked HTTP calls and environment variables.
"""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from engine.newsletter import (
    _md_inline,
    convert_digest_to_email_html,
    send_newsletter,
    send_show_newsletter,
)


class TestConvertDigestHeaders(unittest.TestCase):
    """h1, h2, h3 header conversion with inline styles."""

    def test_h1_conversion(self):
        html = convert_digest_to_email_html("# Main Title")
        self.assertIn("<h1", html)
        self.assertIn("Main Title", html)
        self.assertIn("</h1>", html)

    def test_h1_has_inline_style(self):
        html = convert_digest_to_email_html("# Styled")
        self.assertIn('style="', html.split("<h1")[1].split(">")[0])

    def test_h2_conversion(self):
        html = convert_digest_to_email_html("## Sub Title")
        self.assertIn("<h2", html)
        self.assertIn("Sub Title", html)
        self.assertIn("</h2>", html)

    def test_h2_has_inline_style(self):
        html = convert_digest_to_email_html("## Styled")
        self.assertIn('style="', html.split("<h2")[1].split(">")[0])

    def test_h3_conversion(self):
        html = convert_digest_to_email_html("### Third Level")
        self.assertIn("<h3", html)
        self.assertIn("Third Level", html)
        self.assertIn("</h3>", html)

    def test_h3_has_inline_style(self):
        html = convert_digest_to_email_html("### Styled")
        self.assertIn('style="', html.split("<h3")[1].split(">")[0])

    def test_h1_color(self):
        html = convert_digest_to_email_html("# Title")
        self.assertIn("#1a1a2e", html)

    def test_h2_color(self):
        html = convert_digest_to_email_html("## Title")
        self.assertIn("#2d3748", html)

    def test_h3_color(self):
        html = convert_digest_to_email_html("### Title")
        self.assertIn("#4a5568", html)


class TestConvertDigestFormatting(unittest.TestCase):
    """Bold, italic, links, bullets, numbered lists, separators, empty lines."""

    def test_bold_text(self):
        html = convert_digest_to_email_html("This is **bold** text")
        self.assertIn("<strong>bold</strong>", html)

    def test_italic_text(self):
        html = convert_digest_to_email_html("This is *italic* text")
        self.assertIn("<em>italic</em>", html)

    def test_link_conversion(self):
        html = convert_digest_to_email_html("[Click here](https://example.com)")
        self.assertIn('href="https://example.com"', html)
        self.assertIn("Click here", html)
        self.assertIn("</a>", html)

    def test_link_has_inline_style(self):
        html = convert_digest_to_email_html("[Link](https://example.com)")
        self.assertIn("color: #2b6cb0", html)

    def test_bullet_list(self):
        html = convert_digest_to_email_html("- First item\n- Second item")
        # Bullets are converted to paragraph with bullet character
        self.assertEqual(html.count("\u2022"), 2)
        self.assertIn("First item", html)
        self.assertIn("Second item", html)

    def test_numbered_list(self):
        html = convert_digest_to_email_html("1. First\n2. Second")
        self.assertIn("1. First", html)
        self.assertIn("2. Second", html)

    def test_separator_triple_dash(self):
        html = convert_digest_to_email_html("---")
        self.assertIn("<hr", html)

    def test_separator_unicode_bar(self):
        html = convert_digest_to_email_html("\u2501\u2501\u2501")
        self.assertIn("<hr", html)

    def test_empty_line_becomes_br(self):
        html = convert_digest_to_email_html("Line one\n\nLine two")
        self.assertIn("<br>", html)

    def test_plain_text_becomes_paragraph(self):
        html = convert_digest_to_email_html("Just some text")
        self.assertIn("<p", html)
        self.assertIn("Just some text", html)
        self.assertIn("</p>", html)


class TestConvertDigestStructure(unittest.TestCase):
    """Generated HTML has proper document structure."""

    def test_has_doctype(self):
        html = convert_digest_to_email_html("Hello")
        self.assertTrue(html.startswith("<!DOCTYPE html>"))

    def test_has_html_tag(self):
        html = convert_digest_to_email_html("Hello")
        self.assertIn("<html>", html)
        self.assertIn("</html>", html)

    def test_has_head_tag(self):
        html = convert_digest_to_email_html("Hello")
        self.assertIn("<head>", html)
        self.assertIn("</head>", html)

    def test_has_body_tag(self):
        html = convert_digest_to_email_html("Hello")
        self.assertIn("<body", html)
        self.assertIn("</body>", html)

    def test_body_has_font_family(self):
        html = convert_digest_to_email_html("Hello")
        self.assertIn("font-family", html)

    def test_body_has_max_width(self):
        html = convert_digest_to_email_html("Hello")
        self.assertIn("max-width: 600px", html)

    def test_has_charset_meta(self):
        html = convert_digest_to_email_html("Hello")
        self.assertIn('charset="utf-8"', html)


class TestMdInline(unittest.TestCase):
    """Test _md_inline independently for bold, italic, links."""

    def test_bold(self):
        result = _md_inline("**hello**")
        self.assertEqual(result, "<strong>hello</strong>")

    def test_italic(self):
        result = _md_inline("*world*")
        self.assertEqual(result, "<em>world</em>")

    def test_link(self):
        result = _md_inline("[text](https://url.com)")
        self.assertIn('href="https://url.com"', result)
        self.assertIn("text</a>", result)

    def test_bold_and_italic_together(self):
        result = _md_inline("**bold** and *italic*")
        self.assertIn("<strong>bold</strong>", result)
        self.assertIn("<em>italic</em>", result)

    def test_no_markdown_returns_unchanged(self):
        result = _md_inline("plain text")
        self.assertEqual(result, "plain text")

    def test_multiple_links(self):
        result = _md_inline("[a](http://a.com) [b](http://b.com)")
        self.assertIn('href="http://a.com"', result)
        self.assertIn('href="http://b.com"', result)


class TestSendNewsletter(unittest.TestCase):
    """Mock requests.post for success and failure scenarios."""

    @patch("engine.newsletter.requests.post")
    def test_success_200_returns_email_id(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "email-123"}
        mock_post.return_value = mock_resp

        result = send_newsletter("Subject", "Body", api_key="key123")
        self.assertEqual(result, "email-123")

    @patch("engine.newsletter.requests.post")
    def test_success_201_returns_email_id(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"id": "email-456"}
        mock_post.return_value = mock_resp

        result = send_newsletter("Subject", "Body", api_key="key123")
        self.assertEqual(result, "email-456")

    @patch("engine.newsletter.requests.post")
    def test_failure_returns_none(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "Bad request"
        mock_post.return_value = mock_resp

        result = send_newsletter("Subject", "Body", api_key="key123")
        self.assertIsNone(result)

    @patch("engine.newsletter.requests.post")
    def test_sends_correct_payload(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"id": "x"}
        mock_post.return_value = mock_resp

        send_newsletter("My Subject", "My Body", api_key="mykey", status="draft")
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        self.assertEqual(call_kwargs.kwargs["json"]["subject"], "My Subject")
        self.assertEqual(call_kwargs.kwargs["json"]["body"], "My Body")
        self.assertEqual(call_kwargs.kwargs["json"]["status"], "draft")

    @patch("engine.newsletter.requests.post")
    def test_sends_auth_header(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"id": "x"}
        mock_post.return_value = mock_resp

        send_newsletter("Subj", "Body", api_key="secret-key")
        call_kwargs = mock_post.call_args
        self.assertEqual(
            call_kwargs.kwargs["headers"]["Authorization"],
            "Token secret-key",
        )

    @patch("engine.newsletter.requests.post")
    def test_missing_id_returns_unknown(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {}
        mock_post.return_value = mock_resp

        result = send_newsletter("Subj", "Body", api_key="key")
        self.assertEqual(result, "unknown")

    @patch("engine.newsletter.requests.get")
    @patch("engine.newsletter.requests.post")
    def test_zero_recipients_with_tags_returns_none(self, mock_post, mock_get):
        """Buttondown can accept the email and send to 0 subscribers when
        tag filters match nobody. That's a misconfiguration, not success."""
        import engine.newsletter as _nl
        _nl._TAG_ID_CACHE.clear()
        # Resolve the tag name -> id so the flow reaches the POST and we
        # actually exercise the num_recipients==0 branch (not the
        # unresolved-tag early return).
        get_resp = MagicMock()
        get_resp.status_code = 200
        get_resp.json.return_value = {
            "results": [{"name": "ghost-tag", "id": "tag_ghost"}], "next": None,
        }
        mock_get.return_value = get_resp

        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"id": "eid", "num_recipients": 0}
        mock_post.return_value = mock_resp

        result = send_newsletter(
            "Subj", "Body", api_key="key", tags=["ghost-tag"],
        )
        self.assertIsNone(result)

    @patch("engine.newsletter.requests.post")
    def test_zero_recipients_without_tags_still_succeeds(self, mock_post):
        """No tag filter means the zero count likely reflects API response
        shape, not a misconfiguration — don't fail the call."""
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"id": "eid", "num_recipients": 0}
        mock_post.return_value = mock_resp

        result = send_newsletter("Subj", "Body", api_key="key")
        self.assertEqual(result, "eid")

    @patch("engine.newsletter.requests.post")
    def test_default_status_is_about_to_send(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"id": "x"}
        mock_post.return_value = mock_resp

        send_newsletter("Subj", "Body", api_key="key")
        call_kwargs = mock_post.call_args
        self.assertEqual(call_kwargs.kwargs["json"]["status"], "about_to_send")


class TestSendShowNewsletter(unittest.TestCase):
    """Mock config with newsletter enabled/disabled and missing API key."""

    def _make_config(self, enabled=True, api_key_env="BUTTONDOWN_KEY", name="TestShow"):
        newsletter = SimpleNamespace(enabled=enabled, api_key_env=api_key_env)
        return SimpleNamespace(newsletter=newsletter, name=name)

    @patch("engine.newsletter.send_newsletter")
    @patch("engine.newsletter.os.getenv")
    def test_enabled_with_key_sends(self, mock_getenv, mock_send):
        mock_getenv.return_value = "real-api-key"
        mock_send.return_value = "email-789"
        config = self._make_config()

        result = send_show_newsletter("digest text", config, 42, "2025-01-15")
        self.assertEqual(result, "email-789")
        mock_send.assert_called_once()

    @patch("engine.newsletter._can_send_now", return_value=True)
    @patch("engine.newsletter._record_send")
    @patch("engine.newsletter.send_newsletter")
    @patch("engine.newsletter.os.getenv")
    def test_subject_format_uses_build_subject_line(
        self, mock_getenv, mock_send, _mock_record, _mock_can_send,
    ):
        """Spec v2 §3: daily subject is ``<hook> · <show> <emoji>`` —
        the old ``f"{config.name}: {hook}"`` format was broken because
        the show name preceded a long unbounded hook, getting Gmail-
        truncated. Episode number lives in the hero pill, not the
        subject."""
        mock_getenv.return_value = "key"
        mock_send.return_value = "id"
        ns = self._make_config(name="Tesla Shorts Time")
        ns.slug = "tesla"

        send_show_newsletter(
            "digest", ns, 456, "2026-05-02",
            hook="Cybercab production begins in Texas",
        )
        assert mock_send.call_args is not None, (
            "send_newsletter was never called"
        )
        subject = mock_send.call_args.kwargs["subject"]
        # Hook is present (possibly truncated to 50 chars by the daily cap).
        assert "Cybercab" in subject
        # Show short label is present (Tesla's is "Tesla Shorts").
        assert "Tesla Shorts" in subject
        # Subject does NOT contain the episode number — that lives in
        # the hero pill ("Ep 456 · May 2, 2026").
        assert "Episode 456" not in subject
        # Spec §3: hard cap on overall subject length.
        assert len(subject) <= 100

    def test_disabled_newsletter_returns_none(self):
        config = self._make_config(enabled=False)
        result = send_show_newsletter("digest", config, 1, "2025-01-01")
        self.assertIsNone(result)

    def test_no_newsletter_attr_returns_none(self):
        config = SimpleNamespace(name="Show")  # no newsletter attribute
        result = send_show_newsletter("digest", config, 1, "2025-01-01")
        self.assertIsNone(result)

    @patch("engine.newsletter.os.getenv")
    def test_missing_api_key_returns_none(self, mock_getenv):
        mock_getenv.return_value = ""
        config = self._make_config()
        result = send_show_newsletter("digest", config, 1, "2025-01-01")
        self.assertIsNone(result)

    @patch("engine.newsletter.os.getenv")
    def test_whitespace_only_api_key_returns_none(self, mock_getenv):
        mock_getenv.return_value = "   "
        config = self._make_config()
        result = send_show_newsletter("digest", config, 1, "2025-01-01")
        self.assertIsNone(result)

    @patch("engine.newsletter.send_newsletter")
    @patch("engine.newsletter.os.getenv")
    def test_passes_api_key_from_env(self, mock_getenv, mock_send):
        mock_getenv.return_value = "env-key-value"
        mock_send.return_value = "id"
        config = self._make_config()

        send_show_newsletter("digest", config, 1, "2025-01-01")
        call_kwargs = mock_send.call_args
        self.assertEqual(call_kwargs.kwargs["api_key"], "env-key-value")


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# Hardened error semantics added during P0/P1 cleanup
# ---------------------------------------------------------------------------

def test_validate_api_key_returns_false_on_5xx(monkeypatch):
    """5xx Buttondown response should NOT pass validation (was previously
    a silent True, creating false confidence pre-flight)."""
    from engine import newsletter

    class _Resp:
        status_code = 503
        text = "service unavailable"

    monkeypatch.setattr(newsletter.requests, "get",
                        lambda *a, **kw: _Resp())
    assert newsletter.validate_api_key("any-key") is False


def test_validate_api_key_returns_false_on_429(monkeypatch):
    """Rate-limit during pre-flight = unknown key health = treat as fail."""
    from engine import newsletter

    class _Resp:
        status_code = 429
        text = "rate limited"

    monkeypatch.setattr(newsletter.requests, "get",
                        lambda *a, **kw: _Resp())
    assert newsletter.validate_api_key("any-key") is False


def test_validate_api_key_returns_false_on_403(monkeypatch):
    """403 = bad permissions = clearly invalid key."""
    from engine import newsletter

    class _Resp:
        status_code = 403
        text = "forbidden"

    monkeypatch.setattr(newsletter.requests, "get",
                        lambda *a, **kw: _Resp())
    assert newsletter.validate_api_key("any-key") is False


def test_validate_api_key_returns_true_on_200(monkeypatch):
    from engine import newsletter

    class _Resp:
        status_code = 200
        text = "[]"

    monkeypatch.setattr(newsletter.requests, "get",
                        lambda *a, **kw: _Resp())
    assert newsletter.validate_api_key("any-key") is True


def test_send_newsletter_rejects_invalid_status(monkeypatch):
    """Catch typos in newsletter.status before hitting Buttondown's 400."""
    from engine import newsletter

    # Sentinel — should never be called because we reject the status first.
    def _no_post(*a, **kw):
        raise AssertionError("send_newsletter should not call requests.post"
                             " for invalid status")

    monkeypatch.setattr(newsletter.requests, "post", _no_post)
    out = newsletter.send_newsletter(
        subject="t", body="b", api_key="key",
        status="publish",  # typo
    )
    assert out is None


# ---------------------------------------------------------------------------
# Buttondown filter shape — the v2 tree schema introduced after a
# ``{operator, predicates}`` payload started returning HTTP 422
# ---------------------------------------------------------------------------

def test_send_newsletter_uses_v2_filter_tree_when_tags_set(monkeypatch):
    """When tags are passed, the request body's ``filters`` must
    match Buttondown's current ``{filters, groups, predicate}``
    schema — old ``{operator, predicates}`` was rejected with
    HTTP 422 missing-field errors on filters/groups/predicate.

    May 31 2026: each leaf ``value`` must be the resolved tag
    *identifier* (TypeID), not the display name — passing the name
    returns HTTP 422 "Tag filters must be valid tag identifiers" and
    blocked every show network-wide. The name->id map comes from
    GET /v1/tags."""
    import json as _json
    from engine import newsletter
    newsletter._TAG_ID_CACHE.clear()

    captured = {}

    # GET /v1/tags resolves the display names to TypeIDs.
    class _GetResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "results": [
                    {"name": "Tesla Shorts Time", "id": "tag_tesla"},
                    {"name": "Privet Russian", "id": "tag_privet"},
                ],
                "next": None,
            }

    class _Resp:
        status_code = 200

        def json(self):
            return {"id": "em_test", "num_recipients": 1}

    def _fake_post(url, headers, json, timeout):
        captured["payload"] = _json.loads(_json.dumps(json))
        return _Resp()

    monkeypatch.setattr(newsletter.requests, "get", lambda *a, **kw: _GetResp())
    monkeypatch.setattr(newsletter.requests, "post", _fake_post)

    out = newsletter.send_newsletter(
        subject="Subject",
        body="Body",
        api_key="key",
        tags=["Tesla Shorts Time", "Privet Russian"],
    )
    assert out == "em_test"

    filters = captured["payload"]["filters"]
    # The required v2 keys.
    assert set(filters.keys()) == {"filters", "groups", "predicate"}
    # Buttondown's predicate enum: "and" or "or" (not "any"/"all").
    assert filters["predicate"] in {"and", "or"}
    assert filters["groups"] == []
    # Each tag becomes a leaf condition whose value is the resolved
    # tag IDENTIFIER (TypeID), NOT the display name.
    leaf_values = {f["value"] for f in filters["filters"]}
    assert leaf_values == {"tag_tesla", "tag_privet"}
    # No leftover keys from the old schema. May 26 2026: Buttondown
    # tightened the leaf-condition field enum — ``"tag"`` now 422s,
    # ``"subscriber.tags"`` is the accepted form, and the operator
    # for list membership is ``"contains"``.
    for leaf in filters["filters"]:
        assert leaf["field"] == "subscriber.tags"
        assert leaf["operator"] == "contains"
    # Old keys must NOT appear.
    assert "predicates" not in filters
    assert "operator" not in filters


def test_send_newsletter_refuses_send_when_tags_unresolvable(monkeypatch):
    """If no tag name resolves to a Buttondown tag ID, the send must be
    refused (return None) rather than fall through to an unfiltered
    network-wide blast to every subscriber."""
    from engine import newsletter
    newsletter._TAG_ID_CACHE.clear()

    class _GetResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"results": [], "next": None}  # no tags exist

    def _no_post(*a, **kw):
        raise AssertionError("must not POST when no tag id resolves")

    monkeypatch.setattr(newsletter.requests, "get", lambda *a, **kw: _GetResp())
    monkeypatch.setattr(newsletter.requests, "post", _no_post)

    out = newsletter.send_newsletter(
        subject="s", body="b", api_key="key", tags=["Nonexistent Show"],
    )
    assert out is None


def test_resolve_tag_ids_maps_names_to_ids(monkeypatch):
    """_resolve_tag_ids paginates GET /v1/tags and maps name -> id."""
    from engine import newsletter
    newsletter._TAG_ID_CACHE.clear()

    pages = [
        {"results": [{"name": "A", "id": "tag_a"}], "next": "https://api.buttondown.com/v1/tags?page=2"},
        {"results": [{"name": "B", "id": "tag_b"}], "next": None},
    ]
    calls = {"n": 0}

    class _GetResp:
        status_code = 200

        def __init__(self, body):
            self._body = body

        def raise_for_status(self):
            return None

        def json(self):
            return self._body

    def _fake_get(*a, **kw):
        body = pages[calls["n"]]
        calls["n"] += 1
        return _GetResp(body)

    monkeypatch.setattr(newsletter.requests, "get", _fake_get)
    out = newsletter._resolve_tag_ids(["A", "B"], "key")
    assert out == {"A": "tag_a", "B": "tag_b"}
    assert calls["n"] == 2  # followed the `next` cursor


def test_send_newsletter_omits_filters_when_no_tags(monkeypatch):
    """No tags = no ``filters`` key in the payload — sends to all
    subscribers. (Empty filters would also work, but omitting is
    cleaner and matches the existing behaviour.)"""
    from engine import newsletter

    captured = {}

    class _Resp:
        status_code = 200

        def json(self):
            return {"id": "em_test", "num_recipients": 5}

    def _fake_post(url, headers, json, timeout):
        captured["payload"] = json
        return _Resp()

    monkeypatch.setattr(newsletter.requests, "post", _fake_post)

    newsletter.send_newsletter(
        subject="Subject", body="Body", api_key="key", tags=None,
    )
    assert "filters" not in captured["payload"]


def test_send_newsletter_sets_live_dangerously_header(monkeypatch):
    """Buttondown requires X-Buttondown-Live-Dangerously: true on the
    first email POST with status="about_to_send" for an API key.
    Without it: HTTP 400 sending_requires_confirmation. We send it
    on every request because we always mean to send."""
    from engine import newsletter

    captured = {}

    class _Resp:
        status_code = 200

        def json(self):
            return {"id": "em_test", "num_recipients": 1}

    def _fake_post(url, headers, json, timeout):
        captured["headers"] = headers
        return _Resp()

    monkeypatch.setattr(newsletter.requests, "post", _fake_post)

    newsletter.send_newsletter(
        subject="s", body="b", api_key="key", tags=None,
    )
    assert captured["headers"].get("X-Buttondown-Live-Dangerously") == "true"


# ---------------------------------------------------------------------------
# Pre-send contrast tripwire — Phase 2.2 (May 2026 audit) hard-block
# ---------------------------------------------------------------------------

def test_contrast_failure_blocks_send_and_logs_error(monkeypatch, caplog):
    """A rendered body with a guaranteed WCAG AA failure must cause
    ``send_show_newsletter`` to return ``None`` and emit a
    ``logger.error`` so the operator notices. Pre-bump (#7C5CFF) the
    block was a soft warning; post-bump (#6B47FF) it is a hard block."""
    import logging

    from engine import newsletter

    bad_html = (
        "<html><body>"
        "<p style=\"color:#cccccc;background:#ffffff\">low contrast</p>"
        "</body></html>"
    )

    monkeypatch.setattr(newsletter, "_can_send_now", lambda *a, **kw: True)
    monkeypatch.setattr(newsletter.os, "getenv", lambda *a, **kw: "k")
    monkeypatch.setattr(
        newsletter, "_adjacent_shows_for", lambda *a, **kw: [],
    )

    from engine import newsletter_template as _nt
    monkeypatch.setattr(_nt, "wrap_with_branding", lambda *a, **kw: bad_html)
    monkeypatch.setattr(
        _nt, "build_subject_line", lambda *a, **kw: "Subject",
    )

    sent = {}

    def _no_send(**kw):
        sent["called"] = True
        return "should-not-happen"

    monkeypatch.setattr(newsletter, "send_newsletter", _no_send)

    config = SimpleNamespace(
        newsletter=SimpleNamespace(
            enabled=True,
            api_key_env="BUTTONDOWN_KEY",
            tag="",
            requires_financial_disclaimer=False,
            status="about_to_send",
        ),
        name="Test Show",
        slug="testshow",
    )

    with caplog.at_level(logging.ERROR, logger="engine.newsletter"):
        result = newsletter.send_show_newsletter(
            "digest", config, 1, "2026-05-05",
        )

    assert result is None, "Hard-block must return None on contrast failure"
    assert "called" not in sent, (
        "send_newsletter must NOT be invoked when contrast blocks the send"
    )
    assert any(
        "contrast issues" in rec.getMessage().lower()
        and rec.levelno >= logging.ERROR
        for rec in caplog.records
    ), "Expected a logger.error for the blocking contrast failure"


# ---------------------------------------------------------------------------
# Drift guard: the cross-network adjacency map must live under ``newsletter:``
# in shows/_defaults.yaml. It was originally shipped mis-indented under
# ``cost_circuit_breakers:`` (June 2026 review), which made
# engine.newsletter._adjacent_shows_for and
# engine.synthesizer._load_network_adjacencies silently read an empty map —
# degrading the cross-network module on every daily + weekly send.
# ---------------------------------------------------------------------------

_NON_SHOW_YAML_STEMS = {
    "_defaults", "_blocked_sources", "pronunciation_map",
    "network_meta", "scaffold_pending",
}


def _all_show_slugs():
    from pathlib import Path
    return sorted(
        p.stem for p in Path("shows").glob("*.yaml")
        if p.stem not in _NON_SHOW_YAML_STEMS
        and not p.stem.endswith("_template")
        and not p.stem.startswith("_")
    )


def test_defaults_yaml_network_adjacencies_under_newsletter():
    import yaml
    from pathlib import Path

    data = yaml.safe_load(
        Path("shows/_defaults.yaml").read_text(encoding="utf-8")
    ) or {}
    nl = data.get("newsletter") or {}
    adj = nl.get("network_adjacencies")
    assert isinstance(adj, dict) and adj, (
        "newsletter.network_adjacencies missing/empty in shows/_defaults.yaml "
        "— the cross-network email module reads it from exactly this path"
    )
    slugs = set(_all_show_slugs())
    assert slugs <= set(adj.keys()), (
        f"network_adjacencies missing shows: {sorted(slugs - set(adj.keys()))}"
    )
    # Every referenced sibling must itself be a real show slug.
    for slug, sisters in adj.items():
        for sister in sisters:
            assert sister in slugs, (
                f"network_adjacencies[{slug}] references unknown show {sister!r}"
            )
    # And the newsletter-composition keys moved in the same fix must be
    # readable from the same block.
    for key in ("requires_financial_disclaimer", "short_label", "emoji",
                "newsletter_start_date", "adjacent_shows"):
        assert key in nl, f"newsletter.{key} missing from shows/_defaults.yaml"


def test_synthesizer_reads_nonempty_adjacencies():
    from engine.synthesizer import _load_network_adjacencies

    adj = _load_network_adjacencies()
    assert adj.get("tesla"), (
        "engine.synthesizer._load_network_adjacencies returned an empty map "
        "for tesla — adjacency block likely mis-indented again"
    )
