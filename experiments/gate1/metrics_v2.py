"""
metrics_v2.py — Three candidate viability metrics.
All compute scores from initial state only (no simulation outcome).
Each returns (score, components_dict) for ablation support.
"""
import numpy as np
from config import GSM


# ═══════════════════════════════════════════════════
# Candidate A: Adaptive-field GSM
# ═══════════════════════════════════════════════════

def adaptive_gsm(field, P=(0.70, 0.85, 0.95), R_c=2.5, M_c=5.0,
                 weights=None, eps=1e-6):
    """Multi-threshold adaptive GSM. Averages components across percentile thresholds."""
    if weights is None:
        weights = [GSM["w_a"], GSM["w_r"], GSM["w_m"], GSM["w_t"], GSM["w_g"]]

    N = field.shape[0]
    max_u = float(np.max(field))
    if max_u < eps:
        return 0.0, {"A": 0, "R": 0, "M": 0, "T": 0, "G": 0}

    comp_sums = {"A": 0.0, "R": 0.0, "M": 0.0, "T": 0.0, "G": 0.0}
    valid_thresholds = 0

    for p in P:
        thresh = max(float(np.percentile(field, p * 100)), eps)
        mask = field >= thresh
        area = int(np.sum(mask))
        if area == 0:
            continue
        valid_thresholds += 1

        # Amplitude ratio (capped)
        A_norm = min(max_u / thresh, 5.0)

        # Effective radius
        r_eff = float(np.sqrt(area / np.pi))
        R_norm = r_eff / R_c

        # Mass above threshold
        mass = float(np.sum(field[mask]))
        M_norm = mass / M_c

        # Connectivity (largest connected component fraction)
        mask_flat = mask.ravel()
        visited = np.zeros(N * N, dtype=bool)
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
        T_norm = largest / area if area > 0 else 0.0

        # Gradient shape
        gx = (np.roll(field, -1, axis=1) - np.roll(field, 1, axis=1)) / 2.0
        gy = (np.roll(field, -1, axis=0) - np.roll(field, 1, axis=0)) / 2.0
        grad_mag = np.sqrt(gx ** 2 + gy ** 2)
        G_norm = min(float(np.mean(grad_mag[mask])) / 0.5, 1.0) if area > 0 else 0.0

        comp_sums["A"] += A_norm
        comp_sums["R"] += R_norm
        comp_sums["M"] += M_norm
        comp_sums["T"] += T_norm
        comp_sums["G"] += G_norm

    if valid_thresholds == 0:
        return 0.0, {"A": 0, "R": 0, "M": 0, "T": 0, "G": 0}

    # Average across valid thresholds
    for k in comp_sums:
        comp_sums[k] /= valid_thresholds

    score = (weights[0] * comp_sums["A"] +
             weights[1] * comp_sums["R"] +
             weights[2] * comp_sums["M"] +
             weights[3] * comp_sums["T"] +
             weights[4] * comp_sums["G"])

    return round(score, 4), {k: round(v, 4) for k, v in comp_sums.items()}


# ═══════════════════════════════════════════════════
# Candidate B: Graph-native GSM
# ═══════════════════════════════════════════════════

def _build_adjacency(config):
    """Build adjacency list from config."""
    n = config["n_nodes"]
    adj = [[] for _ in range(n)]
    for u, v in config["edges"]:
        if u < n and v < n:
            adj[u].append(v)
            adj[v].append(u)
    return adj, n


def _clustering_coefficient(adj, n):
    """Average local clustering coefficient."""
    if n < 3:
        return 0.0
    total = 0.0
    for node in range(n):
        neighbors = adj[node]
        k = len(neighbors)
        if k < 2:
            continue
        links = 0
        nset = set(neighbors)
        for i in range(len(neighbors)):
            for j in range(i + 1, len(neighbors)):
                if neighbors[j] in set(adj[neighbors[i]]):
                    links += 1
        total += 2.0 * links / (k * (k - 1))
    return total / n


