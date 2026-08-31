"""Tests the GeminiAPIProvider entirely against a mocked HTTP transport —
no live network calls, no real API key required. What's under test is
this module's own request/response handling (building the right request
body, parsing the response shape, surfacing errors clearly), not
Google's API itself.
"""

import json

import httpx
import pytest

from packages.ai.gemini_provider import GeminiAPIError, GeminiAPIProvider


def _client_with_response(json_body: dict, status_code: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=json_body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def _gemini_envelope(text: str) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


EXEC_SUMMARY_CONTEXT = {
    "total_risks": 1, "extreme_count": 0, "high_count": 0, "moderate_count": 1, "low_count": 0,
    "weak_controls_count": 0, "overdue_actions_count": 0, "risks_outside_appetite_count": 0,
    "top_risk_titles": [],
}


class TestConstruction:
    def test_requires_api_key(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            GeminiAPIProvider()

    def test_uses_default_model_when_unset(self, monkeypatch):
        monkeypatch.delenv("GEMINI_MODEL", raising=False)
        provider = GeminiAPIProvider(api_key="test-key")
        assert provider.model == "gemini-3.6-flash"

    def test_model_overridable_via_env(self, monkeypatch):
        monkeypatch.setenv("GEMINI_MODEL", "gemini-1.5-pro")
        provider = GeminiAPIProvider(api_key="test-key")
        assert provider.model == "gemini-1.5-pro"


class TestExecutiveSummary:
    def test_returns_plain_text_response(self):
        client = _client_with_response(_gemini_envelope("Risk register looks stable."))
        provider = GeminiAPIProvider(api_key="test-key", client=client)

        response = provider.generate_executive_summary(
            {"total_risks": 5, "extreme_count": 0, "high_count": 0, "moderate_count": 3,
             "low_count": 2, "weak_controls_count": 0, "overdue_actions_count": 0,
             "risks_outside_appetite_count": 0, "top_risk_titles": []}
        )
        assert response.text == "Risk register looks stable."
        assert response.model == "gemini-3.6-flash"
        assert response.suggestions == []

    def test_non_200_raises_gemini_api_error(self):
        client = _client_with_response({"error": {"message": "invalid API key"}}, status_code=400)
        provider = GeminiAPIProvider(api_key="bad-key", client=client)

        with pytest.raises(GeminiAPIError, match="400"):
            provider.generate_executive_summary(EXEC_SUMMARY_CONTEXT)

    def test_unexpected_shape_raises_gemini_api_error(self):
        client = _client_with_response({"unexpected": "shape"})
        provider = GeminiAPIProvider(api_key="test-key", client=client)

        with pytest.raises(GeminiAPIError, match="unexpected"):
            provider.generate_executive_summary(EXEC_SUMMARY_CONTEXT)


class TestAnalyzeRisk:
    def test_parses_structured_suggestion(self):
        payload = {
            "narrative": "This risk has escalated recently.",
            "should_suggest_change": True,
            "suggestion_summary": "Increase likelihood to 4",
            "suggestion_rationale": "Two incidents in the last month.",
            "proposed_likelihood": 4,
            "proposed_control_effectiveness": None,
        }
        client = _client_with_response(_gemini_envelope(json.dumps(payload)))
        provider = GeminiAPIProvider(api_key="test-key", client=client)

        response = provider.analyze_risk(
            {"title": "X", "statement": "Y", "category": "Cyber", "likelihood": 3,
             "control_effectiveness": 3, "residual_band": "high",
             "recent_incident_count": 2, "overdue_action_count": 0}
        )
        assert response.text == "This risk has escalated recently."
        assert len(response.suggestions) == 1
        suggestion = response.suggestions[0]
        assert suggestion.proposed_changes == {"likelihood": 4}
        assert suggestion.summary == "Increase likelihood to 4"

    def test_no_suggestion_when_model_declines(self):
        payload = {"narrative": "Nothing notable.", "should_suggest_change": False}
        client = _client_with_response(_gemini_envelope(json.dumps(payload)))
        provider = GeminiAPIProvider(api_key="test-key", client=client)

        response = provider.analyze_risk(
            {"title": "X", "statement": "Y", "category": "Cyber", "likelihood": 3,
             "control_effectiveness": 3, "residual_band": "low",
             "recent_incident_count": 0, "overdue_action_count": 0}
        )
        assert response.suggestions == []

    def test_invalid_json_raises_gemini_api_error(self):
        client = _client_with_response(_gemini_envelope("not valid json"))
        provider = GeminiAPIProvider(api_key="test-key", client=client)

        with pytest.raises(GeminiAPIError, match="valid JSON"):
            provider.analyze_risk(
                {"title": "X", "statement": "Y", "category": "Cyber", "likelihood": 3,
                 "control_effectiveness": 3, "residual_band": "low",
                 "recent_incident_count": 0, "overdue_action_count": 0}
            )

    def test_both_proposed_fields_included_when_present(self):
        payload = {
            "narrative": "Both dimensions look off.",
            "should_suggest_change": True,
            "suggestion_summary": "Adjust both",
            "suggestion_rationale": "Reasons.",
            "proposed_likelihood": 4,
            "proposed_control_effectiveness": 2,
        }
        client = _client_with_response(_gemini_envelope(json.dumps(payload)))
        provider = GeminiAPIProvider(api_key="test-key", client=client)

        response = provider.analyze_risk(
            {"title": "X", "statement": "Y", "category": "Cyber", "likelihood": 3,
             "control_effectiveness": 3, "residual_band": "high",
             "recent_incident_count": 1, "overdue_action_count": 1}
        )
        assert response.suggestions[0].proposed_changes == {
            "likelihood": 4, "control_effectiveness": 2,
        }
