# Current-State Assessment

## Repository inspection (2026-08-30)

The repository `tiaankwag-hub/probable-engine` was inspected before any work began.

**Finding: the repository is empty.**

- `git status` on the checked-out branch (`claude/risk-intelligence-platform-setup-laxkhp`)
  reported "No commits yet".
- `git ls-remote --heads origin` returned no refs.
- The GitHub API confirms zero branches and returns `409 Git Repository is empty` for the
  default branch reference.
- There is no `legacy/` directory, no Streamlit application, no Excel/CSV risk register, and
  no prior documentation or configuration of any kind on disk or on the remote.

This differs from the task brief, which describes a `legacy/` directory containing a prior
Streamlit prototype and a fictitious Risk Register spreadsheet as available reference
material. Neither is present. No files were modified, no legacy code was reviewed, and no
spreadsheet was parsed, because none exist to review or parse.

## How this assessment proceeds despite the gap

The task brief itself contains two things that substitute for the missing artifacts, and
both are treated as authoritative for Milestone 0:

1. **A complete, explicit schema** for the source Risk Register spreadsheet (36 named
   columns, listed verbatim in the brief's "CURRENT SOURCE DATA" section). This is used as
   the input side of the import-mapping layer design (see
   `docs/adr/0008-import-mapping-layer.md`) in place of an actual `.xlsx` file.
2. **A narrative functional description** of the prior Streamlit prototype (risk engine,
   executive dashboard, heatmap, Monte Carlo, emerging-risk forecast, scenario analysis, PDF
   and PowerPoint reporting) used strictly as a list of *capabilities to reproduce*, not as an
   implementation to inspect. This is consistent with the brief's own instruction to treat
   the legacy app as a functional reference only and not to reuse its architecture — moot
   here since no legacy code exists to reuse, but the resulting capability list still drives
   the roadmap in `docs/architecture/roadmap.md`.

No assumption in this document set depends on having seen real data. Where a decision would
normally be validated against a sample file (column data types, actual value ranges for
`status`/`decision`/band fields, real-world messiness like blank cells or free-text dates),
that validation is called out explicitly as deferred and tracked as a risk below and in the
Milestone 1 plan.

## Assumptions introduced by the missing artifacts

| # | Assumption | Basis | Where it's tracked |
|---|---|---|---|
| A1 | The 36-column schema in the brief is the *actual* spreadsheet layout (column order, header text, no hidden columns/merged headers/extra sheets). | No file to verify against. | Milestone 1 plan — import wizard must handle header mismatches gracefully, not assume exact match. |
| A2 | Enumerated fields (`status`, `decision`, `inherent_band_calc`, `residual_band_calc`, `risk_velocity_optional`, `confidence_optional`) use small, stable value sets compatible with the domain enums proposed in `02-domain-model.md`. | Brief names these as "calc" or "optional" fields but does not enumerate values. | Import Wizard's validation step (Milestone 1) surfaces unmapped/unexpected values instead of silently coercing them. |
| A3 | Dates (`raised_date`, `next_review_date`, `due_date`, `last_updated_date`) are real Excel dates, not free text. | Typical for this kind of register, unverified. | Import Wizard validation. |
| A4 | The prototype's Monte Carlo, PDF, and PPTX behavior described narratively is representative of what leadership actually wants reproduced (no undocumented prototype-only features). | No prototype code available to inspect. | Milestones 5–7 will demo outputs to the user before being marked stable, per the "show what was completed" rule at each milestone. |

## Risks introduced by the missing artifacts

| # | Risk | Impact | Mitigation |
|---|---|---|---|
| R1 | Real spreadsheet deviates from the documented schema (extra columns, renamed headers, multiple sheets, formulas instead of values). | Import Wizard column-mapping step could fail or mis-map on first real import. | Import Wizard (Milestone 1) is built as a generic "upload → inspect columns → map → validate → preview → import" flow specifically *because* the mapping is configurable, not hard-coded — see ADR 0008. First real file should be run through in preview mode (no commit) before any production import. |
| R2 | Real data contains values that don't fit the assumed enums/scales (e.g. a 6th impact dimension score, non-numeric likelihood). | Validation step could reject rows that are actually valid. | Validation issues are surfaced to a human for review/remap rather than silently dropped or coerced (brief's explicit "never silently overwrite" principle extended to "never silently drop/coerce"). |
| R3 | No legacy code exists to compare against for subtle prototype business rules (e.g. exact band cut-offs, exact reduction formula). | Milestone 2 deterministic scoring could diverge from stakeholder expectations set by the prototype. | Scoring configuration is stored in the database and versioned (ADR 0007), not hard-coded, so thresholds can be corrected post-hoc without a code change once the real formula is confirmed with the user. |
| R4 | Repository being empty may indicate the intended source repo, branch, or attachment differs from what this session has access to. | Effort could be spent re-deriving something that already exists elsewhere. | Flagged to the user in this Milestone 0 report; user can attach the correct repo/branch or supply the spreadsheet directly if one exists. |

## Conclusion

Milestone 0 proceeds on the written specification in the task brief as the sole authoritative
source. Nothing here was invented beyond what the brief already states; gaps are tracked as
assumptions/risks above rather than silently assumed away.
