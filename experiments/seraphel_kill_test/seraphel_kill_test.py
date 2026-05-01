"""
SERAPHEL'S KILL TEST: Parking State Robustness
================================================
From GRIMOIRE Master Reference Section 6.5:
"Vary λ and α systematically while holding D fixed.
Kill condition: if the parked state vanishes or becomes 
unstable for small deviations from λ=0.45, α=π, the 
parking property is a numerical coincidence, not an 
architectural feature."

Tests:
1. λ sweep (0.1 to 1.0) at α=π: does U=1 remain stable?
2. α sweep (0.5π to 2π) at λ=0.45: does U=1 remain stable?
3. Full λ×α grid: map the parking stability region
4. For each (λ,α), compute J(U*) at the first stable node

Kill criterion: if parking vanishes for deviations < 10%
from locked values, the parking property is fragile.
"""

import numpy as np
import csv
import time

D = 0.12
DX = 1.0
DT = 0.01
N = 64  # 1D grid

def find_fixed_points(lam, alpha, u_max=5.0, resolution=10000):
    """Find zeros of f(U) = λU²sin(αU) in [0, u_max]"""
    U_vals = np.linspace(0.001, u_max, resolution)
    f_vals = lam * U_vals**2 * np.sin(alpha * U_vals)
    
    # Find sign changes
    sign_changes = np.where(np.diff(np.sign(f_vals)))[0]
    
    roots = [0.0]  # U=0 is always a root
    for idx in sign_changes:
        # Linear interpolation for better root estimate
        u1, u2 = U_vals[idx], U_vals[idx+1]
        f1, f2 = f_vals[idx], f_vals[idx+1]
        root = u1 - f1 * (u2 - u1) / (f2 - f1)
        roots.append(float(root))
    
    return roots

def jacobian(U, lam, alpha):
    """f'(U) = λ[2U·sin(αU) + αU²·cos(αU)]"""
    return lam * (2 * U * np.sin(alpha * U) + alpha * U**2 * np.cos(alpha * U))

def classify_fixed_point(J_val):
    if abs(J_val) < 1e-10:
        return "NON-HYPERBOLIC"
    elif J_val < 0:
        return "STABLE"
    else:
        return "UNSTABLE"

def test_parking_numerically(lam, alpha, u_park_approx):
    """
    Plant the system near the expected parking state,
    evolve, and check if it stays parked.
    """
    U = np.ones(N) * u_park_approx
    # Add small perturbation
    np.random.seed(42)
    U += 0.05 * np.random.randn(N)
    U = np.maximum(U, 0)
    
    dt = min(DT, 0.4 * DX**2 / (2 * D))
    
    for _ in range(5000):
        lap = (np.roll(U, 1) + np.roll(U, -1) - 2 * U) / (DX**2)
        reaction = lam * U**2 * np.sin(alpha * U)
        U = np.maximum(U + dt * (D * lap + reaction), 0)
    
    mean_U = np.mean(U)
    std_U = np.std(U)
    
    # Did it stay near the parking state?
    parked = abs(mean_U - u_park_approx) < 0.3 and std_U < 0.1
    
    return {
        'mean_U': float(mean_U),
        'std_U': float(std_U),
        'parked': parked
    }

