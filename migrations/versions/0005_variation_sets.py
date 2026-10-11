"""pre-approved variation sets (narrative / localization options) + poll linkage and stored winner"""
import sqlalchemy as sa
from alembic import op
revision, down_revision = "0005", "0004"

def upgrade():
    op.create_table("variation_sets", sa.Column("id", sa.Integer, primary_key=True), sa.Column("slug", sa.Text, nullable=False, unique=True),
                    sa.Column("title_id", sa.Integer, sa.ForeignKey("titles.id", ondelete="CASCADE"), nullable=False),
                    sa.Column("scene_id", sa.Text),                       # NULL = title-wide (e.g. subtitle/dub choice)
                    sa.Column("kind", sa.Text, nullable=False), sa.Column("question", sa.Text, nullable=False))
    op.create_table("variation_options", sa.Column("id", sa.Integer, primary_key=True),
                    sa.Column("set_id", sa.Integer, sa.ForeignKey("variation_sets.id", ondelete="CASCADE"), nullable=False),
                    sa.Column("position", sa.Integer, nullable=False), sa.Column("label", sa.Text, nullable=False))
    with op.batch_alter_table("polls") as b:
        b.add_column(sa.Column("variation_set_id", sa.Integer)); b.add_column(sa.Column("winner", sa.Text))

def downgrade():
    with op.batch_alter_table("polls") as b:
        b.drop_column("winner"); b.drop_column("variation_set_id")
    op.drop_table("variation_options"); op.drop_table("variation_sets")
