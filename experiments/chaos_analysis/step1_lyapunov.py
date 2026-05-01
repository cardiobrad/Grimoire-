"""
GRIMOIRE CHAOS ANALYSIS — Step 1: Maximum Lyapunov Exponent
============================================================
Tests whether the GRIMOIRE equation with locked parameters
generates deterministic chaos.

Method: Direct perturbation method on discretized PDE.
- Evolve reference trajectory on NxN grid
- Evolve perturbed copy (tiny initial perturbation)
- Measure exponential divergence rate
- Renormalize periodically to prevent overflow
- Average log-divergence rate = max Lyapunov exponent

If λ_max > 0: CHAOTIC (sensitive dependence on initial conditions)
If λ_max ≈ 0: EDGE OF CHAOS (marginal stability)  
If λ_max < 0: ORDERED (perturbations decay)

Locked parameters: D=0.12, λ=0.45, α=π
"""

import numpy as np
import json
import time

# ============================================================
# LOCKED GRIMOIRE PARAMETERS
# ============================================================
D = 0.12        # Diffusion
LAMBDA = 0.45   # Reaction rate  
ALPHA = np.pi   # Oscillation frequency
DX = 1.0        # Spatial step
DT = 0.01       # Time step (must satisfy CFL: dt < dx²/(4D))
# CFL check: 0.01 < 1.0/(4*0.12) = 2.08 ✓

# Grid sizes to test
GRID_SIZES = [16, 32]  # Start small, scale up
N_RENORM_STEPS = 50     # Steps between renormalizations
N_RENORM_CYCLES = 200   # Total renormalization cycles
PERTURBATION_SIZE = 1e-8

def grimoire_reaction(U):
    """The GRIMOIRE SIN term: λU²sin(αU)"""
    return LAMBDA * U**2 * np.sin(ALPHA * U)

def linear_ceiling_reaction(U):
    """Ablation baseline: λU²·max(0, 1-U)"""
    return LAMBDA * U**2 * np.maximum(0, 1.0 - U)

def laplacian_2d(U, dx):
    """2D discrete Laplacian with periodic boundary conditions"""
    return (
        np.roll(U, 1, axis=0) + np.roll(U, -1, axis=0) +
        np.roll(U, 1, axis=1) + np.roll(U, -1, axis=1) -
        4 * U
    ) / (dx**2)

def step_forward(U, reaction_fn, dt, dx):
    """One FTCS timestep of the reaction-diffusion equation"""
    lap = laplacian_2d(U, dx)
    dU = D * lap + reaction_fn(U)
    U_new = U + dt * dU
    U_new = np.maximum(U_new, 0)  # U >= 0 enforced
    return U_new

