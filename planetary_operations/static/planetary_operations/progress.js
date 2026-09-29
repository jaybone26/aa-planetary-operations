(() => {
  const progress = document.getElementById('po-progress');
  if (!progress) return;
  let attempts = 0;
  async function update() {
    try {
      const response = await fetch(progress.dataset.statusUrl, {credentials: 'same-origin'});
      if (!response.ok) return;
      const data = await response.json();
      if (data.status === 'ready' || data.status === 'failed') { location.reload(); return; }
      if (++attempts < 60) setTimeout(update, 5000);
      else progress.textContent = 'Still waiting for the worker. Refresh this page later or check the AA worker status.';
    } catch (_) {
      progress.textContent = 'Connection interrupted. Refresh this page to check your saved plan.';
    }
  }
  setTimeout(update, 3000);
})();
