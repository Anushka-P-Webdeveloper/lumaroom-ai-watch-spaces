"""catalog tables: titles and scenes (scene knowledge used by trivia + RAG)"""
import sqlalchemy as sa
from alembic import op
revision, down_revision = "0002", "0001"

def upgrade():
    op.create_table("titles", sa.Column("id", sa.Integer, primary_key=True), sa.Column("name", sa.Text, nullable=False),
                    sa.Column("genres", sa.Text, nullable=False, server_default="[]"), sa.Column("video", sa.Text))
    op.create_table("scenes", sa.Column("id", sa.Integer, primary_key=True), sa.Column("title_id", sa.Integer, sa.ForeignKey("titles.id", ondelete="CASCADE"), nullable=False),
                    sa.Column("scene_id", sa.Text, nullable=False), sa.Column("start_sec", sa.Integer, nullable=False), sa.Column("end_sec", sa.Integer, nullable=False),
                    sa.Column("summary", sa.Text, nullable=False), sa.Column("trivia", sa.Text, nullable=False, server_default="[]"))
    op.create_index("ix_scenes_title_start", "scenes", ["title_id", "start_sec"])

def downgrade():
    op.drop_table("scenes"); op.drop_table("titles")
