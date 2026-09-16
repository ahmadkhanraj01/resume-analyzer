"""Deterministic: the same inputs always produce the same score, so exact
values are asserted rather than ranges. Uses the real fastembed model; the
first run in a fresh environment downloads it (see README for the size).
"""

from pathlib import Path

from app.schemas.report import Severity
from app.services import extract, scoring

FIXTURES = Path(__file__).parent / "fixtures"

RESUME_TEXT = extract.to_text((FIXTURES / "resume_sample.pdf").read_bytes())

SKILLS = [
    "Python",
    "FastAPI",
    "PostgreSQL",
    "Docker",
    "Kubernetes",
    "AWS",
    "Redis",
    "Kafka",
    "GraphQL",
    "Rust",
]


def test_score_is_deterministic_across_runs():
    first = scoring.score(RESUME_TEXT, SKILLS)
    second = scoring.score(RESUME_TEXT, SKILLS)
    assert first.match_score == second.match_score
    assert [s.similarity for s in first.skills] == [s.similarity for s in second.skills]


def test_literal_skill_mentions_are_covered():
    # A skill explicitly named in the resume ("Docker" appears verbatim)
    # must never come out as missing. This is the exact failure PHASES.md's
    # Phase 4 checkpoint calls out: "if Docker is marked missing on a resume
    # that says Docker, fix the chunking before continuing."
    result = scoring.score(RESUME_TEXT, ["Docker", "Python", "PostgreSQL"])
    by_skill = {s.skill: s for s in result.skills}
    assert by_skill["Docker"].severity == Severity.minor
    assert by_skill["Python"].severity == Severity.minor
    assert by_skill["PostgreSQL"].severity == Severity.minor


def test_absent_unrelated_skill_is_critical():
    result = scoring.score(RESUME_TEXT, ["Rust"])
    assert result.skills[0].severity == Severity.critical
    assert result.skills[0].similarity < scoring.PARTIAL_THRESHOLD


def test_aggregate_match_score_exact_value():
    result = scoring.score(RESUME_TEXT, SKILLS, skill_mentions={"Python": 3, "FastAPI": 2})
    assert result.match_score == 94


def test_weighting_gives_more_weight_to_repeated_skills():
    unweighted = scoring.score(RESUME_TEXT, ["Rust", "Python"])
    weighted = scoring.score(RESUME_TEXT, ["Rust", "Python"], skill_mentions={"Python": 3})
    # Python is covered and Rust is not; weighting Python higher should pull
    # the aggregate up.
    assert weighted.match_score > unweighted.match_score


def test_empty_skill_list_scores_zero():
    result = scoring.score(RESUME_TEXT, [])
    assert result.match_score == 0
    assert result.skills == []


def test_empty_resume_scores_zero():
    result = scoring.score("", ["Python"])
    assert result.match_score == 0
    assert result.skills == []


def test_chunk_text_respects_size_and_overlap():
    words = " ".join(f"word{i}" for i in range(500))
    chunks = scoring.chunk_text(words, size=200, overlap=50)
    assert len(chunks) == 3
    assert all(len(c.split()) == 200 for c in chunks)
    # The tail of chunk 1 and the head of chunk 2 share the 50-word overlap.
    first_tail = chunks[0].split()[-50:]
    second_head = chunks[1].split()[:50]
    assert first_tail == second_head


def test_chunk_text_empty_input():
    assert scoring.chunk_text("") == []


def test_cosine_similarity_identical_vectors_is_one():
    import numpy as np

    v = np.array([1.0, 2.0, 3.0])
    assert abs(scoring.cosine_similarity(v, v) - 1.0) < 1e-9


def test_cosine_similarity_zero_vector_is_zero():
    import numpy as np

    v = np.array([0.0, 0.0, 0.0])
    w = np.array([1.0, 2.0, 3.0])
    assert scoring.cosine_similarity(v, w) == 0.0
