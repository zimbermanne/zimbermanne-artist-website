import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { IconPause, IconPlay, usePlayer } from "./player";
import { fmtCount, SUNO_PROFILE } from "./utils";

// The hover showcase needs room and a mouse: wide screens only. Phones and tablets keep the album list.
const QUERY = "(min-width: 1000px) and (hover: hover)";

export function useShowcaseSupported() {
  const [ok, setOk] = useState(() => typeof window !== "undefined" && window.matchMedia(QUERY).matches);
  useEffect(() => {
    const m = window.matchMedia(QUERY);
    const onChange = () => setOk(m.matches);
    onChange();
    m.addEventListener("change", onChange);
    return () => m.removeEventListener("change", onChange);
  }, []);
  return ok;
}

const plays = (t) => Object.values(t.plays || {}).reduce((a, b) => a + b, 0);

const Icon = ({ children }) => (
  <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{children}</svg>
);
const TABS = [
  ["about", "About", <Icon key="a"><circle cx="12" cy="12" r="9" /><path d="M12 11v6M12 7.5v.01" /></Icon>],
  ["tracks", "Tracks", <Icon key="t"><path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01" /></Icon>],
  ["listen", "Listen", <Icon key="l"><path d="M4 14v-2a8 8 0 0 1 16 0v2" /><rect x="3" y="14" width="4" height="6" rx="1.5" /><rect x="17" y="14" width="4" height="6" rx="1.5" /></Icon>],
];

export function AlbumShowcase({ album }) {
  const { activeSlug, playing, play } = usePlayer();
  const [tab, setTab] = useState("tracks");
  const tracks = album.tracks;
  const total = tracks.reduce((s, t) => s + plays(t), 0);
  const top = [...tracks].sort((a, b) => plays(b) - plays(a)).slice(0, 3); // stable: equal plays keep album order
  const item = (t) => ({ track: t, album });
  const panelId = `${album.id}-panel`;

  return (
    <article className="ac" id={album.id} aria-label={album.title}>
      <div className="ac-art">
        <img src={album.cover} alt={`${album.title} cover`} width="600" height="600" decoding="async" />
        <div className="ac-title">
          <span className="ac-no">{album.number}</span>
          <h3>{album.title}</h3>
        </div>
        {album.tagline && <p className="ac-quote">{album.tagline}</p>}
        {!!(album.chips || []).length && <div className="ac-caption">{album.chips.join(" · ")}</div>}
      </div>

      <div className="ac-tabs" role="tablist" aria-label={`${album.title} details`}>
        {TABS.map(([key, label, icon]) => (
          <button key={key} type="button" role="tab" className="ac-tab" id={`${album.id}-tab-${key}`}
            aria-selected={tab === key} aria-controls={panelId} aria-label={label} onClick={() => setTab(key)}>
            {icon}
            <span className="ac-tip" aria-hidden="true">{label}</span>
          </button>
        ))}
      </div>

      <div className="ac-panel" role="tabpanel" id={panelId} aria-labelledby={`${album.id}-tab-${tab}`} tabIndex={0}>
        {tab === "about" && (
          <>
            <p>{album.description}</p>
            <div className="ac-chips">{(album.chips || []).map((c) => <span key={c}>{c}</span>)}</div>
            <p className="ac-stat">{tracks.length} songs{total > 0 ? ` · ${fmtCount(total)} plays` : ""}</p>
          </>
        )}
        {tab === "tracks" && (
          <ol className="ac-tracks">
            {tracks.map((t) => {
              const on = activeSlug === t.slug;
              const isPlaying = on && playing;
              return (
                <li key={t.slug} className={on ? "now-playing" : undefined}>
                  <div className="ac-ti">
                    <Link to={`/song/${t.slug}`}>{t.title}</Link>
                    {t.subtitle && <small>{t.subtitle}</small>}
                  </div>
                  <button type="button" className="ac-play" aria-label={`${isPlaying ? "Pause" : "Play"} ${t.title}`} onClick={() => play(item(t))}>
                    {isPlaying ? <IconPause /> : <IconPlay />}
                  </button>
                </li>
              );
            })}
          </ol>
        )}
        {tab === "listen" && (
          <div className="ac-links">
            {tracks[0] && <button type="button" className="ac-btn" onClick={() => play(item(tracks[0]))}>Play the album</button>}
            {tracks[0] && <Link className="ac-btn" to={`/song/${tracks[0].slug}`}>Open first song</Link>}
            <a className="ac-btn" href={SUNO_PROFILE} target="_blank" rel="noopener noreferrer">More on Suno ↗</a>
          </div>
        )}
      </div>

      {top.map((t, i) => (
        <button key={t.slug} type="button" className={`ac-tile ac-tile-${i + 1}`}
          style={{ backgroundImage: `url("${t.image || album.cover}")` }}
          aria-label={`Play ${t.title}`} onClick={() => play(item(t))}>
          <span className="ac-tile-title">{t.title}</span>
          <span className="ac-tile-meta">{plays(t) > 0 ? `${fmtCount(plays(t))} plays` : "Play"}</span>
        </button>
      ))}
    </article>
  );
}
