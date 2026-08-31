# Milestone 5 Implementation Plan — COMPLETE

PowerPoint and PDF reporting: a Risk Manager, Executive, or Administrator requests a report,
the API enqueues a background job, `apps/worker` renders the file and stores it, and the
Reports page polls until it's ready to download.

## What was built

### Database (PostgreSQL + Alembic)
New migration adds `report_runs` (report type, requester, period/scope metadata, status,
object-storage key, error, timestamps). The domain model's original `reports`/`report_runs`
split (a separate table of named report *definitions*) is simplified to a single `ReportRun`
row carrying `report_type` directly — the API design's actual endpoints
(`POST /reports/pdf`, `POST /reports/powerpoint`) never call for a template-management CRUD,
and nothing in this prototype ever creates a new named report definition; the three templates
are fixed code in `packages/reporting`, not admin-managed data.

### `packages/reporting` (new package)
- **`data.py`**: `build_report_context()` reuses the exact same
  `packages/shared/dashboard_service.compute_executive_dashboard()` aggregation the Executive
  Dashboard already computes — a report is that same data rendered to a file instead of a
  browser page, not a separate query path.
- **`pdf.py`**: a one-to-several-page PDF Executive Summary via `reportlab` — KPI table, a
  "Top Risks Requiring Leadership Attention" table (band-colored), and a Risk Category
  Exposure table. Long cell text (risk titles, category names) is wrapped in `Paragraph`
  objects, not plain strings — reportlab table cells don't wrap plain text, they overflow
  into neighboring cells (caught during manual review of the first generated PDF; fixed
  before any test was written against it).
- **`pptx.py`**: `python-pptx` generation for both PPTX templates —
  `render_pptx_one_slide()` (title, a compact KPI row, a 6-row top-risks table) and
  `render_pptx_two_slide_elt()` (slide 1: risk overview KPIs + category exposure; slide 2:
  governance KPIs + a fuller top-risks table, band-colored) — a board-pack shape distinct
  from the one-slide summary, not just a truncated version of it.
- Both renderers are pure functions: a `ReportContext` in, a file written to a given path out
  — no I/O beyond that, so they're unit-testable without a database (see Tests below) and
  reusable if a future milestone wants to attach a rendered report to something else (e.g. an
  AI-drafted executive summary in Milestone 8).

### Backend (apps/api + apps/worker)
- **Reports API** (`apps/api/app/routers/reports.py`): `POST /api/v1/reports/pdf` and
  `POST /api/v1/reports/powerpoint` (body: optional `period_start`/`period_end`/`scope`, and
  for PowerPoint a `template` of `one_slide` or `two_slide_elt`) each create a `ReportRun` row
  and enqueue a `report_generate` background job — the same JobQueue pattern (ADR 0005) the
  Import Wizard's commit step already uses, since rendering is CPU-bound and shouldn't block
  a request. `GET /api/v1/reports/runs` (list) and `GET /api/v1/reports/runs/{id}` (single)
  for polling status; `GET /api/v1/reports/runs/{id}/download` streams the finished file with
  the correct content type and filename once `status=succeeded` (400 if requested earlier).
- **`apps/worker/app/jobs/report_generate.py`**: loads the `ReportRun`, marks it `running`,
  builds the report context, calls the matching renderer, stores the output via the
  `ObjectStore` abstraction (ADR 0011 — `LocalFileSystemStore` locally, Cloud Storage in
  Milestone 11), and marks the run `succeeded` with the storage key. On a renderer exception,
  the run is explicitly marked `failed` with the error message *before* re-raising — unlike
  the Import Wizard's commit job, a `ReportRun`'s status is directly user-visible on the
  Reports page, so leaving it stuck at `running` forever on an unexpected failure would be a
  visible bug, not just an internal one.
- **RBAC**: `GENERATE_REPORTS` (request a new report — Risk Manager, Executive,
  Administrator, matching the brief's matrix exactly) and `VIEW_REPORT_RUNS` (list/get/download
  — the same three roles plus Auditor, who can view but not request, also per the brief).
- **CORS**: added `expose_headers=["Content-Disposition"]` so the frontend can read the
  server-supplied filename off a cross-origin download response — without it, the browser
  hides that header from JavaScript entirely, and the download would fall back to a generic
  name.

