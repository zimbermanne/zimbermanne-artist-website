import React, { useState } from "react";
import { Link } from "react-router-dom";
import { sendContact, subscribe } from "./api";
import { DownloadButton, IconPause, IconPlay, usePlayer } from "./player";
import { fmtCount, SUNO_PROFILE } from "./utils";

/* ---- layout ---- */
export function Nav({ home, views }) {
  return (
    <nav>
      <Link to="/" className="brand"><b>Zimbermanne</b></Link>
      <div className="nav-links">
        {home && <Link to="/#about">About</Link>}
        {home && <Link to="/#story">Story</Link>}
        <Link to="/#albums">Albums</Link>
        <Link to="/#subscribe">Fan list</Link>
        <Link to="/#contact">Contact</Link>
        {home && <span className="visitor-badge">👁️ <span className="view-num">{views ?? "…"}</span> Views</span>}
      </div>
    </nav>
  );
}

export function Footer({ views }) {
  return (
    <footer>
      © {new Date().getFullYear()} Zimbermanne · Feel the soul
      {views != null && <span className="footer-views"><span className="footer-num">{views}</span> Total Views</span>}
    </footer>
  );
}

/* ---- discography ---- */
const totalPlays = (t) => Object.values(t.plays || {}).reduce((a, b) => a + b, 0);

function TrackRow({ item }) {
  const { track } = item;
  const { activeSlug, playing, play, openLyrics } = usePlayer();
  const isCurrent = activeSlug === track.slug;
  const isPlaying = isCurrent && playing;
  return (
    <li className={isCurrent ? "now-playing" : undefined}>
      <div className="track-info">
        <Link className="track-title" to={`/song/${track.slug}`}>{track.title}</Link>
        {track.subtitle && <span className="track-subtitle">{track.subtitle}</span>}
        {totalPlays(track) > 0 && <span className="track-plays">{fmtCount(totalPlays(track))} plays</span>}
      </div>
      <div className="track-actions">
        <button className="btn-lyrics" type="button" onClick={() => openLyrics(item)}>Lyrics</button>
        <DownloadButton track={track} className="btn-lyrics" title="Download as MP3" aria-label={`Download ${track.title} as MP3`} />
        <button className={`btn-icon${isPlaying ? " is-active" : ""}`} type="button"
          aria-label={`${isPlaying ? "Pause" : "Play"} ${track.title}`} onClick={() => play(item)}>
          {isPlaying ? <IconPause style={{ display: "block" }} /> : <IconPlay style={{ display: "block" }} />}
        </button>
      </div>
    </li>
  );
}

function Album({ album, index }) {
  return (
    <article className={`album${index % 2 === 1 ? " rev" : ""}`} id={album.id}>
      <div className="cover">
        <img src={album.cover} alt={`${album.title} cover`} width="600" height="600" decoding="async" loading={index === 0 ? "eager" : "lazy"} />
      </div>
      <div>
        <div className="tag">{album.number}</div>
        <h3>{album.title}</h3>
        <div className="album-tagline">{album.tagline}</div>
        <p>{album.description}</p>
        <div className="chips">{(album.chips || []).map((c) => <span key={c}>{c}</span>)}</div>
        <ol className="tracks">{album.tracks.map((t) => <TrackRow key={t.slug} item={{ track: t, album }} />)}</ol>
      </div>
    </article>
  );
}

export function Discography({ albums, failed }) {
  return (
    <section id="albums">
      <div className="album-header-bar">
        <h2><small>Discography</small>Featured Albums</h2>
        <a href={SUNO_PROFILE} target="_blank" rel="noopener noreferrer" className="btn btn-secondary" style={{ padding: "10px 20px", fontSize: 11 }}>View All on Suno ↗</a>
      </div>
      <div id="albumsContainer">
        {albums.map((a, i) => <Album key={a.id} album={a} index={i} />)}
        {!albums.length && <p className="loading-note">{failed ? "The albums could not be loaded. Please refresh the page." : "Loading the music…"}</p>}
      </div>
    </section>
  );
}

/* ---- forms ---- */
const honeypot = { position: "absolute", left: -9999, height: 0, width: 0, opacity: 0 };

export function FormStatus({ result }) {
  return result ? <div className={`form-status ${result.type}`} role="status">{result.message}</div> : null;
}

export function SubscribeForm() {
  const [email, setEmail] = useState("");
  const [website, setWebsite] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    const res = await subscribe({ email, website });
    setResult(res);
    if (res.ok) setEmail("");
    setBusy(false);
  }

  return (
    <section className="subscribe" id="subscribe">
      <h2><small>Stay close</small>New songs, first</h2>
      <p>Leave your email and get a short note when a new song or album is out. No spam, and you can leave anytime.</p>
      <FormStatus result={result} />
      <form className="subscribe-form" onSubmit={onSubmit}>
        <input type="email" placeholder="Your email address" required maxLength={254} aria-label="Email address" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input type="text" tabIndex={-1} autoComplete="off" aria-hidden="true" style={honeypot} value={website} onChange={(e) => setWebsite(e.target.value)} />
        <button type="submit" className="btn" disabled={busy}>{busy ? "Sending…" : "Notify me"}</button>
      </form>
    </section>
  );
}

