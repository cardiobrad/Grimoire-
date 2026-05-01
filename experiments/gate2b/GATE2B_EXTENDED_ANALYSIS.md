# Gate 2B — Extended Statistical Analysis
## 15 tests on the 37-pair dataset

### Core Result
29/37 correct, p = 0.000376
Clopper-Pearson exact 95% CI: [0.618, 0.902]
Cohen's h = 0.604 (medium-large effect)

---

### What Holds Up

**Test 1 — Permutation test:** p = 0.0004 (10,000 permutations). Confirms binomial.

**Test 2 — Effect size separation:** Correct pairs have significantly larger
effects than incorrect (Mann-Whitney p = 0.025). Mean correct = 0.673, mean
wrong = 0.249. GSM gets the easy calls right and struggles with close calls.

**Test 5 — Fiedler value (λ₂) predicts coverage:** Lower λ₂ (more distributed)
wins coverage in 28/37 pairs (76%), Wilcoxon p = 0.0002. This is the strongest
individual predictor and confirms the heterogeneous nucleation interpretation:
distributed formations cover faster because they create more nucleation sites.

**Test 6 — Bootstrap CI:** [0.649, 0.919], excludes 0.5.

**Test 7 — Performance deltas ≠ 0:** Wilcoxon p = 0.0001. The formations
genuinely perform differently — this isn't noise.

**Test 8 — Leave-two-families-out jackknife:** 20/21 combinations pass at p < 0.05.
Only B+E is marginal (p = 0.054). Signal is distributed.

**Test 11 — Confidence thresholding:** Accuracy rises monotonically with GSM gap.
At gap ≥ 0.50: 85% accuracy. At gap ≥ 0.70: 90%. When GSM is confident, it's
usually right.

---

### What's Weak

**Test 3 — GSM confidence vs correctness:** NOT significant (p = 0.079).
GSM gap is trending in the right direction but doesn't reach significance.
This means GSM's confidence in its prediction is not a reliable indicator
of whether it will be correct.

**Test 4 — Drone count effect:** No trend (r = 0.078, p = 0.646).
GSM accuracy does not improve with more drones. This is actually fine —
it means the metric isn't just rewarding bigger formations.

**Test 8 — B+E exclusion:** p = 0.054. Borderline. Families B and E together
contribute enough correct pairs that removing both weakens the signal to
marginal. Not a failure, but worth noting.

**Test 12 — Bimodality:** The delta distribution is heavily non-normal
(Shapiro p < 0.0001) with two outlier pairs at deltas of -12.5 and -13.8
(both Family B, large drone counts). These are genuine large effects but
they pull the mean delta substantially.

**Test 13 — Family F CI:** [0.13, 0.87]. This CI includes 0.5, meaning
we cannot reject chance performance for Family F alone. Consistent with
the Family F diagnosis: the metric fails specifically on this family.

**Test 15 — Calibration:** Spearman ρ = 0.240, p = 0.153. The trend is
right (higher confidence → higher accuracy) but not significant. GSM is
not well-calibrated as a probability estimator.

---

### The λ₂ Finding

This may be the most important result from the extended analysis.

The Fiedler value (algebraic connectivity, λ₂) of the formation's
communication graph predicts the coverage winner 76% of the time
(28/37, p = 0.0002). Lower λ₂ = more distributed = faster coverage.

Winner formations have mean λ₂ = 0.298.
Loser formations have mean λ₂ = 0.926.

This is a single-number predictor that nearly matches the full GSM's
performance (76% vs 78%). It suggests that the primary discriminating
factor is spatial distribution, not the multi-component GSM score.

Implication: the coverage-geometry GSM's 5-component weighting may be
over-engineered. A simpler metric based primarily on spatial spread
(λ₂ or mean inter-agent distance) might perform equally well with
better calibration.

---

### Honest Summary

The 29/37 result is robust across every reasonable statistical test.
It is not driven by any single family, any specific drone count, or
outlier effects. The signal is real.

The weaknesses are: Family F (3/6), marginal B+E jackknife (p=0.054),
uncalibrated confidence, and a non-normal delta distribution with
two extreme outliers.

The strongest single finding: λ₂ predicts coverage at p = 0.0002,
confirming the theoretical prediction that distributed formations
achieve faster coverage through heterogeneous nucleation.
