# TINWALL → GRIMOIRE Enhanced (Safe Fork)

This folder is a standalone enhancement fork. Original repo files remain untouched.

## Phase 1 (now): polished GRIMOIRE-integrated TINWALL fork

1. Copy `game/tinwall-v10.html` into this folder as a safe working fork.
2. Add separate enhancement layer files (`enhanced.css`, `enhanced.js`) so core legacy gameplay remains stable.
3. Run GRIMOIRE PDE in the background with locked constants from validated model:
   - `D = 0.12`
   - `lambda = 0.45`
   - `alpha = π`
   - update equation: `U(t+dt)=max(0,U+dt*(D∇²U + lambda*U²*sin(alpha*U) + Γ(U)))`
4. Bind GSM scoring to selected units and expose **Score the Seed First** action.
5. Render heatmap overlay (terraces + seed intensity + amplifying hotspots) for tactical readability.
6. Add high-contrast modern panel styling and seed pulse particles to increase visual quality.
7. Keep feature toggle-friendly architecture so Godot migration can preserve gameplay semantics.

## Phase 2+ roadmap to TA/BAR-scale battles

1. Extract canonical GRIMOIRE core into language-agnostic tests + fixtures.
2. Port game client to Godot 4.3+ (2.5D tactical renderer + GPU overlay shader).
3. Convert units/buildings to ECS for large-scale simulation.
4. Add commander-style economy and long-range production chains.
5. Massive-map streaming + LOD + deterministic lockstep multiplayer.
6. Keep GSM as strategic doctrine system (opening viability, adaptive reinforcement logic).
7. Keep PDE substrate as hidden battlefield influence for pathing, morale, and local combat bias.

## 2026 stack recommendation (preferred)

- **Primary client**: Godot 4.3+ (Forward+ renderer, CanvasItem shaders for overlays, AnimationTree, particles)
- **Core simulation**: shared GRIMOIRE core library + test fixtures (Python reference + GDExtension/C# port)
- **Networking (later)**: deterministic lockstep + rollback instrumentation
- **Tooling**: scenario editor + heatmap debug panes + replay recorder

This fork remains HTML5 for speed while shaping the exact gameplay contract for the Godot production version.
