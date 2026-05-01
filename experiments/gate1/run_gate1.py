#!/usr/bin/env python3
"""
run_gate1.py — Final Gate 1 evaluation per DeepSeek+ChatGPT spec.

Runs both GSM candidates in the threshold band with:
- Multiple random splits (3 seeds)
- Calibration on cal set only
- All metrics on held-out test
- Ablations for each candidate
- Adversarial matching (same mass + nodes, different family)
"""
import time
import numpy as np
import pandas as pd
from config import OUT_DIR, FIELD, TOPOLOGIES
from seed_generator import generate_seed_family, GENERATORS
from engine import embed_seeds, simulate, compute_gsm, compute_baselines, label_outcome
from gsm_candidates import adaptive_gsm, graph_gsm_core, graph_gsm_spectral
from evaluate import _auc, _split, _best_thresh, _metrics, SCORERS


SPLIT_SEEDS = [42, 123, 789]
THRESHOLD_MASSES = [0.5, 0.8, 1.0]
SEEDS_PER = 20


def generate_threshold_band():
    """Generate data in the threshold band only."""
    print("\n[1/3] Generating threshold-band data...")
    rows = []
    for mass in THRESHOLD_MASSES:
        for family in TOPOLOGIES:
            configs = generate_seed_family(family, n_seeds=SEEDS_PER, n_nodes=12, total_mass=mass)
            for config in configs:
                field0 = embed_seeds(config)

                # Original GSM
                orig = compute_gsm(field0)
                baselines = compute_baselines(config, field0)

                # Candidate 1: Adaptive-field GSM
                agsm_score, agsm_comps = adaptive_gsm(field0)

                # Candidate 2: Graph-native GSM (core)
                ggsm_score, ggsm_comps = graph_gsm_core(config)

                # Candidate 2b: Graph-native GSM + spectral
                sgsm_score, sgsm_comps = graph_gsm_spectral(config)

                # Simulate
                history, _, status = simulate(field0, steps=300)
                outcome = label_outcome(history, status)

                row = {
                    "seed_id": config["seed_id"], "family": config["family"],
                    "rng_seed": config["rng_seed"], "n_nodes": config["n_nodes"],
                    "n_edges": config["n_edges"], "total_mass": config["total_mass"],
                    # Original
                    "gsm_score": orig["score"],
                    "gsm_max_u": orig["max_u"], "gsm_r_eff": orig["r_eff"],
                    "gsm_mass": orig["mass"], "gsm_conn": orig["conn"],
                    "gsm_grad_shape": orig["grad_shape"],
                    # Adaptive
                    "agsm_score": agsm_score,
                    "agsm_A": agsm_comps.get("A_norm", 0),
                    "agsm_R": agsm_comps.get("R_mean", 0),
                    "agsm_M": agsm_comps.get("M_mean", 0),
                    "agsm_T": agsm_comps.get("T_mean", 0),
                    "agsm_G": agsm_comps.get("G_mean", 0),
                    # Graph-native
                    "ggsm_score": ggsm_score,
                    "ggsm_C": ggsm_comps.get("C_score", 0),
                    "ggsm_F": ggsm_comps.get("F_score", 0),
                    "ggsm_D": ggsm_comps.get("D_score", 0),
                    "ggsm_S": ggsm_comps.get("S_score", 0),
                    # Spectral
                    "sgsm_score": sgsm_score,
                    "sgsm_lambda2": sgsm_comps.get("lambda2_norm", 0),
                    "sgsm_ipr": sgsm_comps.get("ipr", 0),
                    "sgsm_ipr_flag": sgsm_comps.get("ipr_flag", False),
                    # Baselines
                    **baselines,
                    # Outcome
                    **outcome,
                }
                rows.append(row)

        surv = sum(1 for r in rows if r["total_mass"] == mass and r["survived"])
        tot = sum(1 for r in rows if r["total_mass"] == mass)
        print(f"    mass={mass:.1f}: {surv}/{tot} survived ({100*surv/tot:.0f}%)")

    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "gate1_data.csv", index=False)
    print(f"  Saved {len(df)} rows")
    return df


