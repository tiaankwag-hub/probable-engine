"""Emerging Risk Radar orchestration (Milestone 9, domain model's
"Emerging risk radar" section). Bridges `packages/emerging_risk` (pure
signal adapters + classification, no DB dependency) and
`packages/ai` (the `analyze_signal` capability) to the database.

`ingest_signals` and `triage_signal` are the only two ways an
`EmergingSignal`/`EmergingRiskCandidate` row is ever created, and neither
one is authoritative: a candidate starts (and can stay) in the
non-terminal `candidate`/`under_review` lifecycle state. `transition_candidate`
and `link_candidate_to_existing_risk` are the *only* code paths that can
move a candidate to a terminal state — both require a human reviewer, and
`accepted` is the only one that ever creates a real `Risk`, always with a
minimal, unrated placeholder assessment (the AI never assigns a real
likelihood/impact score, per ADR 0006).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.ai.provider import AIProvider
from packages.emerging_risk.classification import classify
from packages.emerging_risk.signals import RawSignal, SignalAdapter, fetch_all_signals
from packages.shared.audit import record_audit_event
from packages.shared.models.emerging_risk import (
    CandidateLifecycleStatus,
    EmergingCandidateSignal,
    EmergingRiskCandidate,
    EmergingSignal,
)
from packages.shared.models.risk import Risk, RiskCategory
from packages.shared.risk_service import AssessmentInput, RiskFields, create_risk

TERMINAL_STATUSES = frozenset(
    {
        CandidateLifecycleStatus.ACCEPTED,
        CandidateLifecycleStatus.LINKED_TO_EXISTING,
        CandidateLifecycleStatus.DISMISSED,
    }
)


class CandidateAlreadyFinalizedError(Exception):
    def __init__(self, candidate_id: uuid.UUID):
        self.candidate_id = candidate_id
        super().__init__(f"candidate {candidate_id} has already reached a final lifecycle status")


class InvalidCandidateTransitionError(Exception):
    def __init__(self, requested: CandidateLifecycleStatus):
        super().__init__(
            f"cannot transition directly to {requested.value}; use link_candidate_to_existing_risk for that"
        )


def _known_category_names(session: Session) -> list[str]:
    return list(session.scalars(select(RiskCategory.name)))


def ingest_signals(
    session: Session, adapters: list[SignalAdapter] | None = None
) -> list[EmergingSignal]:
    """Fetches from every signal adapter and persists any not already
    seen (deduped by `source_citation`, which is unique per real-world
    item regardless of how many times ingestion runs). Classifies each
    new signal against the categories that actually exist right now.
    Returns only the newly created rows."""
    raw_signals: list[RawSignal] = fetch_all_signals(adapters)
    known_categories = _known_category_names(session)

    created: list[EmergingSignal] = []
    now = datetime.now(timezone.utc)
    for raw in raw_signals:
        existing = session.scalars(
            select(EmergingSignal).where(EmergingSignal.source_citation == raw.source_citation)
        ).first()
        if existing is not None:
            continue
        signal = EmergingSignal(
            source_adapter=raw.source_adapter,
            source_citation=raw.source_citation,
            raw_content=raw.content,
            classification=classify(raw.content, known_categories=known_categories),
            ingested_at=now,
        )
        session.add(signal)
        session.flush()
        created.append(signal)
    return created


def build_signal_triage_context(session: Session, signal: EmergingSignal) -> dict:
    """Allow-listed: the signal's own content, its classified category
    name, and — scoped to just that category — the titles of risks
    already registered there (never full statements), so a provider can
    avoid proposing a duplicate without being handed the whole register."""
    existing_titles: list[str] = []
    if signal.classification:
        category = session.scalars(
            select(RiskCategory).where(RiskCategory.name == signal.classification)
        ).first()
        if category is not None:
            existing_titles = list(
                session.scalars(select(Risk.title).where(Risk.category_id == category.id))
            )

    return {
        "content": signal.raw_content,
        "classified_category": signal.classification,
        "existing_category_risk_titles": existing_titles,
        "existing_titles_block": "\n".join(f"- {t}" for t in existing_titles) or "(none)",
    }


def triage_signal(
    session: Session, provider: AIProvider, signal: EmergingSignal
) -> EmergingRiskCandidate | None:
    """Calls the provider's `analyze_signal` capability and, only if it
    judges the signal relevant, creates a new `EmergingRiskCandidate` in
    the `candidate` state — never authoritative, never skipping human
    review. Returns `None` when the provider found nothing worth
    proposing."""
    context = build_signal_triage_context(session, signal)
    assessment = provider.analyze_signal(context)
    if not assessment.is_relevant:
        return None

    category_id = None
    if signal.classification:
        category = session.scalars(
            select(RiskCategory).where(RiskCategory.name == signal.classification)
        ).first()
        category_id = category.id if category else None

    now = datetime.now(timezone.utc)
    candidate = EmergingRiskCandidate(
        title=assessment.title or "Untitled emerging-risk candidate",
        summary=assessment.summary or signal.raw_content,
        category_id=category_id,
        relevance_assessment=assessment.relevance_assessment,
        model=assessment.model,
        lifecycle_status=CandidateLifecycleStatus.CANDIDATE,
        created_at=now,
        updated_at=now,
    )
    session.add(candidate)
    session.flush()
    session.add(EmergingCandidateSignal(candidate_id=candidate.id, signal_id=signal.id))
    return candidate


def transition_candidate(
    session: Session,
    candidate: EmergingRiskCandidate,
    *,
    new_status: CandidateLifecycleStatus,
    reviewer_id: uuid.UUID,
    actor_email: str,
) -> EmergingRiskCandidate:
    """The only path (besides `link_candidate_to_existing_risk`) that can
    move a candidate to `under_review`, `accepted`, or `dismissed`.
    `accepted` creates a real `Risk` with a deliberately minimal, unrated
    placeholder assessment via the normal `risk_service.create_risk` —
    the same guarantee ADR 0006 makes for AI-approved risk suggestions."""
    if candidate.lifecycle_status in TERMINAL_STATUSES:
        raise CandidateAlreadyFinalizedError(candidate.id)
    if new_status in (CandidateLifecycleStatus.LINKED_TO_EXISTING, CandidateLifecycleStatus.CANDIDATE):
        raise InvalidCandidateTransitionError(new_status)

    old_status = candidate.lifecycle_status
    now = datetime.now(timezone.utc)
    candidate.lifecycle_status = new_status
    candidate.updated_at = now

    if new_status == CandidateLifecycleStatus.ACCEPTED:
        fields = RiskFields(
            title=candidate.title,
            statement=candidate.summary,
            category_id=candidate.category_id,
            status="draft",
            decision="pending",
            latest_update=(
                "Created from an accepted Emerging Risk Radar candidate. The likelihood and "
                "impact scores are an unrated placeholder — a Risk Owner must record a real "
                "assessment before this risk's score reflects anything meaningful."
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
        new_risk = create_risk(
            session,
            fields=fields,
            assessment_input=assessment_input,
            actor_email=actor_email,
            actor_id=reviewer_id,
            source="emerging-risk-accepted",
        )
        candidate.created_risk_id = new_risk.id

    if new_status in TERMINAL_STATUSES:
        candidate.reviewed_by_id = reviewer_id
        candidate.reviewed_at = now

    record_audit_event(
        session,
        actor=actor_email,
        entity="emerging_risk_candidate",
        entity_id=candidate.id,
        action="transition",
        old_value={"lifecycle_status": old_status.value},
        new_value={"lifecycle_status": new_status.value},
        source="ui",
    )
    return candidate


def link_candidate_to_existing_risk(
    session: Session,
    candidate: EmergingRiskCandidate,
    *,
    matched_risk_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    actor_email: str,
) -> EmergingRiskCandidate:
    if candidate.lifecycle_status in TERMINAL_STATUSES:
        raise CandidateAlreadyFinalizedError(candidate.id)
    if session.get(Risk, matched_risk_id) is None:
        raise ValueError(f"risk not found: {matched_risk_id}")

    old_status = candidate.lifecycle_status
    now = datetime.now(timezone.utc)
    candidate.matched_risk_id = matched_risk_id
    candidate.lifecycle_status = CandidateLifecycleStatus.LINKED_TO_EXISTING
    candidate.reviewed_by_id = reviewer_id
    candidate.reviewed_at = now
    candidate.updated_at = now

    record_audit_event(
        session,
        actor=actor_email,
        entity="emerging_risk_candidate",
        entity_id=candidate.id,
        action="link_existing_risk",
        old_value={"lifecycle_status": old_status.value},
        new_value={"lifecycle_status": "linked_to_existing", "matched_risk_id": str(matched_risk_id)},
        source="ui",
    )
    return candidate
