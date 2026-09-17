"""Mocked providers only. No test here hits a live LLM API, per RULES.md."""

from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.core.exceptions import LLMUnavailableError
from app.services import llm

VALID_REPORT_JSON = """{
  "title": "Backend Engineer Interview Prep",
  "match_score": 88,
  "skill_gaps": [
    {"skill": "Kafka", "severity": "moderate", "similarity": 0.6, "advice": "Review Kafka basics."}
  ],
  "technical_qs": [
    {"question": "How would you scale a Postgres-backed API?", "intention": "system design", "answer": "Discuss read replicas, caching, and connection pooling."}
  ],
  "behavioral_qs": [
    {"question": "Tell me about a time you fixed a production incident.", "intention": "ownership", "answer": "Use the STAR method."}
  ],
  "preparation_plan": [
    {"day": 1, "focus": "Review fundamentals", "tasks": ["Read the JD twice", "List your top 3 gaps"]}
  ]
}"""


def _settings() -> Settings:
    return Settings(
        jwt_secret="test-secret-do-not-use-in-prod-at-least-32-bytes",
        groq_api_key="fake",
        gemini_api_key="fake",
    )


def test_generate_report_discards_llm_match_score():
    with patch.object(llm, "_call_groq", return_value=VALID_REPORT_JSON):
        report = llm.generate_report(
            resume_text="resume",
            job_description="jd",
            self_description="",
            covered_skills=["Python"],
            missing_skills=["Kafka"],
            match_score=42,
            settings=_settings(),
        )
    assert report.match_score == 42  # never 88, the value the model returned
    assert report.title == "Backend Engineer Interview Prep"


def test_generate_report_strips_markdown_fences():
    fenced = f"```json\n{VALID_REPORT_JSON}\n```"
    with patch.object(llm, "_call_groq", return_value=fenced):
        report = llm.generate_report(
            resume_text="r",
            job_description="jd",
            self_description="",
            covered_skills=[],
            missing_skills=[],
            match_score=10,
            settings=_settings(),
        )
    assert report.match_score == 10


def test_malformed_response_retries_once_then_succeeds():
    """First call returns invalid JSON; the retry (same provider, error
    appended) returns valid JSON. Proves the self-correction retry path."""
    calls = {"count": 0}

    def fake_groq(prompt: str, settings: Settings, max_tokens: int) -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            return "{not valid json at all"
        assert "previous response failed validation" in prompt
        return VALID_REPORT_JSON

    with patch.object(llm, "_call_groq", side_effect=fake_groq):
        report = llm.generate_report(
            resume_text="r",
            job_description="jd",
            self_description="",
            covered_skills=[],
            missing_skills=[],
            match_score=50,
            settings=_settings(),
        )
    assert calls["count"] == 2
    assert report.match_score == 50


def test_both_providers_invalid_twice_raises_llm_unavailable():
    with (
        patch.object(llm, "_call_groq", return_value="not json"),
        patch.object(llm, "_call_gemini", return_value="also not json"),
    ):
        with pytest.raises(LLMUnavailableError):
            llm.generate_report(
                resume_text="r",
                job_description="jd",
                self_description="",
                covered_skills=[],
                missing_skills=[],
                match_score=1,
                settings=_settings(),
            )


def test_groq_failure_falls_back_to_gemini():
    with (
        patch.object(llm, "_call_groq", side_effect=RuntimeError("rate limited")),
        patch.object(llm, "_call_gemini", return_value=VALID_REPORT_JSON),
    ):
        report = llm.generate_report(
            resume_text="r",
            job_description="jd",
            self_description="",
            covered_skills=[],
            missing_skills=[],
            match_score=7,
            settings=_settings(),
        )
    assert report.match_score == 7


def test_extract_skills_llm_returns_empty_list_on_total_failure():
    with (
        patch.object(llm, "_call_groq", side_effect=RuntimeError("down")),
        patch.object(llm, "_call_gemini", side_effect=RuntimeError("down")),
    ):
        assert llm.extract_skills_llm("some jd text", _settings()) == []


def test_extract_skills_llm_parses_json_array():
    with patch.object(llm, "_call_groq", return_value='["Python", "Docker", "AWS"]'):
        skills = llm.extract_skills_llm("some jd text", _settings())
    assert skills == ["Python", "Docker", "AWS"]


def test_infer_role_profile_parses_object():
    raw = (
        '{"role": "Data Scientist", "skills": ["Python", " Pandas ", "", "NumPy", '
        '"SQL", "Statistics", "Scikit-learn", "Matplotlib", "Jupyter"]}'
    )
    with patch.object(llm, "_call_groq", return_value=raw):
        role, skills = llm.infer_role_profile("data scientist", _settings())
    assert role == "Data Scientist"
    # Whitespace is stripped and empty entries dropped.
    assert skills[:2] == ["Python", "Pandas"]
    assert "" not in skills


def test_infer_role_profile_null_role_means_no_profile():
    with patch.object(llm, "_call_groq", return_value='{"role": null, "skills": ["x"]}'):
        assert llm.infer_role_profile("hello", _settings()) == (None, [])


def test_infer_role_profile_retries_then_falls_back_on_garbage():
    with (
        patch.object(llm, "_call_groq", return_value="not json") as groq,
        patch.object(llm, "_call_gemini", side_effect=RuntimeError("down")),
    ):
        assert llm.infer_role_profile("ai engineer", _settings()) == (None, [])
    assert groq.call_count == 2


def test_infer_role_profile_rejects_tiny_skill_list_then_accepts_full_one():
    tiny = '{"role": "Flutter Developer", "skills": ["Flutter"]}'
    full = (
        '{"role": "Flutter Developer", "skills": ["Flutter", "Dart", "Firebase", '
        '"Provider", "Riverpod", "Bloc", "Git", "REST APIs"]}'
    )
    with patch.object(llm, "_call_groq", side_effect=[tiny, full]) as groq:
        role, skills = llm.infer_role_profile("I want to be a Flutter developer", _settings())
    assert role == "Flutter Developer"
    assert len(skills) == 8
    assert groq.call_count == 2
    assert "at least 8 skills" in groq.call_args_list[1].args[0]
