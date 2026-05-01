#!/usr/bin/env python3
"""
run_sweep.py — Mass-sweep version of the GSM pipeline.
Varies total mass from sub-threshold to super-threshold to find the band
where topology determines survival. This is the adversarial regime.
"""
import time
import numpy as np
import pandas as pd

from config import OUT_DIR, FIELD, TOPOLOGIES
from seed_generator import generate_seed_family, GENERATORS
from engine import embed_seeds, simulate, compute_gsm, compute_baselines, label_outcome


def main():
    print("=" * 70)
    print("  GSM VALIDATION — MASS SWEEP")
    print("  Finding the threshold band where topology matters")
    print("=" * 70)

    t0 = time.time()

    # Mass values spanning sub-threshold to super-threshold
    mass_values = [0.1, 0.3, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0, 15.0]
    n_seeds_per = 20  # per topology per mass
    n_nodes = 12

    rows = []
    total = len(TOPOLOGIES) * len(mass_values) * n_seeds_per
    count = 0

    for mass in mass_values:
        for family in TOPOLOGIES:
            configs = generate_seed_family(family, n_seeds=n_seeds_per, n_nodes=n_nodes, total_mass=mass)
            for config in configs:
                field0 = embed_seeds(config)
                gsm = compute_gsm(field0)
                baselines = compute_baselines(config, field0)
                history, final_field, status = simulate(field0, steps=300)
                outcome = label_outcome(history, status)

                row = {
                    "seed_id": config["seed_id"],
                    "family": config["family"],
                    "rng_seed": config["rng_seed"],
                    "n_nodes": config["n_nodes"],
                    "n_edges": config["n_edges"],
                    "total_mass": config["total_mass"],
                    "gsm_score": gsm["score"],
                    "gsm_cls": gsm["cls"],
                    "gsm_max_u": gsm["max_u"],
                    "gsm_r_eff": gsm["r_eff"],
                    "gsm_mass": gsm["mass"],
                    "gsm_conn": gsm["conn"],
                    "gsm_grad_shape": gsm["grad_shape"],
                    **baselines,
                    **outcome,
                }
                rows.append(row)
                count += 1

        survived = sum(1 for r in rows if r["total_mass"] == mass and r["survived"])
        total_at_mass = sum(1 for r in rows if r["total_mass"] == mass)
        elapsed = time.time() - t0
        rate = count / elapsed if elapsed > 0 else 0
        eta = (total - count) / rate if rate > 0 else 0
        print(f"  mass={mass:5.1f} | survived {survived}/{total_at_mass} "
              f"({100*survived/total_at_mass:.0f}%) | {count}/{total} done | ETA {eta:.0f}s")

    # Save
    df = pd.DataFrame(rows)
    path = OUT_DIR / "results_sweep.csv"
    df.to_csv(path, index=False)
    print(f"\n  Saved {len(df)} rows to {path}")

    # Quick summary
    print("\n  Mass × Topology survival matrix:")
    pivot = df.pivot_table(
        index="family",
        columns="total_mass",
        values="survived",
        aggfunc="mean"
    ).round(2)
    print(pivot.to_string())

    # Find the threshold band
    overall = df.groupby("total_mass")["survived"].mean()
    print("\n  Overall survival rate by mass:")
    for mass, rate in overall.items():
        marker = " ◀ THRESHOLD BAND" if 0.1 < rate < 0.9 else ""
        print(f"    mass={mass:5.1f}  survival={rate:.2f}{marker}")

    # Now evaluate only the threshold band
    threshold_masses = [m for m, r in overall.items() if 0.05 < r < 0.95]
    if threshold_masses:
        print(f"\n  Evaluating GSM in threshold band: mass ∈ {threshold_masses}")
        df_band = df[df["total_mass"].isin(threshold_masses)]
        df_band.to_csv(OUT_DIR / "results_threshold_band.csv", index=False)

        # Run evaluation on the band
        from evaluate import evaluate_pipeline
        evaluate_pipeline(OUT_DIR / "results_threshold_band.csv")
    else:
        print("\n  ⚠ No threshold band found — all masses are fully survived or fully collapsed")
        print("  Try extending the mass range or adjusting field parameters")

    elapsed = time.time() - t0
    print(f"\n  Total time: {elapsed:.1f}s ({elapsed/60:.1f}min)")


if __name__ == "__main__":
    main()
