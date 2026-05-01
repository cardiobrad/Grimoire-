# Gate 2B Rebuild Engine

This bundle reconstructs a runnable Gate 2B-style engine from the recovered artifacts in this session.

## Files

- `gate2b_rebuild_engine.py` — batch runner / engine
- `gate2b_rebuild_config.json` — locked reconstruction config

## What it does

- loads `gate2_certified_pairs.json`
- computes a coverage-geometry GSM from pre-deployment coordinates
- runs the reconstructed swarm/PDE simulator for each formation
- writes:
  - `gate2b_pair_summary.csv`
  - `gate2b_inference.json`
  - `gate2b_real_result.json`
  - `gate2b_manifest.json`

## Important honesty note

This is a **reconstruction** from recovered artifacts and notes.
It is **not claimed to be the exact original 2026-03-20 simulator source**.
Use it as a transparent rebuild and forward testbed.

## Example usage

```bash
python gate2b_rebuild_engine.py \
  --pairs gate2_certified_pairs.json \
  --output-dir gate2b_rebuild_run \
  --runs-per-formation 30 \
  --movement-mode frontier-pull \
  --gsm-type coverage
```

## Quick smoke test

```bash
python gate2b_rebuild_engine.py \
  --pairs gate2_certified_pairs.json \
  --output-dir smoke_test \
  --runs-per-formation 3 \
  --limit-pairs 2
```

## Optional ablation

To test the kinematic ablation:

```bash
python gate2b_rebuild_engine.py \
  --pairs gate2_certified_pairs.json \
  --output-dir gate2b_ugrad \
  --movement-mode u-gradient \
  --gsm-type coverage
```
