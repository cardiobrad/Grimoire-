import { useState, useEffect, useRef, useCallback } from "react";

// ============================================================
// GRIMOIRE LOCKED PARAMETERS
// ============================================================
const D_DEFAULT = 0.12;
const LAMBDA_DEFAULT = 0.45;
const ALPHA = Math.PI;
const DX = 1.0;
const DT = 0.01;
const GRID = 48;

// Exact effective potential V(U)
function V(U) {
  const term1 = (-U * U / Math.PI + 2 / (Math.PI * Math.PI * Math.PI)) * Math.cos(Math.PI * U);
  const term2 = (2 * U / (Math.PI * Math.PI)) * Math.sin(Math.PI * U);
  return -0.45 * (term1 + term2);
}

// Reaction term
function reaction(U, lambda) {
  return lambda * U * U * Math.sin(ALPHA * U);
}

// Color mapping: U value → RGB
function uToColor(u) {
  if (u < 0.1) return [10, 10, 18];
  if (u < 1.0) {
    const t = u / 1.0;
    return [10 + t * 20, 10 + t * 50, 18 + t * 60];
  }
  if (u < 2.0) {
    const t = (u - 1.0);
    return [30 + t * 200, 60 - t * 20, 78 - t * 40];
  }
  if (u < 3.0) {
    const t = (u - 2.0);
    return [230 - t * 30, 40 + t * 180, 38 + t * 50];
  }
  return [200, 220, 88];
}

const SEED_TYPES = [
  { id: "attractor", label: "Attractor", desc: "Concentrated peak — nucleation seed", amp: 2.5 },
  { id: "repulsor", label: "Repulsor", desc: "Outward gradient — dispersive seed", amp: 1.8 },
  { id: "oscillator", label: "Oscillator", desc: "Ring pattern — phase structure", amp: 2.2 },
  { id: "gate", label: "Gate", desc: "Narrow channel — separatrix probe", amp: 2.0 },
  { id: "source", label: "Source", desc: "Constant high — super-critical", amp: 3.0 },
  { id: "eraser", label: "Eraser", desc: "Reset to U=0", amp: 0 },
];

