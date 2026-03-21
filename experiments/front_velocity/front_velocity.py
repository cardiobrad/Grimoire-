#!/usr/bin/env python3
"""
front_velocity.py — GRIMOIRE Priority 1 Analysis

Measure the front velocity of coverage propagation in swarm simulations.
Compare empirical velocity to PDE prediction v_min ≈ 0.82 cells/step.

Method:
  1. Run formations through the locked PDE simulator
  2. Track coverage_history at each timestep
  3. Convert coverage fraction → equivalent circular radius:
     r(t) = target_radius × √(coverage(t))
  4. Fit linear front from step 5 onward: r(t) = v·t + offset
  5. Compare empirical v to theoretical v_min ≈ 2√(D·|f'(U_stable)|)

Interpretation:
  v ≈ 0.82 → PDE describes the physics correctly
  v >> 0.82 → frontier-pull kinematics dominate
  v << 0.82 → something unexpected
"""

import numpy as np
import json
import os
import sys
from simulator import (
    run, make_compact, make_spread, make_line, make_clusters,
    make_scattered, TARGET_R, MAX_STEPS, D, LAM, ALPHA
)

# PDE-predicted front velocity
# v_min = 2√(D · |f'(U_stable)|) where U_stable = 3, f'(3) = -9λπ ≈ -12.72
V_PDE = 2 * np.sqrt(D * 9 * LAM * np.pi)
print(f"PDE predicted front velocity: v_min = {V_PDE:.4f} cells/step")

RUNS = 30
FIT_START = 5  # start fitting after transient

# ═══════════════════════════════════════════════════════════════
# TEST FORMATIONS
# ═══════════════════════════════════════════════════════════════
formations = {
    "compact_12":    make_compact(12),
    "compact_16":    make_compact(16),
    "compact_20":    make_compact(20),
    "spread_12":     make_spread(12),
    "spread_16":     make_spread(16),
    "spread_20":     make_spread(20),
    "clusters_12":   make_clusters(12, n_clusters=3),
    "clusters_16":   make_clusters(16, n_clusters=3),
    "clusters_20":   make_clusters(20, n_clusters=4),
    "line_12":       make_line(12),
    "line_16":       make_line(16),
}


def coverage_to_radius(coverage_history):
    """Convert coverage fraction → equivalent circular radius."""
    return np.array([TARGET_R * np.sqrt(max(0, c)) for c in coverage_history])


def fit_front_velocity(radius_history, fit_start=FIT_START):
    """
    Fit linear front: r(t) = v·t + offset from fit_start onward.
    Returns (velocity, offset, r_squared).
    Only fits the growing phase (before saturation).
    """
    r = np.array(radius_history)
    # Find where growth is still happening (r < 0.95 * max)
    max_r = TARGET_R
    growing = r < 0.95 * max_r
    
    # Use fit_start to end of growth phase
    valid = np.arange(len(r))
    mask = (valid >= fit_start) & growing
    
    if mask.sum() < 3:
        return 0.0, 0.0, 0.0
    
    t = valid[mask].astype(float)
    y = r[mask]
    
    # Linear least squares: r = v*t + b
    A = np.vstack([t, np.ones(len(t))]).T
    result = np.linalg.lstsq(A, y, rcond=None)
    v, b = result[0]
    
    # R-squared
    y_pred = v * t + b
    ss_res = np.sum((y - y_pred)**2)
    ss_tot = np.sum((y - y.mean())**2)
    r_sq = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    
    return float(v), float(b), float(r_sq)


