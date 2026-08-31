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


class TestAnalyzeControlGaps:
    def test_no_linked_controls_suggests_new_control(self):
        provider = MockAIProvider()
        response = provider.analyze_control_gaps(
            {"title": "Unmitigated risk", "category": "Cyber", "residual_band": "high", "linked_controls": []}
        )
        assert len(response.suggestions) == 1
        suggestion = response.suggestions[0]
        assert suggestion.suggestion_type == "new_control"
        assert suggestion.proposed_changes["control_type"] == "preventive"
        assert "no control" in response.text.lower() or "no linked control" in response.text.lower()

    def test_all_weak_controls_suggests_compensating_control(self):
        provider = MockAIProvider()
        response = provider.analyze_control_gaps(
            {
                "title": "Weakly controlled risk", "category": "Operational", "residual_band": "high",
                "linked_controls": [{"design_effectiveness": 1, "operating_effectiveness": 2}],
            }
        )
        assert len(response.suggestions) == 1
        assert response.suggestions[0].suggestion_type == "new_control"
        assert response.suggestions[0].proposed_changes["control_type"] == "detective"

    def test_adequate_controls_suggest_nothing(self):
        provider = MockAIProvider()
        response = provider.analyze_control_gaps(
            {
                "title": "Well controlled risk", "category": "Financial", "residual_band": "low",
                "linked_controls": [{"design_effectiveness": 4, "operating_effectiveness": 4}],
            }
        )
        assert response.suggestions == []

    def test_mixed_controls_where_one_is_adequate_suggest_nothing(self):
        provider = MockAIProvider()
        response = provider.analyze_control_gaps(
            {
                "title": "Partially controlled risk", "category": "Financial", "residual_band": "moderate",
                "linked_controls": [
                    {"design_effectiveness": 1, "operating_effectiveness": 1},
                    {"design_effectiveness": 4, "operating_effectiveness": 4},
                ],
            }
        )
        assert response.suggestions == []


class TestScanEmergingRisks:
    def test_proposes_a_candidate_for_the_least_covered_category(self):
        provider = MockAIProvider()
        response = provider.scan_emerging_risks(
            {"category_counts": {"Operational": 4, "Legal & Regulatory": 1, "Financial": 4}}
        )
        assert len(response.suggestions) == 1
        suggestion = response.suggestions[0]
        assert suggestion.suggestion_type == "new_risk"
        assert suggestion.proposed_changes["category"] == "Legal & Regulatory"
        assert suggestion.proposed_changes["title"]
        assert suggestion.proposed_changes["statement"]

    def test_no_categories_produces_no_suggestion(self):
        provider = MockAIProvider()
        response = provider.scan_emerging_risks({"category_counts": {}})
        assert response.suggestions == []

    def test_unknown_category_with_no_candidate_produces_no_suggestion(self):
        provider = MockAIProvider()
        response = provider.scan_emerging_risks({"category_counts": {"Some Custom Category": 0}})
        assert response.suggestions == []

    def test_deterministic_given_same_context(self):
        provider = MockAIProvider()
        context = {"category_counts": {"Operational": 4, "Strategic": 1}}
        a = provider.scan_emerging_risks(context)
        b = provider.scan_emerging_risks(context)
        assert a.suggestions == b.suggestions


class TestGenerateMarketAnalysis:
    def test_never_produces_a_suggestion(self):
        provider = MockAIProvider()
        response = provider.generate_market_analysis({"category_counts": {"Operational": 4, "Financial": 2}})
        assert response.suggestions == []

    def test_is_honest_about_having_no_live_data_source(self):
        provider = MockAIProvider()
        response = provider.generate_market_analysis({"category_counts": {}})
        assert "no live market" in response.text.lower() or "no external market" in response.text.lower()


class TestAnalyzeSignal:
    def test_unclassified_signal_is_not_relevant(self):
        provider = MockAIProvider()
        result = provider.analyze_signal({"content": "Some content.", "classified_category": None})
        assert result.is_relevant is False
        assert result.title == ""

    def test_classified_signal_is_relevant_with_derived_title(self):
        provider = MockAIProvider()
        result = provider.analyze_signal(
            {
                "content": "A wave of ransomware incidents has hit vendors. Attackers targeted CI/CD tooling.",
                "classified_category": "Cyber & Information Security",
                "existing_category_risk_titles": [],
            }
        )
        assert result.is_relevant is True
        assert result.title == "A wave of ransomware incidents has hit vendors"
        assert "Cyber & Information Security" in result.relevance_assessment
        assert result.model == "mock-analyst-v1"

    def test_notes_existing_risks_in_the_category_when_present(self):
        provider = MockAIProvider()
        result = provider.analyze_signal(
            {
                "content": "Some signal content.",
                "classified_category": "Financial",
                "existing_category_risk_titles": ["Cloud hosting cost overrun"],
            }
        )
        assert "1 existing risk" in result.relevance_assessment

    def test_deterministic_given_same_context(self):
        provider = MockAIProvider()
        context = {
            "content": "A regulatory notice on AI disclosure.",
            "classified_category": "Legal & Regulatory",
            "existing_category_risk_titles": [],
        }
        a = provider.analyze_signal(context)
        b = provider.analyze_signal(context)
        assert a.title == b.title
        assert a.relevance_assessment == b.relevance_assessment
