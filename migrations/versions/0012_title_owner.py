"""Track which user added a catalog title (NULL = default/seeded catalog)."""
import sqlalchemy as sa
from alembic import op

revision, down_revision = "0012", "0011"


def upgrade():
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("titles")}
    if "added_by" not in cols:
        op.add_column("titles", sa.Column("added_by", sa.Integer, nullable=True))


def downgrade():
    with op.batch_alter_table("titles") as b:
        b.drop_column("added_by")
