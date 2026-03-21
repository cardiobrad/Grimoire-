#!/usr/bin/env python3
"""
zone_sweep.py — GRIMOIRE Priority 2: Target Zone Size Sweep

THE PREDICTION:
  Small zones → compact formations win (footprint already covers zone)
  Large zones → distributed formations win (multiple nucleation sites)
  There exists a crossover radius r* where the advantage flips.

This is the heterogeneous nucleation hypothesis in its purest testable form.

DESIGN:
  - 3 formation pairs: compact vs spread, compact vs clusters, spread vs clusters
  - 3 agent counts: 12, 16, 20
  - 5 target radii: [3, 5, 7, 10, 13] cells
  - 30 runs per configuration
  - Primary outcome: mean T90 (lower = faster = better)
  - Total: 3 pairs × 3 sizes × 5 radii × 2 formations × 30 runs = 2,700 simulations

LOCKED PARAMETERS (from handover):
  PDE: ∂U/∂t = D∇²U + λU²sin(αU), D=0.12, λ=0.45, α=π
  Grid: 64×64
  Movement: frontier-pull
  Max steps: 150 (increased for large zones)
"""

import numpy as np
import json
import os
import sys
import time

# Import simulator core
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from simulator import (
    GRID, D, LAM, ALPHA, DT, PDE_SUBSTEPS, SENSE_R, NOISE,
    step_pde, make_compact, make_spread, make_clusters
)

# ═══════════════════════════════════════════════════════════════
# ZONE SWEEP PARAMETERS
# ═══════════════════════════════════════════════════════════════
TARGET_RADII = [3, 5, 7, 10, 13]
AGENT_COUNTS = [12, 16, 20]
MAX_STEPS = 150  # increased for large zones
COV_THRESHOLD = 0.9
RUNS = 30

FORMATION_TYPES = {
    "compact": make_compact,
    "spread": make_spread,
    "clusters": make_clusters,
}

# Pairs to compare (the high-contrast tests)
PAIRS = [
    ("compact", "spread"),
    ("compact", "clusters"),
    ("spread", "clusters"),
]


def make_target(cy, cx, radius):
    """Create circular target zone mask with variable radius."""
    mask = np.zeros((GRID, GRID), dtype=bool)
    for y in range(GRID):
        for x in range(GRID):
            if (x - cx)**2 + (y - cy)**2 <= radius**2:
                mask[y, x] = True
    return mask


def run_zone(positions, target_radius, seed=0):
    """
    Run one simulation with a specific target zone radius.
    Returns T90 and coverage history.
    """
    rng = np.random.RandomState(seed)
    agents = positions.astype(np.float64) + rng.uniform(-NOISE, NOISE, positions.shape)
    agents = np.clip(agents, 0, GRID - 1)
    n = len(agents)

    U = np.zeros((GRID, GRID), dtype=np.float64)
    for ay, ax in agents:
        iy, ix = int(np.clip(ay, 0, GRID-1)), int(np.clip(ax, 0, GRID-1))
        U[iy, ix] += 0.5

    target_mask = make_target(32, 32, target_radius)
    target_n = int(target_mask.sum())
    if target_n == 0:
        return MAX_STEPS, []

    visited = np.zeros((GRID, GRID), dtype=bool)
    cov_hist = []
    t90 = MAX_STEPS
    tgt_coords = np.argwhere(target_mask)

    for step in range(MAX_STEPS):
        # Mark visited (3x3 footprint)
        for ay, ax in agents:
            iy, ix = int(np.clip(ay, 1, GRID-2)), int(np.clip(ax, 1, GRID-2))
            visited[iy-1:iy+2, ix-1:ix+2] = True

        cov = float((visited & target_mask).sum()) / target_n
        cov_hist.append(cov)

        if cov >= COV_THRESHOLD and t90 == MAX_STEPS:
            t90 = step
        if cov >= 0.99:
            cov_hist.extend([1.0] * (MAX_STEPS - step - 1))
            break

        # PDE substeps
        for _ in range(PDE_SUBSTEPS):
            for ay, ax in agents:
                iy, ix = int(np.clip(ay, 0, GRID-1)), int(np.clip(ax, 0, GRID-1))
                U[iy, ix] = min(U[iy, ix] + 0.08, 5.0)
            U = step_pde(U)

        # Move: frontier-pull
        unvis = target_mask & ~visited
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

    return t90, cov_hist


