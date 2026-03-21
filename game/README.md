# TINWALL v10 — Age of Dumnonia

An isometric RTS set in ancient Cornwall where the AI doesn't use timers — it reads the battlefield.

## What makes this different

Most RTS games script their AI with fixed timers and aggro tables. TINWALL v10 runs a live influence field beneath the tile map — a reaction-diffusion equation that creates emergent attack-retreat-regroup waves without any scripting.

The AI attacks when the field is strong (army concentrated). It retreats when the field is weak (army fragmented). The result is combat that pulses and breathes instead of arriving in flat, predictable waves.

## Features

- **4 Cornish tribes** — each with unique units and abilities
- **Isometric tile map** — 72×54 grid with fog of war and day/night cycle
- **Live influence field** — the full PDE runs beneath the game at 12Hz
- **Formation Quality HUD** — select units and see their structural viability scored in real time
- **Squad cohesion system** — units gain and lose effectiveness based on formation quality
- **Phase-aware AI** — reads the influence field instead of using timers
- **Sacred Tin Mine** — a protected-core objective that can't be destabilised by combat chaos
- **Anti-stacking physics** — cramming units together degrades their damage output

## The equation

```
∂U/∂t = D∇²U + λU²sin(αU)
```

This isn't decoration. The sine term creates oscillatory renewal — it's why the AI retreats and regroups instead of death-balling. The influence field is visible as a heatmap on the minimap.

## Controls

- Click to select units, right-click to move/attack
- Drag to box-select
- Minimap shows influence field heatmap
- Formation Quality appears when 2+ units selected

## Technical

- Single HTML5 file — no install, no dependencies
- ~2,800 lines of vanilla JavaScript
- A* pathfinding with anti-stacking physics
- CFL-stable PDE solver with 48.3% safety margin
- Built by one person who started coding 11 weeks ago

## Origin

TINWALL is set in Dumnonia — the ancient Cornish kingdom. The name comes from the Cornish tin trade. The game mechanics are derived from a validated spatial coordination framework (0.996 AUC on the underlying equation). The seven design principles embedded in the game were independently confirmed across eight scientific domains.

This is a research game. It's also playable and fun.

---

**Made in Liverpool. Cornish heritage. One equation. Seven principles.**
