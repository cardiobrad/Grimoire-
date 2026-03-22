"""Minimal API for the standalone GRIMOIRE RTS prototype."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .grimoire_bridge import GrimoireCore


class SeedPoint(BaseModel):
    x: float
    y: float


class Unit(BaseModel):
    id: str | None = None
    x: float
    y: float
    role: str = "worker"
    battery: float = 1.0
    comms_radius: float = 50.0


class SeedPayload(BaseModel):
    points: list[SeedPoint]
    units: list[Unit]


app = FastAPI(title="GRIMOIRE RTS Prototype")
core = GrimoireCore()

frontend_dir = Path(__file__).resolve().parents[1] / "frontend"
app.mount("/static", StaticFiles(directory=frontend_dir), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(frontend_dir / "index.html")


@app.post("/api/seed/score")
def score_seed(payload: SeedPayload) -> dict[str, Any]:
    core.reset()
    core.inject_seed([(p.x, p.y) for p in payload.points])
    gsm = core.score_seed([u.model_dump() for u in payload.units])
    return {"gsm": gsm, "field": core.field.tolist()}


@app.post("/api/field/step")
def step_field() -> dict[str, Any]:
    field = core.step()
    max_val = float(field.max()) if field.size > 0 else 0.0
    return {"field": field.tolist(), "max": max_val}