def _components(adj, n):
    """Find connected components. Returns list of component sizes."""
    visited = set()
    sizes = []
    for start in range(n):
        if start in visited:
            continue
        stack = [start]
        size = 0
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            size += 1
            stack.extend(adj[node])
        sizes.append(size)
    return sizes


def _diameter_lcc(adj, n):
    """Diameter of the largest connected component via BFS."""
    # Find LCC
    visited = set()
    lcc_nodes = []
    best_size = 0
    for start in range(n):
        if start in visited:
            continue
        stack = [start]
        comp = []
        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            comp.append(node)
            stack.extend(adj[node])
        if len(comp) > best_size:
            best_size = len(comp)
            lcc_nodes = comp

    if len(lcc_nodes) <= 1:
        return 0

    # BFS from each LCC node, track max distance
    lcc_set = set(lcc_nodes)
    max_dist = 0
    for source in lcc_nodes:
        dist = {source: 0}
        queue = [source]
        while queue:
            node = queue.pop(0)
            for nb in adj[node]:
                if nb in lcc_set and nb not in dist:
                    dist[nb] = dist[node] + 1
                    queue.append(nb)
                    if dist[nb] > max_dist:
                        max_dist = dist[nb]
    return max_dist


def graph_gsm_core(config, N=64, weights=None):
    """Graph-native GSM. Pure topology, no field values."""
    if weights is None:
        weights = {"w_C": 0.25, "w_F": 0.25, "w_D": 0.25, "w_S": 0.25}

    adj, n = _build_adjacency(config)

    if n == 0:
        return 0.0, {"C": 0, "F": 1, "D_norm": 1, "S_norm": 1}

    # Clustering coefficient
    C = _clustering_coefficient(adj, n)

    # Fragmentation
    comp_sizes = _components(adj, n)
    lcc_size = max(comp_sizes) if comp_sizes else 0
    F = 1.0 - (lcc_size / n)

    # Diameter (normalized)
    diam = _diameter_lcc(adj, n)
    D_norm = diam / n if n > 0 else 0

    # Spatial compactness (radius of gyration)
    positions = np.array([(x, y) for x, y, _ in config["nodes"]])
    centroid = positions.mean(axis=0)
    Rg = float(np.sqrt(np.mean(np.sum((positions - centroid) ** 2, axis=1))))
    S_norm = Rg / (N / 2)

    # Transform to higher = better
    score = (weights["w_C"] * C +
             weights["w_F"] * (1 - F) +
             weights["w_D"] * (1 - D_norm) +
             weights["w_S"] * (1 - S_norm))

    components = {
        "C": round(C, 4),
        "F": round(F, 4),
        "D_norm": round(D_norm, 4),
        "S_norm": round(S_norm, 4),
    }
    return round(score, 4), components


# ═══════════════════════════════════════════════════
# Candidate C: Hybrid GSM (graph-native + one adaptive field term)
# ═══════════════════════════════════════════════════

def hybrid_gsm(config, field, N=64, eps=1e-6):
    """Minimal hybrid: 4 graph features + 1 adaptive amplitude term, equal weights."""
    _, graph_comp = graph_gsm_core(config, N)

    # Adaptive amplitude from 85th percentile
    T_85 = max(float(np.percentile(field, 85)), eps)
    A_norm = min(float(np.max(field)) / T_85, 5.0)

    w = 0.2
    score = (w * graph_comp["C"] +
             w * (1 - graph_comp["F"]) +
             w * (1 - graph_comp["D_norm"]) +
             w * (1 - graph_comp["S_norm"]) +
             w * A_norm)

    components = {
        "C": graph_comp["C"],
        "F": graph_comp["F"],
        "D_norm": graph_comp["D_norm"],
        "S_norm": graph_comp["S_norm"],
        "A_norm": round(A_norm, 4),
    }
    return round(score, 4), components
