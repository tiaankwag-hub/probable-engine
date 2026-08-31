from datetime import date, datetime, timezone

from packages.reporting.data import ReportContext
from packages.reporting.pdf import render_pdf_executive_summary

SAMPLE_DASHBOARD = {
    "total_risks": 3,
    "extreme_count": 1,
    "high_count": 1,
    "moderate_count": 1,
    "low_count": 0,
    "unscored_count": 0,
    "overdue_reviews_count": 2,
    "weak_controls_count": 1,
    "overdue_actions_count": 4,
    "risks_outside_appetite_count": 1,
    "top_risks": [
        {
            "id": "r1",
            "risk_code": "RSK-0001",
            "title": "A risk with a fairly long title that should wrap onto a second line",
            "category_name": "Cyber & Information Security",
            "residual_score": 12.5,
            "residual_band": "extreme",
            "owner_email": "owner@example.com",
            "next_review_date": "2026-01-01",
        },
    ],
    "category_exposure": [
        {"category_id": "c1", "category_name": "Cyber & Information Security", "risk_count": 3, "avg_residual_score": 8.1},
    ],
}


def _context(dashboard=None) -> ReportContext:
    return ReportContext(
        generated_at=datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
        period_start=date(2026, 5, 1),
        period_end=date(2026, 5, 31),
        scope_label="All risks",
        dashboard=dashboard if dashboard is not None else SAMPLE_DASHBOARD,
    )


class TestRenderPdfExecutiveSummary:
    def test_writes_a_valid_pdf_file(self, tmp_path):
        output_path = tmp_path / "report.pdf"
        render_pdf_executive_summary(_context(), output_path)

        assert output_path.exists()
        content = output_path.read_bytes()
        assert content.startswith(b"%PDF")
        assert len(content) > 500

    def test_handles_empty_dashboard_without_crashing(self, tmp_path):
        empty_dashboard = {**SAMPLE_DASHBOARD, "top_risks": [], "category_exposure": []}
        output_path = tmp_path / "empty.pdf"

        render_pdf_executive_summary(_context(empty_dashboard), output_path)

        assert output_path.exists()
        assert output_path.read_bytes().startswith(b"%PDF")
