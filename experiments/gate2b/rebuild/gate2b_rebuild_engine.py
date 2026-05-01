#!/usr/bin/env python3
"""
GRIMOIRE Gate 2B reconstruction engine.

Purpose
-------
Rebuild a runnable Gate 2B-style batch engine from the recovered artifacts in
this session. This is *not* presented as the original 2026-03-20 simulator;
it is a transparent reconstruction that:

- loads the recovered certified 37-pair library
- computes a coverage-geometry GSM from initial coordinates
- runs the recovered frontier-pull swarm/PDE simulator over each formation
- writes a pair-summary CSV, exact binomial inference JSON, and manifest JSON
- optionally runs a kinematic ablation with pure U-gradient movement

Notes
-----
- The underlying swarm/PDE mechanics are based on the recovered reconstructed
  simulator in this session, not the original manifest-locked backend.
- The coverage-geometry GSM follows the weight inversion discussed in the
  recovered Opus 4.6 handover notes:
    hull area 0.35, mean inter-agent distance 0.30, Voronoi CoV 0.20,
    LCC 0.10, lambda2 0.05.
- Connectivity features are retained as constraints / weak priors rather than
  dominant objectives.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import numpy as np

try:
    from scipy.spatial import ConvexHull
except Exception:  # pragma: no cover
    ConvexHull = None


# =========================
# Locked / default params
# =========================
GRID = 64
D = 0.12
LAM = 0.45
ALPHA = math.pi
DT = 0.05
PDE_SUBSTEPS = 3
TARGET_CY, TARGET_CX = 32, 32
TARGET_R = 7
SENSE_R = 10.0
MAX_STEPS = 100
COV_THRESHOLD = 0.9
NOISE = 0.3
COMMS_R = 6.0


# =========================
# Helper types
# =========================
@dataclass
class PairResult:
    pair_id: int
    family: str
    n: int
    lam2_A: float
    lam2_B: float
    winner: str
    method: str
    mean_t90_A: float
    mean_t90_B: float
    delta: float
    effect_size: float
    censoring_A: float
    censoring_B: float
    n_events_A: int
    n_events_B: int
    gsm_score_A: float
    gsm_score_B: float
    gsm_prediction: str
    gsm_correct: bool
    front_vel_A: float | None
    front_vel_B: float | None
    movement_mode: str
    gsm_type: str


# =========================
# Geometry / graph features
# =========================
def as_array(points: Sequence[Sequence[float]]) -> np.ndarray:
    arr = np.asarray(points, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != 2:
        raise ValueError("Formation coordinates must be an (n,2) array-like.")
    return arr


def pairwise_distances(points: np.ndarray) -> np.ndarray:
    diff = points[:, None, :] - points[None, :, :]
    return np.sqrt(np.sum(diff * diff, axis=2))


def adjacency(points: np.ndarray, comms_r: float = COMMS_R) -> np.ndarray:
    d = pairwise_distances(points)
    A = (d <= comms_r).astype(float)
    np.fill_diagonal(A, 0.0)
    return A


def connected_components(A: np.ndarray) -> List[List[int]]:
    n = A.shape[0]
    seen = [False] * n
    comps: List[List[int]] = []
    for s in range(n):
        if seen[s]:
            continue
        stack = [s]
        seen[s] = True
        comp = []
        while stack:
            u = stack.pop()
            comp.append(u)
            nbrs = np.where(A[u] > 0)[0]
            for v in nbrs:
                if not seen[v]:
                    seen[v] = True
                    stack.append(v)
        comps.append(comp)
    return comps


def lcc_fraction(A: np.ndarray) -> float:
    comps = connected_components(A)
    return max(len(c) for c in comps) / A.shape[0]


def laplacian_lambda2(A: np.ndarray) -> float:
    deg = np.diag(np.sum(A, axis=1))
    L = deg - A
    vals = np.linalg.eigvalsh(L)
    vals = np.sort(np.real(vals))
    if len(vals) < 2:
        return 0.0
    return float(max(vals[1], 0.0))


def mean_nearest_neighbor(points: np.ndarray) -> float:
    d = pairwise_distances(points)
    d = d + np.eye(len(points)) * 1e9
    return float(np.min(d, axis=1).mean())


def convex_hull_area(points: np.ndarray) -> float:
    if len(points) < 3:
        y_min, x_min = np.min(points, axis=0)
        y_max, x_max = np.max(points, axis=0)
        return float(max((y_max - y_min) * (x_max - x_min), 0.0))
    # ConvexHull expects x,y ordering in 2D area calculations.
    xy = np.column_stack([points[:, 1], points[:, 0]])
    if ConvexHull is None:
        x = xy[:, 0]
        y = xy[:, 1]
        x2 = np.roll(x, -1)
        y2 = np.roll(y, -1)
        return float(abs(np.sum(x * y2 - x2 * y)) / 2.0)
    hull = ConvexHull(xy)
    return float(hull.volume)  # volume is area in 2D


def betweenness_centrality(A: np.ndarray) -> np.ndarray:
    # Brandes algorithm for unweighted graphs.
    n = A.shape[0]
    C = np.zeros(n, dtype=float)
    neighbors = [np.where(A[i] > 0)[0].tolist() for i in range(n)]
    for s in range(n):
        S: List[int] = []
        P: List[List[int]] = [[] for _ in range(n)]
        sigma = np.zeros(n, dtype=float)
        sigma[s] = 1.0
        dist = -np.ones(n, dtype=int)
        dist[s] = 0
        Q = [s]
        q_idx = 0
        while q_idx < len(Q):
            v = Q[q_idx]
            q_idx += 1
            S.append(v)
            for w in neighbors[v]:
                if dist[w] < 0:
                    Q.append(w)
                    dist[w] = dist[v] + 1
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    P[w].append(v)
        delta = np.zeros(n, dtype=float)
        while S:
            w = S.pop()
            if sigma[w] > 0:
                coeff = (1.0 + delta[w]) / sigma[w]
                for v in P[w]:
                    delta[v] += sigma[v] * coeff
            if w != s:
                C[w] += delta[w]
    if n > 2:
        C /= 2.0
    return C


def robustness_r(A: np.ndarray) -> int:
    # Remove highest-betweenness nodes until disconnection.
    current = A.copy()
    if lcc_fraction(current) < 1.0:
        return 0
    removed = 0
    while current.shape[0] > 1 and lcc_fraction(current) == 1.0:
        bc = betweenness_centrality(current)
        idx = int(np.argmax(bc))
        current = np.delete(np.delete(current, idx, axis=0), idx, axis=1)
        removed += 1
        if current.shape[0] == 0:
            break
    return max(removed - 1, 0)


def voronoi_cov(points: np.ndarray, grid: int = GRID) -> float:
    # Raster Voronoi approximation: assign each cell to nearest point.
    yy, xx = np.mgrid[0:grid, 0:grid]
    cells = np.stack([yy.ravel(), xx.ravel()], axis=1)
    d2 = ((cells[:, None, :] - points[None, :, :]) ** 2).sum(axis=2)
    nearest = np.argmin(d2, axis=1)
    counts = np.bincount(nearest, minlength=len(points)).astype(float)
    mean = counts.mean()
    if mean <= 0:
        return 0.0
    return float(counts.std(ddof=0) / mean)


def gate1_gsm(points: np.ndarray) -> Tuple[float, Dict[str, float]]:
    A = adjacency(points)
    lam2 = laplacian_lambda2(A)
    lcc = lcc_fraction(A)
    mean_nn = mean_nearest_neighbor(points)
    hull = convex_hull_area(points)
    r = robustness_r(A)
    score = (
        0.35 * lam2
        + 0.20 * lcc
        + 0.20 * (1.0 / (mean_nn + 0.5))
        + 0.15 * (r * 0.1)
        + 0.10 * (1.0 / (hull + 1.0))
    )
    return float(score), {
        "lam2": float(lam2),
        "lcc": float(lcc),
        "mean_nn": float(mean_nn),
        "hull": float(hull),
        "robustness": float(r),
    }


def coverage_geometry_gsm(points: np.ndarray) -> Tuple[float, Dict[str, float]]:
    A = adjacency(points)
    lam2 = laplacian_lambda2(A)
    lcc = lcc_fraction(A)
    mean_nn = mean_nearest_neighbor(points)
    hull = convex_hull_area(points)
    vcv = voronoi_cov(points)
    # Coverage geometry wants larger spread and larger footprint,
    # but lower Voronoi variation (more even area partition).
    score = (
        0.35 * hull
        + 0.30 * mean_nn
        - 0.20 * vcv
        + 0.10 * lcc
        + 0.05 * lam2
    )
    return float(score), {
        "lam2": float(lam2),
        "lcc": float(lcc),
        "mean_nn": float(mean_nn),
        "hull": float(hull),
        "voronoi_cov": float(vcv),
    }


# =========================
# Simulator core
# =========================
def make_target(grid: int = GRID, cy: int = TARGET_CY, cx: int = TARGET_CX, r: int = TARGET_R) -> np.ndarray:
    yy, xx = np.mgrid[0:grid, 0:grid]
    return ((yy - cy) ** 2 + (xx - cx) ** 2) <= r * r


TARGET_MASK = make_target()
TARGET_N = int(TARGET_MASK.sum())
TARGET_COORDS = np.argwhere(TARGET_MASK)


def step_pde(U: np.ndarray) -> np.ndarray:
    lap = np.zeros_like(U)
    lap[1:-1, 1:-1] = (
        U[:-2, 1:-1] + U[2:, 1:-1] + U[1:-1, :-2] + U[1:-1, 2:] - 4 * U[1:-1, 1:-1]
    )
    react = LAM * U * U * np.sin(ALPHA * U)
    return np.maximum(0.0, U + DT * (D * lap + react))


def estimate_front_velocity(coverage_history: Sequence[float]) -> float | None:
    if not coverage_history:
        return None
    hist = np.asarray(coverage_history, dtype=float)
    radius = np.sqrt(np.maximum(hist, 0.0) * TARGET_N / math.pi)
    t = np.arange(len(radius), dtype=float)
    mask = radius > 0.5
    if mask.sum() < 4:
        return None
    x = t[mask]
    y = radius[mask]
    m, _ = np.polyfit(x, y, 1)
    return float(m)


def choose_frontier_target(ay: float, ax: float, unvisited_coords: np.ndarray) -> Tuple[float, float]:
    dists = np.sqrt((unvisited_coords[:, 0] - ay) ** 2 + (unvisited_coords[:, 1] - ax) ** 2)
    within = dists <= SENSE_R
    if within.any():
        idx = int(np.argmin(np.where(within, dists, 1e9)))
    else:
        idx = int(np.argmin(dists))
    ty, tx = unvisited_coords[idx]
    return float(ty), float(tx)


def run_one(positions: Sequence[Sequence[float]], seed: int, movement_mode: str = "frontier-pull") -> Dict[str, Any]:
    rng = np.random.RandomState(seed)
    agents = as_array(positions).astype(np.float64) + rng.uniform(-NOISE, NOISE, (len(positions), 2))
    agents = np.clip(agents, 0, GRID - 1)

    U = np.zeros((GRID, GRID), dtype=np.float64)
    for ay, ax in agents:
        U[int(ay), int(ax)] += 0.5

    visited = np.zeros((GRID, GRID), dtype=bool)
    coverage_history: List[float] = []
    t90 = MAX_STEPS

    for step in range(MAX_STEPS):
        for ay, ax in agents:
            iy = int(np.clip(ay, 1, GRID - 2))
            ix = int(np.clip(ax, 1, GRID - 2))
            visited[iy - 1 : iy + 2, ix - 1 : ix + 2] = True

        cov = float((visited & TARGET_MASK).sum()) / TARGET_N
        coverage_history.append(cov)

        if cov >= COV_THRESHOLD and t90 == MAX_STEPS:
            t90 = step
        if cov >= 0.99:
            coverage_history.extend([1.0] * (MAX_STEPS - step - 1))
            break

        for _ in range(PDE_SUBSTEPS):
            for ay, ax in agents:
                iy = int(np.clip(ay, 0, GRID - 1))
                ix = int(np.clip(ax, 0, GRID - 1))
                U[iy, ix] = min(U[iy, ix] + 0.08, 5.0)
            U = step_pde(U)

        unvisited = TARGET_MASK & ~visited
        uv_coords = np.argwhere(unvisited)
        if len(uv_coords) == 0:
            continue

        for i, (ay, ax) in enumerate(agents):
            iy = int(np.clip(ay, 1, GRID - 2))
            ix = int(np.clip(ax, 1, GRID - 2))
            gy = (U[iy + 1, ix] - U[iy - 1, ix]) / 2.0
            gx = (U[iy, ix + 1] - U[iy, ix - 1]) / 2.0

            if movement_mode == "u-gradient":
                my, mx = gy, gx
            else:
                ty, tx = choose_frontier_target(ay, ax, uv_coords)
                dy, dx = ty - ay, tx - ax
                d = math.hypot(dy, dx)
                if d > 0.3:
                    my = 0.85 * (dy / d) + 0.15 * gy
                    mx = 0.85 * (dx / d) + 0.15 * gx
                else:
                    my, mx = gy, gx

            mm = math.hypot(my, mx)
            if mm > 1e-9:
                my /= mm
                mx /= mm
                agents[i, 0] = np.clip(ay + my, 0, GRID - 1)
                agents[i, 1] = np.clip(ax + mx, 0, GRID - 1)

    return {
        "coverage_history": coverage_history,
        "t90": int(t90),
        "final_coverage": float(coverage_history[-1] if coverage_history else 0.0),
        "front_velocity": estimate_front_velocity(coverage_history),
        "censored": t90 >= MAX_STEPS,
    }


# =========================
# Stats helpers
# =========================
def cliff_delta(a: Sequence[float], b: Sequence[float]) -> float:
    gt = 0
    lt = 0
    for x in a:
        for y in b:
            if x > y:
                gt += 1
            elif x < y:
                lt += 1
    n = len(a) * len(b)
    if n == 0:
        return 0.0
    return float((gt - lt) / n)


def exact_binomial_p_value(x: int, n: int, p: float = 0.5) -> float:
    return float(sum(math.comb(n, k) * (p**k) * ((1 - p) ** (n - k)) for k in range(x, n + 1)))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_csv(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("No rows to write.")
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


# =========================
# Batch runner
# =========================
def run_pair(pair: Dict[str, Any], runs_per_formation: int, movement_mode: str, gsm_type: str) -> PairResult:
    pair_id = int(pair.get("id", pair.get("pair_id")))
    family = str(pair["family"])
    n = int(pair["n"])
    A_pts = as_array(pair["A"])
    B_pts = as_array(pair["B"])

    gate1_A, g1descA = gate1_gsm(A_pts)
    gate1_B, g1descB = gate1_gsm(B_pts)
    cov_A, cdescA = coverage_geometry_gsm(A_pts)
    cov_B, cdescB = coverage_geometry_gsm(B_pts)

    if gsm_type == "gate1":
        gsm_score_A, gsm_score_B = gate1_A, gate1_B
    else:
        gsm_score_A, gsm_score_B = cov_A, cov_B

    gsm_prediction = "A" if gsm_score_A >= gsm_score_B else "B"

    t90_A: List[int] = []
    t90_B: List[int] = []
    vel_A: List[float] = []
    vel_B: List[float] = []
    cens_A = 0
    cens_B = 0

    for r in range(runs_per_formation):
        resA = run_one(A_pts, seed=pair_id * 1000 + r, movement_mode=movement_mode)
        resB = run_one(B_pts, seed=pair_id * 1000 + 100 + r, movement_mode=movement_mode)
        t90_A.append(int(resA["t90"]))
        t90_B.append(int(resB["t90"]))
        if resA["front_velocity"] is not None:
            vel_A.append(float(resA["front_velocity"]))
        if resB["front_velocity"] is not None:
            vel_B.append(float(resB["front_velocity"]))
        cens_A += int(bool(resA["censored"]))
        cens_B += int(bool(resB["censored"]))

    mean_A = float(np.mean(t90_A))
    mean_B = float(np.mean(t90_B))
    # Faster coverage = lower T90.
    winner = "A" if mean_A <= mean_B else "B"
    gsm_correct = gsm_prediction == winner
    delta = mean_B - mean_A
    effect = abs(cliff_delta(t90_A, t90_B))

    return PairResult(
        pair_id=pair_id,
        family=family,
        n=n,
        lam2_A=float(g1descA["lam2"]),
        lam2_B=float(g1descB["lam2"]),
        winner=winner,
        method="mean_t90",
        mean_t90_A=mean_A,
        mean_t90_B=mean_B,
        delta=delta,
        effect_size=effect,
        censoring_A=float(cens_A / runs_per_formation),
        censoring_B=float(cens_B / runs_per_formation),
        n_events_A=runs_per_formation - cens_A,
        n_events_B=runs_per_formation - cens_B,
        gsm_score_A=float(gsm_score_A),
        gsm_score_B=float(gsm_score_B),
        gsm_prediction=gsm_prediction,
        gsm_correct=bool(gsm_correct),
        front_vel_A=float(np.mean(vel_A)) if vel_A else None,
        front_vel_B=float(np.mean(vel_B)) if vel_B else None,
        movement_mode=movement_mode,
        gsm_type=gsm_type,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a reconstructed GRIMOIRE Gate 2B batch engine.")
    parser.add_argument("--pairs", type=Path, default=Path("gate2_certified_pairs.json"), help="Path to certified pair library JSON.")
    parser.add_argument("--output-dir", type=Path, default=Path("gate2b_rebuild_run"), help="Directory for outputs.")
    parser.add_argument("--runs-per-formation", type=int, default=30)
    parser.add_argument("--movement-mode", choices=["frontier-pull", "u-gradient"], default="frontier-pull")
    parser.add_argument("--gsm-type", choices=["coverage", "gate1"], default="coverage")
    parser.add_argument("--limit-pairs", type=int, default=None, help="Optional smoke-test limit.")
    args = parser.parse_args()

    pairs = json.loads(args.pairs.read_text(encoding="utf-8"))
    if not isinstance(pairs, list):
        raise ValueError("Pair library must be a JSON list of pair objects.")
    if args.limit_pairs is not None:
        pairs = pairs[: args.limit_pairs]

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    results: List[PairResult] = []
    for pair in pairs:
        results.append(run_pair(pair, args.runs_per_formation, args.movement_mode, args.gsm_type))

    rows = [asdict(r) for r in results]
    csv_path = out / "gate2b_pair_summary.csv"
    write_csv(csv_path, rows)

    x = sum(1 for r in results if r.gsm_correct)
    n = len(results)
    p_val = exact_binomial_p_value(x, n, 0.5)
    inference = {
        "X": x,
        "n": n,
        "p_value": round(p_val, 8),
        "critical_value": 24 if n == 37 else None,
        "alpha": 0.05,
        "gate_passed": bool(x >= 24 if n == 37 else p_val < 0.05),
        "anti_correlation_flag": bool(x < (n / 2.0)),
        "movement_mode": "frontier" if args.movement_mode == "frontier-pull" else "u-gradient",
        "gsm_type": args.gsm_type,
        "reconstructed_engine": True,
    }
    inf_path = out / "gate2b_inference.json"
    inf_path.write_text(json.dumps(inference, indent=2), encoding="utf-8")

    effect_correct = [r.effect_size for r in results if r.gsm_correct]
    effect_incorrect = [r.effect_size for r in results if not r.gsm_correct]

    summary = {
        "metadata": {
            "protocol_version": "Gate2B-rebuild-v1",
            "reconstructed_engine": True,
            "note": "Rebuilt from recovered artifacts; not the original 2026-03-20 backend file.",
        },
        "locked_params": {
            "D": D,
            "lambda": LAM,
            "alpha_pi": True,
            "grid": f"{GRID}x{GRID}",
            "movement": args.movement_mode,
            "runs_per_pair": args.runs_per_formation,
            "censoring": f"{round(100*statistics.mean([r.censoring_A for r in results] + [r.censoring_B for r in results]), 2)}%",
        },
        "results": {
            "n_pairs": n,
            "correct": x,
            "incorrect": n - x,
            "accuracy": round(x / n, 4) if n else None,
            "p_binomial_onesided": round(p_val, 8),
            "PASSES_GATE": bool(x >= 24 if n == 37 else p_val < 0.05),
        },
        "effect_sizes": {
            "mean_effect_correct": round(float(np.mean(effect_correct)) if effect_correct else 0.0, 3),
            "mean_effect_incorrect": round(float(np.mean(effect_incorrect)) if effect_incorrect else 0.0, 3),
        },
    }
    real_path = out / "gate2b_real_result.json"
    real_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    manifest = {
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "movement_mode": "frontier" if args.movement_mode == "frontier-pull" else "u-gradient",
        "files": {
            "simulator": {
                "path": str(Path(__file__).resolve()),
                "sha256": sha256_file(Path(__file__).resolve()),
            },
            "config": {
                "path": str((Path(__file__).resolve().parent / "gate2b_rebuild_config.json").resolve()),
                "sha256": sha256_file((Path(__file__).resolve().parent / "gate2b_rebuild_config.json").resolve()) if (Path(__file__).resolve().parent / "gate2b_rebuild_config.json").exists() else None,
            },
            "pairs": {
                "path": str(args.pairs.resolve()),
                "sha256": sha256_file(args.pairs.resolve()),
            },
            "pair_summary": {
                "path": str(csv_path.resolve()),
                "sha256": sha256_file(csv_path.resolve()),
            },
        },
    }
    manifest_path = out / "gate2b_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Wrote: {csv_path}")
    print(f"Wrote: {inf_path}")
    print(f"Wrote: {real_path}")
    print(f"Wrote: {manifest_path}")
    print(f"Summary: {x}/{n} correct, p={p_val:.8f}")


if __name__ == "__main__":
    main()