def run_sweep():
    """Execute the full zone sweep experiment."""
    results = []
    total = len(AGENT_COUNTS) * len(TARGET_RADII) * len(FORMATION_TYPES) * RUNS
    done = 0
    start = time.time()

    print("=" * 70)
    print("  GRIMOIRE — Target Zone Size Sweep (Priority 2)")
    print("  Testing heterogeneous nucleation crossover prediction")
    print(f"  {total} total simulations")
    print("=" * 70)

    for n_agents in AGENT_COUNTS:
        for radius in TARGET_RADII:
            for ftype, fn in FORMATION_TYPES.items():
                t90s = []
                if ftype == "clusters":
                    pos = fn(n_agents, n_clusters=3)
                else:
                    pos = fn(n_agents)

                for seed in range(RUNS):
                    t90, _ = run_zone(pos, radius, seed=seed)
                    t90s.append(t90)
                    done += 1

                mean_t90 = np.mean(t90s)
                std_t90 = np.std(t90s)

                results.append({
                    "formation": ftype,
                    "n_agents": n_agents,
                    "target_radius": radius,
                    "target_area": round(np.pi * radius**2, 1),
                    "mean_t90": round(mean_t90, 2),
                    "std_t90": round(std_t90, 2),
                    "median_t90": round(float(np.median(t90s)), 2),
                    "censored_pct": round(100 * sum(1 for t in t90s if t >= MAX_STEPS) / RUNS, 1),
                })

                elapsed = time.time() - start
                rate = done / elapsed if elapsed > 0 else 0
                eta = (total - done) / rate if rate > 0 else 0
                print(f"  [{done:4d}/{total}] {ftype:<10} n={n_agents:2d} r={radius:2d} "
                      f"→ T90={mean_t90:6.1f}±{std_t90:4.1f}  "
                      f"({rate:.0f} runs/s, ETA {eta:.0f}s)")

    return results


def analyse_crossover(results):
    """Find the crossover radius for each pair and agent count."""
    print("\n" + "=" * 70)
    print("  CROSSOVER ANALYSIS")
    print("=" * 70)

    crossovers = []

    for n_agents in AGENT_COUNTS:
        print(f"\n  --- n = {n_agents} agents ---")
        print(f"  {'Radius':>6} {'Area':>6} {'Compact':>10} {'Spread':>10} {'Clusters':>10} {'Winner':>10}")
        print(f"  {'─'*58}")

        for radius in TARGET_RADII:
            row = {}
            for r in results:
                if r["n_agents"] == n_agents and r["target_radius"] == radius:
                    row[r["formation"]] = r["mean_t90"]

            c = row.get("compact", 999)
            s = row.get("spread", 999)
            k = row.get("clusters", 999)
            winner = min([(c, "compact"), (s, "spread"), (k, "clusters")])[1]

            print(f"  {radius:>6} {np.pi*radius**2:>6.0f} {c:>10.1f} {s:>10.1f} {k:>10.1f} {winner:>10}")

            crossovers.append({
                "n_agents": n_agents,
                "target_radius": radius,
                "target_area": round(np.pi * radius**2, 1),
                "compact_t90": c,
                "spread_t90": s,
                "clusters_t90": k,
                "winner": winner,
            })

    # Find crossover points
    print(f"\n  {'─'*58}")
    print(f"  CROSSOVER DETECTION:")

    for n_agents in AGENT_COUNTS:
        sub = [c for c in crossovers if c["n_agents"] == n_agents]
        # Check: does compact ever beat clusters?
        compact_wins = [c for c in sub if c["winner"] == "compact"]
        cluster_wins = [c for c in sub if c["winner"] == "clusters"]

        if compact_wins and cluster_wins:
            # Find the transition radius
            last_compact = max(c["target_radius"] for c in compact_wins)
            first_cluster = min(c["target_radius"] for c in cluster_wins)
            print(f"  n={n_agents}: crossover between r={last_compact} and r={first_cluster}")
        elif cluster_wins:
            print(f"  n={n_agents}: clusters dominate at ALL tested radii (no crossover)")
        elif compact_wins:
            print(f"  n={n_agents}: compact dominates at ALL tested radii (no crossover)")
        else:
            # Check spread vs clusters
            spread_wins = [c for c in sub if c["winner"] == "spread"]
            if spread_wins:
                print(f"  n={n_agents}: spread dominates — mixed result")

    return crossovers


def main():
    results = run_sweep()
    crossovers = analyse_crossover(results)

    # Save
    os.makedirs("outputs", exist_ok=True)
    output = {
        "experiment": "zone_sweep_priority2",
        "prediction": "Small zones → compact wins. Large zones → distributed wins. Crossover at r*.",
        "target_radii": TARGET_RADII,
        "agent_counts": AGENT_COUNTS,
        "runs_per_config": RUNS,
        "max_steps": MAX_STEPS,
        "formation_results": results,
        "crossover_analysis": crossovers,
    }

    with open("outputs/zone_sweep_results.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n  Results saved: outputs/zone_sweep_results.json")
    print(f"\n  Next: run plot_zone_sweep.py for publication figure")

    return output


if __name__ == "__main__":
    main()
