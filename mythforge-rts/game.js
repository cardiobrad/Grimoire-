const cvs = document.getElementById('game');
const ctx = cvs.getContext('2d');
const resourcesEl = document.getElementById('resources');
const statusEl = document.getElementById('status');
const auditLog = document.getElementById('audit-log');

const W = cvs.width, H = cvs.height;
const world = { w: 2400, h: 1400 };
const cam = { x: 0, y: 0, speed: 12 };
const mouse = { x: 0, y: 0 };

const GR = { n: 64, D: 0.12, L: 0.45, A: Math.PI, dt: 0.05, field: new Float32Array(64 * 64) };

const state = {
  metal: 420, energy: 220, won: false, paused: false, muted: false,
  buildMode: null, nextId: 1, select: [], drag: null,
  playerUnits: [], enemyUnits: [], buildings: [], resources: [], projectiles: [], particles: [],
  enemyCoresDestroyed: 0, lastAudit: null,
};

const costs = {
  refinery: { m: 120, e: 0 }, power: { m: 90, e: 0 }, barracks: { m: 180, e: 60 }, turret: { m: 140, e: 30 },
  infantry: { m: 45, e: 10 }, tank: { m: 90, e: 45 }, air: { m: 120, e: 70 },
};

const clamp = (v, a, b) => Math.max(a, Math.min(b, Number.isFinite(v) ? v : a));
const rnd = (a, b) => a + Math.random() * (b - a);
const gid = () => state.nextId++;

class AudioBus {
  constructor() { this.ctx = null; this.master = null; }
  ensure() {
    if (this.ctx) return;
    this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    this.master = this.ctx.createGain(); this.master.gain.value = 0.04; this.master.connect(this.ctx.destination);
  }
  setMuted(v) { state.muted = v; if (this.master) this.master.gain.value = v ? 0 : 0.04; }
  beep(freq = 440, dur = 0.06, type = 'square') {
    if (state.muted) return;
    this.ensure();
    const o = this.ctx.createOscillator(); const g = this.ctx.createGain();
    o.type = type; o.frequency.value = freq; o.connect(g); g.connect(this.master);
    const t = this.ctx.currentTime; g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.5, t + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.start(t); o.stop(t + dur + 0.01);
  }
}
const audio = new AudioBus();

function makeUnit(x, y, team, type = 'infantry') {
  const stats = {
    commander: { hp: 500, spd: 1.45, dmg: 22, rng: 110, cd: 0.85, r: 12, col: '#ffe27a' },
    infantry: { hp: 75, spd: 1.9, dmg: 9, rng: 85, cd: 0.8, r: 7, col: '#8be1ff' },
    tank: { hp: 180, spd: 1.2, dmg: 24, rng: 125, cd: 1.1, r: 10, col: '#96ffa8' },
    air: { hp: 120, spd: 2.7, dmg: 13, rng: 130, cd: 0.5, r: 8, col: '#c0b8ff' },
  }[type] || { hp: 80, spd: 1.7, dmg: 8, rng: 80, cd: 0.9, r: 7, col: '#8be1ff' };
  return { id: gid(), team, type, x, y, tx: x, ty: y, hp: stats.hp, maxHp: stats.hp, spd: stats.spd, baseSpd: stats.spd, dmg: stats.dmg, baseDmg: stats.dmg, rng: stats.rng, cd: 0, maxCd: stats.cd, r: stats.r, col: stats.col, target: null, gather: null, selected: false, alive: true };
}

function makeBuilding(x, y, team, type = 'hq') {
  const map = {
    hq: { hp: 1300, r: 22, col: '#5ec3ff' }, core: { hp: 1000, r: 24, col: '#ff7878' }, refinery: { hp: 380, r: 16, col: '#64d7ff' },
    power: { hp: 320, r: 14, col: '#86a8ff' }, barracks: { hp: 550, r: 18, col: '#9cffd7' }, turret: { hp: 420, r: 14, col: '#ffb4a3' },
  }[type];
  return { id: gid(), team, type, x, y, hp: map.hp, maxHp: map.hp, r: map.r, col: map.col, alive: true };
}

