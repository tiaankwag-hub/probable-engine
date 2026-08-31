"""Provider selection (ADR 0006): `GEMINI_API_KEY` present -> real
`GeminiAPIProvider`, otherwise `MockAIProvider`. Local development and CI
never require credentials — setting the key is the only thing that
switches which provider actually runs, and callers never branch on this
themselves.
"""

from __future__ import annotations

import os

from packages.ai.gemini_provider import GeminiAPIProvider
from packages.ai.mock_provider import MockAIProvider
from packages.ai.provider import AIProvider


def get_provider() -> AIProvider:
    if os.environ.get("GEMINI_API_KEY"):
        return GeminiAPIProvider()
    return MockAIProvider()