def compute_max_lyapunov(N, reaction_fn, reaction_name, seed=42):
    """
    Compute maximum Lyapunov exponent for the discretized GRIMOIRE PDE.
    
    Uses direct perturbation method:
    1. Evolve reference state U
    2. Evolve perturbed state U + δ
    3. Measure ||δ(t)|| / ||δ(0)|| over time
    4. Renormalize δ periodically
    5. Average log-growth rate = max Lyapunov exponent
    """
    np.random.seed(seed)
    
    # Initial condition: random field with some structure
    # Use moderate values so we're in the interesting regime
    U_ref = 0.5 + 0.3 * np.random.randn(N, N)
    U_ref = np.maximum(U_ref, 0)
    
    # Small random perturbation
    delta = PERTURBATION_SIZE * np.random.randn(N, N)
    U_pert = U_ref + delta
    U_pert = np.maximum(U_pert, 0)
    
    # Warm up the reference trajectory (let transients die)
    print(f"  Warming up {N}x{N} grid ({reaction_name})...")
    for _ in range(500):
        U_ref = step_forward(U_ref, reaction_fn, DT, DX)
    
    # Reset perturbation after warmup
    delta = PERTURBATION_SIZE * np.random.randn(N, N)
    U_pert = U_ref + delta
    
    # Compute Lyapunov exponent
    lyapunov_sum = 0.0
    total_time = 0.0
    exponents = []
    
    print(f"  Computing Lyapunov exponent ({N_RENORM_CYCLES} cycles)...")
    
    for cycle in range(N_RENORM_CYCLES):
        # Evolve both trajectories
        for _ in range(N_RENORM_STEPS):
            U_ref = step_forward(U_ref, reaction_fn, DT, DX)
            U_pert = step_forward(U_pert, reaction_fn, DT, DX)
        
        # Measure divergence
        delta = U_pert - U_ref
        delta_norm = np.linalg.norm(delta)
        
        if delta_norm == 0 or np.isnan(delta_norm) or np.isinf(delta_norm):
            print(f"  WARNING: delta_norm={delta_norm} at cycle {cycle}. Stopping.")
            break
        
        # Accumulate log-divergence
        log_ratio = np.log(delta_norm / PERTURBATION_SIZE)
        elapsed = N_RENORM_STEPS * DT
        lyapunov_sum += log_ratio
        total_time += elapsed
        
        # Running estimate
        current_estimate = lyapunov_sum / total_time
        exponents.append(current_estimate)
        
        # Renormalize perturbation
        delta = delta * (PERTURBATION_SIZE / delta_norm)
        U_pert = U_ref + delta
        U_pert = np.maximum(U_pert, 0)
        
        if (cycle + 1) % 50 == 0:
            print(f"    Cycle {cycle+1}/{N_RENORM_CYCLES}: λ_max ≈ {current_estimate:.6f}")
    
    final_lyapunov = lyapunov_sum / total_time if total_time > 0 else 0.0
    
    # Convergence check: compare last 25% to overall
    if len(exponents) > 20:
        late_mean = np.mean(exponents[-len(exponents)//4:])
        early_mean = np.mean(exponents[:len(exponents)//4])
        convergence = abs(late_mean - early_mean) / (abs(final_lyapunov) + 1e-10)
    else:
        convergence = float('inf')
    
    return final_lyapunov, exponents, convergence

def classify_result(lyap):
    """Classify the Lyapunov exponent result"""
    if lyap > 0.01:
        return "CHAOTIC (positive λ_max — sensitive dependence on initial conditions)"
    elif lyap > -0.01:
        return "EDGE OF CHAOS (λ_max ≈ 0 — marginal stability)"
    else:
        return "ORDERED (negative λ_max — perturbations decay)"

# ============================================================
# RUN THE TESTS
# ============================================================
if __name__ == "__main__":
    print("=" * 70)
    print("GRIMOIRE CHAOS ANALYSIS — Step 1: Maximum Lyapunov Exponent")
    print("=" * 70)
    print(f"Parameters: D={D}, λ={LAMBDA}, α=π")
    print(f"Time step: {DT}, Spatial step: {DX}")
    print(f"CFL condition: dt={DT} < dx²/(4D)={DX**2/(4*D):.4f} ✓")
    print()
    
    all_results = {}
    
    for N in GRID_SIZES:
        print(f"\n{'='*60}")
        print(f"GRID SIZE: {N}x{N} ({N*N} dimensions)")
        print(f"{'='*60}")
        
        results = {}
        
        # Test 1: GRIMOIRE (sin term)
        print(f"\n--- TEST: GRIMOIRE sin(αU) term ---")
        t0 = time.time()
        lyap_sin, exp_sin, conv_sin = compute_max_lyapunov(
            N, grimoire_reaction, "GRIMOIRE sin(αU)"
        )
        t_sin = time.time() - t0
        
        print(f"\n  RESULT: λ_max = {lyap_sin:.6f}")
        print(f"  Classification: {classify_result(lyap_sin)}")
        print(f"  Convergence: {conv_sin:.4f} (lower = more stable)")
        print(f"  Time: {t_sin:.1f}s")
        
        results['grimoire_sin'] = {
            'lyapunov_max': lyap_sin,
            'classification': classify_result(lyap_sin),
            'convergence': conv_sin,
            'grid_size': N,
            'n_dimensions': N*N
        }
        
        # Test 2: Linear ceiling ablation
        print(f"\n--- TEST: Linear ceiling ablation ---")
        t0 = time.time()
        lyap_lin, exp_lin, conv_lin = compute_max_lyapunov(
            N, linear_ceiling_reaction, "Linear ceiling"
        )
        t_lin = time.time() - t0
        
        print(f"\n  RESULT: λ_max = {lyap_lin:.6f}")
        print(f"  Classification: {classify_result(lyap_lin)}")
        print(f"  Convergence: {conv_lin:.4f}")
        print(f"  Time: {t_lin:.1f}s")
        
        results['linear_ceiling'] = {
            'lyapunov_max': lyap_lin,
            'classification': classify_result(lyap_lin),
            'convergence': conv_lin,
            'grid_size': N,
            'n_dimensions': N*N
        }
        
        # Comparison
        print(f"\n--- COMPARISON ({N}x{N}) ---")
        print(f"  GRIMOIRE sin(αU):    λ_max = {lyap_sin:.6f}  [{classify_result(lyap_sin)}]")
        print(f"  Linear ceiling:       λ_max = {lyap_lin:.6f}  [{classify_result(lyap_lin)}]")
        
        diff = lyap_sin - lyap_lin
        if diff > 0.01:
            print(f"  → sin(αU) is MORE chaotic by {diff:.6f}")
            print(f"  → The sine term generates dynamics the linear ceiling does not.")
        elif diff < -0.01:
            print(f"  → Linear ceiling is MORE chaotic by {-diff:.6f}")
            print(f"  → WARNING: This undermines the 'sine = chaos generator' hypothesis.")
        else:
            print(f"  → Both models have similar Lyapunov exponents (diff={diff:.6f})")
            print(f"  → The sine term may not be the chaos-generating element.")
        
        all_results[f'{N}x{N}'] = results
    
    # Final verdict
    print("\n" + "=" * 70)
    print("FINAL VERDICT")
    print("=" * 70)
    
    for grid_key, results in all_results.items():
        sin_lyap = results['grimoire_sin']['lyapunov_max']
        lin_lyap = results['linear_ceiling']['lyapunov_max']
        
        print(f"\n{grid_key}:")
        print(f"  GRIMOIRE:       λ_max = {sin_lyap:.6f}")
        print(f"  Linear ceiling: λ_max = {lin_lyap:.6f}")
        
        if sin_lyap > 0.01 and lin_lyap < 0.01:
            print(f"  ★ CHAOS CONFIRMED: sin(αU) generates chaos, linear ceiling does not.")
            print(f"  ★ This is a PHASE TRANSITION between chaotic and ordered dynamics.")
        elif sin_lyap > 0.01 and lin_lyap > 0.01:
            print(f"  ⚠ BOTH CHAOTIC: sin(αU) is not uniquely chaos-generating.")
        elif sin_lyap < -0.01 and lin_lyap < -0.01:
            print(f"  ✗ BOTH ORDERED: No chaos with locked parameters. Chaos claim is DEAD.")
        elif abs(sin_lyap) < 0.01:
            print(f"  ? EDGE: GRIMOIRE is near the edge of chaos. Needs deeper analysis.")
    
    # Save results
    with open('/home/claude/chaos_pipeline/step1_results.json', 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\nResults saved to step1_results.json")
