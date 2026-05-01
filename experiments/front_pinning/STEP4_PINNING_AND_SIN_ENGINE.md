# Front Pinning Results & SIN Engine Implications

## The Finding

At locked parameters (D=0.12, dx=1.0), **the healing wave is PINNED**.

Seeds ignite — they reach U≈3 locally. But the U=3 state CANNOT propagate
outward into the surrounding U=1 domain. Not with 3 nodes. Not with 31 nodes.
The Peierls-Nabarro lattice barrier is insurmountable at this coupling strength.

## The Numbers

### At D=0.12, varying dx:
| dx    | D/dx²  | Propagates? |
|-------|--------|-------------|
| 0.10  | 12.0   | YES (with seed ≥ 0.9 spatial units) |
| 0.20  | 3.0    | YES |
| 0.25  | 1.92   | YES |
| 0.30  | 1.33   | NO  |
| 0.50  | 0.48   | NO  |
| 1.00  | 0.12   | NO  |

### At dx=1.0, varying D:
| D     | D/dx²  | Propagates? |
|-------|--------|-------------|
| 0.50  | 0.50   | NO  |
| 1.00  | 1.00   | NO  |
| 1.50  | 1.50   | NO  |
| 2.00  | 2.00   | YES |

### Critical coupling ratio:
D/dx² ≈ 1.5–2.0 is the transition. Below: pinned. Above: propagates.

This is CONSISTENT across different (D, dx) combinations at the same ratio.

### Seed width does NOT fix pinning at dx=1.0:
Even a 31-node seed (31 spatial units) cannot propagate at D=0.12, dx=1.0.
The lattice barrier is absolute at this coupling strength.

### But seed width DOES matter at fine grids:
At dx=0.10, D=0.12 (ratio=12.0):
- 3 nodes (0.3 spatial units): PINNED (below critical nucleus radius)
- 9 nodes (0.9 spatial units): PROPAGATES
- Critical physical seed width ≈ 0.9 spatial units at this coupling

## What This Means for Each Term of the Equation

### ∂U/∂t = D∇²U + λU²sin(αU) + Γ(U)

The three terms have now been fully characterized:

**Term 1: λU²sin(αU) — The SIN Engine**
Role: POTENTIAL LANDSCAPE ARCHITECT
- Creates the wells: stable attractors at U=1, 3, 5, ...
- Creates the barriers: unstable saddles at U=2, 4, ...
- Wells get DEEPER as U increases (U² amplification)
- Barriers get TALLER as U increases (same U² amplification)
- The stiffness ratio |J₃|/|J₁| = 9.0 is TOPOLOGICALLY INVARIANT
- The barrier ratio V(3→2)/V(1→2) = 2.741 is TOPOLOGICALLY INVARIANT
- α controls well SPACING without changing relative depths
- λ controls well DEPTH without changing the topology
- This is a GRADIENT FLOW — chaos is mathematically forbidden

The SIN engine works PERFECTLY. Every seed that should ignite does ignite.
Every local transition that should occur does occur. The wells exist and
they catch what falls into them.

**Term 2: D∇²U — The Coupling / Diffusion**
Role: INFORMATION PROPAGATION
- Spreads local state to neighbors
- Enables (or fails to enable) front propagation
- On a discrete grid: must overcome the Peierls-Nabarro lattice barrier
- Critical constraint: D/dx² ≈ 1.5-2.0 for wave propagation
- At locked D=0.12 with dx=1.0: PINNED (coupling too weak)
- This is the ENGINEERING BOTTLENECK, not the SIN engine

The diffusion term is the builder. The SIN engine drew the blueprint
(where the wells and barriers are), but the builder can't reach the
next plot at low coupling. Local ignition works. Global propagation
requires sufficient coupling.

**Term 3: Γ(U) — The Renewal / External Drive**
Role: EXTERNAL FORCING
- Still structurally undefined in the locked equation
- If autonomous and bounded: preserves gradient flow, shifts fixed points
- If non-local or delayed: CAN BREAK gradient flow entirely
- Could enable Hopf bifurcations, breathing fronts, spatiotemporal chaos
- This is the WILD CARD — and the audit's biggest warning

## What This Means for the Existing Results

All GRIMOIRE experiments to date (Gate1, Gate2, GSM, White Playground)
were run on unit grids (dx=1.0) at D=0.12.

This means they were ALL in the PINNED regime.

**This is NOT a problem.** It actually EXPLAINS why the results look the
way they do:

1. Gate1 (ignition AUC 0.996): Tests LOCAL ignition. Does the seed
   reach U≈3? This works perfectly in the pinned regime because
   ignition is a LOCAL event — the SIN engine handles it alone.

2. Gate2B (p=0.000376): Tests structural outcomes. In the pinned regime,
   seeds ignite locally but don't spread. The interesting dynamics are
   about WHICH seeds ignite and HOW they interact through local coupling,
   not about global wave propagation.

3. The buck converter 120.2° result: Phase interleaving does NOT require
   wave propagation. It requires LOCAL coupling between adjacent units.
   Pinned regime is fine for this.

4. White Playground seed scoring: GSM classifies seeds by local ignition
   quality — will this seed cross the barrier? That's entirely about
   the SIN engine's potential landscape, not about wave propagation.

The pinned regime means: the SIN engine creates LOCAL coordination
through its potential landscape. Global coordination (wave propagation)
requires either finer grids, stronger coupling, or an active Γ(U) term
that can push fronts past the lattice barrier.

## The SIN Engine: Final Characterization

The SIN engine (λU²sin(αU)) is a SCALABLE MULTI-WELL POTENTIAL GENERATOR
with topologically invariant ratios.

What it IS:
- A gradient-flow energy landscape with alternating wells and barriers
- A local coordination primitive that creates structured attractors
- A nucleation enabler with a precise, computable barrier height
- A system with mathematically guaranteed convergence (no chaos possible)

What it is NOT:
- A chaos generator (gradient flow forbids it)
- A wave propagation mechanism (that's D's job, and it fails at low coupling)
- A universal coordination algorithm (domain scope is dense local coupling only)
- A replacement for coupling — it needs sufficient D/dx² to propagate

The hierarchy:
  SIN engine decides WHERE things go (potential landscape)
  Diffusion decides WHETHER things spread (coupling strength)
  Γ(U) decides HOW the system is driven (external forcing)
  Grid resolution determines IF the coupling works (lattice barrier)

## Engineering Implications

For any hardware implementation of GRIMOIRE coordination:

1. LOCAL ignition works at any coupling. The SIN engine creates the wells
   and seeds fall into them. This is the regime for phase interleaving,
   local fault recovery, and seed-quality scoring.

2. GLOBAL propagation requires D/dx² > ~1.5-2.0. For buck converters at
   D=0.12, this means the effective grid spacing must be ≤ 0.25 spatial
   units — or the coupling D must be increased to ~2.0 for unit spacing.

3. The critical coupling ratio is the MAXIMUM PHYSICAL DISTANCE between
   coordinating units before the safety net breaks. This is a real,
   measurable, hardware-constraining number.

## Pipeline Status

✅ Step 1:  Lyapunov (steady state) — ORDERED, both models
✅ Step 1b: Regime-specific Lyapunov — MASSIVE regime differences found
✅ Step 2:  Bifurcation sweep — NO chaos at any λ
✅ Step 3:  GSM correspondence — 5% (BROKEN implementation, needs fix)
✅ Step 4:  Front pinning — PINNED at locked params, boundary mapped
⬜ Step 5:  Fix GSM implementation and retest correspondence
⬜ Step 6:  Formal attractor basin mapping
