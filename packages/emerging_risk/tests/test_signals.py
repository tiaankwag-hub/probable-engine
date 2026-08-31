from packages.emerging_risk.signals import (
    FixtureNewsAdapter,
    FixtureRegulatoryAdapter,
    RawSignal,
    fetch_all_signals,
)


class TestFixtureAdapters:
    def test_news_adapter_returns_deterministic_signals(self):
        a = FixtureNewsAdapter().fetch()
        b = FixtureNewsAdapter().fetch()
        assert a == b
        assert len(a) > 0
        assert all(isinstance(s, RawSignal) for s in a)
        assert all(s.source_adapter == "fixture_news" for s in a)

    def test_regulatory_adapter_returns_deterministic_signals(self):
        a = FixtureRegulatoryAdapter().fetch()
        b = FixtureRegulatoryAdapter().fetch()
        assert a == b
        assert all(s.source_adapter == "fixture_regulatory" for s in a)

    def test_every_signal_has_a_unique_citation(self):
        signals = fetch_all_signals()
        citations = [s.source_citation for s in signals]
        assert len(citations) == len(set(citations))


class TestFetchAllSignals:
    def test_aggregates_every_default_adapter(self):
        signals = fetch_all_signals()
        adapters_seen = {s.source_adapter for s in signals}
        assert adapters_seen == {"fixture_news", "fixture_regulatory"}

    def test_custom_adapter_list_is_respected(self):
        signals = fetch_all_signals([FixtureNewsAdapter()])
        assert all(s.source_adapter == "fixture_news" for s in signals)
