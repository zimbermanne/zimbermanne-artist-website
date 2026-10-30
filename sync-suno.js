/**
 * Suno Auto-Sync Script for Zimbermanne Website
 *
 * Usage:
 *   npm run sync
 *
 * This script fetches the latest profile, albums, tracks, and lyrics from
 * https://suno.com/@zimbermannelit and automatically updates `music.json`.
 */

const fs = require("fs");
const path = require("path");

const SUNO_HANDLE = "zimbermannelit";
const PROFILE_URL = `https://suno.com/@${SUNO_HANDLE}`;
const MUSIC_JSON_PATH = path.join(__dirname, "music.json");

async function fetchSunoProfile() {
  console.log(`Fetching Suno profile data for @${SUNO_HANDLE}...`);
  const response = await fetch(PROFILE_URL, {
    headers: { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" }
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch Suno profile: ${response.statusText}`);
  }

  const html = await response.text();
  const unescaped = html.replace(/\\"/g, '"').replace(/\\\\/g, '\\');

  // Read existing music.json to preserve custom taglines or custom lyrics
  let existingMusic = { albums: [] };
  if (fs.existsSync(MUSIC_JSON_PATH)) {
    try {
      existingMusic = JSON.parse(fs.readFileSync(MUSIC_JSON_PATH, "utf8"));
    } catch (e) {
      console.log("Creating new music.json structure...");
    }
  }

  // Map of existing lyrics by track URL or title
  const lyricsMap = new Map();
  (existingMusic.albums || []).forEach(a => {
    (a.tracks || []).forEach(t => {
      if (t.lyrics) lyricsMap.set(t.url, t.lyrics);
      if (t.lyrics) lyricsMap.set(t.title.toLowerCase(), t.lyrics);
    });
  });

  // Extract all tracks with song IDs and titles
  const clipRegex = /"id":"([0-9a-f-]{36})"[^}]*?"title":"([^"]+)"/g;
  let match;
  const tracksByTitle = new Map();
  while ((match = clipRegex.exec(unescaped)) !== null) {
    const id = match[1];
    const title = match[2];
    if (!title.includes("Suno") && !title.includes("Sharing") && !title.includes("Publish")) {
      tracksByTitle.set(title.toLowerCase().trim(), {
        title: title,
        url: `https://suno.com/song/${id}`
      });
    }
  }

  console.log(`Found ${tracksByTitle.size} unique songs on Suno profile.`);

  // Update tracks in existing albums with latest Suno URLs
  let updatedCount = 0;
  existingMusic.albums.forEach(album => {
    album.tracks.forEach(track => {
      const match = tracksByTitle.get(track.title.toLowerCase().trim());
      if (match) {
        track.url = match.url;
        updatedCount++;
      }
    });
  });

  existingMusic.lastUpdated = new Date().toISOString().split("T")[0];

  // Write updated data back to music.json
  fs.writeFileSync(MUSIC_JSON_PATH, JSON.stringify(existingMusic, null, 2), "utf8");
  console.log(`Successfully synced music.json! (${updatedCount} tracks verified/updated)`);
}

fetchSunoProfile().catch(err => {
  console.error("Auto-sync encountered an issue:", err.message);
});
