"""PostgreSQL only: pgvector extension + kb_chunks (RAG embeddings). Dimension from EMBED_DIM at migration time."""
import os
from alembic import op
revision, down_revision = "0003", "0002"

def upgrade():
    if op.get_bind().dialect.name != "postgresql": return
    dim = int(os.getenv("EMBED_DIM", "1536"))
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(f"CREATE TABLE IF NOT EXISTS kb_chunks(id SERIAL PRIMARY KEY, title_id INTEGER, scene_id TEXT, start_sec INTEGER, end_sec INTEGER, doc_type TEXT, text TEXT, embedding vector({dim}))")
    op.execute("CREATE INDEX IF NOT EXISTS kb_title_idx ON kb_chunks(title_id, start_sec)")
    op.execute("CREATE INDEX IF NOT EXISTS kb_vec_idx ON kb_chunks USING hnsw (embedding vector_cosine_ops)")

def downgrade():
    if op.get_bind().dialect.name == "postgresql": op.execute("DROP TABLE IF EXISTS kb_chunks")
