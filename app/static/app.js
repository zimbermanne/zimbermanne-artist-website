    let isPlaying = false;
    const audioPlayer = new Audio();
    audioPlayer.crossOrigin = "anonymous";

    let currentTrackData = {
      title: 'Pesa inaongea sana',
      album: 'Mimi Ni Odogwu',
      cover: 'https://cdn2.suno.ai/image_df5c9e26-e996-44ae-b9b0-8fcf468533e8.jpeg',
      url: 'https://suno.com/song/82bcd874-4c22-45b1-a2e3-a40a27a73d82',
      audioUrl: 'https://cdn1.suno.ai/82bcd874-4c22-45b1-a2e3-a40a27a73d82.mp4',
      lyrics: '[Verse 1]\nJana nilisema, \'mimi sina kitu\',\nLeo nauliza, \'Pesa iko wapi?\'\nPesa ikifanya kazi, kesho inakupa nafasi,\nJifunze, wekeza, anza hata kwa kiasi.\n\n[Bridge]\nNitaenda kijijini, nikakae na wazee,\nChini ya mti, swali moja moyoni:\n\'Mzee, nifanyeje? Kibati changu hakijai!\'\n\n[Chorus]\nPesa inaongea sana, Pesa ikiwa na mpango,\nKesho inakuwa sawa! Kibati cha kijiji kinahitaji kibati imara.'
    };

    function extractSongId(url) {
      const match = (url || '').match(/[0-9a-f-]{36}/i);
      return match ? match[0] : null;
    }

    function handlePlayClick(btn) {
      const title = btn.getAttribute('data-title');
      const album = btn.getAttribute('data-album');
      const cover = btn.getAttribute('data-cover');
      const url = btn.getAttribute('data-url');
      const lyrics = btn.getAttribute('data-lyrics');
      const audioUrl = btn.getAttribute('data-audiourl');
      playTrack(title, album, cover, url, lyrics, audioUrl);
    }

    function handleLyricsClick(btn) {
      const title = btn.getAttribute('data-title');
      const album = btn.getAttribute('data-album');
      const url = btn.getAttribute('data-url');
      const lyrics = btn.getAttribute('data-lyrics');
      showLyrics(title, album, lyrics, url);
    }

    function playTrack(title, album, cover, url, lyrics, audioUrl) {
      currentTrackData = { title, album, cover, url, lyrics: lyrics || currentTrackData.lyrics, audioUrl };
      document.getElementById('playerTrackTitle').innerText = title;
      document.getElementById('playerAlbumTitle').innerText = album;
      document.getElementById('playerCover').src = cover;
      document.getElementById('playerSunoLink').href = url;

      const songId = extractSongId(url);
      const streamSrc = audioUrl || (songId ? `https://cdn1.suno.ai/${songId}.mp4` : null);

      if (streamSrc) {
        audioPlayer.src = streamSrc;
        audioPlayer.play().then(() => {
          isPlaying = true;
          document.getElementById('playBtn').innerText = '❚❚';
        }).catch(err => {
          console.log('Audio autoplay blocked or error:', err);
          isPlaying = false;
          document.getElementById('playBtn').innerText = '▶';
        });
      }
    }

    function togglePlay() {
      if (!audioPlayer.src) {
        playTrack(currentTrackData.title, currentTrackData.album, currentTrackData.cover, currentTrackData.url, currentTrackData.lyrics, currentTrackData.audioUrl);
        return;
      }

      if (audioPlayer.paused) {
        audioPlayer.play();
        isPlaying = true;
        document.getElementById('playBtn').innerText = '❚❚';
      } else {
        audioPlayer.pause();
        isPlaying = false;
        document.getElementById('playBtn').innerText = '▶';
      }
    }

    audioPlayer.addEventListener('timeupdate', () => {
      if (!audioPlayer.duration) return;
      const pct = (audioPlayer.currentTime / audioPlayer.duration) * 100;
      document.getElementById('progressFill').style.width = pct + '%';
      document.getElementById('currentTime').innerText = formatTime(audioPlayer.currentTime);
      document.getElementById('totalTime').innerText = formatTime(audioPlayer.duration);
    });

    audioPlayer.addEventListener('ended', () => {
      isPlaying = false;
      document.getElementById('playBtn').innerText = '▶';
      document.getElementById('progressFill').style.width = '0%';
    });

    function formatTime(seconds) {
      if (isNaN(seconds)) return '0:00';
      const m = Math.floor(seconds / 60);
      const s = Math.floor(seconds % 60);
      return `${m}:${s < 10 ? '0' : ''}${s}`;
    }

    function seekProgress(e) {
      if (!audioPlayer.duration) return;
      const bar = e.currentTarget;
      const rect = bar.getBoundingClientRect();
      const pct = (e.clientX - rect.left) / rect.width;
      audioPlayer.currentTime = pct * audioPlayer.duration;
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