def run_formation_batch(name, positions, n_runs=RUNS):
    """Run n_runs simulations, collect coverage histories and fit velocities."""
    print(f"  Running {name} ({len(positions)} agents, {n_runs} runs)...", end="", flush=True)
    
    velocities = []
    t90s = []
    all_radius_histories = []
    
    for seed in range(n_runs):
        result = run(positions, seed=seed)
        ch = result["coverage_history"]
        t90s.append(result["t90"])
        
        rh = coverage_to_radius(ch)
        all_radius_histories.append(rh)
        
        v, offset, r_sq = fit_front_velocity(rh)
        if r_sq > 0.5:  # only count good fits
            velocities.append(v)
    
    # Compute mean radius history (for plotting)
    max_len = max(len(rh) for rh in all_radius_histories)
    padded = np.full((n_runs, max_len), TARGET_R)
    for i, rh in enumerate(all_radius_histories):
        padded[i, :len(rh)] = rh
    mean_radius = padded.mean(axis=0)
    std_radius = padded.std(axis=0)
    
    v_mean = np.mean(velocities) if velocities else 0
    v_std = np.std(velocities) if velocities else 0
    t90_mean = np.mean(t90s)
    
    print(f" v={v_mean:.3f}±{v_std:.3f}, T90={t90_mean:.1f}, fits={len(velocities)}/{n_runs}")
    
    return {
        "name": name,
        "n_agents": len(positions),
        "n_runs": n_runs,
        "velocity_mean": round(v_mean, 4),
        "velocity_std": round(v_std, 4),
        "velocity_samples": len(velocities),
        "t90_mean": round(t90_mean, 2),
        "mean_radius_history": mean_radius.tolist(),
        "std_radius_history": std_radius.tolist(),
    }


# ═══════════════════════════════════════════════════════════════
# MAIN ANALYSIS
# ═══════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("  GRIMOIRE — Front Velocity Measurement (Priority 1)")
    print(f"  PDE prediction: v_min = {V_PDE:.4f} cells/step")
    print(f"  Equation: ∂U/∂t = D∇²U + λU²sin(αU)")
    print(f"  D={D}, λ={LAM}, α=π")
    print("=" * 70)
    
    results = []
    for name, pos in formations.items():
        r = run_formation_batch(name, pos)
        results.append(r)
    
    # Summary table
    print("\n" + "=" * 70)
    print("  FRONT VELOCITY SUMMARY")
    print("=" * 70)
    print(f"  {'Formation':<20} {'n':>3} {'v (cells/step)':>16} {'T90':>6} {'v/v_pde':>8}")
    print(f"  {'─'*60}")
    
    all_v = []
    for r in results:
        ratio = r["velocity_mean"] / V_PDE if V_PDE > 0 else 0
        print(f"  {r['name']:<20} {r['n_agents']:>3} {r['velocity_mean']:>7.3f} ± {r['velocity_std']:<6.3f} {r['t90_mean']:>6.1f} {ratio:>8.2f}")
        if r["velocity_mean"] > 0:
            all_v.append(r["velocity_mean"])
    
    grand_mean_v = np.mean(all_v) if all_v else 0
    grand_std_v = np.std(all_v) if all_v else 0
    
    print(f"  {'─'*60}")
    print(f"  Grand mean velocity: {grand_mean_v:.4f} ± {grand_std_v:.4f} cells/step")
    print(f"  PDE prediction:      {V_PDE:.4f} cells/step")
    print(f"  Ratio (empirical/PDE): {grand_mean_v/V_PDE:.2f}")
    
    # Interpretation
    print(f"\n  {'─'*60}")
    ratio = grand_mean_v / V_PDE
    if 0.5 <= ratio <= 1.5:
        print("  ✅ INTERPRETATION: Empirical velocity is within 50% of PDE prediction.")
        print("     The nucleation interpretation is SUPPORTED.")
        print("     The continuous field approximation describes the dynamics.")
    elif ratio > 1.5:
        print("  ⚠️  INTERPRETATION: Empirical velocity EXCEEDS PDE prediction.")
        print("     Frontier-pull kinematics are amplifying the spread rate.")
        print("     Result is still valid but physical interpretation needs qualifying:")
        print("     'Under a realistic target-attraction movement policy, coverage")
        print("      follows nucleation scaling with amplified front velocity.'")
    else:
        print("  ⚠️  INTERPRETATION: Empirical velocity is BELOW PDE prediction.")
        print("     Something unexpected — investigate movement model or grid effects.")
    print("=" * 70)
    
    # Save results
    output = {
        "analysis": "front_velocity_measurement",
        "pde_prediction": round(V_PDE, 4),
        "grand_mean_velocity": round(grand_mean_v, 4),
        "grand_std_velocity": round(grand_std_v, 4),
        "ratio_empirical_over_pde": round(grand_mean_v / V_PDE if V_PDE > 0 else 0, 4),
        "formations": results,
    }
    
    os.makedirs("outputs", exist_ok=True)
    with open("outputs/front_velocity_results.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"\n  Results saved: outputs/front_velocity_results.json")
    
    return output


if __name__ == "__main__":
    results = main()
