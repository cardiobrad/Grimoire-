# CHANGELOG

## v0.1.0 — 21 March 2026

Initial public release of the GRIMOIRE pipeline.

### Research results
- **Gate 1**: PDE substrate validates ignition prediction (AUC = 0.996)
- **Gate 2A**: Connectivity GSM fails on coverage task — correct domain boundary finding
- **Gate 2B**: Coverage-geometry GSM passes (29/37, p = 0.000376, 2,220 simulations)
- **Front velocity**: Clusters +26% faster than compact (nucleation ordering confirmed)
- **Zone sweep**: Distributed formations win unconditionally across all zone sizes (r=3–13)
- **Bimodality**: Preliminary multi-modal T₉₀ signal detected (dip test p≈0)

### Components
- PDE simulator (locked equation, FTCS scheme, CFL-stable)
- Good Seed Metric (5-component structural viability scorer)
- Swarm Deployment Compiler (pre-flight formation scorer with CLI)
- White Playground (interactive 3D field visualiser, React + Three.js)

### Paper
- v1.7 paper ready for submission
- Target: IEEE Transactions on Games or ICRA

### Multi-AI review history
10 AI models contributed in distinct roles:
Claude (Scribe), ChatGPT (Critic), DeepSeek (Judge), Gemini (Librarian),
Grok (Team Lead), Kimi (Mathematical Rigour), Manus (Builder),
Meta Llama (Sanity Check), GPT-4 (Hostile Reviewer), Gemini 3.1 Pro (Peer Review)

### Honest boundaries
- Framework validated for dense, spatially coupled regimes only
- Sparse/isolated agents are outside the validated domain
- Frontier-pull movement model amplifies heterogeneous advantage
- Financial markets / social networks are not valid domains for this spatial PDE
- Absolute front velocity limited by agent kinematics, not field dynamics
