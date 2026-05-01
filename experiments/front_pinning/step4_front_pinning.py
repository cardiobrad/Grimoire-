"""
GRIMOIRE CHAOS ANALYSIS — Step 4: Front Pinning Boundary
==========================================================
The audit proved: in the continuous PDE, the U=3 state MUST invade U=1.
But on a discrete grid, the Peierls-Nabarro barrier can FREEZE the wave.

This experiment maps the exact pinning boundary:
- Sweep D (diffusion) from very low to high
- Sweep dx (grid spacing) from fine to coarse
- At each (D, dx), plant a supercritical seed and check if propagation occurs

The result is the ENGINEERING CONSTRAINT:
"At what minimum D (or maximum dx) does the healing wave get stuck?"

Also tests at the locked D=0.12 with varying dx to find
the maximum grid spacing that still permits propagation.
"""

import numpy as np
import json
import time

LAMBDA = 0.45
ALPHA = np.pi
DT_SAFETY_FACTOR = 0.4  # Use 40% of CFL limit for stability
N_GRID = 64  # 1D grid nodes
MAX_STEPS = 5000
SEED_AMPLITUDE = 2.5  # Well above barrier
SEED_WIDTH = 3  # nodes

def step_1d(U, D, dx, dt):
    """One FTCS timestep of 1D GRIMOIRE"""
    lap = (np.roll(U, 1) + np.roll(U, -1) - 2 * U) / (dx**2)
    reaction = LAMBDA * U**2 * np.sin(ALPHA * U)
    U_new = U + dt * (D * lap + reaction)
    return np.maximum(U_new, 0)

def test_propagation(D, dx, verbose=False):
    """
    Plant a supercritical seed at center, run simulation,
    check if the U=3 front propagates outward or gets pinned.
    
    Returns:
        propagated: bool - did the front move beyond the seed region?
        final_spread: float - how far U>2.5 extended from center
        seed_survived: bool - did the seed reach U~3?
        steps_to_ignite: int - steps until seed hit U>2.9
    """
    # CFL-safe timestep
    dt = DT_SAFETY_FACTOR * dx**2 / (2 * D) if D > 0 else 0.01
    dt = min(dt, 0.05)  # Hard cap
    
    # Initialize: uniform U=1 with supercritical seed at center
    U = np.ones(N_GRID) * 1.0
    center = N_GRID // 2
    half_w = SEED_WIDTH // 2
    U[center - half_w:center + half_w + 1] = SEED_AMPLITUDE
    
    seed_survived = False
    steps_to_ignite = -1
    
    # Track the rightward edge of the U>2.0 region
    initial_right_edge = center + half_w
    max_right_edge = initial_right_edge
    
    for step in range(MAX_STEPS):
        U = step_1d(U, D, dx, dt)
        
        # Check if seed reached U~3
        if not seed_survived and U[center] > 2.9:
            seed_survived = True
            steps_to_ignite = step
        
        # Track rightward spread of U>2.0
        above_2 = np.where(U > 2.0)[0]
        if len(above_2) > 0:
            current_right = np.max(above_2)
            if current_right > max_right_edge:
                max_right_edge = current_right
    
    # Measure final spread
    above_25 = np.where(U > 2.5)[0]
    final_spread = len(above_25)
    
    # Did it propagate BEYOND the initial seed?
    propagation_distance = max_right_edge - initial_right_edge
    propagated = propagation_distance > 2  # At least 2 nodes beyond seed
    
    if verbose:
        print(f"    D={D:.3f}, dx={dx:.2f}, dt={dt:.4f}")
        print(f"    Seed survived: {seed_survived}, Steps to ignite: {steps_to_ignite}")
        print(f"    Propagation distance: {propagation_distance} nodes")
        print(f"    Final U>2.5 spread: {final_spread} nodes")
        print(f"    PROPAGATED: {propagated}")
    
    return {
        'D': float(D),
        'dx': float(dx),
        'dt': float(dt),
        'coupling_ratio': float(D / dx**2),
        'propagated': propagated,
        'propagation_distance': int(propagation_distance),
        'final_spread': int(final_spread),
        'seed_survived': seed_survived,
        'steps_to_ignite': steps_to_ignite
    }


