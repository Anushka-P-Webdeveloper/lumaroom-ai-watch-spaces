"""Catalog: seed data (open-license videos, fictional scene knowledge) <-> database tables."""
import json
import db

SEED = {1: {'id': 1,
     'name': 'Big Buck Bunny',
     'genres': ['english', 'movies', 'animation', 'comedy', 'family'],
     'video': 'https://www.youtube.com/watch?v=aqz-KE-bpKQ',
     'scenes': [{'id': 'bbb1',
                 'start': 0,
                 'end': 60,
                 'summary': 'A giant rabbit wakes up in a sunny meadow.',
                 'trivia': ['Made with Blender by the Blender Institute.']},
                {'id': 'bbb2',
                 'start': 60,
                 'end': 200,
                 'summary': 'Three rodents bully the rabbit and he plans revenge.',
                 'trivia': ['The squirrel antagonists are named Gimera, Frank and Rinky.']}]},
 2: {'id': 2,
     'name': 'Sintel',
     'genres': ['english', 'movies', 'animation', 'drama', 'romance', 'family'],
     'video': 'https://www.youtube.com/watch?v=eRsGyueVLvQ',
     'scenes': [{'id': 's1',
                 'start': 0,
                 'end': 120,
                 'summary': 'Sintel befriends a baby dragon.',
                 'trivia': ['Sintel is a 2010 open movie.']},
                {'id': 's2',
                 'start': 120,
                 'end': 400,
                 'summary': 'She searches for the dragon across the mountains.',
                 'trivia': ['The dragon is called Scales.']}]},
 3: {'id': 3,
     'name': 'Tears of Steel',
     'genres': ['english', 'movies', 'sci-fi', 'drama', 'action'],
     'video': 'https://www.youtube.com/watch?v=OHOpb2fS-cM',
     'scenes': [{'id': 't1',
                 'start': 0,
                 'end': 150,
                 'summary': 'Scientists gather in Amsterdam to save the world from robots.',
                 'trivia': ['Filmed with live action plus VFX.']}]},
 7: {'id': 7, 'name': 'Elephants Dream', 'genres': ['english', 'movies', 'animation', 'sci-fi'],
     'video': 'https://www.youtube.com/watch?v=ePVe9FzuFfQ', 'scenes': []},
 8: {'id': 8, 'name': 'Cosmos Laundromat: First Cycle', 'genres': ['english', 'movies', 'animation', 'comedy', 'sci-fi'],
     'video': 'https://www.youtube.com/watch?v=Y-rmzh0PI3c', 'scenes': []},
 9: {'id': 9, 'name': 'Caminandes 3: Llamigos', 'genres': ['english', 'movies', 'animation', 'comedy', 'family'],
     'video': 'https://www.youtube.com/watch?v=L6mLFxGRFI4', 'scenes': []},
 10: {'id': 10, 'name': 'Glass Half', 'genres': ['english', 'movies', 'animation', 'comedy'],
     'video': 'https://www.youtube.com/watch?v=lqiN98z6Dak', 'scenes': []},
 11: {'id': 11, 'name': 'Sprite Fright', 'genres': ['english', 'movies', 'animation', 'comedy', 'horror'],
     'video': 'https://www.youtube.com/watch?v=_cMxraX_5RE', 'scenes': []},
 12: {'id': 12, 'name': 'Spring', 'genres': ['english', 'movies', 'animation', 'drama', 'fantasy'],
     'video': 'https://www.youtube.com/watch?v=WhWc3b3KhnY', 'scenes': []},
 13: {'id': 13, 'name': 'Charge', 'genres': ['english', 'movies', 'animation', 'action', 'sci-fi'],
     'video': 'https://www.youtube.com/watch?v=UXqq0ZvbOnk', 'scenes': []},
 14: {'id': 14, 'name': 'Coffee Run', 'genres': ['english', 'movies', 'animation', 'comedy'],
     'video': 'https://www.youtube.com/watch?v=PVGeM40dABA', 'scenes': []},
 16: {'id': 16, 'name': '1920', 'genres': ['hindi', 'bollywood', 'movies', 'horror', 'romance'],
     'video': 'https://www.youtube.com/watch?v=tj814hcan3c', 'scenes': []},
 20: {'id': 20, 'name': 'Caminandes 1: Llama Drama', 'genres': ['english', 'movies', 'animation', 'comedy', 'family'],
     'video': 'https://www.youtube.com/watch?v=JOhiWY7XmoY', 'scenes': []},
 21: {'id': 21, 'name': 'Caminandes 2: Gran Dillama', 'genres': ['english', 'movies', 'animation', 'comedy', 'family'],
     'video': 'https://www.youtube.com/watch?v=Z4C82eyhwgU', 'scenes': []},
 }

