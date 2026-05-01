"""
gsm_candidates.py — Two replacement GSM candidates per DeepSeek+ChatGPT spec.

Candidate 1: Adaptive-field GSM (multi-threshold TFCE-inspired)
Candidate 2: Graph-native GSM (pure topology + spatial embedding)
Candidate 2b: Graph-native GSM + spectral term (optional)
"""
import numpy as np
from scipy import ndimage
from config import GSM

# ═══════════════════════════════════════════════════
# Candidate 1: Adaptive-field GSM
# ═══════════════════════════════════════════════════

def adaptive_gsm(field, P=(0.70, 0.85, 0.95), R_c=2.5, M_c=5.0, weights=None, eps=1e-6):
    """Multi-threshold field GSM. Inputs: initial field only. No simulation data."""
    if weights is None:
        weights = {"w_a": 0.35, "w_r": 0.25, "w_m": 0.20, "w_t": 0.15, "w_g": 0.05}

    T_85 = max(np.percentile(field, 85), eps)
    A_norm = min(float(np.max(field)) / T_85, 5.0)

    R_vals, M_vals, T_vals, G_vals = [], [], [], []
    gx, gy = np.gradient(field)
    grad_mag = np.sqrt(gx**2 + gy**2)

    for p in P:
        T = max(np.percentile(field, p * 100), eps)
        mask = field >= T
        area = int(np.sum(mask))
        if area == 0:
            continue

        R_vals.append(np.sqrt(area / np.pi) / R_c)
        M_vals.append(float(np.sum(field[mask])) / M_c)

        labeled, num = ndimage.label(mask)
        if num > 0:
            sizes = ndimage.sum(mask, labeled, range(1, num + 1))
            largest = float(np.max(sizes))
            T_vals.append(largest / area)
        else:
            T_vals.append(0.0)

        G_vals.append(min(float(np.mean(grad_mag[mask])) / 0.5, 1.0))

    if not R_vals:
        return weights["w_a"] * A_norm, {"A_norm": A_norm, "R_mean": 0, "M_mean": 0, "T_mean": 0, "G_mean": 0}

    comps = {
        "A_norm": round(A_norm, 4),
        "R_mean": round(float(np.mean(R_vals)), 4),
        "M_mean": round(float(np.mean(M_vals)), 4),
        "T_mean": round(float(np.mean(T_vals)), 4),
        "G_mean": round(float(np.mean(G_vals)), 4),
    }

    score = (weights["w_a"] * A_norm +
             weights["w_r"] * np.mean(R_vals) +
             weights["w_m"] * np.mean(M_vals) +
             weights["w_t"] * np.mean(T_vals) +
             weights["w_g"] * np.mean(G_vals))

    return round(float(score), 4), comps


# ═══════════════════════════════════════════════════
# Candidate 2: Graph-native GSM (core)
# ═══════════════════════════════════════════════════

