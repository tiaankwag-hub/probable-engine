"""Applies a column mapping (source spreadsheet column -> domain field, with
an optional named transform) to raw parsed rows, producing plain dicts keyed
by domain field names. This is the boundary described in ADR 0008: nothing
downstream of `apply_mapping` ever sees a spreadsheet column name again.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packages.shared.importing.transforms import TRANSFORMS


@dataclass(frozen=True)
class ColumnMappingSpec:
    source_column: str
    domain_field: str | None
    transform: str | None = None


@dataclass(frozen=True)
class ImportRow:
    row_number: int
    raw: dict[str, Any]
    mapped: dict[str, Any]


def apply_mapping(raw_row: dict[str, Any], mappings: list[ColumnMappingSpec]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for spec in mappings:
        raw_value = raw_row.get(spec.source_column)
        if spec.transform:
            transform_fn = TRANSFORMS.get(spec.transform)
            if transform_fn is None:
                raise ValueError(f"unknown transform: {spec.transform}")
            result = transform_fn(raw_value)
            if isinstance(result, dict):
                output.update(result)
            elif spec.domain_field:
                output[spec.domain_field] = result
        elif spec.domain_field:
            output[spec.domain_field] = raw_value
    return output


def build_import_rows(
    raw_rows: list[dict[str, Any]], mappings: list[ColumnMappingSpec]
) -> list[ImportRow]:
    return [
        ImportRow(row_number=i + 2, raw=raw_row, mapped=apply_mapping(raw_row, mappings))
        for i, raw_row in enumerate(raw_rows)
    ]  # row_number=2 for the first data row (row 1 is the header)


# --- Default mapping template for the brief's documented 37-column schema ---
# (docs/architecture/00-current-state-assessment.md assumption A1: this is
# the *documented* layout, unverified against a real file. Saved here as the
# Import Wizard's suggested starting point — the user can override any entry.)

DEFAULT_RISK_REGISTER_MAPPING: list[ColumnMappingSpec] = [
    ColumnMappingSpec("risk_id", "risk_code", "strip_text"),
    ColumnMappingSpec("risk_title", "title", "strip_text"),
    ColumnMappingSpec(
        "risk_statement_cause_event_impact", None, "split_cause_event_impact"
    ),
    ColumnMappingSpec("category", "category_name", "strip_text"),
    ColumnMappingSpec("business_process_value_stream_optional", "business_process", "strip_text"),
    ColumnMappingSpec("team_department", "department", "strip_text"),
    ColumnMappingSpec("owner_accountable", "owner_email", "strip_text"),
    ColumnMappingSpec("raised_date", "raised_date", "parse_excel_date"),
    ColumnMappingSpec("next_review_date", "next_review_date", "parse_excel_date"),
    ColumnMappingSpec("status", "status_raw", "strip_text"),
    ColumnMappingSpec("decision", "decision_raw", "strip_text"),
    ColumnMappingSpec(
        "acceptance_rationale_required_if_accept", "acceptance_rationale", "strip_text"
    ),
    ColumnMappingSpec("financial_impact_1_5", "impact_financial", "parse_int_1_to_5"),
    ColumnMappingSpec(
        "customer_service_impact_1_5", "impact_customer_service", "parse_int_1_to_5"
    ),
    ColumnMappingSpec(
        "operational_delivery_impact_1_5", "impact_operational_delivery", "parse_int_1_to_5"
    ),
    ColumnMappingSpec(
        "legal_regulatory_impact_1_5", "impact_legal_regulatory", "parse_int_1_to_5"
    ),
    ColumnMappingSpec("reputation_impact_1_5", "impact_reputation", "parse_int_1_to_5"),
    ColumnMappingSpec("health_safety_impact_1_5", "impact_health_safety", "parse_int_1_to_5"),
    ColumnMappingSpec("overall_impact_calc", "ref_overall_impact", "parse_float"),
    ColumnMappingSpec("likelihood_1_5_12_month_horizon", "likelihood", "parse_int_1_to_5"),
    ColumnMappingSpec("inherent_score_calc", "ref_inherent_score", "parse_float"),
    ColumnMappingSpec("inherent_band_calc", "ref_inherent_band", "strip_text"),
    ColumnMappingSpec("key_controls_ids_or_short_list", "control_ids_raw", "split_control_id_list"),
    ColumnMappingSpec("control_effectiveness_1_5", "control_effectiveness", "parse_int_1_to_5"),
    ColumnMappingSpec("reduction_calc", "ref_reduction", "parse_float"),
    ColumnMappingSpec("residual_score_calc", "ref_residual_score", "parse_float"),
    ColumnMappingSpec("residual_band_calc", "ref_residual_band", "strip_text"),
    ColumnMappingSpec("risk_velocity_optional", "velocity", "strip_text"),
    ColumnMappingSpec("confidence_optional", "confidence", "strip_text"),
    ColumnMappingSpec("treatment_plan_summary", "treatment_summary", "strip_text"),
    ColumnMappingSpec("actions_link_jira_servicenow_etc", "actions_link_raw", "strip_text"),
    ColumnMappingSpec("due_date", "action_due_date_raw", "parse_excel_date"),
    ColumnMappingSpec("completion", "action_completion_raw", "strip_text"),
    ColumnMappingSpec("latest_update_note", "latest_update", "strip_text"),
    ColumnMappingSpec("last_updated_date", "last_updated_date_raw", "parse_excel_date"),
    ColumnMappingSpec("updated_by", "updated_by_raw", "strip_text"),
]

# Fields not yet backed by a Milestone 1 table (Actions/Controls land in
# Milestone 3). Surfaced to the user as informational, not silently dropped.
DEFERRED_DOMAIN_FIELDS = {
    "control_ids_raw",
    "actions_link_raw",
    "action_due_date_raw",
    "action_completion_raw",
    "updated_by_raw",
}

IMPACT_FIELDS = (
    "impact_financial",
    "impact_customer_service",
    "impact_operational_delivery",
    "impact_legal_regulatory",
    "impact_reputation",
    "impact_health_safety",
)