function init() {
  state.buildings.push(makeBuilding(250, 700, 'player', 'hq'));
  state.playerUnits.push(makeUnit(320, 720, 'player', 'commander'));
  for (let i = 0; i < 8; i++) state.playerUnits.push(makeUnit(350 + i * 18, 760 + (i % 2) * 14, 'player', 'infantry'));
  state.buildings.push(makeBuilding(2040, 250, 'enemy', 'core'));
  state.buildings.push(makeBuilding(2140, 690, 'enemy', 'core'));
  state.buildings.push(makeBuilding(1930, 1100, 'enemy', 'core'));
  for (let i = 0; i < 20; i++) state.enemyUnits.push(makeUnit(1900 + rnd(-120, 120), 500 + rnd(-300, 300), 'enemy', i % 4 ? 'infantry' : 'tank'));
  for (let i = 0; i < 20; i++) state.resources.push({ id: gid(), x: rnd(580, 1840), y: rnd(130, 1260), amount: 540, r: 13, alive: true });
}

const screenToWorld = (sx, sy) => ({ x: clamp(sx + cam.x, 0, world.w), y: clamp(sy + cam.y, 0, world.h) });
const worldToScreen = (wx, wy) => ({ x: wx - cam.x, y: wy - cam.y });
const canPay = (c) => state.metal >= c.m && state.energy >= c.e;
function pay(c) { state.metal = Math.max(0, state.metal - c.m); state.energy = Math.max(0, state.energy - c.e); }

function nearestEnemy(u) {
  const arr = u.team === 'player' ? [...state.enemyUnits, ...state.buildings.filter((b) => b.team === 'enemy' && b.alive)] : [...state.playerUnits, ...state.buildings.filter((b) => b.team === 'player' && b.alive)];
  let best = null, bd = 1e9;
  for (const e of arr) {
    if (!e.alive) continue;
    const d = Math.hypot(e.x - u.x, e.y - u.y);
    if (d < bd) { bd = d; best = e; }
  }
  return best;
}

function runGR() {
  const { n, field, D, L, A, dt } = GR;
  const next = new Float32Array(field);
  for (let y = 1; y < n - 1; y++) for (let x = 1; x < n - 1; x++) {
    const i = y * n + x, u = field[i];
    const lap = field[i - 1] + field[i + 1] + field[i - n] + field[i + n] - 4 * u;
    const react = L * u * u * Math.sin(A * u);
    next[i] = Math.max(0, u + dt * (D * lap + react));
  }
  for (const u of [...state.playerUnits, ...state.enemyUnits]) {
    if (!u.alive) continue;
    const gx = clamp((u.x / world.w * n) | 0, 1, n - 2), gy = clamp((u.y / world.h * n) | 0, 1, n - 2);
    next[gy * n + gx] = Math.min(5, next[gy * n + gx] + (u.team === 'player' ? 0.06 : 0.05));
  }
  GR.field = next;
}

function readField(x, y) {
  const n = GR.n;
  const gx = clamp((x / world.w * n) | 0, 0, n - 1), gy = clamp((y / world.h * n) | 0, 0, n - 1);
  return GR.field[gy * n + gx] || 0;
}

function gsmForSquad(units) {
  if (units.length < 2) return 0.94;
  const cx = units.reduce((s, u) => s + u.x, 0) / units.length;
  const cy = units.reduce((s, u) => s + u.y, 0) / units.length;
  const spread = units.reduce((s, u) => s + Math.hypot(u.x - cx, u.y - cy), 0) / units.length;
  return clamp(1.28 - spread / 170, 0.84, 1.17);
}

function hiddenBuffs() {
  const pAlive = state.playerUnits.filter((u) => u.alive);
  const eAlive = state.enemyUnits.filter((u) => u.alive);
  const pG = gsmForSquad(pAlive.slice(0, 24));
  const eG = gsmForSquad(eAlive.slice(0, 24));
  for (const u of pAlive) {
    const f = clamp(readField(u.x, u.y), 0, 1.4);
    u.spd = u.baseSpd * pG * (1 + 0.03 * f);
    u.dmg = u.baseDmg * pG * (1 + 0.05 * f);
  }
  for (const u of eAlive) {
    const f = clamp(readField(u.x, u.y), 0, 1.4);
    u.spd = u.baseSpd * eG * (1 + 0.03 * f);
    u.dmg = u.baseDmg * eG * (1 + 0.05 * f);
  }
}

