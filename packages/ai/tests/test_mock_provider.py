from packages.ai.mock_provider import MockAIProvider


class TestExecutiveSummary:
    def test_deterministic_given_same_context(self):
        provider = MockAIProvider()
        context = {
            "total_risks": 18, "extreme_count": 1, "high_count": 3, "moderate_count": 8,
            "low_count": 6, "weak_controls_count": 2, "overdue_actions_count": 5,
            "risks_outside_appetite_count": 1, "top_risk_titles": ["Vendor outage", "Data breach"],
        }
        a = provider.generate_executive_summary(context)
        b = provider.generate_executive_summary(context)
        assert a.text == b.text
        assert a.model == "mock-analyst-v1"
        assert a.suggestions == []

    def test_mentions_counts_present_in_context(self):
        provider = MockAIProvider()
        response = provider.generate_executive_summary(
            {"total_risks": 5, "extreme_count": 0, "high_count": 0, "weak_controls_count": 3,
             "overdue_actions_count": 0, "risks_outside_appetite_count": 0, "top_risk_titles": []}
        )
        assert "5 open risk" in response.text
        assert "3 control(s)" in response.text

    def test_empty_context_does_not_crash(self):
        provider = MockAIProvider()
        response = provider.generate_executive_summary({})
        assert "0 open risk" in response.text


class TestAnalyzeRisk:
    def test_no_suggestion_when_nothing_notable(self):
        provider = MockAIProvider()
        response = provider.analyze_risk(
            {"title": "Stable risk", "residual_band": "low", "likelihood": 2,
             "control_effectiveness": 4, "recent_incident_count": 0, "overdue_action_count": 0}
        )
        assert response.suggestions == []
        assert "Stable risk" in response.text

    def test_recent_incidents_suggest_likelihood_increase(self):
        provider = MockAIProvider()
        response = provider.analyze_risk(
            {"title": "Cyber risk", "residual_band": "moderate", "likelihood": 3,
             "control_effectiveness": 3, "recent_incident_count": 2, "overdue_action_count": 0}
        )
        assert len(response.suggestions) == 1
        suggestion = response.suggestions[0]
        assert suggestion.proposed_changes == {"likelihood": 4}
        assert "incident" in suggestion.rationale.lower()

    def test_likelihood_never_suggested_above_five(self):
        provider = MockAIProvider()
        response = provider.analyze_risk(
            {"title": "Maxed risk", "residual_band": "extreme", "likelihood": 5,
             "control_effectiveness": 3, "recent_incident_count": 3, "overdue_action_count": 0}
        )
        assert response.suggestions == []

    def test_overdue_actions_suggest_control_effectiveness_decrease(self):
        provider = MockAIProvider()
        response = provider.analyze_risk(
            {"title": "Neglected risk", "residual_band": "high", "likelihood": 3,
             "control_effectiveness": 3, "recent_incident_count": 0, "overdue_action_count": 2}
        )
        assert len(response.suggestions) == 1
        assert response.suggestions[0].proposed_changes == {"control_effectiveness": 2}

    def test_deterministic_given_same_context(self):
        provider = MockAIProvider()
        context = {"title": "X", "residual_band": "high", "likelihood": 3,
                   "control_effectiveness": 3, "recent_incident_count": 1, "overdue_action_count": 0}
        a = provider.analyze_risk(context)
        b = provider.analyze_risk(context)
        assert a.text == b.text
        assert a.suggestions == b.suggestions
