"""
GRIMOIRE Step 4 — Front Pinning: REPLICATION SUITE
=====================================================
Single reproducible script generating every quoted threshold.

Solvers:   Euler (FTCS), Heun (RK2)
BCs:       Periodic, Neumann (zero-flux)
Sweeps:    D sweep at dx=1.0, dx sweep at D=0.12, 
           seed-width at locked params, seed-width at fine grid,
           coupling-ratio consistency check

Every number in the results table comes from THIS script.
"""

import numpy as np
import csv
import time

# ============================================================
# LOCKED GRIMOIRE PARAMETERS
# ============================================================
LAMBDA = 0.45
ALPHA = np.pi
MAX_STEPS = 10000
SEED_AMPLITUDE = 2.5

def reaction(U):
    return LAMBDA * U**2 * np.sin(ALPHA * U)

def laplacian_periodic(U, dx):
    return (np.roll(U, 1) + np.roll(U, -1) - 2 * U) / (dx**2)

def laplacian_neumann(U, dx):
    """Zero-flux (Neumann) boundary conditions"""
    lap = np.zeros_like(U)
    lap[1:-1] = (U[:-2] + U[2:] - 2 * U[1:-1]) / (dx**2)
    lap[0] = (U[1] - U[0]) / (dx**2)
    lap[-1] = (U[-2] - U[-1]) / (dx**2)
    return lap

def step_euler(U, D, dx, dt, bc='periodic'):
    lap_fn = laplacian_periodic if bc == 'periodic' else laplacian_neumann
    lap = lap_fn(U, dx)
    U_new = U + dt * (D * lap + reaction(U))
    return np.maximum(U_new, 0)

def step_heun(U, D, dx, dt, bc='periodic'):
    """Heun's method (explicit RK2) for comparison"""
    lap_fn = laplacian_periodic if bc == 'periodic' else laplacian_neumann
    
    # Predictor (Euler step)
    lap1 = lap_fn(U, dx)
    k1 = D * lap1 + reaction(U)
    U_pred = np.maximum(U + dt * k1, 0)
    
    # Corrector
    lap2 = lap_fn(U_pred, dx)
    k2 = D * lap2 + reaction(U_pred)
    U_new = U + 0.5 * dt * (k1 + k2)
    return np.maximum(U_new, 0)

def run_test(D, dx, N, seed_width, solver='euler', bc='periodic'):
    """
    Run a single propagation test.
    Returns: (seed_survived, propagation_distance, final_center_U)
    """
    dt_cfl = 0.4 * dx**2 / (2 * max(D, 1e-6))
    dt = min(dt_cfl, 0.05)
    
    step_fn = step_euler if solver == 'euler' else step_heun
    
    U = np.ones(N)
    center = N // 2
    hw = seed_width // 2
    lo = max(center - hw, 0)
    hi = min(center + hw + 1, N)
    U[lo:hi] = SEED_AMPLITUDE
    
    init_right = hi - 1
    max_right = init_right
    seed_survived = False
    
    for step in range(MAX_STEPS):
        U = step_fn(U, D, dx, dt, bc)
        
        if not seed_survived and U[center] > 2.9:
            seed_survived = True
        
        above = np.where(U > 2.0)[0]
        if len(above) > 0:
            r = np.max(above)
            if r > max_right:
                max_right = r
    
    prop_dist = max(0, max_right - init_right)
    propagated = prop_dist > 2
    
    return {
        'D': D, 'dx': dx, 'N': N, 'seed_width': seed_width,
        'solver': solver, 'bc': bc, 'dt': dt,
        'coupling_ratio': D / dx**2,
        'seed_survived': seed_survived,
        'propagation_distance': prop_dist,
        'propagated': propagated,
        'final_center_U': float(U[center]),
        'physical_seed_width': seed_width * dx
    }


