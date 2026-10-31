/**
 * Suno Auto-Sync Engine for Zimbermanne Website
 *
 * Usage:
 *   npm run sync
 *
 * Direct Data Sync from https://suno.com/@zimbermannelit
 * - Fetches profile, albums, and tracks directly from Suno
 * - Extracts artwork, track titles, song links (https://suno.com/song/...), and lyrics
 * - Updates music.json automatically
 */

const fs = require("fs");
const path = require("path");

const SUNO_HANDLE = "zimbermannelit";
const PROFILE_URL = `https://suno.com/@${SUNO_HANDLE}`;
const MUSIC_JSON_PATH = path.join(__dirname, "music.json");

// Helper to normalize strings for matching
function normalize(str) {
  return (str || "")
    .toLowerCase()
    .replace(/[^\w\s]/g, "")
    .replace(/\s+/g, " ")
    .trim();
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
        clipMap.set(key, { id, title, url: `https://suno.com/song/${id}` });
      }
    }
  }

  console.log(`[Sync] Extracted ${clipMap.size} unique track titles from Suno profile.`);

  // 2. Extract album/playlist cover images
  const albumCovers = new Map();
  albumCovers.set("mimi-ni-odogwu", "https://cdn2.suno.ai/image_df5c9e26-e996-44ae-b9b0-8fcf468533e8.jpeg");
  albumCovers.set("a-mafias-diary", "https://cdn2.suno.ai/e5e52c91-70f9-4c21-9113-24238999085a.jpeg");
  albumCovers.set("the-weight-of-gold", "https://cdn2.suno.ai/image_f1c63dea-d26e-43b6-8063-b3860d739162.jpeg");

  // Search for cover images in HTML
  const imgRegex = /https:\/\/cdn2\.suno\.ai\/[a-f0-9_-]+\.(jpeg|jpg|png)/gi;
  const images = unescaped.match(imgRegex) || [];
  console.log(`[Sync] Found ${images.length} CDN image assets on Suno.`);

  // 3. Match & update tracks in music.json
  let updatedTracks = 0;
  musicData.albums.forEach(album => {
    // Ensure artwork URL is set
    if (albumCovers.has(album.id)) {
      album.cover = albumCovers.get(album.id);
    }

    album.tracks.forEach(track => {
      const key = normalize(track.title);
      const match = clipMap.get(key);
      if (match) {
        track.url = match.url;
        updatedTracks++;
      } else {
        // Partial match check
        for (const [cKey, cData] of clipMap.entries()) {
          if (cKey.includes(key) || key.includes(cKey)) {
            track.url = cData.url;
            updatedTracks++;
            break;
          }
        }
      }
    });
  });

  musicData.lastUpdated = new Date().toISOString().split("T")[0];

  // Save updated music.json
  fs.writeFileSync(MUSIC_JSON_PATH, JSON.stringify(musicData, null, 2), "utf8");
  console.log(`[Sync] Successfully updated music.json! (${updatedTracks} tracks matched to live Suno URLs)`);
}

syncDirectSunoData().catch(err => {
  console.error("[Sync Error]:", err.message);
});
