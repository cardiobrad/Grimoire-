"""
simulator.py — PDE + swarm simulator for front velocity measurement.
Reconstructed from GRIMOIRE Master Handover (Sonnet 4.6 → Opus 4.6).

Locked equation: ∂U/∂t = D∇²U + λU²sin(αU), D=0.12, λ=0.45, α=π
Grid: 64×64, FTCS explicit scheme, CFL-stable.
Movement: frontier-pull (nearest unvisited target cell).
"""

import numpy as np
from typing import Dict, Tuple, List

# ═══ LOCKED PARAMETERS ═══
GRID = 64
D = 0.12
LAM = 0.45
ALPHA = np.pi
DT = 0.05
PDE_SUBSTEPS = 3
TARGET_CY, TARGET_CX = 32, 32
TARGET_R = 7
SENSE_R = 10.0
MAX_STEPS = 100
COV_THRESHOLD = 0.9
NOISE = 0.3

def make_target():
    mask = np.zeros((GRID, GRID), dtype=bool)
    for y in range(GRID):
        for x in range(GRID):
            if (x - TARGET_CX)**2 + (y - TARGET_CY)**2 <= TARGET_R**2:
                mask[y, x] = True
    return mask

TARGET_MASK = make_target()
TARGET_N = int(TARGET_MASK.sum())

def step_pde(U):
    lap = np.zeros_like(U)
    lap[1:-1, 1:-1] = (U[:-2,1:-1] + U[2:,1:-1] + U[1:-1,:-2] + U[1:-1,2:] - 4*U[1:-1,1:-1])
    react = LAM * U * U * np.sin(ALPHA * U)
    return np.maximum(0.0, U + DT * (D * lap + react))

def run(positions, seed=0):
    """
    Run one simulation. Returns dict with coverage_history, t90, etc.
    positions: (n,2) array of (y, x) starting coordinates.
    """
    rng = np.random.RandomState(seed)
    agents = positions.astype(np.float64) + rng.uniform(-NOISE, NOISE, positions.shape)
    agents = np.clip(agents, 0, GRID - 1)
    n = len(agents)

    U = np.zeros((GRID, GRID), dtype=np.float64)
    # Seed field with agent positions
    for ay, ax in agents:
        U[int(ay), int(ax)] += 0.5

    visited = np.zeros((GRID, GRID), dtype=bool)
    cov_hist = []
    t90 = MAX_STEPS

    # Precompute target cell coordinates
    tgt_coords = np.argwhere(TARGET_MASK)

    for step in range(MAX_STEPS):
        # Mark visited (agent footprint = 3x3)
        for ay, ax in agents:
            iy, ix = int(np.clip(ay, 1, GRID-2)), int(np.clip(ax, 1, GRID-2))
            visited[iy-1:iy+2, ix-1:ix+2] = True

        cov = float((visited & TARGET_MASK).sum()) / TARGET_N
        cov_hist.append(cov)

        if cov >= COV_THRESHOLD and t90 == MAX_STEPS:
            t90 = step
        if cov >= 0.99:
            cov_hist.extend([1.0] * (MAX_STEPS - step - 1))
            break

        # PDE substeps with agent energy injection
        for _ in range(PDE_SUBSTEPS):
            for ay, ax in agents:
                iy, ix = int(np.clip(ay, 0, GRID-1)), int(np.clip(ax, 0, GRID-1))
                U[iy, ix] = min(U[iy, ix] + 0.08, 5.0)
            U = step_pde(U)

        # Move agents: frontier-pull
        unvis = TARGET_MASK & ~visited
        uv_coords = np.argwhere(unvis)

        for i in range(n):
            ay, ax = agents[i]
            if len(uv_coords) == 0:
                continue
            dists = np.sqrt((uv_coords[:,0] - ay)**2 + (uv_coords[:,1] - ax)**2)
            within = dists <= SENSE_R
            if within.any():
                idx = np.argmin(np.where(within, dists, 1e9))
            else:
                idx = np.argmin(dists)
            ty, tx = uv_coords[idx]

            dy, dx = ty - ay, tx - ax
            d = np.sqrt(dy**2 + dx**2)
            if d > 0.3:
                # Blend: 85% frontier-pull, 15% U-gradient
                iy2, ix2 = int(np.clip(ay,1,GRID-2)), int(np.clip(ax,1,GRID-2))
                gy = (U[iy2+1,ix2] - U[iy2-1,ix2]) / 2
                gx = (U[iy2,ix2+1] - U[iy2,ix2-1]) / 2
                my = 0.85*(dy/d) + 0.15*gy
                mx = 0.85*(dx/d) + 0.15*gx
                mm = np.sqrt(my**2 + mx**2)
                if mm > 0:
                    my /= mm; mx /= mm
                agents[i, 0] = np.clip(ay + my, 0, GRID-1)
                agents[i, 1] = np.clip(ax + mx, 0, GRID-1)

    return {"coverage_history": cov_hist, "t90": t90, "final_coverage": cov_hist[-1] if cov_hist else 0}


def make_compact(n, cy=15, cx=15, r=3.0):
    """Compact disk formation — homogeneous nucleation seed."""
    pos = []
    for i in range(n):
        a = 2*np.pi*i/n
        ri = r * np.sqrt((i+1)/n)
        pos.append([cy + ri*np.sin(a), cx + ri*np.cos(a)])
    return np.array(pos)

def make_spread(n, cy=15, cx=15, r=10.0):
    """Spread formation — heterogeneous nucleation sites."""
    pos = []
    for i in range(n):
        a = 2*np.pi*i/n
        ri = r * (0.3 + 0.7*(i/n))
        pos.append([cy + ri*np.sin(a), cx + ri*np.cos(a)])
    return np.array(pos)

def make_line(n, y0=15, x0=5, spacing=2.5):
    """Thin line — fragile formation."""
    return np.array([[y0, x0 + i*spacing] for i in range(n)])

def make_scattered(n, cy=32, cx=32, area=25):
    """Scattered random — dormant formation."""
    rng = np.random.RandomState(99)
    return np.column_stack([
        rng.uniform(cy - area, cy + area, n),
        rng.uniform(cx - area, cx + area, n)
    ])

def make_clusters(n, n_clusters=3, cy=15, cx=15, spread=12, cluster_r=2.0):
    """Multi-cluster — distributed nucleation sites."""
    pos = []
    per_cluster = n // n_clusters
    remainder = n % n_clusters
    for c in range(n_clusters):
        angle = 2*np.pi*c/n_clusters
        ccx = cx + spread*np.cos(angle)
        ccy = cy + spread*np.sin(angle)
        nc = per_cluster + (1 if c < remainder else 0)
        for j in range(nc):
            a = 2*np.pi*j/nc
            r = cluster_r * np.sqrt((j+1)/nc)
            pos.append([ccy + r*np.sin(a), ccx + r*np.cos(a)])
    return np.array(pos)
