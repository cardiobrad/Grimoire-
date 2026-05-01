"""
GRIMOIRE CHAOS ANALYSIS — Step 2: Bifurcation Diagram
======================================================
Sweeps the reaction rate λ from 0 to 1 with D=0.12, α=π fixed.
At each value, runs the simulation to steady state, then records
the long-term behavior of U at a probe point.

Looking for:
- Period-doubling cascades
- Windows of order within chaos
- Intermittency
- The specific behavior at λ=0.45 (locked value)

Also computes Lyapunov exponent at each λ value to produce
a Lyapunov spectrum alongside the bifurcation diagram.
"""

import numpy as np
import json
import time

# Fixed parameters
D = 0.12
ALPHA = np.pi
DX = 1.0
DT = 0.01
N = 16  # Grid size (keep small for speed)

# Sweep parameters
LAMBDA_VALUES = np.linspace(0.05, 1.0, 40)
WARMUP_STEPS = 2000
SAMPLE_STEPS = 500
PERTURBATION_SIZE = 1e-8

def laplacian_2d(U, dx):
    return (
        np.roll(U, 1, axis=0) + np.roll(U, -1, axis=0) +
        np.roll(U, 1, axis=1) + np.roll(U, -1, axis=1) - 4 * U
    ) / (dx**2)

def step_forward(U, lam, dt, dx):
    lap = laplacian_2d(U, dx)
    reaction = lam * U**2 * np.sin(ALPHA * U)
    U_new = U + dt * (D * lap + reaction)
    U_new = np.maximum(U_new, 0)
    return U_new

def compute_bifurcation_point(lam, seed=42):
    """Run simulation at given λ, return probe point time series + Lyapunov estimate"""
    np.random.seed(seed)
    
    # Initial condition
    U = 0.5 + 0.3 * np.random.randn(N, N)
    U = np.maximum(U, 0)
    
    # Warmup
    for _ in range(WARMUP_STEPS):
        U = step_forward(U, lam, DT, DX)
    
    # Sample the probe point (center of grid)
    probe_x, probe_y = N // 2, N // 2
    samples = []
    for _ in range(SAMPLE_STEPS):
        U = step_forward(U, lam, DT, DX)
        samples.append(float(U[probe_x, probe_y]))
    
    # Quick Lyapunov estimate
    U_ref = U.copy()
    delta = PERTURBATION_SIZE * np.random.randn(N, N)
    U_pert = U_ref + delta
    U_pert = np.maximum(U_pert, 0)
    
    lyap_sum = 0.0
    n_renorm = 50
    steps_per = 20
    
    for _ in range(n_renorm):
        for _ in range(steps_per):
            U_ref = step_forward(U_ref, lam, DT, DX)
            U_pert = step_forward(U_pert, lam, DT, DX)
        
        delta = U_pert - U_ref
        delta_norm = np.linalg.norm(delta)
        
        if delta_norm == 0 or np.isnan(delta_norm) or np.isinf(delta_norm):
            break
        
        lyap_sum += np.log(delta_norm / PERTURBATION_SIZE)
        delta = delta * (PERTURBATION_SIZE / delta_norm)
        U_pert = U_ref + delta
        U_pert = np.maximum(U_pert, 0)
    
    total_time = n_renorm * steps_per * DT
    lyap_est = lyap_sum / total_time if total_time > 0 else 0.0
    
    # Compute statistics
    samples = np.array(samples)
    
    return {
        'lambda': float(lam),
        'probe_mean': float(np.mean(samples)),
        'probe_std': float(np.std(samples)),
        'probe_min': float(np.min(samples)),
        'probe_max': float(np.max(samples)),
        'probe_range': float(np.max(samples) - np.min(samples)),
        'lyapunov_estimate': float(lyap_est),
        'last_10_samples': [float(s) for s in samples[-10:]],
        'unique_peaks': int(len(set(np.round(samples, 3))))
    }

if __name__ == "__main__":
    print("=" * 70)
    print("GRIMOIRE CHAOS ANALYSIS — Step 2: Bifurcation Diagram")
    print("=" * 70)
    print(f"Fixed: D={D}, α=π, Grid={N}x{N}")
    print(f"Sweeping λ from {LAMBDA_VALUES[0]:.2f} to {LAMBDA_VALUES[-1]:.2f}")
    print(f"({len(LAMBDA_VALUES)} points)")
    print()
    
    results = []
    t0 = time.time()
    
    for i, lam in enumerate(LAMBDA_VALUES):
        result = compute_bifurcation_point(lam)
        results.append(result)
        
        marker = ""
        if abs(lam - 0.45) < 0.02:
            marker = "  ← LOCKED VALUE"
        
        lyap = result['lyapunov_estimate']
        if lyap > 0.01:
            regime = "CHAOTIC"
        elif lyap > -0.01:
            regime = "EDGE"
        else:
            regime = "ORDERED"
        
        print(f"  λ={lam:.3f}  range={result['probe_range']:.4f}  "
              f"λ_max={lyap:.4f}  [{regime}]{marker}")
    
    elapsed = time.time() - t0
    print(f"\nCompleted in {elapsed:.1f}s")
    
    # Analyze the locked value
    print("\n" + "=" * 70)
    print("ANALYSIS AT LOCKED VALUE λ=0.45")
    print("=" * 70)
    
    locked_results = [r for r in results if abs(r['lambda'] - 0.45) < 0.02]
    if locked_results:
        r = locked_results[0]
        print(f"  Probe range: {r['probe_range']:.6f}")
        print(f"  Probe std:   {r['probe_std']:.6f}")
        print(f"  Lyapunov:    {r['lyapunov_estimate']:.6f}")
        
        if r['lyapunov_estimate'] > 0.01:
            print(f"  → CHAOTIC at locked parameters")
        elif r['lyapunov_estimate'] > -0.01:
            print(f"  → EDGE OF CHAOS at locked parameters")
        else:
            print(f"  → ORDERED at locked parameters")
    
    # Look for transitions
    print("\n" + "=" * 70)
    print("REGIME TRANSITIONS")
    print("=" * 70)
    
    prev_regime = None
    for r in results:
        lyap = r['lyapunov_estimate']
        if lyap > 0.01:
            regime = "CHAOTIC"
        elif lyap > -0.01:
            regime = "EDGE"
        else:
            regime = "ORDERED"
        
        if prev_regime and regime != prev_regime:
            print(f"  TRANSITION at λ={r['lambda']:.3f}: {prev_regime} → {regime}")
        prev_regime = regime
    
    # Save
    with open('/home/claude/chaos_pipeline/step2_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to step2_results.json")