# ============================================================
# MAIN TEST SUITE
# ============================================================
if __name__ == "__main__":
    t0 = time.time()
    all_results = []
    
    solvers = ['euler', 'heun']
    bcs = ['periodic', 'neumann']
    N_DEFAULT = 128
    
    # --------------------------------------------------------
    # SWEEP 1: D at fixed dx=1.0, seed_width=3
    # --------------------------------------------------------
    print("=" * 70)
    print("SWEEP 1: D sweep (dx=1.0, seed_width=3)")
    print("=" * 70)
    
    D_vals = [0.02, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.30,
              0.50, 0.80, 1.0, 1.5, 2.0, 3.0]
    
    for solver in solvers:
        for bc in bcs:
            for D in D_vals:
                r = run_test(D, 1.0, N_DEFAULT, 3, solver, bc)
                r['sweep'] = 'D_at_dx1'
                all_results.append(r)
                
                if solver == 'euler' and bc == 'periodic':
                    marker = " ← LOCKED" if abs(D - 0.12) < 0.001 else ""
                    status = "PROP" if r['propagated'] else "PIN"
                    print(f"  D={D:.2f}  ratio={r['coupling_ratio']:.3f}  "
                          f"[{status}]  (euler/periodic){marker}")
    
    # --------------------------------------------------------
    # SWEEP 2: dx at fixed D=0.12, seed_width=3
    # --------------------------------------------------------
    print(f"\n{'='*70}")
    print("SWEEP 2: dx sweep (D=0.12, seed_width=3)")
    print("=" * 70)
    
    dx_vals = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50,
               0.75, 1.0, 1.5, 2.0]
    
    for solver in solvers:
        for bc in bcs:
            for dx in dx_vals:
                # Scale N so physical domain stays ~64 units
                N = max(32, int(64 / dx))
                sw = max(3, int(3.0 / dx))  # Keep physical seed ~3 units
                if sw % 2 == 0: sw += 1  # Keep odd
                
                r = run_test(0.12, dx, N, sw, solver, bc)
                r['sweep'] = 'dx_at_D012'
                all_results.append(r)
                
                if solver == 'euler' and bc == 'periodic':
                    marker = " ← LOCKED" if abs(dx - 1.0) < 0.01 else ""
                    status = "PROP" if r['propagated'] else "PIN"
                    print(f"  dx={dx:.2f}  ratio={r['coupling_ratio']:.3f}  "
                          f"seed={sw}nodes({sw*dx:.1f}u)  [{status}]{marker}")
    
    # --------------------------------------------------------
    # SWEEP 3: Seed width at locked params (D=0.12, dx=1.0)
    # --------------------------------------------------------
    print(f"\n{'='*70}")
    print("SWEEP 3: Seed width at locked params (D=0.12, dx=1.0)")
    print("=" * 70)
    
    for solver in solvers:
        for bc in bcs:
            for sw in [3, 5, 7, 9, 11, 15, 21, 31]:
                r = run_test(0.12, 1.0, N_DEFAULT, sw, solver, bc)
                r['sweep'] = 'width_locked'
                all_results.append(r)
                
                if solver == 'euler' and bc == 'periodic':
                    status = "PROP" if r['propagated'] else "PIN"
                    print(f"  width={sw:2d} nodes ({sw:.0f}u)  [{status}]")
    
    # --------------------------------------------------------
    # SWEEP 4: Seed width at fine grid (D=0.12, dx=0.10)
    # --------------------------------------------------------
    print(f"\n{'='*70}")
    print("SWEEP 4: Seed width at fine grid (D=0.12, dx=0.10)")
    print("=" * 70)
    
    for solver in solvers:
        for bc in bcs:
            for sw in [3, 5, 7, 9, 11, 15, 21, 31]:
                r = run_test(0.12, 0.10, 640, sw, solver, bc)
                r['sweep'] = 'width_fine'
                all_results.append(r)
                
                if solver == 'euler' and bc == 'periodic':
                    phys = sw * 0.10
                    status = "PROP" if r['propagated'] else "PIN"
                    print(f"  width={sw:2d} nodes ({phys:.1f}u)  [{status}]")
    
    # --------------------------------------------------------
    # SWEEP 5: Coupling ratio consistency
    # --------------------------------------------------------
    print(f"\n{'='*70}")
    print("SWEEP 5: Coupling ratio consistency (same ratio, different D/dx)")
    print("=" * 70)
    
    target_ratios = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    
    for ratio in target_ratios:
        combo_results = []
        for dx in [0.5, 1.0, 2.0]:
            D = ratio * dx**2
            if 0.01 <= D <= 5.0:
                N = max(32, int(64 / dx))
                sw = max(3, int(3.0 / dx))
                if sw % 2 == 0: sw += 1
                
                for solver in solvers:
                    r = run_test(D, dx, N, sw, solver, 'periodic')
                    r['sweep'] = 'ratio_consistency'
                    r['target_ratio'] = ratio
                    all_results.append(r)
                    
                    if solver == 'euler':
                        combo_results.append((dx, D, r['propagated']))
        
        if combo_results:
            states = set(c[2] for c in combo_results)
            consistent = "✓" if len(states) == 1 else "✗"
            detail = "  ".join(f"dx={c[0]}(D={c[1]:.2f})={'P' if c[2] else 'X'}" 
                              for c in combo_results)
            print(f"  ratio={ratio:.1f}: {detail}  [{consistent}]")
    
    # ============================================================
    # GENERATE PROVENANCE TABLE
    # ============================================================
    elapsed = time.time() - t0
    
    print(f"\n{'='*70}")
    print(f"PROVENANCE TABLE — {len(all_results)} total tests in {elapsed:.0f}s")
    print("=" * 70)
    
    # Write CSV
    csv_path = '/home/claude/chaos_pipeline/step4_replication_results.csv'
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'sweep', 'solver', 'bc', 'D', 'dx', 'N', 'seed_width',
            'physical_seed_width', 'dt', 'coupling_ratio',
            'seed_survived', 'propagated', 'propagation_distance',
            'final_center_U'
        ])
        writer.writeheader()
        for r in all_results:
            row = {k: r.get(k, '') for k in writer.fieldnames}
            writer.writerow(row)
    
    print(f"  Full results: {csv_path}")
    
    # ============================================================
    # CROSS-SOLVER / CROSS-BC AGREEMENT CHECK
    # ============================================================
    print(f"\n{'='*70}")
    print("SOLVER × BC AGREEMENT")
    print("=" * 70)
    
    # Group by (sweep, D, dx, seed_width) and check if all solvers/BCs agree
    from collections import defaultdict
    groups = defaultdict(list)
    for r in all_results:
        key = (r['sweep'], r['D'], r['dx'], r['seed_width'])
        groups[key].append(r)
    
    agreements = 0
    disagreements = 0
    disagree_list = []
    
    for key, results in groups.items():
        states = set(r['propagated'] for r in results)
        if len(states) == 1:
            agreements += 1
        else:
            disagreements += 1
            disagree_list.append(key)
    
    print(f"  Total parameter combinations: {len(groups)}")
    print(f"  All solvers/BCs agree: {agreements}")
    print(f"  Disagreements: {disagreements}")
    
    if disagree_list:
        print(f"\n  DISAGREEMENTS (solver/BC sensitivity detected):")
        for key in disagree_list[:10]:
            sweep, D, dx, sw = key
            results = groups[key]
            detail = "  ".join(
                f"{r['solver']}/{r['bc']}={'P' if r['propagated'] else 'X'}"
                for r in results
            )
            print(f"    {sweep} D={D} dx={dx} sw={sw}: {detail}")
    
    # ============================================================
    # KEY THRESHOLDS SUMMARY
    # ============================================================
    print(f"\n{'='*70}")
    print("KEY THRESHOLDS (Euler/Periodic baseline)")
    print("=" * 70)
    
    # D threshold at dx=1.0
    d_sweep = [r for r in all_results 
               if r['sweep'] == 'D_at_dx1' and r['solver'] == 'euler' 
               and r['bc'] == 'periodic']
    d_pinned = [r for r in d_sweep if not r['propagated']]
    d_prop = [r for r in d_sweep if r['propagated']]
    
    if d_pinned and d_prop:
        d_max_pin = max(r['D'] for r in d_pinned)
        d_min_prop = min(r['D'] for r in d_prop)
        print(f"  D threshold at dx=1.0: between {d_max_pin:.2f} and {d_min_prop:.2f}")
    elif not d_prop:
        print(f"  D threshold at dx=1.0: ALL PINNED up to D={max(r['D'] for r in d_sweep):.1f}")
    
    # dx threshold at D=0.12
    dx_sweep = [r for r in all_results 
                if r['sweep'] == 'dx_at_D012' and r['solver'] == 'euler' 
                and r['bc'] == 'periodic']
    dx_pinned = [r for r in dx_sweep if not r['propagated']]
    dx_prop = [r for r in dx_sweep if r['propagated']]
    
    if dx_pinned and dx_prop:
        dx_max_prop = max(r['dx'] for r in dx_prop)
        dx_min_pin = min(r['dx'] for r in dx_pinned)
        print(f"  dx threshold at D=0.12: between {dx_max_prop:.2f} and {dx_min_pin:.2f}")
    
    # Width at locked
    w_locked = [r for r in all_results 
                if r['sweep'] == 'width_locked' and r['solver'] == 'euler' 
                and r['bc'] == 'periodic']
    w_prop = [r for r in w_locked if r['propagated']]
    if w_prop:
        print(f"  Width rescue at D=0.12/dx=1.0: YES (min width={min(r['seed_width'] for r in w_prop)})")
    else:
        print(f"  Width rescue at D=0.12/dx=1.0: NO (tested up to {max(r['seed_width'] for r in w_locked)} nodes)")
    
    # Width at fine
    w_fine = [r for r in all_results 
              if r['sweep'] == 'width_fine' and r['solver'] == 'euler' 
              and r['bc'] == 'periodic']
    w_fine_prop = [r for r in w_fine if r['propagated']]
    if w_fine_prop:
        min_w = min(r['seed_width'] for r in w_fine_prop)
        phys = min_w * 0.10
        print(f"  Critical seed at D=0.12/dx=0.10: {min_w} nodes ({phys:.1f} spatial units)")
    
    # Coupling ratio
    print(f"\n  Coupling ratio consistency: checked at ratios {target_ratios}")
    
    print(f"\n  Script completed: {len(all_results)} tests, {elapsed:.0f}s total")
