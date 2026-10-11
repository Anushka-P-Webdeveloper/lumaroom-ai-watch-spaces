"""Seed demo data (idempotent).   python seed.py [--embed]
Creates: catalog (titles+scenes), demo users, a public demo space, sample watch history.
--embed also (re)builds the RAG knowledge-base embeddings (needs AI_PROVIDER + API key)."""
import sys, secrets
import main, ai, catalog
from main import db, hash_pw, TITLES

DEMO_USERS = [("host@demo.com", "Demo Host", "animation,fantasy"), ("viewer@demo.com", "Demo Viewer", "sci-fi,drama")]

def run(embed: bool = False):
    catalog.seed_catalog(); main.reload_catalog()
    c = db()
    for email, name, genres in DEMO_USERS:
        if not c.execute("SELECT 1 AS x FROM users WHERE email=?", (email,)).fetchone():
            c.execute("INSERT INTO users(email,name,pw,genres) VALUES(?,?,?,?)", (email, name, hash_pw("demo1234"), genres))
    host = c.execute("SELECT id FROM users WHERE email='host@demo.com'").fetchone()["id"]
    viewer = c.execute("SELECT id FROM users WHERE email='viewer@demo.com'").fetchone()["id"]
    if not c.execute("SELECT 1 AS x FROM spaces WHERE code='DEMO01'").fetchone():
        c.execute("INSERT INTO spaces(code,name,title_id,host_id,public) VALUES(?,?,?,?,1)", ("DEMO01", "Demo watch party", 1, host))
    sp = c.execute("SELECT id FROM spaces WHERE code='DEMO01'").fetchone()["id"]; c.commit(); main.add_member(c, sp, host, "host")
    if not c.execute("SELECT 1 AS x FROM watch_events WHERE user_id=?", (viewer,)).fetchone():
        c.execute("INSERT INTO watch_events VALUES(?,?,?,?)", (viewer, 3, 900, 1)); c.execute("INSERT INTO watch_events VALUES(?,?,?,?)", (host, 3, 800, 1))
    c.commit()
    if embed: ai.build_index(TITLES, force=True); print("Knowledge base embedded.")
    print(f"Seeded {len(TITLES)} titles, demo users (password: demo1234), space code DEMO01.")

if __name__ == "__main__": run("--embed" in sys.argv)
