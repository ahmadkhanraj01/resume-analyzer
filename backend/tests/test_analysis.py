"""run_analysis composes real extraction and scoring with a mocked LLM.
These tests pin the rule that the LLM never grades: skill gap numbers come
from scoring even when the model renames or invents a skill."""

from pathlib import Path
from unittest.mock import patch

from app.core.config import Settings
from app.schemas.report import InterviewReport
from app.services import analysis, llm, skills

FIXTURES = Path(__file__).parent / "fixtures"


def _settings() -> Settings:
    return Settings(jwt_secret="test-secret-do-not-use-in-prod-at-least-32-bytes")


def _fake_report(gaps: list[dict]) -> InterviewReport:
    return InterviewReport(
        title="t",
        match_score=99,
        skill_gaps=gaps,
        technical_qs=[],
        behavioral_qs=[],
        preparation_plan=[],
    )


def _run_report(report: InterviewReport) -> InterviewReport:
    return _run(report).report


JD = """Senior Backend Engineer. Must know Python, FastAPI, PostgreSQL, Docker,
Kafka and Kubernetes. Terraform and Rust experience is a strong plus."""


def _run(report: InterviewReport, jd: str = JD, role=(None, [])) -> analysis.AnalysisResult:
    resume = (FIXTURES / "resume_sample.pdf").read_bytes()
    with (
        patch.object(skills, "extract_skills_llm", return_value=[]),
        patch.object(llm, "infer_role_profile", return_value=role),
        patch.object(llm, "generate_report", return_value=report) as gen,
    ):
        result = analysis.run_analysis(resume, jd, "", _settings())
        result.prompt_jd = gen.call_args.kwargs["job_description"]
        return result


def test_invented_skill_from_llm_is_dropped():
    report = _run_report(
        _fake_report(
            [
                {
                    "skill": "Quantum Computing",
                    "severity": "critical",
                    "similarity": 0.01,
                    "advice": "made up",
                }
            ]
        )
    )
    assert all(g.skill != "Quantum Computing" for g in report.skill_gaps)


def test_renamed_skill_keeps_scoring_numbers_not_llm_numbers():
    # The model wrote about "Postgres"; scoring knows "PostgreSQL". The gap
    # list must not carry the model's severity or similarity under either name.
    report = _run_report(
        _fake_report(
            [{"skill": "Postgres", "severity": "critical", "similarity": 0.05, "advice": "x"}]
        )
    )
    for gap in report.skill_gaps:
        assert gap.skill.lower() != "postgres"
        assert not (gap.similarity == 0.05 and gap.severity.value == "critical")


def test_gap_advice_is_taken_from_llm_by_name():
    report = _run_report(
        _fake_report(
            [{"skill": "kafka", "severity": "minor", "similarity": 0.99, "advice": "Study Kafka."}]
        )
    )
    kafka = next(g for g in report.skill_gaps if g.skill.lower() == "kafka")
    assert kafka.advice == "Study Kafka."
    # The model claimed minor/0.99; scoring says otherwise for a resume with no Kafka.
    assert kafka.severity.value != "minor"
    assert kafka.similarity < 0.99


def test_gaps_only_contain_non_minor_skills_and_are_capped():
    report = _run_report(_fake_report([]))
    assert all(g.severity.value != "minor" for g in report.skill_gaps)
    assert len(report.skill_gaps) <= analysis.MAX_SKILL_GAPS


def test_role_profile_fallback_when_jd_names_no_skills():
    result = _run(
        _fake_report([]),
        jd="I want to become an AI engineer.",
        role=("AI Engineer", ["Python", "PyTorch", "Kafka"]),
    )
    assert result.scored_against.value == "role_profile"
    assert result.role_title == "AI Engineer"
    assert result.report.match_score > 0
    # The question writer sees the synthesized role description, not the bare sentence.
    assert "Target role: AI Engineer" in result.prompt_jd
    assert "PyTorch" in result.prompt_jd


def test_no_skills_and_no_role_raises():
    import pytest

    from app.core.exceptions import NoSkillsFoundError

    resume = (FIXTURES / "resume_sample.pdf").read_bytes()
    with (
        patch.object(skills, "extract_skills_llm", return_value=[]),
        patch.object(llm, "infer_role_profile", return_value=(None, [])),
        patch.object(llm, "generate_report") as gen,
        pytest.raises(NoSkillsFoundError),
    ):
        analysis.run_analysis(resume, "give me a job", "", _settings())
    # No report call is spent on unusable input.
    gen.assert_not_called()
