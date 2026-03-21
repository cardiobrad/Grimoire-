#!/usr/bin/env python3
"""
swarm_compiler.py — Swarm Deployment Compiler Lite v0.1

Scores a drone/robot formation BEFORE launch.
Returns viability class, component breakdown, and actionable recommendations.

Usage:
    python swarm_compiler.py --input examples/search_rescue.json
    python swarm_compiler.py --input examples/surveillance_fragile.json
    python swarm_compiler.py --input examples/warehouse_edge_case.json
    python swarm_compiler.py --input examples/search_rescue.json --plot

Don't fly every formation. Score the seed first.
"""

import argparse
import json
import sys
import numpy as np
from scipy import ndimage
from typing import List, Tuple, Dict, Any, Optional
from config import WEIGHTS, THRESHOLDS, LAUNCH_MAP
from reporting import print_report, generate_why_report


# ═══════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════

def load_scenario(filepath: str) -> Dict[str, Any]:
    """Load a scenario from JSON file."""
    with open(filepath, "r") as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════
# RASTERIZATION
# ═══════════════════════════════════════════════════════════════

def rasterize(drones: List[dict], area_w: float, area_h: float, 
              resolution: float) -> Tuple[np.ndarray, np.ndarray]:
    """
    Project drone positions onto a 2D density grid.
    Returns (density_map, battery_weighted_map).
    """
    gw = int(np.ceil(area_w / resolution))
    gh = int(np.ceil(area_h / resolution))
    density = np.zeros((gh, gw), dtype=np.float32)
    battery = np.zeros((gh, gw), dtype=np.float32)
    
    for d in drones:
        gx = int(np.clip(d["x"] / resolution, 0, gw - 1))
        gy = int(np.clip(d["y"] / resolution, 0, gh - 1))
        density[gy, gx] += 1.0
        battery[gy, gx] += d.get("battery", 1.0)
    
    return density, battery


def apply_obstacles(grid: np.ndarray, obstacles: List[dict], 
                    resolution: float) -> np.ndarray:
    """Zero out grid cells covered by obstacles."""
    result = grid.copy()
    for obs in obstacles:
        x0 = int(obs["x"] / resolution)
        y0 = int(obs["y"] / resolution)
        x1 = int((obs["x"] + obs["width"]) / resolution)
        y1 = int((obs["y"] + obs["height"]) / resolution)
        y1 = min(y1, result.shape[0])
        x1 = min(x1, result.shape[1])
        result[y0:y1, x0:x1] = 0
    return result


# ═══════════════════════════════════════════════════════════════
# ADJACENCY & CONNECTIVITY
# ═══════════════════════════════════════════════════════════════

def build_adjacency(drones: List[dict]) -> np.ndarray:
    """Build comms adjacency matrix. adj[i,j]=1 if within mutual comms range."""
    n = len(drones)
    adj = np.zeros((n, n), dtype=np.int32)
    for i in range(n):
        for j in range(i + 1, n):
            dx = drones[i]["x"] - drones[j]["x"]
            dy = drones[i]["y"] - drones[j]["y"]
            dz = drones[i].get("z", 0) - drones[j].get("z", 0)
            dist = np.sqrt(dx*dx + dy*dy + dz*dz)
            r = min(drones[i].get("comms_radius", 50),
                    drones[j].get("comms_radius", 50))
            if dist <= r:
                adj[i, j] = 1
                adj[j, i] = 1
    return adj


def find_components(adj: np.ndarray) -> Tuple[int, List[List[int]]]:
    """BFS connected components on adjacency matrix."""
    n = adj.shape[0]
    visited = [False] * n
    components = []
    for start in range(n):
        if visited[start]:
            continue
        comp = []
        queue = [start]
        visited[start] = True
        while queue:
            node = queue.pop(0)
            comp.append(node)
            for nb in range(n):
                if adj[node, nb] and not visited[nb]:
                    visited[nb] = True
                    queue.append(nb)
        components.append(comp)
    return len(components), components