export default function WhitePlayground() {
  const canvasRef = useRef(null);
  const potentialRef = useRef(null);
  const fieldRef = useRef(null);
  const runningRef = useRef(false);
  const frameRef = useRef(null);
  const stepsRef = useRef(0);

  const [running, setRunning] = useState(false);
  const [seedType, setSeedType] = useState("attractor");
  const [brushSize, setBrushSize] = useState(3);
  const [diffusion, setDiffusion] = useState(D_DEFAULT);
  const [lambda, setLambda] = useState(LAMBDA_DEFAULT);
  const [stats, setStats] = useState({ mean: 0, max: 0, min: 0, step: 0 });
  const [showPotential, setShowPotential] = useState(true);

  // Initialize field
  useEffect(() => {
    fieldRef.current = new Float64Array(GRID * GRID).fill(0);
    drawField();
  }, []);

  // Redraw potential when toggled
  useEffect(() => {
    if (showPotential) {
      setTimeout(() => drawPotential(), 50);
    }
  }, [showPotential]);

  // Sync running ref
  useEffect(() => {
    runningRef.current = running;
    if (running) {
      frameRef.current = requestAnimationFrame(simulate);
    }
    return () => {
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
    };
  }, [running, diffusion, lambda]);

  const simulate = useCallback(() => {
    if (!runningRef.current || !fieldRef.current) return;

    const U = fieldRef.current;
    const N = GRID;
    const next = new Float64Array(N * N);
    const D = diffusion;
    const lam = lambda;
    const dx2 = DX * DX;

    // Run multiple substeps per frame for speed
    const substeps = 8;
    let src = U;
    let dst = next;

    for (let sub = 0; sub < substeps; sub++) {
      for (let i = 0; i < N; i++) {
        for (let j = 0; j < N; j++) {
          const idx = i * N + j;
          const u = src[idx];

          // Periodic boundary Laplacian
          const ip = ((i + 1) % N) * N + j;
          const im = ((i - 1 + N) % N) * N + j;
          const jp = i * N + ((j + 1) % N);
          const jm = i * N + ((j - 1 + N) % N);

          const lap = (src[ip] + src[im] + src[jp] + src[jm] - 4 * u) / dx2;
          const react = lam * u * u * Math.sin(ALPHA * u);

          dst[idx] = Math.max(0, u + DT * (D * lap + react));
        }
      }
      // Swap
      const tmp = src;
      src = dst;
      dst = tmp;
    }

    // Copy result back
    if (src !== U) {
      for (let i = 0; i < N * N; i++) U[i] = src[i];
    } else {
      for (let i = 0; i < N * N; i++) U[i] = src[i];
    }

    stepsRef.current += substeps;

    // Stats every few frames
    if (stepsRef.current % 16 === 0) {
      let sum = 0, mx = 0, mn = 999;
      for (let i = 0; i < N * N; i++) {
        sum += U[i];
        if (U[i] > mx) mx = U[i];
        if (U[i] < mn) mn = U[i];
      }
      setStats({
        mean: (sum / (N * N)).toFixed(3),
        max: mx.toFixed(3),
        min: mn.toFixed(3),
        step: stepsRef.current,
      });
    }

    drawField();
    frameRef.current = requestAnimationFrame(simulate);
  }, [diffusion, lambda]);

  const drawField = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !fieldRef.current) return;
    const ctx = canvas.getContext("2d");
    const U = fieldRef.current;
    const N = GRID;
    const cellW = canvas.width / N;
    const cellH = canvas.height / N;

    const imageData = ctx.createImageData(canvas.width, canvas.height);
    const data = imageData.data;

    for (let i = 0; i < N; i++) {
      for (let j = 0; j < N; j++) {
        const u = U[i * N + j];
        const [r, g, b] = uToColor(u);

        const startY = Math.floor(i * cellH);
        const endY = Math.floor((i + 1) * cellH);
        const startX = Math.floor(j * cellW);
        const endX = Math.floor((j + 1) * cellW);

        for (let py = startY; py < endY; py++) {
          for (let px = startX; px < endX; px++) {
            const pidx = (py * canvas.width + px) * 4;
            data[pidx] = r;
            data[pidx + 1] = g;
            data[pidx + 2] = b;
            data[pidx + 3] = 255;
          }
        }
      }
    }
    ctx.putImageData(imageData, 0, 0);

    // Grid overlay (subtle)
    ctx.strokeStyle = "rgba(255,255,255,0.03)";
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= N; i++) {
      ctx.beginPath();
      ctx.moveTo(i * cellW, 0);
      ctx.lineTo(i * cellW, canvas.height);
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(0, i * cellH);
      ctx.lineTo(canvas.width, i * cellH);
      ctx.stroke();
    }
  }, []);

  const drawPotential = useCallback(() => {
    const canvas = potentialRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;

    ctx.fillStyle = "#0a0a12";
    ctx.fillRect(0, 0, w, h);

    // Draw V(U) from U=0 to U=4
    const uMin = 0, uMax = 4;
    const vVals = [];
    for (let px = 0; px < w; px++) {
      const u = uMin + (px / w) * (uMax - uMin);
      vVals.push(V(u));
    }
    const vMin = Math.min(...vVals) - 0.1;
    const vMax = Math.max(...vVals) + 0.1;

    // Axis
    ctx.strokeStyle = "rgba(255,255,255,0.15)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, h * 0.5);
    ctx.lineTo(w, h * 0.5);
    ctx.stroke();

    // V(U) curve
    ctx.strokeStyle = "#e8a030";
    ctx.lineWidth = 2;
    ctx.beginPath();
    for (let px = 0; px < w; px++) {
      const y = h - ((vVals[px] - vMin) / (vMax - vMin)) * h;
      if (px === 0) ctx.moveTo(px, y);
      else ctx.lineTo(px, y);
    }
    ctx.stroke();

    // Mark fixed points
    const marks = [
      { u: 0, label: "U=0", color: "#666" },
      { u: 1, label: "U=1", color: "#4488cc" },
      { u: 2, label: "U=2", color: "#cc4444" },
      { u: 3, label: "U=3", color: "#44cc66" },
    ];

    ctx.font = "10px 'IBM Plex Mono', monospace";
    marks.forEach(({ u, label, color }) => {
      const px = (u / (uMax - uMin)) * w;
      const vy = V(u);
      const py = h - ((vy - vMin) / (vMax - vMin)) * h;

      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(px, py, 4, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = "rgba(255,255,255,0.7)";
      ctx.fillText(label, px - 12, py - 8);
    });

    // Labels
    ctx.fillStyle = "rgba(255,255,255,0.4)";
    ctx.font = "9px 'IBM Plex Mono', monospace";
    ctx.fillText("V(U) Effective Potential", 4, 12);
    ctx.fillText(`V(1)≈${V(1).toFixed(3)}`, 4, h - 24);
    ctx.fillText(`V(3)≈${V(3).toFixed(3)}`, 4, h - 12);
  }, []);

  const plantSeed = useCallback((canvasX, canvasY) => {
    const canvas = canvasRef.current;
    if (!canvas || !fieldRef.current) return;
    const U = fieldRef.current;
    const N = GRID;
    const cellW = canvas.width / N;
    const cellH = canvas.height / N;

    const gj = Math.floor(canvasX / cellW);
    const gi = Math.floor(canvasY / cellH);
    const seed = SEED_TYPES.find((s) => s.id === seedType);
    if (!seed) return;

    const r = brushSize;
    for (let di = -r; di <= r; di++) {
      for (let dj = -r; dj <= r; dj++) {
        const dist = Math.sqrt(di * di + dj * dj);
        if (dist > r) continue;

        const ni = ((gi + di) % N + N) % N;
        const nj = ((gj + dj) % N + N) % N;
        const idx = ni * N + nj;

        switch (seed.id) {
          case "attractor":
            U[idx] = Math.max(U[idx], seed.amp * (1 - dist / r));
            break;
          case "repulsor":
            U[idx] = Math.max(U[idx], seed.amp * (dist / r));
            break;
          case "oscillator":
            U[idx] = Math.max(U[idx], seed.amp * (0.5 + 0.5 * Math.sin(Math.PI * Math.floor(dist))));
            break;
          case "gate":
            if (Math.abs(dj) <= 1) U[idx] = Math.max(U[idx], 0.3);
            else U[idx] = Math.max(U[idx], seed.amp * (1 - dist / r));
            break;
          case "source":
            U[idx] = seed.amp;
            break;
          case "eraser":
            U[idx] = 0;
            break;
        }
      }
    }
    drawField();
  }, [seedType, brushSize, drawField]);

  const handleCanvasClick = useCallback((e) => {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (e.clientX - rect.left) * scaleX;
    const y = (e.clientY - rect.top) * scaleY;
    plantSeed(x, y);
  }, [plantSeed]);

  const handleTouchCanvas = useCallback((e) => {
    e.preventDefault();
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const touch = e.touches[0];
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x = (touch.clientX - rect.left) * scaleX;
    const y = (touch.clientY - rect.top) * scaleY;
    plantSeed(x, y);
  }, [plantSeed]);

  const resetField = () => {
    fieldRef.current = new Float64Array(GRID * GRID).fill(0);
    stepsRef.current = 0;
    setStats({ mean: 0, max: 0, min: 0, step: 0 });
    drawField();
  };

  const fillBaseline = () => {
    fieldRef.current = new Float64Array(GRID * GRID).fill(1.0);
    drawField();
  };

  return (
    <div style={{
      background: "#08080e",
      color: "#d0d0d0",
      minHeight: "100vh",
      fontFamily: "'IBM Plex Mono', 'Fira Code', 'Courier New', monospace",
      padding: "12px",
      boxSizing: "border-box",
    }}>
      {/* Header */}
      <div style={{ borderBottom: "1px solid #1a1a2e", paddingBottom: 8, marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontSize: 18, fontWeight: 700, color: "#e8a030", letterSpacing: 2 }}>
            WHITE PLAYGROUND
          </span>
          <span style={{ fontSize: 11, color: "#555", letterSpacing: 1 }}>
            GRIMOIRE FIELD SIMULATOR
          </span>
        </div>
        <div style={{ fontSize: 9, color: "#444", marginTop: 2, letterSpacing: 0.5 }}>
          ∂U/∂t = D∇²U + λU²sin(πU) &nbsp;|&nbsp; D={diffusion} &nbsp; λ={lambda} &nbsp; α=π &nbsp; dx={DX} &nbsp; dt={DT}
        </div>
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        {/* Main canvas */}
        <div style={{ flex: "1 1 340px", minWidth: 280 }}>
          <canvas
            ref={canvasRef}
            width={480}
            height={480}
            onClick={handleCanvasClick}
            onTouchStart={handleTouchCanvas}
            style={{
              width: "100%",
              maxWidth: 480,
              aspectRatio: "1",
              border: "1px solid #1a1a2e",
              borderRadius: 4,
              cursor: "crosshair",
              imageRendering: "pixelated",
            }}
          />
          {/* Color legend */}
          <div style={{ display: "flex", gap: 8, marginTop: 6, fontSize: 9, color: "#666", flexWrap: "wrap" }}>
            <span><span style={{ color: "#1e3c50" }}>■</span> U≈0</span>
            <span><span style={{ color: "#2e4e60" }}>■</span> U≈1 basin</span>
            <span><span style={{ color: "#e83020" }}>■</span> U≈2 barrier</span>
            <span><span style={{ color: "#c8dc58" }}>■</span> U≈3 attractor</span>
          </div>
        </div>

        {/* Controls panel */}
        <div style={{ flex: "0 0 220px", display: "flex", flexDirection: "column", gap: 10 }}>
          {/* Transport */}
          <div style={{ display: "flex", gap: 6 }}>
            <button onClick={() => setRunning(!running)} style={btnStyle(running ? "#cc4444" : "#44aa66")}>
              {running ? "■ STOP" : "▶ RUN"}
            </button>
            <button onClick={resetField} style={btnStyle("#555")}>CLEAR</button>
            <button onClick={fillBaseline} style={btnStyle("#335")}>U=1</button>
          </div>

          {/* Seed type */}
          <div>
            <div style={labelStyle}>SEED TYPE</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              {SEED_TYPES.map((s) => (
                <button
                  key={s.id}
                  onClick={() => setSeedType(s.id)}
                  style={{
                    ...btnStyle(seedType === s.id ? "#e8a030" : "#222"),
                    color: seedType === s.id ? "#000" : "#888",
                    textAlign: "left",
                    fontSize: 10,
                    padding: "4px 8px",
                  }}
                >
                  {s.label} <span style={{ color: seedType === s.id ? "#333" : "#555", fontSize: 9 }}>
                    {s.desc}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Brush */}
          <div>
            <div style={labelStyle}>BRUSH RADIUS: {brushSize}</div>
            <input
              type="range" min={1} max={8} value={brushSize}
              onChange={(e) => setBrushSize(Number(e.target.value))}
              style={{ width: "100%" }}
            />
          </div>

          {/* Diffusion */}
          <div>
            <div style={labelStyle}>DIFFUSION D: {diffusion.toFixed(3)}</div>
            <input
              type="range" min={0.01} max={2.0} step={0.01} value={diffusion}
              onChange={(e) => setDiffusion(Number(e.target.value))}
              style={{ width: "100%" }}
            />
            <div style={{ fontSize: 9, color: "#555" }}>
              D/dx² = {(diffusion / (DX * DX)).toFixed(3)}
              {diffusion / (DX * DX) < 1.5
                ? " — PINNED regime"
                : " — PROPAGATING regime"}
            </div>
          </div>

          {/* Lambda */}
          <div>
            <div style={labelStyle}>REACTION λ: {lambda.toFixed(3)}</div>
            <input
              type="range" min={0.05} max={1.0} step={0.01} value={lambda}
              onChange={(e) => setLambda(Number(e.target.value))}
              style={{ width: "100%" }}
            />
          </div>

          {/* Stats */}
          <div style={{
            background: "#0d0d18",
            border: "1px solid #1a1a2e",
            borderRadius: 4,
            padding: 8,
            fontSize: 10,
          }}>
            <div style={labelStyle}>FIELD STATE</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2px 12px" }}>
              <span style={{ color: "#666" }}>Step:</span>
              <span>{stats.step}</span>
              <span style={{ color: "#666" }}>Mean U:</span>
              <span>{stats.mean}</span>
              <span style={{ color: "#666" }}>Max U:</span>
              <span style={{ color: Number(stats.max) > 2.5 ? "#44cc66" : "#d0d0d0" }}>{stats.max}</span>
              <span style={{ color: "#666" }}>Min U:</span>
              <span>{stats.min}</span>
              <span style={{ color: "#666" }}>Grid:</span>
              <span>{GRID}×{GRID}</span>
            </div>
          </div>

          {/* V(U) Potential */}
          <div>
            <button
              onClick={() => setShowPotential(!showPotential)}
              style={{ ...btnStyle("#1a1a2e"), fontSize: 10, width: "100%" }}
            >
              {showPotential ? "▼" : "▶"} V(U) POTENTIAL
            </button>
            {showPotential && (
              <canvas
                ref={potentialRef}
                width={220}
                height={120}
                style={{
                  width: "100%",
                  border: "1px solid #1a1a2e",
                  borderRadius: 4,
                  marginTop: 4,
                }}
              />
            )}
          </div>

          {/* Info */}
          <div style={{ fontSize: 9, color: "#444", lineHeight: 1.4 }}>
            Click the field to place seeds. The SIN engine
            creates wells at U=1,3 and a barrier at U=2.
            Below D/dx²≈1.5: seeds ignite locally but
            fronts stay pinned. Above: waves propagate.
          </div>
        </div>
      </div>
    </div>
  );
}

const labelStyle = {
  fontSize: 9,
  color: "#666",
  letterSpacing: 1,
  marginBottom: 3,
  textTransform: "uppercase",
};

const btnStyle = (bg) => ({
  background: bg,
  color: "#ddd",
  border: "none",
  borderRadius: 3,
  padding: "6px 10px",
  fontSize: 11,
  fontFamily: "'IBM Plex Mono', monospace",
  cursor: "pointer",
  flex: 1,
});
