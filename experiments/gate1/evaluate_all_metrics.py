#!/usr/bin/env python3
"""
evaluate_all_metrics.py — Compare three candidate metrics under frozen protocol.
- 5 random split seeds for stability
- Calibration on cal set, metrics on held-out test
- Ablations via component zeroing
- Adversarial matching (same mass + nodes, different family)
- Gate 1 pass/fail per candidate
"""
import numpy as np
import pandas as pd
from config import OUT_DIR

SPLIT_SEEDS = [42, 123, 456, 789, 101112]

BASELINES = {
    "Mass only": "bl_mass",
    "Node count": "bl_node_count",
    "Density": "bl_density",
    "Edge count": "bl_edge_count",
    "Mean degree": "bl_mean_degree",
}

CANDIDATES = {
    "Original GSM": {
        "col": "gsm_original",
        "components": [],  # no stored components for ablation
    },
    "Adaptive GSM": {
        "col": "gsm_adaptive",
        "components": ["adapt_A", "adapt_R", "adapt_M", "adapt_T", "adapt_G"],
        "weights": [0.35, 0.25, 0.20, 0.15, 0.05],
    },
    "Graph GSM": {
        "col": "gsm_graph",
        "components": ["graph_C", "graph_F", "graph_D", "graph_S"],
        "weights": [0.25, 0.25, 0.25, 0.25],
        "transform": [1, -1, -1, -1],  # C is direct, F/D/S are 1-x
    },
    "Hybrid GSM": {
        "col": "gsm_hybrid",
        "components": ["hybrid_C", "hybrid_F", "hybrid_D", "hybrid_S", "hybrid_A"],
        "weights": [0.2, 0.2, 0.2, 0.2, 0.2],
        "transform": [1, -1, -1, -1, 1],  # C and A direct, F/D/S are 1-x
    },
}


def _auc(y_true, y_score):
    pos = sum(y_true); neg = len(y_true) - pos
    if pos == 0 or neg == 0: return float("nan")
    if len(set(round(s, 10) for s in y_score)) <= 1: return float("nan")
    tp = auc = 0.0
    for _, label in sorted(zip(y_score, y_true), reverse=True):
        if label: tp += 1
        else: auc += tp
    return auc / (pos * neg)


def _best_thresh(yt, ys):
    best_t = best_ba = 0
    for t in np.linspace(min(ys) - 0.01, max(ys) + 0.01, 300):
        pred = [1 if s >= t else 0 for s in ys]
        tp = sum(1 for p, y in zip(pred, yt) if p == 1 and y == 1)
        tn = sum(1 for p, y in zip(pred, yt) if p == 0 and y == 0)
        p, n = sum(yt), len(yt) - sum(yt)
        ba = ((tp / p if p else 0) + (tn / n if n else 0)) / 2
        if ba > best_ba: best_ba, best_t = ba, t
    return best_t, best_ba


def _cls_metrics(yt, yp):
    tp = sum(1 for t, p in zip(yt, yp) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(yt, yp) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(yt, yp) if t == 1 and p == 0)
    tn = sum(1 for t, p in zip(yt, yp) if t == 0 and p == 0)
    pr = tp / (tp + fp) if tp + fp else 0
    re = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * pr * re / (pr + re) if pr + re else 0
    p, n = tp + fn, tn + fp
    ba = ((tp / p if p else 0) + (tn / n if n else 0)) / 2
    return {"prec": pr, "rec": re, "f1": f1, "ba": ba}


def _ablated_score(row, candidate_info, drop_idx):
    """Recompute score with one component zeroed."""
    comps = candidate_info["components"]
    weights = candidate_info["weights"]
    transforms = candidate_info.get("transform", [1] * len(comps))
    total = 0.0
    for i, (col, w, tr) in enumerate(zip(comps, weights, transforms)):
        if i == drop_idx:
            continue
        val = row.get(col, 0)
        if tr == -1:
            val = 1 - val
        total += w * val
    return total