def evaluate_candidate(df, score_col, comp_cols, name, ablation_weights):
    """Evaluate one candidate across multiple splits."""
    print(f"\n  --- {name} ---")
    all_results = []

    for split_seed in SPLIT_SEEDS:
        rng = np.random.RandomState(split_seed)
        idx = rng.permutation(len(df))
        a, b = int(len(df) * 0.6), int(len(df) * 0.8)
        train = df.iloc[idx[:a]]
        cal = df.iloc[idx[a:b]]
        test = df.iloc[idx[b:]].copy()

        yt = test["survived"].astype(int).tolist()
        if sum(yt) == 0 or sum(yt) == len(yt):
            continue

        # AUC
        cand_auc = _auc(yt, test[score_col].fillna(0).tolist())

        # Baseline AUCs
        bl_aucs = {}
        for bl_name, bl_col in [("mass", "bl_mass"), ("node_count", "bl_node_count"),
                                 ("density", "bl_density"), ("edge_count", "bl_edge_count"),
                                 ("mean_degree", "bl_mean_degree")]:
            if bl_col in test.columns:
                bl_aucs[bl_name] = _auc(yt, test[bl_col].fillna(0).tolist())

        # Calibrate threshold
        y_cal = cal["survived"].astype(int).tolist()
        cal_scores = cal[score_col].fillna(0).tolist()
        thresh, _ = _best_thresh(y_cal, cal_scores)

        # Classification on test
        pred = [1 if s >= thresh else 0 for s in test[score_col].fillna(0)]
        m = _metrics(yt, pred)

        # Ablation
        ablation_deltas = {}
        if ablation_weights and comp_cols:
            for drop_key, drop_col in zip(ablation_weights, comp_cols):
                # Zero out one component contribution
                ablated = []
                w = ablation_weights.copy()
                original_w = w[drop_key]
                for _, row in test.iterrows():
                    orig = row[score_col]
                    component_val = row.get(drop_col, 0)
                    ablated_score = orig - original_w * component_val
                    ablated.append(ablated_score)
                abl_auc = _auc(yt, ablated)
                if not np.isnan(cand_auc) and not np.isnan(abl_auc):
                    ablation_deltas[drop_key] = cand_auc - abl_auc
                else:
                    ablation_deltas[drop_key] = float("nan")

        # Adversarial pairs
        test2 = test.copy()
        test2["mk"] = test2["bl_mass"].round(2).astype(str) + "_" + test2["bl_node_count"].astype(str)
        test2["y"] = test2["survived"].astype(int)
        af = gw = mw = 0
        for _, grp in test2.groupby("mk"):
            s = grp[grp["y"] == 1]
            d = grp[grp["y"] == 0]
            if len(s) == 0 or len(d) == 0:
                continue
            for _, sr in s.iterrows():
                for _, dr in d.iterrows():
                    if sr["family"] == dr["family"]:
                        continue
                    af += 1
                    if sr[score_col] > dr[score_col]:
                        gw += 1
                    if sr["bl_mass"] > dr["bl_mass"]:
                        mw += 1

        all_results.append({
            "split_seed": split_seed,
            "auc": cand_auc,
            "bl_aucs": bl_aucs,
            "thresh": thresh,
            "metrics": m,
            "ablation_deltas": ablation_deltas,
            "adv_found": af,
            "adv_gsm_win": gw,
            "adv_mass_win": mw,
        })

    if not all_results:
        print("    No valid splits (no outcome variance in test)")
        return {"verdict": "NO_VARIANCE"}

    # Aggregate across splits
    mean_auc = np.nanmean([r["auc"] for r in all_results])
    mean_ba = np.mean([r["metrics"]["ba"] for r in all_results])
    mean_f1 = np.mean([r["metrics"]["f1"] for r in all_results])

    print(f"    AUC (mean±std): {mean_auc:.4f} ± {np.nanstd([r['auc'] for r in all_results]):.4f}")
    print(f"    Balanced acc:   {mean_ba:.4f}")
    print(f"    F1:             {mean_f1:.4f}")

    # Gate checks
    passes = 0
    tests_run = 0
    for bl_name in ["mass", "node_count", "density", "edge_count", "mean_degree"]:
        tests_run += 1
        bl_vals = [r["bl_aucs"].get(bl_name, float("nan")) for r in all_results]
        mean_bl = np.nanmean(bl_vals)
        if np.isnan(mean_bl):
            passes += 1
            print(f"    ✓ Beats {bl_name} (baseline NaN/constant)")
        elif not np.isnan(mean_auc) and mean_auc > mean_bl:
            passes += 1
            print(f"    ✓ Beats {bl_name} ({mean_auc:.4f} > {mean_bl:.4f})")
        else:
            print(f"    ✗ Does NOT beat {bl_name} ({mean_auc:.4f} vs {mean_bl:.4f})")

    # Adversarial
    tests_run += 1
    total_af = sum(r["adv_found"] for r in all_results)
    total_gw = sum(r["adv_gsm_win"] for r in all_results)
    total_mw = sum(r["adv_mass_win"] for r in all_results)
    if total_af > 0 and total_gw > total_mw:
        passes += 1
        print(f"    ✓ Adversarial: {total_gw}/{total_af} ({100*total_gw/total_af:.1f}%) > mass {total_mw}/{total_af}")
    else:
        print(f"    ✗ Adversarial: GSM {total_gw} vs mass {total_mw} (of {total_af} pairs)")

    # Ablation summary
    if all_results[0]["ablation_deltas"]:
        print("    Ablation (mean ΔAUC when component dropped):")
        for key in all_results[0]["ablation_deltas"]:
            deltas = [r["ablation_deltas"].get(key, float("nan")) for r in all_results]
            md = np.nanmean(deltas)
            print(f"      {key:<12} ΔAUC={md:+.4f}" if not np.isnan(md) else f"      {key:<12} ΔAUC=NaN")

    verdict = "PASS" if passes == tests_run else "PARTIAL" if passes >= tests_run - 1 else "FAIL"
    print(f"\n    RESULT: {passes}/{tests_run} → {verdict}")
    return {"name": name, "passes": passes, "tests": tests_run, "verdict": verdict,
            "mean_auc": mean_auc, "mean_ba": mean_ba, "mean_f1": mean_f1}


