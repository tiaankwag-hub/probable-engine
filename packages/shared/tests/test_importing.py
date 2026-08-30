from packages.shared.importing.mapping import (
    DEFAULT_RISK_REGISTER_MAPPING,
    build_import_rows,
)
from packages.shared.importing.transforms import (
    parse_excel_date,
    parse_int_1_to_5,
    split_cause_event_impact,
    split_control_id_list,
)
from packages.shared.importing.validation import has_blocking_errors, validate_rows


def make_raw_row(**overrides):
    row = {
        "risk_id": "RSK-001",
        "risk_title": "Loss of key vendor",
        "risk_statement_cause_event_impact": (
            "Cause: single-sourced vendor Event: vendor insolvency "
            "Impact: service disruption"
        ),
        "category": "Operational",
        "business_process_value_stream_optional": "Order fulfilment",
        "team_department": "Procurement",
        "owner_accountable": "owner@example.com",
        "raised_date": "2026-01-15",
        "next_review_date": "2026-07-15",
        "status": "Open",
        "decision": "Treat",
        "acceptance_rationale_required_if_accept": None,
        "financial_impact_1_5": 4,
        "customer_service_impact_1_5": 3,
        "operational_delivery_impact_1_5": 4,
        "legal_regulatory_impact_1_5": 2,
        "reputation_impact_1_5": 3,
        "health_safety_impact_1_5": 1,
        "overall_impact_calc": 2.83,
        "likelihood_1_5_12_month_horizon": 3,
        "inherent_score_calc": 8.5,
        "inherent_band_calc": "Moderate",
        "key_controls_ids_or_short_list": "CTRL-01, CTRL-02",
        "control_effectiveness_1_5": 3,
        "reduction_calc": 0.36,
        "residual_score_calc": 5.4,
        "residual_band_calc": "Moderate",
        "risk_velocity_optional": "Slow",
        "confidence_optional": "Medium",
        "treatment_plan_summary": "Onboard secondary vendor",
        "actions_link_jira_servicenow_etc": "JIRA-123",
        "due_date": "2026-03-01",
        "completion": "25%",
        "latest_update_note": "RFP issued to alternate vendors",
        "last_updated_date": "2026-02-01",
        "updated_by": "risk.manager@example.com",
    }
    row.update(overrides)
    return row


class TestTransforms:
    def test_split_cause_event_impact_labeled_text(self):
        result = split_cause_event_impact(
            "Cause: A Event: B Impact: C"
        )
        assert result["cause"] == "A"
        assert result["event"] == "B"
        assert result["impact"] == "C"

    def test_split_cause_event_impact_unlabeled_falls_back_to_statement(self):
        result = split_cause_event_impact("just a plain sentence")
        assert result["statement"] == "just a plain sentence"
        assert result["cause"] is None

    def test_split_cause_event_impact_blank(self):
        result = split_cause_event_impact(None)
        assert result == {"statement": None, "cause": None, "event": None, "impact": None}

    def test_parse_excel_date_iso_string(self):
        assert parse_excel_date("2026-01-15").isoformat() == "2026-01-15"

    def test_parse_excel_date_invalid_returns_none(self):
        assert parse_excel_date("not a date") is None

    def test_parse_int_1_to_5_valid(self):
        assert parse_int_1_to_5(4) == 4
        assert parse_int_1_to_5("3") == 3

    def test_parse_int_1_to_5_out_of_range_returns_none(self):
        assert parse_int_1_to_5(9) is None
        assert parse_int_1_to_5(0) is None

    def test_split_control_id_list(self):
        assert split_control_id_list("CTRL-01, CTRL-02;CTRL-03") == [
            "CTRL-01", "CTRL-02", "CTRL-03",
        ]


