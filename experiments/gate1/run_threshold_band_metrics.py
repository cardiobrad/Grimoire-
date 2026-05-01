#!/usr/bin/env python3
"""
run_threshold_band_metrics.py — Regenerate threshold-band data with all three candidate metrics.
Stores component values for ablation support.
"""
import time
import numpy as np
import pandas as pd

from config import OUT_DIR, FIELD, TOPOLOGIES
from seed_generator import generate_seed_family
from engine import embed_seeds, simulate, compute_gsm, compute_baselines, label_outcome
from metrics_v2 import adaptive_gsm, graph_gsm_core, hybrid_gsm

# Threshold masses from prior sweep (where survival rate was 5-95%)
THRESHOLD_MASSES = [0.5, 0.8, 1.0]
N_SEEDS = 20
N_NODES = 12


def main():
    print("=" * 70)
    print("  THRESHOLD-BAND METRIC COMPARISON")
    print("  3 candidates × 9 topologies × 3 masses × 20 seeds = 540 runs")
    print("=" * 70)

    t0 = time.time()
    rows = []
    total = len(TOPOLOGIES) * len(THRESHOLD_MASSES) * N_SEEDS
    count = 0

    for mass in THRESHOLD_MASSES:
        for family in TOPOLOGIES:
            configs = generate_seed_family(family, n_seeds=N_SEEDS, n_nodes=N_NODES, total_mass=mass)
            for config in configs:
                field0 = embed_seeds(config)

                # Original GSM
                gsm_orig = compute_gsm(field0)

                # Candidate A: Adaptive-field GSM
                score_a, comp_a = adaptive_gsm(field0)

                # Candidate B: Graph-native GSM
                score_b, comp_b = graph_gsm_core(config)

                # Candidate C: Hybrid GSM
                score_c, comp_c = hybrid_gsm(config, field0)

                # Baselines
                baselines = compute_baselines(config, field0)

                # Simulate
                history, _, status = simulate(field0, steps=300)
                outcome = label_outcome(history, status)

                row = {
                    "seed_id": config["seed_id"],
                    "family": family,
                    "total_mass": mass,
                    "rng_seed": config["rng_seed"],
                    "n_nodes": config["n_nodes"],
                    "n_edges": config["n_edges"],
                    # Original
                    "gsm_original": gsm_orig["score"],
                    # Candidate A
                    "gsm_adaptive": score_a,
                    "adapt_A": comp_a["A"],
                    "adapt_R": comp_a["R"],
                    "adapt_M": comp_a["M"],
                    "adapt_T": comp_a["T"],
                    "adapt_G": comp_a["G"],
                    # Candidate B
                    "gsm_graph": score_b,
                    "graph_C": comp_b["C"],
                    "graph_F": comp_b["F"],
                    "graph_D": comp_b["D_norm"],
                    "graph_S": comp_b["S_norm"],
                    # Candidate C
                    "gsm_hybrid": score_c,
                    "hybrid_C": comp_c["C"],
                    "hybrid_F": comp_c["F"],
                    "hybrid_D": comp_c["D_norm"],
                    "hybrid_S": comp_c["S_norm"],
                    "hybrid_A": comp_c["A_norm"],
                    # Baselines
                    **baselines,
                    # Outcome
                    **outcome,
                    "survived": outcome["survived"],
                }
                rows.append(row)
                count += 1

        elapsed = time.time() - t0
        survived = sum(1 for r in rows if r["total_mass"] == mass and r["survived"])
        total_at = sum(1 for r in rows if r["total_mass"] == mass)
        rate = count / elapsed if elapsed > 0 else 0
        print(f"  mass={mass:.1f} | survived {survived}/{total_at} ({100*survived/total_at:.0f}%) | "
              f"{count}/{total} | {rate:.1f} runs/s")

    df = pd.DataFrame(rows)
    path = OUT_DIR / "threshold_band_all_metrics.csv"
    df.to_csv(path, index=False)
    print(f"\n  Saved {len(df)} rows to {path}")
    print(f"  Total time: {time.time()-t0:.1f}s")
    return path


if __name__ == "__main__":
    main()