UNEMBEDDABLE_IDS = {4, 5, 6, 15, 17, 18, 19}

SEED_VARIATIONS = [
    {"slug": "bbb-revenge", "title_id": 1, "scene_id": "bbb2", "kind": "narrative", "question": "How should the rabbit get his revenge?",
     "options": ["A clever trap", "A harmless prank", "Call in backup"]},
    {"slug": "bbb-subs", "title_id": 1, "scene_id": None, "kind": "localization", "question": "Pick a subtitle style",
     "options": ["Standard", "Descriptive (SDH)", "Kid-friendly"]},
    {"slug": "sintel-dragon", "title_id": 2, "scene_id": "s2", "kind": "narrative", "question": "What should Sintel do when she finds the dragon?",
     "options": ["Approach slowly", "Call out to it", "Watch from afar"]},
    {"slug": "tos-dub", "title_id": 3, "scene_id": None, "kind": "localization", "question": "Pick a dub flavour",
     "options": ["Neutral", "Regional", "Original audio + subtitles"]},
]

def seed_variations(c):
    for v in SEED_VARIATIONS:
        c.execute("INSERT INTO variation_sets(slug,title_id,scene_id,kind,question) VALUES(?,?,?,?,?) ON CONFLICT(slug) DO UPDATE SET "
                  "title_id=excluded.title_id, scene_id=excluded.scene_id, kind=excluded.kind, question=excluded.question",
                  (v["slug"], v["title_id"], v["scene_id"], v["kind"], v["question"]))
        sid = c.execute("SELECT id FROM variation_sets WHERE slug=?", (v["slug"],)).fetchone()["id"]
        c.execute("DELETE FROM variation_options WHERE set_id=?", (sid,))
        for i, label in enumerate(v["options"]): c.execute("INSERT INTO variation_options(set_id,position,label) VALUES(?,?,?)", (sid, i, label))

def seed_catalog():
    """Idempotent: upserts titles and replaces their scenes."""
    c = db.connect()
    for t in SEED.values():
        c.execute("INSERT INTO titles(id,name,genres,video) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                  "name=excluded.name, genres=excluded.genres, video=excluded.video", (t["id"], t["name"], json.dumps(t["genres"]), t["video"]))
        c.execute("DELETE FROM scenes WHERE title_id=?", (t["id"],))
        for sc in t["scenes"]:
            c.execute("INSERT INTO scenes(title_id,scene_id,start_sec,end_sec,summary,trivia) VALUES(?,?,?,?,?,?)",
                      (t["id"], sc["id"], sc["start"], sc["end"], sc["summary"], json.dumps(sc["trivia"])))
    for tid in UNEMBEDDABLE_IDS:
        c.execute("DELETE FROM scenes WHERE title_id=?", (tid,))
        c.execute("DELETE FROM titles WHERE id=?", (tid,))
    c.execute("UPDATE spaces SET active=0 WHERE title_id IN (%s)" % ",".join("?" for _ in UNEMBEDDABLE_IDS), tuple(UNEMBEDDABLE_IDS))
    seed_variations(c); c.commit()

def load(into: dict) -> int:
    """Fill `into` (in place, so importers keep the same dict object) from the DB. Returns number of titles."""
    c = db.connect(); into.clear()
    disabled = {r["video_url"] for r in c.execute("SELECT video_url FROM disabled_videos").fetchall()}
    for r in c.execute("SELECT * FROM titles ORDER BY id").fetchall():
        if r["video"] in disabled: continue
        into[r["id"]] = {"id": r["id"], "name": r["name"], "genres": json.loads(r["genres"]), "video": r["video"], "added_by": r["added_by"], "scenes": []}
    for s in c.execute("SELECT * FROM scenes ORDER BY title_id, start_sec").fetchall():
        if s["title_id"] in into:
            into[s["title_id"]]["scenes"].append({"id": s["scene_id"], "start": s["start_sec"], "end": s["end_sec"],
                                                  "summary": s["summary"], "trivia": json.loads(s["trivia"])})
    return len(into)
