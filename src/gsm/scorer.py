"""
gsm_swarm.scorer — Good Seed Metric computation for swarm formations.

Scores a drone deployment BEFORE launch.
Returns viability class + actionable diagnostics.

The metric is a pre-simulation structural heuristic, not a proof of outcome.
It is strongest in dense, spatially coupled regimes.
"""

import numpy as np
from scipy import ndimage
from typing import List, Tuple
from .types import (
    Drone, Mission, Obstacle, Formation,
    GSMComponents, GSMResult, OverloadHotspot
)


# ═══════════════════════════════════════════════════════════════
# Default weights — calibrated for general swarm missions.
# Adjust per domain. The ordering wA > wR > wM > wT > wG
# reflects the validated causal chain from the spatial substrate.
# ═══════════════════════════════════════════════════════════════
DEFAULT_WEIGHTS = {
    "wA": 0.30,   # amplitude — necessary but not sufficient
    "wR": 0.25,   # core radius — protects against fragmentation
    "wM": 0.20,   # concentrated mass — usable payload
    "wT": 0.20,   # topology — connectivity and resilience
    "wG": 0.05,   # gradient — boundary quality (secondary)
}

# Thresholds — domain-dependent. These are starting values.
DEFAULT_THRESHOLDS = {
    "A_c": 1.0,    # minimum peak density (drones per cell) for activation
    "R_c": 2.0,    # minimum core radius (grid cells) for stability
    "M_c": 8.0,    # minimum concentrated mass for viability
    "T_c": 0.7,    # minimum connectivity ratio
    "overload_threshold": 4,  # drones per cell = overload
    "comms_min_neighbours": 2,  # minimum comms neighbours for relay
}


def _rasterize(drones: List[Drone], mission: Mission) -> Tuple[np.ndarray, np.ndarray]:
    """
    Rasterize drone positions onto a 2D grid.
    Returns (density_map, battery_map).
    """
    gw = int(np.ceil(mission.area_width / mission.grid_resolution))
    gh = int(np.ceil(mission.area_height / mission.grid_resolution))
    density = np.zeros((gh, gw), dtype=np.float32)
    battery = np.zeros((gh, gw), dtype=np.float32)
    
    for d in drones:
        gx = int(np.clip(d.x / mission.grid_resolution, 0, gw - 1))
        gy = int(np.clip(d.y / mission.grid_resolution, 0, gh - 1))
        density[gy, gx] += 1.0
        battery[gy, gx] += d.battery
    
    return density, battery


def _apply_obstacles(grid: np.ndarray, obstacles: List[Obstacle], 
                     resolution: float) -> np.ndarray:
    """Zero out grid cells covered by obstacles."""
    result = grid.copy()
    for obs in obstacles:
        x0 = int(obs.x / resolution)
        y0 = int(obs.y / resolution)
        x1 = int((obs.x + obs.width) / resolution)
        y1 = int((obs.y + obs.height) / resolution)
        result[y0:y1, x0:x1] = 0
    return result


def _build_adjacency(drones: List[Drone]) -> np.ndarray:
    """
    Build adjacency matrix based on comms radius.
    adj[i,j] = 1 if drone i can communicate with drone j.
    """
    n = len(drones)
    adj = np.zeros((n, n), dtype=np.int32)
    for i in range(n):
        for j in range(i + 1, n):
            dist = np.sqrt(
                (drones[i].x - drones[j].x) ** 2 +
                (drones[i].y - drones[j].y) ** 2 +
                (drones[i].z - drones[j].z) ** 2
            )
            if dist <= min(drones[i].comms_radius, drones[j].comms_radius):
                adj[i, j] = 1
                adj[j, i] = 1
    return adj


def _connected_components(adj: np.ndarray) -> Tuple[int, List[List[int]]]:
    """Find connected components via BFS on adjacency matrix."""
    n = adj.shape[0]
    visited = [False] * n
    components = []
    
    for start in range(n):
        if visited[start]:
            continue
        component = []
        queue = [start]
        visited[start] = True
        while queue:
            node = queue.pop(0)
            component.append(node)
            for neighbour in range(n):
                if adj[node, neighbour] and not visited[neighbour]:
                    visited[neighbour] = True
                    queue.append(neighbour)
        components.append(component)
    
    return len(components), components


def _compute_amplitude(density: np.ndarray, thresholds: dict) -> float:
    """A = peak local density, normalised by threshold."""
    peak = float(np.max(density))
    return peak / thresholds["A_c"] if thresholds["A_c"] > 0 else 0.0


def _compute_core_radius(density: np.ndarray, thresholds: dict) -> Tuple[float, np.ndarray]:
    """
    R = effective radius of suprathreshold core.
    Returns (normalised score, core mask).
    """
    mask = density >= thresholds["A_c"]
    area = int(mask.sum())
    if area == 0:
        return 0.0, mask
    r_eff = float(np.sqrt(area / np.pi))
    return r_eff / thresholds["R_c"], mask


