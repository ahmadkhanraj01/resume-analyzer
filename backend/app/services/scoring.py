"""embeddings -> match score, skill gaps. Deterministic, no network call, no
temperature, no drift: the same inputs always produce the same score.

No FastAPI import. Runnable from a plain python -c script, which is the
point: this is the part of the app that can be tested with exact-value
assertions.
"""

import re
from dataclasses import dataclass
from functools import lru_cache

from fastembed import TextEmbedding

from app.schemas.report import Severity

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

# COVERED is the literal-mention floor (see _literal_mention). PARTIAL was
# 0.55 until a check against three real resumes (Sample/, Sept 2026): skills
# with no trace on the resume at all landed anywhere up to 0.61, so 0.55
# labelled Kubernetes "partial" on a Flutter student's CV. 0.62 sits just
# above that noise ceiling; the lowest genuinely partial signal seen so far
# (a scikit-learn skill against "built ML models in Python") was 0.67.
COVERED_THRESHOLD = 0.75
PARTIAL_THRESHOLD = 0.62

# Chunking approximates tokens with whitespace-split words, avoiding a second
# tokenizer dependency alongside fastembed's own. Close enough for English
# resume text; not used for anything that needs exact token accounting.
CHUNK_SIZE = 200
CHUNK_OVERLAP = 50


@dataclass
class SkillScore:
    skill: str
    similarity: float
    severity: Severity
    mentions_in_jd: int


@dataclass
class ScoringResult:
    match_score: int
    skills: list[SkillScore]


