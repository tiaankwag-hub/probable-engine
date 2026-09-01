"""Guided Risk Intake (post-Milestone-9 enhancement): a live, turn-by-turn
conversation that turns a non-expert's free-text description of a concern
into a structured DRAFT risk. See `packages/shared/models/risk_intake.py`
for why this is synchronous per-turn rather than the usual `BackgroundJob`
pattern, and for the placeholder-assessment principle `finalize_session`
below follows exactly.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.ai.provider import AIProvider
from packages.shared.models.risk import Risk, RiskCategory
from packages.shared.models.risk_intake import IntakeSessionStatus, RiskIntakeSession
from packages.shared.risk_service import AssessmentInput, RiskFields, create_risk, find_category_by_name

MAX_INTAKE_TURNS = 6
OPENING_MESSAGE = (
    "Hi! Tell me in your own words what's worrying you, or what risk you'd like to raise — "
    "don't worry about getting the terminology right, I'll help turn it into something the "
    "risk register can use. What's on your mind?"
)


class IntakeSessionNotActiveError(Exception):
    def __init__(self, session_id: uuid.UUID):
        self.session_id = session_id
        super().__init__(f"risk intake session {session_id} is not open for this action")


def start_session(session: Session, *, user_id: uuid.UUID) -> RiskIntakeSession:
    """The opening question is fixed and asked without a provider call —
    guarantees a good first turn every time and saves an AI call on a
    question that never needs to vary."""
    now = datetime.now(timezone.utc)
    intake = RiskIntakeSession(
        initiated_by_id=user_id,
        status=IntakeSessionStatus.IN_PROGRESS,
        transcript=[{"role": "assistant", "content": OPENING_MESSAGE}],
        draft_fields={},
        turn_count=0,
        created_at=now,
        updated_at=now,
    )
    session.add(intake)
    session.flush()
    return intake


def build_intake_context(
    session: Session, intake: RiskIntakeSession, *, latest_user_message: str
) -> dict:
    """Allow-listed projection handed to the provider: the transcript and
    known fields so far, plus the organization's real category names —
    never the raw ORM session or anything beyond this conversation."""
    category_names = [c.name for c in session.scalars(select(RiskCategory)).all()]
    transcript_block = "\n".join(
        f"{'Assistant' if turn['role'] == 'assistant' else 'User'}: {turn['content']}"
        for turn in intake.transcript
    )
    draft_fields_block = (
        "; ".join(f"{k}: {v}" for k, v in intake.draft_fields.items() if v) or "(nothing captured yet)"
    )
    return {
        "transcript_block": transcript_block,
        "draft_fields": dict(intake.draft_fields),
        "draft_fields_block": draft_fields_block,
        "latest_user_message": latest_user_message,
        "turn_number": intake.turn_count + 1,
        "max_turns": MAX_INTAKE_TURNS,
        "category_names": category_names,
        "category_names_block": ", ".join(category_names) or "(no categories configured)",
    }


def submit_user_message(
    session: Session, provider: AIProvider, intake: RiskIntakeSession, *, message: str
) -> RiskIntakeSession:
    """Advances the conversation by one turn. `MAX_INTAKE_TURNS` is a hard
    guardrail enforced here in Python, never left to the provider's own
    judgment — a session is always forced ready by the last allowed turn,
    however many fields it still lacks, so a user is never trapped in an
    endless back-and-forth. A session already marked ready can still take
    more messages (someone correcting a detail before submitting) — only a
    terminal session (submitted/abandoned) is closed to new turns."""
    if intake.status not in (IntakeSessionStatus.IN_PROGRESS, IntakeSessionStatus.READY_TO_SUBMIT):
        raise IntakeSessionNotActiveError(intake.id)

    intake.transcript = [*intake.transcript, {"role": "user", "content": message}]
    context = build_intake_context(session, intake, latest_user_message=message)
    result = provider.continue_risk_intake(context)

    intake.draft_fields = {
        **intake.draft_fields,
        **{k: v for k, v in result.updated_fields.items() if v},
    }
    intake.turn_count += 1
    intake.model = result.model
    is_ready = result.is_ready_to_submit or intake.turn_count >= MAX_INTAKE_TURNS
    intake.transcript = [*intake.transcript, {"role": "assistant", "content": result.reply_message}]
    intake.status = IntakeSessionStatus.READY_TO_SUBMIT if is_ready else IntakeSessionStatus.IN_PROGRESS
    intake.updated_at = datetime.now(timezone.utc)
    session.flush()
    return intake


def finalize_session(
    session: Session, intake: RiskIntakeSession, *, actor_id: uuid.UUID, actor_email: str
) -> Risk:
    """Creates the draft risk through the exact same `create_risk` path
    every other risk-creation route uses — never a direct write — with the
    same minimal, unrated placeholder assessment as an approved
    emerging-risk suggestion (likelihood=1, every impact dimension=1, no
    control effectiveness). A Risk Manager reviews and completes it from
    there like any other draft; the full conversation stays on this
    session for context."""
    if intake.status not in (IntakeSessionStatus.IN_PROGRESS, IntakeSessionStatus.READY_TO_SUBMIT):
        raise IntakeSessionNotActiveError(intake.id)

    fields_data = intake.draft_fields
    fields = RiskFields(
        title=fields_data.get("title") or "Risk raised via Guided Risk Intake",
        statement=fields_data.get("statement") or fields_data.get("event"),
        cause=fields_data.get("cause"),
        event=fields_data.get("event"),
        impact=fields_data.get("impact"),
        category_id=find_category_by_name(session, fields_data.get("category_guess")),
        department=fields_data.get("department_guess"),
        owner_id=actor_id,
        status="draft",
        decision="pending",
        latest_update=(
            "Captured via the Guided Risk Intake conversational assistant, not filled in "
            "directly — the likelihood and impact scores are an unrated placeholder. A Risk "
            f"Owner must record a real assessment. Intake session: {intake.id}."
        ),
    )
    assessment_input = AssessmentInput(
        likelihood=1,
        impact_financial=1,
        impact_customer_service=1,
        impact_operational_delivery=1,
        impact_legal_regulatory=1,
        impact_reputation=1,
        impact_health_safety=1,
        control_effectiveness=None,
    )
    risk = create_risk(
        session,
        fields=fields,
        assessment_input=assessment_input,
        actor_email=actor_email,
        actor_id=actor_id,
        source="guided-risk-intake",
    )
    intake.status = IntakeSessionStatus.SUBMITTED
    intake.resulting_risk_id = risk.id
    intake.updated_at = datetime.now(timezone.utc)
    session.flush()
    return risk
