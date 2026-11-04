import { useEffect } from "react";

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

export const SUNO_PROFILE = "https://suno.com/@zimbermannelit";
export const DEFAULT_SLUG = "pesa-inaongea-sana";

export const coverOf = ({ track, album }) => track.image || album.cover;
export const hasAudio = (t) => !!(t.url || t.audioUrl);

export function audioSrc(t) {
  if (t.audioUrl) return t.audioUrl;
  const m = UUID.exec(t.url || "");
  return m ? `https://cdn1.suno.ai/${m[0]}.mp4` : null;
}

export const mp3Name = (t) =>
  `${t.title}${t.subtitle ? " " + t.subtitle : ""}`.replace(/[^\w .()'&-]+/g, "").trim() + " - Zimbermanne.mp3";

export function fmtTime(s) {
  if (!Number.isFinite(s)) return "0:00";
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec < 10 ? "0" : ""}${sec}`;
}

export const isMobile = () => window.matchMedia("(max-width: 768px)").matches;

export function useTitle(title) {
  useEffect(() => { if (title) document.title = title; }, [title]);
}

export const fmtDate = (iso) =>
  new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

export function fmtCount(n) {
  if (n == null) return "";
  if (n >= 1e6) return (n / 1e6).toFixed(n >= 1e7 ? 0 : 1).replace(/\.0$/, "") + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(n >= 1e4 ? 0 : 1).replace(/\.0$/, "") + "K";
  return String(n);
}
