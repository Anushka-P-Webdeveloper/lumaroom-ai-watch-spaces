"""Redis wrapper (cache, rate limits, live room state, presence, pub/sub) with an in-memory fallback."""
import asyncio, builtins, os, time
_S = builtins.set   # module defines set(); keep the builtin reachable
try:
    import redis, redis.asyncio as aredis
except ImportError:
    redis = aredis = None

def use_redis(): return bool(os.getenv("REDIS_URL")) and redis is not None

class _Mem:
    def __init__(s): s.d, s.sets = {}, {}
    def _live(s, k):
        v = s.d.get(k)
        if v and v[1] and v[1] < time.time(): s.d.pop(k); return None
        return v
    def get(s, k): v = s._live(k); return v[0] if v else None
    def set(s, k, v, ex=None): s.d[k] = (v, time.time() + ex if ex else 0)
    def delete(s, *ks):
        for k in ks: s.d.pop(k, None); s.sets.pop(k, None)
    def incr(s, k, ex=60):
        v = s._live(k); n = (int(v[0]) if v else 0) + 1; s.d[k] = (n, v[1] if v else time.time() + ex); return n
    def sadd(s, k, m): st = s.sets.setdefault(k, _S()); new = m not in st; st.add(m); return int(new)
    def srem(s, k, m): s.sets.get(k, _S()).discard(m)
    def sismember(s, k, m): return m in s.sets.get(k, _S())
    def smembers(s, k): return _S(s.sets.get(k, _S()))

_c = None
def client():
    global _c
    if _c is None: _c = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True) if use_redis() else _Mem()
    return _c

def get(k): return client().get(k)
def set(k, v, ex=None): client().set(k, v, ex=ex)
def delete(*ks): client().delete(*ks)
def sadd(k, m): return client().sadd(k, m)
def srem(k, m): client().srem(k, m)
def sismember(k, m): return bool(client().sismember(k, m))
def smembers(k): return _S(client().smembers(k))
def incr(k, ex=60):
    c = client()
    if isinstance(c, _Mem): return c.incr(k, ex)
    n = c.incr(k)
    if n == 1: c.expire(k, ex)
    return n

_apubs = {}
def apub():
    """Async client (one per event loop) used for publish/subscribe."""
    loop = id(asyncio.get_running_loop())
    if loop not in _apubs: _apubs[loop] = aredis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    return _apubs[loop]
