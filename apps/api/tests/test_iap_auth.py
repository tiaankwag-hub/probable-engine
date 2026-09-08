"""Unit tests for the IAP verification path (Milestone 11 / ADR 0010). These
never talk to Google's real JWKS endpoint — `google.oauth2.id_token.verify_token`
is monkeypatched, since what's under test is our handling of its result
(email extraction, error mapping), not google-auth's own signature checking.
"""

import pytest

from apps.api.app.iap_auth import IAPVerificationError, verify_iap_assertion


class TestVerifyIapAssertion:
    def test_empty_assertion_is_rejected_without_calling_google(self, monkeypatch):
        def _should_not_be_called(*args, **kwargs):
            raise AssertionError("verify_token should not be called for an empty assertion")

        monkeypatch.setattr("apps.api.app.iap_auth.id_token.verify_token", _should_not_be_called)
        with pytest.raises(IAPVerificationError):
            verify_iap_assertion("", audience="test-audience")

    def test_valid_assertion_returns_the_email_claim(self, monkeypatch):
        def fake_verify_token(assertion, request, audience, certs_url):
            assert assertion == "a-real-looking-jwt"
            assert audience == "test-audience"
            return {"email": "rm@example.com", "sub": "accounts.google.com:12345"}

        monkeypatch.setattr("apps.api.app.iap_auth.id_token.verify_token", fake_verify_token)
        assert verify_iap_assertion("a-real-looking-jwt", "test-audience") == "rm@example.com"

    def test_assertion_with_no_email_claim_is_rejected(self, monkeypatch):
        monkeypatch.setattr(
            "apps.api.app.iap_auth.id_token.verify_token",
            lambda *a, **k: {"sub": "accounts.google.com:12345"},
        )
        with pytest.raises(IAPVerificationError, match="no email claim"):
            verify_iap_assertion("token", "test-audience")

    def test_google_rejecting_the_token_is_surfaced_as_verification_error(self, monkeypatch):
        def fake_verify_token(*args, **kwargs):
            raise ValueError("Token expired")

        monkeypatch.setattr("apps.api.app.iap_auth.id_token.verify_token", fake_verify_token)
        with pytest.raises(IAPVerificationError, match="Token expired"):
            verify_iap_assertion("expired-token", "test-audience")
