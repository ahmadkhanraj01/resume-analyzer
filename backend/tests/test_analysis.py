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


JD = """Senior Backend Engineer. Must know Python, FastAPI, PostgreSQL, Docker,
Kafka and Kubernetes. Terraform and Rust experience is a strong plus."""


def _run(report: InterviewReport) -> InterviewReport:
    resume = (FIXTURES / "resume_sample.pdf").read_bytes()
    with (
        patch.object(skills, "extract_skills_llm", return_value=[]),
        patch.object(llm, "generate_report", return_value=report),
    ):
        return analysis.run_analysis(resume, JD, "", _settings()).report


def test_invented_skill_from_llm_is_dropped():
    report = _run(
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
    report = _run(
        _fake_report(
            [{"skill": "Postgres", "severity": "critical", "similarity": 0.05, "advice": "x"}]
        )
    )
    for gap in report.skill_gaps:
        assert gap.skill.lower() != "postgres"
        assert not (gap.similarity == 0.05 and gap.severity.value == "critical")


def test_gap_advice_is_taken_from_llm_by_name():
    report = _run(
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
    report = _run(_fake_report([]))
    assert all(g.severity.value != "minor" for g in report.skill_gaps)
    assert len(report.skill_gaps) <= analysis.MAX_SKILL_GAPS
