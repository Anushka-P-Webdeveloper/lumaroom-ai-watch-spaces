import sqlite3
import catalog, db

def test_migrate_up_down_and_seed_idempotent(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False); monkeypatch.setenv("DB_PATH", str(tmp_path / "m.db"))
    db.migrate(); db.migrate()                                         # re-running is a no-op
    tables = lambda: {r[0] for r in sqlite3.connect(str(tmp_path / "m.db")).execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"users", "spaces", "votes", "titles", "scenes", "alembic_version"} <= tables()
    catalog.seed_catalog(); catalog.seed_catalog()                     # idempotent: no duplicates
    loaded = {}; assert catalog.load(loaded) == 3 and len(loaded[1]["scenes"]) == 2
    assert loaded[1]["scenes"][0]["trivia"]                            # JSON round-trips
    assert db.connect().execute("SELECT count(*) AS n FROM variation_options").fetchone()["n"] == 12
    db.migrate("0001", downgrade=True)                                 # step back to the baseline
    assert "titles" not in tables() and "users" in tables()
    db.migrate("base", downgrade=True); assert "users" not in tables()
