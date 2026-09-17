"""Integration tests through TestClient. The LLM call is mocked throughout;
real extraction and real scoring run against the fixture files."""

from pathlib import Path
from unittest.mock import patch

from app.schemas.report import InterviewReport
from app.services import llm

FIXTURES = Path(__file__).parent / "fixtures"

FAKE_REPORT = InterviewReport(
    title="Backend Engineer Interview Prep",
    match_score=0,  # overwritten by analysis.run_analysis regardless
    skill_gaps=[
        {"skill": "Kafka", "severity": "moderate", "similarity": 0.6, "advice": "Review Kafka."}
    ],
    technical_qs=[
        {"question": "Explain connection pooling.", "intention": "depth", "answer": "..."}
    ],
    behavioral_qs=[
        {"question": "Describe an incident you fixed.", "intention": "ownership", "answer": "..."}
    ],
    preparation_plan=[{"day": 1, "focus": "Fundamentals", "tasks": ["Review the JD"]}],
)


def _mock_llm():
    return patch.object(llm, "generate_report", return_value=FAKE_REPORT.model_copy())


def _upload_resume(client, headers, jd=None, self_desc=""):
    jd = jd or (FIXTURES / "jd_sample.txt").read_text(encoding="utf-8")
    with open(FIXTURES / "resume_sample.pdf", "rb") as f:
        return client.post(
            "/api/interview/",
            headers=headers,
            files={"resume": ("resume.pdf", f, "application/pdf")},
            data={"job_description": jd, "self_description": self_desc},
        )


def test_create_report_full_flow(client, auth_headers):
    headers = auth_headers()
    with _mock_llm():
        resp = _upload_resume(client, headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert 0 <= body["match_score"] <= 100
    assert body["title"] == "Backend Engineer Interview Prep"
    assert len(body["skill_gaps"]) >= 1


def test_create_report_rejects_short_job_description(client, auth_headers):
    headers = auth_headers()
    with _mock_llm():
        resp = _upload_resume(client, headers, jd="too short")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_report_rejects_non_pdf_non_docx(client, auth_headers):
    headers = auth_headers()
    jd = (FIXTURES / "jd_sample.txt").read_text(encoding="utf-8")
    resp = client.post(
        "/api/interview/",
        headers=headers,
        files={"resume": ("resume.txt", b"plain text resume", "text/plain")},
        data={"job_description": jd},
    )
    assert resp.status_code == 415
    assert resp.json()["error"]["code"] == "UNSUPPORTED_FILE"


def test_create_report_requires_auth(client):
    jd = (FIXTURES / "jd_sample.txt").read_text(encoding="utf-8")
    with open(FIXTURES / "resume_sample.pdf", "rb") as f:
        resp = client.post(
            "/api/interview/",
            files={"resume": ("resume.pdf", f, "application/pdf")},
            data={"job_description": jd},
        )
    assert resp.status_code == 401


def test_list_reports_returns_trimmed_shape(client, auth_headers):
    headers = auth_headers()
    with _mock_llm():
        _upload_resume(client, headers)
    resp = client.get("/api/interview/", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert set(item.keys()) == {"id", "title", "match_score", "created_at"}


def test_get_report_by_id(client, auth_headers):
    headers = auth_headers()
    with _mock_llm():
        create_resp = _upload_resume(client, headers)
    report_id = create_resp.json()["id"]
    resp = client.get(f"/api/interview/{report_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == report_id


def test_get_foreign_report_returns_404_not_403(client, auth_headers):
    owner_headers = auth_headers("owner@example.com")
    with _mock_llm():
        create_resp = _upload_resume(client, owner_headers)
    report_id = create_resp.json()["id"]

    other_headers = auth_headers("other@example.com")
    resp = client.get(f"/api/interview/{report_id}", headers=other_headers)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_get_missing_report_returns_404(client, auth_headers):
    headers = auth_headers()
    resp = client.get("/api/interview/does-not-exist", headers=headers)
    assert resp.status_code == 404


def test_delete_report(client, auth_headers):
    headers = auth_headers()
    with _mock_llm():
        create_resp = _upload_resume(client, headers)
    report_id = create_resp.json()["id"]

    resp = client.delete(f"/api/interview/{report_id}", headers=headers)
    assert resp.status_code == 204

    resp = client.get(f"/api/interview/{report_id}", headers=headers)
    assert resp.status_code == 404


def test_delete_foreign_report_returns_404(client, auth_headers):
    owner_headers = auth_headers("owner2@example.com")
    with _mock_llm():
        create_resp = _upload_resume(client, owner_headers)
    report_id = create_resp.json()["id"]

    other_headers = auth_headers("other2@example.com")
    resp = client.delete(f"/api/interview/{report_id}", headers=other_headers)
    assert resp.status_code == 404


def test_oversized_upload_returns_413_without_reading_it_all(client, auth_headers):
    headers = auth_headers()
    jd = (FIXTURES / "jd_sample.txt").read_text(encoding="utf-8")
    big = b"%PDF-1.7\n" + b"0" * (5 * 1024 * 1024 + 10)
    resp = client.post(
        "/api/interview/",
        headers=headers,
        files={"resume": ("big.pdf", big, "application/pdf")},
        data={"job_description": jd},
    )
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_failed_analysis_refunds_rate_limit_slot(client, auth_headers):
    from app.core import limiter as limiter_module
    from app.core.exceptions import LLMUnavailableError

    headers = auth_headers()
    limiter_module._limiter = limiter_module.RateLimiter(1, 10)
    try:
        with patch.object(llm, "generate_report", side_effect=LLMUnavailableError()):
            resp = _upload_resume(client, headers)
        assert resp.status_code == 503
        # The failed run must not have consumed the user's only slot.
        with _mock_llm():
            resp = _upload_resume(client, headers)
        assert resp.status_code == 201, resp.text
        with _mock_llm():
            resp = _upload_resume(client, headers)
        assert resp.status_code == 429
    finally:
        limiter_module._limiter = None


def test_skill_gaps_come_from_scoring_not_llm(client, auth_headers):
    headers = auth_headers()
    with _mock_llm():
        resp = _upload_resume(client, headers)
    gaps = resp.json()["skill_gaps"]
    # FAKE_REPORT claims Kafka at 0.6/moderate; scoring decides, not the model.
    assert all(not (g["skill"] == "Kafka" and g["similarity"] == 0.6) for g in gaps)
    assert all(g["severity"] != "minor" for g in gaps)


def test_corrupted_pdf_upload_returns_422(client, auth_headers):
    headers = auth_headers()
    jd = (FIXTURES / "jd_sample.txt").read_text(encoding="utf-8")
    resp = client.post(
        "/api/interview/",
        headers=headers,
        files={"resume": ("bad.pdf", b"%PDF-1.4\nbroken" * 50, "application/pdf")},
        data={"job_description": jd},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "EXTRACTION_FAILED"
