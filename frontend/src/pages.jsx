import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getSong, unsubscribe, unsubscribeInfo } from "./api";
import { ContactForm, Discography, FormStatus, SubscribeForm } from "./components";
import { DownloadButton, usePlayer } from "./player";
import { coverOf, SUNO_PROFILE, useTitle } from "./utils";

export function Home({ albums, failed, whatsappUrl }) {
  useTitle("Zimbermanne — Afro Soul Pop Artist | Official Website");
  return (
    <>
      <header className="hero">
        <div className="kicker">A Soulful Afro Soul Pop Artist</div>
        <h1>Zimbermanne</h1>
        <div className="script">Love. Rhythm. Connection.</div>
        <p>Music that moves between the warmth of a city night and the cold drama of a winter story, always led by the soul.</p>
        <div style={{ display: "flex", justifyContent: "center", gap: 16, flexWrap: "wrap" }}>
          <Link className="btn" to="/#albums">Explore Discography</Link>
          <a className="btn btn-secondary" href={SUNO_PROFILE} target="_blank" rel="noopener noreferrer">Listen on Suno ↗</a>
        </div>
      </header>

      <section id="about">
        <div className="about">
          <div>
            <h2><small>The Artist</small>Feel the soul</h2>
            <p>Zimbermanne is a music artist making Afro Soul Pop: smooth, melodic records built on groove, emotion and storytelling. His work speaks about love, rhythm and the connection between people, wrapped in a refined, cinematic style.</p>
            <p>Each record is its own world. One glows with late-night city lights and romance; another steps into a snow-covered, mysterious chapter of diary-style confession; while the latest explores ambition, wealth, and industrial soul.</p>
          </div>
          <div className="pillars">
            <div><strong>Love</strong>Honest, grown-up songs about the heart.</div>
            <div><strong>Rhythm</strong>Afro-flavoured grooves with a soul and pop finish.</div>
            <div><strong>Connection</strong>Music that brings listeners close to the story.</div>
          </div>
        </div>
      </section>

      <section id="story" className="story">
        <h2><small>His Story</small>Just a listener, once</h2>
        <p>Zimbermanne did not begin as a star. He began exactly where you are now: a listener with headphones on, letting other people’s songs carry him through long days, quiet nights and the moments words failed him.</p>
        <p>Music was always there. It held him when he was happy, and it sat beside him when he was not. Somewhere between one song and the next, he started to notice something: there were things he wished he could tell the world. Things about love and loss, about hard work and hope, about the struggles people carry in silence and the dreams they are afraid to say aloud.</p>
        <blockquote>If I have something to say, why keep it inside?</blockquote>
        <p>Today, every record is a letter to society, written in rhythm and soul. Some are tender, some are bold, and some carry the weight of stories people rarely hear. And behind each one is still that same listener, hoping that somewhere, someone presses play and feels a little less alone.</p>
      </section>

      <Discography albums={albums} failed={failed} />
      <SubscribeForm />
      <ContactForm whatsappUrl={whatsappUrl} />
    </>
  );
}

export function NotFound({ title = "Page not found", text = "We couldn't find that page." }) {
  useTitle(`${title} — Zimbermanne`);
  return (
    <section className="notice">
      <h2>{title}</h2>
      <p>{text}</p>
      <p><Link className="btn btn-secondary" to="/">Back to the music</Link></p>
    </section>
  );
}

export function SongPage() {
  const { slug } = useParams();
  const [data, setData] = useState(undefined); // undefined = loading, null = missing
  const [copied, setCopied] = useState(false);
  const { activeSlug, playing, play } = usePlayer();

  useEffect(() => {
    let alive = true;
    setData(undefined);
    getSong(slug).then((d) => alive && setData(d)).catch(() => alive && setData(null));
    return () => { alive = false; };
  }, [slug]);

  useTitle(data ? `${data.track.title} — Zimbermanne | ${data.album.title}` : null);

  if (data === undefined) return <p className="loading-note">Loading…</p>;
  if (data === null) return <NotFound title="Song not found" text="We couldn't find that song." />;

  const { track, album, prev, next } = data;
  const item = { track, album };
  const isPlaying = activeSlug === track.slug && playing;
  const shareUrl = `${window.location.origin}/song/${track.slug}`;

  async function share() {
    const payload = { title: `${track.title} — Zimbermanne`, url: shareUrl };
    if (navigator.share) { navigator.share(payload).catch(() => {}); return; }
    try { await navigator.clipboard.writeText(shareUrl); setCopied(true); setTimeout(() => setCopied(false), 2000); }
    catch (e) { window.prompt("Copy this link:", shareUrl); }
  }

  return (
    <main className="song">
      <div className="song-cover"><img src={coverOf(item)} alt={`${album.title} cover`} width="600" height="600" decoding="async" /></div>
      <div className="song-body">
        <div className="tag">{album.number} · {album.title}</div>
        <h1>{track.title}</h1>
        {track.subtitle && <div className="album-tagline">{track.subtitle}</div>}
        <div className="song-meta">Zimbermanne · {album.tagline}{track.duration ? ` · ${track.duration}` : ""}</div>
        <div className="song-actions">
          <button className="btn" type="button" onClick={() => play(item)}>{isPlaying ? "Pause" : "Play"}</button>
          {track.url && <a className="btn btn-secondary" href={track.url} target="_blank" rel="noopener noreferrer">Stream on Suno ↗</a>}
          <DownloadButton track={track} className="btn btn-secondary">Download MP3</DownloadButton>
          <button className="btn btn-secondary" type="button" onClick={share}>{copied ? "Link copied ✓" : "Share"}</button>
        </div>
        {track.lyrics && (<><h2 className="lyrics-heading"><small>Lyrics</small></h2><div className="song-lyrics">{track.lyrics}</div></>)}
        <nav className="song-nav" aria-label="More songs">
          {prev ? <Link to={`/song/${prev.slug}`}>← {prev.title}</Link> : <span />}
          {next && <Link to={`/song/${next.slug}`}>{next.title} →</Link>}
        </nav>
      </div>
    </main>
  );
}

export function UnsubscribePage() {
  const { token } = useParams();
  const [info, setInfo] = useState(undefined);
  const [result, setResult] = useState(null);
  useTitle("Unsubscribe — Zimbermanne");
  useEffect(() => { unsubscribeInfo(token).then(setInfo).catch(() => setInfo({ valid: false })); }, [token]);

  if (info === undefined) return <p className="loading-note">Loading…</p>;
  if (!info.valid) return <NotFound title="Link not valid" text="This unsubscribe link is not valid." />;
  return (
    <section className="notice">
      <h2>Leave the fan list</h2>
      <FormStatus result={result} />
      {!result && (info.active
        ? <><p>Do you want to stop getting emails about new songs?</p>
            <button className="btn" type="button" onClick={async () => setResult(await unsubscribe(token))}>Yes, unsubscribe me</button></>
        : <p>You are already off the list.</p>)}
      <p><Link className="btn btn-secondary" to="/">Back to the music</Link></p>
    </section>
  );
}
