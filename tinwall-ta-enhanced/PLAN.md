# tinwall-ta-enhanced — Fresh Execution Plan

## Guardrails
- Work only inside `tinwall-ta-enhanced/`.
- Original repo and original `game/` files are untouched.
- Hidden GRIMOIRE logic stays invisible to players (no science UI/readouts).

## Phase 1 (now): immediate playable RTS feel
1. Start from a full safe copy of TINWALL in this folder.
2. Tighten core RTS input loop: left-click select, drag-box select, right-click command intent.
3. Improve command interpretation priority: attack > gather > build/place > move.
4. Keep base-building and training hotkeys fast and readable.
5. Add polished feedback (command rings, hit sparks, damage floaters, better impact readability).
6. Add macro economy framing with metal/energy style bars (mapped from existing resources for now).
7. Keep commander-centered play loop (anchor unit, rally, pressure, recover).
8. Add hidden GRIMOIRE micro-modulation only in behaviour/pathing/stat nudges.

## Phase 2 (near-term): TA/BAR-style depth
1. Factory queues + rally points + shift command queue.
2. Attack-move/patrol/guard stance set.
3. Larger maps and higher concurrent unit counts.
4. Better target prioritisation and squad cohesion under pressure.
5. Distinct unit roles: raider, skirmisher, artillery, anti-armor.

## Phase 3 (production migration)
1. Keep HTML5 as fast balance sandbox until loops are proven addictive.
2. Migrate to Godot 4.3+ for visual polish and production tooling, OR BAR/Recoil fork for massive deterministic battles.
3. Maintain hidden GRIMOIRE parity tests across runtimes.
