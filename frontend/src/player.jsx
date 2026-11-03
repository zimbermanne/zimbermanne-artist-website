import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { audioSrc, coverOf, DEFAULT_SLUG, fmtTime, hasAudio, isMobile, mp3Name, SUNO_PROFILE } from "./utils";

const PlayerCtx = createContext(null);
const TimeCtx = createContext({ cur: 0, dur: 0 });
export const usePlayer = () => useContext(PlayerCtx);
export const useTime = () => useContext(TimeCtx);

/* icons */
const Svg = ({ children, ...p }) => <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" {...p}>{children}</svg>;
export const IconPlay = (p) => <Svg className="ico-play" {...p}><path fill="currentColor" d="M8 5v14l11-7z" /></Svg>;
export const IconPause = (p) => <Svg className="ico-pause" {...p}><path fill="currentColor" d="M6 5h4v14H6zm8 0h4v14h-4z" /></Svg>;
const IconPrev = (p) => <Svg {...p}><path fill="currentColor" d="M6 6h2v12H6zm3.5 6l8.5 6V6z" /></Svg>;
const IconNext = (p) => <Svg {...p}><path fill="currentColor" d="M16 6h2v12h-2zM6 18l8.5-6L6 6z" /></Svg>;
const IconDown = (p) => (
  <Svg {...p}><path fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" d="M6 9l6 6 6-6" /></Svg>
);

export function PlayerProvider({ albums, children }) {
  const audioRef = useRef(null);
  if (!audioRef.current && typeof Audio !== "undefined") {
    audioRef.current = new Audio();
    audioRef.current.preload = "none";
    audioRef.current.crossOrigin = "anonymous";
  }

  const queue = useMemo(() => albums.flatMap((album) => album.tracks.map((track) => ({ track, album }))), [albums]);
  const [current, setCurrent] = useState(null);
  const [activeSlug, setActiveSlug] = useState(null);
  const [playing, setPlaying] = useState(false);
  const [time, setTime] = useState({ cur: 0, dur: 0 });
  const [expanded, setExpandedState] = useState(false);
  const [lyricsItem, setLyricsItem] = useState(null);

  useEffect(() => {
    if (!current && queue.length) setCurrent(queue.find((q) => q.track.slug === DEFAULT_SLUG) || queue[0]);
  }, [queue, current]);

  const play = useCallback((item) => {
    const a = audioRef.current;
    if (!a) return;
    if (a.src && activeSlug === item.track.slug) { a.paused ? a.play().catch(() => {}) : a.pause(); return; }
    const src = audioSrc(item.track);
    if (!src) return;
    setCurrent(item);
    setActiveSlug(item.track.slug);
    setTime({ cur: 0, dur: 0 });
    a.src = src;
    a.play().catch(() => setPlaying(false));
  }, [activeSlug]);

  const toggle = useCallback(() => {
    const a = audioRef.current;
    if (!a || !current) return;
    if (!a.src) { play(current); return; }
    a.paused ? a.play().catch(() => {}) : a.pause();
  }, [current, play]);

  const skip = useCallback((dir) => {
    const a = audioRef.current;
    if (!queue.length) return;
    if (dir < 0 && a && a.currentTime > 3) { a.currentTime = 0; return; }
    const i = queue.findIndex((q) => current && q.track.slug === current.track.slug);
    const next = i < 0 ? (dir > 0 ? 0 : queue.length - 1) : (i + dir + queue.length) % queue.length;
    setActiveSlug(null);
    if (a) a.removeAttribute("src");
    play(queue[next]);
  }, [queue, current, play]);

  const seekTo = useCallback((f) => {
    const a = audioRef.current;
    if (a && Number.isFinite(a.duration)) a.currentTime = Math.min(1, Math.max(0, f)) * a.duration;
  }, []);
  const seekBy = useCallback((s) => { const a = audioRef.current; if (a) a.currentTime = Math.max(0, a.currentTime + s); }, []);
  const setExpanded = useCallback((v) => setExpandedState(v && isMobile()), []);
  const openLyrics = useCallback((item) => setLyricsItem(item), []);
  const closeLyrics = useCallback(() => setLyricsItem(null), []);

  const live = useRef({});
  live.current = { skip, seekBy, queueLength: queue.length };

  useEffect(() => {
    const a = audioRef.current;
    if (!a) return;
    let last = 0;
    const pos = () => {
      if (!("mediaSession" in navigator) || !navigator.mediaSession.setPositionState || !Number.isFinite(a.duration)) return;
      try { navigator.mediaSession.setPositionState({ duration: a.duration, playbackRate: a.playbackRate, position: a.currentTime }); } catch (e) { /* ignore */ }
    };
    const h = {
      play: () => setPlaying(true),
      pause: () => setPlaying(false),
      error: () => setPlaying(false),
      loadedmetadata: () => { setTime({ cur: 0, dur: a.duration || 0 }); pos(); },
      timeupdate: () => { setTime({ cur: a.currentTime, dur: a.duration || 0 }); if (Date.now() - last > 1000) { last = Date.now(); pos(); } },
      ended: () => { setPlaying(false); if (live.current.queueLength > 1) live.current.skip(1); },
    };
    Object.entries(h).forEach(([e, f]) => a.addEventListener(e, f));
    return () => Object.entries(h).forEach(([e, f]) => a.removeEventListener(e, f));
  }, []);

  useEffect(() => {
    if (!("mediaSession" in navigator)) return;
    const ms = navigator.mediaSession, a = audioRef.current;
    const set = (k, f) => { try { ms.setActionHandler(k, f); } catch (e) { /* ignore */ } };
    set("play", () => a.play());
    set("pause", () => a.pause());
    set("previoustrack", () => live.current.skip(-1));
    set("nexttrack", () => live.current.skip(1));
    set("seekbackward", () => live.current.seekBy(-10));
    set("seekforward", () => live.current.seekBy(10));
    set("seekto", (d) => { if (d.seekTime != null) a.currentTime = d.seekTime; });
  }, []);

  useEffect(() => {
    if (!current || !("mediaSession" in navigator) || typeof MediaMetadata === "undefined") return;
    navigator.mediaSession.metadata = new MediaMetadata({
      title: current.track.title, artist: "Zimbermanne", album: current.album.title,
      artwork: [{ src: coverOf(current), sizes: "512x512" }],
    });
  }, [current]);

  useEffect(() => {
    document.body.classList.toggle("player-open", expanded);
    return () => document.body.classList.remove("player-open");
  }, [expanded]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") (lyricsItem ? setLyricsItem(null) : setExpandedState(false)); };
    const onResize = () => { if (!isMobile()) setExpandedState(false); };
    window.addEventListener("keydown", onKey);
    window.addEventListener("resize", onResize);
    return () => { window.removeEventListener("keydown", onKey); window.removeEventListener("resize", onResize); };
  }, [lyricsItem]);

  const value = useMemo(() => ({
    queue, current, activeSlug, playing, expanded, lyricsItem,
    play, toggle, skip, seekTo, seekBy, setExpanded, openLyrics, closeLyrics,
  }), [queue, current, activeSlug, playing, expanded, lyricsItem, play, toggle, skip, seekTo, seekBy, setExpanded, openLyrics, closeLyrics]);

  return <PlayerCtx.Provider value={value}><TimeCtx.Provider value={time}>{children}</TimeCtx.Provider></PlayerCtx.Provider>;
}

