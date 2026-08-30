# Domain Model

The internal domain model is independent of the spreadsheet schema described in the brief.
Spreadsheet column names appear only inside the import-mapping layer (`packages/shared`'s
import module and the `import_*` tables) — never as domain field names.

## Import mapping layer

Decouples "whatever a source file calls a column" from "what the domain calls a field".

- `import_jobs` — one row per upload: file reference (object storage), uploader, status
  (`uploaded` → `mapped` → `validated` → `previewed` → `committed` / `failed`), timestamps.
- `import_column_mappings` — per job, `source_column -> domain_field` pairs, plus an optional
  transform (e.g. date parsing, enum normalization). Mappings can be saved as reusable
  templates so repeat imports from the same source don't require re-mapping.
- `import_row_errors` — per job, row number, field, error type, raw value; surfaced to the
  user before commit.
- Commit never overwrites an existing authoritative risk silently: a row that matches an
  existing `risk_code` produces a proposed update requiring explicit confirmation (or is
  routed as a new `risk_history` version), and every commit emits an `audit_events` record
  with `source = 'import'` and the `import_jobs.id`.

Example mappings from the brief's 37 spreadsheet columns to domain fields (illustrative, not
exhaustive — full mapping table is configured per job, not hard-coded):

| Spreadsheet column | Domain field(s) |
|---|---|
| `risk_id` | `risks.risk_code` |
| `risk_statement_cause_event_impact` | split via transform into `risks.cause`, `risks.event`, `risks.impact`, `risks.statement` |
| `financial_impact_1_5` … `health_safety_impact_1_5` | six rows in `risk_impact_scores` (one per dimension) |
| `overall_impact_calc`, `inherent_score_calc`, `inherent_band_calc`, `residual_score_calc`, `residual_band_calc` | imported as historical reference values only; recomputed authoritatively by `packages/risk_engine` on import and on every subsequent assessment change, with a validation warning if the imported value disagrees with the recomputed one |
| `key_controls_ids_or_short_list` | parsed into `risk_controls` links where a matching `controls` row exists; unmatched entries become validation issues, not silently dropped |
| `actions_link_jira_servicenow_etc` | `actions.evidence` / an external reference field, not a first-class integration in Milestone 1 |

## Core entities

### Identity & access
- **users** — id, email, display name, status, SSO subject identifier.
- **roles** — Viewer, Risk Owner, Control Owner, Risk Manager, Executive, Administrator,
  Auditor.
- **user_roles** — many-to-many, optionally scoped to a department/business unit.

### Risk register
- **risks** — `id`, `risk_code`, `title`, `statement`, `cause`, `event`, `impact`, `category`
  (FK), `business_process`, `department`, `owner` (FK user), `accountable_executive` (FK
  user), `status`, `decision`, `acceptance_rationale`, `raised_date`, `next_review_date`,
  `velocity`, `confidence`, `treatment_summary`, `latest_update`, `created_at`, `updated_at`,
  `version` (optimistic concurrency). Computed scoring fields
  (`likelihood`, `overall_impact`, `inherent_score`, `inherent_band`, `control_effectiveness`,
  `residual_score`, `residual_band`) are derived and stored redundantly for query performance
  but are only ever written by `packages/risk_engine`, never directly by a user or import.
- **risk_categories** — configurable taxonomy (id, name, parent, description).
- **risk_assessments** — one row per assessment event for a risk: likelihood, computed
  scores/bands, control-effectiveness input, `scoring_config_version` (FK), assessed_by,
  assessed_at. `risks`' current score fields always mirror the latest assessment.
- **risk_impact_scores** — per assessment, per dimension (Financial, Customer/Service,
  Operational Delivery, Legal/Regulatory, Reputation, Health & Safety): raw 1–5 score.
- **risk_history** — append-only snapshot of a risk's full field state at each change, keyed
  by `risk_id` + `version`. Never updated or deleted.
- **risk_appetite** — configurable by category and optionally business unit: appetite band,
  tolerance band, limit value, effective_from/to. Drives the within/approaching/outside/
  material-breach flag, computed at read time (or cached on `risks`) rather than hard-coded.
- **scoring_config** (impact scale definitions, band thresholds, control-reduction formula
  parameters, priority-engine weights) — versioned; every `risk_assessments` row references
  the config version used, so historical scores remain reproducible after a config change.

### Controls & assurance
- **controls** — `control_id`, name, description, `control_type`,
  preventive/detective/corrective, manual/automated, owner (FK user), frequency,
  design_effectiveness, operating_effectiveness, last_tested, next_test, evidence (object
  storage reference), status.