### Frontend
`/reports`: a "Generate a report" panel (hidden unless the signed-in role can generate,
mirroring the API's own enforcement) with three buttons, and a Report Runs table showing
every run's type, request time, and live status. While any run is `pending`/`running` the
page polls every 2 seconds and stops automatically once nothing is left in flight. A
`Download` link appears once a run succeeds; clicking it fetches the file as an
authenticated `Blob` (a plain `<a href>` can't carry the bearer token) and triggers a normal
browser save with the server's filename. A role without `VIEW_REPORT_RUNS` sees a plain
explanatory message instead of an empty table with an unexplained error line.

## Tests

- 5 `packages/reporting` unit tests (no database): both PDF and PPTX renderers produce valid
  output files from a hand-built `ReportContext`, including the empty-dashboard case (no
  scored risks, no categorized risks) that must render a "no data" placeholder row rather
  than crash. Reopening the generated `.pptx` files with `python-pptx` and asserting on
  actual slide count, table dimensions, and cell text is what caught a real bug: an empty
  table cell produces a paragraph with zero runs, and the original `_add_table()` blindly
  indexed `runs[0]` to set font size — `IndexError` on any row with a blank cell. Fixed by
  skipping font styling when a cell has no runs.
- 3 `apps/worker` tests exercising `report_generate.handle()` through `process_one()` exactly
  like the Import Wizard's worker tests: a PDF run and a PPTX run both reach `succeeded` with
  a real file at the stored key (opened and its magic bytes checked), and a `ReportRun` that
  doesn't exist marks the `BackgroundJob` `failed` with a clear message.
- 15 `apps/api` integration tests: RBAC on both request endpoints (all 3 allowed roles, all 4
  forbidden roles), PowerPoint template selection, list/get/404, download-before-ready (400),
  download-after-processing for both PDF and PPTX (correct content type, real file bytes),
  and a non-viewer role forbidden from downloading. These synchronously call the worker's
  `process_one()` against the same test database mid-test (rather than mocking the job
  queue), so the assertions are against what the renderer actually produced, not a stub.

**235 pytest tests, all passing** (up from 215). Frontend verified via `npx tsc --noEmit` and
`npm run build` (both clean, `/reports` present in the route manifest), plus a full live-stack
Playwright pass: requested a PDF and both PowerPoint templates as different eligible roles,
watched the run transition from Pending → Succeeded via the page's own polling (no manual
refresh), clicked Download, and confirmed the browser actually saved a real `.pptx` file
(`file` command: "Microsoft PowerPoint 2007+") under the server-supplied filename. Also
verified the Viewer role sees the polished "no access" message rather than a raw permission
error.

One verification gap, disclosed rather than worked around: this sandbox's `libreoffice
--headless --convert-to pdf` fails to load even a trivial python-pptx-generated file
(`Error: source file could not be loaded`, reproduced against a one-shape file from a bare
`Presentation()` with no customization at all) — a sandbox/environment limitation in the same
family as the Docker Hub pull restriction noted in Milestone 1, not a defect in the generated
files. The `.pptx` files were instead verified by (a) `file` reporting valid OOXML, (b)
reopening them with `python-pptx` and asserting on actual slide/table/cell content matching
the input data, and (c) a real user's browser (Playwright/Chromium) successfully downloading
and saving them. A user with a real PowerPoint or LibreOffice install can open the downloaded
files directly.

## Local demonstration

1. **Start:** `docker compose up --build` (from the repo root, after `cp .env.example .env`).
2. **Open:** http://localhost:3000
3. **What you should see and be able to test (in addition to Milestones 1–4):**
   - **Reports** (`/reports`): sign in as `risk.manager@example.com`,
     `executive@example.com`, or `admin@example.com` to see the "Generate a report" panel.
     Click any of the three buttons — a new row appears immediately with status "Pending",
     automatically flips to "Succeeded" within a few seconds (no page refresh needed), and a
     Download link appears. Click it to save the real `.pdf` or `.pptx` file and open it —
     it reflects the current seeded risk register (KPIs, top risks, category exposure).
   - Sign in as `auditor@example.com` to confirm they can see the Report Runs history and
     download existing files, but have no "Generate a report" panel (view-only, per RBAC).
   - Sign in as `viewer@example.com`, `risk.owner@example.com`, or `control.owner@example.com`
     to confirm the page shows a plain "your role doesn't have access" message rather than an
     error or a misleadingly empty table.
4. **Test credentials:** unchanged — see
   [`docs/architecture/milestone-1-plan.md`](milestone-1-plan.md#local-demonstration).
5. **Stop:** `docker compose down` (`-v` to also wipe volumes).

Verified the same way as prior milestones (this sandbox's Docker Hub pull restriction is
unchanged — see Milestone 1's note): every service run as a local process against the same
Postgres instance and environment variables the Compose file uses, migrations applied with
Alembic, all 235 pytest tests passing, and a full Playwright pass against a live stack as
described above.

## Bugs found and fixed during verification

- **reportlab table cells don't wrap plain strings** — the first generated PDF had risk
  titles and category names overlapping into neighboring columns whenever they were longer
  than the column width. Fixed by wrapping those cell values in `reportlab.platypus.Paragraph`
  objects (a small `_cell()` helper with a shared style) instead of passing raw strings.
  Caught by reading the actual rendered PDF, not by any automated test — the fix was in place
  before `test_pdf.py` was written, so there's no regression test proving the wrap behavior
  itself, only that the empty-data path doesn't crash.
- **`IndexError` on an empty PPTX table cell** — `cell.text = ""` produces a paragraph with
  zero runs, and `_add_table()` unconditionally indexed `runs[0]` to apply font size. Caught
  by `test_handles_no_scored_risks`, which was written specifically to exercise the "no data"
  fallback row (`["No scored risks yet.", "", ""]`) that both PPTX templates render when the
  dashboard has no scored risks yet. Fixed by skipping font styling when a cell's run list is
  empty.

## Explicitly still deferred

- **Scope/period filtering is metadata only.** `period_start`, `period_end`, and `scope` are
  accepted by the request endpoints, stored on the `ReportRun`, and printed on the report's
  cover/subtitle line for traceability — but the underlying content is always the full
  current-state dashboard aggregation, not filtered by category, business unit, or a
  historical period. Wiring real scope filtering into
  `packages/shared/dashboard_service.compute_executive_dashboard()` is a reasonably contained
  follow-up, deferred rather than rushed into this milestone.
- **No scheduled/recurring report generation** (e.g. an automatic month-end PDF) — every
  report in this milestone is requested on demand through the UI or API.
- Monte Carlo simulations (Milestones 6–7), AI integration (8), Emerging Risk Radar (9), MCP
  gateway (10), and GCP hardening (11) are unchanged.
