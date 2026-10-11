import { useEffect, useRef, useState, useCallback } from "react";

const API = (import.meta as any).env.VITE_API || "http://localhost:8000";
const WS = API.replace(/^http/, "ws");
type Title = {
  id: number;
  name: string;
  genres: string[];
  video: string;
  added_by?: number | null;
};
type SpaceT = {
  id: number;
  code: string;
  name: string;
  title_id: number;
  host_id: number;
  host_name?: string | null;
};
type User = { id: number; name: string; genres?: string };
type Rec = { id: number; title: string; score: number; personalized?: boolean };
type RatingSummary = { average: number; count: number };
type ReviewComment = {
  id: number;
  author: string;
  body: string;
  created_at: number;
};
type Review = {
  id: number;
  user_id: number;
  author: string;
  rating: number;
  headline: string;
  body: string;
  created_at: number;
  updated_at: number;
  comment_count: number;
};
type ReviewData = {
  count: number;
  average: number | null;
  positive_percent: number | null;
  mine: { id: number; rating: number; headline: string; body: string } | null;
  reviews: Review[];
};
const PREFERENCES = [
  {
    label: "Languages",
    values: ["Hindi", "Marathi", "English", "Tamil", "Telugu"],
  },
  {
    label: "Film industries",
    values: ["Bollywood", "Hollywood", "Marathi cinema", "South Indian Films"],
  },
  { label: "Format", values: ["Movies", "Series"] },
  {
    label: "Genres",
    values: [
      "Action",
      "Comedy",
      "Romance",
      "Drama",
      "Sci-fi",
      "Thriller",
      "Horror",
      "Animation",
      "Documentary",
      "Family",
    ],
  },
];
const preferenceKey = (s: string) => s.toLocaleLowerCase();
const youtubeSearch = (taste: string) => {
  const q = taste.toLocaleLowerCase();
  const source = q.includes("marathi")
    ? "EverestTalkies official full movie"
    : q.includes("bollywood") || q.includes("hindi")
      ? "Shemaroo Rajshri official full movie"
      : q.includes("series")
        ? "FilmRise full episodes official"
        : q.includes("hollywood") || q.includes("english")
          ? "FilmRise full movie official"
          : `official free full ${taste} movie`;
  return `https://www.youtube.com/results?search_query=${encodeURIComponent(source + " " + taste)}`;
};

function youtubeId(url: string) {
  try {
    const u = new URL(url);
    if (u.hostname.endsWith("youtu.be")) return u.pathname.slice(1);
    if (u.hostname.includes("youtube.com")) {
      const parts = u.pathname.split("/").filter(Boolean);
      return u.searchParams.get("v") || parts[parts.length - 1] || "";
    }
  } catch {
    /* not a URL */
  }
  return url;
}
const poster = (url: string) =>
  `https://img.youtube.com/vi/${youtubeId(url)}/hqdefault.jpg`;

type MediaHandle = {
  getCurrentTime: () => number;
  isPlaying: () => boolean;
  play: () => void;
  pause: () => void;
  seek: (s: number) => void;
  setRate: (r: number) => void;
  suppress: () => void;
};
type YTPlayer = {
  getCurrentTime: () => number;
  getPlayerState: () => number;
  playVideo: () => void;
  pauseVideo: () => void;
  seekTo: (s: number, allow: boolean) => void;
  setPlaybackRate: (r: number) => void;
  destroy: () => void;
};
declare global {
  interface Window {
    YT?: { Player: new (id: string, opts: any) => YTPlayer };
    onYouTubeIframeAPIReady?: () => void;
  }
}
let youtubeApi: Promise<void> | null = null;
function loadYouTubeApi() {
  if (window.YT?.Player) return Promise.resolve();
  if (!youtubeApi)
    youtubeApi = new Promise((resolve) => {
      window.onYouTubeIframeAPIReady = () => resolve();
      if (
        !document.querySelector(
          'script[src="https://www.youtube.com/iframe_api"]'
        )
      ) {
        const script = document.createElement("script");
        script.src = "https://www.youtube.com/iframe_api";
        document.head.appendChild(script);
      }
    });
  return youtubeApi;
}
if (typeof window !== "undefined") loadYouTubeApi(); // warm up the player API so the theatre opens faster

function YouTubePlayer({
  src,
  host,
  onReady,
  onAction,
  notify,
  onEmbedDisabled,
}: {
  src: string;
  host: boolean;
  onReady: (p: MediaHandle) => void;
  onAction: (type: string, position: number) => void;
  notify: (m: string) => void;
  onEmbedDisabled: () => void;
}) {
  const id = useRef(`yt-${Math.random().toString(36).slice(2)}`);
  const player = useRef<YTPlayer | null>(null);
  const mutedUntil = useRef(0);
  const expectedState = useRef<number | null>(null);
  const callbacks = useRef({ onAction, notify, onEmbedDisabled });
  callbacks.current = { onAction, notify, onEmbedDisabled };
  const embedErrorReported = useRef(false);
  useEffect(() => {
    let cancelled = false,
      previous = 0,
      timer = 0;
    loadYouTubeApi()
      .then(() => {
        if (cancelled || !window.YT?.Player) return;
        const p = new window.YT.Player(id.current, {
          playerVars: {
            autoplay: 0,
            controls: 1,
            fs: 0,
            disablekb: 0,
            modestbranding: 1,
            rel: 0,
            playsinline: 1,
            origin: location.origin,
          },
          events: {
            onReady: () => {
              const handle: MediaHandle = {
                getCurrentTime: () => p.getCurrentTime() || 0,
                isPlaying: () => p.getPlayerState() === 1,
                play: () => {
                  expectedState.current = 1;
                  p.playVideo();
                },
                pause: () => {
                  expectedState.current = 2;
                  p.pauseVideo();
                },
                seek: (s) => {
                  expectedState.current = null;
                  mutedUntil.current = Date.now() + 1800;
                  p.seekTo(s, true);
                },
                setRate: (r) => {
                  try {
                    p.setPlaybackRate(r);
                  } catch {
                    /* player may not support rate yet */
                  }
                },
                suppress: () => {
                  mutedUntil.current = Date.now() + 1800;
                },
              };
              onReady(handle);
              timer = window.setInterval(() => {
                if (cancelled || p.getPlayerState() !== 1) return;
                const now = p.getCurrentTime() || 0;
                if (
                  previous &&
                  Math.abs(now - previous) > 2.5 &&
                  Date.now() > mutedUntil.current
                )
                  callbacks.current.onAction("SEEK", now);
                previous = now;
              }, 700);
            },
            onStateChange: (e: { data: number }) => {
              if (e.data !== 1 && e.data !== 2) return;
              if (
                Date.now() < mutedUntil.current &&
                expectedState.current === e.data
              ) {
                expectedState.current = null;
                return;
              }
              expectedState.current = null;
              callbacks.current.onAction(
                e.data === 1 ? "PLAY" : "PAUSE",
                p.getCurrentTime() || 0
              );
            },
            onError: (e: { data: number }) => {
              if (e.data === 101 || e.data === 150) {
                if (!embedErrorReported.current) {
                  embedErrorReported.current = true;
                  callbacks.current.onEmbedDisabled();
                }
                return;
              }
              callbacks.current.notify(
                `YouTube player error ${e.data}; open the video on YouTube if it is unavailable here.`
              );
            },
          },
        });
        player.current = p;
      })
      .catch(() =>
        callbacks.current.notify("YouTube player could not be loaded")
      );
    return () => {
      cancelled = true;
      window.clearInterval(timer);
      player.current = null; // iframe is owned by React; destroy() would remove it from under React
    };
  }, [src, host, onReady]);
  const embed = new URL(`https://www.youtube.com/embed/${youtubeId(src)}`);
  embed.searchParams.set("enablejsapi", "1");
  embed.searchParams.set("origin", location.origin);
  embed.searchParams.set("fs", "0");
  return (
    <div className="youtube-frame">
      <iframe
        id={id.current}
        src={embed.toString()}
        title="Watch together"
        referrerPolicy="origin"
        allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
        allowFullScreen
      />
    </div>
  );
}