- **risk_controls** — many-to-many between `risks` and `controls`.
- **control_assessments** — periodic effectiveness assessments of a control (distinct from a
  point-in-time test — this is the ongoing rating history feeding `control_effectiveness`).
- **control_tests** — `test_id`, control (FK), tester, date, test_method, result
  (Effective / Partially Effective / Ineffective / Not Tested), evidence, finding,
  remediation_action.

### Actions, issues, incidents
- **actions** — `action_id`, risk (FK, nullable if linked to an issue instead), owner,
  due_date, priority, status, completion_percent, expected_risk_reduction, evidence,
  completed_date. Overdue = `due_date < today` and `status != completed`; escalation rules
  configurable (see priority engine).
- **issues** — description, source, linked risk(s), linked control(s); can generate an
  `actions` row (remediation).
- **incidents** — description, date, severity, linked risk(s), linked control(s) (to record a
  failed control); an incident can be marked as triggering a risk review (sets
  `risks.next_review_date`) and/or as evidence supporting a likelihood increase (feeds a new
  `risk_assessments` row, subject to human confirmation, not automatic silent change).

### Snapshots & change tracking
- **snapshots** — a named/periodic point-in-time capture (e.g. monthly close).
- **snapshot_risks** — the frozen state of every risk at that snapshot (score, band, status,
  owner, appetite flag, key control effectiveness) — enables current-vs-previous-period
  comparison without recomputing from `risk_history` every time.

### Scenarios & simulation
- **scenarios** — description, assumptions, affected risks/controls (link tables), duration,
  financial range, operational impact, recovery assumptions.
- **scenario_risks** — many-to-many, `scenarios` ↔ `risks`.
- **simulation_configs** — `loss_min`, `loss_most_likely`, `loss_max`,
  `annual_event_frequency`, `distribution_type`, `confidence`, `correlation_group`, target
  (single risk or portfolio/scenario), iterations, seed.
- **simulation_runs** — one row per execution of a config: status, started_at, completed_at,
  seed used, iterations used.
- **simulation_results** — outputs of a run: expected annual loss, median, P75/P90/P95/P99,
  probability of exceeding a stored threshold, and references to stored histogram/exceedance
  curve data (object storage or a compact serialized array).

### Emerging risk radar
- **emerging_signals** — raw ingested signal: source adapter, source citation/URL,
  ingested_at, raw content reference, classification (taxonomy tag).
- **emerging_risk_candidates** — derived from one or more signals: organisation-relevance
  assessment, matched existing risk (nullable FK), lifecycle status (`Candidate` →
  `Under Review` → `Accepted as Emerging Risk` / `Linked to Existing Risk` / `Dismissed`),
  reviewed_by, reviewed_at. AI can create/update a *candidate*; only a human transition (via
  the API, audited) can move a candidate to an official risk.

### AI
- **ai_runs** — model, prompt_version, timestamp, requested_by, capability (Executive
  Analyst / Risk Analyst / etc.), input risk IDs, sources, raw response, latency, status.
- **ai_suggestions** — a structured, actionable suggestion derived from an `ai_runs` output
  (e.g. "increase likelihood to 4 because X"), `human_review_status`
  (`pending` / `approved` / `rejected`), reviewed_by, reviewed_at, and — only if approved —
  the resulting authoritative change is applied through the normal risk-update path (so it
  still produces a `risk_history` row and an `audit_events` row attributing the change to the
  reviewing human, with a note that it originated from an AI suggestion).

### Reporting
- **reports** — a named report definition/template reference (e.g. "Monthly Executive PDF",
  "1-slide ELT PPTX").
- **report_runs** — one row per generation: report (FK), parameters (period, scope),
  requested_by, status, generated_file reference (object storage), generated_at.

### Audit
- **audit_events** — `actor`, `timestamp`, `entity`, `entity_id`, `action`, `old_value`
  (JSON), `new_value` (JSON), `reason`, `source` (`ui` / `api` / `import` / `ai-approved` /
  `system`). Immutable — no update or delete path exists for this table at the application
  layer.

## Versioning strategy

- **Optimistic concurrency**: `risks.version` increments on every authoritative write; a
  `PATCH` must supply the version it read, rejected with `409` on mismatch.
- **Full history**: `risk_history` stores the complete field state at each version, so "what
  did this risk look like on date X" never requires replaying audit deltas.
- **Config versioning**: `scoring_config` and `risk_appetite` changes are versioned and
  timestamped, not overwritten in place, so past scores/appetite flags remain explainable.

See `docs/architecture/03-er-diagram.md` for the entity-relationship diagram and
`docs/adr/` for the reasoning behind the import-mapping layer, audit strategy, and
deterministic-scoring decisions.