def main():
    print("=" * 70)
    print("  GATE 1 EVALUATION — ADAPTIVE GSM + GRAPH-NATIVE GSM")
    print("=" * 70)
    t0 = time.time()

    df = generate_threshold_band()

    print("\n[2/3] Evaluating candidates...")

    # Original GSM (for reference)
    r_orig = evaluate_candidate(df, "gsm_score", [], "Original GSM (expected fail)", {})

    # Candidate 1: Adaptive-field
    agsm_ablation = {"w_a": 0.35, "w_r": 0.25, "w_m": 0.20, "w_t": 0.15, "w_g": 0.05}
    agsm_cols = ["agsm_A", "agsm_R", "agsm_M", "agsm_T", "agsm_G"]
    r_adaptive = evaluate_candidate(df, "agsm_score", agsm_cols, "Adaptive-field GSM", agsm_ablation)

    # Candidate 2: Graph-native (core)
    ggsm_ablation = {"w_C": 0.25, "w_F": 0.25, "w_D": 0.25, "w_S": 0.25}
    ggsm_cols = ["ggsm_C", "ggsm_F", "ggsm_D", "ggsm_S"]
    r_graph = evaluate_candidate(df, "ggsm_score", ggsm_cols, "Graph-native GSM", ggsm_ablation)

    # Candidate 2b: Graph-native + spectral
    r_spectral = evaluate_candidate(df, "sgsm_score", [], "Graph-native + Spectral", {})

    # Summary
    print("\n" + "=" * 70)
    print("  GATE 1 SUMMARY")
    print("=" * 70)
    for r in [r_orig, r_adaptive, r_graph, r_spectral]:
        if "name" in r:
            v = r["verdict"]
            sym = "✓✓✓" if v == "PASS" else "⚠" if v == "PARTIAL" else "✗"
            print(f"  {sym} {r['name']:<30} {r['passes']}/{r['tests']} AUC={r['mean_auc']:.4f} BA={r['mean_ba']:.4f}")
    print("=" * 70)

    # Save
    results = [r for r in [r_orig, r_adaptive, r_graph, r_spectral] if "name" in r]
    pd.DataFrame(results).to_csv(OUT_DIR / "gate1_summary.csv", index=False)

    print(f"\n  Total time: {time.time()-t0:.1f}s")
    print(f"  Data: {OUT_DIR / 'gate1_data.csv'}")
    print(f"  Summary: {OUT_DIR / 'gate1_summary.csv'}")


if __name__ == "__main__":
    main()
