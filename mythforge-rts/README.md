# MYTHFORGE: IRON ECLIPSE

A standalone RTS prototype inspired by Total Annihilation, Red Alert, and Age of Empires.

## Play

```bash
python -m http.server 8000 --directory mythforge-rts
```
Open `http://localhost:8000`.

## Current production-facing features

- Commander-led RTS gameplay loop
- Left-click + drag-box selection
- Smart right-click move/attack/gather commands
- Base building placement (Refinery, Power Core, Barracks, Turret)
- Unit training (Infantry, Siege Tank, Skimmer)
- Metal/Energy economy mapped to macro layer
- Enemy wave pressure + 3-core victory objective
- SFX via WebAudio (command, hit, build, select cues)
- Pause, mute, save/load, hotkeys
- Runtime audit button for integrity checks

## Hidden substrate

The game runs hidden influence modulation in runtime:

- Reaction-diffusion kernel `∂U/∂t = D∇²U + λU²sin(αU)`
- Constants `D=0.12`, `λ=0.45`, `α=π`
- Hidden squad compactness modifier for subtle movement/damage tuning

Player-facing UI stays gameplay-first.
