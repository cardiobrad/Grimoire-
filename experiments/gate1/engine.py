"""
engine.py — Embedding, simulation, GSM scoring, baseline scoring, outcome labeling.
All computation. No plotting. No interpretation.
"""
import numpy as np
from config import FIELD, GSM, OUTCOME

N = FIELD["N"]


# ═══════════════════════════════════════════════════
# 1. Embed graph seeds into a 2D field
# ═══════════════════════════════════════════════════

def embed_seeds(config, radius=4.0):
    """Convert a seed config (nodes with positions and amplitudes) into a 64x64 field."""
    field = np.zeros((N, N), dtype=np.float64)
    yy, xx = np.mgrid[0:N, 0:N]
    for x, y, amp in config["nodes"]:
        r2 = (xx - x) ** 2 + (yy - y) ** 2
        field += amp * np.exp(-r2 / (2.0 * radius ** 2))
    return field


# ═══════════════════════════════════════════════════
# 2. PDE simulator
# ═══════════════════════════════════════════════════

def _laplacian(U):
    return (
        np.roll(U, 1, axis=0) + np.roll(U, -1, axis=0) +
        np.roll(U, 1, axis=1) + np.roll(U, -1, axis=1) - 4.0 * U
    )


def simulate(field, steps=None, dt=None, D=None, lam=None, alpha=None):
    """Run the reduced RDR equation. Returns trajectory metrics."""
    steps = steps or FIELD["steps"]
    dt = dt or FIELD["dt"]
    D = D or FIELD["D"]
    lam = lam or FIELD["lam"]
    alpha = alpha or FIELD["alpha"]

    U = field.copy()
    history = []

    for t in range(steps):
        mean_u = float(np.mean(U))
        max_u = float(np.max(U))
        min_u = float(np.min(U))

        gx = (np.roll(U, -1, axis=1) - np.roll(U, 1, axis=1)) / 2.0
        gy = (np.roll(U, -1, axis=0) - np.roll(U, 1, axis=0)) / 2.0
        mean_grad = float(np.mean(gx ** 2 + gy ** 2))

        # Above-threshold area
        above = U >= GSM["A_c"]
        area_frac = float(np.sum(above)) / (N * N)

        history.append({
            "step": t,
            "mean_u": mean_u,
            "max_u": max_u,
            "min_u": min_u,
            "mean_grad": mean_grad,
            "area_frac": area_frac,
        })

        # Check for collapse
        if max_u > 50.0:
            return history, U, "UNSTABLE"

        # PDE update
        lap = _laplacian(U)
        renewal = lam * U * U * np.sin(alpha * U)
        U = U + dt * (D * lap + renewal)
        if FIELD["positivity_clip"]:
            U = np.clip(U, 0.0, None)

    return history, U, "COMPLETE"


# ═══════════════════════════════════════════════════
# 3. Good Seed Metric (exact reference implementation)
# ═══════════════════════════════════════════════════

def compute_gsm(field):
    """Compute the Good Seed Metric on a field state.
    Returns dict with score, classification, and all components."""
    A_c = GSM["A_c"]

    max_u = float(np.max(field))
    if max_u < 1e-12:
        return {"score": 0.0, "cls": "DORMANT", "max_u": 0.0, "r_eff": 0.0,
                "mass": 0.0, "conn": 0.0, "grad_shape": 0.0}

    # Above-threshold mask
    mask = field >= A_c
    area = int(np.sum(mask))
    mass = float(np.sum(field[mask])) if area > 0 else 0.0

    if area == 0:
        return {"score": 0.0, "cls": "DORMANT", "max_u": max_u, "r_eff": 0.0,
                "mass": 0.0, "conn": 0.0, "grad_shape": 0.0}

    r_eff = float(np.sqrt(area / np.pi))

    # Connectivity: largest connected component fraction
    visited = np.zeros(N * N, dtype=bool)
    mask_flat = mask.ravel()
    largest = 0
    for start in range(N * N):
        if not mask_flat[start] or visited[start]:
            continue
        queue = [start]
        visited[start] = True
        size = 0
        while queue:
            cur = queue.pop()
            size += 1
            cr, cc = divmod(cur, N)
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = cr + dr, cc + dc
                if 0 <= nr < N and 0 <= nc < N:
                    ni = nr * N + nc
                    if mask_flat[ni] and not visited[ni]:
                        visited[ni] = True
                        queue.append(ni)
        if size > largest:
            largest = size
    conn = largest / area if area > 0 else 0.0

    # Gradient shape diagnostic
    gx = (np.roll(field, -1, axis=1) - np.roll(field, 1, axis=1)) / 2.0
    gy = (np.roll(field, -1, axis=0) - np.roll(field, 1, axis=0)) / 2.0
    grad_mag = np.sqrt(gx ** 2 + gy ** 2)
    grad_shape = float(np.mean(grad_mag[mask])) if area > 0 else 0.0

    # Composite score
    score = (
        GSM["w_a"] * (max_u / A_c) +
        GSM["w_r"] * (r_eff / GSM["R_c"]) +
        GSM["w_m"] * (mass / GSM["M_c"]) +
        GSM["w_t"] * conn +
        GSM["w_g"] * min(grad_shape / 0.5, 1.0)
    )

    # Classification
    if max_u < A_c:
        cls = "DORMANT"
    elif r_eff < GSM["R_c"]:
        cls = "FRAGILE"
    elif score < 1.0:
        cls = "EDGE_CASE"
    elif conn > 0.8:
        cls = "AMPLIFYING"
    else:
        cls = "RESILIENT"

    return {
        "score": round(score, 4),
        "cls": cls,
        "max_u": round(max_u, 4),
        "r_eff": round(r_eff, 2),
        "mass": round(mass, 2),
        "conn": round(conn, 4),
        "grad_shape": round(grad_shape, 4),
    }


