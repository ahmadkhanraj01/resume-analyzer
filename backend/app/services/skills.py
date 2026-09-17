"""JD -> skill list, regex + LLM union.

Kept separate from scoring.py because this is the one place the LLM touches
the scoring path, and only to name skills, never to grade them. Isolating it
here keeps scoring.py deterministic and unit-testable with no mocks.
"""

import hashlib
import re
from functools import lru_cache
from pathlib import Path

from app.core.config import Settings
from app.services.llm import extract_skills_llm

SEED_PATH = Path(__file__).parent.parent / "data" / "skill_seeds.txt"
MAX_SKILLS = 25


@lru_cache(maxsize=1)
def _load_seeds() -> list[str]:
    return [
        line.strip() for line in SEED_PATH.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


# Word-boundary lookaround that also tolerates the punctuation inside skill
# names like "C++", "C#", and "Next.js": a plain \b would split those on the
# symbol. The lookahead blocks a following word char or +/# outright (so
# "Python" doesn't match inside "Pythonic"), but only blocks a following
# period when a word char comes right after it ("Node.js"), so a skill at
# the end of a sentence ("...built in Python.") still counts.
# Single-character seeds ("C", "R") get a stricter boundary that also
# rejects an adjacent "&", so "R&D" is not read as the R language.
_BEFORE = r"(?<![\w+#.])"
_AFTER = r"(?![\w+#]|\.\w)"
_BEFORE_SINGLE = r"(?<![\w+#.&])"
_AFTER_SINGLE = r"(?![\w+#&]|\.\w)"


def _pattern(skill: str) -> str:
    if len(skill) == 1:
        return _BEFORE_SINGLE + re.escape(skill) + _AFTER_SINGLE
    return _BEFORE + re.escape(skill) + _AFTER


def _seed_matches(job_description: str) -> list[str]:
    """Regex, word-boundary, case-insensitive match against the seed list.
    Cheap, high precision, catches the obvious."""
    matches = []
    for seed in _load_seeds():
        if re.search(_pattern(seed), job_description, re.IGNORECASE):
            matches.append(seed)
    return matches


def _count_mentions(job_description: str, skill: str) -> int:
    return len(re.findall(_pattern(skill), job_description, re.IGNORECASE))


# The same JD is often analyzed more than once (a second resume, a retry
# after LLM_UNAVAILABLE). Keying the LLM pass on the JD's hash saves one of
# the two provider round trips per analysis in that case. Bounded so it
# cannot grow without limit on a 512 MB instance; an empty result is not
# cached because it usually means the provider was down, not that the JD
# has no skills.
_LLM_SKILLS_CACHE_MAX = 256
_llm_skills_cache: dict[str, list[str]] = {}


def _llm_skills_cached(job_description: str, settings: Settings) -> list[str]:
    key = hashlib.sha256(job_description.encode("utf-8")).hexdigest()
    cached = _llm_skills_cache.get(key)
    if cached is not None:
        return list(cached)
    result = extract_skills_llm(job_description, settings)
    if result:
        if len(_llm_skills_cache) >= _LLM_SKILLS_CACHE_MAX:
            _llm_skills_cache.pop(next(iter(_llm_skills_cache)))
        _llm_skills_cache[key] = list(result)
    return result


def extract_skills(
    job_description: str, settings: Settings, use_llm: bool = True
) -> tuple[list[str], dict[str, int]]:
    """Union of the regex seed pass and the LLM pass, deduplicated
    case-insensitively, capped at MAX_SKILLS. Returns the skill list and a
    mention-count map used to weight the aggregate score.

    A hardcoded list alone cannot keep up with tooling, and every miss is
    invisible to the user; the LLM pass adds recall the seed list will
    always lack.
    """
    seed_skills = _seed_matches(job_description)
    llm_skills = _llm_skills_cached(job_description, settings) if use_llm else []

    seen: dict[str, str] = {}  # lowercase -> original casing, first occurrence wins
    for skill in seed_skills + llm_skills:
        key = skill.strip().lower()
        if key and key not in seen:
            seen[key] = skill.strip()

    skills = list(seen.values())[:MAX_SKILLS]
    mentions = {skill: max(1, _count_mentions(job_description, skill)) for skill in skills}
    return skills, mentions