export function DownloadButton({ track, className, children = "MP3", ...rest }) {
  const [label, setLabel] = useState(null);
  const busy = useRef(false);
  if (!hasAudio(track)) return null;
  const href = `/download/${track.slug}.mp3`;

  async function onClick(e) {
    e.preventDefault();
    if (busy.current) return;
    busy.current = true;
    setLabel("Preparing…");
    try {
      const res = await fetch(href);
      if (!res.ok) throw new Error("HTTP " + res.status);
      const total = parseInt(res.headers.get("Content-Length"), 10) || 0;
      const reader = res.body.getReader();
      const chunks = [];
      let got = 0;
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
        got += value.length;
        setLabel(total ? Math.round((got / total) * 100) + "%" : (got / 1048576).toFixed(1) + " MB");
      }
      if (total && got !== total) throw new Error("Incomplete download");
      setLabel("Saving…");
      const url = URL.createObjectURL(new Blob(chunks, { type: "audio/mpeg" }));
      const a = Object.assign(document.createElement("a"), { href: url, download: mp3Name(track) });
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
      setLabel("Saved ✓");
    } catch (err) {
      setLabel("Failed, retry");
    }
    setTimeout(() => { setLabel(null); busy.current = false; }, 2500);
  }

  return <a className={className} href={href} download onClick={onClick} aria-busy={label ? "true" : undefined} {...rest}>{label ?? children}</a>;
}

