"""Verifies Google IAP's signed identity assertion (ADR 0010's production
identity path). IAP sits in front of Cloud Run, terminates the user's real
sign-in, and injects `X-Goog-IAP-JWT-Assertion` on every request it lets
through — that header is signed by Google, not something a caller can set
themselves (IAP strips any client-supplied copy before proxying). Verifying
it here, on every request, is what ADR 0010 means by "not just at the
edge": a network path that somehow bypassed IAP would carry no such header
and would be rejected the same as a forged one.

Swap point for a non-Google corporate SSO: replace `verify_iap_assertion`
with a call to that provider's own OIDC token verification (audience and
JWKS URL come from the identity provider instead of Google's), keeping the
same (email) return contract — nothing in deps.py needs to change.
"""

from __future__ import annotations

from google.auth.transport import requests as google_auth_requests
from google.oauth2 import id_token

_IAP_PUBLIC_KEY_URL = "https://www.gstatic.com/iap/verify/public_key-jwk"
_google_request = google_auth_requests.Request()


class IAPVerificationError(Exception):
    """The assertion is missing, expired, wrongly-audienced, or not
    actually signed by Google — never treat this as "unknown user", it
    means the request didn't genuinely come through IAP."""


def verify_iap_assertion(assertion: str, audience: str) -> str:
    if not assertion:
        raise IAPVerificationError("no IAP assertion header present")
    try:
        payload = id_token.verify_token(
            assertion,
            _google_request,
            audience=audience,
            certs_url=_IAP_PUBLIC_KEY_URL,
        )
    except Exception as exc:  # noqa: BLE001 - every google-auth failure mode means "reject"
        raise IAPVerificationError(f"IAP assertion failed verification: {exc}") from exc

    email = payload.get("email")
    if not email:
        raise IAPVerificationError("verified assertion carries no email claim")
    return email
