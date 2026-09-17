"""sync_sqlite_schema is the dev stand-in for migrations on SQLite: an old
dev.db must gain new model columns on startup instead of 500ing."""

from sqlalchemy import inspect, text
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from app.db.session import sync_sqlite_schema


def test_missing_columns_are_added_to_existing_sqlite_table():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    with engine.begin() as conn:
        # A reports table from before scored_against and role_title existed.
        conn.execute(
            text(
                "CREATE TABLE reports (id VARCHAR PRIMARY KEY, user_id VARCHAR NOT NULL, "
                "title VARCHAR NOT NULL, job_description VARCHAR NOT NULL, "
                "self_description VARCHAR NOT NULL, resume_text VARCHAR NOT NULL, "
                "match_score INTEGER NOT NULL, skill_gaps JSON, technical_qs JSON, "
                "behavioral_qs JSON, preparation_plan JSON, created_at DATETIME NOT NULL)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO reports VALUES ('r1','u1','t','jd','', 'resume', 50, "
                "'[]','[]','[]','[]','2026-01-01 00:00:00')"
            )
        )

    sync_sqlite_schema(engine)
    sync_sqlite_schema(engine)  # idempotent

    cols = {c["name"] for c in inspect(engine).get_columns("reports")}
    assert {"scored_against", "role_title"} <= cols
    with engine.connect() as conn:
        row = conn.execute(text("SELECT scored_against, role_title FROM reports")).one()
    assert row == ("job_description", None)
