"""Generates database/seed/fixtures/risk_register_fixture.xlsx: a synthetic
Risk Register spreadsheet matching the 36-column schema documented in the
task brief (see docs/architecture/00-current-state-assessment.md — no real
spreadsheet was available, so this fixture stands in for one and is used to
exercise the Import Wizard end-to-end).

All content is fabricated for prototype purposes; it does not describe any
real organization, person, or incident.

Usage:
    python database/seed/generate_fixture.py
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

COLUMNS = [
    "risk_id", "risk_title", "risk_statement_cause_event_impact", "category",
    "business_process_value_stream_optional", "team_department", "owner_accountable",
    "raised_date", "next_review_date", "status", "decision",
    "acceptance_rationale_required_if_accept", "financial_impact_1_5",
    "customer_service_impact_1_5", "operational_delivery_impact_1_5",
    "legal_regulatory_impact_1_5", "reputation_impact_1_5", "health_safety_impact_1_5",
    "overall_impact_calc", "likelihood_1_5_12_month_horizon", "inherent_score_calc",
    "inherent_band_calc", "key_controls_ids_or_short_list", "control_effectiveness_1_5",
    "reduction_calc", "residual_score_calc", "residual_band_calc",
    "risk_velocity_optional", "confidence_optional", "treatment_plan_summary",
    "actions_link_jira_servicenow_etc", "due_date", "completion", "latest_update_note",
    "last_updated_date", "updated_by",
]

# fmt: off
ROWS = [
    dict(risk_id="RSK-1001", risk_title="Single-sourced payment processor outage",
         risk_statement_cause_event_impact="Cause: reliance on one payment processor Event: extended processor outage Impact: inability to take customer payments",
         category="Operational", business_process_value_stream_optional="Order to Cash",
         team_department="Finance Operations", owner_accountable="risk.owner@example.com",
         raised_date="2026-01-10", next_review_date="2026-07-10", status="Open", decision="Treat",
         acceptance_rationale_required_if_accept=None, financial_impact_1_5=4, customer_service_impact_1_5=4,
         operational_delivery_impact_1_5=3, legal_regulatory_impact_1_5=2, reputation_impact_1_5=3,
         health_safety_impact_1_5=1, overall_impact_calc=2.83, likelihood_1_5_12_month_horizon=2,
         inherent_score_calc=5.67, inherent_band_calc="Moderate", key_controls_ids_or_short_list="CTRL-PAY-01",
         control_effectiveness_1_5=3, reduction_calc=0.36, residual_score_calc=3.63, residual_band_calc="Low",
         risk_velocity_optional="Fast", confidence_optional="High",
         treatment_plan_summary="Add secondary payment processor", actions_link_jira_servicenow_etc="JIRA-4501",
         due_date="2026-04-01", completion="30%", latest_update_note="Vendor evaluation in progress",
         last_updated_date="2026-02-05", updated_by="risk.manager@example.com"),
    dict(risk_id="RSK-1002", risk_title="Unpatched internet-facing servers",
         risk_statement_cause_event_impact="Cause: delayed patch cycle Event: exploitation of known vulnerability Impact: data breach",
         category="Cyber & Information Security", business_process_value_stream_optional="IT Operations",
         team_department="Information Security", owner_accountable="risk.manager@example.com",
         raised_date="2025-11-20", next_review_date="2026-05-20", status="Open", decision="Treat",
         acceptance_rationale_required_if_accept=None, financial_impact_1_5=5, customer_service_impact_1_5=3,
         operational_delivery_impact_1_5=3, legal_regulatory_impact_1_5=5, reputation_impact_1_5=5,
         health_safety_impact_1_5=1, overall_impact_calc=3.67, likelihood_1_5_12_month_horizon=3,
         inherent_score_calc=11.0, inherent_band_calc="Moderate", key_controls_ids_or_short_list="CTRL-SEC-04, CTRL-SEC-07",
         control_effectiveness_1_5=2, reduction_calc=0.24, residual_score_calc=8.36, residual_band_calc="Moderate",
         risk_velocity_optional="Fast", confidence_optional="High",
         treatment_plan_summary="Automate patch management pipeline", actions_link_jira_servicenow_etc="SNOW-8821",
         due_date="2026-03-15", completion="60%", latest_update_note="Automated scanning enabled on 80% of estate",
         last_updated_date="2026-02-10", updated_by="risk.manager@example.com"),
    dict(risk_id="RSK-1003", risk_title="Key engineering talent concentration",
         risk_statement_cause_event_impact="Cause: single engineer owns core billing system Event: departure without knowledge transfer Impact: extended delivery delays",
         category="People & Culture", business_process_value_stream_optional="Product Delivery",
         team_department="Engineering", owner_accountable="risk.owner@example.com",
         raised_date="2025-09-01", next_review_date="2026-03-01", status="Monitoring", decision="Treat",
         acceptance_rationale_required_if_accept=None, financial_impact_1_5=2, customer_service_impact_1_5=2,
         operational_delivery_impact_1_5=4, legal_regulatory_impact_1_5=1, reputation_impact_1_5=1,
         health_safety_impact_1_5=1, overall_impact_calc=1.83, likelihood_1_5_12_month_horizon=2,
         inherent_score_calc=3.67, inherent_band_calc="Low", key_controls_ids_or_short_list="CTRL-PPL-02",
         control_effectiveness_1_5=2, reduction_calc=0.24, residual_score_calc=2.79, residual_band_calc="Low",
         risk_velocity_optional="Slow", confidence_optional="Medium",
         treatment_plan_summary="Cross-train two additional engineers", actions_link_jira_servicenow_etc="JIRA-3390",
         due_date="2026-05-01", completion="10%", latest_update_note="Cross-training plan drafted",
         last_updated_date="2026-01-20", updated_by="risk.owner@example.com"),
    dict(risk_id="RSK-1004", risk_title="Upcoming data-residency regulation",
         risk_statement_cause_event_impact="Cause: new regional data-residency law Event: non-compliance at enforcement date Impact: regulatory fines and forced re-architecture",
         category="Legal & Regulatory", business_process_value_stream_optional="Data Platform",
         team_department="Legal & Compliance", owner_accountable="risk.manager@example.com",
         raised_date="2026-01-05", next_review_date="2026-04-05", status="Open", decision="Treat",
         acceptance_rationale_required_if_accept=None, financial_impact_1_5=4, customer_service_impact_1_5=2,
         operational_delivery_impact_1_5=3, legal_regulatory_impact_1_5=5, reputation_impact_1_5=3,
         health_safety_impact_1_5=1, overall_impact_calc=3.0, likelihood_1_5_12_month_horizon=4,
         inherent_score_calc=12.0, inherent_band_calc="High", key_controls_ids_or_short_list="CTRL-LEG-01",
         control_effectiveness_1_5=1, reduction_calc=0.12, residual_score_calc=10.56, residual_band_calc="Moderate",
         risk_velocity_optional="Medium", confidence_optional="High",
         treatment_plan_summary="Data residency compliance program", actions_link_jira_servicenow_etc="JIRA-4602",
         due_date="2026-03-30", completion="15%", latest_update_note="Legal assessment underway",
         last_updated_date="2026-02-01", updated_by="risk.manager@example.com"),
    dict(risk_id="RSK-1005", risk_title="Cloud hosting cost overrun",
         risk_statement_cause_event_impact="Cause: unbounded auto-scaling configuration Event: unexpected traffic spike Impact: budget overrun",
         category="Financial", business_process_value_stream_optional="Cloud Platform",
         team_department="Finance Operations", owner_accountable="risk.owner@example.com",
         raised_date="2025-12-01", next_review_date="2026-06-01", status="Closed", decision="Accept",
         acceptance_rationale_required_if_accept="Cost capped by new billing alerts; residual exposure within appetite",
         financial_impact_1_5=3, customer_service_impact_1_5=1, operational_delivery_impact_1_5=1,
         legal_regulatory_impact_1_5=1, reputation_impact_1_5=1, health_safety_impact_1_5=1,
         overall_impact_calc=1.33, likelihood_1_5_12_month_horizon=2, inherent_score_calc=2.67,
         inherent_band_calc="Low", key_controls_ids_or_short_list="CTRL-FIN-03", control_effectiveness_1_5=4,
         reduction_calc=0.48, residual_score_calc=1.39, residual_band_calc="Low", risk_velocity_optional="Slow",
         confidence_optional="High", treatment_plan_summary="Billing alerts and scaling caps implemented",
         actions_link_jira_servicenow_etc="JIRA-4210", due_date="2026-01-15", completion="100%",
         latest_update_note="Controls implemented and verified effective", last_updated_date="2026-01-16",
         updated_by="risk.owner@example.com"),
]
# fmt: on


def _extend_rows() -> list[dict]:
    """Pads the five hand-authored rows out to twenty by cloning them with
    varied risk_id/category/scores, so the fixture exercises pagination and
    filtering without hand-writing twenty distinct narratives."""
    rows = list(ROWS)
    categories = [
        "Operational", "Cyber & Information Security", "Third Party & Vendor",
        "Strategic", "Financial",
    ]
    for i in range(6, 21):
        base = ROWS[i % len(ROWS)]
        row = dict(base)
        row["risk_id"] = f"RSK-1{i:03d}"
        row["risk_title"] = f"{base['risk_title']} (variant {i})"
        row["category"] = categories[i % len(categories)]
        row["financial_impact_1_5"] = ((base["financial_impact_1_5"] + i) % 5) + 1
        rows.append(row)
    return rows[:20]


def generate(output_path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Risk Register"
    ws.append(COLUMNS)
    for row in _extend_rows():
        ws.append([row.get(col) for col in COLUMNS])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    generate(Path(__file__).parent / "fixtures" / "risk_register_fixture.xlsx")
