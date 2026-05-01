"""
GRIMOIRE CHAOS ANALYSIS — Step 3: GSM-Bifurcation Correspondence
=================================================================
Tests whether Good Seed Metric classifications correspond to 
formally computed dynamical regimes.

For each seed type, we:
1. Plant the seed on a blank field
2. Evolve the system  
3. Compute the local Lyapunov exponent around the seed
4. Measure the actual dynamical regime
5. Compare against GSM classification

Hypothesis:
  DORMANT   → ordered (negative Lyapunov) — trivial fixed point
  FRAGILE   → near separatrix (Lyapunov near zero)
  EDGE CASE → bifurcation boundary (Lyapunov ≈ 0)
  AMPLIFYING → chaotic/unstable (positive Lyapunov)
  RESILIENT  → robust attractor (negative but complex dynamics)
"""

import numpy as np
import json
import time

D = 0.12
LAMBDA = 0.45
ALPHA = np.pi
DX = 1.0
DT = 0.01
N = 32  # Grid size

PERTURBATION_SIZE = 1e-8

def laplacian_2d(U, dx):
    return (
        np.roll(U, 1, axis=0) + np.roll(U, -1, axis=0) +
        np.roll(U, 1, axis=1) + np.roll(U, -1, axis=1) - 4 * U
    ) / (dx**2)

def step_forward(U, dt, dx):
    lap = laplacian_2d(U, dx)
    reaction = LAMBDA * U**2 * np.sin(ALPHA * U)
    U_new = U + dt * (D * lap + reaction)
    U_new = np.maximum(U_new, 0)
    return U_new

def plant_seed(U, cx, cy, seed_type, radius=3, amplitude=1.0):
    """Plant a typed seed on the field"""
    for i in range(-radius, radius+1):
        for j in range(-radius, radius+1):
            dist = np.sqrt(i**2 + j**2)
            if dist <= radius:
                x = (cx + i) % N
                y = (cy + j) % N
                
                if seed_type == 'attractor':
                    # High U center, pulls neighbors
                    U[x, y] += amplitude * (1.0 - dist/radius)
                    
                elif seed_type == 'repulsor':
                    # Creates outward pressure gradient
                    U[x, y] += amplitude * (dist/radius)
                    
                elif seed_type == 'oscillator':
                    # Alternating high/low rings
                    ring = int(dist)
                    U[x, y] += amplitude * (0.5 + 0.5 * np.sin(np.pi * ring))
                    
                elif seed_type == 'gate':
                    # Narrow channel with high edges
                    if abs(j) <= 1:
                        U[x, y] += amplitude * 0.1  # Low channel
                    else:
                        U[x, y] += amplitude * (1.0 - dist/radius)
                    
                elif seed_type == 'source':
                    # Constant high emission point
                    U[x, y] += amplitude * 1.5
    
    U = np.maximum(U, 0)
    return U

def compute_gsm(U, cx, cy, radius=5):
    """
    Simplified Good Seed Metric computation.
    Based on the GSM reference: amplitude, effective radius, 
    concentrated mass, topology, gradient.
    """
    # Extract local region
    values = []
    for i in range(-radius, radius+1):
        for j in range(-radius, radius+1):
            x = (cx + i) % N
            y = (cy + j) % N
            values.append(U[x, y])
    
    values = np.array(values)
    
    # Amplitude: peak value
    amplitude = np.max(values)
    
    # Concentrated mass: sum in core vs total
    core_values = []
    total_values = []
    for i in range(-radius, radius+1):
        for j in range(-radius, radius+1):
            x = (cx + i) % N
            y = (cy + j) % N
            dist = np.sqrt(i**2 + j**2)
            total_values.append(U[x, y])
            if dist <= radius/2:
                core_values.append(U[x, y])
    
    core_mass = np.sum(core_values) if core_values else 0
    total_mass = np.sum(total_values) if total_values else 1
    concentration = core_mass / max(total_mass, 1e-10)
    
    # Gradient: average radial gradient
    center_val = U[cx % N, cy % N]
    gradients = []
    for i in range(-radius, radius+1):
        for j in range(-radius, radius+1):
            dist = np.sqrt(i**2 + j**2)
            if 0 < dist <= radius:
                x = (cx + i) % N
                y = (cy + j) % N
                gradients.append(abs(U[x, y] - center_val) / dist)
    
    avg_gradient = np.mean(gradients) if gradients else 0
    
    # Effective radius: where values drop below threshold
    threshold = amplitude * 0.1
    effective_r = 0
    for r in range(1, radius+1):
        ring_vals = []
        for i in range(-r, r+1):
            for j in range(-r, r+1):
                if abs(np.sqrt(i**2 + j**2) - r) < 0.5:
                    x = (cx + i) % N
                    y = (cy + j) % N
                    ring_vals.append(U[x, y])
        if ring_vals and np.mean(ring_vals) > threshold:
            effective_r = r
    
    # Classify using thresholds inspired by the GSM reference
    # M_min = πD/λ ≈ 0.84 (critical mass for nucleation)
    M_min = np.pi * D / LAMBDA
    
    score = amplitude * concentration * (1 + avg_gradient) * (effective_r / radius)
    
    if amplitude < 0.1 or total_mass < M_min * 0.3:
        classification = 'DORMANT'
    elif total_mass < M_min * 0.7:
        classification = 'FRAGILE'
    elif total_mass < M_min * 1.2:
        classification = 'EDGE_CASE'
    elif total_mass < M_min * 3.0 and concentration > 0.3:
        classification = 'AMPLIFYING'
    else:
        classification = 'RESILIENT'
    
    return {
        'amplitude': float(amplitude),
        'concentration': float(concentration),
        'avg_gradient': float(avg_gradient),
        'effective_radius': effective_r,
        'total_mass': float(total_mass),
        'M_min': float(M_min),
        'score': float(score),
        'classification': classification
    }

