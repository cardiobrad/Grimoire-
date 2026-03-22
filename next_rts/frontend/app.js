const canvas = document.getElementById('field');
const ctx = canvas.getContext('2d');
const report = document.getElementById('report');

const seedPoints = [
  { x: 18, y: 18 }, { x: 21, y: 18 }, { x: 24, y: 20 },
  { x: 20, y: 23 }, { x: 16, y: 22 }, { x: 19, y: 20 },
];

const units = seedPoints.map((p, i) => ({ id: `u-${i + 1}`, x: p.x * 5, y: p.y * 5, role: i === 0 ? 'command' : 'worker' }));

function drawField(field) {
  const n = field.length;
  const cell = canvas.width / n;
  let max = 0;
  for (const row of field) for (const v of row) max = Math.max(max, v);
  const norm = max > 0 ? max : 1;

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  for (let y = 0; y < n; y++) {
    for (let x = 0; x < n; x++) {
      const t = field[y][x] / norm;
      const hue = 240 - Math.round(t * 220);
      const alpha = Math.max(0.05, t);
      ctx.fillStyle = `hsla(${hue}, 90%, ${30 + t * 30}%, ${alpha})`;
      ctx.fillRect(x * cell, y * cell, cell + 0.4, cell + 0.4);
    }
  }
}

async function scoreSeed() {
  const res = await fetch('/api/seed/score', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ points: seedPoints, units }),
  });
  const data = await res.json();
  drawField(data.field);
  report.textContent = [
    `GSM: ${data.gsm.score}  (${data.gsm.classification})`,
    `A:${data.gsm.components.amplitude} R:${data.gsm.components.core_radius} M:${data.gsm.components.concentrated_mass}`,
    `T:${data.gsm.components.topology} G:${data.gsm.components.gradient}`,
    '',
    'Strengths:',
    ...data.gsm.strengths.slice(0, 3).map((s) => `+ ${s}`),
    '',
    'Recommendations:',
    ...data.gsm.recommendations.slice(0, 3).map((s) => `- ${s}`),
  ].join('\n');
}

async function stepField() {
  const res = await fetch('/api/field/step', { method: 'POST' });
  const data = await res.json();
  drawField(data.field);
}

document.getElementById('score').addEventListener('click', scoreSeed);
document.getElementById('step').addEventListener('click', stepField);