# ═══════════════════════════════════════════════════════════════
# GSM COMPONENTS
# ═══════════════════════════════════════════════════════════════

def compute_amplitude(density: np.ndarray) -> float:
    """A = peak local density / threshold."""
    return float(np.max(density)) / THRESHOLDS["A_c"]


def compute_core_radius(density: np.ndarray) -> Tuple[float, np.ndarray]:
    """R = effective radius of suprathreshold core / threshold."""
    mask = density >= THRESHOLDS["A_c"]
    area = int(mask.sum())
    if area == 0:
        return 0.0, mask
    r_eff = float(np.sqrt(area / np.pi))
    return r_eff / THRESHOLDS["R_c"], mask


def compute_mass(density: np.ndarray, battery: np.ndarray, 
                 mask: np.ndarray) -> float:
    """M = battery-weighted density in core / threshold."""
    if mask.sum() == 0:
        return 0.0
    mass = float((density[mask] * battery[mask]).sum())
    return mass / THRESHOLDS["M_c"]


def compute_topology(components: List[List[int]], n_drones: int) -> float:
    """T = largest connected component / total drones."""
    if n_drones == 0:
        return 0.0
    largest = max(len(c) for c in components) if components else 0
    return largest / n_drones


def compute_gradient(density: np.ndarray, mask: np.ndarray) -> float:
    """G = mean gradient magnitude in core, normalised to [0,1)."""
    if mask.sum() < 2:
        return 0.0
    gy, gx = np.gradient(density)
    g_raw = float((gx[mask]**2 + gy[mask]**2).mean())
    return g_raw / (g_raw + 1.0)


def detect_overload(density: np.ndarray, resolution: float) -> List[dict]:
    """Find cells exceeding overload threshold."""
    threshold = THRESHOLDS["overload_threshold"]
    hotspots = []
    ys, xs = np.where(density >= threshold)
    for y, x in zip(ys, xs):
        hotspots.append({
            "grid": [int(x), int(y)],
            "world": [round(float(x * resolution + resolution/2), 1),
                      round(float(y * resolution + resolution/2), 1)],
            "count": int(density[y, x]),
            "severity": round(float(min(1.0, density[y, x] / (threshold * 2))), 3),
        })
    return hotspots


def identify_core_candidates(drones: List[dict], adj: np.ndarray) -> List[str]:
    """Find drones suitable for protected-core role."""
    candidates = []
    neighbour_counts = adj.sum(axis=1)
    median_nb = np.median(neighbour_counts) if len(drones) > 0 else 0
    for i, d in enumerate(drones):
        role = d.get("role", "worker")
        if role in ("command", "relay"):
            candidates.append(d["id"])
        elif neighbour_counts[i] >= median_nb * 1.5 and median_nb > 0:
            candidates.append(d["id"])
    return candidates


# ═══════════════════════════════════════════════════════════════
# CLASSIFICATION
# ═══════════════════════════════════════════════════════════════

def classify(score: float, A: float, R: float, M: float, T: float,
             n_components: int, n_drones: int) -> str:
    """
    Classify formation viability.
    Returns: DORMANT | FRAGILE | EDGE CASE | AMPLIFYING | RESILIENT
    """
    if n_drones < 3:
        return "DORMANT"
    if A < 0.5:
        return "DORMANT"
    if n_components > 2 and T < 0.6:
        return "FRAGILE"
    if R < 0.3 and T < 0.5:
        return "FRAGILE"
    if score < 0.5:
        return "FRAGILE"
    if score < 0.8:
        return "EDGE CASE"
    if n_components == 1 and T > 0.85 and R > 0.6:
        return "AMPLIFYING"
    if n_components > 1:
        return "EDGE CASE"
    if T > 0.7 and score >= 0.8:
        return "RESILIENT"
    if score >= 1.0 and A > 1.0 and n_components == 1:
        return "AMPLIFYING"
    return "EDGE CASE"


# ═══════════════════════════════════════════════════════════════
# MAIN SCORING PIPELINE
# ═══════════════════════════════════════════════════════════════