function canPlaceBuilding(wx, wy, radius = 20) {
  if (!Number.isFinite(wx) || !Number.isFinite(wy)) return false;
  if (wx < 60 || wy < 60 || wx > world.w - 60 || wy > world.h - 60) return false;
  for (const b of state.buildings) if (b.alive && Math.hypot(b.x - wx, b.y - wy) < b.r + radius + 14) return false;
  return true;
}

function commandSelected(wx, wy) {
  if (!Number.isFinite(wx) || !Number.isFinite(wy)) return;
  const enemy = [...state.enemyUnits, ...state.buildings.filter((b) => b.team === 'enemy')].find((e) => e.alive && Math.hypot(e.x - wx, e.y - wy) < (e.r || 10) + 18);
  const node = state.resources.find((r) => r.alive && Math.hypot(r.x - wx, r.y - wy) < r.r + 16);
  state.select.forEach((u, i) => {
    if (!u.alive) return;
    if (enemy) { u.target = enemy; u.gather = null; }
    else if (node) { u.gather = node; u.target = null; }
    else {
      const cols = Math.max(1, Math.ceil(Math.sqrt(state.select.length)));
      const ox = (i % cols) * 18 - cols * 9, oy = Math.floor(i / cols) * 18;
      u.tx = clamp(wx + ox, 0, world.w); u.ty = clamp(wy + oy, 0, world.h); u.target = null; u.gather = null;
    }
  });
  state.particles.push({ x: wx, y: wy, life: 0.9, col: enemy ? '#ff8080' : node ? '#90ffd3' : '#8cd0ff', r: 12 });
  audio.beep(enemy ? 200 : node ? 360 : 520, 0.05, 'triangle');
}

function placeBuilding(wx, wy) {
  if (!state.buildMode) return;
  const c = costs[state.buildMode];
  if (!canPay(c)) return status('Insufficient resources.');
  if (!canPlaceBuilding(wx, wy)) return status('Invalid placement zone.');
  pay(c);
  state.buildings.push(makeBuilding(wx, wy, 'player', state.buildMode));
  state.buildMode = null;
  audio.beep(300, 0.09, 'square');
}

function spawnFromBarracks(type) {
  const b = state.buildings.find((x) => x.team === 'player' && x.type === 'barracks' && x.alive);
  if (!b) return status('Build a Barracks first.');
  const c = costs[type];
  if (!canPay(c)) return;
  pay(c);
  state.playerUnits.push(makeUnit(b.x + rnd(-18, 18), b.y + 42, 'player', type));
  audio.beep(type === 'tank' ? 180 : type === 'air' ? 600 : 420, 0.07, 'sawtooth');
}

function status(msg) { statusEl.textContent = msg; }

function serializeState() {
  return JSON.stringify({
    metal: state.metal, energy: state.energy, nextId: state.nextId,
    playerUnits: state.playerUnits, enemyUnits: state.enemyUnits, buildings: state.buildings,
    resources: state.resources, enemyCoresDestroyed: state.enemyCoresDestroyed,
  });
}

function saveGame() { localStorage.setItem('mythforge_save_v1', serializeState()); status('Game saved.'); }
function loadGame() {
  const raw = localStorage.getItem('mythforge_save_v1');
  if (!raw) return status('No save found.');
  try {
    const d = JSON.parse(raw);
    for (const k of ['metal', 'energy', 'nextId', 'enemyCoresDestroyed']) state[k] = clamp(d[k], 0, 1e9);
    state.playerUnits = Array.isArray(d.playerUnits) ? d.playerUnits : [];
    state.enemyUnits = Array.isArray(d.enemyUnits) ? d.enemyUnits : [];
    state.buildings = Array.isArray(d.buildings) ? d.buildings : [];
    state.resources = Array.isArray(d.resources) ? d.resources : [];
    status('Game loaded.');
  } catch { status('Save corrupted.'); }
}

