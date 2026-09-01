"""Guided Risk Intake API tests (post-Milestone-9 enhancement). Every test
runs against the deterministic mock provider (no GEMINI_API_KEY in the
test environment) so the full turn-by-turn script in
`packages.ai.mock_provider._generate_intake_turn` is exercised exactly as
a real conversation would drive it.
"""

from apps.api.tests.conftest import login

INTAKE_ANSWERS = [
    "A vendor could fail and we'd lose our data feed.",
    "We'd lose a few days of processing and it would cost us money.",
    "They've had financial trouble reported in the news.",
    "Operations team mostly.",
    "I'd say Operational fits best.",
    "Vendor financial instability risk",
]


def _run_full_conversation(client, headers):
    session = client.post("/api/v1/risk-intake/sessions", headers=headers).json()
    assert session["status"] == "in_progress"
    assert session["transcript"][0]["role"] == "assistant"

    updated = None
    for answer in INTAKE_ANSWERS:
        response = client.post(
            f"/api/v1/risk-intake/sessions/{session['id']}/messages",
            json={"message": answer},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        updated = response.json()
    return updated


class TestRbac:
    def test_allowed_roles_can_start_a_session(self, client):
        for email in [
            "risk.owner@example.com", "control.owner@example.com",
            "risk.manager@example.com", "executive@example.com", "admin@example.com",
        ]:
            headers = login(client, email)
            response = client.post("/api/v1/risk-intake/sessions", headers=headers)
            assert response.status_code == 201, f"{email}: {response.text}"

    def test_forbidden_roles_cannot_start_a_session(self, client):
        for email in ["viewer@example.com", "auditor@example.com"]:
            headers = login(client, email)
            response = client.post("/api/v1/risk-intake/sessions", headers=headers)
            assert response.status_code == 403, f"{email} should not be able to start a session"


class TestConversationFlow:
    def test_six_turns_reaches_ready_to_submit(self, client):
        headers = login(client, "risk.owner@example.com")
        final = _run_full_conversation(client, headers)
        assert final["status"] == "ready_to_submit"
        assert final["turn_count"] == 6
        assert final["draft_fields"]["title"] == "Vendor financial instability risk"
        assert final["draft_fields"]["category_guess"] == "Operational"
        assert final["model"] == "mock-analyst-v1"

    def test_empty_message_is_rejected(self, client):
        headers = login(client, "risk.owner@example.com")
        session = client.post("/api/v1/risk-intake/sessions", headers=headers).json()
        response = client.post(
            f"/api/v1/risk-intake/sessions/{session['id']}/messages",
            json={"message": "   "},
            headers=headers,
        )
        assert response.status_code == 422

    def test_another_users_session_is_forbidden(self, client):
        owner_headers = login(client, "risk.owner@example.com")
        session = client.post("/api/v1/risk-intake/sessions", headers=owner_headers).json()

        other_headers = login(client, "control.owner@example.com")
        response = client.post(
            f"/api/v1/risk-intake/sessions/{session['id']}/messages",
            json={"message": "hello"},
            headers=other_headers,
        )
        assert response.status_code == 403


class TestSubmit:
    def test_submit_creates_a_draft_risk_with_placeholder_assessment(self, client):
        headers = login(client, "risk.owner@example.com")
        final = _run_full_conversation(client, headers)

        result = client.post(
            f"/api/v1/risk-intake/sessions/{final['id']}/submit", headers=headers
        )
        assert result.status_code == 200, result.text
        risk_id = result.json()["risk_id"]

        risk = client.get(f"/api/v1/risks/{risk_id}", headers=headers).json()
        assert risk["status"] == "draft"
        assert risk["decision"] == "pending"
        assert risk["title"] == "Vendor financial instability risk"
        assert risk["likelihood"] == 1
        assert risk["control_effectiveness"] is None
        assert risk["category_id"] is not None

    def test_submit_before_ready_still_works_with_partial_fields(self, client):
        """A user can submit early — the guardrail is a courtesy, not a
        lock. Whatever's known so far still becomes a valid draft."""
        headers = login(client, "risk.owner@example.com")
        session = client.post("/api/v1/risk-intake/sessions", headers=headers).json()
        client.post(
            f"/api/v1/risk-intake/sessions/{session['id']}/messages",
            json={"message": "Something might go wrong with our main supplier."},
            headers=headers,
        )
        result = client.post(f"/api/v1/risk-intake/sessions/{session['id']}/submit", headers=headers)
        assert result.status_code == 200, result.text

    def test_submitting_twice_conflicts(self, client):
        headers = login(client, "risk.owner@example.com")
        final = _run_full_conversation(client, headers)
        client.post(f"/api/v1/risk-intake/sessions/{final['id']}/submit", headers=headers)
        second = client.post(f"/api/v1/risk-intake/sessions/{final['id']}/submit", headers=headers)
        assert second.status_code == 409


class TestReviewVisibility:
    def test_owner_sees_only_their_own_sessions(self, client):
        owner_headers = login(client, "risk.owner@example.com")
        client.post("/api/v1/risk-intake/sessions", headers=owner_headers)

        other_headers = login(client, "control.owner@example.com")
        client.post("/api/v1/risk-intake/sessions", headers=other_headers)

        response = client.get("/api/v1/risk-intake/sessions", headers=owner_headers)
        sessions = response.json()
        assert len(sessions) == 1
        assert sessions[0]["initiated_by_email"] == "risk.owner@example.com"

    def test_risk_manager_sees_every_session(self, client):
        owner_headers = login(client, "risk.owner@example.com")
        client.post("/api/v1/risk-intake/sessions", headers=owner_headers)

        other_headers = login(client, "control.owner@example.com")
        client.post("/api/v1/risk-intake/sessions", headers=other_headers)

        manager_headers = login(client, "risk.manager@example.com")
        response = client.get("/api/v1/risk-intake/sessions", headers=manager_headers)
        assert len(response.json()) == 2
