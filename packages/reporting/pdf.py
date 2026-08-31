"""PDF Executive Summary generation (Milestone 5) via reportlab.

Pure function: a `ReportContext` in, a PDF file written to `output_path`.
Always renders the full current-state dashboard aggregation — `scope` and
`period` are recorded on the `ReportRun` and printed on the cover for
traceability, but do not yet filter the underlying data (see the
Milestone 5 plan's "Explicitly deferred" section).
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from packages.reporting.data import ReportContext

CELL_STYLE = ParagraphStyle("cell", fontName="Helvetica", fontSize=8, leading=10)


def _cell(text: str) -> Paragraph:
    """Wraps table cell text in a Paragraph so long values (risk titles,
    category names) wrap within the column instead of overflowing into
    neighboring cells — a plain string in a reportlab Table cell never
    wraps."""
    return Paragraph(text, CELL_STYLE)

BAND_COLORS = {
    "low": colors.HexColor("#1a7f37"),
    "moderate": colors.HexColor("#9a6700"),
    "high": colors.HexColor("#bc4c00"),
    "extreme": colors.HexColor("#cf222e"),
}

HEADER_STYLE = TableStyle(
    [
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d0d7de")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f6f8fa")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]
)


def render_pdf_executive_summary(context: ReportContext, output_path: str | Path) -> None:
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        title="Risk Intelligence Platform — Executive Summary",
    )
    story = [
        Paragraph("Risk Intelligence Platform", styles["Title"]),
        Paragraph("Executive Summary", styles["Heading2"]),
    ]

    meta = (
        f"Generated {context.generated_at.strftime('%Y-%m-%d %H:%M UTC')} "
        f"&middot; Scope: {context.scope_label}"
    )
    if context.period_start or context.period_end:
        meta += f" &middot; Period: {context.period_start or '—'} to {context.period_end or '—'}"
    story.append(Paragraph(meta, styles["Normal"]))
    story.append(Spacer(1, 0.3 * inch))

    d = context.dashboard
    kpi_rows = [
        ["Total risks", str(d["total_risks"])],
        ["Extreme", str(d["extreme_count"])],
        ["High", str(d["high_count"])],
        ["Moderate", str(d["moderate_count"])],
        ["Low", str(d["low_count"])],
        ["Weak controls", str(d["weak_controls_count"])],
        ["Overdue actions", str(d["overdue_actions_count"])],
        ["Risks outside appetite", str(d["risks_outside_appetite_count"])],
        ["Overdue reviews", str(d["overdue_reviews_count"])],
    ]
    kpi_table = Table(kpi_rows, colWidths=[2.5 * inch, 1.5 * inch])
    kpi_table.setStyle(HEADER_STYLE)
    story.append(Paragraph("Key Indicators", styles["Heading3"]))
    story.append(kpi_table)
    story.append(Spacer(1, 0.3 * inch))

    story.append(Paragraph("Top Risks Requiring Leadership Attention", styles["Heading3"]))
    top_rows = [["Risk", "Category", "Residual", "Band", "Owner", "Next review"]]
    for r in d["top_risks"]:
        top_rows.append(
            [
                _cell(r["title"]),
                _cell(r["category_name"] or "Uncategorized"),
                str(r["residual_score"]) if r["residual_score"] is not None else "—",
                (r["residual_band"] or "—").capitalize(),
                _cell(r["owner_email"] or "Unassigned"),
                r["next_review_date"] or "—",
            ]
        )
    if len(top_rows) == 1:
        top_rows.append(["No scored risks yet.", "", "", "", "", ""])
    top_table = Table(
        top_rows, colWidths=[2 * inch, 1.3 * inch, 0.6 * inch, 0.7 * inch, 1.5 * inch, 0.8 * inch]
    )
    style_cmds = list(HEADER_STYLE.getCommands())
    for i, r in enumerate(d["top_risks"], start=1):
        band = r["residual_band"]
        if band in BAND_COLORS:
            style_cmds.append(("TEXTCOLOR", (3, i), (3, i), BAND_COLORS[band]))
    top_table.setStyle(TableStyle(style_cmds))
    story.append(top_table)
    story.append(Spacer(1, 0.3 * inch))

    story.append(Paragraph("Risk Category Exposure", styles["Heading3"]))
    cat_rows = [["Category", "Risk count", "Avg residual score"]] + [
        [
            _cell(c["category_name"]),
            str(c["risk_count"]),
            str(c["avg_residual_score"]) if c["avg_residual_score"] is not None else "—",
        ]
        for c in d["category_exposure"]
    ]
    if len(cat_rows) == 1:
        cat_rows.append(["No categorized risks.", "", ""])
    cat_table = Table(cat_rows, colWidths=[2.5 * inch, 1.2 * inch, 1.5 * inch])
    cat_table.setStyle(HEADER_STYLE)
    story.append(cat_table)

    doc.build(story)
