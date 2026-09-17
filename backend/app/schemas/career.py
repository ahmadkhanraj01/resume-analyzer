"""Career-fit contract: the resume scored against every curated role
profile, no LLM involved. Mirrored by the frontend CareerFit component."""

from pydantic import BaseModel


class CareerFit(BaseModel):
    role: str
    match_score: int
    covered_skills: list[str]
    missing_skills: list[str]


class CareerFitOut(BaseModel):
    fits: list[CareerFit]
    profile_count: int
