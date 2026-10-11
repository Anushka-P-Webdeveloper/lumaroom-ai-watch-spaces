import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from alembic import context
from sqlalchemy import create_engine
import db

if context.is_offline_mode(): raise SystemExit("Offline mode not supported; run against a database.")
engine = create_engine(db.sqlalchemy_url())
with engine.begin() as conn:
    context.configure(connection=conn, target_metadata=None)
    with context.begin_transaction(): context.run_migrations()
engine.dispose()
