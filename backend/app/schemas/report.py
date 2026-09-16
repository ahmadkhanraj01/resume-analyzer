"""The report contract. THE single source of truth: the LLM prompt embeds
this schema, the response is validated against it, the DB columns mirror it,
and the frontend types match it.

Changing this file means changing the DB columns (app/db/models.py), the
prompt (app/services/prompts.py), the frontend types, and a migration, all in
the same commit. See CLAUDE.md.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    critical = "critical"
    moderate = "moderate"
    minor = "minor"


class SkillGap(BaseModel):
    skill: str
    severity: Severity
    similarity: float = Field(ge=0, le=1)  # from scoring, not the LLM
    advice: str = Field(max_length=300)


class Question(BaseModel):
    question: str
    intention: str  # what the interviewer is probing
    answer: str  # a model answer to study


class PrepDay(BaseModel):
    day: int = Field(ge=1, le=14)
    focus: str
    tasks: list[str] = Field(min_length=1, max_length=5)


class InterviewReport(BaseModel):
    """What the LLM must produce. match_score is accepted so the model has a
    field to fill, but the value is always overwritten by scoring.py."""

    title: str
    match_score: int = Field(ge=0, le=100)  # overwritten by scoring
    skill_gaps: list[SkillGap] = Field(max_length=12)
    technical_qs: list[Question] = Field(max_length=10)
    behavioral_qs: list[Question] = Field(max_length=6)
    preparation_plan: list[PrepDay] = Field(max_length=14)


class ReportOut(InterviewReport):
    """What the API returns for a single report."""

    id: str
    created_at: datetime


class ReportSummaryOut(BaseModel):
    """Trimmed shape for the history list. A history page does not need the
    full report per row."""

    id: str
    title: str
    match_score: int
    created_at: datetime