def _compute_mass(density: np.ndarray, battery_map: np.ndarray, 
                  mask: np.ndarray, thresholds: dict) -> float:
    """M = concentrated payload (battery-weighted density) in core."""
    if mask.sum() == 0:
        return 0.0
    mass = float((density[mask] * battery_map[mask]).sum())
    return mass / thresholds["M_c"] if thresholds["M_c"] > 0 else 0.0


def _compute_topology(adj: np.ndarray, n_components: int, 
                      components: List[List[int]], n_drones: int) -> float:
    """T = largest connected component / total drones."""
    if n_drones == 0:
        return 0.0
    largest = max(len(c) for c in components) if components else 0
    return largest / n_drones


def _compute_gradient(density: np.ndarray, mask: np.ndarray) -> float:
    """G = mean gradient magnitude in the core (boundary smoothness)."""
    if mask.sum() < 2:
        return 0.0
    gy, gx = np.gradient(density)
    grad_mag = gx ** 2 + gy ** 2
    return float(grad_mag[mask].mean())


def _detect_overload(density: np.ndarray, thresholds: dict,
                     resolution: float) -> List[OverloadHotspot]:
    """Find cells where drone density exceeds overload threshold."""
    hotspots = []
    threshold = thresholds["overload_threshold"]
    ys, xs = np.where(density >= threshold)
    for y, x in zip(ys, xs):
        hotspots.append(OverloadHotspot(
            grid_x=int(x), grid_y=int(y),
            world_x=float(x * resolution + resolution / 2),
            world_y=float(y * resolution + resolution / 2),
            drone_count=int(density[y, x]),
            severity=float(min(1.0, density[y, x] / (threshold * 2)))
        ))
    return hotspots


def _identify_core_candidates(drones: List[Drone], adj: np.ndarray) -> List[str]:
    """
    Identify protected-core candidates: drones with high connectivity
    and command/relay roles that should remain frozen during adaptation.
    """
    candidates = []
    neighbour_counts = adj.sum(axis=1)
    median_neighbours = np.median(neighbour_counts) if len(drones) > 0 else 0
    
    for i, d in enumerate(drones):
        if d.role in ("command", "relay"):
            candidates.append(d.id)
        elif neighbour_counts[i] >= median_neighbours * 1.5:
            candidates.append(d.id)
    
    return candidates


def _classify(score: float, components: GSMComponents, 
              n_components: int, n_drones: int) -> Formation:
    """
    Classify the formation based on GSM score and components.
    Decision logic mirrors the spatial substrate classifications.
    Penalises disconnected groups and overload.
    """
    if n_drones < 3:
        return Formation.DORMANT
    if components.amplitude < 0.5:
        return Formation.DORMANT
    
    # Connectivity penalty: multiple disconnected groups = fragile or edge
    if n_components > 2 and components.topology < 0.6:
        return Formation.FRAGILE
    
    if components.core_radius < 0.3 and components.topology < 0.5:
        return Formation.FRAGILE
    if score < 0.5:
        return Formation.FRAGILE
    if score < 0.8:
        return Formation.EDGE
    
    # High score — distinguish AMPLIFYING (compact+connected) from RESILIENT (spread)
    if n_components == 1 and components.topology > 0.85 and components.core_radius > 0.6:
        return Formation.AMPLIFYING
    if n_components > 1:
        # Disconnected but high score = EDGE (overload-driven score inflation)
        return Formation.EDGE
    if components.topology > 0.7 and score >= 0.8:
        return Formation.RESILIENT
    if score >= 1.0 and components.amplitude > 1.0 and n_components == 1:
        return Formation.AMPLIFYING
    return Formation.EDGE


