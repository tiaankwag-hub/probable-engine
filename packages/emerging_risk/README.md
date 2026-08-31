# packages/emerging_risk

Signal adapters and taxonomy classification for the Emerging Risk Radar (Milestone 9).

- `signals.py`: `RawSignal`, the `SignalAdapter` protocol, and two deterministic fixture
  adapters (`FixtureNewsAdapter`, `FixtureRegulatoryAdapter`) standing in for a real external
  feed this prototype has no live connection to. Swapping in a real adapter later is adding
  one more class with the same `fetch() -> list[RawSignal]` shape.
- `classification.py`: a pure keyword-based classifier mapping a signal's text to one of the
  organization's existing risk categories — deliberately simple and fully explainable, no
  NLP/ML dependency, matching `packages/risk_engine` and `packages/simulations`'s own
  stdlib-only approach.

No database dependency and no AI provider dependency here — `packages/shared/emerging_risk_service.py`
is what persists ingested signals and calls `packages/ai`'s `analyze_signal` capability to
turn a classified signal into a candidate.