class TestMapping:
    def test_default_mapping_produces_expected_domain_fields(self):
        rows = build_import_rows([make_raw_row()], DEFAULT_RISK_REGISTER_MAPPING)
        mapped = rows[0].mapped
        assert mapped["risk_code"] == "RSK-001"
        assert mapped["title"] == "Loss of key vendor"
        assert mapped["cause"] == "single-sourced vendor"
        assert mapped["event"] == "vendor insolvency"
        assert mapped["impact"] == "service disruption"
        assert mapped["impact_financial"] == 4
        assert mapped["likelihood"] == 3
        assert mapped["control_ids_raw"] == ["CTRL-01", "CTRL-02"]
        assert mapped["raised_date"].isoformat() == "2026-01-15"

    def test_row_numbers_start_at_two(self):
        rows = build_import_rows([make_raw_row(), make_raw_row(risk_id="RSK-002")],
                                  DEFAULT_RISK_REGISTER_MAPPING)
        assert [r.row_number for r in rows] == [2, 3]


class TestValidation:
    def test_valid_row_has_no_errors(self):
        rows = build_import_rows([make_raw_row()], DEFAULT_RISK_REGISTER_MAPPING)
        issues = validate_rows(
            rows,
            known_category_names={"Operational"},
            known_owner_emails={"owner@example.com"},
        )
        assert not has_blocking_errors(issues)

    def test_missing_risk_code_is_blocking_error(self):
        rows = build_import_rows([make_raw_row(risk_id=None)], DEFAULT_RISK_REGISTER_MAPPING)
        issues = validate_rows(rows)
        assert has_blocking_errors(issues)
        assert any(i.error_type == "missing_required_field" and i.field == "risk_code"
                   for i in issues)

    def test_duplicate_risk_code_is_blocking_error(self):
        rows = build_import_rows(
            [make_raw_row(), make_raw_row()], DEFAULT_RISK_REGISTER_MAPPING
        )
        issues = validate_rows(rows)
        assert any(i.error_type == "duplicate_risk_code" for i in issues)
        assert has_blocking_errors(issues)

    def test_invalid_impact_score_is_blocking_error(self):
        rows = build_import_rows(
            [make_raw_row(financial_impact_1_5=99)], DEFAULT_RISK_REGISTER_MAPPING
        )
        issues = validate_rows(rows)
        assert any(i.field == "impact_financial" for i in issues)
        assert has_blocking_errors(issues)

    def test_unknown_category_is_warning_not_error(self):
        rows = build_import_rows([make_raw_row()], DEFAULT_RISK_REGISTER_MAPPING)
        issues = validate_rows(rows, known_category_names=set())
        category_issues = [i for i in issues if i.error_type == "unknown_category"]
        assert len(category_issues) == 1
        assert category_issues[0].severity == "warning"
        assert not has_blocking_errors(category_issues)

    def test_unknown_owner_is_warning_not_error(self):
        rows = build_import_rows([make_raw_row()], DEFAULT_RISK_REGISTER_MAPPING)
        issues = validate_rows(rows, known_category_names={"Operational"}, known_owner_emails=set())
        owner_issues = [i for i in issues if i.error_type == "unknown_owner"]
        assert len(owner_issues) == 1
        assert owner_issues[0].severity == "warning"

    def test_accept_decision_without_rationale_is_error(self):
        rows = build_import_rows(
            [make_raw_row(decision="Accept", acceptance_rationale_required_if_accept=None)],
            DEFAULT_RISK_REGISTER_MAPPING,
        )
        issues = validate_rows(rows)
        assert any(
            i.field == "acceptance_rationale" and i.severity == "error" for i in issues
        )

    def test_accept_decision_with_rationale_is_fine(self):
        rows = build_import_rows(
            [make_raw_row(
                decision="Accept",
                acceptance_rationale_required_if_accept="Within appetite",
            )],
            DEFAULT_RISK_REGISTER_MAPPING,
        )
        issues = validate_rows(rows, known_category_names={"Operational"},
                                known_owner_emails={"owner@example.com"})
        assert not any(i.field == "acceptance_rationale" for i in issues)
