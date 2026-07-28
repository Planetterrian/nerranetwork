"""Drift guards for the billing-stop detector.

Incident, 28 July 2026: the xAI account crossed its monthly spending
limit mid-run. Chat completions succeeded, TTS returned 403, and the
pipeline died at synthesis — after fetching, generating a digest,
expanding it, generating a script and retrying that script. Every show
in the matrix repeated the whole paid generation stage before hitting
the same wall.

The pre-flight ping talks to the same billing account, so shows two
through sixteen could have stopped immediately. They didn't, because the
ping treats every failure as a warning.

Two ways to get this wrong, and both are worse than the bug:

* **Too narrow** — miss the billing wording and keep burning money.
* **Too broad** — treat any 403 as a billing stop and cancel a whole
  day of episodes over a revoked key or a transient error.

So the detector keys on the provider's wording, never on the status
code, and this file pins both directions.
"""

from __future__ import annotations

import pytest

from engine.provider_quota import is_quota_exhausted, quota_message

# Verbatim from the incident log.
XAI_BODY = (
    '{"code":"The caller does not have permission to execute the specified '
    'operation","error":"Your team fae4735c-ce67-4a51-933c-1fecf062fe21 has '
    "either used all available credits or reached its monthly spending limit. "
    "To continue making API requests, please purchase more credits or raise "
    'your spending limit."}'
)


class TestRecognisesABillingStop:
    def test_the_real_xai_403_body(self):
        assert is_quota_exhausted(XAI_BODY)

    def test_wrapped_in_the_exception_the_pipeline_actually_raises(self):
        class GrokTTSClientError(Exception):
            def __init__(self, message, status_code=None, body=None):
                super().__init__(message)
                self.status_code = status_code
                self.body = body

        exc = GrokTTSClientError(f"Grok TTS returned 403: {XAI_BODY}",
                                 status_code=403, body=XAI_BODY)
        assert is_quota_exhausted(exc)

    def test_reads_the_body_attribute_when_the_message_is_terse(self):
        class Err(Exception):
            body = XAI_BODY

        assert is_quota_exhausted(Err("403"))

    @pytest.mark.parametrize("phrasing", [
        "You have exceeded your current quota, please check your plan.",
        "Insufficient credits remaining on this account.",
        "Billing hard limit reached for this organization.",
        "quota exceeded",
    ])
    def test_other_providers_phrasings(self, phrasing):
        """Not xAI-specific — the same stop from another vendor should
        abort just as fast."""
        assert is_quota_exhausted(phrasing)

    def test_case_insensitive(self):
        assert is_quota_exhausted("USED ALL AVAILABLE CREDITS")


class TestDoesNotOverreach:
    """A false positive cancels a day of episodes. These must all stay
    warnings that let the run continue."""

    @pytest.mark.parametrize("message", [
        "Grok TTS returned 401 Unauthorized. Verify GROK_API_KEY.",
        "403 Forbidden: the caller does not have permission to execute the "
        "specified operation",  # the 403 wording WITHOUT the credit sentence
        "429 Too Many Requests",
        "Connection timed out",
        "model grok-4.1 has been deprecated",
        "500 Internal Server Error",
        "",
    ])
    def test_not_a_billing_stop(self, message):
        assert not is_quota_exhausted(message)

    def test_none_is_not_a_billing_stop(self):
        assert not is_quota_exhausted(None)

    def test_a_bare_403_status_is_not_enough(self):
        """A revoked key is also a 403 and needs a different response
        from the operator."""
        class Err(Exception):
            status_code = 403

        assert not is_quota_exhausted(Err("Forbidden"))


class TestOperatorMessage:
    def test_says_what_to_do_not_just_what_broke(self):
        text = quota_message("xAI", XAI_BODY)
        assert "console.x.ai" in text
        assert "Re-run" in text
        assert "billing stop, not a code failure" in text

    def test_includes_what_the_provider_said(self):
        assert "fae4735c" in quota_message("xAI", XAI_BODY)

    def test_usable_without_an_error(self):
        assert "Billing" in quota_message() or "billing" in quota_message()
