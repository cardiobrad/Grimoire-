# Tech Stack Recommendation (2026)

## Short-term (recommended now): HTML5 Canvas
### Pros
- Fastest iteration on game feel, controls, economy pacing, and combat readability.
- Zero migration overhead while testing addictive loops.
- Easy deployment for rapid playtests.

### Cons
- Harder to scale to very large unit counts with rich visuals.
- Tooling/content pipeline is lighter than game engines.

## Long-term Option A: Godot 4.3+
### Pros
- Excellent 2D/2.5D rendering, lighting, particles, shaders.
- Strong editor workflow for maps/UI/FX.
- Good balance of performance and developer speed.

### Cons
- Requires migration of battle logic and content pipeline.
- Deterministic lockstep multiplayer needs careful architecture.

## Long-term Option B: BAR/Recoil fork (Lua mod stack)
### Pros
- Closest native TA/BAR feel at scale (massive armies, commander macro).
- Mature deterministic RTS patterns and Lua hooks.
- Strong for huge maps and long macro games.

### Cons
- Engine/content complexity is significantly higher.
- Art/asset and licensing boundaries require discipline.

## Migration path (practical)
1. Keep polishing the HTML5 fork until retention/fun loop is strong.
2. Freeze gameplay contracts (commands, economy timings, unit roles).
3. Port to Godot **or** BAR/Recoil based on target scale and team skill.
4. Keep hidden GRIMOIRE as a runtime service/module with parity tests.
