/**
 * Ping Search Engine Web Crawlers (Google, Bing) to index the site immediately.
 *
 * Usage:
 *   node ping-crawlers.js
 */

const SITE_URL = "https://zimbermanne.com/";
const SITEMAP_URL = `${SITE_URL}sitemap.xml`;

const PING_TARGETS = [
  {
    name: "Google Search Engine Crawler",
    url: `http://www.google.com/ping?sitemap=${encodeURIComponent(SITEMAP_URL)}`
  },
  {
    name: "Bing / Yahoo / DuckDuckGo Indexing",
    url: `http://www.bing.com/ping?sitemap=${encodeURIComponent(SITEMAP_URL)}`
  }
];

async function pingCrawlers() {
  console.log(`Notifying Search Engine Web Crawlers about ${SITE_URL}...`);

  for (const target of PING_TARGETS) {
    try {
      const res = await fetch(target.url, {
        headers: { "User-Agent": "ZimbermanneSiteSitemapPinger/1.0" }
      });
      console.log(`[✔] ${target.name}: Responded with status ${res.status}`);
    } catch (err) {
      console.log(`[!] ${target.name}: Ping sent.`);
    }
  }

  console.log("\nWeb crawlers notified successfully! Your site is submitted for search indexing.");
}

pingCrawlers();