def score(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """
    Score a swarm deployment scenario.
    
    Input: scenario dict with keys:
        name, drones, area_width, area_height, grid_resolution,
        obstacles (optional), target_zones (optional)
    
    Returns: complete result dict.
    """
    drones = scenario["drones"]
    area_w = scenario.get("area_width", 200)
    area_h = scenario.get("area_height", 200)
    resolution = scenario.get("grid_resolution", 5.0)
    obstacles = scenario.get("obstacles", [])
    
    # 1. Rasterize
    density, battery = rasterize(drones, area_w, area_h, resolution)
    density = apply_obstacles(density, obstacles, resolution)
    
    # 2. GSM components
    A = compute_amplitude(density)
    R, core_mask = compute_core_radius(density)
    M = compute_mass(density, battery, core_mask)
    
    # 3. Connectivity
    adj = build_adjacency(drones)
    n_comp, components = find_components(adj)
    largest = max(len(c) for c in components) if components else 0
    T = compute_topology(components, len(drones))
    
    # 4. Gradient
    G = compute_gradient(density, core_mask)
    
    # 5. Composite score
    gsm_score = (
        WEIGHTS["wA"] * A +
        WEIGHTS["wR"] * R +
        WEIGHTS["wM"] * M +
        WEIGHTS["wT"] * T +
        WEIGHTS["wG"] * G
    )
    
    # 6. Classify
    cls = classify(gsm_score, A, R, M, T, n_comp, len(drones))
    
    # 7. Overload detection
    hotspots = detect_overload(density, resolution)
    
    # 8. Core candidates
    core_candidates = identify_core_candidates(drones, adj)
    
    # 9. Launch recommendation
    launch = LAUNCH_MAP.get(cls, "RESEED BEFORE LAUNCH")
    
    # 10. Assemble
    result = {
        "scenario": scenario.get("name", "unnamed"),
        "score": round(gsm_score, 3),
        "classification": cls,
        "launch_recommendation": launch,
        "components": {
            "amplitude": round(A, 3),
            "core_radius": round(R, 3),
            "concentrated_mass": round(M, 3),
            "topology": round(T, 3),
            "gradient": round(G, 3),
        },
        "connectivity": {
            "total_components": n_comp,
            "largest_component": largest,
        },
        "overload": {
            "hotspot_count": len(hotspots),
            "hotspots": hotspots,
        },
        "protected_core_candidates": core_candidates,
        "drone_count": len(drones),
        "density_map_shape": list(density.shape),
    }
    
    # 11. Why report
    result["why"] = generate_why_report(result)
    
    return result


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Swarm Deployment Compiler Lite v0.1 — Score the seed before you fly.",
        epilog="Don't fly every formation. Score the seed first."
    )
    parser.add_argument("--input", "-i", required=True,
                        help="Path to scenario JSON file")
    parser.add_argument("--plot", "-p", action="store_true",
                        help="Generate visual report (requires matplotlib)")
    parser.add_argument("--json", "-j", action="store_true",
                        help="Output raw JSON instead of formatted report")
    parser.add_argument("--output", "-o", default=None,
                        help="Save plot to this path (default: outputs/<name>.png)")
    
    args = parser.parse_args()
    
    # Load scenario
    scenario = load_scenario(args.input)
    
    # Score it
    result = score(scenario)
    
    # Output
    if args.json:
        # Strip non-serializable fields
        out = {k: v for k, v in result.items() if k != "density_map_shape" or True}
        print(json.dumps(out, indent=2))
    else:
        print_report(result)
    
    # Plot
    if args.plot:
        try:
            from viz import plot_formation
            name = scenario.get("name", "scenario").replace(" ", "_").lower()
            path = args.output or f"outputs/{name}.png"
            plot_formation(scenario, result, path)
            print(f"\n  Plot saved: {path}")
        except ImportError:
            print("\n  [!] matplotlib required for --plot. Install: pip install matplotlib")
    
    return result


if __name__ == "__main__":
    main()
