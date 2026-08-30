"""Asserts the RBAC matrix in docs/api/00-api-design.md against every role,
directly against the API (not the UI) — the brief's explicit "frontend
hiding alone is insufficient" requirement.
"""

import pytest

from apps.api.tests.conftest import login

ALL_ROLES = [
    "viewer",
    "risk_owner",
    "control_owner",
    "risk_manager",
    "executive",
    "administrator",
    "auditor",
]

ROLE_EMAILS = {
    "viewer": "viewer@example.com",
    "risk_owner": "risk.owner@example.com",
    "control_owner": "control.owner@example.com",
    "risk_manager": "risk.manager@example.com",
    "executive": "executive@example.com",
    "administrator": "admin@example.com",
    "auditor": "auditor@example.com",
}

CAN_CREATE_RISK = {"risk_owner", "risk_manager", "administrator"}
CAN_RUN_IMPORTS = {"risk_manager", "administrator"}


def make_risk_payload():
    return {
        "title": "RBAC probe risk",
        "assessment": {
            "likelihood": 2,
            "impact_scores": {
                "financial": 2, "customer_service": 2, "operational_delivery": 2,
                "legal_regulatory": 2, "reputation": 2, "health_safety": 2,
            },
            "control_effectiveness": 2,
        },
    }


@pytest.mark.parametrize("role", ALL_ROLES)
def test_every_role_can_view_risks(client, role):
    headers = login(client, ROLE_EMAILS[role])
    response = client.get("/api/v1/risks", headers=headers)
    assert response.status_code == 200


@pytest.mark.parametrize("role", ALL_ROLES)
def test_create_risk_permission_matrix(client, role):
    headers = login(client, ROLE_EMAILS[role])
    response = client.post("/api/v1/risks", json=make_risk_payload(), headers=headers)
    if role in CAN_CREATE_RISK:
        assert response.status_code == 201, f"{role} should be able to create a risk"
    else:
        assert response.status_code == 403, f"{role} should NOT be able to create a risk"


@pytest.mark.parametrize("role", ALL_ROLES)
def test_run_imports_permission_matrix(client, role, tmp_path):
    headers = login(client, ROLE_EMAILS[role])
    fixture = tmp_path / "probe.xlsx"
    from openpyxl import Workbook

    wb = Workbook()
    wb.active.append(["risk_id", "risk_title"])
    wb.save(fixture)

    with open(fixture, "rb") as f:
        response = client.post(
            "/api/v1/imports",
            files={"file": ("probe.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=headers,
        )
    if role in CAN_RUN_IMPORTS:
        assert response.status_code == 201, f"{role} should be able to start an import"
    else:
        assert response.status_code == 403, f"{role} should NOT be able to start an import"


def test_no_bearer_token_is_rejected_even_for_get(client):
    response = client.get("/api/v1/risks")
    assert response.status_code == 401
