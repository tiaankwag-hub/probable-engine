# templates/import

Generates the downloadable Risk Register import template offered on the Import Wizard page
(`apps/web/app/imports/page.tsx`), served as a static file from
`apps/web/public/templates/risk-register-import-template.xlsx`.

`build_risk_register_template.py` reads its column list, required/optional split, enum
values, and scoring formulas directly from `packages/shared/importing/mapping.py`,
`packages/shared/importing/validation.py`, `packages/shared/importing/transforms.py`, and
`packages/risk_engine/scoring.py` — not from the brief's original documented 34-column
assumption. It deliberately excludes the platform-calculated reference columns
(`*_calc`) and the columns accepted by the mapper but not yet wired into risk creation
(Controls/Actions link columns), so every column in the template is something a user fills
in that actually does something.

Regenerate after changing import mapping/validation/scoring rules:

```
source .venv/bin/activate
python templates/import/build_risk_register_template.py
```

This overwrites `apps/web/public/templates/risk-register-import-template.xlsx` directly —
there is no separate build/copy step. After regenerating, re-verify it round-trips cleanly
through the real import pipeline before committing:

```python
from packages.shared.importing.parser import parse_columns, parse_rows
from packages.shared.importing.mapping import DEFAULT_RISK_REGISTER_MAPPING, build_import_rows
from packages.shared.importing.validation import validate_rows, has_blocking_errors

path = "apps/web/public/templates/risk-register-import-template.xlsx"
columns = parse_columns(path)
by_source = {m.source_column: m for m in DEFAULT_RISK_REGISTER_MAPPING}
assert not [c for c in columns if c not in by_source], "a header no longer auto-maps"
mappings = [by_source[c] for c in columns]
rows = build_import_rows(parse_rows(path), mappings)
issues = validate_rows(rows, known_category_names={"Operational"}, known_owner_emails={"risk.owner@example.com"})
assert not has_blocking_errors(issues), issues
```
