// MP3 download: read the audio stream chunk by chunk (with live progress), and once the
// stream is complete assemble the chunks into one MP3 file and hand it to the browser.
// Without JavaScript the same links still work as normal downloads.
(function () {
  function save(blob, name) {
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 10000);
  }

  async function download(el) {
    if (el.dataset.busy) return;
    var label = el.textContent;
    var name = el.dataset.filename || 'track.mp3';
    el.dataset.busy = '1';
    el.setAttribute('aria-busy', 'true');
    el.textContent = 'Preparing…';
    try {
      var res = await fetch(el.getAttribute('href'));
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var blob;
      if (res.body && res.body.getReader) {
        var total = parseInt(res.headers.get('Content-Length'), 10) || 0;
        var reader = res.body.getReader();
        var chunks = [];
        var got = 0;
        for (;;) {
          var part = await reader.read();
          if (part.done) break;
          chunks.push(part.value);
          got += part.value.length;
          el.textContent = total ? Math.round((got / total) * 100) + '%' : (got / 1048576).toFixed(1) + ' MB';
        }
        if (total && got !== total) throw new Error('Incomplete download');
        blob = new Blob(chunks, { type: 'audio/mpeg' });
      } else {
        blob = await res.blob(); // older browsers: no streaming reader
      }
      el.textContent = 'Saving…';
      save(blob, name);
      el.textContent = 'Saved ✓';
    } catch (err) {
      el.textContent = 'Failed, retry';
    }
    setTimeout(function () {
      el.textContent = label;
      delete el.dataset.busy;
      el.removeAttribute('aria-busy');
    }, 2500);
  }

  document.addEventListener('click', function (e) {
    var el = e.target.closest('[data-dl]');
    if (!el || !window.fetch || !window.Blob) return; // fall back to the plain link
    e.preventDefault();
    download(el);
  });
})();
