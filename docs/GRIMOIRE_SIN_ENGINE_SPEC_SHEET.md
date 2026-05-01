# GRIMOIRE SIN Engine — Technical Specification Sheet
### A Nonlinear Coordination Primitive with Proven Properties
**Author:** Bradley Grant Edwards | **DOI:** 10.5281/zenodo.19152177 | **Repo:** github.com/cardiobrad/Grimoire-

---

## What It Is

A reaction-diffusion update law with a sine-modulated nonlinear term that creates a structured multi-well potential landscape for decentralised coordination.

**The equation:**

∂U/∂t = D∇²U + λU²sin(πU) + Γ(U)

**Locked parameters:** D=0.12, λ=0.45, α=π

The sine term generates alternating stable and unstable fixed points. Stable wells at U=1 (standby) and U=3 (active). Unstable barrier at U=2 (threshold). Nodes transition between states through local coupling only — no central controller, no global state.

---

## Proven Properties

Every number below is computationally verified. Sources cited by test name and file.

### Fixed-Point Architecture

| Fixed Point | Jacobian f'(U) | Stability | Physical Role |
|:-----------:|:--------------:|:---------:|:-------------:|
| U = 0 | 0 | Marginal | Extinction |
| U = 1 | −1.414 | Stable | Standby / Parking |
| U = 2 | +5.655 | Unstable | Threshold / Barrier |
| U = 3 | −12.723 | Stable | Active / Coordinated |

*Source: Analytical derivation, confirmed by independent mathematical audit (Reaction-Diffusion System Audit, 10 pages, 30+ citations)*

### Exact Effective Potential V(U)

| State | V(U) | Classification |
|:-----:|:-----:|:--------------:|
| U = 1 | −0.114 | Metastable basin |
| U = 2 | +0.544 | Barrier peak |
| U = 3 | −1.260 | Global attractor |

The system is a **gradient flow**: the energy functional monotonically decreases over time. Sustained chaos is mathematically forbidden in the unperturbed (Γ=0) system.

*Source: Exact integration of f(U), verified in audit Section 3*

### Topological Invariants (α-independent)

| Ratio | Value | Meaning |
|:-----:|:-----:|:-------:|
| Stiffness |J₃|/|J₁| | 9.0 | Deep attractor is 9× stronger than standby |
| Barrier asymmetry V(3→2)/V(1→2) | 2.741 | Escaping active state costs 2.7× more than leaving standby |

These ratios hold for ALL values of α. They are structural properties of the U²sin(αU) form, not parameter-specific accidents.

*Source: Seraphel's kill test — 20/20 λ values, 20/20 α values, 45/54 grid combinations. File: seraphel_kill_test.csv*

### Propagation Threshold (Discrete Grid)

| Quantity | Value | Meaning |
|:--------:|:-----:|:-------:|
| Critical coupling D/dx² | 1.5 – 2.0 | Below: local ignition only. Above: fronts propagate. |
| At locked D=0.12, dx=1.0 | 0.12 | Pinned regime — coordination stays local |

**Replication:** 196 tests, 2 solvers (Euler + Heun/RK2), 2 boundary conditions (periodic + Neumann). Zero disagreements between any solver/BC combination.

*Source: step4_replication.py, step4_replication_results.csv*

### Fixed-Point Arithmetic Stability (Q8.8)

| Test | Result |
|:----:|:------:|
| Parking drift (100,000 steps, zero demand) | 0 LSBs — perfectly stable |
| Barrier threshold | Deterministic: U ≤ 2.012 decays, U ≥ 2.031 crosses |
| Limit cycles at parking state | None detected |

The parking state at U=1.0 sits at an exact zero of both the reaction term (sin(π)=0) and the diffusion term (uniform neighbors). No sub-LSB rounding force exists. The quantisation dead zone IS the stability mechanism.

*Source: Shadow zone tests 2 and 4, integer arithmetic verified*

### Gate 2B: Structural Prediction

| Metric | Value |
|:------:|:-----:|
| GSM prediction accuracy | 29/37 (78.4%) |
| Binomial p-value | 0.000376 |
| Clopper-Pearson 95% CI | [0.618, 0.902] |
| Cohen's h effect size | 0.604 (medium-large) |
| Jackknife (leave-one-family-out) | 7/7 families pass |
| Leave-two-families-out | 20/21 pass (B+E marginal at p=0.054) |
| Fiedler value (λ₂) predicts coverage winner | 28/37 (76%), p=0.0002 |

*Source: gate2b_pair_summary.csv, gate2b_robustness_addendum.json, extended analysis (15 statistical tests)*

---

## What It Is NOT

This specification describes a **mathematical coordination primitive**, not a validated product.

**Not proven:** superiority over DRR, WRR, or credit-based schedulers.
**Not proven:** hardware performance on FPGA or ASIC.
**Not proven:** applicability to any specific domain (batteries, grids, chips) without domain-specific validation.
**Not proven:** behaviour under non-trivial Γ(U) (the external drive term).

Current status per independent audit (Gemma 4, April 2026):
**"Mathematically interesting behaviour, transitioning toward hardware-plausible heuristic."**

---

## The Novel Property

**No existing scheduler has a nonlinear multi-well potential governing state transitions.**

Round-robin, DRR, credit-based, age-based, and priority arbiters all use linear or threshold logic. The SIN engine creates three things none of them have:

1. **A metastable standby state (U=1)** that is faster to activate than cold-start (U=0). Nodes maintain "potential energy" while consuming zero arbitration resources.

2. **A nucleation barrier (U=2)** that naturally filters transient noise. Only sustained demand crosses the threshold. No explicit filtering logic required.

3. **Local-only coupling** with a computable maximum coordination range (D/dx² ≈ 1.5–2.0). No global state, no central controller, no broadcast overhead.

---

## Reproducibility

All results are reproducible from the public repository.

| Resource | Location |
|:--------:|:--------:|
| Equation & parameters | github.com/cardiobrad/Grimoire-/README.md |
| Gate 2B data | github.com/cardiobrad/Grimoire-/experiments/gate2b/ |
| Pinning replication | step4_replication.py (196 tests) |
| Kill test | seraphel_kill_test.py (94 tests) |
| Mathematical audit | Reaction-Diffusion System Audit (10 pages) |
| Zenodo DOI | 10.5281/zenodo.19152177 |

---

## Next Milestone

**FPGA embodiment test (FairField arbiter).** 8-node ring on Lattice iCE40, Q8.8 fixed-point, head-to-head against Deficit Round-Robin. Verilog written. Awaiting hardware. Budget: £40.

**Pass criterion:** Jain's Fairness Index matches or exceeds DRR under uniform and hotspot workloads.
**Kill criterion:** Fixed-point limit cycles, delay-induced oscillation, or fairness collapse below round-robin baseline.

---

*Bradley Grant Edwards — Liverpool, UK — April 2026*
*Independent researcher. Former dry liner. Building coordination primitives from first principles.*