# ═══════════════════════════════════════════════════
# 4. Baseline scorers
# ═══════════════════════════════════════════════════

def compute_baselines(config, field):
    """Compute naive baseline features for comparison with GSM."""
    n_nodes = config["n_nodes"]
    n_edges = config["n_edges"]
    total_mass = config["total_mass"]

    # Density = edges / max possible edges
    max_edges = n_nodes * (n_nodes - 1) / 2
    density = n_edges / max_edges if max_edges > 0 else 0.0

    # Mean degree
    degree = np.zeros(n_nodes)
    for u, v in config["edges"]:
        if u < n_nodes:
            degree[u] += 1
        if v < n_nodes:
            degree[v] += 1
    mean_degree = float(np.mean(degree)) if n_nodes > 0 else 0.0
    max_degree = float(np.max(degree)) if n_nodes > 0 else 0.0

    # Diameter estimate (BFS from node 0)
    if n_nodes > 0 and n_edges > 0:
        adj = [[] for _ in range(n_nodes)]
        for u, v in config["edges"]:
            if u < n_nodes and v < n_nodes:
                adj[u].append(v)
                adj[v].append(u)
        max_dist = 0
        visited = {0}
        frontier = [0]
        while frontier:
            next_frontier = []
            for node in frontier:
                for nb in adj[node]:
                    if nb not in visited:
                        visited.add(nb)
                        next_frontier.append(nb)
            if next_frontier:
                max_dist += 1
            frontier = next_frontier
        diameter = max_dist
    else:
        diameter = 0

    # Field-level baselines
    field_mean = float(np.mean(field))
    field_max = float(np.max(field))
    field_std = float(np.std(field))

    # Largest connected component (of graph, not field)
    if n_nodes > 0:
        adj = [[] for _ in range(n_nodes)]
        for u, v in config["edges"]:
            if u < n_nodes and v < n_nodes:
                adj[u].append(v)
                adj[v].append(u)
        visited = set()
        largest_cc = 0
        for start in range(n_nodes):
            if start in visited:
                continue
            stack = [start]
            cc_size = 0
            while stack:
                node = stack.pop()
                if node in visited:
                    continue
                visited.add(node)
                cc_size += 1
                stack.extend(adj[node])
            largest_cc = max(largest_cc, cc_size)
        lcc_frac = largest_cc / n_nodes
    else:
        lcc_frac = 0.0

    return {
        "bl_mass": total_mass,
        "bl_node_count": n_nodes,
        "bl_edge_count": n_edges,
        "bl_density": round(density, 4),
        "bl_mean_degree": round(mean_degree, 2),
        "bl_max_degree": round(max_degree, 0),
        "bl_diameter": diameter,
        "bl_lcc_frac": round(lcc_frac, 4),
        "bl_field_mean": round(field_mean, 6),
        "bl_field_max": round(field_max, 4),
        "bl_field_std": round(field_std, 4),
    }


# ═══════════════════════════════════════════════════
# 5. Outcome labeling
# ═══════════════════════════════════════════════════

def label_outcome(history, status):
    """Label based on whether the field GREW or DECAYED, not just collapse."""
    if status == "UNSTABLE":
        return {
            "outcome": "UNSTABLE", "survived": False,
            "pct_mean_change": float("nan"), "pct_grad_change": float("nan"),
            "peak_reached": max(h["max_u"] for h in history) if history else 0,
            "final_mean": float("nan"), "final_area_frac": float("nan"),
            "time_to_collapse": len(history),
        }

    if len(history) < 20:
        return {
            "outcome": "TOO_SHORT", "survived": False,
            "pct_mean_change": float("nan"), "pct_grad_change": float("nan"),
            "peak_reached": 0, "final_mean": 0, "final_area_frac": 0,
            "time_to_collapse": 0,
        }

    n = len(history)
    window = max(10, n // 10)
    early = history[:window]
    late = history[-window:]

    early_mean = np.mean([h["mean_u"] for h in early])
    late_mean = np.mean([h["mean_u"] for h in late])
    early_grad = np.mean([h["mean_grad"] for h in early])
    late_grad = np.mean([h["mean_grad"] for h in late])

    pct_mean = 100.0 * ((late_mean / early_mean) - 1.0) if early_mean > 1e-12 else float("nan")
    pct_grad = 100.0 * ((late_grad / early_grad) - 1.0) if early_grad > 1e-12 else float("nan")

    final = history[-1]
    peak = max(h["max_u"] for h in history)

    # Classification based on gradient change (matches reproducibility package)
    if np.isnan(pct_grad):
        outcome = "INDETERMINATE"
        survived = False
    elif pct_grad > 5.0:
        outcome = "AMPLIFIED"
        survived = True
    elif pct_grad < -5.0:
        outcome = "DECAYED"
        survived = False
    else:
        outcome = "FLAT"
        survived = False  # conservative: flat = did not clearly amplify

    return {
        "outcome": outcome,
        "survived": survived,
        "pct_mean_change": round(pct_mean, 2) if not np.isnan(pct_mean) else float("nan"),
        "pct_grad_change": round(pct_grad, 2) if not np.isnan(pct_grad) else float("nan"),
        "peak_reached": round(peak, 4),
        "final_mean": round(final["mean_u"], 6),
        "final_area_frac": round(final["area_frac"], 4),
        "time_to_collapse": n,
    }
