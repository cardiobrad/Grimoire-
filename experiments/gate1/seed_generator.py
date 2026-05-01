"""
seed_generator.py — Generate graph-based seed families with controlled mass.

Each seed family produces a set of (x,y) node positions and edges on a 64x64 grid.
Total mass (sum of amplitudes) is held constant across families.
Topology varies deliberately.

Returns a list of SeedConfig dicts, each containing:
  - family: topology name
  - nodes: list of (x, y, amplitude)
  - edges: list of (i, j) node index pairs
  - seed_id: unique identifier
  - rng_seed: for reproducibility
"""
import numpy as np
from config import FIELD, TARGET_MASS, TARGET_NODES, AMPLITUDE_PER_NODE, SEEDS_PER_FAMILY, SEED_RNG_BASE

N = FIELD["N"]
PAD = 6  # keep seeds away from edges for cleaner dynamics


def _place_nodes_circle(n, rng, radius=18):
    """Place n nodes in a circle around grid center."""
    cx, cy = N // 2, N // 2
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    jitter = rng.normal(0, 1.5, (n, 2))
    nodes = []
    for i, a in enumerate(angles):
        x = int(np.clip(cx + radius * np.cos(a) + jitter[i, 0], PAD, N - PAD))
        y = int(np.clip(cy + radius * np.sin(a) + jitter[i, 1], PAD, N - PAD))
        nodes.append((x, y))
    return nodes


def _place_nodes_random(n, rng):
    """Place n nodes randomly on grid."""
    xs = rng.randint(PAD, N - PAD, n)
    ys = rng.randint(PAD, N - PAD, n)
    return list(zip(xs.tolist(), ys.tolist()))


def _place_nodes_line(n, rng):
    """Place n nodes in a line across the grid."""
    cx, cy = N // 2, N // 2
    xs = np.linspace(PAD, N - PAD, n).astype(int)
    ys = (cy + rng.normal(0, 1.5, n)).astype(int)
    ys = np.clip(ys, PAD, N - PAD)
    return list(zip(xs.tolist(), ys.tolist()))