def evaluate_one_split(df, candidate_name, cand_info, split_seed):
    """Evaluate one candidate on one split. Returns result dict."""
    rng = np.random.RandomState(split_seed)
    idx = rng.permutation(len(df))
    a, b = int(len(df) * 0.6), int(len(df) * 0.8)
    train = df.iloc[idx[:a]]
    cal = df.iloc[idx[a:b]]
    test = df.iloc[idx[b:]]

    score_col = cand_info["col"]
    yt = test["y"].tolist()
    ys = test[score_col].fillna(0).tolist()

    # AUC
    cand_auc = _auc(yt, ys)

    # Baseline AUCs
    bl_aucs = {}
    for bl_name, bl_col in BASELINES.items():
        if bl_col in test.columns:
            bl_aucs[bl_name] = _auc(yt, test[bl_col].fillna(0).tolist())

    # Calibrate threshold
    cal_yt = cal["y"].tolist()
    cal_ys = cal[score_col].fillna(0).tolist()
    thresh, _ = _best_thresh(cal_yt, cal_ys)

    # Classification on test
    pred = [1 if s >= thresh else 0 for s in ys]
    cls = _cls_metrics(yt, pred)

    # Adversarial pairs
    test2 = test.copy()
    test2["mk"] = test2["bl_mass"].round(2).astype(str) + "_" + test2["bl_node_count"].astype(str)
    af = gw = mw = 0
    for _, grp in test2.groupby("mk"):
        surv = grp[grp["y"] == 1]
        dead = grp[grp["y"] == 0]
        if len(surv) == 0 or len(dead) == 0:
            continue
        for _, sr in surv.iterrows():
            for _, dr in dead.iterrows():
                if sr["family"] == dr["family"]:
                    continue
                af += 1
                if sr[score_col] > dr[score_col]:
                    gw += 1
                if sr["bl_mass"] > dr["bl_mass"]:
                    mw += 1

    adv_pct = 100 * gw / af if af > 0 else 0
    mass_adv_pct = 100 * mw / af if af > 0 else 0

    # Ablations
    ablation_deltas = {}
    if cand_info.get("components") and cand_info.get("weights"):
        for drop_i, comp_name in enumerate(cand_info["components"]):
            abl_scores = [_ablated_score(row, cand_info, drop_i) for _, row in test.iterrows()]
            abl_auc = _auc(yt, abl_scores)
            delta = cand_auc - abl_auc if not (np.isnan(cand_auc) or np.isnan(abl_auc)) else float("nan")
            ablation_deltas[comp_name] = delta

    # Gate checks
    beats_mass = cand_auc > bl_aucs.get("Mass only", float("nan")) if not np.isnan(cand_auc) else False
    beats_nodes = np.isnan(bl_aucs.get("Node count", float("nan"))) or (not np.isnan(cand_auc) and cand_auc > bl_aucs.get("Node count", 0))
    beats_density = cand_auc > bl_aucs.get("Density", float("nan")) if not np.isnan(cand_auc) else False
    adv_wins = af > 0 and gw > mw

    passes = sum([beats_mass, beats_nodes, beats_density, adv_wins])

    return {
        "candidate": candidate_name,
        "split_seed": split_seed,
        "auc": cand_auc,
        "bl_mass_auc": bl_aucs.get("Mass only", float("nan")),
        "bl_density_auc": bl_aucs.get("Density", float("nan")),
        "thresh": thresh,
        "ba": cls["ba"],
        "prec": cls["prec"],
        "rec": cls["rec"],
        "f1": cls["f1"],
        "adv_pairs": af,
        "adv_correct_pct": adv_pct,
        "mass_adv_pct": mass_adv_pct,
        "passes": passes,
        "gate": "PASS" if passes == 4 else "PARTIAL" if passes >= 3 else "FAIL",
        **{f"abl_{k}": v for k, v in ablation_deltas.items()},
    }


