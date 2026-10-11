import os, pytest
os.environ.setdefault("DB_PATH", "test.db")                      # SQLite unless DATABASE_URL is set
if os.getenv("DATABASE_URL"):                                    # clean slate on PostgreSQL (TEST DATABASE ONLY!)
    import psycopg
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True) as c: c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public")
elif os.path.exists("test.db"): os.remove("test.db")
if os.getenv("REDIS_URL"):
    import redis; redis.Redis.from_url(os.environ["REDIS_URL"]).flushdb()

@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from main import app
    with TestClient(app) as c: yield c                          # runs startup/shutdown (Redis listener)
