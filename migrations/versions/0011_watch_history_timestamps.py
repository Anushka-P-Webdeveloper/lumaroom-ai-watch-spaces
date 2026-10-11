"""Timestamp watch activity so profile history can be grouped and ordered."""
import sqlalchemy as sa
from alembic import op

revision, down_revision = "0011", "0010"


def upgrade():
    op.add_column("watch_events", sa.Column("watched_at", sa.Float, nullable=False, server_default="0"))


def downgrade():
    op.drop_column("watch_events", "watched_at")