if __name__ == "__main__":
    print("=" * 70)
    print("GRIMOIRE — Step 4: Front Pinning Boundary")
    print("=" * 70)
    print(f"Grid: {N_GRID} nodes, Seed: amplitude={SEED_AMPLITUDE}, width={SEED_WIDTH}")
    print(f"Max steps: {MAX_STEPS}")
    print()
    
    all_results = []
    
    # ============================================================
    # TEST 1: D sweep at locked dx=1.0
    # ============================================================
    print("=" * 60)
    print("TEST 1: D sweep (dx=1.0 fixed)")
    print("  Finding minimum D for propagation")
    print("=" * 60)
    
    D_values = [0.005, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 
                0.10, 0.12, 0.15, 0.20, 0.30, 0.50]
    dx_fixed = 1.0
    
    for D in D_values:
        result = test_propagation(D, dx_fixed)
        result['test'] = 'D_sweep'
        all_results.append(result)
        
        status = "PROPAGATES" if result['propagated'] else "PINNED"
        seed_ok = "✓" if result['seed_survived'] else "✗"
        marker = " ← LOCKED" if abs(D - 0.12) < 0.001 else ""
        
        print(f"  D={D:.3f}  coupling={result['coupling_ratio']:.3f}  "
              f"seed={seed_ok}  spread={result['propagation_distance']:3d} nodes  "
              f"[{status}]{marker}")
    
    # Find transition
    d_sweep = [r for r in all_results if r['test'] == 'D_sweep']
    pinned = [r for r in d_sweep if not r['propagated']]
    propagating = [r for r in d_sweep if r['propagated']]
    
    if pinned and propagating:
        d_pin_max = max(r['D'] for r in pinned)
        d_prop_min = min(r['D'] for r in propagating)
        print(f"\n  PINNING BOUNDARY: D_critical is between {d_pin_max:.3f} and {d_prop_min:.3f}")
        print(f"  Coupling ratio at transition: {d_prop_min/dx_fixed**2:.4f}")
    elif not pinned:
        print(f"\n  All tested D values propagate at dx={dx_fixed}")
    else:
        print(f"\n  No propagation at any tested D value at dx={dx_fixed}")
    
    # ============================================================
    # TEST 2: dx sweep at locked D=0.12
    # ============================================================
    print(f"\n{'='*60}")
    print("TEST 2: dx sweep (D=0.12 fixed)")
    print("  Finding maximum grid spacing for propagation")
    print("=" * 60)
    
    D_fixed = 0.12
    dx_values = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 
                 2.5, 3.0, 4.0, 5.0]
    
    for dx in dx_values:
        result = test_propagation(D_fixed, dx)
        result['test'] = 'dx_sweep'
        all_results.append(result)
        
        status = "PROPAGATES" if result['propagated'] else "PINNED"
        seed_ok = "✓" if result['seed_survived'] else "✗"
        marker = " ← LOCKED" if abs(dx - 1.0) < 0.01 else ""
        
        print(f"  dx={dx:.2f}  coupling={result['coupling_ratio']:.4f}  "
              f"seed={seed_ok}  spread={result['propagation_distance']:3d} nodes  "
              f"[{status}]{marker}")
    
    # Find transition
    dx_sweep = [r for r in all_results if r['test'] == 'dx_sweep']
    pinned_dx = [r for r in dx_sweep if not r['propagated']]
    prop_dx = [r for r in dx_sweep if r['propagated']]
    
    if pinned_dx and prop_dx:
        dx_prop_max = max(r['dx'] for r in prop_dx)
        dx_pin_min = min(r['dx'] for r in pinned_dx)
        print(f"\n  PINNING BOUNDARY: dx_critical is between {dx_prop_max:.2f} and {dx_pin_min:.2f}")
        print(f"  Coupling ratio at transition: {D_fixed/dx_pin_min**2:.4f}")
    
    # ============================================================
    # TEST 3: Full D×dx phase diagram
    # ============================================================
    print(f"\n{'='*60}")
    print("TEST 3: D × dx phase diagram")
    print("  Mapping the full pinning boundary")
    print("=" * 60)
    
    D_grid = [0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20, 0.30, 0.50]
    dx_grid = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
    
    phase_map = np.zeros((len(D_grid), len(dx_grid)), dtype=int)
    
    for i, D in enumerate(D_grid):
        row = ""
        for j, dx in enumerate(dx_grid):
            result = test_propagation(D, dx)
            result['test'] = 'phase_diagram'
            all_results.append(result)
            
            if result['propagated']:
                phase_map[i, j] = 2
                row += " ■"
            elif result['seed_survived']:
                phase_map[i, j] = 1
                row += " □"
            else:
                phase_map[i, j] = 0
                row += " ·"
        
        marker = " ←" if abs(D - 0.12) < 0.001 else ""
        print(f"  D={D:.2f}: {row}{marker}")
    
    print(f"\n  Legend: ■=propagates  □=ignites but pinned  ·=seed dies")
    print(f"  dx:    {' '.join(f'{dx:3.1f}' for dx in dx_grid)}")
    
    # ============================================================
    # TEST 4: Critical coupling ratio
    # ============================================================
    print(f"\n{'='*60}")
    print("TEST 4: Is the pinning boundary a function of D/dx²?")
    print("=" * 60)
    
    # If pinning depends on the coupling ratio D/dx², then different
    # (D, dx) combinations with the same ratio should behave the same
    
    target_ratios = [0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.15, 0.20]
    
    for ratio in target_ratios:
        # Test with two different (D, dx) combinations giving same ratio
        combos = []
        
        # Combo 1: dx=1.0
        D1 = ratio * 1.0**2
        if 0.005 <= D1 <= 1.0:
            r1 = test_propagation(D1, 1.0)
            combos.append(('dx=1.0', D1, r1))
        
        # Combo 2: dx=2.0
        D2 = ratio * 2.0**2
        if 0.005 <= D2 <= 1.0:
            r2 = test_propagation(D2, 2.0)
            combos.append(('dx=2.0', D2, r2))
        
        # Combo 3: dx=0.5
        D3 = ratio * 0.5**2
        if 0.005 <= D3 <= 1.0:
            r3 = test_propagation(D3, 0.5)
            combos.append(('dx=0.5', D3, r3))
        
        if len(combos) >= 2:
            results_match = all(c[2]['propagated'] == combos[0][2]['propagated'] for c in combos)
            match_str = "✓ CONSISTENT" if results_match else "✗ INCONSISTENT"
            
            detail = "  ".join(
                f"{c[0]}(D={c[1]:.3f})={'PROP' if c[2]['propagated'] else 'PIN'}"
                for c in combos
            )
            print(f"  ratio={ratio:.2f}: {detail}  [{match_str}]")
    
    # ============================================================
    # FINAL SUMMARY
    # ============================================================
    print(f"\n{'='*70}")
    print("FINAL SUMMARY — FRONT PINNING ANALYSIS")
    print("=" * 70)
    
    # At locked parameters
    locked = [r for r in all_results 
              if r['test'] == 'D_sweep' and abs(r['D'] - 0.12) < 0.001]
    if locked:
        r = locked[0]
        print(f"\n  AT LOCKED PARAMETERS (D=0.12, dx=1.0):")
        print(f"    Coupling ratio: {r['coupling_ratio']:.4f}")
        print(f"    Propagation: {'YES' if r['propagated'] else 'NO (PINNED)'}")
        print(f"    Spread: {r['propagation_distance']} nodes beyond seed")
    
    # Count phase diagram
    phase_results = [r for r in all_results if r['test'] == 'phase_diagram']
    n_prop = sum(1 for r in phase_results if r['propagated'])
    n_ign = sum(1 for r in phase_results if r['seed_survived'] and not r['propagated'])
    n_dead = sum(1 for r in phase_results if not r['seed_survived'])
    
    print(f"\n  PHASE DIAGRAM ({len(phase_results)} combinations tested):")
    print(f"    Full propagation: {n_prop}")
    print(f"    Ignite but pinned: {n_ign}")
    print(f"    Seed death: {n_dead}")
    
    # Save
    with open('/home/claude/chaos_pipeline/step4_results.json', 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n  Results saved to step4_results.json")
