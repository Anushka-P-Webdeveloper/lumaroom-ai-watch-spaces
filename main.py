"""Netflix AI Watch Spaces - backend core (FastAPI + SQLite + WebSockets).
Swap SQLite->PostgreSQL and Hub->Redis pub/sub later without changing the API."""
import hashlib, os, re, secrets, sqlite3, time, json
from collections import Counter
from urllib.parse import parse_qs, urlparse
import jwt
import httpx
import ai, kv, asyncio, catalog
import db as dbm
from fastapi import FastAPI, HTTPException, Depends, WebSocket, WebSocketDisconnect, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
DB = os.getenv("DB_PATH", "app.db")
app = FastAPI(title="Netflix AI Watch Spaces")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

db = dbm.connect
dbm.migrate()   # Alembic: upgrade to head

# ---- Catalog lives in the DB (tables titles/scenes); TITLES is an in-process cache of it ----
TITLES: dict = {}
def reload_catalog():
    if not catalog.load(TITLES) and os.getenv("AUTO_SEED", "1") != "0":   # empty DB: seed on first boot (or run `python seed.py`)
        catalog.seed_catalog(); catalog.load(TITLES)
reload_catalog()

# ---- Auth ----
def hash_pw(p): return hashlib.pbkdf2_hmac("sha256", p.encode(), b"salt-" + SECRET.encode(), 100_000).hex()
def make_token(uid, minutes=60): return jwt.encode({"sub": str(uid), "exp": time.time() + minutes*60}, SECRET, "HS256")
def decode(token):
    try: return int(jwt.decode(token, SECRET, ["HS256"])["sub"])
    except Exception: raise HTTPException(401, "Invalid token")
def current_user(authorization: str = Header("")):
    uid = decode(authorization.replace("Bearer ", ""))
    c = db(); u = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone(); c.close()
    if not u: raise HTTPException(401, "Unknown user")
    return dict(u)

class Reg(BaseModel): email: str; name: str; password: str; genres: list[str] = []
class Login(BaseModel): email: str; password: str

@app.post("/auth/register")
def register(r: Reg):
    c = db()
    try:
        cur = c.execute("INSERT INTO users(email,name,pw,genres) VALUES(?,?,?,?)", (r.email, r.name, hash_pw(r.password), ",".join(r.genres)))
        c.commit()
    except dbm.IntegrityError: raise HTTPException(409, "Email already registered")
    return {"token": make_token(cur.lastrowid)}

@app.post("/auth/login")
def login(r: Login):
    c = db(); u = c.execute("SELECT * FROM users WHERE email=? AND pw=?", (r.email, hash_pw(r.password))).fetchone()
    if not u: raise HTTPException(401, "Bad credentials")
    return {"token": make_token(u["id"])}

@app.get("/me")
def me(u=Depends(current_user)): return {k: u[k] for k in ("id","email","name","genres")}

def owner_name(c, uid):
    if not uid: return None
    r = c.execute("SELECT name FROM users WHERE id=?", (uid,)).fetchone()
    return r["name"] if r else None

@app.get("/titles")
def titles(): return [{k: t[k] for k in ("id","name","genres","video","added_by")} for t in TITLES.values()]

