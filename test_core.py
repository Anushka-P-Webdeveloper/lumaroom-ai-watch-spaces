import os, time
from fastapi.testclient import TestClient
from main import app, expected_position, drift_action, retrieve

def test_sync_math():
    st = {"position": 10, "playing": True, "server_ts": 100}
    assert expected_position(st, now=105) == 15
    assert drift_action(20, 15)[0] == "seek" and drift_action(15.5, 15)[0] == "rate"

def test_spoiler_filter():
    assert retrieve(1, 10, "rodents revenge") == []   # scene 2 not reached yet
    assert retrieve(1, 100, "rodents revenge")

def test_one_vote_and_host_flow(client):
    c = client
    h = {"Authorization": "Bearer " + c.post("/auth/register", json={"email": "a@x.com", "name": "A", "password": "p"}).json()["token"]}
    h2 = {"Authorization": "Bearer " + c.post("/auth/register", json={"email": "b@x.com", "name": "B", "password": "p"}).json()["token"]}
    sp = c.post("/spaces", json={"name": "Room", "title_id": 1}, headers=h).json()
    c.post("/spaces/join", json={"code": sp["code"]}, headers=h2)
    loc = next(v for v in c.get(f"/spaces/{sp['id']}/variations", headers=h).json() if v["kind"] == "localization")
    pid = c.post(f"/spaces/{sp['id']}/polls", json={"variation_set_id": loc["id"]}, headers=h).json()["id"]
    c.post(f"/polls/{pid}/vote", json={"option": 0}, headers=h2)
    r = c.post(f"/polls/{pid}/vote", json={"option": 1}, headers=h2).json()
    assert sum(r["tally"]) == 1                                   # changed vote, not a second vote
    assert c.post(f"/polls/{pid}/close", headers=h2).status_code == 403
    with c.websocket_connect(f"/ws/spaces/{sp['id']}?token={h2['Authorization'][7:]}") as ws:
        assert ws.receive_json()["type"] == "SYNC_STATE"; ws.receive_json()
        ws.send_json({"type": "PLAY", "payload": {"position": 5}})
        assert ws.receive_json()["type"] == "ERROR"                # non-host blocked

def test_trivia_once_per_scene():
    from main import pick_trivia
    seen = set()
    assert pick_trivia(seen, 1, 10)["scene_id"] == "bbb1"
    assert pick_trivia(seen, 1, 20) is None                      # same scene: deduplicated
    assert pick_trivia(seen, 1, 70)["scene_id"] == "bbb2"        # new scene: fires again
    assert pick_trivia(set(), 1, 9999) is None                   # past the end: nothing

def test_trivia_broadcast_over_ws(client):
    c = client
    tk = c.post("/auth/register", json={"email": "h@x.com", "name": "H", "password": "p"}).json()["token"]
    sp = c.post("/spaces", json={"name": "R", "title_id": 1}, headers={"Authorization": "Bearer " + tk}).json()
    with c.websocket_connect(f"/ws/spaces/{sp['id']}?token={tk}") as ws:
        ws.receive_json(); ws.receive_json()
        ws.send_json({"type": "PLAY", "payload": {"position": 5}})
        assert ws.receive_json()["type"] == "PLAY"
        assert ws.receive_json()["type"] == "AI_TRIVIA"

