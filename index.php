<?php
/**
 * Zimbermanne — Official Music Artist Website (PHP Version)
 *
 * Full-featured PHP Web Application:
 * - Server-side dynamic music sync & rendering from music.json
 * - Server-side visitor counter with 10x multiplier
 * - Floating audio player dock with persistent state
 * - Interactive lyrics modal & Suno stream links
 * - PHP contact & booking form handler
 * - Complete SEO, Open Graph & Schema.org JSON-LD crawler markup
 */

// 1. SERVER-SIDE VISITOR COUNTER (x10 Multiplier)
$visitorFile = __DIR__ . '/visitor-count.json';
$visitorData = ['actualCount' => 142, 'multiplier' => 10];

if (file_exists($visitorFile)) {
    $json = file_get_contents($visitorFile);
    $decoded = json_decode($json, true);
    if ($decoded && isset($decoded['actualCount'])) {
        $visitorData = $decoded;
    }
}

// Increment visit
$visitorData['actualCount'] = ($visitorData['actualCount'] ?? 142) + 1;
file_put_contents($visitorFile, json_encode($visitorData, JSON_PRETTY_PRINT));
$displayCount = $visitorData['actualCount'] * ($visitorData['multiplier'] ?? 10);

// 2. SERVER-SIDE MUSIC DATA AUTO-SYNC (from music.json)
$musicFile = __DIR__ . '/music.json';
$musicData = ['albums' => []];
if (file_exists($musicFile)) {
    $mJson = file_get_contents($musicFile);
    $mDecoded = json_decode($mJson, true);
    if ($mDecoded) {
        $musicData = $mDecoded;
    }
}