function runtimeAudit() {
  const report = [];
  const arrs = [state.playerUnits, state.enemyUnits, state.buildings, state.resources];
  const flat = arrs.flat();
  const badNums = flat.filter((o) => Object.values(o).some((v) => typeof v === 'number' && !Number.isFinite(v))).length;
  report.push(`finite-numbers: ${badNums === 0 ? 'PASS' : 'FAIL (' + badNums + ')'}`);
  const dup = new Set(); let dupCount = 0;
  for (const o of flat) { if (dup.has(o.id)) dupCount++; dup.add(o.id); }
  report.push(`unique-ids: ${dupCount === 0 ? 'PASS' : 'FAIL (' + dupCount + ')'}`);
  report.push(`resource-floor: ${(state.metal >= 0 && state.energy >= 0) ? 'PASS' : 'FAIL'}`);
  report.push(`object-count: ${flat.length}`);
  state.lastAudit = report.join('\n');
  auditLog.textContent = `Audit @ ${new Date().toLocaleTimeString()}\n${state.lastAudit}`;
}

function update(dt) {
  if (state.paused || state.won) return;

  runGR(); hiddenBuffs();

  for (const b of state.buildings) {
    if (!b.alive || b.team !== 'player') continue;
    if (b.type === 'refinery') state.metal += dt * 12;
    if (b.type === 'power') state.energy += dt * 11;
    if (b.type === 'hq') { state.metal += dt * 4; state.energy += dt * 4; }
    if (b.type === 'turret') {
      const e = state.enemyUnits.find((u) => u.alive && Math.hypot(u.x - b.x, u.y - b.y) < 210);
      if (e) { e.hp -= 12 * dt; if (Math.random() < 0.12) audio.beep(120, 0.03, 'square'); }
    }
  }

  for (const u of state.playerUnits) {
    if (!u.alive || !u.gather || !u.gather.alive) continue;
    const d = Math.hypot(u.gather.x - u.x, u.gather.y - u.y);
    if (d > 16) { u.tx = u.gather.x; u.ty = u.gather.y; }
    else if (u.gather.amount > 0) {
      const amt = Math.min(u.gather.amount, dt * 16);
      u.gather.amount -= amt; state.metal += amt * 0.8; state.energy += amt * 0.25;
      if (u.gather.amount <= 0) u.gather.alive = false;
    }
  }

  if (Math.random() < dt * 0.16) {
    const p = state.playerUnits.find((u) => u.alive) || state.buildings.find((b) => b.team === 'player' && b.alive);
    if (p) state.enemyUnits.filter((u) => u.alive).slice(0, 8).forEach((u) => { u.tx = p.x + rnd(-120, 120); u.ty = p.y + rnd(-80, 80); u.target = p; });
  }

  for (const u of [...state.playerUnits, ...state.enemyUnits]) {
    if (!u.alive) continue;
    const tgt = u.target && u.target.alive ? u.target : nearestEnemy(u);
    const dEnemy = tgt ? Math.hypot(tgt.x - u.x, tgt.y - u.y) : 1e9;
    if (tgt && dEnemy < u.rng) {
      u.cd -= dt;
      if (u.cd <= 0) { u.cd = u.maxCd; state.projectiles.push({ x: u.x, y: u.y, tx: tgt.x, ty: tgt.y, dmg: u.dmg, team: u.team, life: 0.35 }); }
    } else {
      const tx = (u.target && u.target.alive) ? u.target.x : u.tx;
      const ty = (u.target && u.target.alive) ? u.target.y : u.ty;
      const dx = tx - u.x, dy = ty - u.y, d = Math.hypot(dx, dy);
      if (d > 2) { u.x += dx / d * u.spd * 60 * dt; u.y += dy / d * u.spd * 60 * dt; }
    }
    u.x = clamp(u.x, 0, world.w); u.y = clamp(u.y, 0, world.h);
  }

  for (const p of state.projectiles) {
    p.life -= dt;
    const dx = p.tx - p.x, dy = p.ty - p.y, d = Math.hypot(dx, dy) || 1;
    p.x += dx / d * 860 * dt; p.y += dy / d * 860 * dt;
    const pool = p.team === 'player' ? [...state.enemyUnits, ...state.buildings] : [...state.playerUnits, ...state.buildings];
    const hit = pool.find((e) => e.alive && e.team !== p.team && Math.hypot(e.x - p.x, e.y - p.y) < (e.r || 8) + 4);
    if (hit) {
      hit.hp -= p.dmg; p.life = -1;
      for (let i = 0; i < 4; i++) state.particles.push({ x: hit.x + rnd(-8, 8), y: hit.y + rnd(-8, 8), life: 0.35, col: '#ffd2a8', r: rnd(2, 5) });
      audio.beep(90 + Math.random() * 40, 0.04, 'triangle');
    }
  }
  state.projectiles = state.projectiles.filter((p) => p.life > 0);

  for (const arr of [state.playerUnits, state.enemyUnits, state.buildings]) {
    for (const o of arr) if (o.alive && o.hp <= 0) { o.alive = false; if (o.type === 'core' && o.team === 'enemy') state.enemyCoresDestroyed++; }
  }
  if (state.enemyCoresDestroyed >= 3) { state.won = true; status('Victory. The Iron Eclipse rises.'); audio.beep(880, 0.2, 'sine'); }

  for (const p of state.particles) p.life -= dt;
  state.particles = state.particles.filter((p) => p.life > 0);

  if (mouse.x < 16) cam.x -= cam.speed;
  if (mouse.y < 16) cam.y -= cam.speed;
  if (mouse.x > W - 16) cam.x += cam.speed;
  if (mouse.y > H - 16) cam.y += cam.speed;
  cam.x = clamp(cam.x, 0, world.w - W); cam.y = clamp(cam.y, 0, world.h - H);

  state.metal = clamp(state.metal, 0, 999999);
  state.energy = clamp(state.energy, 0, 999999);
  resourcesEl.textContent = `Metal: ${state.metal | 0} | Energy: ${state.energy | 0} | Units: ${state.playerUnits.filter((u) => u.alive).length}`;
}

