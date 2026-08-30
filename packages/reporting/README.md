# packages/reporting

PDF and PowerPoint generation. Populates `templates/pptx` and `templates/pdf` template files
rather than positioning elements programmatically, so report layout can change without code
changes.

Runs only inside `apps/worker` (report generation is never executed inline in an HTTP
request). Persists `report_runs` records (inputs, template version, generated file reference,
status) so every report is reproducible and auditable.

Status: not yet implemented. Planned for Milestone 5.