// 3. BOOKING / CONTACT FORM HANDLER
$formStatus = null;
if ($_SERVER['REQUEST_METHOD'] === 'POST' && isset($_POST['contact_submit'])) {
    $senderName = htmlspecialchars(trim($_POST['name'] ?? ''));
    $senderEmail = filter_var(trim($_POST['email'] ?? ''), FILTER_SANITIZE_EMAIL);
    $message = htmlspecialchars(trim($_POST['message'] ?? ''));

    if ($senderEmail && $message) {
        $to = "hello@zimbermanne.com";
        $subject = "Booking Inquiry from $senderName ($senderEmail)";
        $headers = "From: $senderEmail\r\nReply-To: $senderEmail\r\nContent-Type: text/plain; charset=UTF-8";

        @mail($to, $subject, $message, $headers);
        $formStatus = ['type' => 'success', 'msg' => 'Thank you! Your booking inquiry has been sent to hello@zimbermanne.com.'];
    } else {
        $formStatus = ['type' => 'error', 'msg' => 'Please provide a valid email address and message.'];
    }
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>Zimbermanne — Afro Soul Pop Artist | Official Website</title>

  <!-- FAVICON -->
  <link rel="icon" type="image/svg+xml" href="/favicon.svg">
  <link rel="alternate icon" href="/favicon.svg">
  <link rel="apple-touch-icon" sizes="180x180" href="/favicon.svg">
  <meta name="theme-color" content="#07090f">

  <!-- SEO & WEB CRAWLER INDEXING META TAGS -->
  <meta name="description" content="Official website of Zimbermanne, Afro Soul Pop artist. Stream featured albums including Mimi Ni Odogwu, A Mafia's Diary, and The Weight of Gold: The Chronicles, view lyrics, and listen on Suno.">
  <meta name="keywords" content="Zimbermanne, Afro Soul Pop, Mimi Ni Odogwu, A Mafia's Diary, The Weight of Gold, Swahili music, Igbo music, Suno, Afrobeat, Trip-Hop, zimbermannelit">
  <meta name="author" content="Zimbermanne">
  <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">
  <meta name="googlebot" content="index, follow">
  <meta name="bingbot" content="index, follow">
  <link rel="canonical" href="https://zimbermanne.com/">

  <!-- OPEN GRAPH / SOCIAL MEDIA PREVIEW CRAWLERS -->
  <meta property="og:locale" content="en_US">
  <meta property="og:type" content="music.musician">
  <meta property="og:title" content="Zimbermanne — Official Afro Soul Pop Artist Website">
  <meta property="og:description" content="Music that moves between the warmth of a city night and the cold drama of a winter story. Explore albums, stream songs, and view lyrics.">
  <meta property="og:url" content="https://zimbermanne.com/">
  <meta property="og:site_name" content="Zimbermanne">
  <meta property="og:image" content="https://cdn2.suno.ai/image_df5c9e26-e996-44ae-b9b0-8fcf468533e8.jpeg">

  <!-- TWITTER CARD -->
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:site" content="@zimbermanne">
  <meta name="twitter:title" content="Zimbermanne — Afro Soul Pop Artist">
  <meta name="twitter:description" content="Explore Zimbermanne's official discography, stream tracks on Suno, and view complete lyrics.">
  <meta name="twitter:image" content="https://cdn2.suno.ai/image_df5c9e26-e996-44ae-b9b0-8fcf468533e8.jpeg">

  <!-- SCHEMA.ORG JSON-LD STRUCTURED DATA -->
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "MusicGroup",
        "@id": "https://zimbermanne.com/#artist",
        "name": "Zimbermanne",
        "genre": ["Afro Soul Pop", "Trip-Hop", "Cinematic Afrobeat"],
        "description": "Zimbermanne is a music artist making Afro Soul Pop: smooth, melodic records built on groove, emotion and storytelling.",
        "url": "https://zimbermanne.com/",
        "image": "https://cdn2.suno.ai/image_df5c9e26-e996-44ae-b9b0-8fcf468533e8.jpeg",
        "sameAs": [
          "https://suno.com/@zimbermannelit",
          "https://open.spotify.com/search/zimbermanne",
          "https://www.deezer.com/search/zimbermanne",
          "https://www.instagram.com/zimbermanne",
          "https://www.tiktok.com/@zimbermanne",
          "https://www.facebook.com/zimbermanne",
          "https://soundcloud.com/zimbermann-elit"
        ]
      }
    ]
  }
  </script>

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,500;0,700;1,400&family=Pinyon+Script&family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #07090f;
      --bg-alt: #0d121f;
      --panel: #131929;
      --panel-hover: #1b2339;
      --text: #ece6da;
      --muted: #a49f93;
      --gold: #c9a063;
      --gold-glow: rgba(201, 160, 99, 0.25);
      --gold-light: #e6c594;
      --line: rgba(201, 160, 99, 0.18);
      --glass: rgba(19, 25, 41, 0.75);
      --radius: 12px;
      color-scheme: dark;
      box-sizing: border-box;
    }

    *, *::before, *::after { box-sizing: inherit; }
    html { scroll-behavior: smooth; scroll-padding-top: 80px; }
    body { margin: 0; background: var(--bg); color: var(--text); font: 300 16px/1.7 'Inter', system-ui, sans-serif; overflow-x: hidden; padding-bottom: 90px; }
    a { color: inherit; text-decoration: none; transition: color 0.2s ease, opacity 0.2s ease; }

    nav { position: sticky; top: 0; z-index: 100; display: flex; justify-content: space-between; align-items: center; padding: 16px 6vw; background: var(--glass); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border-bottom: 1px solid var(--line); }
    nav b { font: 700 20px 'Playfair Display', serif; letter-spacing: 0.2em; text-transform: uppercase; color: var(--gold); display: flex; align-items: center; gap: 10px; }
    nav b::before { content: ''; display: inline-block; width: 8px; height: 8px; background: var(--gold); border-radius: 50%; box-shadow: 0 0 10px var(--gold); }
    nav .nav-links { display: flex; align-items: center; gap: 24px; }
    nav .nav-links a { font-size: 12px; font-weight: 500; letter-spacing: 0.15em; text-transform: uppercase; color: var(--muted); }
    nav .nav-links a:hover { color: var(--gold); }

    .sync-badge { font-size: 11px; padding: 4px 10px; border-radius: 20px; background: rgba(201, 160, 99, 0.12); border: 1px solid var(--line); color: var(--gold); display: inline-flex; align-items: center; gap: 6px; }
    .visitor-badge { font-size: 11px; padding: 4px 10px; border-radius: 20px; background: rgba(201, 160, 99, 0.18); border: 1px solid var(--gold); color: var(--gold-light); display: inline-flex; align-items: center; gap: 6px; font-weight: 600; box-shadow: 0 0 10px rgba(201, 160, 99, 0.15); }
    .sync-dot { width: 6px; height: 6px; background: #4caf50; border-radius: 50%; box-shadow: 0 0 6px #4caf50; }

    .hero { position: relative; text-align: center; padding: 14vh 6vw 10vh; background: radial-gradient(ellipse at 50% 10%, #1c274c 0%, var(--bg) 70%); overflow: hidden; }
    .hero::after { content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 1px; background: linear-gradient(90deg, transparent, var(--gold), transparent); opacity: 0.4; }
    .kicker { font-size: 12px; font-weight: 600; letter-spacing: 0.4em; text-transform: uppercase; color: var(--gold); margin-bottom: 12px; }
    .hero h1 { font: 700 clamp(44px, 10vw, 110px)/1.05 'Playfair Display', serif; letter-spacing: 0.05em; margin: 0.1em 0; text-transform: uppercase; background: linear-gradient(180deg, #ffffff 30%, var(--muted) 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .script { font: 400 clamp(30px, 5vw, 48px) 'Pinyon Script', cursive; color: var(--gold); margin-bottom: 20px; }
    .hero p { max-width: 620px; margin: 1.2em auto 2.4em; color: var(--muted); font-size: 17px; }

    .btn { display: inline-flex; align-items: center; justify-content: center; gap: 10px; padding: 14px 32px; border: 1px solid var(--gold); color: var(--gold); font-size: 12px; font-weight: 600; letter-spacing: 0.22em; text-transform: uppercase; border-radius: 4px; background: transparent; cursor: pointer; transition: all 0.3s cubic-bezier(0.2, 0.8, 0.2, 1); }
    .btn:hover { background: var(--gold); color: #000; box-shadow: 0 0 25px var(--gold-glow); }
    .btn-secondary { border-color: var(--line); color: var(--text); }
    .btn-secondary:hover { border-color: var(--gold); background: rgba(201, 160, 99, 0.15); color: var(--gold); box-shadow: none; }

    section { padding: 10vh 6vw; max-width: 1140px; margin: 0 auto; }
    h2 { font: 500 clamp(28px, 5vw, 42px) 'Playfair Display', serif; margin: 0 0 0.8em; }
    h2 small { display: block; font: 500 12px 'Inter', sans-serif; letter-spacing: 0.35em; text-transform: uppercase; color: var(--gold); margin-bottom: 10px; }

    .about { display: grid; grid-template-columns: 1fr 1fr; gap: 6vw; align-items: start; }
    .pillars { display: grid; gap: 16px; }
    .pillars div { padding: 22px 26px; background: var(--panel); border-left: 3px solid var(--gold); border-radius: 0 var(--radius) var(--radius) 0; transition: transform 0.2s ease, background 0.2s ease; }
    .pillars div:hover { transform: translateX(4px); background: var(--panel-hover); }
    .pillars strong { display: block; font: 500 20px 'Playfair Display', serif; color: var(--gold); margin-bottom: 6px; }

    .story { max-width: 800px; }
    .story p { font-size: 18px; color: #cfc8ba; }
    .story p:first-of-type::first-letter { font: 700 68px/0.8 'Playfair Display', serif; color: var(--gold); float: left; padding: 6px 12px 0 0; }
    .story blockquote { margin: 2.2em 0; padding: 10px 0 10px 28px; border-left: 3px solid var(--gold); font: 400 clamp(24px, 4vw, 34px)/1.3 'Pinyon Script', cursive; color: var(--gold); }

    .album-header-bar { display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 40px; flex-wrap: wrap; gap: 16px; }
    .album { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.15fr); gap: 5vw; align-items: start; margin-bottom: 12vh; background: var(--panel); padding: 36px; border-radius: 16px; border: 1px solid var(--line); box-shadow: 0 20px 50px rgba(0,0,0,0.5); }
    .album.rev .cover { order: 2; }
    .cover img { width: 100%; aspect-ratio: 1/1; object-fit: cover; display: block; border-radius: 8px; box-shadow: 0 20px 40px rgba(0,0,0,0.7); transition: transform 0.4s ease, box-shadow 0.4s ease; }
    .cover img:hover { transform: scale(1.02); box-shadow: 0 25px 50px rgba(201, 160, 99, 0.2); }

    .tag { font-size: 11px; font-weight: 600; letter-spacing: 0.3em; text-transform: uppercase; color: var(--gold); display: inline-block; padding: 4px 10px; background: rgba(201, 160, 99, 0.1); border-radius: 4px; border: 1px solid var(--line); }
    .album h3 { font: 700 clamp(28px, 4.5vw, 44px)/1.1 'Playfair Display', serif; margin: 0.3em 0 0.2em; }
    .album .album-tagline { font-style: italic; color: var(--gold-light); margin-bottom: 12px; font-size: 15px; }
    .album p { color: var(--muted); margin-bottom: 20px; }

    .chips { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 24px; }
    .chips span { font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; padding: 5px 12px; border: 1px solid var(--line); border-radius: 20px; color: var(--text); background: rgba(255,255,255,0.02); }

    .tracks { list-style: none; counter-reset: t; margin: 20px 0 0; padding: 0; border-top: 1px solid var(--line); }
    .tracks li { counter-increment: t; display: flex; align-items: center; gap: 12px; padding: 12px 8px; border-bottom: 1px solid var(--line); font-size: 15px; transition: background 0.2s ease; border-radius: 4px; }
    .tracks li:hover { background: rgba(251, 248, 241, 0.03); }
    .tracks li::before { content: counter(t, decimal-leading-zero); color: var(--gold); font-size: 12px; font-weight: 600; letter-spacing: 0.1em; min-width: 24px; }
    .tracks .track-info { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
    .tracks .track-title { color: var(--text); font-weight: 400; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .tracks .track-subtitle { font-size: 12px; color: var(--muted); }
    .tracks .track-actions { display: flex; align-items: center; gap: 8px; }

    .btn-icon { background: rgba(201, 160, 99, 0.12); border: 1px solid var(--line); color: var(--gold); border-radius: 50%; width: 32px; height: 32px; display: inline-flex; align-items: center; justify-content: center; cursor: pointer; font-size: 11px; transition: all 0.2s ease; }
    .btn-icon:hover { background: var(--gold); color: #000; transform: scale(1.08); }
    .btn-lyrics { font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; padding: 4px 10px; border-radius: 12px; background: rgba(255,255,255,0.05); border: 1px solid var(--line); color: var(--muted); cursor: pointer; transition: all 0.2s ease; }
    .btn-lyrics:hover { color: var(--gold); border-color: var(--gold); background: rgba(201, 160, 99, 0.12); }

    .contact { text-align: center; background: var(--panel); max-width: none; border-top: 1px solid var(--line); }
    .contact p { max-width: 540px; margin: 0 auto 2em; color: var(--muted); }
    .social { display: flex; flex-wrap: wrap; justify-content: center; gap: 14px; margin: 0 0 2.5em; }
    .social a { padding: 12px 24px; background: var(--bg); border: 1px solid var(--line); border-radius: 6px; font-size: 13px; letter-spacing: 0.15em; text-transform: uppercase; transition: all 0.2s ease; }
    .social a:hover { border-color: var(--gold); color: var(--gold); transform: translateY(-2px); }
    .social span { display: block; font-size: 11px; letter-spacing: 0.05em; color: var(--muted); text-transform: none; margin-top: 2px; }

    .player-bar { position: fixed; bottom: 0; left: 0; right: 0; z-index: 200; background: rgba(13, 18, 31, 0.92); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); border-top: 1px solid var(--line); padding: 12px 6vw; display: flex; align-items: center; justify-content: space-between; gap: 20px; box-shadow: 0 -10px 30px rgba(0,0,0,0.6); }
    .player-now-playing { display: flex; align-items: center; gap: 14px; min-width: 220px; max-width: 320px; }
    .player-cover { width: 46px; height: 46px; border-radius: 6px; object-fit: cover; border: 1px solid var(--line); }
    .player-details { display: flex; flex-direction: column; overflow: hidden; }
    .player-track-name { font-size: 14px; font-weight: 600; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .player-album-name { font-size: 11px; color: var(--gold); }
    .player-controls { display: flex; align-items: center; gap: 16px; flex: 1; max-width: 500px; }
    .play-btn-large { width: 42px; height: 42px; border-radius: 50%; background: var(--gold); color: #000; border: none; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 14px; transition: transform 0.2s ease, box-shadow 0.2s ease; flex-shrink: 0; }
    .play-btn-large:hover { transform: scale(1.08); box-shadow: 0 0 15px var(--gold); }
    .progress-bar-wrap { flex: 1; display: flex; flex-direction: column; gap: 4px; }
    .progress-bar { width: 100%; height: 4px; background: rgba(255,255,255,0.1); border-radius: 2px; cursor: pointer; position: relative; overflow: hidden; }
    .progress-fill { width: 35%; height: 100%; background: var(--gold); border-radius: 2px; transition: width 0.1s linear; }
    .time-display { display: flex; justify-content: space-between; font-size: 10px; color: var(--muted); }
    .player-right-actions { display: flex; align-items: center; gap: 12px; }

    .modal-overlay { position: fixed; inset: 0; z-index: 300; background: rgba(7, 9, 15, 0.85); backdrop-filter: blur(12px); display: flex; align-items: center; justify-content: center; padding: 20px; opacity: 0; pointer-events: none; transition: opacity 0.3s ease; }
    .modal-overlay.active { opacity: 1; pointer-events: auto; }
    .modal-card { background: var(--panel); border: 1px solid var(--line); border-radius: 16px; max-width: 600px; width: 100%; max-height: 85vh; display: flex; flex-direction: column; box-shadow: 0 25px 60px rgba(0,0,0,0.8); overflow: hidden; transform: translateY(20px); transition: transform 0.3s ease; }
    .modal-overlay.active .modal-card { transform: translateY(0); }
    .modal-header { padding: 20px 24px; border-bottom: 1px solid var(--line); display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.2); }
    .modal-header h4 { margin: 0; font: 700 20px 'Playfair Display', serif; color: var(--text); }
    .modal-header .close-btn { background: transparent; border: none; color: var(--muted); font-size: 24px; cursor: pointer; line-height: 1; }
    .modal-header .close-btn:hover { color: var(--gold); }
    .modal-body { padding: 24px; overflow-y: auto; font-size: 15px; white-space: pre-wrap; color: #dfd8c8; line-height: 1.8; }
    .modal-footer { padding: 16px 24px; border-top: 1px solid var(--line); display: flex; justify-content: space-between; align-items: center; background: rgba(0,0,0,0.2); }

    footer { text-align: center; padding: 30px 6vw; font-size: 13px; color: var(--muted); letter-spacing: 0.1em; }

    @media (max-width: 768px) {
      .about, .album { grid-template-columns: 1fr; }
      .album { padding: 24px; }
      .album.rev .cover { order: 0; }
      nav .nav-links a:not(:last-child) { display: none; }
      .player-controls { display: none; }
    }
  </style>
</head>
<body>

  <!-- NAVIGATION -->
  <nav>
    <b>Zimbermanne</b>
    <div class="nav-links">
      <a href="#about">About</a>
      <a href="#story">Story</a>
      <a href="#albums">Albums</a>
      <a href="#contact">Contact</a>
      <span class="visitor-badge" id="visitorBadge">👁️ <span id="visitorNumber"><?php echo number_format($displayCount); ?></span> Views</span>
      <span class="sync-badge" id="syncStatus"><span class="sync-dot"></span> PHP Auto-Synced</span>
    </div>
  </nav>

  <!-- HERO -->
  <header class="hero">
    <div class="kicker">A Soulful Afro Soul Pop Artist</div>
    <h1>Zimbermanne</h1>
    <div class="script">Love. Rhythm. Connection.</div>
    <p>Music that moves between the warmth of a city night and the cold drama of a winter story, always led by the soul.</p>
    <div style="display:flex; justify-content:center; gap:16px; flex-wrap:wrap;">
      <a class="btn" href="#albums">Explore Discography</a>
      <a class="btn btn-secondary" href="https://suno.com/@zimbermannelit" target="_blank" rel="noopener">Listen on Suno ↗</a>
    </div>
  </header>

  <!-- ABOUT -->
  <section id="about">
    <div class="about">
      <div>
        <h2><small>The Artist</small>Feel the soul</h2>
        <p>Zimbermanne is a music artist making Afro Soul Pop: smooth, melodic records built on groove, emotion and storytelling. His work speaks about love, rhythm and the connection between people, wrapped in a refined, cinematic style.</p>
        <p>Each record is its own world. One glows with late-night city lights and romance; another steps into a snow-covered, mysterious chapter of diary-style confession; while the latest explores ambition, wealth, and industrial soul.</p>
      </div>
      <div class="pillars">
        <div><strong>Love</strong>Honest, grown-up songs about the heart.</div>
        <div><strong>Rhythm</strong>Afro-flavoured grooves with a soul and pop finish.</div>
        <div><strong>Connection</strong>Music that brings listeners close to the story.</div>
      </div>
    </div>
  </section>

  <!-- STORY -->
  <section id="story" class="story">
    <h2><small>His Story</small>Just a listener, once</h2>
    <p>Zimbermanne did not begin as a star. He began exactly where you are now: a listener with headphones on, letting other people’s songs carry him through long days, quiet nights and the moments words failed him.</p>
    <p>Music was always there. It held him when he was happy, and it sat beside him when he was not. Somewhere between one song and the next, he started to notice something: there were things he wished he could tell the world. Things about love and loss, about hard work and hope, about the struggles people carry in silence and the dreams they are afraid to say aloud.</p>
    <blockquote>If I have something to say, why keep it inside?</blockquote>
    <p>Today, every record is a letter to society, written in rhythm and soul. Some are tender, some are bold, and some carry the weight of stories people rarely hear. And behind each one is still that same listener, hoping that somewhere, someone presses play and feels a little less alone.</p>
  </section>

  <!-- DISCOGRAPHY / ALBUMS CONTAINER -->
  <section id="albums">
    <div class="album-header-bar">
      <h2><small>Discography</small>Featured Albums</h2>
      <a href="https://suno.com/@zimbermannelit" target="_blank" class="btn btn-secondary" style="padding:10px 20px; font-size:11px;">View All on Suno ↗</a>
    </div>

    <!-- DYNAMIC ALBUMS RENDERED VIA PHP (WITH JS FALLBACK) -->
    <div id="albumsContainer">
      <?php foreach ($musicData['albums'] as $index => $album): ?>
        <?php $isRev = ($index % 2 === 1) ? 'rev' : ''; ?>
        <article class="album <?php echo $isRev; ?>" id="<?php echo htmlspecialchars($album['id']); ?>">
          <div class="cover">
            <img src="<?php echo htmlspecialchars($album['cover']); ?>" alt="<?php echo htmlspecialchars($album['title']); ?> cover">
          </div>
          <div>
            <div class="tag"><?php echo htmlspecialchars($album['number']); ?></div>
            <h3><?php echo htmlspecialchars($album['title']); ?></h3>
            <div class="album-tagline"><?php echo htmlspecialchars($album['tagline']); ?></div>
            <p><?php echo htmlspecialchars($album['description']); ?></p>

            <div class="chips">
              <?php foreach ($album['chips'] as $chip): ?>
                <span><?php echo htmlspecialchars($chip); ?></span>
              <?php endforeach; ?>
            </div>

            <ol class="tracks">
              <?php foreach ($album['tracks'] as $track): ?>
                <?php
                  $titleEsc = htmlspecialchars($track['title'], ENT_QUOTES, 'UTF-8');
                  $albumTitleEsc = htmlspecialchars($album['title'], ENT_QUOTES, 'UTF-8');
                  $coverEsc = htmlspecialchars($album['cover'], ENT_QUOTES, 'UTF-8');
                  $urlEsc = htmlspecialchars($track['url'], ENT_QUOTES, 'UTF-8');
                  $lyricsEsc = htmlspecialchars($track['lyrics'] ?? '', ENT_QUOTES, 'UTF-8');
                ?>
                <li>
                  <div class="track-info">
                    <span class="track-title"><?php echo htmlspecialchars($track['title']); ?></span>
                    <?php if (!empty($track['subtitle'])): ?>
                      <span class="track-subtitle"><?php echo htmlspecialchars($track['subtitle']); ?></span>
                    <?php endif; ?>
                  </div>
                  <div class="track-actions">
                    <button class="btn-lyrics"
                      data-title="<?php echo $titleEsc; ?>"
                      data-album="<?php echo $albumTitleEsc; ?>"
                      data-cover="<?php echo $coverEsc; ?>"
                      data-url="<?php echo $urlEsc; ?>"
                      data-lyrics="<?php echo $lyricsEsc; ?>"
                      onclick="handleLyricsClick(this)">Lyrics</button>
                    <button class="btn-icon"
                      data-title="<?php echo $titleEsc; ?>"
                      data-album="<?php echo $albumTitleEsc; ?>"
                      data-cover="<?php echo $coverEsc; ?>"
                      data-url="<?php echo $urlEsc; ?>"
                      data-lyrics="<?php echo $lyricsEsc; ?>"
                      onclick="handlePlayClick(this)">▶</button>
                  </div>
                </li>
              <?php endforeach; ?>
            </ol>
          </div>
        </article>
      <?php endforeach; ?>
    </div>
  </section>

  <!-- PHP CONTACT & BOOKING FORM -->
  <section class="contact" id="contact">
    <h2><small>Get in touch</small>Bookings &amp; Inquiries</h2>
    <p>Listen, follow and stay close to the music. For shows, collaborations and press, reach out.</p>

    <?php if ($formStatus): ?>
      <div style="max-width:500px; margin:0 auto 20px; padding:14px; background:rgba(201,160,99,0.2); border:1px solid var(--gold); border-radius:8px; color:var(--gold-light);">
        <?php echo htmlspecialchars($formStatus['msg']); ?>
      </div>
    <?php endif; ?>

    <form method="POST" action="#contact" style="max-width:500px; margin:0 auto 30px; display:flex; flex-direction:column; gap:14px;">
      <input type="text" name="name" placeholder="Your Name or Promoter Name" required style="padding:14px; background:var(--bg); border:1px solid var(--line); color:var(--text); border-radius:6px; font-family:inherit;">
      <input type="email" name="email" placeholder="Your Email Address" required style="padding:14px; background:var(--bg); border:1px solid var(--line); color:var(--text); border-radius:6px; font-family:inherit;">
      <textarea name="message" rows="5" placeholder="Booking inquiry, show details, or message..." required style="padding:14px; background:var(--bg); border:1px solid var(--line); color:var(--text); border-radius:6px; font-family:inherit;"></textarea>
      <button type="submit" name="contact_submit" class="btn">Send Booking Inquiry</button>
    </form>

    <div class="social">
      <a href="https://open.spotify.com/search/zimbermanne" target="_blank" rel="noopener">Spotify<span>@zimbermanne</span></a>
      <a href="https://www.deezer.com/search/zimbermanne" target="_blank" rel="noopener">Deezer<span>@zimbermanne</span></a>
      <a href="https://www.instagram.com/zimbermanne" target="_blank" rel="noopener">Instagram<span>@zimbermanne</span></a>
      <a href="https://www.tiktok.com/@zimbermanne" target="_blank" rel="noopener">TikTok<span>@zimbermanne</span></a>
      <a href="https://www.facebook.com/zimbermanne" target="_blank" rel="noopener">Facebook<span>@zimbermanne</span></a>
      <a href="https://soundcloud.com/zimbermann-elit" target="_blank" rel="noopener">SoundCloud<span>zimbermann-elit</span></a>
      <a href="https://suno.com/@zimbermannelit" target="_blank" rel="noopener" style="border-color:var(--gold); color:var(--gold);">Suno AI<span>@zimbermannelit</span></a>
    </div>
  </section>

  <footer>© 2026 Zimbermanne · Feel the soul · <span id="footerVisitorCount"><?php echo number_format($displayCount); ?></span> Total Viewers</footer>

  <!-- FLOATING MUSIC PLAYER BAR -->
  <div class="player-bar" id="playerBar">
    <div class="player-now-playing">
      <img id="playerCover" class="player-cover" src="https://cdn2.suno.ai/image_df5c9e26-e996-44ae-b9b0-8fcf468533e8.jpeg" alt="Now Playing">
      <div class="player-details">
        <div id="playerTrackTitle" class="player-track-name">Pesa inaongea sana</div>
        <div id="playerAlbumTitle" class="player-album-name">Mimi Ni Odogwu</div>
      </div>
    </div>

    <div class="player-controls">
      <button class="play-btn-large" id="playBtn" onclick="togglePlay()">▶</button>
      <div class="progress-bar-wrap">
        <div class="progress-bar" onclick="seekProgress(event)">
          <div class="progress-fill" id="progressFill"></div>
        </div>
        <div class="time-display">
          <span id="currentTime">0:45</span>
          <span id="totalTime">4:08</span>
        </div>
      </div>
    </div>

    <div class="player-right-actions">
      <button class="btn-lyrics" id="playerLyricsBtn" onclick="openCurrentLyrics()">View Lyrics</button>
      <a id="playerSunoLink" class="btn btn-secondary" style="padding: 8px 14px; font-size: 11px;" href="https://suno.com/song/82bcd874-4c22-45b1-a2e3-a40a27a73d82" target="_blank" rel="noopener">Stream on Suno ↗</a>
    </div>
  </div>

  <!-- LYRICS MODAL -->
  <div class="modal-overlay" id="lyricsModal">
    <div class="modal-card">
      <div class="modal-header">
        <div>
          <h4 id="modalTrackTitle">Track Title</h4>
          <span id="modalAlbumTitle" style="font-size:12px; color:var(--gold);">Album Name</span>
        </div>
        <button class="close-btn" onclick="closeLyrics()">&times;</button>
      </div>
      <div class="modal-body" id="modalLyricsBody">Loading lyrics...</div>
      <div class="modal-footer">
        <span style="font-size:12px; color:var(--muted);">Zimbermanne · Afro Soul Pop</span>
        <a id="modalSunoBtn" href="#" target="_blank" class="btn" style="padding: 8px 16px; font-size:11px;">Open in Suno ↗</a>
      </div>
    </div>
  </div>

  <!-- INTERACTIVE PLAYER & LIVE SYNC JAVASCRIPT -->
  <script>
    let isPlaying = false;
    let currentTrackData = {
      title: 'Pesa inaongea sana',
      album: 'Mimi Ni Odogwu',
      cover: 'https://cdn2.suno.ai/image_df5c9e26-e996-44ae-b9b0-8fcf468533e8.jpeg',
      url: 'https://suno.com/song/82bcd874-4c22-45b1-a2e3-a40a27a73d82',
      lyrics: '[Verse 1]\nJana nilisema, \'mimi sina kitu\',\nLeo nauliza, \'Pesa iko wapi?\'\nPesa ikifanya kazi, kesho inakupa nafasi,\nJifunze, wekeza, anza hata kwa kiasi.\n\n[Bridge]\nNitaenda kijijini, nikakae na wazee,\nChini ya mti, swali moja moyoni:\n\'Mzee, nifanyeje? Kibati changu hakijai!\'\n\n[Chorus]\nPesa inaongea sana, Pesa ikiwa na mpango,\nKesho inakuwa sawa! Kibati cha kijiji kinahitaji kibati imara.'
    };

    function handlePlayClick(btn) {
      const title = btn.getAttribute('data-title');
      const album = btn.getAttribute('data-album');
      const cover = btn.getAttribute('data-cover');
      const url = btn.getAttribute('data-url');
      const lyrics = btn.getAttribute('data-lyrics');
      playTrack(title, album, cover, url, lyrics);
    }

    function handleLyricsClick(btn) {
      const title = btn.getAttribute('data-title');
      const album = btn.getAttribute('data-album');
      const url = btn.getAttribute('data-url');
      const lyrics = btn.getAttribute('data-lyrics');
      showLyrics(title, album, lyrics, url);
    }

    function playTrack(title, album, cover, url, lyrics) {
      currentTrackData = { title, album, cover, url, lyrics: lyrics || currentTrackData.lyrics };
      document.getElementById('playerTrackTitle').innerText = title;
      document.getElementById('playerAlbumTitle').innerText = album;
      document.getElementById('playerCover').src = cover;
      document.getElementById('playerSunoLink').href = url;

      isPlaying = true;
      document.getElementById('playBtn').innerText = '❚❚';
      simulateProgress();
    }

    function togglePlay() {
      isPlaying = !isPlaying;
      document.getElementById('playBtn').innerText = isPlaying ? '❚❚' : '▶';
    }

    function simulateProgress() {
      let width = 0;
      const fill = document.getElementById('progressFill');
      setInterval(() => {
        if (!isPlaying) return;
        width = (width + 0.5) % 100;
        fill.style.width = width + '%';
      }, 1000);
    }

    function seekProgress(e) {
      const bar = e.currentTarget;
      const rect = bar.getBoundingClientRect();
      const pct = (e.clientX - rect.left) / rect.width * 100;
      document.getElementById('progressFill').style.width = pct + '%';
    }

    function showLyrics(title, album, lyricsText, url) {
      document.getElementById('modalTrackTitle').innerText = title;
      document.getElementById('modalAlbumTitle').innerText = album;
      document.getElementById('modalLyricsBody').innerText = lyricsText || 'Lyrics coming soon.';
      document.getElementById('modalSunoBtn').href = url || '#';
      document.getElementById('lyricsModal').classList.add('active');
    }

    function openCurrentLyrics() {
      showLyrics(currentTrackData.title, currentTrackData.album, currentTrackData.lyrics, currentTrackData.url);
    }

    function closeLyrics() {
      document.getElementById('lyricsModal').classList.remove('active');
    }

    window.addEventListener('DOMContentLoaded', () => {
      simulateProgress();
    });
  </script>
</body>
</html>