def _place_nodes_grid(n, rng):
    """Place n nodes in a roughly square lattice."""
    side = int(np.ceil(np.sqrt(n)))
    cx, cy = N // 2, N // 2
    spacing = min(8, (N - 2 * PAD) // (side + 1))
    nodes = []
    for i in range(side):
        for j in range(side):
            if len(nodes) >= n:
                break
            x = int(cx + (i - side // 2) * spacing + rng.normal(0, 0.8))
            y = int(cy + (j - side // 2) * spacing + rng.normal(0, 0.8))
            nodes.append((int(np.clip(x, PAD, N - PAD)), int(np.clip(y, PAD, N - PAD))))
    return nodes[:n]


# ═══════════════════════════════════════════════════
# Topology generators
# ═══════════════════════════════════════════════════

def gen_line(n, rng):
    nodes = _place_nodes_line(n, rng)
    edges = [(i, i + 1) for i in range(n - 1)]
    return nodes, edges


def gen_ring(n, rng):
    nodes = _place_nodes_circle(n, rng)
    edges = [(i, (i + 1) % n) for i in range(n)]
    return nodes, edges


def gen_star(n, rng):
    nodes = _place_nodes_circle(n, rng, radius=14)
    # node 0 is hub (move to center)
    nodes[0] = (N // 2, N // 2)
    edges = [(0, i) for i in range(1, n)]
    return nodes, edges


def gen_lattice(n, rng):
    nodes = _place_nodes_grid(n, rng)
    side = int(np.ceil(np.sqrt(n)))
    edges = []
    for i in range(n):
        r, c = i // side, i % side
        if c + 1 < side and i + 1 < n:
            edges.append((i, i + 1))
        if r + 1 < side and i + side < n:
            edges.append((i, i + side))
    return nodes, edges


def gen_tree(n, rng):
    nodes = _place_nodes_random(n, rng)
    edges = []
    for i in range(1, n):
        parent = rng.randint(0, i)
        edges.append((parent, i))
    return nodes, edges


def gen_clustered_islands(n, rng):
    """3 dense clusters with no inter-cluster edges."""
    k = max(2, n // 3)
    remainder = n - 3 * k
    clusters = [k, k, k + remainder]
    nodes = []
    edges = []
    offsets = [(-15, -10), (15, -10), (0, 15)]
    idx_offset = 0
    for ci in range(3):
        ox, oy = offsets[ci]
        cx, cy = N // 2 + ox, N // 2 + oy
        for j in range(clusters[ci]):
            x = int(np.clip(cx + rng.normal(0, 3), PAD, N - PAD))
            y = int(np.clip(cy + rng.normal(0, 3), PAD, N - PAD))
            nodes.append((x, y))
            if j > 0:
                edges.append((idx_offset + j, idx_offset + j - 1))
                if j > 1 and rng.random() > 0.5:
                    edges.append((idx_offset + j, idx_offset + rng.randint(0, j)))
        idx_offset += clusters[ci]
    return nodes, edges


def gen_erdos_renyi(n, rng, p=0.3):
    nodes = _place_nodes_random(n, rng)
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            if rng.random() < p:
                edges.append((i, j))
    return nodes, edges


def gen_small_world(n, rng, k=4, p_rewire=0.2):
    nodes = _place_nodes_circle(n, rng)
    edges = set()
    for i in range(n):
        for j in range(1, k // 2 + 1):
            edges.add((i, (i + j) % n))
    rewired = set()
    for (u, v) in list(edges):
        if rng.random() < p_rewire:
            new_v = rng.randint(0, n)
            while new_v == u or (u, new_v) in edges or (new_v, u) in edges:
                new_v = rng.randint(0, n)
            rewired.add((u, new_v))
        else:
            rewired.add((u, v))
    return nodes, list(rewired)


def gen_scale_free(n, rng, m0=3):
    """Barabási-Albert preferential attachment."""
    nodes = _place_nodes_random(n, rng)
    edges = []
    # Start with complete graph on m0 nodes
    for i in range(m0):
        for j in range(i + 1, m0):
            edges.append((i, j))
    degree = np.zeros(n)
    for u, v in edges:
        degree[u] += 1
        degree[v] += 1
    for new in range(m0, n):
        targets = set()
        probs = degree[:new] + 1
        probs = probs / probs.sum()
        while len(targets) < min(2, new):
            t = rng.choice(new, p=probs)
            targets.add(t)
        for t in targets:
            edges.append((new, t))
            degree[new] += 1
            degree[t] += 1
    return nodes, edges


GENERATORS = {
    "line": gen_line,
    "ring": gen_ring,
    "star": gen_star,
    "lattice": gen_lattice,
    "tree": gen_tree,
    "clustered_islands": gen_clustered_islands,
    "erdos_renyi": gen_erdos_renyi,
    "small_world": gen_small_world,
    "scale_free": gen_scale_free,
}


FAMILY_SEEDS = {
    "line": 100, "ring": 200, "star": 300, "lattice": 400, "tree": 500,
    "clustered_islands": 600, "erdos_renyi": 700, "small_world": 800, "scale_free": 900,
}


def generate_seed_family(family, n_seeds=SEEDS_PER_FAMILY, n_nodes=TARGET_NODES, total_mass=TARGET_MASS):
    """Generate a family of seed configurations with controlled mass."""
    configs = []
    gen_fn = GENERATORS[family]
    base = FAMILY_SEEDS.get(family, 1000)

    for i in range(n_seeds):
        rng_seed = SEED_RNG_BASE + base + i
        rng = np.random.RandomState(rng_seed)
        nodes_xy, edges = gen_fn(n_nodes, rng)

        # Assign amplitudes: equal distribution to hold mass constant
        amp = total_mass / len(nodes_xy)
        nodes = [(x, y, amp) for x, y in nodes_xy]

        configs.append({
            "family": family,
            "seed_id": f"{family}_{i:03d}",
            "rng_seed": rng_seed,
            "nodes": nodes,
            "edges": edges,
            "n_nodes": len(nodes),
            "n_edges": len(edges),
            "total_mass": sum(a for _, _, a in nodes),
        })

    return configs


def generate_all_families():
    """Generate all topology families."""
    all_configs = []
    for family in GENERATORS:
        configs = generate_seed_family(family)
        all_configs.extend(configs)
        print(f"  {family:>20}: {len(configs)} seeds, {configs[0]['n_nodes']} nodes, {configs[0]['n_edges']} edges (first)")
    return all_configs
