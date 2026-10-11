"""query indexes for the hot paths (history/recommendations, chat replay, polls per space)"""
from alembic import op
revision, down_revision = "0004", "0003"
IDX = [("ix_watch_events_user", "watch_events", ["user_id"]), ("ix_chat_space_ts", "chat", ["space_id", "ts"]), ("ix_polls_space", "polls", ["space_id"])]

def upgrade():
    for n, t, c in IDX: op.create_index(n, t, c)

def downgrade():
    for n, t, _ in IDX: op.drop_index(n, table_name=t)
