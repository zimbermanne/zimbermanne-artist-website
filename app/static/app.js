    // ---------- player ----------
    const $ = (id) => document.getElementById(id);
    const audioPlayer = new Audio();
    audioPlayer.crossOrigin = "anonymous";
    audioPlayer.preload = "none";

    const bar = $('playerBar');
    const isMobile = () => window.matchMedia('(max-width: 768px)').matches;

    let currentTrackData = {
      title: 'Pesa inaongea sana',
      album: 'Mimi Ni Odogwu',
      cover: 'https://cdn2.suno.ai/image_df5c9e26-e996-44ae-b9b0-8fcf468533e8.jpeg',
      url: 'https://suno.com/song/82bcd874-4c22-45b1-a2e3-a40a27a73d82',
      audioUrl: 'https://cdn1.suno.ai/82bcd874-4c22-45b1-a2e3-a40a27a73d82.mp4',
      lyrics: ''
    };
    let queue = [];       // every play button on the page, in order: next/previous walk this list
    let queueIndex = -1;
    let currentBtn = null;

    function extractSongId(url) {
      const match = (url || '').match(/[0-9a-f-]{36}/i);
      return match ? match[0] : null;
    }

    function buildQueue() {
      queue = Array.from(document.querySelectorAll('.tracks .btn-icon'));
    }

    function dataFromButton(btn) {
      return {
        title: btn.getAttribute('data-title'),
        album: btn.getAttribute('data-album'),
        cover: btn.getAttribute('data-cover'),
        url: btn.getAttribute('data-url'),
        lyrics: btn.getAttribute('data-lyrics'),
        audioUrl: btn.getAttribute('data-audiourl')
      };
    }

    function setPlayingUI(on) {
      bar.classList.toggle('is-playing', on);
      const b = $('playBtn');
      b.setAttribute('aria-label', on ? 'Pause' : 'Play');
      document.querySelectorAll('.tracks li.now-playing').forEach((li) => li.classList.remove('now-playing'));
      if (currentBtn) {
        const li = currentBtn.closest('li');
        if (li) li.classList.toggle('now-playing', true);
      }
    }

    function setTrackUI(btn) {
      const t = currentTrackData;
      $('playerTrackTitle').innerText = t.title;
      $('playerAlbumTitle').innerText = t.album;
      $('playerCover').src = t.cover;
      $('playerSunoLink').href = t.url;
      // MP3 link: reuse the one in the same list row
      const dl = $('playerDownload');
      const rowLink = btn && btn.closest('li') ? btn.closest('li').querySelector('a[data-dl]') : null;
      if (rowLink) {
        dl.href = rowLink.getAttribute('href');
        dl.setAttribute('data-filename', rowLink.getAttribute('data-filename') || 'track.mp3');
        dl.hidden = false;
      } else {
        dl.hidden = true;
      }
      $('progressFill').style.width = '0%';
      $('miniFill').style.width = '0%';
      $('currentTime').innerText = '0:00';
      $('totalTime').innerText = '0:00';
      updateMediaSession();
    }

    function startStream() {
      const t = currentTrackData;
      const songId = extractSongId(t.url);
      const streamSrc = t.audioUrl || (songId ? `https://cdn1.suno.ai/${songId}.mp4` : null);
      if (!streamSrc) return;
      audioPlayer.src = streamSrc;
      audioPlayer.play().catch((err) => {
        console.log('Audio autoplay blocked or error:', err);
        setPlayingUI(false);
      });
    }

    function handlePlayClick(btn) {
      if (btn === currentBtn && audioPlayer.src) { togglePlay(); return; }
      buildQueue();
      queueIndex = queue.indexOf(btn);
      currentBtn = btn;
      currentTrackData = { ...currentTrackData, ...dataFromButton(btn), lyrics: btn.getAttribute('data-lyrics') || '' };
      setTrackUI(btn);
      startStream();
    }

    function skip(dir) {
      if (!queue.length) buildQueue();
      if (!queue.length) return;
      if (queueIndex < 0) queueIndex = dir > 0 ? -1 : 0;
      // previous: restart the song when it is already a few seconds in
      if (dir < 0 && audioPlayer.currentTime > 3) { audioPlayer.currentTime = 0; return; }
      const next = (queueIndex + dir + queue.length) % queue.length;
      handlePlayClick(queue[next]);
    }

    function togglePlay() {
      if (!audioPlayer.src) {
        // nothing loaded yet: play the first song of the list (or the default one)
        buildQueue();
        const first = queue.find((b) => b.getAttribute('data-url') === currentTrackData.url) || queue[0];
        if (first) { handlePlayClick(first); } else { startStream(); }
        return;
      }
      if (audioPlayer.paused) { audioPlayer.play().catch(() => {}); } else { audioPlayer.pause(); }
    }

    audioPlayer.addEventListener('play', () => setPlayingUI(true));
    audioPlayer.addEventListener('pause', () => setPlayingUI(false));
    audioPlayer.addEventListener('ended', () => {
      setPlayingUI(false);
      $('progressFill').style.width = '0%';
      $('miniFill').style.width = '0%';
      if (queue.length > 1) skip(1);   // keep the music going
    });
    audioPlayer.addEventListener('error', () => setPlayingUI(false));

    function formatTime(seconds) {
      if (!isFinite(seconds)) return '0:00';
      const m = Math.floor(seconds / 60);
      const s = Math.floor(seconds % 60);
      return `${m}:${s < 10 ? '0' : ''}${s}`;
    }

    let lastPos = 0;
    audioPlayer.addEventListener('timeupdate', () => {
      if (!audioPlayer.duration) return;
      const pct = (audioPlayer.currentTime / audioPlayer.duration) * 100;
      $('progressFill').style.width = pct + '%';
      $('miniFill').style.width = pct + '%';
      $('progressBar').setAttribute('aria-valuenow', Math.round(pct));
      $('currentTime').innerText = formatTime(audioPlayer.currentTime);
      $('totalTime').innerText = formatTime(audioPlayer.duration);
      const now = Date.now();
      if (now - lastPos > 1000) { lastPos = now; updatePosition(); }
    });

    // show the real length as soon as a song loads, and start the bar from zero
    audioPlayer.addEventListener('loadedmetadata', () => {
      $('totalTime').innerText = formatTime(audioPlayer.duration);
      $('currentTime').innerText = '0:00';
      $('progressFill').style.width = '0%';
      $('miniFill').style.width = '0%';
      updatePosition();
    });

    // ---------- seeking: tap or drag on the bar (finger or mouse), arrow keys on the slider ----------
    function seekFromEvent(e, el) {
      if (!audioPlayer.duration) return;
      const rect = el.getBoundingClientRect();
      const pct = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
      audioPlayer.currentTime = pct * audioPlayer.duration;
    }
    function bindSeek(el) {
      let dragging = false;
      el.addEventListener('pointerdown', (e) => { dragging = true; el.setPointerCapture(e.pointerId); seekFromEvent(e, el); });
      el.addEventListener('pointermove', (e) => { if (dragging) seekFromEvent(e, el); });
      const stop = () => { dragging = false; };
      el.addEventListener('pointerup', stop);
      el.addEventListener('pointercancel', stop);
    }
    bindSeek($('progressBar'));
    $('progressBar').addEventListener('keydown', (e) => {
      if (e.key === 'ArrowRight') { audioPlayer.currentTime += 5; e.preventDefault(); }
      if (e.key === 'ArrowLeft') { audioPlayer.currentTime -= 5; e.preventDefault(); }
    });
    // the thin line along the top of the phone mini bar is tappable too
    $('miniProgress').style.pointerEvents = 'auto';
    bindSeek($('miniProgress'));
    function seekProgress(e) { seekFromEvent(e, e.currentTarget); } // kept for old inline handlers

    $('prevBtn').addEventListener('click', () => skip(-1));
    $('nextBtn').addEventListener('click', () => skip(1));

    // ---------- phone: tap the mini bar to open the full-screen player ----------
    function setExpanded(on) {
      if (on && !isMobile()) return;
      bar.classList.toggle('expanded', on);
      document.body.classList.toggle('player-open', on);
      $('playerExpand').setAttribute('aria-expanded', String(on));
      $('playerExpand').setAttribute('aria-label', on ? 'Full player' : 'Open full player');
      if (on) $('playerCollapse').focus({ preventScroll: true });
    }
    $('playerExpand').addEventListener('click', () => { if (isMobile() && !bar.classList.contains('expanded')) setExpanded(true); });
    $('playerCollapse').addEventListener('click', () => setExpanded(false));
    window.addEventListener('resize', () => { if (!isMobile()) setExpanded(false); });
    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape') return;
      if ($('lyricsModal').classList.contains('active')) closeLyrics(); else setExpanded(false);
    });

    // ---------- lock screen / headphone / notification controls ----------
    function updateMediaSession() {
      if (!('mediaSession' in navigator) || typeof MediaMetadata === 'undefined') return;
      const t = currentTrackData;
      navigator.mediaSession.metadata = new MediaMetadata({
        title: t.title, artist: 'Zimbermanne', album: t.album,
        artwork: [{ src: t.cover, sizes: '512x512' }]
      });
    }
    function updatePosition() {
      if (!('mediaSession' in navigator) || !navigator.mediaSession.setPositionState || !isFinite(audioPlayer.duration)) return;
      try {
        navigator.mediaSession.setPositionState({ duration: audioPlayer.duration, playbackRate: audioPlayer.playbackRate, position: audioPlayer.currentTime });
      } catch (e) { /* some browsers reject odd values */ }
    }
    if ('mediaSession' in navigator) {
      const ms = navigator.mediaSession;
      const set = (a, fn) => { try { ms.setActionHandler(a, fn); } catch (e) {} };
      set('play', () => audioPlayer.play());
      set('pause', () => audioPlayer.pause());
      set('previoustrack', () => skip(-1));
      set('nexttrack', () => skip(1));
      set('seekbackward', () => { audioPlayer.currentTime = Math.max(0, audioPlayer.currentTime - 10); });
      set('seekforward', () => { audioPlayer.currentTime += 10; });
      set('seekto', (d) => { if (d.seekTime != null) audioPlayer.currentTime = d.seekTime; });
    }

    // ---------- lyrics modal ----------
    function handleLyricsClick(btn) {
      const title = btn.getAttribute('data-title');
      const album = btn.getAttribute('data-album');
      const url = btn.getAttribute('data-url');
      const lyrics = btn.getAttribute('data-lyrics');
      showLyrics(title, album, lyrics, url);
    }

    function showLyrics(title, album, lyricsText, url) {
      $('modalTrackTitle').innerText = title;
      $('modalAlbumTitle').innerText = album;
      $('modalLyricsBody').innerText = lyricsText || 'Lyrics coming soon.';
      $('modalSunoBtn').href = url || '#';
      $('lyricsModal').classList.add('active');
    }

    function openCurrentLyrics() {
      showLyrics(currentTrackData.title, currentTrackData.album, currentTrackData.lyrics, currentTrackData.url);
    }

    function closeLyrics() {
      $('lyricsModal').classList.remove('active');
    }

    // ---------- start state: show the default song in the bar (not playing) ----------
    (function init() {
      buildQueue();
      const first = queue.find((b) => b.getAttribute('data-url') === currentTrackData.url);
      if (first) {
        currentBtn = first;
        queueIndex = queue.indexOf(first);
        currentTrackData = { ...currentTrackData, lyrics: first.getAttribute('data-lyrics') || '' };
        setTrackUI(first);
      }
    })();
