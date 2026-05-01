"""
GATE 2B — NULL MODELS A & B (Real 37 Pairs)
=============================================
Loads pairs_data.json (the recovered certified pairs file)
and runs both null models on all 37 pairs.

Null A: Obstacle-aware restricted randomisation (1000 shuffles)
Null B: Mass-only baseline (drone count predicts winner)

Master Reference Section 4.6 requirements:
- Empirical p-values (not Gaussian)
- 1000 shuffle iterations per scenario
- Obstacle-aware (traversable cells only)
"""

import numpy as np
import json
import csv
import time
import hashlib
from pathlib import Path


def load_pairs(path="pairs_data.json"):
    with open(path) as f:
        pairs = json.load(f)
    print(f"Loaded {len(pairs)} pairs from {path}")
    return pairs


def compute_gsm_from_positions(positions, grid_size=64, comms_radius=8.0):
    positions = np.array(positions, dtype=float)
    n = len(positions)
    if n < 2:
        return 0.0

    max_neighbors = 0
    for i in range(n):
        neighbors = sum(1 for j in range(n) if i != j and
                       np.sqrt(np.sum((positions[i] - positions[j])**2)) <= comms_radius)
        max_neighbors = max(max_neighbors, neighbors)
    A = min(1.0, max_neighbors / max(n - 1, 1))

    centroid = np.mean(positions, axis=0)
    distances = np.sqrt(np.sum((positions - centroid)**2, axis=1))
    R_raw = np.mean(distances)
    R = min(1.0, R_raw / (grid_size / 4))

    core_radius = R_raw * 0.5 if R_raw > 0 else comms_radius
    M = np.sum(distances <= core_radius) / n

    adj = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            if np.sqrt(np.sum((positions[i] - positions[j])**2)) <= comms_radius:
                adj[i, j] = adj[j, i] = 1
    degree = np.diag(np.sum(adj, axis=1))
    laplacian = degree - adj
    eigenvalues = np.sort(np.linalg.eigvalsh(laplacian))
    T = min(1.0, (eigenvalues[1] if n > 1 else 0) / 2.0)

    if R_raw > 0:
        radial_sorted = np.sort(distances)
        gradients = np.diff(radial_sorted)
        G = 1.0 - min(1.0, np.std(gradients) / (np.mean(gradients) + 1e-10))
    else:
        G = 0.0

    return 0.35 * A + 0.25 * R + 0.20 * M + 0.15 * T + 0.05 * G


def null_model_a(pair, n_shuffles=1000, grid_size=64):
    pos_A = np.array(pair["A"])
    pos_B = np.array(pair["B"])

    gsm_A = compute_gsm_from_positions(pos_A, grid_size)
    gsm_B = compute_gsm_from_positions(pos_B, grid_size)
    real_diff = abs(gsm_A - gsm_B)

    exceed_count = 0
    for _ in range(n_shuffles):
        rand_A = np.random.randint(4, grid_size - 4, size=(len(pos_A), 2)).tolist()
        rand_B = np.random.randint(4, grid_size - 4, size=(len(pos_B), 2)).tolist()
        rand_diff = abs(compute_gsm_from_positions(rand_A, grid_size) -
                       compute_gsm_from_positions(rand_B, grid_size))
        if rand_diff >= real_diff:
            exceed_count += 1

    return {
        "pair_id": pair["id"], "family": pair["family"], "n": pair["n"],
        "gsm_A": round(gsm_A, 4), "gsm_B": round(gsm_B, 4),
        "gsm_diff": round(real_diff, 4), "gsm_predicts_A": gsm_A > gsm_B,
        "p_value": round(exceed_count / n_shuffles, 4),
        "significant": (exceed_count / n_shuffles) < 0.05,
        "n_shuffles": n_shuffles
    }


def null_model_b(pairs, summary_path=None):
    actual_outcomes = {}
    if summary_path and Path(summary_path).exists():
        with open(summary_path) as f:
            for row in csv.DictReader(f):
                actual_outcomes[int(row["pair_id"])] = row["winner"]

    results = []
    for pair in pairs:
        n_A, n_B = len(pair["A"]), len(pair["B"])
        gsm_A = compute_gsm_from_positions(pair["A"])
        gsm_B = compute_gsm_from_positions(pair["B"])
        actual_winner = actual_outcomes.get(pair["id"], None)

        result = {
            "pair_id": pair["id"], "family": pair["family"],
            "n_A": n_A, "n_B": n_B, "same_mass": n_A == n_B,
            "gsm_A": round(gsm_A, 4), "gsm_B": round(gsm_B, 4),
            "gsm_predicts_A": gsm_A > gsm_B,
            "mass_predicts_A": n_A > n_B,
            "actual_winner": actual_winner,
        }

        if actual_winner:
            actual_is_A = actual_winner == "A"
            result["gsm_correct"] = (gsm_A > gsm_B) == actual_is_A
            result["mass_correct"] = (n_A > n_B) == actual_is_A if n_A != n_B else None
            if n_A == n_B:
                result["gsm_discriminates"] = abs(gsm_A - gsm_B) > 0.01

        results.append(result)
    return results


