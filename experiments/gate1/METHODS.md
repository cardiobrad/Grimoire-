# Methods Note — GSM Validation Pipeline

## Outcome definition (FROZEN)
A run is classified as:
- **AMPLIFIED** (survived=True): early→late gradient change > +5%
- **DECAYED** (survived=False): early→late gradient change < -5%
- **FLAT** (survived=False): gradient change between -5% and +5%
- **UNSTABLE** (survived=False): field max exceeds 50.0 before completion

Early window: first 10% of steps. Late window: last 10% of steps.
This matches the reproducibility package definition.

## Sweep range
- Mass values: 0.1, 0.3, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0, 15.0
- Threshold band: masses where overall survival rate is between 5% and 95%
- Evaluation runs only on the threshold band

## Topology vs geometry
This experiment varies topology AND spatial geometry jointly.
Each topology family has a different placement pattern (circular, linear, grid, random, clustered).
This means the test is "topology + embedding geometry", not pure graph topology alone.
This is documented honestly and should be stated in any paper.

## Fairness controls
- Total mass is held constant within each mass level
- Node count is held constant at 12
- Amplitude per node = total_mass / n_nodes (equal distribution)

## Deterministic reproducibility
- Family-to-seed mapping uses fixed integer offsets, not Python hash()
- All random operations use numpy RandomState with explicit seeds
- PYTHONHASHSEED should be set to 0 for extra safety

## Evaluation protocol
- 60/20/20 train/calibration/test split
- GSM threshold calibrated on calibration set only (max balanced accuracy)
- All reported metrics are on held-out test set only
- Constant predictors return NaN for AUC
- Adversarial pairs require same mass AND same node count AND different family

## Ablation protocol
- Each GSM component is zeroed one at a time
- AUC is recomputed on test set with ablated score
- Delta = full_GSM_AUC - ablated_AUC
- Positive delta = that component contributed to discrimination

## Gate criteria
All four must pass on held-out test:
1. GSM AUC > mass-only AUC
2. GSM AUC > node-count AUC (or node-count is NaN/constant)
3. GSM AUC > density-only AUC
4. GSM adversarial-pair correct% > mass adversarial-pair correct%
