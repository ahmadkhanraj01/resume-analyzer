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
    # Seven of ten skills are literal mentions (full credit), Kafka and
    # GraphQL sit below the partial threshold (zero), Rust is far below.
    result = scoring.score(RESUME_TEXT, SKILLS, skill_mentions={"Python": 3, "FastAPI": 2})
    assert result.match_score == 74


def test_resume_with_none_of_the_skills_scores_near_zero():
    # The original formula (similarity / covered_threshold) gave unrelated
    # text a floor around 65%. A resume that names none of the skills must
    # not read as a mostly good match.
    # GraphQL is left out: on this resume it lands at 0.6216, right on the
    # noise ceiling that set PARTIAL_THRESHOLD, and would flip the severity
    # assertion on a model update without meaning anything changed.
    result = scoring.score(RESUME_TEXT, ["Rust", "Kafka", "Haskell", "Unity"])
    assert result.match_score < 10
    assert all(s.severity == Severity.critical for s in result.skills)


def test_coverage_credit_is_anchored_at_partial_threshold():
    assert scoring._coverage(0.50, 0.75, 0.62) == 0.0
    assert scoring._coverage(0.62, 0.75, 0.62) == 0.0
    assert abs(scoring._coverage(0.685, 0.75, 0.62) - 0.5) < 1e-9
    assert scoring._coverage(0.75, 0.75, 0.62) == 1.0
    assert scoring._coverage(0.90, 0.75, 0.62) == 1.0


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


def test_literal_mention_tries_parenthesised_alternatives():
    text = "Implemented state management with GetX, Provider and Riverpod. Used Git daily."
    assert scoring._literal_mention("State Management (Provider, Bloc, Riverpod)", text)
    assert scoring._literal_mention("Version Control (Git)", text)
    assert scoring._literal_mention("Third-party Packages (e.g., http, dio)", text) is False
    assert scoring._literal_mention("Testing (unit, widget, integration)", text) is False


def test_short_acronyms_match_case_sensitively():
    assert scoring._literal_mention("SOC", "Worked on a Zynq-7000 SoC platform") is False
    assert scoring._literal_mention("SOC", "Monitored alerts in the SOC") is True
    # Longer names and mixed-case names stay case-insensitive.
    assert scoring._literal_mention("Python", "built in python and PYTHON") is True
    assert scoring._literal_mention("MATLAB", "used matlab") is True
