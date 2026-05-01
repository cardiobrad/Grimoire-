"""
GRIMOIRE CHAOS ANALYSIS — Step 1b: Regime-Specific Lyapunov Tests
==================================================================
The initial test showed ORDERED at U≈0.5 initial conditions.
But the system decays to the stable fixed point at U=1.

The INTERESTING dynamics happen:
- Near U*=2 (the unstable nucleation barrier)
- During transient nucleation events
- With structured seeds at different amplitudes

This test probes THOSE regimes specifically.
"""

import numpy as np
import json
import time

D = 0.12
LAMBDA = 0.45
ALPHA = np.pi
DX = 1.0
DT = 0.01
N = 32

PERTURBATION_SIZE = 1e-8

def laplacian_2d(U, dx):
    return (
        np.roll(U, 1, axis=0) + np.roll(U, -1, axis=0) +
        np.roll(U, 1, axis=1) + np.roll(U, -1, axis=1) - 4 * U
    ) / (dx**2)

def step_grimoire(U, dt, dx):
    lap = laplacian_2d(U, dx)
    reaction = LAMBDA * U**2 * np.sin(ALPHA * U)
    U_new = U + dt * (D * lap + reaction)
    return np.maximum(U_new, 0)

def step_linear(U, dt, dx):
    lap = laplacian_2d(U, dx)
    reaction = LAMBDA * U**2 * np.maximum(0, 1.0 - U)
    U_new = U + dt * (D * lap + reaction)
    return np.maximum(U_new, 0)

def compute_lyapunov(U_init, step_fn, label, n_warmup=200, n_cycles=150, steps_per=30):
    """Compute max Lyapunov from a specific initial condition"""
    U = U_init.copy()
    
    # Brief warmup (shorter — we want to stay near the interesting regime)
    for _ in range(n_warmup):
        U = step_fn(U, DT, DX)
    
    # Check where we ended up
    u_mean = np.mean(U)
    u_max = np.max(U)
    u_std = np.std(U)
    
    # Perturb
    np.random.seed(99)
    delta = PERTURBATION_SIZE * np.random.randn(N, N)
    U_ref = U.copy()
    U_pert = U + delta
    U_pert = np.maximum(U_pert, 0)
    
    lyap_sum = 0.0
    
    for cycle in range(n_cycles):
        for _ in range(steps_per):
            U_ref = step_fn(U_ref, DT, DX)
            U_pert = step_fn(U_pert, DT, DX)
        
        delta = U_pert - U_ref
        delta_norm = np.linalg.norm(delta)
        
        if delta_norm == 0 or np.isnan(delta_norm) or np.isinf(delta_norm):
            break
        
        lyap_sum += np.log(delta_norm / PERTURBATION_SIZE)
        delta = delta * (PERTURBATION_SIZE / delta_norm)
        U_pert = U_ref + delta
        U_pert = np.maximum(U_pert, 0)
    
    total_time = n_cycles * steps_per * DT
    lyap = lyap_sum / total_time if total_time > 0 else 0.0
    
    if lyap > 0.01:
        regime = "CHAOTIC"
    elif lyap > -0.01:
        regime = "EDGE"
    else:
        regime = "ORDERED"
    
    return lyap, regime, u_mean, u_max, u_std

