# GRIMOIRE Architecture

## System overview

```
┌─────────────────────────────────────────────────┐
│                 WHITE PLAYGROUND                  │
│            Interactive 3D field lab               │
│         React + Three.js + live PDE              │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────┴───────────────────────────────┐
│            SWARM DEPLOYMENT COMPILER             │
│    Score formations before launch / execution    │
│    Input: positions + constraints                │
│    Output: class + score + recommendations       │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────┴───────────────────────────────┐
│              GOOD SEED METRIC (GSM)              │
│     Pre-simulation structural viability scorer   │
│     5 components: A, R, M, T, G                  │
│     Classes: DORMANT → FRAGILE → EDGE →          │
│              AMPLIFYING → RESILIENT              │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────┴───────────────────────────────┐
│           PDE SIMULATOR (locked equation)        │
│     ∂U/∂t = D∇²U + λU²sin(αU) + Γ(U)          │
│     D=0.12, λ=0.45, α=π                         │
│     FTCS explicit, CFL-stable                    │
│     Frontier-pull movement model                 │
└─────────────────────────────────────────────────┘
```

## Three-layer evidence model

| Layer | Description | Status |
|-------|-------------|--------|
| **A — Substrate** | Continuous PDE, 0.996 AUC, 500+ ablation sims | VALIDATED |
| **B — Principles** | 7 design principles across 8 domains | EXTRACTED |
| **C — Heuristic** | Discrete update law U(t+1) = U(t) + αS + βC − γD − δO + ρR | PROPOSED |

## The nucleation interpretation

U is a **latent nucleation potential**. You do not measure it directly.
You measure its signatures: T₉₀, front velocity, bimodality, coverage arrest.

- Gate 1 = "Will the system ignite?" = homogeneous nucleation predictor
- Gate 2 = "How fast will it cover?" = heterogeneous nucleation predictor

These are orthogonal questions. The GSM domain boundary is a correct physical finding.

## Design tool direction

Reaction-diffusion equations are an **established technique** for topology optimisation
in engineering (Yamada et al., Kyoto University, 2010–2025). The same PDE class that
validates swarm formations can generate optimal structures via level-set methods.

This means the equation doesn't just analyse — it generates.

The design tool pathway:
1. **White Playground** — interactive exploration (MVP, done)
2. **Field-to-mesh** — convert U field to 3D geometry (next)
3. **Topology optimisation** — use the PDE to generate optimal structures
4. **Export to fabrication** — STL/3MF for 3D printing