def _generate_report(result: GSMResult) -> GSMResult:
    """Generate human-readable strengths, weaknesses, recommendations."""
    c = result.components
    
    # Strengths
    if c.topology > 0.85:
        result.strengths.append("Strong connected topology — high rerouting potential")
    if c.amplitude > 1.5:
        result.strengths.append("High peak density — fast local ignition")
    if c.core_radius > 1.0:
        result.strengths.append("Thick core — resists fragmentation under disruption")
    if c.concentrated_mass > 1.2:
        result.strengths.append("High concentrated payload — substantial mission capacity")
    if not result.overload_hotspots:
        result.strengths.append("No overload zones detected")
    if result.connected_components == 1:
        result.strengths.append("Fully connected — single communication graph")
    
    # Weaknesses
    if c.amplitude < 0.5:
        result.weaknesses.append("Below activation threshold — formation unlikely to sustain coordination")
    if c.core_radius < 0.4:
        result.weaknesses.append("Thin core — vulnerable to immediate fragmentation")
    if c.topology < 0.5:
        result.weaknesses.append("Poor connectivity — large isolated fragments")
    if c.concentrated_mass < 0.5:
        result.weaknesses.append("Low concentrated payload — insufficient mission capacity in core")
    if result.connected_components > 2:
        result.weaknesses.append(f"{result.connected_components} disconnected groups — comms gaps")
    if len(result.overload_hotspots) > 0:
        result.weaknesses.append(f"{len(result.overload_hotspots)} overload hotspot(s) — collision/congestion risk")
    
    # Recommendations
    if c.core_radius < 0.6 and c.amplitude > 0.5:
        result.recommendations.append("Move peripheral drones inward to thicken the core")
    if result.connected_components > 1:
        result.recommendations.append("Add relay drone(s) to bridge disconnected groups")
    if len(result.overload_hotspots) > 0:
        result.recommendations.append("Spread drones from overloaded cells to neighbouring positions")
    if c.amplitude < 0.8 and result.drone_count > 5:
        result.recommendations.append("Concentrate drones closer to target zones for higher peak density")
    if not result.protected_core_candidates:
        result.recommendations.append("Designate at least one drone as command/relay core")
    if c.topology < 0.7 and c.core_radius > 0.5:
        result.recommendations.append("Reposition outlier drones within comms range of the main cluster")
    
    if not result.weaknesses:
        result.strengths.append("No critical weaknesses detected")
    if not result.recommendations:
        result.recommendations.append("Formation is viable — proceed to launch")
    
    return result


# ═══════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════

def score_formation(
    drones: List[Drone],
    mission: Mission,
    weights: dict = None,
    thresholds: dict = None
) -> GSMResult:
    """
    Score a swarm formation using the Good Seed Metric.
    
    This is a pre-simulation structural heuristic.
    It does not guarantee mission success.
    It is strongest in dense, spatially coupled regimes.
    
    Args:
        drones: List of Drone objects with positions and parameters
        mission: Mission parameters (area size, grid resolution, obstacles)
        weights: GSM component weights (default: validated ordering)
        thresholds: Activation thresholds (default: general swarm values)
    
    Returns:
        GSMResult with score, classification, diagnostics, and recommendations.
    """
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    
    # Step 1: Rasterize positions onto grid
    density, battery = _rasterize(drones, mission)
    density = _apply_obstacles(density, mission.obstacles, mission.grid_resolution)
    
    # Step 2: Compute GSM components
    A = _compute_amplitude(density, t)
    R, core_mask = _compute_core_radius(density, t)
    M = _compute_mass(density, battery, core_mask, t)
    
    # Step 3: Build connectivity graph
    adj = _build_adjacency(drones)
    n_comp, components = _connected_components(adj)
    largest_size = max(len(c) for c in components) if components else 0
    T = _compute_topology(adj, n_comp, components, len(drones))
    
    # Step 4: Gradient diagnostic
    G_raw = _compute_gradient(density, core_mask)
    G = G_raw / (G_raw + 1.0) if G_raw > 0 else 0.0  # normalise to [0,1)
    
    # Step 5: Composite score
    gsm_components = GSMComponents(
        amplitude=round(A, 3),
        core_radius=round(R, 3),
        concentrated_mass=round(M, 3),
        topology=round(T, 3),
        gradient=round(G, 3),
    )
    
    score = (
        w["wA"] * A +
        w["wR"] * R +
        w["wM"] * M +
        w["wT"] * T +
        w["wG"] * G
    )
    score = round(score, 3)
    
    # Step 6: Classify
    classification = _classify(score, gsm_components, n_comp, len(drones))
    
    # Step 7: Detect overload
    overload_hotspots = _detect_overload(density, t, mission.grid_resolution)
    
    # Step 8: Identify protected-core candidates
    core_candidates = _identify_core_candidates(drones, adj)
    
    # Step 9: Build overload map
    overload_map = (density >= t["overload_threshold"]).astype(np.float32)
    
    # Step 10: Connectivity map (neighbour count per cell)
    conn_map = np.zeros_like(density)
    neighbour_counts = adj.sum(axis=1)
    for i, d in enumerate(drones):
        gx = int(np.clip(d.x / mission.grid_resolution, 0, conn_map.shape[1] - 1))
        gy = int(np.clip(d.y / mission.grid_resolution, 0, conn_map.shape[0] - 1))
        conn_map[gy, gx] = max(conn_map[gy, gx], neighbour_counts[i])
    
    # Assemble result
    gw = density.shape[1]
    gh = density.shape[0]
    total_cells = gw * gh
    
    result = GSMResult(
        score=score,
        classification=classification,
        components=gsm_components,
        drone_count=len(drones),
        density=len(drones) / total_cells if total_cells > 0 else 0,
        connected_components=n_comp,
        largest_component_size=largest_size,
        overload_hotspots=overload_hotspots,
        protected_core_candidates=core_candidates,
        density_map=density,
        connectivity_map=conn_map,
        overload_map=overload_map,
    )
    
    # Generate human-readable report
    result = _generate_report(result)
    
    return result