let token = localStorage.getItem("token") || "";
async function api<T = any>(
  path: string,
  method = "GET",
  body?: unknown
): Promise<T> {
  const r = await fetch(API + path, {
    method,
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer " + token,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.detail || "Request failed");
  return j;
}

export default function App() {
  const [me, setMe] = useState<User | null>(null);
  const [space, setSpace] = useState<SpaceT | null>(null);
  const [view, setView] = useState<{ page: string; id?: number }>({
    page: "home",
  });
  const [toast, setToast] = useState("");
  const [titles, setTitles] = useState<Title[]>([]);
  const [historyRevision, setHistoryRevision] = useState(0);
  const notify = useCallback((m: string) => {
    setToast(m);
    setTimeout(() => setToast(""), 3000);
  }, []);
  const refreshHistory = useCallback(
    () => setHistoryRevision((value) => value + 1),
    []
  );

  useEffect(() => {
    if (token)
      api("/me")
        .then(setMe)
        .catch(() => {
          token = "";
          localStorage.removeItem("token");
        });
    api("/titles")
      .then(setTitles)
      .catch(() => notify("Backend not reachable"));
  }, [notify]);

  const logout = () => {
    token = "";
    localStorage.removeItem("token");
    setMe(null);
    setSpace(null);
  };
  return (
    <>
      <div className="curtain curtain-left" aria-hidden="true" />
      <div className="curtain curtain-right" aria-hidden="true" />
      <div className="stage-lights" aria-hidden="true" />

      <nav>
        <span className="logo">LUMAROOM</span>
        {me && (
          <span>
            <button
              className="ghost"
              onClick={() => {
                setSpace(null);
                setView({ page: "home" });
              }}
            >
              Home
            </button>
            <button
              className="ghost"
              onClick={() => {
                setSpace(null);
                setView({ page: "profile" });
              }}
            >
              {me.name}
            </button>
            <button className="ghost" onClick={logout}>
              Logout
            </button>
          </span>
        )}
      </nav>

      {!me ? (
        <Auth onAuth={setMe} notify={notify} />
      ) : space && titles.some((t) => t.id === space.title_id) ? (
        <Space
          me={me}
          space={space}
          title={titles.find((t) => t.id === space.title_id)!}
          onLeave={() => setSpace(null)}
          notify={notify}
          onHistoryUpdated={refreshHistory}
          onEmbedDisabled={() => {
            setTitles((current) =>
              current.filter((t) => t.id !== space.title_id)
            );
            setSpace(null);
            setView({ page: "home" });
          }}
        />
      ) : view.page === "title" ? (
        <TitleDetail
          id={view.id!}
          meId={me.id}
          onChanged={(t, tid) => {
            if (t) setTitles((cur) => cur.map((x) => (x.id === tid ? t : x)));
            else {
              setTitles((cur) => cur.filter((x) => x.id !== tid));
              setView({ page: "home" });
            }
          }}
          onEnter={setSpace}
          onBack={() => setView({ page: "home" })}
          notify={notify}
        />
      ) : view.page === "profile" ? (
        <ProfilePage
          me={me}
          onSaved={setMe}
          historyRevision={historyRevision}
          notify={notify}
        />
      ) : (
        <Home
          me={me}
          titles={titles}
          preferences={(me.genres || "").split(",").filter(Boolean)}
          onEnter={setSpace}
          onOpen={(id) => setView({ page: "title", id })}
          onTitleAdded={(t) => setTitles((current) => [...current, t])}
          notify={notify}
        />
      )}
      {toast && <div className="toast">{toast}</div>}
    </>
  );
}

function Auth({
  onAuth,
  notify,
}: {
  onAuth: (u: User) => void;
  notify: (m: string) => void;
}) {
  const [reg, setReg] = useState(false);
  const [f, setF] = useState({ email: "", name: "", password: "" });
  const [genres, setGenres] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (busy) return;
    if (!f.email || !f.password) {
      notify("Enter your email and password.");
      return;
    }
    if (reg && !f.name.trim()) {
      notify("Enter a display name.");
      return;
    }
    try {
      setBusy(true);
      const body = reg
        ? { email: f.email, name: f.name, password: f.password, genres }
        : { email: f.email, password: f.password };
      const { token: t } = await api(
        reg ? "/auth/register" : "/auth/login",
        "POST",
        body
      );
      token = t;
      localStorage.setItem("token", t);
      onAuth(await api("/me"));
    } catch (e: any) {
      notify(e.message);
    } finally {
      setBusy(false);
    }
  };
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setF({ ...f, [k]: e.target.value });
  return (
    <div className="auth-stage">
      <div
        className={`auth-card ${reg ? "flipped auth-register" : "auth-login"}`}
      >
        {/* ---- SIGN IN: only email + password ---- */}
        <div className="auth-face auth-front">
          <span className="eyebrow">ADMIT ONE</span>
          <h2>Sign in</h2>
          <p className="auth-tag">Return to your private screening room.</p>
          <input
            type="email"
            placeholder="Email"
            autoComplete="email"
            value={f.email}
            onChange={set("email")}
          />
          <input
            type="password"
            placeholder="Password"
            autoComplete="current-password"
            value={f.password}
            onChange={set("password")}
            onKeyDown={(e) => e.key === "Enter" && submit()}
          />
          <div className="auth-actions">
            <button className="auth-primary" disabled={busy} onClick={submit}>
              {busy ? "Signing in…" : "Sign in"}
            </button>
            <button
              className="ghost auth-switch"
              type="button"
              onClick={() => setReg(true)}
            >
              New here? Create an account →
            </button>
          </div>
        </div>

        {/* ---- REGISTER: side-by-side so nothing needs to scroll ---- */}
        <div className="auth-face auth-back">
          <div className="auth-register-grid">
            <div className="auth-register-form">
              <span className="eyebrow">NEW GUEST</span>
              <h2>Create account</h2>
              <p className="auth-tag">
                Pick what you love. We'll seat you accordingly.
              </p>
              <input
                type="email"
                placeholder="Email"
                autoComplete="email"
                value={f.email}
                onChange={set("email")}
              />
              <input
                placeholder="Display name"
                autoComplete="name"
                value={f.name}
                onChange={set("name")}
              />
              <input
                type="password"
                placeholder="Password"
                autoComplete="new-password"
                value={f.password}
                onChange={set("password")}
              />
            </div>
            <div className="auth-register-prefs">
              <PreferencesPicker
                value={genres}
                onChange={setGenres}
                title="What do you like to watch?"
              />
            </div>
          </div>
          <div className="auth-actions">
            <button className="auth-primary" disabled={busy} onClick={submit}>
              {busy ? "Creating…" : "Create your account"}
            </button>
            <button
              className="ghost auth-switch"
              type="button"
              onClick={() => setReg(false)}
            >
              ← Have an account? Sign in
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function PreferencesPicker({
  value,
  onChange,
  title,
}: {
  value: string[];
  onChange: (items: string[]) => void;
  title: string;
}) {
  const selected = new Set(value.map(preferenceKey));
  const toggle = (item: string) =>
    onChange(
      selected.has(preferenceKey(item))
        ? value.filter((x) => preferenceKey(x) !== preferenceKey(item))
        : [...value, preferenceKey(item)]
    );
  return (
    <section className="preferences">
      <b>{title}</b>
      <small>Pick any that fit. We'll use them to personalize your feed.</small>
      {PREFERENCES.map((group) => (
        <div className="preference-group" key={group.label}>
          <span>{group.label}</span>
          <div>
            {group.values.map((item) => (
              <button
                type="button"
                key={item}
                className={`preference-chip ${selected.has(preferenceKey(item)) ? "selected" : ""}`}
                aria-pressed={selected.has(preferenceKey(item))}
                onClick={() => toggle(item)}
              >
                {item}
              </button>
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}

function Home({
  me,
  titles,
  preferences,
  onEnter,
  onOpen,
  onTitleAdded,
  notify,
}: {
  me: User;
  titles: Title[];
  preferences: string[];
  onEnter: (s: SpaceT) => void;
  onOpen: (id: number) => void;
  onTitleAdded: (title: Title) => void;
  notify: (m: string) => void;
}) {
  const [recs, setRecs] = useState<Rec[]>([]);
  const [ratings, setRatings] = useState<Record<number, RatingSummary>>({});
  const [lobby, setLobby] = useState<SpaceT[]>([]);
  const [code, setCode] = useState("");
  const [sel, setSel] = useState(0);
  const [name, setName] = useState("Movie night");
  const [taste, setTaste] = useState("");
  const [videoName, setVideoName] = useState("");
  const [videoUrl, setVideoUrl] = useState("");
  const [videoTags, setVideoTags] = useState<string[]>([]);
  const [addingVideo, setAddingVideo] = useState(false);
  const load = () => {
    api("/recommendations")
      .then(setRecs)
      .catch(() => {});
    api("/spaces")
      .then(setLobby)
      .catch(() => {});
    api("/ratings")
      .then(setRatings)
      .catch(() => {});
  };
  useEffect(load, []);
  useEffect(() => setTaste(""), [preferences.join(",")]);
  const recommendationTastes = new Set(
    [...preferences, ...(taste ? [taste] : [])].map(preferenceKey)
  );
  const visibleRecs = recs.filter((r) => {
    const activeTastes = taste
      ? new Set([preferenceKey(taste)])
      : recommendationTastes;
    if (!activeTastes.size) return true;
    const t = titles.find((x) => x.id === r.id);
    return t?.genres.some((g) => activeTastes.has(preferenceKey(g)));
  });
  const visibleTitles = taste
    ? titles.filter((t) =>
        t.genres.some((g) => preferenceKey(g) === preferenceKey(taste))
      )
    : titles;
  const visibleLobby = lobby.filter((s) =>
    titles.some((t) => t.id === s.title_id)
  );
  const topRated = [...visibleRecs]
    .filter((r) => (ratings[r.id]?.count || 0) > 0)
    .sort(
      (a, b) =>
        (ratings[b.id]?.average || 0) - (ratings[a.id]?.average || 0) ||
        (ratings[b.id]?.count || 0) - (ratings[a.id]?.count || 0) ||
        b.score - a.score
    )[0];
  // Featured = best rated by the most people, computed from real ratings across the whole catalog.
  // Weighted (Bayesian) average so one lone 10/10 can't beat a title many people rated highly.
  const featured = (() => {
    const rated = titles.filter((t) => (ratings[t.id]?.count || 0) > 0);
    if (!rated.length) return null;
    const m = 3; // prior weight: votes needed before a title's own average dominates
    const globalAvg =
      rated.reduce(
        (a, t) => a + ratings[t.id].average * ratings[t.id].count,
        0
      ) / rated.reduce((a, t) => a + ratings[t.id].count, 0);
    const weighted = (id: number) =>
      (ratings[id].count * ratings[id].average + m * globalAvg) /
      (ratings[id].count + m);
    return [...rated].sort(
      (a, b) =>
        weighted(b.id) - weighted(a.id) ||
        ratings[b.id].count - ratings[a.id].count
    )[0];
  })();
  const selId = titles.some((t) => t.id === sel) ? sel : (titles[0]?.id ?? 0);
  const join = async (c: string) => {
    try {
      onEnter(await api("/spaces/join", "POST", { code: c }));
    } catch (e: any) {
      notify(e.message);
    }
  };
  const create = async () => {
    try {
      const s = await api("/spaces", "POST", {
        name: name.trim() || "Movie night",
        title_id: selId,
        public: true,
      });
      onEnter(await api("/spaces/join", "POST", { code: s.code }));
    } catch (e: any) {
      notify(e.message);
    }
  };
  const deleteLobbySpace = async (s: SpaceT) => {
    if (!window.confirm(`Delete “${s.name}” for everyone?`)) return;
    try {
      await api(`/spaces/${s.id}`, "DELETE");
      load();
      notify("Watch space deleted.");
    } catch (e: any) {
      notify(e.message);
    }
  };
  const addVideo = async (e: React.FormEvent) => {
    e.preventDefault();
    setAddingVideo(true);
    try {
      const title = await api<Title>("/titles", "POST", {
        name: videoName,
        video: videoUrl,
        genres: videoTags,
      });
      onTitleAdded(title);
      setVideoName("");
      setVideoUrl("");
      setVideoTags([]);
      notify("Video added to the catalog.");
    } catch (error: any) {
      notify(error.message);
    } finally {
      setAddingVideo(false);
    }
  };

  return (
    <main className="home">
      {/* ===== BILLBOARD HERO (ambient trailer + tilted poster) ===== */}
      <section className="billboard">
        {featured && (
          <img
            className="billboard-video"
            src={poster(featured.video)}
            alt=""
            aria-hidden="true"
          />
        )}
        <div className="billboard-scrim" aria-hidden="true" />
        <div className="billboard-inner">
          <div className="billboard-copy">
            <span className="eyebrow">NOW SHOWING · WATCH TOGETHER</span>
            <h1>
              Pick a movie.
              <br />
              Bring your people.
            </h1>
            <p>
              Start a synchronized watch party with chat, trivia, polls and a
              live AI co-pilot — inside your own private cinema.
            </p>
            <div className="inline">
              <button
                onClick={() =>
                  document
                    .getElementById("create-space")
                    ?.scrollIntoView({ behavior: "smooth" })
                }
              >
                Book a watch space
              </button>
            </div>
          </div>
          {featured && (
            <div
              className="billboard-poster"
              onClick={() => onOpen(featured.id)}
            >
              <img src={poster(featured.video)} alt="Featured film" />
              <span className="billboard-tag">FEATURED</span>
              <span className="billboard-name">{featured.name}</span>
            </div>
          )}
        </div>
      </section>

      <section className="add-video-panel">
        <header className="console-head">
          <span className="eyebrow">COMMUNITY CATALOG</span>
          <h2>Add a video</h2>
          <p>
            Share a direct YouTube video link and tag every language, format,
            industry, or genre that fits.
          </p>
        </header>
        <form className="add-video-form" onSubmit={addVideo}>
          <label>
            Video title
            <input
              required
              maxLength={160}
              value={videoName}
              onChange={(e) => setVideoName(e.target.value)}
              placeholder="Title shown in the catalog"
            />
          </label>
          <label>
            YouTube video link
            <input
              required
              type="url"
              value={videoUrl}
              onChange={(e) => setVideoUrl(e.target.value)}
              placeholder="https://youtu.be/… (direct video link)"
            />
          </label>
          <div className="add-video-groups">
            {PREFERENCES.map((group) => (
              <div className="add-video-group" key={group.label}>
                <b>{group.label}</b>
                <div>
                  {group.values.map((item) => (
                    <button
                      type="button"
                      key={item}
                      className={`preference-chip ${videoTags.includes(item) ? "selected" : ""}`}
                      aria-pressed={videoTags.includes(item)}
                      onClick={() =>
                        setVideoTags((tags) =>
                          tags.includes(item)
                            ? tags.filter((tag) => tag !== item)
                            : [...tags, item]
                        )
                      }
                    >
                      {item}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <button type="submit" disabled={addingVideo}>
            {addingVideo ? "Adding…" : "Add to catalog"}
          </button>
        </form>
      </section>

      {/* ===== CONSOLE ===== */}
      <section id="create-space" className="console">
        <header className="console-head">
          <span className="eyebrow">CONCIERGE</span>
          <h2>Create a watch space</h2>
          <p>Choose a film and invite friends with a short room code.</p>
        </header>
        <div className="console-fields">
          <label>
            Space name
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Movie night"
            />
          </label>
          <label>
            Choose a movie
            <select value={selId} onChange={(e) => setSel(+e.target.value)}>
              {titles.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </label>
          <button onClick={create} disabled={!titles.length}>
            Create space <span aria-hidden="true">→</span>
          </button>
        </div>
        <div className="join-line">
          <span>Already have an invite code?</span>
          <input
            placeholder="Enter code"
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === "Enter" && join(code)}
          />
          <button className="ghost" onClick={() => join(code)}>
            Join space
          </button>
        </div>
      </section>

      {/* ===== TASTE HUB — "Tune the Room" dial panel ===== */}
      <section className="taste-hub">
        <header className="taste-hub-head">
          <span className="eyebrow">TUNE THE ROOM</span>
          <h2>Filter by language, format or genre</h2>
          <p>
            Tap a tag to re-tune your recommendations. Saved tags glow brighter.
          </p>
        </header>
        <div className="taste-dial">
          <div className="taste-dial-track" aria-hidden="true" />
          <div className="taste-dial-chips">
            {PREFERENCES.flatMap((g) => g.values).map((p) => (
              <button
                key={p}
                className={`taste-tag ${taste === p ? "on" : ""} ${preferences.some((x) => preferenceKey(x) === preferenceKey(p)) ? "saved" : ""}`}
                onClick={() => setTaste(taste === p ? "" : p)}
              >
                <span className="taste-tag-dot" aria-hidden="true" />
                <span className="taste-tag-label">{p}</span>
              </button>
            ))}
          </div>
          <footer className="taste-dial-foot">
            <span className="taste-now">
              Now tuned to{" "}
              <b>
                {taste
                  ? `${taste} + profile tastes`
                  : preferences.length
                    ? "all profile tastes"
                    : "Anything"}
              </b>
            </span>
            <a
              href={youtubeSearch(taste || preferences[0] || "free movies")}
              target="_blank"
              rel="noreferrer"
            >
              Browse {taste || preferences[0] || "free movies"} on YouTube ↗
            </a>
          </footer>
        </div>
      </section>

      {/* ===== RECOMMENDATIONS — spotlight mosaic grid ===== */}
      <section className="recs">
        <h2 className="rail-title">Recommended for you</h2>
        {visibleRecs.length ? (
          <div className="recs-grid">
            {visibleRecs.slice(0, 10).map((r) => {
              const t = titles.find((x) => x.id === r.id);
              const isSpot = topRated?.id === r.id;
              return (
                <div
                  className={`rec-card ${isSpot ? "spot" : ""} click`}
                  key={r.id}
                  onClick={() => onOpen(r.id)}
                >
                  {t && <img src={poster(t.video)} alt="" loading="lazy" />}
                  <div className="rec-card-meta">
                    {isSpot && <span className="rec-badge">TOP PICK</span>}
                    <b>{r.title}</b>
                    {ratings[r.id]?.count ? (
                      <small>
                        ★ {ratings[r.id].average.toFixed(1)} / 10 ·{" "}
                        {ratings[r.id].count}{" "}
                        {ratings[r.id].count === 1 ? "rating" : "ratings"}{" "}
                        <br />
                      </small>
                    ) : null}
                    <small>
                      Match {Math.max(1, Math.round(r.score * 90))}%
                    </small>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="taste-empty">
            No catalog picks for <b>{taste}</b> yet.{" "}
            <a
              href={youtubeSearch(taste || "free movies")}
              target="_blank"
              rel="noreferrer"
            >
              Browse free videos on YouTube ↗
            </a>
          </div>
        )}
      </section>

      {/* ===== CATALOG — numbered contact-sheet wall ===== */}
      <section className="catalog">
        <h2 className="rail-title">Full catalog{taste ? ` · ${taste}` : ""}</h2>
        <div className="catalog-wall">
          {visibleTitles.map((t, i) => (
            <div
              className="catalog-frame click"
              key={t.id}
              onClick={() => onOpen(t.id)}
            >
              <span className="catalog-num">
                {String(i + 1).padStart(2, "0")}
              </span>
              <img
                src={poster(t.video)}
                alt={`${t.name} poster`}
                loading="lazy"
              />
              <div className="catalog-frame-meta">
                <b>{t.name}</b>
                <small>{t.genres.join(" · ")}</small>
              </div>
            </div>
          ))}
        </div>
        {!visibleTitles.length && (
          <div className="taste-empty">
            No catalog titles are tagged <b>{taste}</b> yet.
          </div>
        )}
      </section>

      {/* ===== LOBBY ===== */}
      <section className="rail">
        <h2 className="rail-title">Public lobby</h2>
        <div className="rail-scroll">
          {visibleLobby.length ? (
            visibleLobby.map((s) => {
              const t = titles.find((x) => x.id === s.title_id);
              return (
                <div className="lobby-card" key={s.id}>
                  {t && <img src={poster(t.video)} alt="" />}
                  {t && (
                    <div>
                      <b>{s.name}</b>
                      <small>
                        {t.name} · code {s.code}
                      </small>
                      <small>
                        Hosted by{" "}
                        {s.host_id === me.id ? "you" : s.host_name || "Unknown"}
                      </small>
                      <div className="inline">
                        <button onClick={() => join(s.code)}>Enter room</button>
                        {s.host_id === me.id && (
                          <button
                            className="danger-button"
                            onClick={() => deleteLobbySpace(s)}
                          >
                            Delete
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <small className="badge">No public spaces yet</small>
          )}
        </div>
      </section>
    </main>
  );
}

type Msg = { type: string; payload: any; server_ts: number };
type PollT = {
  id: number;
  question: string;
  options: string[];
  tally: number[];
  winner?: string;
};
type ChatMessage = { user_id: number; user: string; text: string; ts: number };
type AiExchange = { q: string; a: string; src: string[]; created_at?: number };
const mergeChat = (current: ChatMessage[], incoming: ChatMessage[]) => {
  const merged = new Map<string, ChatMessage>();
  for (const message of [...current, ...incoming]) {
    const key = `${message.ts}:${message.user_id}:${message.text}`;
    merged.set(key, message);
  }
  return [...merged.values()].sort((a, b) => a.ts - b.ts).slice(-100);
};
const mergeAiHistory = (current: AiExchange[], incoming: AiExchange[]) => {
  const merged = new Map<string, AiExchange>();
  for (const exchange of [...current, ...incoming]) {
    const key =
      exchange.created_at != null
        ? String(exchange.created_at)
        : `${exchange.q}\n${exchange.a}`;
    merged.set(key, exchange);
  }
  return [...merged.values()]
    .sort((a, b) => (a.created_at ?? 0) - (b.created_at ?? 0))
    .slice(-100);
};

function Space({
  me,
  space,
  title,
  onLeave,
  notify,
  onEmbedDisabled,
  onHistoryUpdated,
}: {
  me: User;
  space: SpaceT;
  title: Title;
  onLeave: () => void;
  notify: (m: string) => void;
  onEmbedDisabled: () => void;
  onHistoryUpdated: () => void;
}) {
  const isHost = me.id === space.host_id;
  const player = useRef<MediaHandle | null>(null);
  const videoArea = useRef<HTMLDivElement | null>(null);
  const skipFullscreenBroadcast = useRef(false);
  const ws = useRef<WebSocket | null>(null);
  const target = useRef<{ pos: number; playing: boolean; at: number } | null>(
    null
  );
  const [tab, setTab] = useState("Chat");
  const [chat, setChat] = useState<ChatMessage[]>([]);
  const [online, setOnline] = useState<string[]>([]);
  const [poll, setPoll] = useState<PollT | null>(null);
  const [trivia, setTrivia] = useState<{
    scene_id: string;
    text: string;
  } | null>(null);
  const [qa, setQa] = useState<AiExchange[]>([]);
  const [fullscreenPrompt, setFullscreenPrompt] = useState<{
    user_id: number;
    user: string;
  } | null>(null);
  const [fullscreenActive, setFullscreenActive] = useState(false);

  const onPlayerReady = useCallback((p: MediaHandle) => {
    player.current = p;
    const t = target.current;
    if (t) {
      p.suppress();
      p.seek(t.pos);
      if (t.playing) p.play();
    }
  }, []);
  const removeEmbedDisabled = useCallback(async () => {
    try {
      await api(`/titles/${title.id}/embed-disabled`, "POST");
      notify(
        "Embedding is disabled for this video. It has been removed from the catalog."
      );
    } catch {
      notify(
        "Embedding is disabled for this video. It was removed from your view; the catalog update could not be saved."
      );
    }
    onEmbedDisabled();
  }, [title.id, notify, onEmbedDisabled]);
  const apply = (pos: number, playing: boolean) => {
    target.current = { pos, playing, at: performance.now() };
    const v = player.current;
    if (!v) return;
    v.suppress();
    if (Math.abs(v.getCurrentTime() - pos) > 1) v.seek(pos);
    if (playing && !v.isPlaying()) v.play();
    if (!playing && v.isPlaying()) v.pause();
  };

  useEffect(() => {
    let active = true;
    api<ChatMessage[]>(`/spaces/${space.id}/chat?limit=100`)
      .then((history) => {
        if (active) setChat((current) => mergeChat(current, history));
      })
      .catch((e: any) => {
        if (active)
          notify(e.message || "Couldn't load this watch space's chat history.");
      });
    return () => {
      active = false;
    };
  }, [space.id, notify]);

  useEffect(() => {
    let closed = false,
      retry = 0,
      ping: number;
    const connect = () => {
      const s = new WebSocket(`${WS}/ws/spaces/${space.id}?token=${token}`);
      ws.current = s;
      s.onopen = () => {
        retry = 0;
        ping = window.setInterval(
          () => s.send(JSON.stringify({ type: "PING" })),
          15000
        );
      };
      s.onmessage = (e) => {
        const m: Msg = JSON.parse(e.data),
          p = m.payload;
        if (m.type === "SYNC_STATE") apply(p.expected, p.playing);
        else if (["PLAY", "PAUSE", "SEEK"].includes(m.type)) {
          target.current = {
            pos: p.position,
            playing: p.playing,
            at: performance.now(),
          };
          if (p.user_id !== me.id) apply(p.position, p.playing);
        } else if (m.type === "FULLSCREEN" && p.user_id !== me.id) {
          if (p.active)
            setFullscreenPrompt({ user_id: p.user_id, user: p.user });
          else {
            setFullscreenPrompt((current) =>
              current?.user_id === p.user_id ? null : current
            );
            if (
              document.fullscreenElement &&
              videoArea.current?.contains(document.fullscreenElement)
            )
              document.exitFullscreen().catch(() => {});
          }
        } else if (m.type === "CHAT_MESSAGE") setChat((c) => mergeChat(c, [p]));
        else if (m.type === "PRESENCE_JOIN") setOnline(p.online);
        else if (m.type === "PRESENCE_LEAVE")
          setOnline((o) => o.filter((n) => n !== p.user));
        else if (m.type === "POLL_OPEN")
          setPoll({
            id: p.id,
            question: p.question,
            options: p.options,
            tally: p.options.map(() => 0),
          });
        else if (m.type === "POLL_VOTE")
          setPoll((x) => x && { ...x, tally: p.tally });
        else if (m.type === "POLL_RESULT")
          setPoll((x) => x && { ...x, tally: p.tally, winner: p.winner });
        else if (m.type === "AI_TRIVIA") {
          setTrivia(p);
          setTimeout(() => setTrivia((x) => (x === p ? null : x)), 12000);
        } else if (m.type === "ERROR") notify(p.msg);
      };
      s.onclose = () => {
        clearInterval(ping);
        if (!closed) setTimeout(connect, Math.min(1000 * 2 ** retry++, 15000));
      };
    };
    connect();
    const drift = window.setInterval(() => {
      const v = player.current,
        t = target.current;
      if (!v || !t) return;
      if (t.playing !== v.isPlaying()) {
        v.suppress();
        t.playing ? v.play() : v.pause();
      }
      const expected =
          t.pos + (t.playing ? (performance.now() - t.at) / 1000 : 0),
        d = v.getCurrentTime() - expected;
      if (Math.abs(d) > 1) v.seek(expected);
    }, 2000);
    let lastHistoryCheck = Date.now(),
      accumulatedPlaybackSeconds = 0;
    const tick = window.setInterval(() => {
      const v = player.current;
      if (isHost && v?.isPlaying())
        send("TIME_UPDATE", { position: v.getCurrentTime() });
      const now = Date.now();
      if (v?.isPlaying())
        accumulatedPlaybackSeconds += Math.max(
          0,
          (now - lastHistoryCheck) / 1000
        );
      lastHistoryCheck = now;
      if (accumulatedPlaybackSeconds >= 30) {
        const seconds = Math.floor(accumulatedPlaybackSeconds);
        accumulatedPlaybackSeconds = 0;
        api("/activity/watch", "POST", {
          title_id: title.id,
          seconds,
          completed: false,
        })
          .then(onHistoryUpdated)
          .catch(() => {});
      }
    }, 5000);
    return () => {
      closed = true;
      clearInterval(ping);
      clearInterval(drift);
      clearInterval(tick);
      ws.current?.close();
    };
  }, [space.id]); // eslint-disable-line

  const send = (type: string, payload: object = {}) =>
    ws.current?.readyState === 1 &&
    ws.current.send(JSON.stringify({ type, payload }));
  useEffect(() => {
    const onFullscreenChange = () => {
      const activeElement = document.fullscreenElement;
      const active = !!(
        activeElement && videoArea.current?.contains(activeElement)
      );
      setFullscreenActive(active);
      if (skipFullscreenBroadcast.current) {
        skipFullscreenBroadcast.current = false;
        return;
      }
      send("FULLSCREEN", { active });
    };
    document.addEventListener("fullscreenchange", onFullscreenChange);
    return () =>
      document.removeEventListener("fullscreenchange", onFullscreenChange);
  }, [space.id]); // eslint-disable-line
  const followFullscreen = async () => {
    try {
      if (videoArea.current?.requestFullscreen) {
        skipFullscreenBroadcast.current = true;
        await videoArea.current.requestFullscreen();
        setFullscreenPrompt(null);
      }
    } catch {
      skipFullscreenBroadcast.current = false;
      notify("Fullscreen was blocked by the browser. Click again to allow it.");
    }
  };
  const toggleFullscreen = async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await videoArea.current?.requestFullscreen();
    } catch {
      notify("Fullscreen was blocked by the browser. Click again to allow it.");
    }
  };
  const deleteSpace = async () => {
    if (!isHost || !window.confirm(`Delete “${space.name}” for everyone?`))
      return;
    try {
      await api(`/spaces/${space.id}`, "DELETE");
      onLeave();
      notify("Watch space deleted.");
    } catch (e: any) {
      notify(e.message);
    }
  };

  return (
    <div className="theatre">
      <div className="stage">
        <header className="stage-bar">
          <button className="ghost" onClick={onLeave}>
            ← Leave theatre
          </button>
          <div className="stage-title">
            <b>{space.name}</b>
            <span className="badge">
              Invite code <strong>{space.code}</strong>
            </span>
            <span className="badge role">{isHost ? "HOST" : "GUEST"}</span>
            <span className="badge">
              Host:{" "}
              <strong>{isHost ? "You" : space.host_name || "Unknown"}</strong>
            </span>
          </div>
          {isHost && (
            <button className="danger-button" onClick={deleteSpace}>
              Delete watch space
            </button>
          )}
        </header>

        {trivia && (
          <div className="trivia">
            💡 <b>Did you know?</b> {trivia.text}
          </div>
        )}

        <div ref={videoArea} className="screen-wrap">
          <div className="screen-bulbs-top" aria-hidden="true" />
          <div className="screen-bulbs-bottom" aria-hidden="true" />
          <YouTubePlayer
            key={title.video}
            src={title.video}
            host={isHost}
            onReady={onPlayerReady}
            onAction={(type, position) => {
              const previous = target.current;
              const playing =
                type === "PLAY"
                  ? true
                  : type === "PAUSE"
                    ? false
                    : (previous?.playing ?? false);
              target.current = {
                pos: position,
                playing,
                at: performance.now(),
              };
              send(type, { position });
            }}
            notify={notify}
            onEmbedDisabled={removeEmbedDisabled}
          />
          <div className="screen-controls">
            <button className="ghost" onClick={toggleFullscreen}>
              {fullscreenActive ? "Exit fullscreen" : "Fullscreen"}
            </button>
          </div>
          {fullscreenPrompt && (
            <div className="fullscreen-follow">
              <span>
                <b>{fullscreenPrompt.user}</b> entered fullscreen
              </span>
              <button onClick={followFullscreen}>Follow fullscreen</button>
              <button
                className="ghost"
                onClick={() => setFullscreenPrompt(null)}
                aria-label="Dismiss fullscreen request"
              >
                ×
              </button>
            </div>
          )}
        </div>
        <p className="player-note">
          Playing <b>{title.name}</b> · Play, pause and seeking sync for
          everyone. Quality, volume and captions follow each viewer's YouTube
          settings.
        </p>
      </div>

      <aside className="balcony">
        <div className="tabs">
          {["Chat", "AI", "Polls", "People"].map((t) => (
            <button
              key={t}
              className={tab === t ? "on" : ""}
              onClick={() => setTab(t)}
            >
              {t}
            </button>
          ))}
        </div>
        {tab === "Chat" && (
          <Chat
            msgs={chat}
            myId={me.id}
            onSend={(t) => send("CHAT_MESSAGE", { text: t })}
          />
        )}
        {tab === "AI" && (
          <AI
            spaceId={space.id}
            qa={qa}
            setQa={setQa}
            notify={notify}
            ask={async (q, includeSpoilers) => {
              try {
                const r = await api("/ai/ask", "POST", {
                  space_id: space.id,
                  question: q,
                  current_time: player.current?.getCurrentTime() ?? 0,
                  include_spoilers: includeSpoilers,
                });
                setQa((x) =>
                  mergeAiHistory(x, [
                    {
                      q,
                      a: r.answer,
                      src: r.sources,
                      created_at: r.created_at,
                    },
                  ])
                );
              } catch (e: any) {
                notify(
                  e instanceof TypeError
                    ? "Can't reach the Watch Spaces backend. Check that it is running, then try again."
                    : e.message ||
                        "Video assistant request failed. Please try again."
                );
              }
            }}
          />
        )}
        {tab === "Polls" && (
          <Polls
            poll={poll}
            setPoll={(p) => setPoll(p)}
            isHost={isHost}
            spaceId={space.id}
            notify={notify}
          />
        )}
        {tab === "People" && <People online={online} spaceId={space.id} />}
      </aside>
    </div>
  );
}

function Chat({
  msgs,
  myId,
  onSend,
}: {
  msgs: { user_id: number; user: string; text: string }[];
  myId: number;
  onSend: (t: string) => void;
}) {
  const [t, setT] = useState("");
  const bodyRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const el = bodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [msgs.length]);
  const go = () => {
    if (t.trim()) {
      onSend(t);
      setT("");
    }
  };
  return (
    <>
      <div className="body" ref={bodyRef}>
        {msgs.map((m, i) => {
          const mine = m.user_id === myId;
          return (
            <div className={`msg chat-message${mine ? " mine" : ""}`} key={i}>
              <b>{mine ? "You" : m.user}</b>
              <span>{m.text}</span>
            </div>
          );
        })}
      </div>
      <div className="inline composer">
        <input
          value={t}
          onChange={(e) => setT(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && go()}
          placeholder="Say something"
        />
        <button onClick={go}>Send</button>
      </div>
    </>
  );
}

function AI({
  qa,
  setQa,
  ask,
  spaceId,
  notify,
}: {
  qa: AiExchange[];
  setQa: (update: (current: AiExchange[]) => AiExchange[]) => void;
  ask: (q: string, includeSpoilers: boolean) => Promise<void>;
  spaceId: number;
  notify: (message: string) => void;
}) {
  const [q, setQ] = useState("");
  const [includeSpoilers, setIncludeSpoilers] = useState(true);
  const [busy, setBusy] = useState(false);
  const [pendingQuestion, setPendingQuestion] = useState("");
  const [status, setStatus] = useState<{
    configured: boolean;
    provider: string;
    scene_notes: number;
  } | null>(null);
  useEffect(() => {
    api(`/ai/status?space_id=${spaceId}`)
      .then(setStatus)
      .catch(() => setStatus(null));
  }, [spaceId]);
  useEffect(() => {
    let active = true;
    api<AiExchange[]>(`/spaces/${spaceId}/ai/history?limit=100`)
      .then((history) => {
        if (active) setQa((current) => mergeAiHistory(current, history));
      })
      .catch((e: any) => {
        if (active) notify(e.message || "Couldn't load your co-pilot history.");
      });
    return () => {
      active = false;
    };
  }, [spaceId, setQa, notify]);
  const go = async (x: string) => {
    const question = x.trim();
    if (!question || busy) return;
    setBusy(true);
    setPendingQuestion(question);
    setQ("");
    try {
      await ask(question, includeSpoilers);
    } finally {
      setBusy(false);
      setPendingQuestion("");
    }
  };
  const helpText =
    status?.provider === "gemini"
      ? "Gemini can analyze this public YouTube video's audio and visuals. Answers may include spoilers when full-video access is enabled."
      : status?.configured
        ? "Answers use the available scene notes for this video."
        : `AI provider is not configured. Answers use available scene notes (${status?.scene_notes ?? 0} for this title) and may be limited.`;
  return (
    <>
      <div className="body">
        <span className="badge">{helpText}</span>
        <label className="spoiler-toggle">
          <input
            type="checkbox"
            checked={includeSpoilers}
            disabled={busy}
            onChange={(e) => setIncludeSpoilers(e.target.checked)}
          />{" "}
          Allow full-video answers (may contain spoilers)
        </label>
        <div className="inline">
          {["Who made this?", "What just happened?"].map((s) => (
            <button
              className="ghost"
              key={s}
              disabled={busy}
              onClick={() => void go(s)}
            >
              {s}
            </button>
          ))}
        </div>
        {qa.map((x, i) => (
          <div key={i}>
            <div className="msg">
              <b>You</b> {x.q}
            </div>
            <div className="bubble">
              {x.a}
              <br />
              <span className="badge">
                {x.src.length ? "Sources: " + x.src.join(", ") : "No source"}
              </span>
            </div>
          </div>
        ))}
        {pendingQuestion && (
          <div>
            <div className="msg">
              <b>You</b> {pendingQuestion}
            </div>
            <div className="bubble ai-thinking">
              <span className="ai-spinner" />
              Analyzing video…
            </div>
          </div>
        )}
      </div>
      <div className="inline composer">
        <input
          value={q}
          disabled={busy}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && void go(q)}
          placeholder={busy ? "Analyzing video…" : "Ask the co-pilot"}
        />
        <button disabled={busy || !q.trim()} onClick={() => void go(q)}>
          {busy ? "Thinking…" : "Ask"}
        </button>
      </div>
    </>
  );
}

type VSet = { id: number; kind: string; question: string; options: string[] };
function Polls({
  poll,
  setPoll,
  isHost,
  spaceId,
  notify,
}: {
  poll: PollT | null;
  setPoll: (p: PollT) => void;
  isHost: boolean;
  spaceId: number;
  notify: (m: string) => void;
}) {
  const [sets, setSets] = useState<VSet[]>([]);
  const [pick, setPick] = useState(0);
  const [defaults, setDefaults] = useState<
    { key: string; question: string; options: string[] }[]
  >([]);
  const [defPick, setDefPick] = useState("break");
  useEffect(() => {
    if (isHost)
      api("/polls/defaults")
        .then((d) => {
          setDefaults(d);
          if (d[0]) setDefPick(d[0].key);
        })
        .catch(() => {});
  }, [isHost]);
  const [customQuestion, setCustomQuestion] = useState("");
  const [customOptions, setCustomOptions] = useState(["", ""]);
  const [past, setPast] = useState<
    { id: number; question: string; winner: string }[]
  >([]);
  const load = () => {
    if (isHost)
      api(`/spaces/${spaceId}/variations`)
        .then((v: VSet[]) => {
          setSets(v);
          setPick((p) => (v.some((x) => x.id === p) ? p : (v[0]?.id ?? 0)));
        })
        .catch(() => {});
    api(`/spaces/${spaceId}/polls`)
      .then((ps: any[]) => {
        const open = ps.find((p) => p.open);
        if (open && !poll)
          setPoll({
            id: open.id,
            question: open.question,
            options: open.options,
            tally: open.tally,
          });
        setPast(ps.filter((p) => !p.open && p.winner).reverse());
      })
      .catch(() => {});
  };
  useEffect(load, [spaceId, poll?.id, poll?.winner]); // eslint-disable-line
  const run = (p: string, m: string, b?: object) =>
    api(p, m, b).catch((e) => notify(e.message));
  const openCustom = async () => {
    try {
      await api(`/spaces/${spaceId}/polls`, "POST", {
        question: customQuestion,
        options: customOptions,
      });
      setCustomQuestion("");
      setCustomOptions(["", ""]);
    } catch (e: any) {
      notify(e.message);
    }
  };
  const total = poll ? poll.tally.reduce((a, b) => a + b, 0) || 1 : 1;
  const active = poll && !poll.winner;
  return (
    <div className="body">
      {isHost && !active && (
        <div className="poll-create-options">
          {sets.length > 0 && (
            <div className="poll-approved">
              <span className="badge">Start a pre-approved poll</span>
              <select value={pick} onChange={(e) => setPick(+e.target.value)}>
                {sets.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.kind === "narrative" ? "🎬" : "🌐"} {v.question}
                  </option>
                ))}
              </select>
              <div className="inline">
                <button
                  onClick={() =>
                    run(`/spaces/${spaceId}/polls`, "POST", {
                      variation_set_id: pick,
                    })
                  }
                >
                  Open approved poll
                </button>
              </div>
            </div>
          )}
          {defaults.length > 0 && (
            <div className="poll-approved">
              <span className="badge">Start a default poll</span>
              <select
                value={defPick}
                onChange={(e) => setDefPick(e.target.value)}
              >
                {defaults.map((d) => (
                  <option key={d.key} value={d.key}>
                    🗳️ {d.question}
                  </option>
                ))}
              </select>
              <div className="inline">
                <button
                  onClick={() =>
                    run(`/spaces/${spaceId}/polls`, "POST", {
                      default_key: defPick,
                    })
                  }
                >
                  Open default poll
                </button>
              </div>
            </div>
          )}
          <div className="poll-custom">
            <b>Create a poll in your own words</b>
            <input
              maxLength={240}
              value={customQuestion}
              onChange={(e) => setCustomQuestion(e.target.value)}
              placeholder="Ask the room a question"
            />
            {customOptions.map((option, i) => (
              <div className="inline" key={i}>
                <input
                  maxLength={100}
                  value={option}
                  onChange={(e) =>
                    setCustomOptions((items) =>
                      items.map((x, j) => (j === i ? e.target.value : x))
                    )
                  }
                  placeholder={`Option ${i + 1}`}
                />
                {customOptions.length > 2 && (
                  <button
                    className="ghost"
                    onClick={() =>
                      setCustomOptions((items) =>
                        items.filter((_, j) => j !== i)
                      )
                    }
                  >
                    Remove
                  </button>
                )}
              </div>
            ))}
            {customOptions.length < 6 && (
              <button
                className="ghost"
                onClick={() => setCustomOptions((items) => [...items, ""])}
              >
                + Add option
              </button>
            )}
            <button
              disabled={
                !customQuestion.trim() ||
                customOptions.length < 2 ||
                customOptions.some((x) => !x.trim())
              }
              onClick={openCustom}
            >
              Open custom poll
            </button>
          </div>
        </div>
      )}
      {!poll ? (
        <span className="badge">No active poll.</span>
      ) : (
        <div>
          <b>{poll.question}</b>
          {poll.options.map((o, i) => (
            <div key={i} className="poll-row">
              <button
                className="ghost"
                disabled={!!poll.winner}
                onClick={() =>
                  run(`/polls/${poll.id}/vote`, "POST", { option: i })
                }
              >
                {o}
              </button>{" "}
              <span>{poll.tally[i]}</span>
              <div
                className="bar"
                style={{ width: `${(poll.tally[i] / total) * 100}%` }}
              />
            </div>
          ))}
          {poll.winner ? (
            <div className="bubble">🏆 Winner: {poll.winner}</div>
          ) : (
            isHost && (
              <button onClick={() => run(`/polls/${poll.id}/close`, "POST")}>
                Close poll
              </button>
            )
          )}
        </div>
      )}
      {past.filter((p) => p.id !== poll?.id).length > 0 && (
        <div>
          <b>Earlier results</b>
          {past
            .filter((p) => p.id !== poll?.id)
            .map((p) => (
              <div className="bubble" key={p.id}>
                {p.question}
                <br />
                <span className="badge">🏆 {p.winner}</span>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

function TitleDetail({
  id,
  meId,
  onEnter,
  onBack,
  onChanged,
  notify,
}: {
  id: number;
  meId: number;
  onChanged: (t: Title | null, id: number) => void;
  onEnter: (s: SpaceT) => void;
  onBack: () => void;
  notify: (m: string) => void;
}) {
  const [t, setT] = useState<
    | (Title & {
        scene_count: number;
        added_by_name?: string | null;
        watch_count: number;
        watched_by_me: boolean;
      })
    | null
  >(null);
  const [reviewData, setReviewData] = useState<ReviewData | null>(null);
  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editTags, setEditTags] = useState<string[]>([]);
  const [rating, setRating] = useState("8");
  const [headline, setHeadline] = useState("");
  const [body, setBody] = useState("");
  const refreshReviews = useCallback(
    () =>
      api(`/titles/${id}/reviews`)
        .then((data: ReviewData) => {
          setReviewData(data);
          if (data.mine) {
            setRating(String(data.mine.rating));
            setHeadline(data.mine.headline);
            setBody(data.mine.body);
          }
        })
        .catch((e) => notify(e.message)),
    [id, notify]
  );
  useEffect(() => {
    api("/titles/" + id)
      .then(setT)
      .catch((e) => notify(e.message));
    refreshReviews();
  }, [id, notify, refreshReviews]);
  useEffect(() => {
    if (t) {
      setEditName(t.name);
      setEditTags(t.genres);
    }
  }, [t?.name, t?.genres.join(",")]); // eslint-disable-line
  const saveEdit = async () => {
    try {
      const u = await api<Title>(`/titles/${id}`, "PUT", {
        name: editName,
        genres: editTags,
      });
      setT((v) => v && { ...v, name: u.name, genres: u.genres });
      onChanged(u, id);
      setEditing(false);
      notify("Catalogue entry updated.");
    } catch (e: any) {
      notify(e.message);
    }
  };
  const removeTitle = async () => {
    if (!window.confirm("Delete this catalogue entry for everyone?")) return;
    try {
      await api(`/titles/${id}`, "DELETE");
      onChanged(null, id);
      notify("Catalogue entry deleted.");
    } catch (e: any) {
      notify(e.message);
    }
  };
  const host = async () => {
    try {
      const c = await api("/spaces", "POST", {
        name: `${t!.name} night`,
        title_id: id,
        public: true,
      });
      onEnter(await api("/spaces/join", "POST", { code: c.code }));
    } catch (e: any) {
      notify(e.message);
    }
  };
  const watched = () =>
    api("/activity/watch", "POST", {
      title_id: id,
      seconds: 0,
      completed: true,
    })
      .then(() => {
        setT(
          (v) =>
            v && {
              ...v,
              watched_by_me: true,
              watch_count: v.watch_count + (v.watched_by_me ? 0 : 1),
            }
        );
        notify("Marked as watched. Recommendations updated.");
      })
      .catch((e) => notify(e.message));
  const submitReview = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api(`/titles/${id}/reviews`, "POST", {
        rating: Number(rating),
        headline,
        body,
      });
      await refreshReviews();
      notify("Your review was saved.");
    } catch (err: any) {
      notify(err.message);
    }
  };
  if (!t) return <main className="loading">Loading…</main>;
  return (
    <main className="detail">
      <button className="ghost" onClick={onBack}>
        ← Back to lobby
      </button>

      <section className="detail-stage">
        <div className="detail-poster">
          <img src={poster(t.video)} alt={`${t.name} poster`} />
          <span className="poster-frame" aria-hidden="true" />
        </div>
        <div className="detail-copy">
          <span className="eyebrow">NOW PLAYING</span>
          <h1>{t.name}</h1>
          <p>
            {[
              t.genres.join(" · "),
              t.scene_count > 0 ? `${t.scene_count} annotated scenes` : "",
              `${t.watch_count} watched`,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
          {t.added_by && t.added_by_name && (
            <p className="added-by">Added by {t.added_by_name}</p>
          )}
          {t.added_by === meId && (
            <div className="inline">
              <button
                className="edit-button"
                onClick={() => setEditing((v) => !v)}
              >
                {editing ? "Cancel edit" : "Edit"}
              </button>
              <button className="danger-button" onClick={removeTitle}>
                Delete
              </button>
            </div>
          )}
          {editing && (
            <div className="add-video-form">
              <label>
                Video title
                <input
                  maxLength={160}
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                />
              </label>
              <div className="add-video-groups">
                {PREFERENCES.map((group) => (
                  <div className="add-video-group" key={group.label}>
                    <b>{group.label}</b>
                    <div>
                      {group.values.map((item) => (
                        <button
                          type="button"
                          key={item}
                          className={`preference-chip ${editTags.includes(item) ? "selected" : ""}`}
                          onClick={() =>
                            setEditTags((tags) =>
                              tags.includes(item)
                                ? tags.filter((x) => x !== item)
                                : [...tags, item]
                            )
                          }
                        >
                          {item}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              <button onClick={saveEdit}>Save changes</button>
            </div>
          )}
          <div className="inline">
            <button onClick={host}>Host a watch space</button>
            <a
              className="button secondary"
              href={t.video}
              target="_blank"
              rel="noreferrer"
            >
              Watch on YouTube ↗
            </a>
            <button
              className="ghost"
              onClick={watched}
              disabled={t.watched_by_me}
            >
              {t.watched_by_me ? "✓ Marked as watched" : "Mark as watched"}
            </button>
          </div>
        </div>
      </section>

      <section className="reviews-section">
        <div className="reviews-heading">
          <div>
            <span className="eyebrow">AUDIENCE</span>
            <h2>Reviews & ratings</h2>
          </div>
          {reviewData?.count ? (
            <div className="rating-summary">
              <b>{reviewData.average?.toFixed(1)}</b>
              <span>
                out of 10 · {reviewData.count}{" "}
                {reviewData.count === 1 ? "review" : "reviews"}
              </span>
              {reviewData.positive_percent !== null && (
                <small>
                  {reviewData.positive_percent}% rated it 6 or higher
                </small>
              )}
            </div>
          ) : (
            <span className="badge">No ratings yet</span>
          )}
        </div>
        <form className="review-form" onSubmit={submitReview}>
          <h3>{reviewData?.mine ? "Update your review" : "Write a review"}</h3>
          <label>
            Your rating (0.5–10)
            <select value={rating} onChange={(e) => setRating(e.target.value)}>
              {Array.from({ length: 20 }, (_, i) => (i + 1) / 2).map(
                (value) => (
                  <option key={value} value={value}>
                    {value} / 10
                  </option>
                )
              )}
            </select>
          </label>
          <label>
            Headline{" "}
            <input
              maxLength={120}
              value={headline}
              onChange={(e) => setHeadline(e.target.value)}
              placeholder="Give your review a title"
            />
          </label>
          <label>
            Your review{" "}
            <textarea
              required
              maxLength={5000}
              rows={5}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="What did you think?"
            />
          </label>
          <button type="submit">
            {reviewData?.mine ? "Save changes" : "Post review"}
          </button>
        </form>
        <div className="review-list">
          {reviewData?.reviews.length ? (
            reviewData.reviews.map((review) => (
              <ReviewCard key={review.id} review={review} notify={notify} />
            ))
          ) : (
            <p className="review-empty">
              Be the first to share what you thought of {t.name}.
            </p>
          )}
        </div>
      </section>
    </main>
  );
}

function ReviewCard({
  review,
  notify,
}: {
  review: Review;
  notify: (m: string) => void;
}) {
  const [comments, setComments] = useState<ReviewComment[] | null>(null);
  const [draft, setDraft] = useState("");
  const load = () =>
    api(`/reviews/${review.id}/comments`)
      .then(setComments)
      .catch((e) => notify(e.message));
  useEffect(() => {
    load();
  }, [review.id]);
  const addComment = async () => {
    if (!draft.trim()) return;
    try {
      await api(`/reviews/${review.id}/comments`, "POST", { body: draft });
      setDraft("");
      await load();
    } catch (e: any) {
      notify(e.message);
    }
  };
  const date = new Date(review.created_at * 1000).toLocaleDateString();
  return (
    <article className="review-card">
      <div className="review-meta">
        <b>{review.author}</b>
        <span>{review.rating.toFixed(1)} / 10</span>
        <time>{date}</time>
      </div>
      {review.headline && <h3>{review.headline}</h3>}
      <p>{review.body}</p>
      <button
        className="ghost"
        onClick={() => (comments === null ? load() : setComments(null))}
      >
        {comments === null
          ? `Comments (${review.comment_count})`
          : "Hide comments"}
      </button>
      {comments !== null && (
        <div className="comment-list">
          {comments.map((comment) => (
            <div className="comment-item" key={comment.id}>
              <b>{comment.author}</b>
              <span>{comment.body}</span>
              <time>
                {new Date(comment.created_at * 1000).toLocaleDateString()}
              </time>
            </div>
          ))}
          <div className="comment-compose">
            <input
              maxLength={1500}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && addComment()}
              placeholder="Add a comment"
            />
            <button onClick={addComment} disabled={!draft.trim()}>
              Comment
            </button>
          </div>
        </div>
      )}
    </article>
  );
}

function ProfilePage({
  me,
  onSaved,
  historyRevision,
  notify,
}: {
  me: User;
  onSaved: (u: User) => void;
  historyRevision: number;
  notify: (m: string) => void;
}) {
  const [name, setName] = useState(me.name);
  const [genres, setGenres] = useState<string[]>([]);
  const [hist, setHist] = useState<
    { title: string; seconds: number; completed: boolean }[]
  >([]);
  useEffect(() => {
    api("/me").then((m) =>
      setGenres((m.genres || "").split(",").filter(Boolean))
    );
    api("/me/history")
      .then(setHist)
      .catch((e) => notify(e.message));
  }, [historyRevision, notify]);
  const save = async () => {
    try {
      await api("/me", "PUT", { name, genres });
      onSaved(await api("/me"));
      notify("Profile saved. Recommendations updated.");
    } catch (e: any) {
      notify(e.message);
    }
  };
  return (
    <main className="profile">
      <section className="profile-card">
        <span className="eyebrow">MEMBER CARD</span>
        <h2>{name || me.name}</h2>
        <div className="inline">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Display name"
          />
        </div>
        <PreferencesPicker
          value={genres}
          onChange={setGenres}
          title="Your viewing preferences"
        />
        <button onClick={save}>Save</button>
      </section>
      <section className="history">
        <h2>Watch history</h2>
        {hist.length ? (
          hist.map((h, i) => (
            <div className="bubble" key={i}>
              {h.title} ·{" "}
              {h.seconds
                ? `${Math.round(h.seconds / 60)} min watched`
                : h.completed
                  ? "Marked watched"
                  : "Joined watch space"}{" "}
              {h.completed && "✓"}
            </div>
          ))
        ) : (
          <small className="badge">Nothing watched yet</small>
        )}
      </section>
    </main>
  );
}

function People({ online, spaceId }: { online: string[]; spaceId: number }) {
  const [recs, setRecs] = useState<Rec[]>([]);
  useEffect(() => {
    api(`/spaces/${spaceId}/recommendations`)
      .then(setRecs)
      .catch(() => {});
  }, [spaceId, online.length]);
  return (
    <div className="body">
      {online.map((n) => (
        <div className="bubble" key={n}>
          🟢 {n}
        </div>
      ))}
      <b style={{ marginTop: 12 }}>Recommended for this group</b>
      {recs.length ? (
        recs.map((r) => (
          <div className="bubble" key={r.id}>
            {r.title}{" "}
            <span className="badge">{Math.round(r.score * 100)}%</span>
          </div>
        ))
      ) : (
        <span className="badge">Nothing new for everyone here.</span>
      )}
    </div>
  );
}
