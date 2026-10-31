// Minimal static file server (no dependencies) for Railway & web crawlers.
const http = require("http");
const fs = require("fs");
const path = require("path");

const PORT = process.env.PORT || 3000;
const ROOT = __dirname;
const TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".xml": "application/xml; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".mp3": "audio/mpeg",
  ".webp": "image/webp",
};

http
  .createServer((req, res) => {
    let urlPath = decodeURIComponent(req.url.split("?")[0]);
    if (urlPath === "/") urlPath = "/index.html";
    const file = path.normalize(path.join(ROOT, urlPath));
    const blocked = ["server.js", "package.json"].includes(path.basename(file));
    if (!file.startsWith(ROOT) || blocked) {
      res.writeHead(403);
      return res.end("Forbidden");
    }
    fs.readFile(file, (err, data) => {
      if (err) {
        // Single-page fallback: always serve the site
        return fs.readFile(path.join(ROOT, "index.html"), (e2, page) => {
          if (e2) { res.writeHead(404); return res.end("Not found"); }
          res.writeHead(200, { "Content-Type": TYPES[".html"] });
          res.end(page);
        });
      }
      res.writeHead(200, {
        "Content-Type": TYPES[path.extname(file).toLowerCase()] || "application/octet-stream",
      });
      res.end(data);
    });
  })
  .listen(PORT, "0.0.0.0", () => console.log("Zimbermanne site running on port " + PORT));
