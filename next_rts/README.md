# GRIMOIRE RTS (Standalone) — Phase 0 Bootstrap

This folder starts a **new standalone RTS-style game** while preserving the existing validated mechanics:

- Locked PDE kernel from `src/simulator/simulator.py`
- Locked GSM scoring from `src/gsm/scorer.py`
- Existing formation classes and diagnostics

## Why this bootstrap exists

Phase 0 creates a professional-feeling prototype loop:

1. Player seeds units.
2. Clicks **Score Seed First**.
3. Sees GSM class + recommendations.
4. Watches hidden field evolve as heatmap.

## Quick start

```bash
pip install fastapi uvicorn numpy scipy
uvicorn next_rts.backend.server:app --reload
```

Open `http://127.0.0.1:8000`.

## Folder map

- `backend/grimoire_bridge.py` — adapter that calls existing PDE + GSM modules.
- `backend/server.py` — API + static hosting.
- `frontend/` — polished seed console with heatmap and GSM pane.

## Phase roadmap (high-level)

- **Phase 1**: ECS units + command system + minimap + battle sandbox.
- **Phase 2**: Full terrain and terrace generation from PDE layers.
- **Phase 3**: Campaign and faction asymmetry encoded as seed doctrines.
- **Phase 4**: Mod kit and scenario editor.