function drawGrid() {
  ctx.fillStyle = '#0b1b30'; ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = 'rgba(80,130,180,0.15)'; ctx.lineWidth = 1;
  for (let x = -cam.x % 60; x < W; x += 60) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
  for (let y = -cam.y % 60; y < H; y += 60) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
}

function draw() {
  drawGrid();
  for (const r of state.resources) if (r.alive) { const s = worldToScreen(r.x, r.y); ctx.fillStyle = '#7ed6ff'; ctx.beginPath(); ctx.arc(s.x, s.y, r.r, 0, Math.PI * 2); ctx.fill(); }
  for (const b of state.buildings) if (b.alive) {
    const s = worldToScreen(b.x, b.y);
    ctx.fillStyle = b.col; ctx.fillRect(s.x - b.r, s.y - b.r, b.r * 2, b.r * 2);
    ctx.fillStyle = '#0008'; ctx.fillRect(s.x - b.r, s.y - b.r - 7, b.r * 2, 4);
    ctx.fillStyle = '#87ff8f'; ctx.fillRect(s.x - b.r, s.y - b.r - 7, (b.hp / b.maxHp) * b.r * 2, 4);
  }
  for (const u of [...state.playerUnits, ...state.enemyUnits]) if (u.alive) {
    const s = worldToScreen(u.x, u.y);
    ctx.fillStyle = u.team === 'player' ? u.col : '#ff8f8f'; ctx.beginPath(); ctx.arc(s.x, s.y, u.r, 0, Math.PI * 2); ctx.fill();
    if (u.selected) { ctx.strokeStyle = '#d5f0ff'; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(s.x, s.y, u.r + 4, 0, Math.PI * 2); ctx.stroke(); }
  }
  for (const p of state.projectiles) { const s = worldToScreen(p.x, p.y); ctx.fillStyle = '#ffd18f'; ctx.fillRect(s.x - 2, s.y - 2, 4, 4); }
  for (const p of state.particles) { const s = worldToScreen(p.x, p.y); ctx.globalAlpha = p.life; ctx.fillStyle = p.col; ctx.beginPath(); ctx.arc(s.x, s.y, p.r, 0, Math.PI * 2); ctx.fill(); ctx.globalAlpha = 1; }
  if (state.drag) { ctx.strokeStyle = '#98ddff'; ctx.strokeRect(state.drag.x1, state.drag.y1, state.drag.x2 - state.drag.x1, state.drag.y2 - state.drag.y1); }
  if (state.buildMode) { ctx.fillStyle = '#ffffffd0'; ctx.fillText(`Place ${state.buildMode}`, 12, H - 14); }
  if (state.paused) { ctx.fillStyle = 'rgba(0,0,0,0.45)'; ctx.fillRect(0, 0, W, H); ctx.fillStyle = '#fff'; ctx.font = 'bold 32px sans-serif'; ctx.fillText('PAUSED', W / 2 - 60, H / 2); }
}