function Seekable({ className, children, ...rest }) {
  const { seekTo } = usePlayer();
  const dragging = useRef(false);
  const seek = (e) => { const r = e.currentTarget.getBoundingClientRect(); seekTo((e.clientX - r.left) / r.width); };
  return (
    <div {...rest} className={className}
      onPointerDown={(e) => { dragging.current = true; e.currentTarget.setPointerCapture(e.pointerId); seek(e); }}
      onPointerMove={(e) => { if (dragging.current) seek(e); }}
      onPointerUp={() => { dragging.current = false; }}
      onPointerCancel={() => { dragging.current = false; }}>
      {children}
    </div>
  );
}

export function PlayerBar() {
  const { current, playing, expanded, setExpanded, toggle, skip, seekBy, openLyrics } = usePlayer();
  const { cur, dur } = useTime();
  if (!current) return null;
  const { track, album } = current;
  const pct = dur ? Math.min(100, (cur / dur) * 100) : 0;

  return (
    <div className={`player-bar${playing ? " is-playing" : ""}${expanded ? " expanded" : ""}`} role="region" aria-label="Music player">
      <Seekable className="mini-progress" aria-hidden="true"><div className="mini-fill" style={{ width: pct + "%" }} /></Seekable>
      <button className="sheet-close" type="button" aria-label="Close full player" onClick={() => setExpanded(false)}><IconDown /></button>
      <button className="player-now-playing" type="button" aria-expanded={expanded}
        aria-label={expanded ? "Full player" : "Open full player"} onClick={() => { if (!expanded) setExpanded(true); }}>
        <img className="player-cover" src={coverOf(current)} alt="" />
        <span className="player-details">
          <span className="player-track-name">{track.title}</span>
          <span className="player-album-name">{album.title}</span>
        </span>
      </button>
      <div className="player-controls">
        <div className="transport">
          <button className="skip-btn" type="button" aria-label="Previous song" onClick={() => skip(-1)}><IconPrev /></button>
          <button className="play-btn-large" type="button" aria-label={playing ? "Pause" : "Play"} onClick={toggle}><IconPlay /><IconPause /></button>
          <button className="skip-btn" type="button" aria-label="Next song" onClick={() => skip(1)}><IconNext /></button>
        </div>
        <div className="progress-bar-wrap">
          <Seekable className="progress-bar" role="slider" tabIndex={0} aria-label="Seek" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)}
            onKeyDown={(e) => { if (e.key === "ArrowRight") { seekBy(5); e.preventDefault(); } if (e.key === "ArrowLeft") { seekBy(-5); e.preventDefault(); } }}>
            <div className="progress-fill" style={{ width: pct + "%" }} />
          </Seekable>
          <div className="time-display"><span>{fmtTime(cur)}</span><span>{fmtTime(dur)}</span></div>
        </div>
      </div>
      <div className="player-right-actions">
        <button className="btn-lyrics" type="button" onClick={() => openLyrics(current)}>Lyrics</button>
        <DownloadButton track={track} className="btn-lyrics" title="Download as MP3" />
        <a className="btn btn-secondary" href={track.url || SUNO_PROFILE} target="_blank" rel="noopener noreferrer">Stream on Suno ↗</a>
      </div>
    </div>
  );
}

export function LyricsModal() {
  const { lyricsItem: it, closeLyrics } = usePlayer();
  return (
    <div className={`modal-overlay${it ? " active" : ""}`} onClick={(e) => { if (e.target === e.currentTarget) closeLyrics(); }}>
      <div className="modal-card" role="dialog" aria-modal="true" aria-label="Lyrics">
        <div className="modal-header">
          <div>
            <h4>{it ? it.track.title : ""}</h4>
            <span style={{ fontSize: 12, color: "var(--gold)" }}>{it ? it.album.title : ""}</span>
          </div>
          <button className="close-btn" type="button" aria-label="Close lyrics" onClick={closeLyrics}>×</button>
        </div>
        <div className="modal-body">{it ? it.track.lyrics || "Lyrics coming soon." : ""}</div>
        <div className="modal-footer">
          <span style={{ fontSize: 12, color: "var(--muted)" }}>Zimbermanne · Afro Soul Pop</span>
          <a className="btn" href={it?.track.url || SUNO_PROFILE} target="_blank" rel="noopener noreferrer" style={{ padding: "8px 16px", fontSize: 11 }}>Open in Suno ↗</a>
        </div>
      </div>
    </div>
  );
}
