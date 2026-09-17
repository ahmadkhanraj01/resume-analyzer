"""Ranks a resume against the curated role profiles in data/role_profiles.json.

Deterministic and LLM-free: the profiles were generated once, reviewed by
hand, and checked in, so the same resume always gets the same ranking and
a request costs one resume embedding plus cached skill embeddings. Regenerate
or edit the JSON to change what the app considers a typical posting.
"""

import json
from functools import lru_cache
from pathlib import Path

from app.schemas.career import CareerFit
from app.services import scoring

PROFILES_PATH = Path(__file__).parent.parent / "data" / "role_profiles.json"


@lru_cache(maxsize=1)
def _load() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    data = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
    profiles = {p["role"]: list(p["skills"]) for p in data["profiles"]}
    aliases = {k: list(v) for k, v in data.get("aliases", {}).items()}
    return profiles, aliases


def profile_count() -> int:
    return len(_load()[0])


def rank_careers(
    resume_text: str,
    covered_threshold: float = scoring.COVERED_THRESHOLD,
    partial_threshold: float = scoring.PARTIAL_THRESHOLD,
    limit: int | None = None,
) -> list[CareerFit]:
    """Every profile scored and sorted best first. Ties break on role name
    so the order is stable across runs."""
    profiles, aliases = _load()
    results = scoring.score_profiles(
        resume_text, profiles, covered_threshold, partial_threshold, aliases
    )
    fits = [
        CareerFit(
            role=role,
            match_score=result.match_score,
            covered_skills=[s.skill for s in result.skills if s.severity.value == "minor"],
            missing_skills=[s.skill for s in result.skills if s.severity.value != "minor"],
        )
        for role, result in results.items()
    ]
    fits.sort(key=lambda f: (-f.match_score, f.role))
    return fits[:limit] if limit else fits
