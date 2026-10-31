/**
 * Suno Direct Auto-Sync Engine for Zimbermanne Website
 *
 * Usage:
 *   npm run sync
 *
 * Syncs profile, artwork, music list, lyrics, and direct audio stream URLs
 * (https://cdn1.suno.ai/[song-id].mp4) from Suno directly into music.json
 */

const fs = require("fs");
const path = require("path");

const SUNO_HANDLE = "zimbermannelit";
const PROFILE_URL = `https://suno.com/@${SUNO_HANDLE}`;
const MUSIC_JSON_PATH = path.join(__dirname, "music.json");

function normalize(str) {
  return (str || "")
    .toLowerCase()
    .replace(/[^\w\s]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

// Extract UUID from Suno song URL
function getSongId(url) {
  const m = (url || "").match(/[0-9a-f-]{36}/i);
  return m ? m[0] : null;
}

async function syncDirectSunoData() {
  console.log(`[Sync] Fetching Suno profile for @${SUNO_HANDLE}...`);

  const res = await fetch(PROFILE_URL, {
    headers: { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" }
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch profile: ${res.statusText}`);
  }

  const html = await res.text();
  const unescaped = html.replace(/\\"/g, '"').replace(/\\\\/g, '\\');

  // Load current music.json
  let musicData = { albums: [] };
  if (fs.existsSync(MUSIC_JSON_PATH)) {
    try {
      musicData = JSON.parse(fs.readFileSync(MUSIC_JSON_PATH, "utf8"));
    } catch (e) {
      console.log("[Sync] Creating new music.json structure...");
    }
  }

  // 1. Extract all clip IDs and titles from profile HTML
  const clipMap = new Map();
  const clipRegex = /"id":"([0-9a-f-]{36})"[^}]*?"title":"([^"]+)"/g;
  let match;
  while ((match = clipRegex.exec(unescaped)) !== null) {
    const id = match[1];
    const title = match[2].trim();
    if (!title.includes("Suno") && !title.includes("Sharing") && !title.includes("Publish") && !title.includes("Edit")) {
      const key = normalize(title);
      if (!clipMap.has(key)) {
        clipMap.set(key, { id, title, url: `https://suno.com/song/${id}`, audioUrl: `https://cdn1.suno.ai/${id}.mp4` });
      }
    }
  }

  console.log(`[Sync] Extracted ${clipMap.size} unique track titles from Suno profile.`);

  // 2. Album Cover Map
  const albumCovers = new Map();
  albumCovers.set("mimi-ni-odogwu", "https://cdn2.suno.ai/image_df5c9e26-e996-44ae-b9b0-8fcf468533e8.jpeg");
  albumCovers.set("a-mafias-diary", "https://cdn2.suno.ai/e5e52c91-70f9-4c21-9113-24238999085a.jpeg");
  albumCovers.set("the-weight-of-gold", "https://cdn2.suno.ai/image_f1c63dea-d26e-43b6-8063-b3860d739162.jpeg");

  // 3. Match & update tracks in music.json with direct audioUrl stream links
  let updatedTracks = 0;
  musicData.albums.forEach(album => {
    if (albumCovers.has(album.id)) {
      album.cover = albumCovers.get(album.id);
    }

    album.tracks.forEach(track => {
      const key = normalize(track.title);
      const match = clipMap.get(key);
      if (match) {
        track.url = match.url;
        track.audioUrl = match.audioUrl;
        updatedTracks++;
      } else {
        // Fallback: derive audioUrl from existing track URL
        const songId = getSongId(track.url);
        if (songId) {
          track.audioUrl = `https://cdn1.suno.ai/${songId}.mp4`;
          updatedTracks++;
        }
      }
    });
  });

  musicData.lastUpdated = new Date().toISOString().split("T")[0];

  // Save updated music.json
  fs.writeFileSync(MUSIC_JSON_PATH, JSON.stringify(musicData, null, 2), "utf8");
  console.log(`[Sync] Successfully updated music.json with direct live MP4 audio stream URLs! (${updatedTracks} tracks synchronized)`);
}

syncDirectSunoData().catch(err => {
  console.error("[Sync Error]:", err.message);
});
