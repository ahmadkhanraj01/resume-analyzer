"""Orchestrates one analysis run: extract -> skill extraction -> scoring ->
LLM report generation.

Not in STRUCTURE.md's original file list. Added because api/interview.py's
create endpoint otherwise composes four services inline, which pushes the
router body past the ~20 line threshold CLAUDE.md sets for "this belongs in
a service." Framework-free like every other module in this package, so it
stays runnable from a plain script and callable through run_in_threadpool
as one blocking unit.
"""

from dataclasses import dataclass

from app.core.config import Settings
from app.schemas.report import InterviewReport
from app.services import extract, llm, scoring, skills


@dataclass
class AnalysisResult:
    resume_text: str
    report: InterviewReport


def run_analysis(
    resume_bytes: bytes,
    job_description: str,
    self_description: str,
    settings: Settings,
) -> AnalysisResult:
    resume_text = extract.to_text(resume_bytes)

    skill_list, mentions = skills.extract_skills(job_description, settings)
    scoring_result = scoring.score(
        resume_text,
        skill_list,
        mentions,
        covered_threshold=settings.covered_threshold,
        partial_threshold=settings.partial_threshold,
    )

    covered = [s.skill for s in scoring_result.skills if s.severity.value == "minor"]
    missing = [s.skill for s in scoring_result.skills if s.severity.value != "minor"]

    report = llm.generate_report(
        resume_text=resume_text,
        job_description=job_description,
        self_description=self_description,
        covered_skills=covered,
        missing_skills=missing,
        match_score=scoring_result.match_score,
        settings=settings,
    )

    # The LLM's skill_gaps are prose (advice text); the severity and
    # similarity for each must still come from scoring, not the model. Merge
    # scoring's numbers onto whatever skills the LLM chose to write about.
    similarity_by_skill = {s.skill.lower(): s for s in scoring_result.skills}
    for gap in report.skill_gaps:
        match = similarity_by_skill.get(gap.skill.lower())
        if match:
            gap.severity = match.severity
            gap.similarity = match.similarity

    return AnalysisResult(resume_text=resume_text, report=report)
