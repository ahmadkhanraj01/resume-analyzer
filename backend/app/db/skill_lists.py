"""Postgres-backed store for LLM-named skill lists. See SkillList.

Lives in app/db rather than app/services so the services stay free of
database code: the router hands an instance to run_analysis, and tests or
scripts get the in-memory store in services/skills.py instead.
"""

import logging

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import Session

from app.db.models import SkillList

logger = logging.getLogger(__name__)


class DbSkillListStore:
    """Survives restarts, which an in-memory cache does not: Render's free
    instance sleeps after 15 idle minutes, and every wake-up used to give
    the same job description a freshly extracted, slightly different skill
    list and so a different score.

    Opens its own sessions because it runs inside run_in_threadpool, where
    the request's session is not safe to share. A database error degrades
    to "not cached" so a missing table or a blip never fails an analysis."""

    def __init__(self, engine):
        self._engine = engine

    def get(self, key: str) -> tuple[str | None, list[str]] | None:
        try:
            with Session(self._engine) as session:
                row = session.get(SkillList, key)
                return (row.role, list(row.skills)) if row else None
        except SQLAlchemyError:
            logger.warning("skill list lookup failed", exc_info=True)
            return None

    def put(self, key: str, role: str | None, skills: list[str]) -> None:
        try:
            with Session(self._engine) as session:
                session.add(SkillList(key=key, role=role, skills=list(skills)))
                session.commit()
        except IntegrityError:
            # A concurrent request stored this key first. Keep its list: the
            # first one written is the one every later analysis must see.
            pass
        except SQLAlchemyError:
            logger.warning("skill list store failed", exc_info=True)
