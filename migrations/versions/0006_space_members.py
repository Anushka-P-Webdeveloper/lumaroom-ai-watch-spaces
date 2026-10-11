"""space membership (who joined which space, with role); backfills hosts of existing spaces"""
import sqlalchemy as sa
from alembic import op
revision, down_revision = "0006", "0005"

def upgrade():
    op.create_table("space_members", sa.Column("id", sa.Integer, primary_key=True), sa.Column("space_id", sa.Integer, nullable=False),
                    sa.Column("user_id", sa.Integer, nullable=False), sa.Column("role", sa.Text, nullable=False, server_default="participant"),
                    sa.Column("joined_at", sa.Float), sa.UniqueConstraint("space_id", "user_id"))
    op.execute("INSERT INTO space_members(space_id,user_id,role,joined_at) SELECT id, host_id, 'host', 0 FROM spaces")

def downgrade(): op.drop_table("space_members")
