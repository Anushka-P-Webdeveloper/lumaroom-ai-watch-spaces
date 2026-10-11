"""Remember YouTube videos that reject embedding."""
import sqlalchemy as sa
from alembic import op

revision, down_revision = "0009", "0008"

def upgrade():
    op.create_table(
        "disabled_videos",
        sa.Column("video_url", sa.Text, primary_key=True),
        sa.Column("created_at", sa.Float, nullable=False),
    )

def downgrade():
    op.drop_table("disabled_videos")
