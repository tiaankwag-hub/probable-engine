"""Named, tested transforms selectable per column mapping (ADR 0008).

Transforms are pure functions `(raw_value) -> transformed_value` (or, for a
one-to-many split, `(raw_value) -> dict[domain_field, value]`). They never
raise on bad input — they return `None`/leave the value as-is and let
validation.py surface the problem, so one bad cell doesn't blow up an entire
import.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

_STATEMENT_SPLIT_RE = re.compile(
    r"cause\s*:\s*(?P<cause>.*?)\s*(?:event\s*:\s*(?P<event>.*?)\s*)?"
    r"(?:impact\s*:\s*(?P<impact>.*))?$",
    re.IGNORECASE | re.DOTALL,
)


def split_cause_event_impact(raw_value: Any) -> dict[str, str | None]:
    """Splits a combined 'Cause: ... Event: ... Impact: ...' statement into
    its three parts. Falls back to putting the whole string in `statement`
    with cause/event/impact left blank if it doesn't match the expected
    labeled format — never silently guesses."""
    text = "" if raw_value is None else str(raw_value).strip()
    if not text:
        return {"statement": None, "cause": None, "event": None, "impact": None}

    match = _STATEMENT_SPLIT_RE.match(text)
    if match and match.group("cause"):
        return {
            "statement": text,
            "cause": (match.group("cause") or "").strip() or None,
            "event": (match.group("event") or "").strip() or None,
            "impact": (match.group("impact") or "").strip() or None,
        }
    return {"statement": text, "cause": None, "event": None, "impact": None}


def parse_excel_date(raw_value: Any) -> date | None:
    if raw_value is None or raw_value == "":
        return None
    if isinstance(raw_value, datetime):
        return raw_value.date()
    if isinstance(raw_value, date):
        return raw_value
    if isinstance(raw_value, str):
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%b-%Y"):
            try:
                return datetime.strptime(raw_value.strip(), fmt).date()
            except ValueError:
                continue
    return None


def parse_int_1_to_5(raw_value: Any) -> int | None:
    if raw_value is None or raw_value == "":
        return None
    try:
        value = int(float(raw_value))
    except (TypeError, ValueError):
        return None
    if 1 <= value <= 5:
        return value
    return None


def strip_text(raw_value: Any) -> str | None:
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    return text or None


def parse_float(raw_value: Any) -> float | None:
    if raw_value is None or raw_value == "":
        return None
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return None


def split_control_id_list(raw_value: Any) -> list[str]:
    text = strip_text(raw_value)
    if not text:
        return []
    return [part.strip() for part in re.split(r"[,;/]", text) if part.strip()]


TRANSFORMS: dict[str, Any] = {
    "split_cause_event_impact": split_cause_event_impact,
    "parse_excel_date": parse_excel_date,
    "parse_int_1_to_5": parse_int_1_to_5,
    "parse_float": parse_float,
    "strip_text": strip_text,
    "split_control_id_list": split_control_id_list,
}