class NewTitle(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    video: str = Field(min_length=8, max_length=500)
    genres: list[str] = Field(default_factory=list)

def canonical_youtube_video_url(raw: str) -> str:
    try:
        parsed = urlparse(raw.strip())
        host = (parsed.hostname or "").lower()
        if host in {"youtu.be", "www.youtu.be"}:
            video_id = parsed.path.strip("/").split("/")[0]
        elif host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
            parts = [part for part in parsed.path.split("/") if part]
            video_id = parse_qs(parsed.query).get("v", [""])[0]
            if not video_id and len(parts) > 1 and parts[0] in {"embed", "shorts", "live"}:
                video_id = parts[1]
        else:
            video_id = ""
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            raise ValueError
        return f"https://www.youtube.com/watch?v={video_id}"
    except Exception:
        raise HTTPException(400, "Enter a direct YouTube video link (not a channel or playlist).")

@app.post("/titles")
def add_title(t: NewTitle, u=Depends(current_user)):
    name = t.name.strip()
    if not name: raise HTTPException(400, "Enter a video title.")
    video = canonical_youtube_video_url(t.video)
    c = db()
    if c.execute("SELECT 1 AS x FROM titles WHERE video=?", (video,)).fetchone():
        raise HTTPException(409, "That video is already in the catalog.")
    if c.execute("SELECT 1 AS x FROM disabled_videos WHERE video_url=?", (video,)).fetchone():
        raise HTTPException(409, "That video was removed because embedding is disabled.")
    genres = list(dict.fromkeys(" ".join(g.split()).strip() for g in t.genres if g.strip()))[:20]
    cur = c.execute("INSERT INTO titles(name,genres,video,added_by) VALUES(?,?,?,?)", (name, json.dumps(genres), video, u["id"]))
    c.commit(); reload_catalog()
    return {k: TITLES[cur.lastrowid][k] for k in ("id", "name", "genres", "video", "added_by")}

class EditTitle(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    genres: list[str] | None = None

def own_title_or_403(c, tid, u):
    row = c.execute("SELECT added_by FROM titles WHERE id=?", (tid,)).fetchone()
    if not row or tid not in TITLES: raise HTTPException(404, "Title not found")
    if not row["added_by"] or row["added_by"] != u["id"]: raise HTTPException(403, "Only the user who added this catalogue entry can change it")

@app.put("/titles/{tid}")
def edit_title(tid: int, e: EditTitle, u=Depends(current_user)):
    c = db(); own_title_or_403(c, tid, u)
    name = (e.name if e.name is not None else TITLES[tid]["name"]).strip()
    if not name: raise HTTPException(400, "Enter a video title.")
    genres = TITLES[tid]["genres"] if e.genres is None else list(dict.fromkeys(" ".join(g.split()) for g in e.genres if g.strip()))[:20]
    c.execute("UPDATE titles SET name=?, genres=? WHERE id=?", (name, json.dumps(genres), tid)); c.commit(); reload_catalog()
    return {k: TITLES[tid][k] for k in ("id", "name", "genres", "video", "added_by")}

@app.delete("/titles/{tid}")
def delete_title(tid: int, u=Depends(current_user)):
    c = db(); own_title_or_403(c, tid, u)
    c.execute("UPDATE spaces SET active=0 WHERE title_id=?", (tid,))
    c.execute("DELETE FROM scenes WHERE title_id=?", (tid,))
    c.execute("DELETE FROM watch_events WHERE title_id=?", (tid,))
    c.execute("DELETE FROM review_comments WHERE review_id IN (SELECT id FROM title_reviews WHERE title_id=?)", (tid,))
    c.execute("DELETE FROM title_reviews WHERE title_id=?", (tid,))
    c.execute("DELETE FROM variation_options WHERE set_id IN (SELECT id FROM variation_sets WHERE title_id=?)", (tid,))
    c.execute("DELETE FROM variation_sets WHERE title_id=?", (tid,))
    c.execute("DELETE FROM titles WHERE id=?", (tid,)); c.commit(); reload_catalog()
    return {"deleted": True}

@app.post("/titles/{tid}/embed-disabled")
def mark_embed_disabled(tid: int, u=Depends(current_user)):
    c = db()
    row = c.execute("SELECT video FROM titles WHERE id=?", (tid,)).fetchone()
    if not row: raise HTTPException(404, "Title not found")
    c.execute("INSERT INTO disabled_videos(video_url,created_at) VALUES(?,?) ON CONFLICT(video_url) DO NOTHING", (row["video"], time.time()))
    c.commit(); reload_catalog()
    return {"removed": True}

# ---- Spaces ----
def add_member(c, sid, uid, role="participant"):
    c.execute("INSERT INTO space_members(space_id,user_id,role,joined_at) VALUES(?,?,?,?) ON CONFLICT(space_id,user_id) DO NOTHING", (sid, uid, role, time.time())); c.commit()
def is_member(c, sid, uid): return bool(c.execute("SELECT 1 AS x FROM space_members WHERE space_id=? AND user_id=?", (sid, uid)).fetchone())

class NewSpace(BaseModel): name: str; title_id: int; public: bool = True
class Join(BaseModel): code: str

def record_watch_event(user_id: int, title_id: int, seconds: int = 0, completed: bool = False):
    c = db()
    c.execute("INSERT INTO watch_events(user_id,title_id,seconds,completed,watched_at) VALUES(?,?,?,?,?)",
              (user_id, title_id, max(0, int(seconds)), int(completed), time.time()))
    c.commit()

@app.post("/spaces")
def create_space(s: NewSpace, u=Depends(current_user)):
    if s.title_id not in TITLES: raise HTTPException(404, "Title not found")
    code = secrets.token_hex(3).upper(); c = db()
    cur = c.execute("INSERT INTO spaces(code,name,title_id,host_id,public) VALUES(?,?,?,?,?)", (code, s.name, s.title_id, u["id"], int(s.public)))
    c.commit(); add_member(c, cur.lastrowid, u["id"], "host"); record_watch_event(u["id"], s.title_id)
    return {"id": cur.lastrowid, "code": code}

@app.get("/spaces")
def lobby():
    c = db()
    rows = c.execute("SELECT s.id,s.code,s.name,s.title_id,s.host_id,u.name AS host_name FROM spaces s JOIN titles t ON t.id=s.title_id LEFT JOIN users u ON u.id=s.host_id WHERE s.public=1 AND s.active=1").fetchall()
    return [dict(r) for r in rows if r["title_id"] in TITLES]

@app.post("/spaces/join")
def join(j: Join, u=Depends(current_user)):
    c = db(); s = c.execute("SELECT * FROM spaces WHERE code=? AND active=1", (j.code.upper(),)).fetchone()
    if not s or s["title_id"] not in TITLES: raise HTTPException(404, "Watch space or its video is no longer available")
    add_member(c, s["id"], u["id"]); record_watch_event(u["id"], s["title_id"])
    return dict(s) | {"host_name": owner_name(c, s["host_id"])}

@app.get("/spaces/{sid}/chat")
def chat_history(sid: int, limit: int = 100, u=Depends(current_user)):
    c = db()
    if not c.execute("SELECT 1 AS x FROM spaces WHERE id=?", (sid,)).fetchone(): raise HTTPException(404, "Watch space not found")
    if not is_member(c, sid, u["id"]): raise HTTPException(403, "Join the watch space to view its chat")
    limit = min(max(limit, 1), 100)
    rows = c.execute("SELECT user_id,name AS user,text,ts FROM chat WHERE space_id=? ORDER BY ts DESC LIMIT ?", (sid, limit)).fetchall()
    return [dict(r) for r in reversed(rows)]

@app.delete("/spaces/{sid}")
def end_space(sid: int, u=Depends(current_user)):
    c = db(); s = c.execute("SELECT * FROM spaces WHERE id=?", (sid,)).fetchone()
    if not s or s["host_id"] != u["id"]: raise HTTPException(403, "Only host can end")
    c.execute("UPDATE spaces SET active=0 WHERE id=?", (sid,)); c.commit()
    kv.delete(f"space:{sid}:state", f"space:{sid}:trivia", f"space:{sid}:online", f"space:{sid}:uids"); return {"ended": True}

# ---- Playback state + sync math ----
def expected_position(state, now=None):
    """Position a late joiner/client should be at right now."""
    now = now or time.time()
    return state["position"] + (now - state["server_ts"]) if state["playing"] else state["position"]

def drift_action(local, expected, threshold=1.0):
    """'seek' on large drift, otherwise a gentle playbackRate nudge."""
    d = local - expected
    if abs(d) > threshold: return ("seek", expected)
    return ("rate", 0.95 if d > 0.1 else 1.05 if d < -0.1 else 1.0)

def pick_trivia(announced: set, title_id: int, t: float):
    """Trivia for the scene playing at time t, once per scene per space (swap `announced` for a Redis set to dedupe across instances)."""
    for sc in TITLES[title_id]["scenes"]:
        if sc["start"] <= t < sc["end"]:
            if sc["id"] in announced or not sc["trivia"]: return None
            announced.add(sc["id"]); return {"scene_id": sc["id"], "text": sc["trivia"][0]}
    return None

class Announced:
    """Trivia already shown in a space (Redis set => deduplicated across server instances)."""
    def __init__(s, sid): s.k = f"space:{sid}:trivia"
    def __contains__(s, m): return kv.sismember(s.k, m)
    def add(s, m): kv.sadd(s.k, m)

class Hub:
    """Sockets are per-process. With REDIS_URL set, events go through Redis pub/sub so any instance reaches any room."""
    def __init__(self): self.rooms = {}
    async def deliver(self, sid, msg):
        for ws in list(self.rooms.get(sid, {})):
            try: await ws.send_json(msg)
            except Exception: self.rooms[sid].pop(ws, None)
    async def publish(self, sid, msg):
        msg["server_ts"] = time.time()
        if kv.use_redis(): await kv.apub().publish(f"space:{sid}", json.dumps(msg))
        else: await self.deliver(sid, msg)
    async def listen(self):
        ps = kv.apub().pubsub(); await ps.psubscribe("space:*")
        async for m in ps.listen():
            if m["type"] == "pmessage": await self.deliver(int(m["channel"].split(":")[1]), json.loads(m["data"]))
hub = Hub()

# ---- RAG co-pilot (retrieval + optional spoiler-safe mode). ----
def tokenize(t): return set(re.findall(r"[a-z]+", t.lower()))
def retrieve(title_id, current_time, question, k=3, include_spoilers=True):
    chunks = []
    for sc in TITLES[title_id]["scenes"]:
        if include_spoilers or sc["start"] <= current_time:
            for text in [sc["summary"]] + sc["trivia"]:
                chunks.append((len(tokenize(question) & tokenize(text)), sc["id"], text))
    chunks = [c for c in sorted(chunks, reverse=True) if c[0] > 0]
    return chunks[:k]

def generate(question, ctx):
    """Grounded answer. For an LLM: send ONLY ctx in the prompt, tell it ctx is data not instructions."""
    if not ctx: return "I don't have approved info on that.", []
    return " ".join(c[2] for c in ctx), sorted({c[1] for c in ctx})

class Ask(BaseModel): space_id: int; question: str; current_time: float = 0; include_spoilers: bool = True
_rate = {}
@app.post("/ai/ask")
def ask(a: Ask, u=Depends(current_user)):
    if len(a.question) > 300: raise HTTPException(400, "Question too long")
    if kv.incr(f"rl:ai:{u['id']}", 60) > 10: raise HTTPException(429, "Rate limit")
    c = db(); s = c.execute("SELECT title_id FROM spaces WHERE id=?", (a.space_id,)).fetchone()
    if not s: raise HTTPException(404, "Space not found")
    mode = "lexical"
    if ai.is_configured():
        try:
            ans, sources = ai.answer(TITLES, s["title_id"], a.current_time, a.question, a.include_spoilers); mode = ai.PROVIDER()
        except httpx.TimeoutException:
            if ai.PROVIDER() == "gemini" and a.include_spoilers:
                raise HTTPException(504, "Video analysis took too long. Please try again in a moment.")
            ans, sources = generate(a.question, retrieve(s["title_id"], a.current_time, a.question, include_spoilers=a.include_spoilers))
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if ai.PROVIDER() == "gemini" and a.include_spoilers:
                if status == 429:
                    message = "Gemini free-tier limit reached. Please wait and try again later."
                elif status in (401, 403):
                    message = "Gemini rejected the API key or video request. Check the key and video access."
                elif status == 400:
                    message = "Gemini could not process this video. Try a public YouTube video."
                else:
                    message = "Gemini video analysis is temporarily unavailable. Please try again."
                print("AI provider HTTP error:", status)
                raise HTTPException(status if status in (400, 401, 403, 429) else 502, message)
            else:
                ans, sources = generate(a.question, retrieve(s["title_id"], a.current_time, a.question, include_spoilers=a.include_spoilers))
        except Exception as e:                      # provider down / bad key -> degrade gracefully
            print("AI provider error:", e)
            if ai.PROVIDER() == "gemini" and a.include_spoilers:
                raise HTTPException(502, "Gemini video analysis failed. Check the API key, quota, and that this is a public YouTube video.")
            ans, sources = generate(a.question, retrieve(s["title_id"], a.current_time, a.question, include_spoilers=a.include_spoilers))
    else: ans, sources = generate(a.question, retrieve(s["title_id"], a.current_time, a.question, include_spoilers=a.include_spoilers))
    created_at = time.time()
    c.execute("INSERT INTO ai_history(space_id,user_id,question,answer,sources,created_at) VALUES(?,?,?,?,?,?)",
              (a.space_id, u["id"], a.question, ans, json.dumps(sources), created_at)); c.commit()
    return {"answer": ans, "sources": sources, "mode": mode, "created_at": created_at}

@app.get("/spaces/{sid}/ai/history")
def ai_history(sid: int, limit: int = 100, u=Depends(current_user)):
    c = db()
    if not c.execute("SELECT 1 AS x FROM spaces WHERE id=?", (sid,)).fetchone(): raise HTTPException(404, "Watch space not found")
    if not is_member(c, sid, u["id"]): raise HTTPException(403, "Join the watch space to view its co-pilot history")
    limit = min(max(limit, 1), 100)
    rows = c.execute("SELECT question,answer,sources,created_at FROM ai_history WHERE space_id=? AND user_id=? ORDER BY created_at DESC,id DESC LIMIT ?",
                     (sid, u["id"], limit)).fetchall()
    return [{"q": r["question"], "a": r["answer"], "src": json.loads(r["sources"] or "[]"), "created_at": r["created_at"]} for r in reversed(rows)]

@app.get("/ai/status")
def ai_status(space_id: int, u=Depends(current_user)):
    c = db(); s = c.execute("SELECT title_id FROM spaces WHERE id=?", (space_id,)).fetchone()
    if not s: raise HTTPException(404, "Space not found")
    if not is_member(c, space_id, u["id"]): raise HTTPException(403, "Join the space to use its co-pilot")
    title = TITLES[s["title_id"]]
    return {"provider": ai.PROVIDER() if ai.is_configured() else "none", "configured": ai.is_configured(), "scene_notes": len(title["scenes"])}

# ---- Polls (pre-approved options only, one vote per user) ----
DEFAULT_POLLS = {
    "break": {"question": "Take a short break?", "options": ["Yes, pause for 5 min", "No, keep watching"]},
    "rate": {"question": "How are we liking it so far?", "options": ["Loving it", "It's okay", "Not for me"]},
    "next": {"question": "What should we watch next?", "options": ["Something similar", "A comedy", "An action movie", "Surprise us"]},
}

@app.get("/polls/defaults")
def default_polls(u=Depends(current_user)):
    return [{"key": k, **v} for k, v in DEFAULT_POLLS.items()]

class NewPoll(BaseModel):
    default_key: str | None = None
    variation_set_id: int | None = None
    question: str = ""
    options: list[str] = Field(default_factory=list)
class Vote(BaseModel): option: int

def unlocked_sets(c, sid, title_id):
    """Approved variation sets for this space's title. Scene-specific ones unlock only once the host has reached that scene (spoiler-safe)."""
    pos = expected_position(get_state(sid))
    starts = {sc["id"]: sc["start"] for sc in TITLES[title_id]["scenes"]}
    out = []
    for v in c.execute("SELECT * FROM variation_sets WHERE title_id=? ORDER BY id", (title_id,)).fetchall():
        if v["scene_id"] is None or starts.get(v["scene_id"], 0) <= pos:
            opts = [o["label"] for o in c.execute("SELECT label FROM variation_options WHERE set_id=? ORDER BY position", (v["id"],)).fetchall()]
            out.append({"id": v["id"], "kind": v["kind"], "question": v["question"], "options": opts})
    return out

@app.get("/spaces/{sid}/variations")
def variations(sid: int, u=Depends(current_user)):
    c = db(); s = c.execute("SELECT title_id FROM spaces WHERE id=?", (sid,)).fetchone()
    if not s: raise HTTPException(404, "Space not found")
    return unlocked_sets(c, sid, s["title_id"])

@app.get("/spaces/{sid}/polls")
def list_polls(sid: int, u=Depends(current_user)):
    c = db(); out = []
    for p in c.execute("SELECT * FROM polls WHERE space_id=? ORDER BY id", (sid,)).fetchall():
        opts = json.loads(p["options"])
        out.append({"id": p["id"], "question": p["question"], "options": opts, "open": bool(p["open"]), "winner": p["winner"], "tally": tally(c, p["id"], len(opts))})
    return out

@app.post("/spaces/{sid}/polls")
async def open_poll(sid: int, p: NewPoll, u=Depends(current_user)):
    c = db(); s = c.execute("SELECT * FROM spaces WHERE id=?", (sid,)).fetchone()
    if not s or s["host_id"] != u["id"]: raise HTTPException(403, "Only host")
    if c.execute("SELECT 1 AS x FROM polls WHERE space_id=? AND open=1", (sid,)).fetchone(): raise HTTPException(409, "Close the active poll first")
    if p.default_key is not None:
        d = DEFAULT_POLLS.get(p.default_key)
        if not d: raise HTTPException(422, "Unknown default poll")
        question, options, variation_id = d["question"], d["options"], None
    elif p.variation_set_id is not None:
        v = next((x for x in unlocked_sets(c, sid, s["title_id"]) if x["id"] == p.variation_set_id), None)
        if not v: raise HTTPException(403, "Not an approved variation for this title, or its scene has not been reached")
        question, options, variation_id = v["question"], v["options"], v["id"]
    else:
        question = p.question.strip()
        options = [x.strip() for x in p.options]
        if not question or len(question) > 240: raise HTTPException(422, "Enter a poll question (up to 240 characters)")
        if not 2 <= len(options) <= 6: raise HTTPException(422, "A custom poll needs between 2 and 6 options")
        if any(not x or len(x) > 100 for x in options): raise HTTPException(422, "Each option must be 1–100 characters")
        if len({x.casefold() for x in options}) != len(options): raise HTTPException(422, "Poll options must be unique")
        variation_id = None
    cur = c.execute("INSERT INTO polls(space_id,question,options,variation_set_id) VALUES(?,?,?,?)", (sid, question, json.dumps(options), variation_id)); c.commit()
    await hub.publish(sid, {"type": "POLL_OPEN", "payload": {"id": cur.lastrowid, "question": question, "options": options, "kind": "custom" if variation_id is None else v["kind"]}})
    return {"id": cur.lastrowid}

def tally(c, pid, n):
    cnt = Counter(r["option"] for r in c.execute("SELECT option FROM votes WHERE poll_id=?", (pid,)))
    return [cnt.get(i, 0) for i in range(n)]

@app.post("/polls/{pid}/vote")
async def vote(pid: int, v: Vote, u=Depends(current_user)):
    c = db(); p = c.execute("SELECT * FROM polls WHERE id=? AND open=1", (pid,)).fetchone()
    opts = json.loads(p["options"]) if p else []
    if not p or not 0 <= v.option < len(opts): raise HTTPException(400, "Invalid poll/option")
    if not is_member(c, p["space_id"], u["id"]): raise HTTPException(403, "Join the space to vote")
    c.execute("INSERT INTO votes VALUES(?,?,?) ON CONFLICT(poll_id,user_id) DO UPDATE SET option=excluded.option", (pid, u["id"], v.option)); c.commit()
    t = tally(c, pid, len(opts))
    await hub.publish(p["space_id"], {"type": "POLL_VOTE", "payload": {"poll_id": pid, "tally": t}})
    return {"tally": t}

@app.post("/polls/{pid}/close")
async def close_poll(pid: int, u=Depends(current_user)):
    c = db(); p = c.execute("SELECT * FROM polls WHERE id=?", (pid,)).fetchone()
    s = c.execute("SELECT host_id FROM spaces WHERE id=?", (p["space_id"],)).fetchone() if p else None
    if not s or s["host_id"] != u["id"]: raise HTTPException(403, "Only host")
    opts = json.loads(p["options"]); t = tally(c, pid, len(opts))
    win = opts[t.index(max(t))]                          # ties go to the first option
    c.execute("UPDATE polls SET open=0, winner=? WHERE id=?", (win, pid)); c.commit()
    await hub.publish(p["space_id"], {"type": "POLL_RESULT", "payload": {"poll_id": pid, "winner": win, "tally": t}})
    return {"winner": win, "tally": t}

# ---- Recommendations (content-based + collaborative + cold start) ----
class Watch(BaseModel): title_id: int; seconds: int; completed: bool = False
@app.post("/activity/watch")
def log_watch(w: Watch, u=Depends(current_user)):
    if w.title_id not in TITLES: raise HTTPException(404, "Title not found")
    record_watch_event(u["id"], w.title_id, w.seconds, w.completed)
    kv.delete(f"recs:v3:{u['id']}"); return {"ok": True}   # invalidate cached recommendations

def recommend(c, uid, genres):
    """Match % = share of a title's categories that appear in the user's categories
    (categories selected in their profile + categories of titles they have watched).
    No overlap at all -> 1% by default. Ties are broken by what similar viewers watched."""
    seen = {r["title_id"] for r in c.execute("SELECT title_id FROM watch_events WHERE user_id=?", (uid,))}
    mine_cats = {g.strip().lower() for g in genres if g and g.strip()}
    for t in seen:
        if t in TITLES: mine_cats.update(g.lower() for g in TITLES[t]["genres"])
    collab = Counter()
    for row in c.execute("SELECT DISTINCT user_id FROM watch_events WHERE user_id!=?", (uid,)):
        theirs = {r["title_id"] for r in c.execute("SELECT title_id FROM watch_events WHERE user_id=?", (row["user_id"],))}
        if seen & theirs:
            for t in theirs - seen: collab[t] += len(seen & theirs)
    out = []
    for t in TITLES.values():
        if t["id"] in seen: continue
        cats = [g.lower() for g in t["genres"]]
        match = sum(1 for g in cats if g in mine_cats) / len(cats) if cats else 0
        out.append({"title": t["name"], "id": t["id"], "score": round(max(match, 0.01), 3), "personalized": True, "_c": collab[t["id"]]})
    out.sort(key=lambda x: (-x["score"], -x["_c"]))
    for o in out: o.pop("_c")
    return out

@app.get("/recommendations")
def recs(u=Depends(current_user)):
    key = f"recs:v3:{u['id']}"
    if hit := kv.get(key): return json.loads(hit)
    out = recommend(db(), u["id"], u["genres"].split(","))
    kv.set(key, json.dumps(out), ex=600); return out         # 10-minute per-user cache

@app.get("/ratings")
def title_rating_summaries(u=Depends(current_user)):
    c = db()
    rows = c.execute("SELECT title_id,COUNT(*) AS count,AVG(rating) AS average FROM title_reviews GROUP BY title_id").fetchall()
    return {r["title_id"]: {"average": round(r["average"], 1), "count": r["count"]} for r in rows}

# ---- Title detail, profile, history, group recommendations ----
@app.get("/titles/{tid}")
def title_detail(tid: int, u=Depends(current_user)):
    if tid not in TITLES: raise HTTPException(404, "Title not found")
    t = TITLES[tid]; c = db()
    watch_count = c.execute("SELECT COUNT(DISTINCT user_id) AS n FROM watch_events WHERE title_id=? AND completed=1", (tid,)).fetchone()["n"]
    watched = bool(c.execute("SELECT 1 FROM watch_events WHERE title_id=? AND user_id=? AND completed=1 LIMIT 1", (tid, u["id"])).fetchone())
    return {k: t[k] for k in ("id", "name", "genres", "video")} | {"added_by": t["added_by"], "added_by_name": owner_name(c, t["added_by"]), "scene_count": len(t["scenes"]), "watch_count": watch_count, "watched_by_me": watched}   # no scene text: spoiler-free

class ReviewInput(BaseModel):
    rating: float = Field(ge=0.5, le=10)
    headline: str = Field(default="", max_length=120)
    body: str = Field(min_length=1, max_length=5000)

class CommentInput(BaseModel):
    body: str = Field(min_length=1, max_length=1500)

@app.get("/titles/{tid}/reviews")
def title_reviews(tid: int, u=Depends(current_user)):
    if tid not in TITLES: raise HTTPException(404, "Title not found")
    c = db()
    summary = c.execute("SELECT COUNT(*) AS count, AVG(rating) AS average, SUM(CASE WHEN rating >= 6 THEN 1 ELSE 0 END) AS positive FROM title_reviews WHERE title_id=?", (tid,)).fetchone()
    rows = c.execute("SELECT r.id,r.user_id,u.name AS author,r.rating,r.headline,r.body,r.created_at,r.updated_at,(SELECT COUNT(*) FROM review_comments c WHERE c.review_id=r.id) AS comment_count FROM title_reviews r JOIN users u ON u.id=r.user_id WHERE r.title_id=? ORDER BY r.updated_at DESC LIMIT 50", (tid,)).fetchall()
    mine = c.execute("SELECT id,rating,headline,body FROM title_reviews WHERE title_id=? AND user_id=?", (tid, u["id"])).fetchone()
    count = summary["count"]
    return {"count": count, "average": round(summary["average"], 1) if count else None, "positive_percent": round(summary["positive"] * 100 / count) if count else None, "mine": dict(mine) if mine else None, "reviews": [dict(r) for r in rows]}

@app.post("/titles/{tid}/reviews")
def save_title_review(tid: int, item: ReviewInput, u=Depends(current_user)):
    if tid not in TITLES: raise HTTPException(404, "Title not found")
    body = item.body.strip()
    if not body: raise HTTPException(422, "Review text is required")
    now = time.time(); c = db()
    c.execute("INSERT INTO title_reviews(title_id,user_id,rating,headline,body,created_at,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(title_id,user_id) DO UPDATE SET rating=excluded.rating,headline=excluded.headline,body=excluded.body,updated_at=excluded.updated_at", (tid, u["id"], item.rating, item.headline.strip(), body, now, now)); c.commit()
    row = c.execute("SELECT id FROM title_reviews WHERE title_id=? AND user_id=?", (tid, u["id"])).fetchone()
    return {"id": row["id"], "ok": True}

@app.get("/reviews/{rid}/comments")
def review_comments(rid: int, u=Depends(current_user)):
    c = db()
    if not c.execute("SELECT 1 FROM title_reviews WHERE id=?", (rid,)).fetchone(): raise HTTPException(404, "Review not found")
    return [dict(r) for r in c.execute("SELECT c.id,c.user_id,u.name AS author,c.body,c.created_at FROM review_comments c JOIN users u ON u.id=c.user_id WHERE c.review_id=? ORDER BY c.created_at", (rid,)).fetchall()]

@app.post("/reviews/{rid}/comments")
def add_review_comment(rid: int, item: CommentInput, u=Depends(current_user)):
    body = item.body.strip()
    if not body: raise HTTPException(422, "Comment text is required")
    c = db()
    if not c.execute("SELECT 1 FROM title_reviews WHERE id=?", (rid,)).fetchone(): raise HTTPException(404, "Review not found")
    cur = c.execute("INSERT INTO review_comments(review_id,user_id,body,created_at) VALUES(?,?,?,?)", (rid,u["id"],body,time.time())); c.commit()
    return {"id": cur.lastrowid, "ok": True}

class Profile(BaseModel): name: str; genres: list[str] = []
@app.put("/me")
def update_me(p: Profile, u=Depends(current_user)):
    c = db(); c.execute("UPDATE users SET name=?, genres=? WHERE id=?", (p.name.strip()[:40] or u["name"], ",".join(p.genres), u["id"])); c.commit()
    kv.delete(f"recs:v3:{u['id']}"); return {"ok": True}

@app.get("/me/history")
def history(u=Depends(current_user)):
    rows = db().execute("SELECT t.name AS title,SUM(w.seconds) AS seconds,MAX(w.completed) AS completed,MAX(w.watched_at) AS watched_at "
                        "FROM watch_events w JOIN titles t ON t.id=w.title_id WHERE w.user_id=? "
                        "GROUP BY t.id,t.name ORDER BY MAX(w.watched_at) DESC", (u["id"],)).fetchall()
    return [{"title": r["title"], "seconds": r["seconds"] or 0, "completed": bool(r["completed"])} for r in rows]

@app.get("/spaces/{sid}/recommendations")
def group_recs(sid: int, u=Depends(current_user)):
    """Titles nobody in the room has seen, ranked by the average personal score of everyone currently connected."""
    ids = sorted(int(x) for x in kv.smembers(f"space:{sid}:uids")) or [u["id"]]
    c = db(); per = []
    for i in ids:
        row = c.execute("SELECT genres FROM users WHERE id=?", (i,)).fetchone()
        per.append({r["id"]: r for r in recommend(c, i, row["genres"].split(","))})
    common = set.intersection(*[set(p) for p in per])
    out = [{"id": t, "title": per[0][t]["title"], "score": round(sum(p[t]["score"] for p in per) / len(per), 3)} for t in common]
    return sorted(out, key=lambda x: -x["score"])

# ---- WebSocket: /ws/spaces/{id}?token=JWT ----
_listener = None
@app.on_event("startup")
async def _start():
    global _listener
    if kv.use_redis(): _listener = asyncio.create_task(hub.listen())
@app.on_event("shutdown")
async def _stop():
    if _listener: _listener.cancel()

def get_state(sid):
    return json.loads(kv.get(f"space:{sid}:state") or "null") or {"position": 0.0, "playing": False, "server_ts": time.time()}
def put_state(sid, st): kv.set(f"space:{sid}:state", json.dumps(st), ex=86400)

@app.websocket("/ws/spaces/{sid}")
async def ws_space(ws: WebSocket, sid: int, token: str):
    try: uid = decode(token)
    except HTTPException: await ws.close(4401); return
    c = db(); s = c.execute("SELECT * FROM spaces WHERE id=?", (sid,)).fetchone()
    u = c.execute("SELECT name FROM users WHERE id=?", (uid,)).fetchone()
    if not s or not u: await ws.close(4404); return
    if not is_member(c, sid, uid): await ws.close(4403); return      # must have joined via /spaces/join
    await ws.accept()
    hub.rooms.setdefault(sid, {})[ws] = {"id": uid, "name": u["name"]}
    kv.sadd(f"space:{sid}:online", u["name"]); kv.sadd(f"space:{sid}:uids", str(uid))
    st = get_state(sid); ann = Announced(sid)
    await ws.send_json({"type": "SYNC_STATE", "payload": {**st, "expected": expected_position(st)}, "server_ts": time.time()})
    await hub.publish(sid, {"type": "PRESENCE_JOIN", "payload": {"user": u["name"], "online": sorted(kv.smembers(f"space:{sid}:online"))}})

    async def trivia(st):
        if st["playing"] and (tv := pick_trivia(ann, s["title_id"], st["position"])):
            await hub.publish(sid, {"type": "AI_TRIVIA", "payload": tv})
    try:
        while True:
            m = await ws.receive_json(); t = m.get("type"); p = m.get("payload", {})
            if t in ("PLAY", "PAUSE", "SEEK"):
                st = get_state(sid)
                st.update(position=float(p.get("position", st["position"])), playing=(t == "PLAY" or (t == "SEEK" and st["playing"])), server_ts=time.time())
                put_state(sid, st); await hub.publish(sid, {"type": t, "payload": {**dict(st), "user_id": uid}}); await trivia(st)
            elif t == "TIME_UPDATE" and uid == s["host_id"]:       # host heartbeat: detects scene changes
                st = get_state(sid); st.update(position=float(p.get("position", st["position"])), server_ts=time.time())
                put_state(sid, st); await trivia(st)
            elif t == "FULLSCREEN":
                await hub.publish(sid, {"type": t, "payload": {"user_id": uid, "user": u["name"], "active": bool(p.get("active"))}})
            elif t == "CHAT_MESSAGE":
                text = str(p.get("text", ""))[:500]
                ts = time.time()
                c.execute("INSERT INTO chat VALUES(?,?,?,?,?)", (sid, uid, u["name"], text, ts)); c.commit()
                await hub.publish(sid, {"type": "CHAT_MESSAGE", "payload": {"user_id": uid, "user": u["name"], "text": text, "ts": ts}})
            elif t == "REACTION": await hub.publish(sid, {"type": "REACTION", "payload": {"user": u["name"], "emoji": str(p.get("emoji", ""))[:4]}})
            elif t == "PING": await ws.send_json({"type": "PONG", "payload": {}, "server_ts": time.time()})
    except WebSocketDisconnect:
        hub.rooms[sid].pop(ws, None); kv.srem(f"space:{sid}:online", u["name"]); kv.srem(f"space:{sid}:uids", str(uid))
        await hub.publish(sid, {"type": "PRESENCE_LEAVE", "payload": {"user": u["name"]}})