if __name__ == "__main__":
    t0 = time.time()
    all_results = []
    
    print("=" * 70)
    print("SERAPHEL'S KILL TEST: Parking State Robustness")
    print("=" * 70)
    print(f"Kill condition: parking vanishes for <10% deviation from locked values")
    print(f"Locked: λ=0.45, α=π")
    print()
    
    # ============================================================
    # TEST 1: λ sweep at α=π
    # ============================================================
    print("=" * 60)
    print("TEST 1: λ sweep (α=π fixed)")
    print("=" * 60)
    
    lambda_vals = np.arange(0.05, 1.05, 0.05)
    
    for lam in lambda_vals:
        roots = find_fixed_points(lam, np.pi)
        
        # Find first non-zero stable node (the "parking state")
        parking_root = None
        parking_J = None
        barrier_root = None
        barrier_J = None
        deep_root = None
        deep_J = None
        
        for r in roots:
            if r < 0.01:
                continue
            J = jacobian(r, lam, np.pi)
            if parking_root is None and J < 0:
                parking_root = r
                parking_J = J
            elif parking_root is not None and barrier_root is None and J > 0:
                barrier_root = r
                barrier_J = J
            elif barrier_root is not None and deep_root is None and J < 0:
                deep_root = r
                deep_J = J
        
        # Numerical parking test
        if parking_root is not None:
            num_test = test_parking_numerically(lam, np.pi, parking_root)
        else:
            num_test = {'mean_U': 0, 'std_U': 0, 'parked': False}
        
        marker = " ← LOCKED" if abs(lam - 0.45) < 0.01 else ""
        park_str = f"U*={parking_root:.3f} J={parking_J:.3f}" if parking_root else "NONE"
        bar_str = f"U*={barrier_root:.3f} J={barrier_J:+.3f}" if barrier_root else "NONE"
        deep_str = f"U*={deep_root:.3f} J={deep_J:.3f}" if deep_root else "NONE"
        num_str = "PARKED" if num_test['parked'] else f"DRIFTED→{num_test['mean_U']:.2f}"
        
        print(f"  λ={lam:.2f}: park={park_str}  barrier={bar_str}  "
              f"deep={deep_str}  [{num_str}]{marker}")
        
        all_results.append({
            'test': 'lambda_sweep',
            'lambda': float(lam),
            'alpha': float(np.pi),
            'parking_root': parking_root,
            'parking_J': parking_J,
            'barrier_root': barrier_root,
            'barrier_J': barrier_J,
            'deep_root': deep_root,
            'deep_J': deep_J,
            'numerical_parked': num_test['parked'],
            'numerical_mean': num_test['mean_U'],
            'numerical_std': num_test['std_U']
        })
    
    # ============================================================
    # TEST 2: α sweep at λ=0.45
    # ============================================================
    print(f"\n{'='*60}")
    print("TEST 2: α sweep (λ=0.45 fixed)")
    print("=" * 60)
    
    alpha_vals = np.linspace(0.5 * np.pi, 2.0 * np.pi, 20)
    
    for alpha in alpha_vals:
        roots = find_fixed_points(0.45, alpha)
        
        parking_root = None
        parking_J = None
        barrier_root = None
        barrier_J = None
        deep_root = None
        deep_J = None
        
        for r in roots:
            if r < 0.01:
                continue
            J = jacobian(r, 0.45, alpha)
            if parking_root is None and J < 0:
                parking_root = r
                parking_J = J
            elif parking_root is not None and barrier_root is None and J > 0:
                barrier_root = r
                barrier_J = J
            elif barrier_root is not None and deep_root is None and J < 0:
                deep_root = r
                deep_J = J
        
        if parking_root is not None:
            num_test = test_parking_numerically(0.45, alpha, parking_root)
        else:
            num_test = {'mean_U': 0, 'std_U': 0, 'parked': False}
        
        marker = " ← LOCKED" if abs(alpha - np.pi) < 0.05 else ""
        park_str = f"U*={parking_root:.3f} J={parking_J:.3f}" if parking_root else "NONE"
        num_str = "PARKED" if num_test['parked'] else f"DRIFTED→{num_test['mean_U']:.2f}"
        
        print(f"  α={alpha/np.pi:.2f}π: park={park_str}  [{num_str}]{marker}")
        
        all_results.append({
            'test': 'alpha_sweep',
            'lambda': 0.45,
            'alpha': float(alpha),
            'alpha_over_pi': float(alpha / np.pi),
            'parking_root': parking_root,
            'parking_J': parking_J,
            'barrier_root': barrier_root,
            'barrier_J': barrier_J,
            'deep_root': deep_root,
            'deep_J': deep_J,
            'numerical_parked': num_test['parked'],
            'numerical_mean': num_test['mean_U'],
            'numerical_std': num_test['std_U']
        })
    
    # ============================================================
    # TEST 3: Full λ×α grid (coarse)
    # ============================================================
    print(f"\n{'='*60}")
    print("TEST 3: λ×α stability grid")
    print("=" * 60)
    
    lam_grid = [0.10, 0.20, 0.30, 0.40, 0.45, 0.50, 0.60, 0.80, 1.00]
    alpha_grid = [0.5*np.pi, 0.75*np.pi, np.pi, 1.25*np.pi, 1.5*np.pi, 2.0*np.pi]
    
    # Header
    header = "       " + "  ".join(f"α={a/np.pi:.2f}π" for a in alpha_grid)
    print(header)
    
    for lam in lam_grid:
        row = f"λ={lam:.2f}: "
        for alpha in alpha_grid:
            roots = find_fixed_points(lam, alpha)
            
            has_parking = False
            has_barrier = False
            has_deep = False
            
            found_first_stable = False
            for r in roots:
                if r < 0.01:
                    continue
                J = jacobian(r, lam, alpha)
                if not found_first_stable and J < 0:
                    has_parking = True
                    found_first_stable = True
                elif found_first_stable and not has_barrier and J > 0:
                    has_barrier = True
                elif has_barrier and not has_deep and J < 0:
                    has_deep = True
            
            if has_parking and has_barrier and has_deep:
                row += "  P+B+D  "  # Full bistable with parking
            elif has_parking and has_barrier:
                row += "  P+B    "
            elif has_parking:
                row += "  P      "
            else:
                row += "  ---    "
            
            all_results.append({
                'test': 'grid',
                'lambda': float(lam),
                'alpha': float(alpha),
                'has_parking': has_parking,
                'has_barrier': has_barrier,
                'has_deep': has_deep
            })
        
        marker = " ←" if abs(lam - 0.45) < 0.01 else ""
        print(row + marker)
    
    # ============================================================
    # TEST 4: Sensitivity — how far can you deviate before parking dies?
    # ============================================================
    print(f"\n{'='*60}")
    print("TEST 4: Parking sensitivity (% deviation from locked)")
    print("=" * 60)
    
    locked_lam = 0.45
    locked_alpha = np.pi
    
    deviations = [0.01, 0.02, 0.05, 0.10, 0.20, 0.30, 0.50]
    
    print("\n  λ deviations (α=π fixed):")
    for dev in deviations:
        lam_lo = locked_lam * (1 - dev)
        lam_hi = locked_lam * (1 + dev)
        
        roots_lo = find_fixed_points(lam_lo, np.pi)
        roots_hi = find_fixed_points(lam_hi, np.pi)
        
        # Check parking exists in both
        park_lo = any(jacobian(r, lam_lo, np.pi) < -0.1 for r in roots_lo if r > 0.5)
        park_hi = any(jacobian(r, lam_hi, np.pi) < -0.1 for r in roots_hi if r > 0.5)
        
        status = "✓ BOTH" if (park_lo and park_hi) else ("✗ LOST" if not (park_lo or park_hi) else "~ PARTIAL")
        print(f"    ±{dev*100:.0f}%: λ=[{lam_lo:.3f}, {lam_hi:.3f}]  parking={status}")
    
    print("\n  α deviations (λ=0.45 fixed):")
    for dev in deviations:
        alpha_lo = locked_alpha * (1 - dev)
        alpha_hi = locked_alpha * (1 + dev)
        
        roots_lo = find_fixed_points(0.45, alpha_lo)
        roots_hi = find_fixed_points(0.45, alpha_hi)
        
        park_lo = any(jacobian(r, 0.45, alpha_lo) < -0.1 for r in roots_lo if r > 0.5)
        park_hi = any(jacobian(r, 0.45, alpha_hi) < -0.1 for r in roots_hi if r > 0.5)
        
        status = "✓ BOTH" if (park_lo and park_hi) else ("✗ LOST" if not (park_lo or park_hi) else "~ PARTIAL")
        print(f"    ±{dev*100:.0f}%: α=[{alpha_lo/np.pi:.3f}π, {alpha_hi/np.pi:.3f}π]  parking={status}")
    
    # ============================================================
    # VERDICT
    # ============================================================
    elapsed = time.time() - t0
    
    print(f"\n{'='*70}")
    print("SERAPHEL'S VERDICT")
    print("=" * 70)
    
    # Check λ sweep
    lam_results = [r for r in all_results if r['test'] == 'lambda_sweep']
    lam_parked = [r for r in lam_results if r.get('numerical_parked', False)]
    lam_range = (min(r['lambda'] for r in lam_parked), max(r['lambda'] for r in lam_parked)) if lam_parked else (0,0)
    
    print(f"\n  λ sweep: parking survived in {len(lam_parked)}/{len(lam_results)} values")
    if lam_parked:
        print(f"  Parking range: λ ∈ [{lam_range[0]:.2f}, {lam_range[1]:.2f}]")
        print(f"  Locked λ=0.45 is {'INSIDE' if lam_range[0] <= 0.45 <= lam_range[1] else 'OUTSIDE'} the range")
    
    # Check α sweep  
    alpha_results = [r for r in all_results if r['test'] == 'alpha_sweep']
    alpha_parked = [r for r in alpha_results if r.get('numerical_parked', False)]
    alpha_range = (min(r['alpha']/np.pi for r in alpha_parked), max(r['alpha']/np.pi for r in alpha_parked)) if alpha_parked else (0,0)
    
    print(f"\n  α sweep: parking survived in {len(alpha_parked)}/{len(alpha_results)} values")
    if alpha_parked:
        print(f"  Parking range: α ∈ [{alpha_range[0]:.2f}π, {alpha_range[1]:.2f}π]")
        print(f"  Locked α=π is {'INSIDE' if alpha_range[0] <= 1.0 <= alpha_range[1] else 'OUTSIDE'} the range")
    
    # Grid summary
    grid_results = [r for r in all_results if r['test'] == 'grid']
    full_bistable = [r for r in grid_results if r.get('has_parking') and r.get('has_barrier') and r.get('has_deep')]
    
    print(f"\n  λ×α grid: full bistable (park+barrier+deep) in {len(full_bistable)}/{len(grid_results)} combinations")
    
    # KILL DECISION
    if len(lam_parked) >= len(lam_results) * 0.8 and len(alpha_parked) >= len(alpha_results) * 0.8:
        print(f"\n  ★ PARKING IS ROBUST: survives across wide parameter ranges.")
        print(f"    This is an ARCHITECTURAL feature of the sin(αU) term, not a numerical coincidence.")
        print(f"    Kill test: SURVIVED.")
    elif len(lam_parked) >= len(lam_results) * 0.5:
        print(f"\n  ◐ PARKING IS MODERATELY ROBUST: survives in a substantial but not universal range.")
        print(f"    Kill test: SURVIVED with caveats.")
    else:
        print(f"\n  ✗ PARKING IS FRAGILE: collapses for small deviations.")
        print(f"    Kill test: KILLED. Parking is a numerical coincidence at λ=0.45, α=π.")
    
    print(f"\n  Completed: {len(all_results)} tests in {elapsed:.0f}s")
    
    # Save CSV
    csv_path = '/home/claude/chaos_pipeline/seraphel_kill_test.csv'
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'test', 'lambda', 'alpha', 'alpha_over_pi',
            'parking_root', 'parking_J', 'barrier_root', 'barrier_J',
            'deep_root', 'deep_J', 'has_parking', 'has_barrier', 'has_deep',
            'numerical_parked', 'numerical_mean', 'numerical_std'
        ])
        writer.writeheader()
        for r in all_results:
            row = {k: r.get(k, '') for k in writer.fieldnames}
            writer.writerow(row)
    
    print(f"  Results saved: {csv_path}")