def compute_local_lyapunov(seed_type, amplitude, seed_seed=42):
    """Compute Lyapunov exponent for a specific seed configuration"""
    np.random.seed(seed_seed)
    
    # Blank field with seed
    U_ref = np.zeros((N, N))
    cx, cy = N // 2, N // 2
    U_ref = plant_seed(U_ref, cx, cy, seed_type, radius=3, amplitude=amplitude)
    
    # GSM before evolution
    gsm_initial = compute_gsm(U_ref, cx, cy)
    
    # Evolve to see what happens
    U_evolved = U_ref.copy()
    evolution_trace = []
    for step in range(1000):
        U_evolved = step_forward(U_evolved, DT, DX)
        if step % 100 == 0:
            center_val = float(U_evolved[cx, cy])
            total = float(np.sum(U_evolved))
            evolution_trace.append({
                'step': step,
                'center_U': center_val,
                'total_U': total
            })
    
    # GSM after evolution
    gsm_final = compute_gsm(U_evolved, cx, cy)
    
    # Lyapunov computation on the evolved state
    U_ref_lyap = U_evolved.copy()
    delta = PERTURBATION_SIZE * np.random.randn(N, N)
    U_pert = U_ref_lyap + delta
    U_pert = np.maximum(U_pert, 0)
    
    lyap_sum = 0.0
    n_renorm = 80
    steps_per = 30
    
    for _ in range(n_renorm):
        for _ in range(steps_per):
            U_ref_lyap = step_forward(U_ref_lyap, DT, DX)
            U_pert = step_forward(U_pert, DT, DX)
        
        delta = U_pert - U_ref_lyap
        delta_norm = np.linalg.norm(delta)
        
        if delta_norm == 0 or np.isnan(delta_norm) or np.isinf(delta_norm):
            break
        
        lyap_sum += np.log(delta_norm / PERTURBATION_SIZE)
        delta = delta * (PERTURBATION_SIZE / delta_norm)
        U_pert = U_ref_lyap + delta
        U_pert = np.maximum(U_pert, 0)
    
    total_time = n_renorm * steps_per * DT
    lyap_est = lyap_sum / total_time if total_time > 0 else 0.0
    
    # Classify dynamical regime
    if lyap_est > 0.01:
        regime = "CHAOTIC"
    elif lyap_est > -0.01:
        regime = "EDGE"
    else:
        regime = "ORDERED"
    
    return {
        'seed_type': seed_type,
        'amplitude': amplitude,
        'gsm_initial': gsm_initial,
        'gsm_final': gsm_final,
        'lyapunov': float(lyap_est),
        'dynamical_regime': regime,
        'evolution_trace': evolution_trace
    }

if __name__ == "__main__":
    print("=" * 70)
    print("GRIMOIRE CHAOS ANALYSIS — Step 3: GSM-Bifurcation Correspondence")
    print("=" * 70)
    print(f"Parameters: D={D}, λ={LAMBDA}, α=π, Grid={N}x{N}")
    print()
    
    seed_types = ['attractor', 'repulsor', 'oscillator', 'gate', 'source']
    amplitudes = [0.3, 0.8, 1.5, 2.5]  # From sub-critical to super-critical
    
    all_results = []
    
    for seed_type in seed_types:
        print(f"\n{'='*50}")
        print(f"SEED TYPE: {seed_type}")
        print(f"{'='*50}")
        
        for amp in amplitudes:
            print(f"\n  Amplitude={amp}...")
            result = compute_local_lyapunov(seed_type, amp)
            all_results.append(result)
            
            gsm_class = result['gsm_initial']['classification']
            regime = result['dynamical_regime']
            lyap = result['lyapunov']
            
            # Check correspondence
            expected_map = {
                'DORMANT': 'ORDERED',
                'FRAGILE': 'EDGE',
                'EDGE_CASE': 'EDGE',
                'AMPLIFYING': 'CHAOTIC',
                'RESILIENT': 'ORDERED'  # Robust attractor = stable
            }
            
            expected = expected_map.get(gsm_class, '???')
            match = "✓ MATCH" if regime == expected else "✗ MISMATCH"
            
            print(f"    GSM: {gsm_class:<12} | Lyapunov: {lyap:+.4f} | "
                  f"Regime: {regime:<8} | Expected: {expected:<8} | {match}")
    
    # Summary
    print("\n" + "=" * 70)
    print("CORRESPONDENCE SUMMARY")
    print("=" * 70)
    
    matches = 0
    total = 0
    
    for r in all_results:
        gsm_class = r['gsm_initial']['classification']
        regime = r['dynamical_regime']
        
        expected_map = {
            'DORMANT': 'ORDERED',
            'FRAGILE': 'EDGE',
            'EDGE_CASE': 'EDGE',
            'AMPLIFYING': 'CHAOTIC',
            'RESILIENT': 'ORDERED'
        }
        
        expected = expected_map.get(gsm_class, '???')
        if regime == expected:
            matches += 1
        total += 1
    
    pct = (matches / total * 100) if total > 0 else 0
    print(f"\n  Matches: {matches}/{total} ({pct:.0f}%)")
    
    if pct > 70:
        print(f"  → STRONG CORRESPONDENCE: GSM classifications predict dynamical regimes")
    elif pct > 50:
        print(f"  → MODERATE CORRESPONDENCE: Some alignment but not conclusive")
    else:
        print(f"  → WEAK CORRESPONDENCE: GSM classifications do NOT predict dynamical regimes")
    
    # Save
    with open('/home/claude/chaos_pipeline/step3_results.json', 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    print(f"\nResults saved to step3_results.json")