const SOCIALS = [
  ["Spotify", "https://open.spotify.com/search/zimbermanne", "@zimbermanne"],
  ["Deezer", "https://www.deezer.com/search/zimbermanne", "@zimbermanne"],
  ["Instagram", "https://www.instagram.com/zimbermanne", "@zimbermanne"],
  ["TikTok", "https://www.tiktok.com/@zimbermanne", "@zimbermanne"],
  ["Facebook", "https://www.facebook.com/zimbermanne", "@zimbermanne"],
  ["SoundCloud", "https://soundcloud.com/zimbermann-elit", "zimbermann-elit"],
];

export function ContactForm({ whatsappUrl }) {
  const empty = { name: "", email: "", message: "", website: "" };
  const [f, setF] = useState(empty);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const set = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));

  async function onSubmit(e) {
    e.preventDefault();
    setBusy(true);
    const res = await sendContact(f);
    setResult(res);
    if (res.ok) setF(empty);
    setBusy(false);
  }

  return (
    <section className="contact" id="contact">
      <h2><small>Get in touch</small>Bookings &amp; Inquiries</h2>
      <p>Listen, follow and stay close to the music. For shows, collaborations and press, reach out.</p>
      <FormStatus result={result} />
      <form className="contact-form" onSubmit={onSubmit}>
        <input type="text" placeholder="Your Name or Promoter Name" required maxLength={120} value={f.name} onChange={set("name")} />
        <input type="email" placeholder="Your Email Address" required maxLength={254} value={f.email} onChange={set("email")} />
        <textarea rows={5} placeholder="Booking inquiry, show details, or message..." required maxLength={5000} value={f.message} onChange={set("message")} />
        <input type="text" tabIndex={-1} autoComplete="off" aria-hidden="true" style={honeypot} value={f.website} onChange={set("website")} />
        <button type="submit" className="btn" disabled={busy}>{busy ? "Sending…" : "Send Booking Inquiry"}</button>
      </form>
      {whatsappUrl && <p className="whatsapp-wrap"><a className="btn btn-whatsapp" href={whatsappUrl} target="_blank" rel="noopener noreferrer">Book on WhatsApp</a></p>}
      <div className="social">
        {SOCIALS.map(([n, href, handle]) => <a key={n} href={href} target="_blank" rel="noopener noreferrer">{n}<span>{handle}</span></a>)}
        <a href={SUNO_PROFILE} target="_blank" rel="noopener noreferrer" style={{ borderColor: "var(--gold)", color: "var(--gold)" }}>Suno AI<span>@zimbermannelit</span></a>
      </div>
    </section>
  );
}

/* ---- listeners + platforms ---- */
export function ListenerStats({ stats = {} }) {
  const plays = (stats.suno_plays || 0) + (stats.soundcloud_plays || 0);
  const items = [
    [plays, "Total plays"],
    [stats.spotify_monthly_listeners, "Spotify monthly listeners"],
    [(stats.spotify_followers || 0) + (stats.soundcloud_followers || 0) + (stats.suno_followers || 0), "Followers"],
    [stats.suno_songs, "Songs"],
  ].filter(([v]) => v > 0);
  if (!items.length) return null;
  return (
    <section className="listener-stats" aria-label="Listener numbers">
      {items.map(([v, label]) => <div key={label}><b>{fmtCount(v)}</b><span>{label}</span></div>)}
    </section>
  );
}

export function ListenEverywhere({ site }) {
  const sc = site.soundcloudUrl;
  return (
    <section id="listen" className="listen">
      <h2><small>Listen</small>Everywhere you stream</h2>
      <div className="listen-grid">
        {site.spotifyArtistId && (
          <iframe title="Zimbermanne on Spotify" data-testid="embed-iframe" style={{ borderRadius: 12 }}
            src={`https://open.spotify.com/embed/artist/${site.spotifyArtistId}?utm_source=generator`}
            width="100%" height="352" frameBorder="0" allowFullScreen
            allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy" />
        )}
        {sc && (
          <iframe title="Zimbermanne on SoundCloud" width="100%" height="352" scrolling="no" frameBorder="no" loading="lazy"
            style={{ borderRadius: 12 }} allow="autoplay"
            src={`https://w.soundcloud.com/player/?url=${encodeURIComponent(sc)}&color=%23c9a24b&auto_play=false&hide_related=true&show_comments=false&show_user=true&show_reposts=false&show_teaser=false&visual=false`} />
        )}
      </div>
    </section>
  );
}