def test_profile_and_group_recs(client):
    c = client; tk = {}
    for n, g in (("p1", ["animation"]), ("p2", ["sci-fi"])):
        tk[n] = c.post("/auth/register", json={"email": f"{n}@x.com", "name": n, "password": "p", "genres": g}).json()["token"]
    H = lambda n: {"Authorization": "Bearer " + tk[n]}
    assert c.put("/me", json={"name": "Pat", "genres": ["animation"]}, headers=H("p1")).json()["ok"]
    assert c.get("/me", headers=H("p1")).json()["name"] == "Pat"
    assert c.get("/titles/99").status_code == 404 and "scenes" not in c.get("/titles/1").json()
    sp = c.post("/spaces", json={"name": "G", "title_id": 1}, headers=H("p1")).json()
    c.post("/spaces/join", json={"code": sp["code"]}, headers=H("p2"))
    with c.websocket_connect(f"/ws/spaces/{sp['id']}?token={tk['p1']}"), c.websocket_connect(f"/ws/spaces/{sp['id']}?token={tk['p2']}"):
        r = c.get(f"/spaces/{sp['id']}/recommendations", headers=H("p1")).json()
    assert len(r) == 3 and r == sorted(r, key=lambda x: -x["score"])
    c.post("/activity/watch", json={"title_id": 1, "seconds": 600, "completed": True}, headers=H("p1"))
    assert c.get("/me/history", headers=H("p1")).json()[0]["title"] == "Big Buck Bunny"

def test_variations_preapproved_only_and_spoiler_gated(client):
    import time, main
    c = client; tk = c.post("/auth/register", json={"email": "v@x.com", "name": "V", "password": "p"}).json()["token"]; h = {"Authorization": "Bearer " + tk}
    sp = c.post("/spaces", json={"name": "V", "title_id": 1}, headers=h).json()
    kinds = {v["kind"] for v in c.get(f"/spaces/{sp['id']}/variations", headers=h).json()}
    assert kinds == {"localization"}                                          # narrative set (scene bbb2) still locked at t=0
    assert c.post(f"/spaces/{sp['id']}/polls", json={"question": "free", "options": ["a", "b"]}, headers=h).status_code == 422   # free-form rejected
    main.put_state(sp["id"], {"position": 100.0, "playing": False, "server_ts": time.time()})
    sets = c.get(f"/spaces/{sp['id']}/variations", headers=h).json()
    nar = next(v for v in sets if v["kind"] == "narrative"); assert len(nar["options"]) == 3
    assert c.post(f"/spaces/{sp['id']}/polls", json={"variation_set_id": 999}, headers=h).status_code == 403
    pid = c.post(f"/spaces/{sp['id']}/polls", json={"variation_set_id": nar["id"]}, headers=h).json()["id"]
    assert c.post(f"/spaces/{sp['id']}/polls", json={"variation_set_id": nar["id"]}, headers=h).status_code == 409   # one active poll at a time
    c.post(f"/polls/{pid}/vote", json={"option": 2}, headers=h)
    assert c.post(f"/polls/{pid}/close", headers=h).json()["winner"] == nar["options"][2]
    done = c.get(f"/spaces/{sp['id']}/polls", headers=h).json()[0]
    assert done["winner"] == nar["options"][2] and not done["open"]           # winner persisted

def test_membership_required_for_voting_and_ws(client):
    import pytest
    from starlette.websockets import WebSocketDisconnect
    c = client; reg = lambda e: c.post("/auth/register", json={"email": e, "name": e, "password": "p"}).json()["token"]
    ho, out = reg("mh@x.com"), reg("mo@x.com"); H = lambda t: {"Authorization": "Bearer " + t}
    sp = c.post("/spaces", json={"name": "M", "title_id": 1}, headers=H(ho)).json()
    loc = next(v for v in c.get(f"/spaces/{sp['id']}/variations", headers=H(ho)).json() if v["kind"] == "localization")
    pid = c.post(f"/spaces/{sp['id']}/polls", json={"variation_set_id": loc["id"]}, headers=H(ho)).json()["id"]
    assert c.post(f"/polls/{pid}/vote", json={"option": 0}, headers=H(out)).status_code == 403     # outsider cannot vote
    with pytest.raises(WebSocketDisconnect): c.websocket_connect(f"/ws/spaces/{sp['id']}?token={out}").__enter__()
    c.post("/spaces/join", json={"code": sp["code"]}, headers=H(out))
    assert c.post(f"/polls/{pid}/vote", json={"option": 0}, headers=H(out)).status_code == 200      # joined => allowed
