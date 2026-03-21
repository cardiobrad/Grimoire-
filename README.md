# GRIMOIRE

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.19152177.svg)](https://doi.org/10.5281/zenodo.19152177)

**Spatial orchestration through nucleation physics.**

A validated framework for predicting and optimising multi-agent coordination using reaction-diffusion-renewal dynamics. The equation predicts which formations will amplify and which will fragment — before you run the simulation.

```
∂U/∂t = D∇²U + λU²sin(αU) + Γ(U),  U ≥ 0
```

---

## Results

| Gate | Question | Result |
|------|----------|--------|
| **Gate 1** — Ignition prediction | Will this formation nucleate? | **0.996 AUC** across 9 topology families |
| **Gate 2A** — Connectivity GSM on coverage | Will connected formations cover fastest? | **13/37 — killed** (correct domain boundary) |
| **Gate 2B** — Coverage GSM on coverage | Will distributed formations cover fastest? | **29/37, p = 0.000376** |
| **Front velocity** | Do distributed formations propagate faster? | **Clusters +26% over compact** |
| **Zone sweep** | Is there a crossover radius? | **No — distributed wins unconditionally** |

Gate 2A's failure is informative: ignition and coverage are orthogonal questions requiring different predictors. This is the homogeneous vs heterogeneous nucleation distinction.

---

## What's in this repo

### `src/simulator/` — PDE + swarm simulator
The locked reaction-diffusion-renewal equation with frontier-pull movement model. 64×64 grid, CFL-stable FTCS scheme. This is the engine that produced all results.

### `src/gsm/` — Good Seed Metric
Pre-simulation structural viability scorer. Evaluates amplitude, core radius, concentrated mass, topology, and gradient. Classifies formations as DORMANT / FRAGILE / EDGE CASE / AMPLIFYING / RESILIENT.

### `src/compiler/` — Swarm Deployment Compiler
Scores drone/robot formations before launch. Input: positions + comms radius + battery + obstacles. Output: score, class, heatmap, "why" report, launch recommendation.

### `src/playground/` — White Playground
Interactive 3D visualisation of the PDE field evolving in real time. See the nucleation barrier at U*=2, watch formations amplify or fragment, compare compact vs distributed seeds.

### `experiments/` — Reproducible results
All four experiments with raw data, analysis scripts, and publication-ready figures.

### `docs/` — Paper and specifications
Paper v1.7, swarm architecture brief, calibration notes.

---

## Quick start

```bash
# Run the swarm deployment compiler
cd src/compiler
pip install numpy scipy
python swarm_compiler.py --input examples/search_rescue.json

# Run the front velocity experiment
cd experiments/front_velocity
python front_velocity.py

# Run the zone sweep
python zone_sweep.py
```

---

## The equation

```
∂U/∂t = D∇²U + λU²sin(αU) + Γ(U)

D = 0.12    (diffusion)
λ = 0.45    (reaction rate)
α = π       (oscillation frequency)
```

**Fixed points:**

| U | f'(U) | Stability | Meaning |
|---|-------|-----------|---------|
| 0 | 0 | Marginal | No coordination |
| 1 | −λπ ≈ −1.41 | **Stable** | Partial coordination |
| **2** | **+4λπ ≈ +5.65** | **Unstable** | **Nucleation barrier** |
| 3 | −9λπ ≈ −12.72 | **Stable (deep)** | Full coordination |

The unstable saddle at U*=2 creates a first-order nucleation barrier. Formations must exceed the critical mass M_min = πD/λ ≈ 0.84 to cross it.

---

## Key insight

**Gate 1** asks: "Will the system ignite?" → thermodynamic question → homogeneous nucleation predictor.

**Gate 2** asks: "How fast will it cover space?" → kinetic question → heterogeneous nucleation predictor.

Compact formations create one strong nucleus. Distributed formations create many weak nuclei. For coverage speed, distributed always wins — exactly as classical nucleation theory predicts.

---

## Honest boundaries

- This framework is validated for **dense, spatially coupled regimes only**
- Sparse or isolated-agent scenarios are outside the validated domain
- The frontier-pull movement model amplifies the heterogeneous advantage — this is acknowledged, not hidden
- Absolute front velocity (0.34 cells/step) is below the PDE prediction (0.82) — agent kinematics are the rate-limiting step
- Cross-domain analogies (biofilms, thermal ignition) are structural, not exact isomorphisms
- Financial markets and social networks are **not valid domains** for this spatial PDE

A swarm is not a field until density makes it one.

---

## Origin

Developed by **Bradley Grant Edwards**, Liverpool, 2026.

The equation descends from the Unified Multiversal Dynamics (UMD) framework, refined through Brian Roemmele's cooperation/defection dynamics, and validated through 11 weeks of multi-AI collaborative research using Claude, ChatGPT, DeepSeek, Gemini, Grok, Kimi, and Manus in distinct roles.

The nucleation interpretation came while clearing strawberry plants in the garden. The best physics happens outside.

---

## Citation

```
Edwards, B.G. (2026). GRIMOIRE: A Topology-Aware Coordination Heuristic 
for Dense Tactical Regimes — From Spatial Substrate to Game Engine. 
Zenodo. https://doi.org/10.5281/zenodo.19152177
```

Prior work:
```
Edwards, B.G. (2025). Unified Multiversal Dynamics (UMD) v1.0. 
Zenodo. https://doi.org/10.5281/zenodo.17743734

Edwards, B.G. (2025). UMD and Bioenergetic Applications v2.0. 
Zenodo. https://doi.org/10.5281/zenodo.17743948
```

---

Seeds beat noise. Topology beats headcount. Don't fly every formation — score the seed first.
