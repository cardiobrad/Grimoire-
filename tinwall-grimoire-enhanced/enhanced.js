(() => {
  const cvs = document.getElementById('c');
  if (!cvs) return;

  const overlay = document.getElementById('grimoire-overlay');
  const octx = overlay.getContext('2d');
  const result = document.getElementById('seed-result');
  const btn = document.getElementById('seed-btn');

  function resizeOverlay() {
    overlay.width = cvs.width;
    overlay.height = cvs.height;
  }

  function gamma(u) {
    return 0.0 * u;
  }

  function pdeTick() {
    if (!window.influenceField || !window.GW || !window.GH) return;
    const GW = window.GW;
    const GH = window.GH;
    const D = 0.12;
    const LAM = 0.45;
    const ALPHA = Math.PI;
    const DT = 0.05;
    const next = new Float32Array(window.influenceField);
    for (let y = 1; y < GH - 1; y++) {
      for (let x = 1; x < GW - 1; x++) {
        const i = y * GW + x;
        const u = window.influenceField[i];
        const lap = window.influenceField[i - 1] + window.influenceField[i + 1] + window.influenceField[i - GW] + window.influenceField[i + GW] - 4 * u;
        const react = LAM * u * u * Math.sin(ALPHA * u) + gamma(u);
        next[i] = Math.max(0, u + DT * (D * lap + react));
      }
    }
    window.influenceField = next;
  }

  function renderOverlay() {
    const field = window.influenceField;
    if (!field || !window.GW || !window.GH) return;
    octx.clearRect(0, 0, overlay.width, overlay.height);

    const GW = window.GW;
    const GH = window.GH;
    let mx = 0;
    for (let i = 0; i < field.length; i++) mx = Math.max(mx, field[i]);
    const inv = mx > 0 ? 1 / mx : 1;

    const cellW = overlay.width / GW;
    const cellH = overlay.height / GH;

    for (let y = 0; y < GH; y++) {
      for (let x = 0; x < GW; x++) {
        const u = field[y * GW + x] * inv;
        if (u < 0.07) continue;
        const hue = 230 - Math.floor(220 * u);
        const alpha = Math.min(0.45, u * 0.35);
        octx.fillStyle = `hsla(${hue},95%,${28 + 40 * u}%,${alpha})`;
        octx.fillRect(x * cellW, y * cellH, cellW + 0.8, cellH + 0.8);
        if (u > 0.82) {
          octx.fillStyle = `hsla(45,100%,70%,${Math.min(0.24, u * 0.22)})`;
          octx.fillRect(x * cellW + 1, y * cellH + 1, cellW - 2, cellH - 2);
        }
      }
    }
  }

  function unitSelection() {
    if (window.G && Array.isArray(window.G.selected) && window.G.selected.length) return window.G.selected;
    if (Array.isArray(window.playerUnits)) return window.playerUnits.filter((u) => u.alive).slice(0, 16);
    return [];
  }

  function pulseAtSelection(units) {
    units.slice(0, 8).forEach((u) => {
      if (!window.w2s) return;
      const p = window.w2s(u.wx, u.wy);
      const dot = document.createElement('div');
      dot.className = 'seed-pulse';
      dot.style.left = `${p.x}px`;
      dot.style.top = `${p.y}px`;
      document.body.appendChild(dot);
      setTimeout(() => dot.remove(), 1300);
    });
  }

  function scoreSeedFirst() {
    const units = unitSelection();
    if (!units.length) {
      result.textContent = 'Select units first to score your seed posture.';
      return;
    }
    const gsm = typeof window.computeFormationGSM === 'function'
      ? window.computeFormationGSM(units)
      : { score: 0, cls: 'DORMANT', pct: 0 };

    const badge = `<span class="gsm-badge gsm-${gsm.cls}">${gsm.cls}</span>`;
    result.innerHTML = `GSM ${gsm.score.toFixed ? gsm.score.toFixed(2) : gsm.score} ${badge}<br/>` +
      `Readiness ${Math.round(gsm.pct || 0)}% • ${units.length} units<br/>` +
      `Rule: Score the Seed First before hard engagement.`;

    pulseAtSelection(units);
  }

  btn.addEventListener('click', scoreSeedFirst);
  window.addEventListener('resize', resizeOverlay);
  resizeOverlay();

  (function loop() {
    pdeTick();
    renderOverlay();
    requestAnimationFrame(loop);
  })();
})();
