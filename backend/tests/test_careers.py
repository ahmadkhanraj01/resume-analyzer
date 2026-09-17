"""Career ranking is deterministic and LLM-free, so exact assertions hold."""

import json
from pathlib import Path

from app.services import careers, extract, scoring

FIXTURES = Path(__file__).parent / "fixtures"
RESUME_TEXT = extract.to_text((FIXTURES / "resume_sample.pdf").read_bytes())


def test_profiles_file_is_well_formed():
    data = json.loads(careers.PROFILES_PATH.read_text(encoding="utf-8"))
    roles = [p["role"] for p in data["profiles"]]
    assert len(roles) == len(set(roles))
    for profile in data["profiles"]:
        assert 12 <= len(profile["skills"]) <= 16, profile["role"]
        assert len(set(profile["skills"])) == len(profile["skills"]), profile["role"]
        for skill in profile["skills"]:
            # Grouped names never literal-match a resume; see prompts.py.
            assert "(" not in skill, (profile["role"], skill)
    for skill, alternatives in data["aliases"].items():
        assert alternatives, skill
        assert all(len(a) >= 2 for a in alternatives), skill


def test_rank_returns_every_profile_sorted_best_first():
    fits = careers.rank_careers(RESUME_TEXT)
    assert len(fits) == careers.profile_count()
    scores = [f.match_score for f in fits]
    assert scores == sorted(scores, reverse=True)
    for fit in fits:
        assert set(fit.covered_skills).isdisjoint(fit.missing_skills)


def test_backend_fixture_resume_ranks_backend_first():
    fits = careers.rank_careers(RESUME_TEXT, limit=3)
    assert fits[0].role == "Backend Developer"
    assert fits[0].match_score >= 60
    assert "Accountant" not in [f.role for f in fits]


def test_ranking_is_deterministic():
    first = careers.rank_careers(RESUME_TEXT)
    second = careers.rank_careers(RESUME_TEXT)
    assert [(f.role, f.match_score) for f in first] == [(f.role, f.match_score) for f in second]


def test_score_profiles_matches_score_per_profile():
    # The batch path embeds the resume once; it must not change any number.
    profiles, aliases = careers._load()
    subset = {k: profiles[k] for k in ["Backend Developer", "Accountant"]}
    batch = scoring.score_profiles(RESUME_TEXT, subset, aliases=aliases)
    for role, skills in subset.items():
        single = scoring.score(RESUME_TEXT, skills, aliases=aliases)
        assert batch[role].match_score == single.match_score
        assert [s.similarity for s in batch[role].skills] == [s.similarity for s in single.skills]


def test_alias_counts_as_literal_mention():
    text = "Shipped a service with GitHub Actions and documented its RESTful APIs."
    assert scoring._literal_mention("CI/CD", text) is False
    assert scoring._literal_mention("CI/CD", text, ["GitHub Actions"]) is True
    assert scoring._literal_mention("REST APIs", text, ["RESTful APIs"]) is True
    result = scoring.score(
        text,
        ["CI/CD", "REST APIs"],
        aliases={"CI/CD": ["GitHub Actions"], "REST APIs": ["RESTful APIs"]},
    )
    assert all(s.severity.value == "minor" for s in result.skills)


def test_find_profile_matches_role_name_in_text():
    assert careers.find_profile("I want to be an AI Engineer.")[0] == "AI Engineer"
    assert careers.find_profile("i want to be a machine learning engineer")[0] == (
        "Machine Learning Engineer"
    )
    assert careers.find_profile("Give me a job please") is None


def test_report_path_scores_same_as_career_fit(monkeypatch):
    # The panel and the report must agree on the same target. Both go
    # through run_analysis's scoring inputs; compare the scorer's number
    # for the curated profile with the ranking's number for that role.
    role, skill_list = careers.find_profile("I want to be a Backend Developer.")
    direct = scoring.score(RESUME_TEXT, skill_list, aliases=careers.aliases())
    ranked = {f.role: f.match_score for f in careers.rank_careers(RESUME_TEXT)}
    assert direct.match_score == ranked[role]