def graph_gsm_core(config, N=64, weights=None):
    """Score from graph topology + spatial embedding only. No field values used."""
    if weights is None:
        weights = {"w_C": 0.25, "w_F": 0.25, "w_D": 0.25, "w_S": 0.25}

    n = config["n_nodes"]
    pos = np.array([(x, y) for (x, y, _) in config["nodes"]])
    adj = [[] for _ in range(n)]
    for u, v in config["edges"]:
        if u < n and v < n:
            adj[u].append(v)
            adj[v].append(u)

    # 1. Clustering coefficient
    C = 0.0
    for i in range(n):
        deg_i = len(adj[i])
        if deg_i < 2:
            continue
        neighbors = set(adj[i])
        triangles = 0
        for j in neighbors:
            for k in neighbors:
                if j < k and k in set(adj[j]):
                    triangles += 1
        C += (2.0 * triangles) / (deg_i * (deg_i - 1))
    C /= max(n, 1)

    # 2. Fragmentation (LCC fraction)
    visited = [False] * n
    largest = 0
    for start in range(n):
        if visited[start]:
            continue
        queue = [start]
        visited[start] = True
        size = 0
        while queue:
            u = queue.pop()
            size += 1
            for v in adj[u]:
                if not visited[v]:
                    visited[v] = True
                    queue.append(v)
        largest = max(largest, size)
    F = 1.0 - (largest / n) if n > 0 else 1.0

    # 3. Diameter (BFS from each node in LCC, find max distance)
    # First identify LCC nodes
    visited2 = [False] * n
    lcc_nodes = []
    for start in range(n):
        if visited2[start]:
            continue
        queue = [start]
        visited2[start] = True
        component = []
        while queue:
            u = queue.pop()
            component.append(u)
            for v in adj[u]:
                if not visited2[v]:
                    visited2[v] = True
                    queue.append(v)
        if len(component) > len(lcc_nodes):
            lcc_nodes = component

    diameter = 0
    if len(lcc_nodes) > 1:
        lcc_set = set(lcc_nodes)
        for source in lcc_nodes:
            dist = {source: 0}
            queue = [source]
            while queue:
                u = queue.pop(0)
                for v in adj[u]:
                    if v in lcc_set and v not in dist:
                        dist[v] = dist[u] + 1
                        queue.append(v)
            max_d = max(dist.values())
            diameter = max(diameter, max_d)

    D_norm = diameter / max(n, 1)

    # 4. Spatial compactness (radius of gyration)
    centroid = np.mean(pos, axis=0)
    Rg = float(np.sqrt(np.mean(np.sum((pos - centroid) ** 2, axis=1))))
    S_norm = Rg / (N / 2)

    # Transform to [0,1] where higher = better
    C_score = C
    F_score = 1.0 - F
    D_score = 1.0 - D_norm
    S_score = max(0.0, 1.0 - S_norm)

    score = (weights["w_C"] * C_score +
             weights["w_F"] * F_score +
             weights["w_D"] * D_score +
             weights["w_S"] * S_score)

    comps = {
        "clustering": round(C, 4),
        "fragmentation": round(F, 4),
        "diameter_norm": round(D_norm, 4),
        "spatial_compact": round(S_norm, 4),
        "C_score": round(C_score, 4),
        "F_score": round(F_score, 4),
        "D_score": round(D_score, 4),
        "S_score": round(S_score, 4),
    }

    return round(float(score), 4), comps


# ═══════════════════════════════════════════════════
# Candidate 2b: Graph-native GSM + spectral
# ═══════════════════════════════════════════════════

def graph_gsm_spectral(config, N=64, weights=None):
    """Graph GSM with algebraic connectivity (Fiedler value)."""
    if weights is None:
        weights = {"w_C": 0.20, "w_F": 0.20, "w_D": 0.20, "w_S": 0.20, "w_L": 0.20}

    # Get core scores first
    core_score, comps = graph_gsm_core(config, N, {"w_C": 0.20, "w_F": 0.20, "w_D": 0.20, "w_S": 0.20})

    n = config["n_nodes"]
    adj = [[] for _ in range(n)]
    for u, v in config["edges"]:
        if u < n and v < n:
            adj[u].append(v)
            adj[v].append(u)

    # Build Laplacian
    A = np.zeros((n, n))
    for i in range(n):
        for j in adj[i]:
            A[i, j] = 1.0
    degrees = np.array([len(adj[i]) for i in range(n)])
    L = np.diag(degrees) - A

    eigenvalues = np.linalg.eigvalsh(L)
    eigenvalues.sort()
    lambda2 = float(eigenvalues[1]) if len(eigenvalues) > 1 else 0.0

    # Normalize lambda2 (typical range 0 to ~n for complete graph)
    lambda2_norm = min(lambda2 / max(n * 0.5, 1.0), 1.0)

    # IPR diagnostic (not used in score)
    eigvecs = np.linalg.eigh(A)[1]
    principal = eigvecs[:, -1]
    ipr = float(np.sum(principal ** 4) / max(np.sum(principal ** 2) ** 2, 1e-12))

    score = core_score + weights["w_L"] * lambda2_norm

    comps["lambda2"] = round(lambda2, 4)
    comps["lambda2_norm"] = round(lambda2_norm, 4)
    comps["ipr"] = round(ipr, 4)
    comps["ipr_flag"] = ipr > 0.3

    return round(float(score), 4), comps
