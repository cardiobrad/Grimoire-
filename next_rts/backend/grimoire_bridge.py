"""Bridge layer that reuses the existing GRIMOIRE PDE + GSM logic without rewriting formulas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from src.simulator import simulator
from src.gsm.scorer import score_formation
from src.gsm.types import Drone, Mission


@dataclass
class FieldConfig:
    grid: int = simulator.GRID
    dt: float = simulator.DT
    diffusion: float = simulator.D
    lam: float = simulator.LAM
    alpha: float = float(simulator.ALPHA)


class GrimoireCore:
    """Thin adapter over locked modules in src/simulator and src/gsm."""

    def __init__(self, grid_size: int | None = None):
        self.grid = grid_size or simulator.GRID
        self.field = np.zeros((self.grid, self.grid), dtype=np.float64)
        self.config = FieldConfig(grid=self.grid)

    def reset(self) -> None:
        self.field = np.zeros((self.grid, self.grid), dtype=np.float64)

    def inject_seed(self, points: list[tuple[float, float]], energy: float = 0.6) -> np.ndarray:
        for x, y in points:
            gx = int(np.clip(round(x), 0, self.grid - 1))
            gy = int(np.clip(round(y), 0, self.grid - 1))
            self.field[gy, gx] = min(self.field[gy, gx] + energy, 5.0)
        return self.field

    def step(self, substeps: int = simulator.PDE_SUBSTEPS) -> np.ndarray:
        for _ in range(substeps):
            self.field = simulator.step_pde(self.field)
        return self.field

    def score_seed(self, units: list[dict[str, Any]], mission: Mission | None = None) -> dict[str, Any]:
        mission = mission or Mission()
        drones = [
            Drone(
                id=u.get("id", f"unit-{i}"),
                x=float(u["x"]),
                y=float(u["y"]),
                role=u.get("role", "worker"),
                battery=float(u.get("battery", 1.0)),
                comms_radius=float(u.get("comms_radius", 50.0)),
            )
            for i, u in enumerate(units)
        ]
        result = score_formation(drones=drones, mission=mission)
        return {
            "score": result.score,
            "classification": result.classification.value,
            "components": {
                "amplitude": result.components.amplitude,
                "core_radius": result.components.core_radius,
                "concentrated_mass": result.components.concentrated_mass,
                "topology": result.components.topology,
                "gradient": result.components.gradient,
            },
            "strengths": result.strengths,
            "weaknesses": result.weaknesses,
            "recommendations": result.recommendations,
            "overload_hotspots": [hotspot.__dict__ for hotspot in result.overload_hotspots],
        }
