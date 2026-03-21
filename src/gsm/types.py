"""
gsm_swarm — Swarm Deployment Compiler Lite
Good Seed Metric for drone/robot swarm formations.

Score the seed before you fly.
A swarm is not a field until density makes it one.

Based on: "From Spatial Substrate to Game Engine" (Edwards, 2026)
Validated at 0.996 AUC on the spatial substrate.
Adapted for swarm deployment pre-flight scoring.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple
import numpy as np


class Formation(Enum):
    """Seed viability classification."""
    DORMANT = "DORMANT"         # Below threshold — will fragment
    FRAGILE = "FRAGILE"         # Has peak but too thin — dies under mild disruption
    EDGE = "EDGE CASE"          # Near threshold — sensitive to perturbation
    AMPLIFYING = "AMPLIFYING"   # Strong compact seed — rapid local coordination
    RESILIENT = "RESILIENT"     # Connected, spread — slower start, better persistence


@dataclass
class Drone:
    """Single drone/robot agent."""
    id: str
    x: float
    y: float
    z: float = 0.0
    battery: float = 1.0        # 0.0–1.0 normalised
    comms_radius: float = 50.0  # metres
    sensor_radius: float = 30.0 # metres
    role: str = "worker"        # worker | relay | command


@dataclass
class Obstacle:
    """Rectangular obstacle in the operating area."""
    x: float
    y: float
    width: float
    height: float


@dataclass
class Mission:
    """Mission parameters."""
    area_width: float = 200.0   # metres
    area_height: float = 200.0
    grid_resolution: float = 5.0  # metres per cell
    target_zones: List[Tuple[float, float, float]] = field(default_factory=list)  # (x, y, radius)
    obstacles: List[Obstacle] = field(default_factory=list)


@dataclass
class GSMComponents:
    """Individual GSM component scores (unnormalised)."""
    amplitude: float        # A — peak local density / activation
    core_radius: float      # R — thickness of suprathreshold core
    concentrated_mass: float  # M — usable payload in viable region
    topology: float         # T — connectivity / largest component ratio
    gradient: float         # G — boundary smoothness


@dataclass
class OverloadHotspot:
    """A detected overload zone."""
    grid_x: int
    grid_y: int
    world_x: float
    world_y: float
    drone_count: int
    severity: float  # 0.0–1.0


@dataclass
class GSMResult:
    """Complete output of a seed scoring pass."""
    score: float
    classification: Formation
    components: GSMComponents
    
    # Diagnostics
    drone_count: int
    density: float                    # drones per grid cell
    connected_components: int
    largest_component_size: int
    overload_hotspots: List[OverloadHotspot]
    protected_core_candidates: List[str]  # drone IDs
    
    # Maps (numpy arrays)
    density_map: Optional[np.ndarray] = None
    connectivity_map: Optional[np.ndarray] = None
    overload_map: Optional[np.ndarray] = None
    
    # Recommendations
    weaknesses: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
