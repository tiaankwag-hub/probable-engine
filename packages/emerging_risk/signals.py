"""Signal adapters (Milestone 9) — fixture-based, deterministic sources
standing in for a real external feed (a news API, a regulatory bulletin
service) that this prototype has no live connection to, matching the
roadmap's "signal adapters (fixtures first)" phrasing. Each adapter's
`fetch()` returns the same fixed set every call; ingestion in
`packages/shared/emerging_risk_service.py` dedupes by `source_citation`,
so re-running ingestion never creates duplicates. Swapping in a real feed
later (an actual news API, a regulator's RSS feed) means adding another
class with the same `fetch() -> list[RawSignal]` shape — nothing else in
the pipeline changes, mirroring the `AIProvider` swap-point pattern.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RawSignal:
    source_adapter: str
    source_citation: str
    content: str


class SignalAdapter(Protocol):
    name: str

    def fetch(self) -> list[RawSignal]: ...


class FixtureNewsAdapter:
    name = "fixture_news"

    def fetch(self) -> list[RawSignal]:
        return [
            RawSignal(
                source_adapter=self.name,
                source_citation="https://example-news.test/articles/supply-chain-ransomware-wave",
                content=(
                    "A wave of ransomware incidents has hit software supply-chain companies this "
                    "quarter, with attackers specifically targeting build pipelines and CI/CD "
                    "tooling used by mid-size technology firms."
                ),
            ),
            RawSignal(
                source_adapter=self.name,
                source_citation="https://example-news.test/articles/senior-engineer-attrition-report",
                content=(
                    "A new labor-market report finds accelerating voluntary attrition among "
                    "senior engineering staff at companies without formalized remote-work and "
                    "career-progression policies."
                ),
            ),
            RawSignal(
                source_adapter=self.name,
                source_citation="https://example-news.test/articles/payment-processor-outage-trend",
                content=(
                    "Analysts note a rising trend of extended service outages among a small "
                    "number of dominant payment-processing companies, driven by consolidation in "
                    "that market."
                ),
            ),
        ]


class FixtureRegulatoryAdapter:
    name = "fixture_regulatory"

    def fetch(self) -> list[RawSignal]:
        return [
            RawSignal(
                source_adapter=self.name,
                source_citation="https://example-regulator.test/notices/ai-model-disclosure-rule",
                content=(
                    "A regulatory body has issued a draft rule requiring companies to disclose "
                    "when AI or machine-learning models are used in decisions affecting "
                    "customers, ahead of formal data-protection requirements taking effect."
                ),
            ),
            RawSignal(
                source_adapter=self.name,
                source_citation="https://example-regulator.test/notices/single-supplier-guidance",
                content=(
                    "New supervisory guidance calls out single-supplier concentration risk, "
                    "recommending companies formally document contingency plans wherever a "
                    "critical service depends on one external supplier."
                ),
            ),
        ]


DEFAULT_ADAPTERS: list[SignalAdapter] = [FixtureNewsAdapter(), FixtureRegulatoryAdapter()]


def fetch_all_signals(adapters: list[SignalAdapter] | None = None) -> list[RawSignal]:
    signals: list[RawSignal] = []
    for adapter in adapters if adapters is not None else DEFAULT_ADAPTERS:
        signals.extend(adapter.fetch())
    return signals
