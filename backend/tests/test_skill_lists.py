"""The Postgres-backed skill list store, run against the test SQLite engine."""

from sqlmodel import SQLModel, create_engine

from app.db.skill_lists import DbSkillListStore


def test_round_trip(engine):
    store = DbSkillListStore(engine)
    assert store.get("jd:abc") is None
    store.put("jd:abc", None, ["Python", "Go"])
    assert store.get("jd:abc") == (None, ["Python", "Go"])


def test_first_writer_wins(engine):
    store = DbSkillListStore(engine)
    store.put("role:abc", "Game Developer", ["Unity"])
    store.put("role:abc", "Something Else", ["Unreal"])
    assert store.get("role:abc") == ("Game Developer", ["Unity"])


def test_missing_table_degrades_to_uncached():
    # Before the migration runs in production the table does not exist;
    # analysis must keep working, just without the cache.
    bare = create_engine("sqlite://")
    SQLModel.metadata.drop_all(bare)
    store = DbSkillListStore(bare)
    assert store.get("jd:abc") is None
    store.put("jd:abc", None, ["Python"])  # must not raise
