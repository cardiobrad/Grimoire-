#!/usr/bin/env python3
"""
run_pipeline.py — One command runs the entire GSM validation pipeline.

Usage:
    python run_pipeline.py

This will:
  1. Generate 450 graph-based seed configurations (9 topologies × 50 seeds)
  2. Embed each into a 64×64 field
  3. Compute GSM score and all baseline features on the initial field
  4. Simulate each to 500 steps
  5. Label outcomes (COLLAPSED / PERSISTED / AMPLIFIED / UNSTABLE)
  6. Save all results to outputs/results.csv
  7. Run full evaluation: ROC-AUC, adversarial pairs, ablation, verdict
"""
import time
import numpy as np
import pandas as pd

from config import OUT_DIR, FIELD, TOPOLOGIES
from seed_generator import generate_all_families
from engine import embed_seeds, simulate, compute_gsm, compute_baselines, label_outcome
from evaluate import evaluate_pipeline


def main():
    print("=" * 70)
    print("  GSM VALIDATION PIPELINE")
    print("  Good Seed Metric vs Naive Baselines")
    print("=" * 70)
    print(f"  Grid: {FIELD['N']}×{FIELD['N']}")
    print(f"  Steps per run: {FIELD['steps']}")
    print(f"  Topologies: {', '.join(TOPOLOGIES)}")
    print("=" * 70)

    t0 = time.time()

    # 1. Generate seed families
    print("\n[1/4] Generating seed families...")
    configs = generate_all_families()
    print(f"  Total configs: {len(configs)}")

    # 2-5. Run pipeline
    print("\n[2/4] Running simulations + scoring...")
    rows = []
    for i, config in enumerate(configs):
        # Embed
        field0 = embed_seeds(config)

        # Score initial field
        gsm = compute_gsm(field0)
        baselines = compute_baselines(config, field0)

        # Simulate
        history, final_field, status = simulate(field0)

        # Label outcome
        outcome = label_outcome(history, status)

        # Assemble row
        row = {
            "seed_id": config["seed_id"],
            "family": config["family"],
            "rng_seed": config["rng_seed"],
            "n_nodes": config["n_nodes"],
            "n_edges": config["n_edges"],
            "total_mass": config["total_mass"],
            # GSM
            "gsm_score": gsm["score"],
            "gsm_cls": gsm["cls"],
            "gsm_max_u": gsm["max_u"],
            "gsm_r_eff": gsm["r_eff"],
            "gsm_mass": gsm["mass"],
            "gsm_conn": gsm["conn"],
            "gsm_grad_shape": gsm["grad_shape"],
            # Baselines
            **baselines,
            # Outcome
            **outcome,
        }
        rows.append(row)

        if (i + 1) % 50 == 0 or i == len(configs) - 1:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(configs) - i - 1) / rate if rate > 0 else 0
            print(f"  [{i+1}/{len(configs)}] {config['family']:>20} | "
                  f"GSM={gsm['score']:.2f} {gsm['cls']:<12} | "
                  f"{outcome['outcome']:<12} | "
                  f"{rate:.1f} runs/s | ETA {eta:.0f}s")

    # 6. Save results
    print("\n[3/4] Saving results...")
    df = pd.DataFrame(rows)
    results_path = OUT_DIR / "results.csv"
    df.to_csv(results_path, index=False)
    print(f"  Saved {len(df)} rows to {results_path}")

    # 7. Evaluate
    print("\n[4/4] Running evaluation...")
    summary = evaluate_pipeline(results_path)

    elapsed = time.time() - t0
    print(f"\n  Total time: {elapsed:.1f}s ({elapsed/60:.1f}min)")
    print(f"  Results: {results_path}")
    print(f"  Evaluation: {OUT_DIR / 'evaluation_summary.csv'}")


if __name__ == "__main__":
    main()
