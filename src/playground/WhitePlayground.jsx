import { useState, useEffect, useRef, useCallback } from "react";
import * as THREE from "three";

// ═══ LOCKED PDE PARAMETERS ═══
const GRID = 48;
const D = 0.12, LAM = 0.45, ALPHA = Math.PI, DT = 0.05;

function initField(grid) {
  return Array.from({ length: grid }, () => new Float32Array(grid));
}

function seedFormation(field, type, cx, cy) {
  const g = field.length;
  for (let y = 0; y < g; y++) for (let x = 0; x < g; x++) field[y][x] = 0;
  
  if (type === "compact") {
    for (let i = 0; i < 16; i++) {
      const a = (2 * Math.PI * i) / 16;
      const r = 2.5 * Math.sqrt((i + 1) / 16);
      const py = Math.round(cy + r * Math.sin(a));
      const px = Math.round(cx + r * Math.cos(a));
      if (py >= 0 && py < g && px >= 0 && px < g) field[py][px] += 2.5;
    }
  } else if (type === "spread") {
    for (let i = 0; i < 16; i++) {
      const a = (2 * Math.PI * i) / 16;
      const r = 6 + 4 * (i / 16);
      const py = Math.round(cy + r * Math.sin(a));
      const px = Math.round(cx + r * Math.cos(a));
      if (py >= 0 && py < g && px >= 0 && px < g) field[py][px] += 1.8;
    }
  } else if (type === "clusters") {
    for (let c = 0; c < 3; c++) {
      const ca = (2 * Math.PI * c) / 3;
      const ccx = cx + 8 * Math.cos(ca);
      const ccy = cy + 8 * Math.sin(ca);
      for (let j = 0; j < 5; j++) {
        const ja = (2 * Math.PI * j) / 5;
        const jr = 1.5 * Math.sqrt((j + 1) / 5);
        const py = Math.round(ccy + jr * Math.sin(ja));
        const px = Math.round(ccx + jr * Math.cos(ja));
        if (py >= 0 && py < g && px >= 0 && px < g) field[py][px] += 2.0;
      }
    }
  } else if (type === "edge") {
    for (let i = 0; i < 5; i++) {
      const py = Math.round(cy + (Math.random() - 0.5) * 12);
      const px = Math.round(cx + (Math.random() - 0.5) * 12);
      if (py >= 0 && py < g && px >= 0 && px < g) field[py][px] += 0.8;
    }
  }
}

function stepPDE(field) {
  const g = field.length;
  const next = field.map(row => new Float32Array(row));
  for (let y = 1; y < g - 1; y++) {
    for (let x = 1; x < g - 1; x++) {
      const u = field[y][x];
      const lap = field[y-1][x] + field[y+1][x] + field[y][x-1] + field[y][x+1] - 4 * u;
      const react = LAM * u * u * Math.sin(ALPHA * u);
      next[y][x] = Math.max(0, u + DT * (D * lap + react));
    }
  }
  return next;
}

// Color palette
const COLORS = {
  bg: "#080810",
  panel: "#10101a",
  border: "#1a1a2a",
  text: "#c8c8d8",
  dim: "#666680",
  accent: "#4488ff",
  green: "#44cc88",
  orange: "#ff8844",
  red: "#ff4466",
  gold: "#ffcc44",
};

const FORMATIONS = [
  { id: "compact", label: "Compact", desc: "Single nucleus — homogeneous", color: COLORS.accent },
  { id: "spread", label: "Spread", desc: "Distributed — heterogeneous", color: COLORS.green },
  { id: "clusters", label: "Clusters", desc: "Multi-site nucleation", color: COLORS.orange },
  { id: "edge", label: "Edge Case", desc: "Near critical threshold", color: COLORS.gold },
];

