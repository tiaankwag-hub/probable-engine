"""Deterministic keyword-based taxonomy classifier (Milestone 9) — maps a
raw signal's text to one of the organization's existing risk categories.
Pure stdlib, no NLP/ML dependency: a prototype-appropriate, fully
explainable substitute for a real classification model, matching this
codebase's other deliberately-simple deterministic engines
(`packages/risk_engine`, `packages/simulations`) rather than reaching for
a library this scale doesn't need.
"""

from __future__ import annotations

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Cyber & Information Security": (
        "ransomware", "cyberattack", "cyber attack", "data breach", "vulnerability",
        "ci/cd", "malware", "hacked",
    ),
    "Third Party & Vendor": (
        "vendor", "third-party", "third party", "supplier", "outsourc", "single-supplier",
    ),
    "Legal & Regulatory": (
        "regulatory body", "regulation", "compliance", "disclosure", "draft rule",
        "supervisory guidance", "data-protection",
    ),
    "People & Culture": (
        "attrition", "turnover", "talent", "workforce", "engineering staff", "hiring",
    ),
    "Financial": (
        "interest rate", "inflation", "currency", "credit", "liquidity", "margin", "cost overrun",
    ),
    "Operational": (
        "outage", "downtime", "disruption", "process failure", "capacity",
    ),
    "Strategic": (
        "market entrant", "competitor", "business model", "consolidation in that market",
    ),
}


def classify(content: str, *, known_categories: list[str] | None = None) -> str | None:
    """Returns the best-matching category name, or `None` if nothing
    matches. `known_categories` (when given) restricts matches to
    categories that actually exist in this organization's taxonomy right
    now — never proposes a category that isn't real. Ties are broken by
    keyword-map insertion order, so this is fully deterministic given the
    same input."""
    lowered = content.lower()
    candidates = CATEGORY_KEYWORDS.items()
    if known_categories is not None:
        known = set(known_categories)
        candidates = [(name, kws) for name, kws in candidates if name in known]

    best_match: str | None = None
    best_score = 0
    for category, keywords in candidates:
        score = sum(1 for kw in keywords if kw in lowered)
        if score > best_score:
            best_score = score
            best_match = category
    return best_match
