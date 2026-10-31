# Implementation plan (FastAPI)

## Phase 0: Migration (this package)
1. In the repo, delete: `index.php`, `index.html`, `server.js`, `package.json`, `test_embed.js`,
   `ping-crawlers.js`, `visitor-count.json`, `gitignore`, the `.idea/` folder and the exported `.md` file.
2. Add the files from this package, commit and push.
3. Railway → service → Settings → Build: delete the Watch Paths pattern (`**/*.php`).
4. Railway → service → Variables: add `DATABASE_URL` as a reference to the existing Postgres service.
5. Check `/healthz`, the home page, then send a test inquiry and look at the `messages` table.
Done when: the site loads on the Railway domain and the counter survives a redeploy.

## Phase 1: Email you control
Create a Resend account, verify the sender address, set `RESEND_API_KEY`, `CONTACT_TO`, `CONTACT_FROM`.
Add a WhatsApp booking button. Done when a test inquiry reaches the inbox.

## Phase 2: Fan list
"Notify me of new songs" form, `subscribers` table, unsubscribe link, export to CSV.

## Phase 3: Song pages and search markup
`/song/<slug>` pages from `music.json` (cover, lyrics, Suno link, share preview), automatic `sitemap.xml`,
`MusicAlbum` / `MusicRecording` JSON-LD.

## Phase 4: Auto-updating music
Port `sync-suno.js` to Python and run it on a schedule that commits `music.json` only when it changes.
Keep the committed file as the fallback because Suno's pages can change without notice.

## Phase 5: Speed and analytics
Smaller lazy-loaded covers (partly done), Plausible analytics, domain `zimbermanne.com`, update `robots.txt` and `sitemap.xml`.

## Later
Mobile-money fan support (Selcom or ClickPesa), video section, English/Swahili switch, press kit page.