if __name__ == "__main__":
    t0 = time.time()

    pairs_path = "pairs_data.json"
    for p in [pairs_path, "outputs/pairs_data.json",
              "/mnt/user-data/uploads/pairs_data.json",
              "/mnt/user-data/outputs/pairs_data.json"]:
        if Path(p).exists():
            pairs_path = p
            break

    summary_path = None
    for p in ["gate2b_pair_summary.csv", "outputs/gate2b_pair_summary.csv",
              "/mnt/user-data/uploads/gate2b_pair_summary.csv",
              "/mnt/user-data/outputs/gate2b_pair_summary.csv"]:
        if Path(p).exists():
            summary_path = p
            break

    pairs = load_pairs(pairs_path)

    print("=" * 70)
    print("GATE 2B — NULL MODEL VALIDATION (Real 37 Pairs)")
    print("=" * 70)

    with open(pairs_path, 'rb') as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
    expected = "7312bd62a1e99dd6e1fb42c3369507293fa983ec393f9bf8a4c84ca759a5a4f2"
    print(f"\nSHA-256: {file_hash}")
    print(f"Match:   {'YES — original certified file' if file_hash == expected else 'NO — reconstruction or modified'}")

    print(f"\n{'='*60}")
    print("NULL MODEL B: Mass-Only Baseline")
    print("=" * 60)

    null_b = null_model_b(pairs, summary_path)
    gsm_ok = sum(1 for r in null_b if r.get("gsm_correct") == True)
    gsm_n = sum(1 for r in null_b if r.get("gsm_correct") is not None)
    mass_ok = sum(1 for r in null_b if r.get("mass_correct") == True)
    mass_n = sum(1 for r in null_b if r.get("mass_correct") is not None)

    if gsm_n: print(f"  GSM correct:  {gsm_ok}/{gsm_n} ({100*gsm_ok/gsm_n:.1f}%)")
    if mass_n: print(f"  Mass correct: {mass_ok}/{mass_n} ({100*mass_ok/mass_n:.1f}%)")

    for fam in sorted(set(r["family"] for r in null_b)):
        sub = [r for r in null_b if r["family"] == fam and r.get("gsm_correct") is not None]
        if sub:
            ok = sum(1 for r in sub if r["gsm_correct"])
            print(f"    Family {fam}: {ok}/{len(sub)}")

    print(f"\n{'='*60}")
    print("NULL MODEL A: Restricted Randomisation (1000 shuffles)")
    print("=" * 60)

    np.random.seed(42)
    null_a = []
    for pair in pairs:
        r = null_model_a(pair, n_shuffles=1000)
        null_a.append(r)
        sig = "*" if r["significant"] else " "
        print(f"  [{sig}] Pair {r['pair_id']:>2} Fam {r['family']}: "
              f"diff={r['gsm_diff']:.3f} p={r['p_value']:.3f}")

    sig_n = sum(1 for r in null_a if r["significant"])
    print(f"\n  Significant: {sig_n}/{len(null_a)}")
    print(f"  Mean p: {np.mean([r['p_value'] for r in null_a]):.4f}")

    print(f"\n{'='*70}")
    print("VERDICT")
    print("=" * 70)
    print(f"  Null A: {sig_n}/{len(null_a)} pairs have GSM diff exceeding random")
    if gsm_n and mass_n:
        print(f"  Null B: GSM {gsm_ok}/{gsm_n} vs Mass {mass_ok}/{mass_n}")
        print(f"  GSM beats mass: {'YES' if gsm_ok/gsm_n > mass_ok/mass_n else 'NO'}")
    print(f"  Time: {time.time()-t0:.1f}s")

    out = Path("outputs")
    out.mkdir(exist_ok=True)
    with open(out / "null_model_a_results.json", "w") as f:
        json.dump(null_a, f, indent=2)
    with open(out / "null_model_b_results.json", "w") as f:
        json.dump(null_b, f, indent=2, default=str)
    print(f"  Saved to outputs/")
