"""Orchestrates one analysis run: extract -> skill extraction -> scoring ->
LLM report generation.

Not in STRUCTURE.md's original file list. Added because api/interview.py's
create endpoint otherwise composes four services inline, which pushes the
router body past the ~20 line threshold CLAUDE.md sets for "this belongs in
a service." Framework-free like every other module in this package, so it
stays runnable from a plain script and callable through run_in_threadpool
as one blocking unit.
"""

import logging
import time
from dataclasses import dataclass

from app.core.config import Settings
from app.schemas.report import InterviewReport, SkillGap
from app.services import extract, llm, scoring, skills

logger = logging.getLogger(__name__)

# Matches the max_length on InterviewReport.skill_gaps; scoring can produce
# up to skills.MAX_SKILLS entries, so the worst ones are kept.
MAX_SKILL_GAPS = 12


def _default_advice(skill: str) -> str:
    # Used when the model wrote about a skill under a different name or not
    # at all. Blank advice reads as a rendering bug, so say something true.
    return (
        f"{skill} is asked for in the job description but not evident on your resume. "
        "Review the fundamentals and be ready to speak to any related experience."
    )


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
    # Per-stage timings are the only way to tell a slow Groq call from a
    # Gemini fallback or a cold embedding-model load after the fact.
    t0 = time.perf_counter()
    resume_text = extract.to_text(resume_bytes)
    t1 = time.perf_counter()

    skill_list, mentions = skills.extract_skills(job_description, settings)
    t2 = time.perf_counter()
    scoring_result = scoring.score(
        resume_text,
        skill_list,
        mentions,
        covered_threshold=settings.covered_threshold,
        partial_threshold=settings.partial_threshold,
    )
    t3 = time.perf_counter()

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
    t4 = time.perf_counter()
    logger.info(
        "analysis stages: extract=%.2fs skills=%.2fs score=%.2fs llm=%.2fs total=%.2fs",
        t1 - t0,
        t2 - t1,
        t3 - t2,
        t4 - t3,
        t4 - t0,
    )

    # Skill gaps are built from scoring, never from the model. The LLM only
    # contributes the advice text, matched by name; a skill it renamed or
    # invented has no scoring numbers behind it and is dropped rather than
    # shipped with the model's own severity and similarity.
    advice_by_skill = {g.skill.strip().lower(): g.advice for g in report.skill_gaps}
    weak = sorted(
        (s for s in scoring_result.skills if s.severity.value != "minor"),
        key=lambda s: (s.severity.value != "critical", s.similarity),
    )
    gaps = [
        SkillGap(
            skill=s.skill,
            severity=s.severity,
            similarity=s.similarity,
            advice=advice_by_skill.get(s.skill.lower(), _default_advice(s.skill)),
        )
        for s in weak[:MAX_SKILL_GAPS]
    ]
    report = report.model_copy(update={"skill_gaps": gaps})

    return AnalysisResult(resume_text=resume_text, report=report)
