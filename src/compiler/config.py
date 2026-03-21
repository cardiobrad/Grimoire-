"""
config.py — Calibrated thresholds and weights for the Swarm Deployment Compiler.

CALIBRATION HISTORY:
  v0.1 (2026-03-17)
    - A_c lowered from 2.0 to 1.0
      Reason: 5m grid means most cells hold 0 or 1 drone.
      At A_c=2.0, even a well-formed 20-drone cluster scored FRAGILE
      because peak density rarely exceeded 2 drones/cell.
      A_c=1.0 means "at least one drone present" = activated.
    - R_c lowered from 3.0 to 2.0
      Reason: at 5m resolution, a 20-drone cluster spans ~5 cells radius.
      R_c=3.0 was calibrated for the 64x64 validation grid (1m cells).
      R_c=2.0 matches the coarser swarm grid.
    - M_c lowered from 10.0 to 8.0
      Reason: battery-weighted mass in a 20-drone cluster with 0.7-1.0
      battery typically sums to 8-15. M_c=10 was too strict.
    - overload_threshold lowered from 5 to 4
      Reason: in a 5m cell, 4+ drones = genuine congestion risk.
    - wT raised from 0.15 to 0.20, wG lowered from 0.05 to 0.05 (unchanged)
      Reason: topology (connectivity) is more critical than gradient
      smoothness for swarm viability. Connected > smooth.

USAGE:
  These thresholds are domain-dependent hyperparameters.
  They MUST be recalibrated for:
    - Different grid resolutions (2m vs 5m vs 10m)
    - Different comms radii
    - Different mission types
    - Different swarm sizes
  
  The scaling ansatz from Appendix B of the paper provides principled
  recalibration: A_c ~ 1/alpha, R_c ~ sqrt(D/lambda), M_c ~ (1/alpha)(D/lambda).
  But for swarm ops, empirical tuning per domain is the practical path.
"""

# ═══════════════════════════════════════════════════════════════
# GSM Component Weights
# Ordering: wA > wR >= wT > wM > wG
# Reflects validated causal chain from spatial substrate
# ═══════════════════════════════════════════════════════════════
WEIGHTS = {
    "wA": 0.30,   # amplitude — peak density, ignition threshold
    "wR": 0.25,   # core radius — thickness, fragmentation resistance
    "wM": 0.20,   # concentrated mass — battery-weighted payload
    "wT": 0.20,   # topology — connectivity, rerouting potential
    "wG": 0.05,   # gradient — boundary smoothness (secondary)
}

# ═══════════════════════════════════════════════════════════════
# Activation Thresholds
# ═══════════════════════════════════════════════════════════════
THRESHOLDS = {
    "A_c": 1.0,    # min peak drones/cell for activation
    "R_c": 2.0,    # min core radius (grid cells) for stability
    "M_c": 8.0,    # min concentrated mass for viability
    "T_c": 0.7,    # min connectivity ratio for resilience
    "overload_threshold": 4,   # drones/cell triggering overload
    "comms_min_neighbours": 2, # min neighbours for relay candidacy
}

# ═══════════════════════════════════════════════════════════════
# Grid Defaults
# ═══════════════════════════════════════════════════════════════
DEFAULT_GRID_RESOLUTION = 5.0   # metres per cell
DEFAULT_AREA_WIDTH = 200.0      # metres
DEFAULT_AREA_HEIGHT = 200.0     # metres

# ═══════════════════════════════════════════════════════════════
# Launch Recommendation Mapping
# ═══════════════════════════════════════════════════════════════
LAUNCH_MAP = {
    "AMPLIFYING": "PROCEED",
    "RESILIENT":  "PROCEED",
    "EDGE CASE":  "PROCEED WITH CAUTION",
    "FRAGILE":    "RESEED BEFORE LAUNCH",
    "DORMANT":    "RESEED BEFORE LAUNCH",
}