def main():
    path = OUT_DIR / "threshold_band_all_metrics.csv"
    df = pd.read_csv(path)
    df["y"] = df["survived"].astype(int)

    ns = df["y"].sum()
    n = len(df)
    print("=" * 70)
    print("  MULTI-METRIC EVALUATION (5 splits × 4 candidates)")
    print("=" * 70)
    print(f"  Total runs: {n}  Survived: {ns} ({100*ns/n:.1f}%)")

    if ns == 0 or ns == n:
        print("  ⚠ No outcome variance. Cannot evaluate.")
        return

    all_results = []

    for cand_name, cand_info in CANDIDATES.items():
        for seed in SPLIT_SEEDS:
            result = evaluate_one_split(df, cand_name, cand_info, seed)
            all_results.append(result)

    results_df = pd.DataFrame(all_results)

    # Summary per candidate (mean ± std across splits)
    print("\n" + "=" * 70)
    print("  RESULTS SUMMARY (mean ± std across 5 splits)")
    print("=" * 70)

    summary_rows = []
    for cand_name in CANDIDATES:
        subset = results_df[results_df["candidate"] == cand_name]
        row = {"candidate": cand_name}
        for col in ["auc", "ba", "prec", "rec", "f1", "adv_correct_pct", "mass_adv_pct", "passes"]:
            vals = subset[col].dropna()
            row[f"{col}_mean"] = round(vals.mean(), 4) if len(vals) > 0 else float("nan")
            row[f"{col}_std"] = round(vals.std(), 4) if len(vals) > 0 else float("nan")

        gate_counts = subset["gate"].value_counts()
        row["gate_PASS"] = int(gate_counts.get("PASS", 0))
        row["gate_PARTIAL"] = int(gate_counts.get("PARTIAL", 0))
        row["gate_FAIL"] = int(gate_counts.get("FAIL", 0))

        summary_rows.append(row)

        print(f"\n  {cand_name}:")
        print(f"    AUC:          {row['auc_mean']:.4f} ± {row['auc_std']:.4f}")
        print(f"    Balanced Acc: {row['ba_mean']:.4f} ± {row['ba_std']:.4f}")
        print(f"    F1:           {row['f1_mean']:.4f} ± {row['f1_std']:.4f}")
        print(f"    Precision:    {row['prec_mean']:.4f} ± {row['prec_std']:.4f}")
        print(f"    Recall:       {row['rec_mean']:.4f} ± {row['rec_std']:.4f}")
        print(f"    Adv correct:  {row['adv_correct_pct_mean']:.1f}% ± {row['adv_correct_pct_std']:.1f}%")
        print(f"    Mass adv:     {row['mass_adv_pct_mean']:.1f}% ± {row['mass_adv_pct_std']:.1f}%")
        print(f"    Gate: PASS={row['gate_PASS']} PARTIAL={row['gate_PARTIAL']} FAIL={row['gate_FAIL']}")

    # Overall verdict
    print("\n" + "=" * 70)
    print("  FINAL VERDICT")
    print("=" * 70)

    for row in summary_rows:
        cand = row["candidate"]
        if row["gate_PASS"] >= 3:
            print(f"  ✓✓✓ {cand}: CLEARS GATE 1 ({row['gate_PASS']}/5 splits pass)")
        elif row["gate_PASS"] + row["gate_PARTIAL"] >= 3:
            print(f"  ⚠   {cand}: MOSTLY PASSES ({row['gate_PASS']} pass, {row['gate_PARTIAL']} partial)")
        else:
            print(f"  ✗   {cand}: DOES NOT CLEAR ({row['gate_PASS']} pass, {row['gate_FAIL']} fail)")

    # Find best
    best = max(summary_rows, key=lambda r: (r["gate_PASS"], r.get("auc_mean", 0)))
    print(f"\n  Best candidate: {best['candidate']} (AUC={best['auc_mean']:.4f}, {best['gate_PASS']}/5 gate passes)")
    print("=" * 70)

    # Save
    pd.DataFrame(summary_rows).to_csv(OUT_DIR / "metric_comparison_summary.csv", index=False)
    results_df.to_csv(OUT_DIR / "metric_comparison_all_splits.csv", index=False)
    print(f"\n  Saved to {OUT_DIR}/metric_comparison_*.csv")


if __name__ == "__main__":
    main()
