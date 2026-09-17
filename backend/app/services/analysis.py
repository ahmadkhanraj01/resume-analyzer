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
import re
import time
from dataclasses import dataclass

from app.core.config import Settings
from app.core.exceptions import NoSkillsFoundError
from app.schemas.report import InterviewReport, ScoredAgainst, SkillGap
from app.services import careers, extract, llm, scoring, skills

logger = logging.getLogger(__name__)

# Matches the max_length on InterviewReport.skill_gaps; scoring can produce
# up to skills.MAX_SKILLS entries, so the worst ones are kept.
MAX_SKILL_GAPS = 12

# Longer than this and the text is treated as a posting even if it names a
# curated role; a real JD always mentions its own title.
ROLE_TEXT_MAX_CHARS = 200


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
    scored_against: ScoredAgainst = ScoredAgainst.job_description
    role_title: str | None = None


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

    scored_against = ScoredAgainst.job_description
    role_title = None
    # A short text naming a curated role is a target, not a posting, even
    # when it contains a skill word: "I want to be a Flutter Developer"
    # would otherwise be scored against the single JD skill "Flutter" and
    # come out at 100%. The curated profile is also the rubric the
    # career-fit panel used, so the report's score matches the panel's,
    # and it costs no LLM call.
    curated = (
        careers.find_profile(job_description)
        if len(job_description) <= ROLE_TEXT_MAX_CHARS
        else None
    )
    if curated:
        role_title, skill_list = curated
    else:
        skill_list, mentions = skills.extract_skills(job_description, settings)
    if not skill_list and not curated:
        # Nothing to score against. Usually the user typed a target role
        # the curated set does not cover, so ask the model for a typical
        # profile before giving up. Scoring a resume against an empty list
        # would report 0% and mean nothing.
        role_title, skill_list = llm.infer_role_profile(job_description, settings)
        if not skill_list:
            raise NoSkillsFoundError()
    if role_title:
        scored_against = ScoredAgainst.role_profile
        mentions = dict.fromkeys(skill_list, 1)
        job_description = _role_profile_description(role_title, skill_list, job_description)
    t2 = time.perf_counter()
    scoring_result = scoring.score(
        resume_text,
        skill_list,
        mentions,
        covered_threshold=settings.covered_threshold,
        partial_threshold=settings.partial_threshold,
        aliases=careers.aliases(),
    )
    t3 = time.perf_counter()

    covered = [s.skill for s in scoring_result.skills if s.severity.value == "minor"]
    missing = [s.skill for s in scoring_result.skills if s.severity.value != "minor"]
    # Umbrella names from the curated profiles ("Containers", "Cloud") mean
    # little to the model on their own, so the prompt shows what each one
    # stands for. The model tends to answer under those concrete names,
    # which _advice_lookup maps back.
    aliases = careers.aliases()
    missing_for_prompt = [_with_aliases(skill, aliases) for skill in missing]

    report = llm.generate_report(
        resume_text=resume_text,
        job_description=job_description,
        self_description=self_description,
        covered_skills=covered,
        missing_skills=missing_for_prompt,
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
    # contributes the advice text, matched by name or alias; a skill it
    # renamed beyond recognition or invented has no scoring numbers behind
    # it and is dropped rather than shipped with the model's own severity
    # and similarity.
    advice_by_skill = _advice_lookup(report.skill_gaps, missing, aliases)
    weak = sorted(
        (s for s in scoring_result.skills if s.severity.value != "minor"),
        key=lambda s: (s.severity.value != "critical", s.similarity),
    )
    gaps = [
        SkillGap(
            skill=s.skill,
            severity=s.severity,
            similarity=s.similarity,
            advice=advice_by_skill.get(s.skill, _default_advice(s.skill)),
        )
        for s in weak[:MAX_SKILL_GAPS]
    ]
    # match_score is set here as well as in llm.generate_report so the rule
    # holds even if that wrapper is bypassed or replaced.
    report = report.model_copy(
        update={"skill_gaps": gaps, "match_score": scoring_result.match_score}
    )

    return AnalysisResult(
        resume_text=resume_text,
        report=report,
        scored_against=scored_against,
        role_title=role_title,
    )


def _with_aliases(skill: str, aliases: dict[str, list[str]]) -> str:
    """ "Containers (Docker, Kubernetes, K8s)" for the prompt; the bare name
    when the skill has no aliases."""
    alts = aliases.get(skill)
    return f"{skill} ({', '.join(alts)})" if alts else skill


def _normalize_name(name: str) -> str:
    # Lowercase, parenthetical dropped: the model often echoes the prompt's
    # "Containers (Docker, Kubernetes)" form or writes just "Docker".
    return re.sub(r"\s*\(.*\)\s*$", "", name).strip().lower()


def _advice_lookup(
    model_gaps: list[SkillGap], skills: list[str], aliases: dict[str, list[str]]
) -> dict[str, str]:
    """Maps each scored skill to the model's advice for it, accepting the
    skill's own name, any alias, or either with a trailing parenthetical.
    First match wins so a skill the model wrote about twice keeps the
    first, and an alias shared by two skills goes to the first in scoring
    order."""
    name_to_skill: dict[str, str] = {}
    for skill in skills:
        for name in [skill, *aliases.get(skill, [])]:
            name_to_skill.setdefault(_normalize_name(name), skill)
    advice: dict[str, str] = {}
    for gap in model_gaps:
        skill = name_to_skill.get(_normalize_name(gap.skill))
        if skill is not None and skill not in advice:
            advice[skill] = gap.advice
    return advice


def _role_profile_description(role: str, skill_list: list[str], original: str) -> str:
    """Stands in for the job description in the report prompt when the user
    gave a role rather than a posting, so the question writer has the same
    kind of context it would get from a real listing."""
    return (
        f"Target role: {role}\n\n"
        f"Typical requirements for this role: {', '.join(skill_list)}\n\n"
        f"The candidate wrote: {original.strip()}"
    )
