"""User-submitted ratings, reviews, and review comments."""
import sqlalchemy as sa
from alembic import op

revision, down_revision = "0007", "0006"

def upgrade():
    op.create_table(
        "title_reviews",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title_id", sa.Integer, nullable=False),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("rating", sa.Float, nullable=False),
        sa.Column("headline", sa.Text, nullable=False, server_default=""),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_at", sa.Float, nullable=False),
        sa.Column("updated_at", sa.Float, nullable=False),
        sa.UniqueConstraint("title_id", "user_id", name="uq_title_review_user"),
        sa.CheckConstraint("rating >= 0.5 AND rating <= 10", name="ck_title_review_rating"),
    )
    op.create_index("ix_title_reviews_title", "title_reviews", ["title_id", "created_at"])
    op.create_table(
        "review_comments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("review_id", sa.Integer, nullable=False),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_at", sa.Float, nullable=False),
    )
    op.create_index("ix_review_comments_review", "review_comments", ["review_id", "created_at"])

def downgrade():
    op.drop_table("review_comments")
    op.drop_index("ix_title_reviews_title", table_name="title_reviews")
    op.drop_table("title_reviews")
