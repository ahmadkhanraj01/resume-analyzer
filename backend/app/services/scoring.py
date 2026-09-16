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

# Starting values. They need calibration against real resume/JD pairs before
# they mean anything; see docs/calibration.
COVERED_THRESHOLD = 0.75
PARTIAL_THRESHOLD = 0.55

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


def _literal_mention(skill: str, resume_text: str) -> bool:
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
    # See app/services/skills.py for why the lookaround treats a trailing
    # period specially: it must not block a skill at the end of a sentence.
    pattern = r"(?<![\w+#.])" + re.escape(skill) + r"(?![\w+#]|\.\w)"
    return bool(re.search(pattern, resume_text, re.IGNORECASE))


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


def score(
    resume_text: str,
    skills: list[str],
    skill_mentions: dict[str, int] | None = None,
    covered_threshold: float = COVERED_THRESHOLD,
    partial_threshold: float = PARTIAL_THRESHOLD,
) -> ScoringResult:
    """Scores a resume against a list of JD skills.

    skill_mentions maps a skill to how many times it appears in the JD, used
    to weight the aggregate. Skills not in the map default to one mention.
    """
    skill_mentions = skill_mentions or {}
    chunks = chunk_text(resume_text)
    if not chunks or not skills:
        return ScoringResult(match_score=0, skills=[])

    model = _model()
    chunk_vecs = list(model.embed(chunks))
    skill_vecs = list(model.embed(skills))

    skill_scores: list[SkillScore] = []
    total_weight = 0.0
    raw_sum = 0.0

    for skill, skill_vec in zip(skills, skill_vecs, strict=True):
        similarity = max(cosine_similarity(skill_vec, chunk_vec) for chunk_vec in chunk_vecs)
        if _literal_mention(skill, resume_text):
            similarity = max(similarity, covered_threshold)
        mentions = skill_mentions.get(skill, 1)
        weight = 1 + 0.5 * min(mentions - 1, 2)
        total_weight += weight
        raw_sum += weight * min(similarity / covered_threshold, 1.0)

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
