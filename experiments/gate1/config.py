"""
config.py — Single source of truth for the GSM batch validation pipeline.
"""
from pathlib import Path

OUT_DIR = Path("outputs")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Field parameters (match reproducibility package)
FIELD = {
    "N": 64,
    "dt": 0.05,
    "D": 0.12,
    "lam": 0.45,
    "alpha": 3.141592653589793,
    "steps": 500,
    "positivity_clip": True,
}

# Good Seed Metric thresholds (from good-seed-metric-reference.docx)
GSM = {
    "A_c": 0.25,
    "R_c": 2.5,
    "M_c": 5.0,
    "w_a": 0.35,
    "w_r": 0.25,
    "w_m": 0.20,
    "w_t": 0.15,
    "w_g": 0.05,
}

# Outcome classification thresholds
OUTCOME = {
    "survival_step_frac": 0.8,   # survived if still active at 80% of steps
    "amplify_threshold": 0.05,   # field mean grew by >5%
    "collapse_threshold": 0.01,  # field mean fell below this = collapsed
}

# Seed generation
SEEDS_PER_FAMILY = 50
SEED_RNG_BASE = 1000
TARGET_MASS = 15.0        # total amplitude budget held constant
TARGET_NODES = 12         # node count held constant where possible
AMPLITUDE_PER_NODE = TARGET_MASS / TARGET_NODES

# Topology families
TOPOLOGIES = [
    "line",
    "ring",
    "star",
    "lattice",
    "tree",
    "clustered_islands",
    "erdos_renyi",
    "small_world",
    "scale_free",
]
