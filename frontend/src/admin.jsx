import React, { useCallback, useEffect, useState } from "react";
import { NavLink, Navigate, Outlet, useNavigate } from "react-router-dom";
import * as api from "./api";
import { useAuth } from "./auth";
import { fmtCount, fmtDate, useTitle } from "./utils";

/* ---------- small helpers ---------- */
function useLoad(fn) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const reload = useCallback(() => fn().then((d) => { setData(d); setError(""); }).catch((e) => setError(e.message)), [fn]);
  useEffect(() => { reload(); }, [reload]);
  return [data, reload, error];
}

function Field({ label, children }) {
  return <label className="adm-field"><span>{label}</span>{children}</label>;
}

/* ---------- login ---------- */
export function Login() {
  const { user, ready, login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useTitle("Admin sign in — Zimbermanne");

  if (ready && user) return <Navigate to="/admin" replace />;

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try { await login(email, password); nav("/admin", { replace: true }); }
    catch (err) { setError(err.message); }
    setBusy(false);
  }

  return (
    <div className="adm-login">
      <form className="adm-card" onSubmit={submit}>
        <h1>Zimbermanne</h1>
        <p className="adm-muted">Sign in to manage songs, messages and your fan list.</p>
        {error && <div className="form-status error" role="alert">{error}</div>}
        <Field label="Email"><input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <Field label="Password"><input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
        <button className="btn" type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
      </form>
    </div>
  );
}

/* ---------- shell ---------- */
export function AdminLayout() {
  const { user, ready, logout } = useAuth();
  useTitle("Admin — Zimbermanne");
  if (!ready) return <p className="loading-note">Loading…</p>;
  if (!user) return <Navigate to="/admin/login" replace />;

  const link = ({ isActive }) => (isActive ? "active" : undefined);
  return (
    <div className="adm">
      <aside className="adm-side">
        <div className="adm-brand">Zimbermanne<small>Admin</small></div>
        <nav>
          <NavLink end to="/admin" className={link}>Overview</NavLink>
          <NavLink to="/admin/catalog" className={link}>Albums &amp; songs</NavLink>
          <NavLink to="/admin/sync" className={link}>Sync</NavLink>
          <NavLink to="/admin/inbox" className={link}>Inbox</NavLink>
          <NavLink to="/admin/fans" className={link}>Fan list</NavLink>
          <NavLink to="/admin/account" className={link}>Account</NavLink>
        </nav>
        <div className="adm-side-foot">
          <a href="/" target="_blank" rel="noopener noreferrer">View site ↗</a>
          <span>{user.email}</span>
          <button type="button" className="adm-link" onClick={logout}>Sign out</button>
        </div>
      </aside>
      <main className="adm-main"><Outlet /></main>
    </div>
  );
}

/* ---------- overview ---------- */
export function Dashboard() {
  const [s, , error] = useLoad(api.adminStats);
  const cards = s && [
    ["Views", s.views], ["Albums", s.albums], ["Songs", s.tracks],
    ["Fans", s.subscribers], ["Messages", s.messages], ["Unread", s.unread],
  ];
  return (
    <>
      <h1 className="adm-h">Overview</h1>
      {error && <div className="form-status error">{error}</div>}
      <div className="adm-stats">
        {cards ? cards.map(([k, v]) => <div className="adm-stat" key={k}><b>{v}</b><span>{k}</span></div>) : <p className="adm-muted">Loading…</p>}
      </div>
    </>
  );
}

/* ---------- albums & songs ---------- */
const blankAlbum = { title: "", number: "", tagline: "", description: "", cover: "", chips: [] };
const blankTrack = { title: "", subtitle: "", url: "", audioUrl: "", image: "", duration: "", lyrics: "" };

