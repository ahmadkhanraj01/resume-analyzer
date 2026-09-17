from unittest.mock import patch

from app.core.config import Settings
from app.services import skills


def _settings() -> Settings:
    return Settings(jwt_secret="test-secret-do-not-use-in-prod-at-least-32-bytes")


JD = """We need a Senior Backend Engineer with strong Python and FastAPI
experience. Must know PostgreSQL and Docker. Kubernetes and AWS a plus.
Python experience is required, at least 5 years of Python."""


def test_seed_matches_are_case_insensitive_and_word_bounded():
    matches = skills._seed_matches("I know python and Docker but not dockerfile-ish things")
    assert "Python" in matches
    assert "Docker" in matches


def test_seed_matches_do_not_match_substrings():
    # "C" as a seed should not match inside "Doctor" or "Vaccine"; word
    # boundaries with the +#. exception list must not be too permissive.
    matches = skills._seed_matches("The doctor gave a vaccine")
    assert "C" not in matches


def test_count_mentions_counts_repeats():
    assert skills._count_mentions(JD, "Python") == 3


def test_extract_skills_unions_seed_and_llm_without_llm_call(monkeypatch):
    with patch.object(skills, "extract_skills_llm", return_value=["Go", "Python"]):
        found, mentions = skills.extract_skills(JD, _settings())
    assert "Python" in found
    assert "Go" in found  # only from the LLM pass
    # deduped case-insensitively: Python only appears once even though both
    # the seed pass and the LLM pass surfaced it
    assert found.count("Python") == 1
    assert mentions["Python"] == 3


def test_extract_skills_llm_disabled_uses_seed_only():
    with patch.object(skills, "extract_skills_llm") as mock_llm:
        found, _ = skills.extract_skills(JD, _settings(), use_llm=False)
    mock_llm.assert_not_called()
    assert "Python" in found


def test_extract_skills_caps_at_max():
    long_jd = " ".join(skills._load_seeds())  # every seed appears at least once
    found, _ = skills.extract_skills(long_jd, _settings(), use_llm=False)
    assert len(found) <= skills.MAX_SKILLS


def test_single_letter_seed_ignores_initialisms():
    assert "R" not in skills._seed_matches("Join our R&D team building tools in Go.")
    assert "R" in skills._seed_matches("Statistical analysis in R and Python.")
    assert "C" in skills._seed_matches("Firmware written in C, C++ and Rust.")


def test_llm_skill_pass_is_cached_per_jd():
    skills._llm_skills_cache.clear()
    with patch.object(skills, "extract_skills_llm", return_value=["Go"]) as mock_llm:
        skills.extract_skills(JD, _settings())
        skills.extract_skills(JD, _settings())
        assert mock_llm.call_count == 1
        skills.extract_skills(JD + " and Rust.", _settings())
        assert mock_llm.call_count == 2
    skills._llm_skills_cache.clear()


def test_llm_skill_pass_does_not_cache_empty_results():
    skills._llm_skills_cache.clear()
    with patch.object(skills, "extract_skills_llm", return_value=[]) as mock_llm:
        skills.extract_skills(JD, _settings())
        skills.extract_skills(JD, _settings())
        assert mock_llm.call_count == 2
