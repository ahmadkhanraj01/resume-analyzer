"""WeasyPrint needs Pango/GDK-Pixbuf/Cairo native libraries. They are
installed via apt-get in the Dockerfile for the real deploy target, but are
commonly absent on a bare Windows dev machine. Skip rather than fail in that
case; see PHASES.md Phase 8's note about verifying these libs on deploy."""

import pytest

try:
    # WeasyPrint raises OSError (not ImportError) at import time when its
    # native libraries are missing, so pytest.importorskip alone won't
    # catch it; the try/except here does.
    from weasyprint import HTML

    HTML(string="<html><body>probe</body></html>").write_pdf()
    WEASYPRINT_USABLE = True
except Exception:
    WEASYPRINT_USABLE = False

pytestmark = pytest.mark.skipif(
    not WEASYPRINT_USABLE,
    reason="WeasyPrint native libraries (Pango/GDK-Pixbuf/Cairo) not installed on this machine",
)

from app.services.pdf import render_report_pdf  # noqa: E402

SAMPLE_REPORT = {
    "id": "abc-123",
    "title": "Backend Engineer Interview Prep",
    "match_score": 78,
    "created_at": "2026-01-01T00:00:00Z",
    "skill_gaps": [
        {
            "skill": "Kafka",
            "severity": "moderate",
            "similarity": 0.6,
            "advice": "Review Kafka basics.",
        }
    ],
    "technical_qs": [
        {
            "question": "How would you scale this?",
            "intention": "system design",
            "answer": "Discuss caching.",
        }
    ],
    "behavioral_qs": [
        {
            "question": "Describe a conflict you resolved.",
            "intention": "teamwork",
            "answer": "Use STAR.",
        }
    ],
    "preparation_plan": [{"day": 1, "focus": "Fundamentals", "tasks": ["Review the JD"]}],
}


def test_render_report_pdf_produces_pdf_bytes():
    pdf_bytes = render_report_pdf(SAMPLE_REPORT)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500


def test_render_report_pdf_handles_empty_lists():
    empty = {
        **SAMPLE_REPORT,
        "skill_gaps": [],
        "technical_qs": [],
        "behavioral_qs": [],
        "preparation_plan": [],
    }
    pdf_bytes = render_report_pdf(empty)
    assert pdf_bytes.startswith(b"%PDF")