function AlbumForm({ initial, onSave, onCancel }) {
  const [f, setF] = useState({ ...initial, chipsText: (initial.chips || []).join(", ") });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await onSave({ title: f.title, number: f.number, tagline: f.tagline, description: f.description, cover: f.cover,
        chips: f.chipsText.split(",").map((c) => c.trim()).filter(Boolean) });
    } catch (x) { setErr(x.message); setBusy(false); }
  }
  return (
    <form className="adm-card adm-form" onSubmit={submit}>
      {err && <div className="form-status error">{err}</div>}
      <div className="adm-grid">
        <Field label="Title"><input required value={f.title} onChange={set("title")} /></Field>
        <Field label="Number (e.g. Album 04)"><input value={f.number} onChange={set("number")} /></Field>
        <Field label="Tagline"><input value={f.tagline} onChange={set("tagline")} /></Field>
        <Field label="Cover image URL"><input value={f.cover} onChange={set("cover")} /></Field>
      </div>
      <Field label="Description"><textarea rows={3} value={f.description} onChange={set("description")} /></Field>
      <Field label="Chips (comma separated)"><input value={f.chipsText} onChange={set("chipsText")} /></Field>
      <div className="adm-actions">
        <button className="btn" type="submit" disabled={busy}>{busy ? "Saving…" : "Save album"}</button>
        <button className="btn btn-secondary" type="button" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

function TrackForm({ initial, onSave, onCancel }) {
  const [f, setF] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try { await onSave({ title: f.title, subtitle: f.subtitle, url: f.url, audioUrl: f.audioUrl, image: f.image, duration: f.duration, lyrics: f.lyrics }); }
    catch (x) { setErr(x.message); setBusy(false); }
  }
  return (
    <form className="adm-card adm-form" onSubmit={submit}>
      {err && <div className="form-status error">{err}</div>}
      <div className="adm-grid">
        <Field label="Title"><input required value={f.title} onChange={set("title")} /></Field>
        <Field label="Subtitle (e.g. Remastered)"><input value={f.subtitle || ""} onChange={set("subtitle")} /></Field>
        <Field label="Suno song link"><input value={f.url || ""} onChange={set("url")} /></Field>
        <Field label="Audio URL (optional)"><input value={f.audioUrl || ""} onChange={set("audioUrl")} /></Field>
        <Field label="Cover override (optional)"><input value={f.image || ""} onChange={set("image")} /></Field>
        <Field label="Duration"><input placeholder="3:45" value={f.duration || ""} onChange={set("duration")} /></Field>
      </div>
      <Field label="Lyrics"><textarea rows={10} value={f.lyrics || ""} onChange={set("lyrics")} /></Field>
      <div className="adm-actions">
        <button className="btn" type="submit" disabled={busy}>{busy ? "Saving…" : "Save song"}</button>
        <button className="btn btn-secondary" type="button" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

export function Catalog() {
  const [albums, reload, error] = useLoad(api.adminAlbums);
  const [edit, setEdit] = useState(null); // { kind: "album"|"track", album?, track? }
  const [open, setOpen] = useState({});

  const done = async () => { setEdit(null); await reload(); };
  const remove = async (what, fn, id) => {
    if (window.confirm(`Delete this ${what}? This cannot be undone.`)) { await fn(id); reload(); }
  };

  if (edit?.kind === "album") {
    const a = edit.album;
    return (<><h1 className="adm-h">{a ? "Edit album" : "New album"}</h1>
      <AlbumForm initial={a || blankAlbum} onCancel={() => setEdit(null)}
        onSave={async (b) => { a ? await api.updateAlbum(a.dbId, b) : await api.createAlbum(b); await done(); }} /></>);
  }
  if (edit?.kind === "track") {
    const { album, track } = edit;
    return (<><h1 className="adm-h">{track ? "Edit song" : `New song in ${album.title}`}</h1>
      <TrackForm initial={track || blankTrack} onCancel={() => setEdit(null)}
        onSave={async (b) => { track ? await api.updateTrack(track.id, b) : await api.createTrack(album.dbId, b); await done(); }} /></>);
  }

  return (
    <>
      <div className="adm-bar">
        <h1 className="adm-h">Albums &amp; songs</h1>
        <button className="btn" type="button" onClick={() => setEdit({ kind: "album" })}>New album</button>
      </div>
      {error && <div className="form-status error">{error}</div>}
      {!albums && !error && <p className="adm-muted">Loading…</p>}
      {albums?.map((a) => (
        <div className="adm-card" key={a.dbId}>
          <div className="adm-row">
            <img className="adm-thumb" src={a.cover} alt="" />
            <div className="adm-grow">
              <b>{a.title}</b>
              <div className="adm-muted">{a.number} · {a.tracks.length} songs</div>
            </div>
            <button className="adm-link" type="button" onClick={() => setOpen((o) => ({ ...o, [a.dbId]: !o[a.dbId] }))}>{open[a.dbId] ? "Hide songs" : "Songs"}</button>
            <button className="adm-link" type="button" onClick={() => setEdit({ kind: "album", album: a })}>Edit</button>
            <button className="adm-link danger" type="button" onClick={() => remove("album and all its songs", api.deleteAlbum, a.dbId)}>Delete</button>
          </div>
          {open[a.dbId] && (
            <div className="adm-tracks">
              {a.tracks.map((t) => (
                <div className="adm-row" key={t.id}>
                  <div className="adm-grow">{t.title}{t.subtitle && <span className="adm-muted"> {t.subtitle}</span>}</div>
                  <a className="adm-link" href={`/song/${t.slug}`} target="_blank" rel="noopener noreferrer">Open</a>
                  <button className="adm-link" type="button" onClick={() => setEdit({ kind: "track", album: a, track: t })}>Edit</button>
                  <button className="adm-link danger" type="button" onClick={() => remove("song", api.deleteTrack, t.id)}>Delete</button>
                </div>
              ))}
              <button className="btn btn-secondary" type="button" onClick={() => setEdit({ kind: "track", album: a })}>Add song</button>
            </div>
          )}
        </div>
      ))}
    </>
  );
}

/* ---------- inbox ---------- */
export function Inbox() {
  const [msgs, reload, error] = useLoad(api.adminMessages);
  return (
    <>
      <h1 className="adm-h">Inbox</h1>
      {error && <div className="form-status error">{error}</div>}
      {msgs && !msgs.length && <p className="adm-muted">No messages yet. Booking inquiries from the site land here.</p>}
      {msgs?.map((m) => (
        <article key={m.id} className={`adm-card adm-msg${m.read ? "" : " unread"}`}>
          <div className="adm-row">
            <div className="adm-grow"><b>{m.name}</b> <a className="adm-link" href={`mailto:${m.email}`}>{m.email}</a></div>
            <span className="adm-muted">{fmtDate(m.createdAt)}</span>
          </div>
          <p className="adm-body">{m.message}</p>
          <div className="adm-actions">
            <button className="adm-link" type="button" onClick={async () => { await api.markMessage(m.id, !m.read); reload(); }}>{m.read ? "Mark unread" : "Mark read"}</button>
            <a className="adm-link" href={`mailto:${m.email}?subject=Re: your inquiry`}>Reply</a>
            <button className="adm-link danger" type="button" onClick={async () => { if (window.confirm("Delete this message?")) { await api.deleteMessage(m.id); reload(); } }}>Delete</button>
          </div>
        </article>
      ))}
    </>
  );
}

/* ---------- fan list ---------- */
export function Fans() {
  const [subs, , error] = useLoad(api.adminSubscribers);
  const active = subs?.filter((s) => s.active).length ?? 0;
  return (
    <>
      <div className="adm-bar">
        <h1 className="adm-h">Fan list</h1>
        <button className="btn btn-secondary" type="button" onClick={() => api.downloadSubscribersCsv(false)}>Export CSV</button>
      </div>
      {error && <div className="form-status error">{error}</div>}
      {subs && <p className="adm-muted">{active} active · {subs.length - active} unsubscribed (never email those)</p>}
      <div className="adm-card">
        {subs?.map((s) => (
          <div className="adm-row" key={s.id}>
            <div className="adm-grow">{s.email}</div>
            <span className="adm-muted">{s.active ? fmtDate(s.createdAt) : "unsubscribed"}</span>
          </div>
        ))}
        {subs && !subs.length && <p className="adm-muted">Nobody has signed up yet.</p>}
      </div>
    </>
  );
}

/* ---------- account ---------- */
export function Account() {
  const [cur, setCur] = useState("");
  const [next, setNext] = useState("");
  const [msg, setMsg] = useState(null);
  async function submit(e) {
    e.preventDefault();
    try { await api.changePassword(cur, next); setMsg({ type: "success", message: "Password changed." }); setCur(""); setNext(""); }
    catch (x) { setMsg({ type: "error", message: x.message }); }
  }
  return (
    <>
      <h1 className="adm-h">Account</h1>
      <form className="adm-card adm-form" onSubmit={submit} style={{ maxWidth: 420 }}>
        {msg && <div className={`form-status ${msg.type}`} role="status">{msg.message}</div>}
        <Field label="Current password"><input type="password" autoComplete="current-password" required value={cur} onChange={(e) => setCur(e.target.value)} /></Field>
        <Field label="New password (10+ characters)"><input type="password" autoComplete="new-password" required minLength={10} value={next} onChange={(e) => setNext(e.target.value)} /></Field>
        <button className="btn" type="submit">Change password</button>
      </form>
    </>
  );
}

/* ---------- platform sync ---------- */
const SOURCE_INFO = {
  suno: { title: "Suno", gives: "songs, albums, artwork, plays", setup: "No keys needed. Reads your public Suno profile." },
  spotify: { title: "Spotify", gives: "Spotify links and cover art for matching songs", setup: "Add SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in Railway (the app owner needs Spotify Premium)." },
  soundcloud: { title: "SoundCloud", gives: "plays, followers, links, artwork", setup: "Add SOUNDCLOUD_CLIENT_ID and SOUNDCLOUD_CLIENT_SECRET in Railway (needs SoundCloud Artist Pro to register an app)." },
};
const STAT_LABELS = {
  suno_plays: "Suno plays", suno_songs: "Songs on Suno", suno_followers: "Suno followers",
  soundcloud_plays: "SoundCloud plays", soundcloud_followers: "SoundCloud followers",
  spotify_followers: "Spotify followers", spotify_monthly_listeners: "Spotify monthly listeners",
};

function ManualStat({ k, stat, onSaved }) {
  const [v, setV] = useState(stat ? String(stat.value) : "");
  const [err, setErr] = useState("");
  async function save(value) {
    setErr("");
    try { await api.setPlatformStat(k, value); await onSaved(); } catch (e) { setErr(e.message); }
  }
  return (
    <div className="adm-row">
      <div className="adm-grow">{STAT_LABELS[k]}<div className="adm-muted">{stat ? `${stat.source === "manual" ? "typed by you" : "from sync"} · ${fmtDate(stat.updatedAt)}` : "not set"}</div></div>
      <input className="adm-num" inputMode="numeric" value={v} onChange={(e) => setV(e.target.value.replace(/\D/g, ""))} placeholder="0" aria-label={STAT_LABELS[k]} />
      <button className="adm-link" type="button" disabled={v === ""} onClick={() => save(parseInt(v, 10))}>Save</button>
      {stat?.source === "manual" && <button className="adm-link" type="button" onClick={() => { setV(""); save(null); }}>Use sync</button>}
      {err && <span className="adm-muted" style={{ color: "#d0645a" }}>{err}</span>}
    </div>
  );
}

export function Sync() {
  const [d, reload, error] = useLoad(api.adminSync);
  const [busy, setBusy] = useState("");
  const [result, setResult] = useState({});

  async function run(name) {
    setBusy(name);
    try { const res = await api.runSync(name); setResult((r) => ({ ...r, [name]: res })); }
    catch (e) { setResult((r) => ({ ...r, [name]: { ok: false, summary: e.message, log: "" } })); }
    await reload();
    setBusy("");
  }

  return (
    <>
      <h1 className="adm-h">Sync</h1>
      <p className="adm-muted">Pulls songs, artwork and play counts from your platforms{d?.intervalHours ? ` every ${d.intervalHours} hours` : ""}. Titles, lyrics and anything you edited are never overwritten.</p>
      {error && <div className="form-status error">{error}</div>}
      {d?.sources.map((s) => {
        const info = SOURCE_INFO[s.name];
        const shown = result[s.name] || s.last;
        return (
          <div className="adm-card" key={s.name}>
            <div className="adm-row">
              <div className="adm-grow">
                <b>{info.title}</b> <span className="adm-muted">· {info.gives}</span>
                {!s.configured && <div className="adm-muted">Not set up. {info.setup}</div>}
              </div>
              <button className="btn btn-secondary" type="button" disabled={!s.configured || busy === s.name} onClick={() => run(s.name)}>
                {busy === s.name ? "Syncing…" : "Run now"}
              </button>
            </div>
            {shown && (
              <details className="adm-log">
                <summary className={shown.ok ? "" : "bad"}>
                  {shown.ok ? "✓" : "✕"} {shown.summary}{shown.at ? ` · ${fmtDate(shown.at)}` : ""}
                </summary>
                <pre>{shown.log || "No details."}</pre>
              </details>
            )}
          </div>
        );
      })}

      <h2 className="adm-h" style={{ fontSize: 20, marginTop: 28 }}>Numbers shown on the site</h2>
      <p className="adm-muted">Spotify does not share monthly listeners with apps. Copy the number from Spotify for Artists and type it here.</p>
      <div className="adm-card">
        {d && ["spotify_monthly_listeners", "spotify_followers", "suno_plays", "soundcloud_plays"].map((k) => (
          <ManualStat key={k + (d.stats[k]?.updatedAt || "")} k={k} stat={d.stats[k]} onSaved={reload} />
        ))}
      </div>
      {d && (
        <p className="adm-muted">
          Also tracked: {["suno_songs", "suno_followers", "soundcloud_followers"].filter((k) => d.stats[k]).map((k) => `${STAT_LABELS[k]} ${fmtCount(d.stats[k].value)}`).join(" · ") || "nothing yet, run a sync"}
        </p>
      )}
    </>
  );
}