if __name__ == "__main__":
    print("=" * 70)
    print("GRIMOIRE CHAOS — Step 1b: Regime-Specific Tests")
    print("=" * 70)
    print(f"Fixed points: U=0 (marginal), U=1 (stable, f'=-1.41),")
    print(f"              U=2 (UNSTABLE, f'=+5.65), U=3 (deep stable)")
    print(f"Grid: {N}x{N}")
    print()
    
    tests = []
    
    # ============================================================
    # TEST 1: Near U*=2 (the nucleation barrier)
    # ============================================================
    print("=" * 60)
    print("TEST 1: Initial conditions near U*=2 (nucleation barrier)")
    print("=" * 60)
    
    for u_init in [1.8, 1.9, 2.0, 2.1, 2.2, 2.5]:
        np.random.seed(42)
        U0 = u_init + 0.1 * np.random.randn(N, N)
        U0 = np.maximum(U0, 0)
        
        lyap_sin, regime_sin, mean_sin, max_sin, std_sin = compute_lyapunov(
            U0, step_grimoire, f"GRIMOIRE U≈{u_init}"
        )
        lyap_lin, regime_lin, mean_lin, max_lin, std_lin = compute_lyapunov(
            U0, step_linear, f"Linear U≈{u_init}"
        )
        
        print(f"\n  U_init ≈ {u_init}:")
        print(f"    GRIMOIRE: λ_max={lyap_sin:+.4f} [{regime_sin}] "
              f"(settled: mean={mean_sin:.2f}, max={max_sin:.2f})")
        print(f"    Linear:   λ_max={lyap_lin:+.4f} [{regime_lin}] "
              f"(settled: mean={mean_lin:.2f}, max={max_lin:.2f})")
        
        if regime_sin != regime_lin:
            print(f"    ★ REGIME DIFFERENCE DETECTED!")
        
        tests.append({
            'test': 'near_barrier',
            'u_init': u_init,
            'grimoire': {'lyapunov': lyap_sin, 'regime': regime_sin, 
                        'settled_mean': mean_sin, 'settled_max': max_sin},
            'linear': {'lyapunov': lyap_lin, 'regime': regime_lin,
                      'settled_mean': mean_lin, 'settled_max': max_lin}
        })
    
    # ============================================================
    # TEST 2: Mixed regime (some cells below barrier, some above)
    # ============================================================
    print(f"\n{'='*60}")
    print("TEST 2: Mixed regime (structured seed near barrier)")
    print("=" * 60)
    
    np.random.seed(42)
    
    # Create a seed: high-U nucleus surrounded by low-U field
    U0 = np.ones((N, N)) * 0.5  # Background at 0.5
    cx, cy = N//2, N//2
    for i in range(-4, 5):
        for j in range(-4, 5):
            dist = np.sqrt(i**2 + j**2)
            if dist < 4:
                x = (cx + i) % N
                y = (cy + j) % N
                U0[x, y] = 2.5 * (1.0 - dist/4)  # Peak at 2.5, decays to 0
    
    lyap_sin, regime_sin, mean_sin, max_sin, std_sin = compute_lyapunov(
        U0, step_grimoire, "GRIMOIRE seed", n_warmup=100
    )
    lyap_lin, regime_lin, mean_lin, max_lin, std_lin = compute_lyapunov(
        U0, step_linear, "Linear seed", n_warmup=100
    )
    
    print(f"\n  Structured seed (peak=2.5, background=0.5):")
    print(f"    GRIMOIRE: λ_max={lyap_sin:+.4f} [{regime_sin}] "
          f"(settled: mean={mean_sin:.2f}, std={std_sin:.2f})")
    print(f"    Linear:   λ_max={lyap_lin:+.4f} [{regime_lin}] "
          f"(settled: mean={mean_lin:.2f}, std={std_lin:.2f})")
    
    if regime_sin != regime_lin:
        print(f"    ★ REGIME DIFFERENCE DETECTED!")
    
    tests.append({
        'test': 'structured_seed',
        'grimoire': {'lyapunov': lyap_sin, 'regime': regime_sin,
                    'settled_mean': mean_sin, 'settled_std': std_sin},
        'linear': {'lyapunov': lyap_lin, 'regime': regime_lin,
                  'settled_mean': mean_lin, 'settled_std': std_lin}
    })
    
    # ============================================================
    # TEST 3: Super-critical (above barrier everywhere)  
    # ============================================================
    print(f"\n{'='*60}")
    print("TEST 3: Super-critical (U > 2 everywhere)")
    print("=" * 60)
    
    for u_init in [2.5, 3.0, 3.5, 4.0]:
        np.random.seed(42)
        U0 = u_init + 0.2 * np.random.randn(N, N)
        U0 = np.maximum(U0, 0)
        
        lyap_sin, regime_sin, mean_sin, max_sin, std_sin = compute_lyapunov(
            U0, step_grimoire, f"GRIMOIRE U≈{u_init}"
        )
        lyap_lin, regime_lin, mean_lin, max_lin, std_lin = compute_lyapunov(
            U0, step_linear, f"Linear U≈{u_init}"
        )
        
        print(f"\n  U_init ≈ {u_init}:")
        print(f"    GRIMOIRE: λ_max={lyap_sin:+.4f} [{regime_sin}] "
              f"(settled: mean={mean_sin:.2f}, max={max_sin:.2f})")
        print(f"    Linear:   λ_max={lyap_lin:+.4f} [{regime_lin}] "
              f"(settled: mean={mean_lin:.2f}, max={max_lin:.2f})")
        
        if regime_sin != regime_lin:
            print(f"    ★ REGIME DIFFERENCE DETECTED!")
        
        tests.append({
            'test': 'super_critical',
            'u_init': u_init,
            'grimoire': {'lyapunov': lyap_sin, 'regime': regime_sin,
                        'settled_mean': mean_sin, 'settled_max': max_sin},
            'linear': {'lyapunov': lyap_lin, 'regime': regime_lin,
                      'settled_mean': mean_lin, 'settled_max': max_lin}
        })
    
    # ============================================================
    # TEST 4: Transient Lyapunov (measure DURING nucleation, not after)
    # ============================================================
    print(f"\n{'='*60}")
    print("TEST 4: Transient Lyapunov (during nucleation event)")
    print("=" * 60)
    
    np.random.seed(42)
    U0 = np.ones((N, N)) * 0.5
    cx, cy = N//2, N//2
    for i in range(-3, 4):
        for j in range(-3, 4):
            dist = np.sqrt(i**2 + j**2)
            if dist < 3:
                x = (cx + i) % N
                y = (cy + j) % N
                U0[x, y] = 2.2 * (1.0 - dist/3)
    
    # NO warmup — measure from the start of the nucleation event
    lyap_sin, regime_sin, mean_sin, max_sin, std_sin = compute_lyapunov(
        U0, step_grimoire, "GRIMOIRE transient", n_warmup=0, n_cycles=100, steps_per=20
    )
    lyap_lin, regime_lin, mean_lin, max_lin, std_lin = compute_lyapunov(
        U0, step_linear, "Linear transient", n_warmup=0, n_cycles=100, steps_per=20
    )
    
    print(f"\n  Nucleation seed (no warmup):")
    print(f"    GRIMOIRE: λ_max={lyap_sin:+.4f} [{regime_sin}]")
    print(f"    Linear:   λ_max={lyap_lin:+.4f} [{regime_lin}]")
    
    if regime_sin != regime_lin:
        print(f"    ★ REGIME DIFFERENCE DETECTED!")
    
    tests.append({
        'test': 'transient',
        'grimoire': {'lyapunov': lyap_sin, 'regime': regime_sin},
        'linear': {'lyapunov': lyap_lin, 'regime': regime_lin}
    })
    
    # ============================================================
    # TEST 5: Time-windowed Lyapunov (how does it change over time?)
    # ============================================================
    print(f"\n{'='*60}")
    print("TEST 5: Time-windowed Lyapunov evolution")
    print("=" * 60)
    print("  (Tracking Lyapunov as the system evolves through regimes)")
    
    np.random.seed(42)
    U0 = np.ones((N, N)) * 0.5
    cx, cy = N//2, N//2
    for i in range(-3, 4):
        for j in range(-3, 4):
            dist = np.sqrt(i**2 + j**2)
            if dist < 3:
                x = (cx + i) % N
                y = (cy + j) % N
                U0[x, y] = 2.5 * (1.0 - dist/3)
    
    U_ref = U0.copy()
    np.random.seed(99)
    delta = PERTURBATION_SIZE * np.random.randn(N, N)
    U_pert = U_ref + delta
    U_pert = np.maximum(U_pert, 0)
    
    window_lyaps = []
    window_size = 20  # steps per window
    n_windows = 50
    
    for w in range(n_windows):
        for _ in range(window_size):
            U_ref = step_grimoire(U_ref, DT, DX)
            U_pert = step_grimoire(U_pert, DT, DX)
        
        delta = U_pert - U_ref
        delta_norm = np.linalg.norm(delta)
        
        if delta_norm > 0 and not np.isnan(delta_norm):
            log_ratio = np.log(delta_norm / PERTURBATION_SIZE)
            window_lyap = log_ratio / (window_size * DT)
            window_lyaps.append({
                'window': w,
                'time': w * window_size * DT,
                'lyapunov': float(window_lyap),
                'u_mean': float(np.mean(U_ref)),
                'u_max': float(np.max(U_ref)),
                'u_std': float(np.std(U_ref))
            })
            
            delta = delta * (PERTURBATION_SIZE / delta_norm)
            U_pert = U_ref + delta
            U_pert = np.maximum(U_pert, 0)
    
    print(f"\n  Time-windowed Lyapunov evolution:")
    for wl in window_lyaps[::5]:  # Print every 5th
        regime = "CHAOTIC" if wl['lyapunov'] > 0.01 else ("EDGE" if wl['lyapunov'] > -0.01 else "ORDERED")
        print(f"    t={wl['time']:.1f}: λ={wl['lyapunov']:+.4f} [{regime}] "
              f"U_mean={wl['u_mean']:.2f} U_max={wl['u_max']:.2f}")
    
    # Check if there were ANY chaotic windows
    chaotic_windows = [w for w in window_lyaps if w['lyapunov'] > 0.01]
    edge_windows = [w for w in window_lyaps if -0.01 <= w['lyapunov'] <= 0.01]
    
    print(f"\n  Summary:")
    print(f"    Chaotic windows: {len(chaotic_windows)}/{len(window_lyaps)}")
    print(f"    Edge windows:    {len(edge_windows)}/{len(window_lyaps)}")
    print(f"    Ordered windows: {len(window_lyaps) - len(chaotic_windows) - len(edge_windows)}/{len(window_lyaps)}")
    
    if chaotic_windows:
        print(f"    ★ TRANSIENT CHAOS DETECTED in {len(chaotic_windows)} windows!")
        print(f"    Peak Lyapunov: {max(w['lyapunov'] for w in chaotic_windows):.4f}")
    
    tests.append({
        'test': 'time_windowed',
        'windows': window_lyaps,
        'n_chaotic': len(chaotic_windows),
        'n_edge': len(edge_windows)
    })
    
    # ============================================================
    # FINAL SUMMARY
    # ============================================================
    print(f"\n{'='*70}")
    print("FINAL SUMMARY — REGIME-SPECIFIC CHAOS ANALYSIS")
    print("=" * 70)
    
    any_chaos = False
    any_regime_diff = False
    
    for t in tests:
        if t['test'] == 'time_windowed':
            if t['n_chaotic'] > 0:
                any_chaos = True
                print(f"  ★ TRANSIENT CHAOS found in time-windowed analysis")
        elif 'grimoire' in t and 'linear' in t:
            if t['grimoire']['regime'] == 'CHAOTIC':
                any_chaos = True
            if t['grimoire']['regime'] != t['linear']['regime']:
                any_regime_diff = True
    
    if any_chaos:
        print(f"\n  CHAOS EXISTS in at least some regimes/conditions.")
    else:
        print(f"\n  NO CHAOS detected in any tested regime.")
    
    if any_regime_diff:
        print(f"  REGIME DIFFERENCES exist between GRIMOIRE and linear ceiling.")
    else:
        print(f"  No regime differences between GRIMOIRE and linear ceiling.")
    
    # Save
    with open('/home/claude/chaos_pipeline/step1b_results.json', 'w') as f:
        json.dump(tests, f, indent=2, default=str)
    
    print(f"\nResults saved to step1b_results.json")
