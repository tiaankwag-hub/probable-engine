# packages/ai

Provider-neutral AI abstraction (`AIProvider` interface) with a `MockAIProvider` for local
development/tests and a `VertexGeminiProvider` for production. Implements the analyst
personas (Executive Analyst, Risk Analyst, Control Advisor, Treatment Advisor, Scenario
Analyst, Emerging Risk Analyst) as prompt/response contracts, not free-form chat.

Every AI output is persisted (`ai_runs` / `ai_suggestions`: model, prompt version, timestamp,
input risk IDs, sources, response, human review status) and clearly marked AI-generated.
AI suggestions can only become authoritative data through an explicit human-approval step
handled by `apps/api` — this package never writes directly to `risks`, `controls`, or any
other authoritative table, and never receives secrets in a prompt.

Status: not yet implemented. Planned for Milestone 8 (core abstraction may be stubbed with
the mock provider earlier if a dependent feature needs the interface shape).
