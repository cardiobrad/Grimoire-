(() => {
  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  async function boot() {
    for (let i = 0; i < 120; i++) {
      if (window.CVS && window.CAM && window.G && Array.isArray(window.playerUnits) && Array.isArray(window.enemyUnits)) break;
      await wait(100);
    }

    const canvas = document.getElementById('c');
    const fx = document.getElementById('rts-fx');
    const macroRes = document.getElementById('macro-res');
    const macroArmy = document.getElementById('macro-army');
    const macroFill = document.getElementById('macro-fill');
    if (!canvas || !fx) return;
    const ctx = fx.getContext('2d');

    const hpMap = new WeakMap();
    const rings = [];
    const sparkles = [];

    function resize() { fx.width = canvas.width; fx.height = canvas.height; }

    function toCanvas(clientX, clientY) {
      const rect = canvas.getBoundingClientRect();
      return {
        x: (clientX - rect.left) * (canvas.width / rect.width),
        y: (clientY - rect.top) * (canvas.height / rect.height),
      };
    }

    // Smart right-click command intent: attack > gather > move
    canvas.addEventListener('contextmenu', (e) => {
      if (!window.G?.active || !Array.isArray(window.G.selected) || !window.G.selected.length) return;
      const p = toCanvas(e.clientX, e.clientY);
      const w = window.CAM.fromCanvas(p.x, p.y);

      const enemy = window.enemyUnits?.find((u) => u.alive && Math.hypot(u.wx - w.x, u.wy - w.y) < 1.4);
      const res = window.resNodes?.find((r) => !r.depleted && Math.hypot(r.wx - w.x, r.wy - w.y) < 1.2);

      window.G.selected.forEach((u, i) => {
        if (!u.alive) return;
        if (enemy) {
          u.attackTarget = enemy;
          u.gatherTarget = null;
          u.state = 'attack';
        } else if (res) {
          u.gatherTarget = res;
          u.attackTarget = null;
          u.state = 'gather';
        } else {
          const ox = (i % 6) * 0.5 - 1.2;
          const oy = Math.floor(i / 6) * 0.5;
          u.tx = w.x + ox;
          u.ty = w.y + oy;
          u.attackTarget = null;
          u.gatherTarget = null;
          u.state = 'moving';
        }
      });

      rings.push({ x: p.x, y: p.y, born: performance.now(), col: enemy ? '255,120,120' : res ? '120,255,180' : '120,210,255' });
    });

    // Hidden GRIMOIRE modulation (no player-facing UI)
    function hiddenFieldAssist() {
      const squad = window.playerUnits.filter((u) => u.alive).slice(0, 18);
      if (!squad.length) return;

      let cls = 'EDGE';
      if (typeof window.computeFormationGSM === 'function') {
        const gsm = window.computeFormationGSM(squad);
        cls = gsm.cls || cls;
      }
      const clsBuff = cls === 'AMPLIFYING' ? 1.1 : cls === 'RESILIENT' ? 1.06 : cls === 'FRAGILE' ? 0.95 : cls === 'DORMANT' ? 0.9 : 1.0;

      for (const u of squad) {
        if (u._baseDmg == null) u._baseDmg = u.dmg;
        if (u._baseSpd == null) u._baseSpd = u.spd;
        const f0 = typeof window.readField === 'function' ? window.readField(u.wx, u.wy) : 0;
        const fxp = typeof window.readField === 'function' ? window.readField(u.wx + 1, u.wy) : f0;
        const fxm = typeof window.readField === 'function' ? window.readField(u.wx - 1, u.wy) : f0;
        const fyp = typeof window.readField === 'function' ? window.readField(u.wx, u.wy + 1) : f0;
        const fym = typeof window.readField === 'function' ? window.readField(u.wx, u.wy - 1) : f0;
        const gx = (fxp - fxm) * 0.3;
        const gy = (fyp - fym) * 0.3;

        // tiny steering bias improves cohesion/path smoothness
        if (u.state === 'moving') {
          u.tx += gx * 0.08;
          u.ty += gy * 0.08;
        }

        const local = Math.max(0, Math.min(1.4, f0));
        u.dmg = u._baseDmg * clsBuff * (1 + 0.04 * local);
        u.spd = u._baseSpd * (1 + 0.03 * local);
      }
    }

    function updateMacroHUD() {
      if (!macroRes || !macroArmy) return;
      const tin = Number(document.getElementById('r-tin')?.textContent || 0);
      const gold = Number(document.getElementById('r-gold')?.textContent || 0);
      const fish = Number(document.getElementById('r-fish')?.textContent || 0);
      const timber = Number(document.getElementById('r-timber')?.textContent || 0);
      const metal = Math.round(tin + gold * 2.2);
      const energy = Math.round(fish * 1.4 + timber * 1.1);
      const own = window.playerUnits.filter((u) => u.alive).length;
      const enemy = window.enemyUnits.filter((u) => u.alive).length;
      const ratio = own + enemy > 0 ? (own / (own + enemy)) : 0.5;

      macroRes.textContent = `Metal ${metal}  •  Energy ${energy}`;
      macroArmy.textContent = `Army ${own} vs ${enemy}`;
      macroFill.style.width = `${Math.max(8, Math.min(92, ratio * 100))}%`;
    }

    function updateCombatFx() {
      const units = [...window.playerUnits, ...window.enemyUnits].filter((u) => u.alive);
      for (const u of units) {
        const prev = hpMap.get(u) ?? u.hp;
        if (u.hp < prev - 0.01) {
          const p = window.w2s ? window.w2s(u.wx, u.wy) : { x: 0, y: 0 };
          sparkles.push({ x: p.x, y: p.y - 10, txt: `-${Math.round(prev - u.hp)}`, life: 800 });
        }
        hpMap.set(u, u.hp);
      }
    }

    function drawFx() {
      ctx.clearRect(0, 0, fx.width, fx.height);
      const now = performance.now();

      for (let i = rings.length - 1; i >= 0; i--) {
        const r = rings[i];
        const t = (now - r.born) / 700;
        if (t >= 1) { rings.splice(i, 1); continue; }
        ctx.strokeStyle = `rgba(${r.col},${1 - t})`;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(r.x, r.y, 10 + 28 * t, 0, Math.PI * 2);
        ctx.stroke();
      }

      for (let i = sparkles.length - 1; i >= 0; i--) {
        const s = sparkles[i];
        s.life -= 16;
        s.y -= 0.28;
        if (s.life <= 0) { sparkles.splice(i, 1); continue; }
        ctx.globalAlpha = Math.max(0.08, s.life / 800);
        ctx.fillStyle = '#ffb1b1';
        ctx.font = '700 12px Inter';
        ctx.fillText(s.txt, s.x, s.y);
        ctx.globalAlpha = 1;
      }
    }

    resize();
    window.addEventListener('resize', resize);

    setInterval(hiddenFieldAssist, 220);
    setInterval(updateMacroHUD, 200);
    setInterval(updateCombatFx, 120);

    (function loop() {
      drawFx();
      requestAnimationFrame(loop);
    })();
  }

  boot();
})();