@lru_cache(maxsize=1)
def _model() -> TextEmbedding:
    # Loaded once at module level (via this cache), not per request. Reloading
    # a ~130 MB ONNX model on every call would make each analysis pay a fixed
    # cost this pipeline is designed to avoid.
    return TextEmbedding(model_name=EMBEDDING_MODEL)


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Splits text into overlapping word chunks. Overlap matters: a skill
    mentioned across a chunk boundary would otherwise be split in half and
    score low in both halves."""
    words = text.split()
    if not words:
        return []

    step = size - overlap
    chunks = []
    for start in range(0, len(words), step):
        chunk = words[start : start + size]
        if chunk:
            chunks.append(" ".join(chunk))
        if start + size >= len(words):
            break
    return chunks


def cosine_similarity(a, b) -> float:
    import numpy as np

    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _literal_mention(skill: str, resume_text: str, aliases: list[str] | None = None) -> bool:
    """Word-boundary, case-insensitive check for the skill name appearing
    verbatim in the resume.

    Embedding a two-word skill name and comparing it against a 200-word
    prose chunk structurally caps the cosine similarity well below what
    "the same word appears in both" would suggest: short-query-vs-long-
    passage comparisons dilute a single-word signal across the whole chunk
    embedding. Measured against the fixture resume, every skill it actually
    contains landed at 0.58 to 0.71, under COVERED_THRESHOLD, which is
    exactly the "Docker marked missing on a resume that says Docker" failure
    PHASES.md's Phase 4 checkpoint calls out. A literal mention is used as a
    floor on top of the embedding similarity rather than a replacement for
    it: it catches the exact-name case the embedding alone misses, while
    similarity still does the real work of catching synonyms, related
    tools, and partial coverage the resume never states verbatim.
    """
    names = _literal_names(skill)
    for alias in aliases or ():
        names.extend(_literal_names(alias))
    return any(_word_match(name, resume_text) for name in names)


def _literal_names(skill: str) -> list[str]:
    """Names to try verbatim for one skill. LLM-written skill lists often
    group tools as "State Management (Provider, Bloc, Riverpod)" or qualify
    a name as "Version Control (Git)". The whole string never appears on a
    resume, but the head and each parenthesised alternative often do, and a
    resume that says "Provider" has that skill."""
    names = [skill.strip()]
    m = re.fullmatch(r"(.+?)\s*\((.*)\)", skill.strip())
    if m:
        head, inner = m.group(1).strip(), m.group(2)
        # "e.g." and "such as" mark examples, not part of a name.
        inner = re.sub(r"^\s*(e\.?g\.?|such as|like)[:,]?\s*", "", inner, flags=re.IGNORECASE)
        names.append(head)
        names.extend(part.strip() for part in re.split(r"[,/]", inner))
    return [n for n in names if len(n) > 1]


def _word_match(name: str, resume_text: str) -> bool:
    # See app/services/skills.py for why the lookaround treats a trailing
    # period specially: it must not block a skill at the end of a sentence.
    pattern = r"(?<![\w+#.])" + re.escape(name) + r"(?![\w+#]|\.\w)"
    # Short all-caps names are acronyms, and acronyms collide across fields
    # when case is ignored: "SOC" (security operations centre) matched
    # "Zynq-7000 SoC" (system on chip) on an FPGA intern's resume. Resumes
    # write real acronyms in caps, so requiring exact case costs little.
    flags = 0 if (name.isupper() and len(name) <= 4) else re.IGNORECASE
    return bool(re.search(pattern, resume_text, flags))


def _severity(similarity: float, covered: float, partial: float) -> Severity:
    # skill_gaps carries every JD skill, not only the missing ones, so the
    # report can say "you're solid here" as well as "you're missing this".
    # Covered -> minor (present, worth a one-line mention), partial ->
    # moderate, missing -> critical. Per DESIGN.md's threshold mapping.
    if similarity >= covered:
        return Severity.minor
    if similarity >= partial:
        return Severity.moderate
    return Severity.critical


def _coverage(similarity: float, covered: float, partial: float) -> float:
    """Maps a similarity to the 0..1 credit it earns toward the match score.

    Credit is zero at or below the partial threshold, rising linearly to
    full at the covered threshold. The earlier formula, similarity divided
    by the covered threshold, gave every skill a large floor: the embedding
    model never scores unrelated English text much below 0.46, so a resume
    with none of the skills still came out around 65 to 75%. Three real
    resumes with no ML content scored 74 to 77% against an AI Engineer
    profile. Anchoring zero credit at the partial threshold is what makes a
    20% match display as 20%, which DESIGN.md requires.
    """
    if similarity >= covered:
        return 1.0
    if similarity <= partial:
        return 0.0
    return (similarity - partial) / (covered - partial)


@lru_cache(maxsize=64)
def _skill_vecs(skills: tuple[str, ...]) -> list:
    """Skill-name embeddings, cached by the exact list. Role profiles are
    static and scored on every career-fit request, so re-embedding 36
    lists of 15 names per request would dominate the cost. A JD's ad hoc
    list simply misses the cache. 64 entries of 16 x 384 floats is under
    2 MB."""
    return list(_model().embed(list(skills)))


def score(
    resume_text: str,
    skills: list[str],
    skill_mentions: dict[str, int] | None = None,
    covered_threshold: float = COVERED_THRESHOLD,
    partial_threshold: float = PARTIAL_THRESHOLD,
    aliases: dict[str, list[str]] | None = None,
) -> ScoringResult:
    """Scores a resume against a list of JD skills.

    skill_mentions maps a skill to how many times it appears in the JD, used
    to weight the aggregate. Skills not in the map default to one mention.
    aliases maps a skill to other spellings a resume may use for it; a
    literal mention of any alias counts as a mention of the skill.
    """
    chunks = chunk_text(resume_text)
    if not chunks or not skills:
        return ScoringResult(match_score=0, skills=[])
    chunk_vecs = list(_model().embed(chunks))
    return _score_against_chunks(
        resume_text,
        chunk_vecs,
        skills,
        skill_mentions,
        covered_threshold,
        partial_threshold,
        aliases,
    )


def score_profiles(
    resume_text: str,
    profiles: dict[str, list[str]],
    covered_threshold: float = COVERED_THRESHOLD,
    partial_threshold: float = PARTIAL_THRESHOLD,
    aliases: dict[str, list[str]] | None = None,
) -> dict[str, ScoringResult]:
    """Scores one resume against many skill lists, embedding the resume
    once. Same numbers as calling score() per profile; the only difference
    is cost."""
    chunks = chunk_text(resume_text)
    if not chunks:
        return {name: ScoringResult(match_score=0, skills=[]) for name in profiles}
    chunk_vecs = list(_model().embed(chunks))
    return {
        name: _score_against_chunks(
            resume_text, chunk_vecs, skills, None, covered_threshold, partial_threshold, aliases
        )
        for name, skills in profiles.items()
    }


def _score_against_chunks(
    resume_text: str,
    chunk_vecs: list,
    skills: list[str],
    skill_mentions: dict[str, int] | None,
    covered_threshold: float,
    partial_threshold: float,
    aliases: dict[str, list[str]] | None,
) -> ScoringResult:
    skill_mentions = skill_mentions or {}
    aliases = aliases or {}
    if not skills:
        return ScoringResult(match_score=0, skills=[])
    skill_vecs = _skill_vecs(tuple(skills))

    skill_scores: list[SkillScore] = []
    total_weight = 0.0
    raw_sum = 0.0

    for skill, skill_vec in zip(skills, skill_vecs, strict=True):
        similarity = max(cosine_similarity(skill_vec, chunk_vec) for chunk_vec in chunk_vecs)
        if _literal_mention(skill, resume_text, aliases.get(skill)):
            similarity = max(similarity, covered_threshold)
        mentions = skill_mentions.get(skill, 1)
        weight = 1 + 0.5 * min(mentions - 1, 2)
        total_weight += weight
        raw_sum += weight * _coverage(similarity, covered_threshold, partial_threshold)

        skill_scores.append(
            SkillScore(
                skill=skill,
                similarity=round(similarity, 4),
                severity=_severity(similarity, covered_threshold, partial_threshold),
                mentions_in_jd=mentions,
            )
        )

    match_score = round(100 * raw_sum / total_weight) if total_weight else 0
    return ScoringResult(match_score=match_score, skills=skill_scores)
