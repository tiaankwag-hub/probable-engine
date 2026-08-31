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


CONTROL_GAP_CONTEXT = {
    "title": "X", "category": "Cyber", "residual_band": "high",
    "control_count": 0, "controls_block": "(none)", "linked_controls": [],
}


class TestAnalyzeControlGaps:
    def test_parses_structured_control_suggestion(self):
        payload = {
            "narrative": "No control mitigates this risk.",
            "should_suggest_control": True,
            "control_name": "Vendor security review",
            "control_description": "Annual review of vendor security posture.",
            "control_type": "Preventive",
            "rationale": "No control is currently linked.",
        }
        client = _client_with_response(_gemini_envelope(json.dumps(payload)))
        provider = GeminiAPIProvider(api_key="test-key", client=client)

        response = provider.analyze_control_gaps(CONTROL_GAP_CONTEXT)
        assert response.text == "No control mitigates this risk."
        assert len(response.suggestions) == 1
        suggestion = response.suggestions[0]
        assert suggestion.suggestion_type == "new_control"
        assert suggestion.proposed_changes == {
            "name": "Vendor security review",
            "description": "Annual review of vendor security posture.",
            "control_type": "preventive",
        }

    def test_no_suggestion_when_model_declines(self):
        payload = {"narrative": "Controls look adequate.", "should_suggest_control": False}
        client = _client_with_response(_gemini_envelope(json.dumps(payload)))
        provider = GeminiAPIProvider(api_key="test-key", client=client)

        response = provider.analyze_control_gaps(CONTROL_GAP_CONTEXT)
        assert response.suggestions == []

    def test_invalid_json_raises_gemini_api_error(self):
        client = _client_with_response(_gemini_envelope("not valid json"))
        provider = GeminiAPIProvider(api_key="test-key", client=client)

        with pytest.raises(GeminiAPIError, match="valid JSON"):
            provider.analyze_control_gaps(CONTROL_GAP_CONTEXT)


EMERGING_RISK_CONTEXT = {
    "category_summary": "Operational: 4, Legal & Regulatory: 1",
    "existing_titles": "- Some existing risk",
}


class TestScanEmergingRisks:
    def test_parses_structured_risk_proposal(self):
        payload = {
            "narrative": "Legal & Regulatory is the least represented category.",
            "should_propose_risk": True,
            "proposed_title": "New data-protection rule",
            "proposed_statement": "A new rule may require changes to current data practices.",
            "proposed_category": "Legal & Regulatory",
            "rationale": "Fewest registered risks in that category.",
        }
        client = _client_with_response(_gemini_envelope(json.dumps(payload)))
        provider = GeminiAPIProvider(api_key="test-key", client=client)

        response = provider.scan_emerging_risks(EMERGING_RISK_CONTEXT)
        assert len(response.suggestions) == 1
        suggestion = response.suggestions[0]
        assert suggestion.suggestion_type == "new_risk"
        assert suggestion.proposed_changes == {
            "title": "New data-protection rule",
            "statement": "A new rule may require changes to current data practices.",
            "category": "Legal & Regulatory",
        }

    def test_no_suggestion_when_model_declines(self):
        payload = {"narrative": "Coverage looks even.", "should_propose_risk": False}
        client = _client_with_response(_gemini_envelope(json.dumps(payload)))
        provider = GeminiAPIProvider(api_key="test-key", client=client)

        response = provider.scan_emerging_risks(EMERGING_RISK_CONTEXT)
        assert response.suggestions == []

    def test_invalid_json_raises_gemini_api_error(self):
        client = _client_with_response(_gemini_envelope("not valid json"))
        provider = GeminiAPIProvider(api_key="test-key", client=client)

        with pytest.raises(GeminiAPIError, match="valid JSON"):
            provider.scan_emerging_risks(EMERGING_RISK_CONTEXT)


class TestGenerateMarketAnalysis:
    def test_returns_plain_text_response_with_no_suggestions(self):
        client = _client_with_response(_gemini_envelope("General commentary on industry trends."))
        provider = GeminiAPIProvider(api_key="test-key", client=client)

        response = provider.generate_market_analysis({"category_summary": "Operational: 4, Financial: 2"})
        assert response.text == "General commentary on industry trends."
        assert response.suggestions == []

    def test_non_200_raises_gemini_api_error(self):
        client = _client_with_response({"error": {"message": "quota exceeded"}}, status_code=429)
        provider = GeminiAPIProvider(api_key="test-key", client=client)

        with pytest.raises(GeminiAPIError, match="429"):
            provider.generate_market_analysis({"category_summary": "Operational: 4"})


SIGNAL_CONTEXT = {
    "content": "A wave of ransomware incidents has hit software supply-chain vendors.",
    "classified_category": "Cyber & Information Security",
    "existing_titles_block": "(none)",
}


class TestAnalyzeSignal:
    def test_parses_relevant_candidate(self):
        payload = {
            "is_relevant": True,
            "title": "Supply-chain ransomware exposure",
            "summary": "A compromised build pipeline could allow ransomware into our software supply chain.",
            "relevance_assessment": "No existing risk covers build-pipeline compromise specifically.",
        }
        client = _client_with_response(_gemini_envelope(json.dumps(payload)))
        provider = GeminiAPIProvider(api_key="test-key", client=client)

        result = provider.analyze_signal(SIGNAL_CONTEXT)
        assert result.is_relevant is True
        assert result.title == "Supply-chain ransomware exposure"
        assert result.model == "gemini-3.6-flash"

    def test_not_relevant(self):
        payload = {"is_relevant": False, "relevance_assessment": "Already covered by an existing risk."}
        client = _client_with_response(_gemini_envelope(json.dumps(payload)))
        provider = GeminiAPIProvider(api_key="test-key", client=client)

        result = provider.analyze_signal(SIGNAL_CONTEXT)
        assert result.is_relevant is False
        assert result.title == ""

    def test_invalid_json_raises_gemini_api_error(self):
        client = _client_with_response(_gemini_envelope("not valid json"))
        provider = GeminiAPIProvider(api_key="test-key", client=client)

        with pytest.raises(GeminiAPIError, match="valid JSON"):
            provider.analyze_signal(SIGNAL_CONTEXT)
