# Gate 2B — Coverage-Geometry GSM

**Result: 29/37 correct, p = 0.000376. PASSED.**

## Chain of custody

```
Simulator SHA-256: 071c45f016ed360ad167f7fb376eeb147a406580e251d2cb99031941b03d770b
Config SHA-256:    57839788818a1f97878ae931c795b9e8aaf37fa0445ac9452d7459599b6c78bb  
Pairs SHA-256:     7312bd62a1e99dd6e1fb42c3369507293fa983ec393f9bf8a4c84ca759a5a4f2
```

- 37 certified adversarial pairs
- 30 runs per formation per pair = 2,220 total simulations
- 0% censoring
- Movement mode: frontier-pull
- GSM type: coverage-geometry (hull area + mean distance + LCC + 1/λ₂ + robustness)

## Files

- `gate2b_inference.json` — final binomial test result
- `gate2b_manifest.json` — SHA-256 chain of custody
- `gate2b_pair_summary.csv` — per-pair results with effect sizes

## Statistical design

```
n = 37 pairs
Critical value c = 24
P(X ≥ 24 | n=37, p=0.5) = 0.04944  [α at c=24]
P(X ≥ 24 | n=37, p=0.7) = 0.80710  [power at p₁=0.7]
MDES p₁_min = 0.698
```

Observed: X = 29, p = 0.000376. Nearly 100× more significant than threshold.

## The 8 incorrect pairs

All had effect sizes < 0.7. These are genuine close calls where formations are structurally distinct but performatively similar. "Structurally distinct ≠ performance distinct" is information, not failure.