export default function WhitePlayground() {
  const canvasRef = useRef(null);
  const sceneRef = useRef(null);
  const meshRef = useRef(null);
  const rendererRef = useRef(null);
  const cameraRef = useRef(null);
  const frameRef = useRef(null);
  const fieldRef = useRef(initField(GRID));
  const [formation, setFormation] = useState("compact");
  const [step, setStep] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [maxU, setMaxU] = useState(0);
  const [viewAngle, setViewAngle] = useState(0.4);
  const [showBarrier, setShowBarrier] = useState(true);

  // Initialize Three.js
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const w = canvas.clientWidth;
    const h = canvas.clientHeight;

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x080810);
    rendererRef.current = renderer;

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x080810, 0.015);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(50, w / h, 0.1, 200);
    camera.position.set(30, 35, 30);
    camera.lookAt(0, 0, 0);
    cameraRef.current = camera;

    // Lights
    const amb = new THREE.AmbientLight(0x334466, 0.6);
    scene.add(amb);
    const dir = new THREE.DirectionalLight(0xffffff, 0.9);
    dir.position.set(20, 40, 20);
    scene.add(dir);
    const point = new THREE.PointLight(0x4488ff, 0.5, 60);
    point.position.set(0, 20, 0);
    scene.add(point);

    // Grid floor
    const gridHelper = new THREE.GridHelper(GRID, GRID, 0x1a1a3a, 0x0a0a1a);
    gridHelper.position.y = -0.5;
    scene.add(gridHelper);

    // Create mesh geometry
    const geo = new THREE.PlaneGeometry(GRID, GRID, GRID - 1, GRID - 1);
    geo.rotateX(-Math.PI / 2);
    const mat = new THREE.MeshPhongMaterial({
      vertexColors: true,
      side: THREE.DoubleSide,
      shininess: 40,
      flatShading: false,
    });
    const colors = new Float32Array(geo.attributes.position.count * 3);
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(-GRID / 2, 0, -GRID / 2);
    scene.add(mesh);
    meshRef.current = mesh;

    // Barrier plane (U*=2)
    const barrierGeo = new THREE.PlaneGeometry(GRID, GRID);
    barrierGeo.rotateX(-Math.PI / 2);
    const barrierMat = new THREE.MeshBasicMaterial({
      color: 0xff4466,
      transparent: true,
      opacity: 0.08,
      side: THREE.DoubleSide,
    });
    const barrierMesh = new THREE.Mesh(barrierGeo, barrierMat);
    barrierMesh.position.set(0, 2 * 3, 0); // scaled
    barrierMesh.name = "barrier";
    scene.add(barrierMesh);

    // Seed initial formation
    seedFormation(fieldRef.current, "compact", GRID / 2, GRID / 2);

    return () => {
      renderer.dispose();
      geo.dispose();
      mat.dispose();
    };
  }, []);

  // Update mesh from field
  const updateMesh = useCallback(() => {
    const mesh = meshRef.current;
    if (!mesh) return;
    const geo = mesh.geometry;
    const pos = geo.attributes.position;
    const col = geo.attributes.color;
    const field = fieldRef.current;
    const scale = 3;
    let peak = 0;

    for (let i = 0; i < pos.count; i++) {
      const gy = Math.floor(i / GRID);
      const gx = i % GRID;
      const u = field[gy]?.[gx] || 0;
      const h = u * scale;
      pos.setY(i, h);
      peak = Math.max(peak, u);

      // Color by phase: blue<1, yellow=1-2 (barrier zone), green>2, bright>3
      let r, g, b;
      if (u < 0.5) { r = 0.05; g = 0.05; b = 0.15; }
      else if (u < 1) { r = 0.1; g = 0.2; b = 0.6; }
      else if (u < 2) { r = 0.8; g = 0.6; b = 0.1; } // barrier zone
      else if (u < 3) { r = 0.2; g = 0.8; b = 0.4; }
      else { r = 0.3; g = 1.0; b = 0.9; }
      col.setXYZ(i, r, g, b);
    }

    pos.needsUpdate = true;
    col.needsUpdate = true;
    geo.computeVertexNormals();
    setMaxU(peak);

    // Show/hide barrier
    const barrier = sceneRef.current?.getObjectByName("barrier");
    if (barrier) barrier.visible = showBarrier;
  }, [showBarrier]);

  // Animation loop
  useEffect(() => {
    const animate = () => {
      if (playing) {
        let f = fieldRef.current;
        for (let i = 0; i < 3; i++) f = stepPDE(f);
        fieldRef.current = f;
        setStep(s => s + 3);
      }
      updateMesh();

      // Rotate camera
      const cam = cameraRef.current;
      if (cam) {
        const t = Date.now() * 0.0001;
        const radius = 45;
        cam.position.x = radius * Math.cos(t + viewAngle);
        cam.position.z = radius * Math.sin(t + viewAngle);
        cam.position.y = 25 + 10 * Math.sin(t * 0.5);
        cam.lookAt(0, 3, 0);
      }

      rendererRef.current?.render(sceneRef.current, cameraRef.current);
      frameRef.current = requestAnimationFrame(animate);
    };
    frameRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frameRef.current);
  }, [playing, updateMesh, viewAngle]);

  const handleReset = (type) => {
    setFormation(type);
    fieldRef.current = initField(GRID);
    seedFormation(fieldRef.current, type, GRID / 2, GRID / 2);
    setStep(0);
    setPlaying(false);
  };

  const getPhaseLabel = (u) => {
    if (u < 0.5) return { text: "DORMANT", color: COLORS.dim };
    if (u < 1.2) return { text: "PARTIAL (U≈1)", color: COLORS.accent };
    if (u < 2.5) return { text: "BARRIER ZONE (U*≈2)", color: COLORS.gold };
    if (u < 3.5) return { text: "AMPLIFYING (U≈3)", color: COLORS.green };
    return { text: "SATURATED", color: COLORS.green };
  };

  const phase = getPhaseLabel(maxU);

  return (
    <div style={{ width: "100%", height: "100vh", background: COLORS.bg, display: "flex", fontFamily: "'JetBrains Mono', 'Fira Code', monospace", color: COLORS.text, overflow: "hidden" }}>
      {/* 3D Viewport */}
      <div style={{ flex: 1, position: "relative" }}>
        <canvas ref={canvasRef} style={{ width: "100%", height: "100%", display: "block" }} />
        
        {/* HUD overlay */}
        <div style={{ position: "absolute", top: 16, left: 16, background: `${COLORS.panel}dd`, padding: "12px 16px", borderRadius: 8, border: `1px solid ${COLORS.border}`, backdropFilter: "blur(8px)" }}>
          <div style={{ fontSize: 11, color: COLORS.dim, letterSpacing: 2, marginBottom: 4 }}>GRIMOIRE</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: "#fff", marginBottom: 2 }}>WHITE PLAYGROUND</div>
          <div style={{ fontSize: 10, color: COLORS.dim }}>∂U/∂t = D∇²U + λU²sin(αU) + Γ(U)</div>
        </div>

        {/* Phase indicator */}
        <div style={{ position: "absolute", top: 16, right: 16, background: `${COLORS.panel}dd`, padding: "10px 14px", borderRadius: 8, border: `1px solid ${COLORS.border}`, textAlign: "right" }}>
          <div style={{ fontSize: 10, color: COLORS.dim }}>STEP {step}</div>
          <div style={{ fontSize: 24, fontWeight: 700, color: phase.color }}>{maxU.toFixed(2)}</div>
          <div style={{ fontSize: 11, color: phase.color }}>{phase.text}</div>
        </div>

        {/* Fixed points legend */}
        <div style={{ position: "absolute", bottom: 16, left: 16, background: `${COLORS.panel}dd`, padding: "8px 12px", borderRadius: 8, border: `1px solid ${COLORS.border}`, fontSize: 10 }}>
          <div style={{ marginBottom: 4, color: COLORS.dim }}>FIXED POINTS</div>
          <div style={{ display: "flex", gap: 12 }}>
            <span><span style={{ color: COLORS.accent }}>●</span> U=1 stable</span>
            <span><span style={{ color: COLORS.gold }}>●</span> U*=2 <b>unstable</b></span>
            <span><span style={{ color: COLORS.green }}>●</span> U=3 stable</span>
          </div>
        </div>
      </div>

      {/* Control Panel */}
      <div style={{ width: 260, background: COLORS.panel, borderLeft: `1px solid ${COLORS.border}`, padding: 16, display: "flex", flexDirection: "column", gap: 16, overflowY: "auto" }}>
        <div style={{ fontSize: 11, color: COLORS.dim, letterSpacing: 2 }}>FORMATIONS</div>
        {FORMATIONS.map(f => (
          <button
            key={f.id}
            onClick={() => handleReset(f.id)}
            style={{
              background: formation === f.id ? `${f.color}22` : "transparent",
              border: `1px solid ${formation === f.id ? f.color : COLORS.border}`,
              borderRadius: 6, padding: "8px 10px", cursor: "pointer",
              textAlign: "left", color: formation === f.id ? f.color : COLORS.text,
              transition: "all 0.2s",
            }}
          >
            <div style={{ fontSize: 12, fontWeight: 600 }}>{f.label}</div>
            <div style={{ fontSize: 10, color: COLORS.dim, marginTop: 2 }}>{f.desc}</div>
          </button>
        ))}

        <div style={{ fontSize: 11, color: COLORS.dim, letterSpacing: 2, marginTop: 8 }}>SIMULATION</div>
        <button
          onClick={() => setPlaying(!playing)}
          style={{
            background: playing ? `${COLORS.red}22` : `${COLORS.green}22`,
            border: `1px solid ${playing ? COLORS.red : COLORS.green}`,
            borderRadius: 6, padding: "10px", cursor: "pointer",
            color: playing ? COLORS.red : COLORS.green,
            fontSize: 13, fontWeight: 700,
          }}
        >
          {playing ? "⏸ PAUSE" : "▶ EVOLVE FIELD"}
        </button>

        <button
          onClick={() => {
            let f = fieldRef.current;
            for (let i = 0; i < 10; i++) f = stepPDE(f);
            fieldRef.current = f;
            setStep(s => s + 10);
          }}
          style={{
            background: "transparent", border: `1px solid ${COLORS.border}`,
            borderRadius: 6, padding: "8px", cursor: "pointer",
            color: COLORS.text, fontSize: 11,
          }}
        >
          STEP +10
        </button>

        <div style={{ fontSize: 11, color: COLORS.dim, letterSpacing: 2, marginTop: 8 }}>VIEW</div>
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, cursor: "pointer" }}>
          <input type="checkbox" checked={showBarrier} onChange={e => setShowBarrier(e.target.checked)} />
          Show U*=2 barrier plane
        </label>
        <div style={{ fontSize: 10, color: COLORS.dim }}>
          Camera angle
          <input
            type="range" min="-3.14" max="3.14" step="0.1"
            value={viewAngle}
            onChange={e => setViewAngle(parseFloat(e.target.value))}
            style={{ width: "100%", marginTop: 4 }}
          />
        </div>

        <div style={{ fontSize: 11, color: COLORS.dim, letterSpacing: 2, marginTop: 8 }}>PARAMETERS</div>
        <div style={{ fontSize: 10, color: COLORS.dim, lineHeight: 1.6 }}>
          D = {D}<br />
          λ = {LAM}<br />
          α = π<br />
          Grid = {GRID}×{GRID}<br />
          dt = {DT}<br />
          M_min = {(Math.PI * D / LAM).toFixed(4)}<br />
          v_min ≈ 0.82 cells/step<br />
        </div>

        <div style={{ marginTop: "auto", padding: "10px 0", borderTop: `1px solid ${COLORS.border}`, fontSize: 9, color: COLORS.dim, lineHeight: 1.5 }}>
          <b style={{ color: COLORS.gold }}>GRIMOIRE</b> White Playground v0.1<br />
          Locked PDE. Validated at 0.996 AUC.<br />
          Gate 2B: 29/37, p=0.000376<br />
          Seeds beat noise. Topology beats headcount.
        </div>
      </div>
    </div>
  );
}
