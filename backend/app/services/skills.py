"""JD -> skill list, regex + LLM union.

Kept separate from scoring.py because this is the one place the LLM touches
the scoring path, and only to name skills, never to grade them. Isolating it
here keeps scoring.py deterministic and unit-testable with no mocks.
"""

import hashlib
import re
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from app.core.config import Settings
from app.services import llm
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


class SkillListStore(Protocol):
    """Where LLM-named skill lists are kept once named. The app passes a
    Postgres-backed store (app/db/skill_lists.py); anything else gets the
    in-memory one below."""

    def get(self, key: str) -> tuple[str | None, list[str]] | None: ...

    def put(self, key: str, role: str | None, skills: list[str]) -> None: ...


class MemorySkillListStore:
    """Per-process fallback for tests and scripts. Bounded so it cannot grow
    without limit on a 512 MB instance; lost on restart, which is why the
    app does not rely on it."""

    def __init__(self, max_items: int = 256):
        self._items: dict[str, tuple[str | None, list[str]]] = {}
        self._max = max_items

    def get(self, key: str) -> tuple[str | None, list[str]] | None:
        item = self._items.get(key)
        return (item[0], list(item[1])) if item else None

    def put(self, key: str, role: str | None, skills: list[str]) -> None:
        if key in self._items:
            return
        if len(self._items) >= self._max:
            self._items.pop(next(iter(self._items)))
        self._items[key] = (role, list(skills))

    def clear(self) -> None:
        self._items.clear()


_memory_store = MemorySkillListStore()


def _key(kind: str, text: str) -> str:
    # Whitespace and case are folded so a re-paste with a trailing newline,
    # or "Supply Chain Analyst" typed after "supply chain analyst", is the
    # same input. Only the lookup key is folded; extraction still sees the
    # original text.
    norm = re.sub(r"\s+", " ", text).strip().lower()
    return f"{kind}:" + hashlib.sha256(norm.encode("utf-8")).hexdigest()


def _llm_skills_cached(
    job_description: str, settings: Settings, store: SkillListStore
) -> list[str]:
    """The LLM pass is the only non-deterministic input to scoring, so its
    first answer for a job description is kept and reused: the same posting
    must always produce the same score. A real empty answer is stored too:
    it is what sends a bare role sentence to the role-profile path, and a
    later non-empty answer for the same text would send it down the other
    path with a different score. A provider outage (None) is not stored."""
    key = _key("jd", job_description)
    cached = store.get(key)
    if cached is not None:
        return cached[1]
    result = extract_skills_llm(job_description, settings)
    if result is None:
        return []
    store.put(key, None, result)
    return result


def role_profile(
    text: str, settings: Settings, store: SkillListStore | None = None
) -> tuple[str | None, list[str]]:
    """llm.infer_role_profile, kept the same way as the JD pass so a typed
    role outside the curated set gets the same profile, and score, every
    time. Only a recognised role is stored; (None, []) can mean every
    provider failed."""
    store = store or _memory_store
    key = _key("role", text)
    cached = store.get(key)
    if cached is not None:
        return cached
    role, skills = llm.infer_role_profile(text, settings)
    if role and skills:
        store.put(key, role, skills)
    return role, skills


def extract_skills(
    job_description: str,
    settings: Settings,
    use_llm: bool = True,
    store: SkillListStore | None = None,
) -> tuple[list[str], dict[str, int]]:
    """Union of the regex seed pass and the LLM pass, deduplicated
    case-insensitively, capped at MAX_SKILLS. Returns the skill list and a
    mention-count map used to weight the aggregate score.

    A hardcoded list alone cannot keep up with tooling, and every miss is
    invisible to the user; the LLM pass adds recall the seed list will
    always lack.
    """
    seed_skills = _seed_matches(job_description)
    store = store or _memory_store
    llm_skills = _llm_skills_cached(job_description, settings, store) if use_llm else []

    seen: dict[str, str] = {}  # lowercase -> original casing, first occurrence wins
    for skill in seed_skills + llm_skills:
        key = skill.strip().lower()
        if key and key not in seen:
            seen[key] = skill.strip()

    skills = list(seen.values())[:MAX_SKILLS]
    mentions = {skill: max(1, _count_mentions(job_description, skill)) for skill in skills}
    return skills, mentions
