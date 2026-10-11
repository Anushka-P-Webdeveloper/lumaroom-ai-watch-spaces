"""Persist each member's co-pilot conversation for a watch space."""
import sqlalchemy as sa
from alembic import op

revision, down_revision = "0008", "0007"

def upgrade():
    op.create_table(
        "ai_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("space_id", sa.Integer, nullable=False),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("answer", sa.Text, nullable=False),
        sa.Column("sources", sa.Text, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.Float, nullable=False),
    )
    op.create_index("ix_ai_history_user_space", "ai_history", ["user_id", "space_id", "created_at"])

def downgrade():
    op.drop_index("ix_ai_history_user_space", table_name="ai_history")
    op.drop_table("ai_history")