function bindUI() {
  cvs.addEventListener('mousemove', (e) => {
    const rect = cvs.getBoundingClientRect();
    mouse.x = (e.clientX - rect.left) * (W / rect.width);
    mouse.y = (e.clientY - rect.top) * (H / rect.height);
    if (state.drag) { state.drag.x2 = mouse.x; state.drag.y2 = mouse.y; }
  });

  cvs.addEventListener('mousedown', (e) => {
    if (e.button !== 0 || state.paused) return;
    audio.ensure();
    if (state.buildMode) { const w = screenToWorld(mouse.x, mouse.y); placeBuilding(w.x, w.y); return; }
    state.drag = { x1: mouse.x, y1: mouse.y, x2: mouse.x, y2: mouse.y };
  });

  window.addEventListener('mouseup', (e) => {
    if (e.button !== 0 || !state.drag || state.paused) return;
    const d = state.drag, minx = Math.min(d.x1, d.x2), maxx = Math.max(d.x1, d.x2), miny = Math.min(d.y1, d.y2), maxy = Math.max(d.y1, d.y2);
    const click = (maxx - minx) < 5 && (maxy - miny) < 5;
    state.select = []; for (const u of state.playerUnits) u.selected = false;
    if (click) {
      const w = screenToWorld(mouse.x, mouse.y);
      const unit = state.playerUnits.find((u) => u.alive && Math.hypot(u.x - w.x, u.y - w.y) < u.r + 6);
      if (unit) { unit.selected = true; state.select.push(unit); audio.beep(700, 0.04, 'triangle'); }
    } else {
      for (const u of state.playerUnits) if (u.alive) {
        const s = worldToScreen(u.x, u.y);
        if (s.x >= minx && s.x <= maxx && s.y >= miny && s.y <= maxy) { u.selected = true; state.select.push(u); }
      }
      if (state.select.length) audio.beep(600, 0.05, 'triangle');
    }
    state.drag = null;
  });

  cvs.addEventListener('contextmenu', (e) => {
    e.preventDefault();
    if (state.paused) return;
    const w = screenToWorld(mouse.x, mouse.y);
    if (state.select.length) commandSelected(w.x, w.y);
  });

  window.addEventListener('keydown', (e) => {
    if (e.key === ' ') state.paused = !state.paused;
    if (e.key.toLowerCase() === 'm') { audio.setMuted(!state.muted); document.getElementById('btn-mute').textContent = `Sound: ${state.muted ? 'Off' : 'On'}`; }
    if (e.key === '1') state.buildMode = 'refinery';
    if (e.key === '2') state.buildMode = 'power';
    if (e.key === '3') state.buildMode = 'barracks';
    if (e.key === '4') state.buildMode = 'turret';
    if (e.key.toLowerCase() === 'q') spawnFromBarracks('infantry');
    if (e.key.toLowerCase() === 'w') spawnFromBarracks('tank');
    if (e.key.toLowerCase() === 'e') spawnFromBarracks('air');
  });

  for (const b of document.querySelectorAll('[data-build]')) b.onclick = () => state.buildMode = b.dataset.build;
  document.getElementById('train-inf').onclick = () => spawnFromBarracks('infantry');
  document.getElementById('train-tank').onclick = () => spawnFromBarracks('tank');
  document.getElementById('train-air').onclick = () => spawnFromBarracks('air');
  document.getElementById('btn-pause').onclick = () => { state.paused = !state.paused; };
  document.getElementById('btn-mute').onclick = () => { audio.setMuted(!state.muted); document.getElementById('btn-mute').textContent = `Sound: ${state.muted ? 'Off' : 'On'}`; };
  document.getElementById('btn-save').onclick = saveGame;
  document.getElementById('btn-load').onclick = loadGame;
  document.getElementById('btn-audit').onclick = runtimeAudit;
}

let last = performance.now();
function loop(t) {
  const dt = clamp((t - last) / 1000, 0, 0.033);
  last = t;
  update(dt);
  draw();
  requestAnimationFrame(loop);
}

init();
bindUI();
runtimeAudit();
requestAnimationFrame(loop);
