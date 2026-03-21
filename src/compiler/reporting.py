"""
reporting.py — Human-readable output for the Swarm Deployment Compiler.
"""

from typing import Dict, Any, List


def generate_why_report(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate strengths, weaknesses, and recommendations from scored result.
    Returns dict with keys: strengths, weaknesses, recommendations, reason.
    """
    c = result["components"]
    n_comp = result["connectivity"]["total_components"]
    cls = result["classification"]
    hotspots = result["overload"]["hotspot_count"]
    
    strengths = []
    weaknesses = []
    recommendations = []
    
    # ── Strengths ──
    if c["topology"] > 0.85:
        strengths.append("Strong connected topology — high rerouting potential")
    if c["amplitude"] > 1.5:
        strengths.append("High peak density — fast local ignition")
    if c["core_radius"] > 1.0:
        strengths.append("Thick core — resists fragmentation under disruption")
    if c["concentrated_mass"] > 1.2:
        strengths.append("High concentrated payload — substantial mission capacity")
    if hotspots == 0:
        strengths.append("No overload zones detected")
    if n_comp == 1:
        strengths.append("Fully connected — single communication graph")
    
    # ── Weaknesses ──
    if c["amplitude"] < 0.5:
        weaknesses.append("Below activation threshold — formation unlikely to sustain coordination")
    if c["core_radius"] < 0.4:
        weaknesses.append("Thin core — vulnerable to immediate fragmentation")
    if c["topology"] < 0.5:
        weaknesses.append("Poor connectivity — large isolated fragments")
    if c["concentrated_mass"] < 0.5:
        weaknesses.append("Low concentrated payload — insufficient mission capacity in core")
    if n_comp > 2:
        weaknesses.append(f"{n_comp} disconnected groups — comms gaps")
    if hotspots > 0:
        weaknesses.append(f"{hotspots} overload hotspot(s) — collision/congestion risk")
    
    # ── Recommendations ──
    if c["core_radius"] < 0.6 and c["amplitude"] > 0.5:
        recommendations.append("Move peripheral drones inward to thicken the core")
    if n_comp > 1:
        recommendations.append("Add relay drone(s) to bridge disconnected groups")
    if hotspots > 0:
        recommendations.append("Spread drones from overloaded cells to neighbouring positions")
    if c["amplitude"] < 0.8 and result["drone_count"] > 5:
        recommendations.append("Concentrate drones closer to target zone for higher peak density")
    if not result["protected_core_candidates"]:
        recommendations.append("Designate at least one drone as command/relay core")
    if c["topology"] < 0.7 and c["core_radius"] > 0.5:
        recommendations.append("Reposition outlier drones within comms range of main cluster")
    
    if not weaknesses:
        strengths.append("No critical weaknesses detected")
    if not recommendations:
        recommendations.append("Formation is viable — proceed to launch")
    
    # ── One-line reason ──
    if cls == "AMPLIFYING":
        reason = "compact core, high coherence, low overload risk"
    elif cls == "RESILIENT":
        reason = "spread but well-connected, good persistence and coverage"
    elif cls == "EDGE CASE":
        reason = "near threshold — review recommendations before proceeding"
    elif cls == "FRAGILE":
        reason = "formation will fragment under mild disruption"
    else:
        reason = "below activation threshold — restructure completely"
    
    return {
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendations": recommendations,
        "reason": reason,
    }


def print_report(result: Dict[str, Any]):
    """Print a formatted seed score report to stdout."""
    c = result["components"]
    why = result["why"]
    cls = result["classification"]
    launch = result["launch_recommendation"]
    
    bar_len = 40
    score_pct = min(result["score"] / 2.0, 1.0)
    filled = int(score_pct * bar_len)
    bar = "\u2588" * filled + "\u2591" * (bar_len - filled)
    
    print(f"\n{'=' * 60}")
    print(f"  SWARM DEPLOYMENT COMPILER \u2014 SEED SCORE")
    print(f"{'=' * 60}")
    print(f"  Scenario:  {result['scenario']}")
    print(f"  Score:     {result['score']:.3f}  [{bar}]")
    print(f"  Class:     {cls}")
    print(f"  Launch:    {launch}")
    print(f"  Reason:    {why['reason']}")
    print(f"{'─' * 60}")
    print(f"  Components:")
    print(f"    Amplitude (A):          {c['amplitude']:.3f}")
    print(f"    Core Radius (R):        {c['core_radius']:.3f}")
    print(f"    Concentrated Mass (M):  {c['concentrated_mass']:.3f}")
    print(f"    Topology (T):           {c['topology']:.3f}")
    print(f"    Gradient (G):           {c['gradient']:.3f}")
    print(f"{'─' * 60}")
    print(f"  Drones:              {result['drone_count']}")
    print(f"  Connected groups:    {result['connectivity']['total_components']}")
    print(f"  Largest group:       {result['connectivity']['largest_component']}")
    print(f"  Core candidates:     {len(result['protected_core_candidates'])}")
    print(f"  Overload hotspots:   {result['overload']['hotspot_count']}")
    print(f"{'─' * 60}")
    
    if why["strengths"]:
        print(f"  \u2705 Strengths:")
        for s in why["strengths"]:
            print(f"     + {s}")
    
    if why["weaknesses"]:
        print(f"  \u26a0\ufe0f  Weaknesses:")
        for w in why["weaknesses"]:
            print(f"     - {w}")
    
    if why["recommendations"]:
        print(f"  \U0001f4a1 Recommendations:")
        for r in why["recommendations"]:
            print(f"     \u2192 {r}")
    
    print(f"{'=' * 60}\n")
