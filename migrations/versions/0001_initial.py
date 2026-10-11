"""initial schema: users, spaces, polls, votes, watch_events, chat (baseline; skips tables that already exist)"""
import sqlalchemy as sa
from alembic import op
revision, down_revision = "0001", None
C = sa.Column

def _ct(name, *cols):
    if not sa.inspect(op.get_bind()).has_table(name): op.create_table(name, *cols)

def upgrade():
    _ct("users", C("id", sa.Integer, primary_key=True), C("email", sa.Text, unique=True), C("name", sa.Text), C("pw", sa.Text), C("genres", sa.Text, server_default=""))
    _ct("spaces", C("id", sa.Integer, primary_key=True), C("code", sa.Text, unique=True), C("name", sa.Text), C("title_id", sa.Integer),
        C("host_id", sa.Integer), C("public", sa.Integer), C("active", sa.Integer, server_default="1"))
    _ct("polls", C("id", sa.Integer, primary_key=True), C("space_id", sa.Integer), C("question", sa.Text), C("options", sa.Text), C("open", sa.Integer, server_default="1"))
    _ct("votes", C("poll_id", sa.Integer), C("user_id", sa.Integer), C("option", sa.Integer), sa.UniqueConstraint("poll_id", "user_id"))   # one vote per user per poll
    _ct("watch_events", C("user_id", sa.Integer), C("title_id", sa.Integer), C("seconds", sa.Integer), C("completed", sa.Integer))
    _ct("chat", C("space_id", sa.Integer), C("user_id", sa.Integer), C("name", sa.Text), C("text", sa.Text), C("ts", sa.Float))

def downgrade():
    for t in ("chat", "watch_events", "votes", "polls", "spaces", "users"): op.drop_table(t)
