"""DB adapter: PostgreSQL (DATABASE_URL, + pgvector) or SQLite fallback. Same `?` placeholder API for both."""
import os, sqlite3, threading
try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
IntegrityError = (sqlite3.IntegrityError,) + ((psycopg.IntegrityError,) if psycopg else ())
ID_TABLES = ("users", "spaces", "polls", "ai_history", "titles")
_local = threading.local()

def is_pg(): return os.getenv("DATABASE_URL", "").startswith("postgres")
def embed_dim(): return int(os.getenv("EMBED_DIM", "1536"))   # OpenAI 1536, Gemini text-embedding-004 = 768

class _R:
    def __init__(s, cur, rid=None): s.cur, s.lastrowid = cur, rid
    def fetchone(s): return s.cur.fetchone()
    def fetchall(s): return s.cur.fetchall()
    def __iter__(s): return iter(s.cur.fetchall())

class Conn:
    def __init__(s, raw, pg): s.raw, s.pg = raw, pg
    def execute(s, sql, params=()):
        if not s.pg:
            cur = s.raw.execute(sql, params); return _R(cur, cur.lastrowid)
        sql = sql.replace("?", "%s")
        parts = sql.split()
        want = sql.lstrip().upper().startswith("INSERT INTO") and parts[2].split("(")[0].lower() in ID_TABLES
        cur = s.raw.execute(sql + (" RETURNING id" if want else ""), params)
        return _R(cur, cur.fetchone()["id"] if want else None)
    def commit(s):
        if not s.pg: s.raw.commit()
    def close(s):
        if not s.pg: s.raw.close()          # PG connection is cached per thread (autocommit)

def connect() -> Conn:
    if is_pg():
        c = getattr(_local, "c", None)
        if c is None or c.closed:
            c = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, row_factory=dict_row); _local.c = c
        return Conn(c, True)
    r = sqlite3.connect(os.getenv("DB_PATH", "app.db")); r.row_factory = sqlite3.Row
    return Conn(r, False)

HERE = os.path.dirname(os.path.abspath(__file__))
def sqlalchemy_url():
    """URL for Alembic (SQLAlchemy). Runtime queries use psycopg/sqlite3 directly."""
    if is_pg(): return os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1).replace("postgresql://", "postgresql+psycopg://", 1)
    return "sqlite:///" + os.path.abspath(os.getenv("DB_PATH", "app.db"))

def migrate(revision: str = "head", downgrade: bool = False):
    """Run Alembic programmatically (same as `alembic upgrade head`)."""
    from alembic import command
    from alembic.config import Config
    cfg = Config(os.path.join(HERE, "alembic.ini")); cfg.set_main_option("script_location", os.path.join(HERE, "migrations"))
    (command.downgrade if downgrade else command.upgrade)(cfg, revision)
