"""
gsm_swarm.viz — Visualization for swarm deployment scoring.
Generates heatmaps, connectivity graphs, and formation quality plots.
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle
from matplotlib.colors import LinearSegmentedColormap
from typing import List, Optional
from .types import Drone, Mission, GSMResult, Formation


# Custom colourmap: black → red → orange → green → cyan
_COLORS = ["#0a0605", "#cc2200", "#ff8800", "#44cc44", "#44aaff"]
GSM_CMAP = LinearSegmentedColormap.from_list("gsm", _COLORS, N=256)

# Classification colours
CLASS_COLORS = {
    Formation.DORMANT: "#664400",
    Formation.FRAGILE: "#cc4400",
    Formation.EDGE: "#ccaa00",
    Formation.AMPLIFYING: "#44cc44",
    Formation.RESILIENT: "#44aaff",
}


def plot_formation(
    drones: List[Drone],
    mission: Mission,
    result: GSMResult,
    output_path: str = "formation_report.png",
    title: str = "Swarm Deployment Compiler — Seed Score"
):
    """
    Generate a complete formation analysis plot.
    4-panel layout: density heatmap, connectivity, overload, score card.
    """
    fig, axes = plt.subplots(2, 2, figsize=(14, 12), facecolor="#0a0a1a")
    fig.suptitle(title, color="white", fontsize=16, fontweight="bold", y=0.98)
    
    res = mission.grid_resolution
    
    # ── Panel 1: Density Heatmap ──
    ax1 = axes[0, 0]
    ax1.set_facecolor("#0a0a1a")
    if result.density_map is not None:
        im1 = ax1.imshow(
            result.density_map, cmap=GSM_CMAP, origin="lower",
            extent=[0, mission.area_width, 0, mission.area_height],
            interpolation="nearest", vmin=0
        )
        plt.colorbar(im1, ax=ax1, label="Drones/cell", shrink=0.8)
    
    # Plot drone positions
    for d in drones:
        color = "#44aaff" if d.role == "command" else "#44cc44" if d.role == "relay" else "#ffffff"
        marker = "D" if d.role == "command" else "^" if d.role == "relay" else "o"
        ax1.plot(d.x, d.y, marker, color=color, markersize=6, markeredgecolor="#000", markeredgewidth=0.5)
    
    # Plot obstacles
    for obs in mission.obstacles:
        ax1.add_patch(Rectangle(
            (obs.x, obs.y), obs.width, obs.height,
            facecolor="#333333", edgecolor="#666666", linewidth=1
        ))
    
    # Plot target zones
    for tx, ty, tr in mission.target_zones:
        ax1.add_patch(Circle(
            (tx, ty), tr, fill=False, edgecolor="#ff4444", linewidth=1.5, linestyle="--"
        ))
    
    ax1.set_title("Density Heatmap + Positions", color="white", fontsize=11)
    ax1.set_xlabel("x (m)", color="#888")
    ax1.set_ylabel("y (m)", color="#888")
    ax1.tick_params(colors="#666")
    
    # ── Panel 2: Connectivity Graph ──
    ax2 = axes[0, 1]
    ax2.set_facecolor("#0a0a1a")
    
    # Draw comms links
    for i, d1 in enumerate(drones):
        for j, d2 in enumerate(drones):
            if j <= i:
                continue
            dist = np.sqrt((d1.x - d2.x)**2 + (d1.y - d2.y)**2 + (d1.z - d2.z)**2)
            if dist <= min(d1.comms_radius, d2.comms_radius):
                ax2.plot([d1.x, d2.x], [d1.y, d2.y], color="#335566", linewidth=0.8, alpha=0.6)
    
    # Draw drones coloured by battery
    for d in drones:
        bat_color = plt.cm.RdYlGn(d.battery)
        ax2.plot(d.x, d.y, "o", color=bat_color, markersize=7, markeredgecolor="#000", markeredgewidth=0.5)
        # Comms radius circle
        ax2.add_patch(Circle(
            (d.x, d.y), d.comms_radius, fill=False, 
            edgecolor="#224455", linewidth=0.4, alpha=0.3
        ))
    
    ax2.set_xlim(0, mission.area_width)
    ax2.set_ylim(0, mission.area_height)
    ax2.set_title(f"Connectivity ({result.connected_components} component{'s' if result.connected_components != 1 else ''})",
                  color="white", fontsize=11)
    ax2.set_xlabel("x (m)", color="#888")
    ax2.set_ylabel("y (m)", color="#888")
    ax2.tick_params(colors="#666")
    ax2.set_aspect("equal")
    
    # ── Panel 3: Overload Map ──
    ax3 = axes[1, 0]
    ax3.set_facecolor("#0a0a1a")
    if result.overload_map is not None:
        im3 = ax3.imshow(
            result.overload_map, cmap="YlOrRd", origin="lower",
            extent=[0, mission.area_width, 0, mission.area_height],
            interpolation="nearest", vmin=0, vmax=1
        )
        plt.colorbar(im3, ax=ax3, label="Overload severity", shrink=0.8)
    
    # Mark hotspots
    for hs in result.overload_hotspots:
        ax3.plot(hs.world_x, hs.world_y, "x", color="#ff0000", markersize=12, markeredgewidth=2)
    
    ax3.set_title(f"Overload Map ({len(result.overload_hotspots)} hotspot{'s' if len(result.overload_hotspots) != 1 else ''})",
                  color="white", fontsize=11)
    ax3.set_xlabel("x (m)", color="#888")
    ax3.set_ylabel("y (m)", color="#888")
    ax3.tick_params(colors="#666")
    
    # ── Panel 4: Score Card ──
    ax4 = axes[1, 1]
    ax4.set_facecolor("#0a0a1a")
    ax4.axis("off")
    
    cls_color = CLASS_COLORS.get(result.classification, "#888888")
    
    # Big score
    ax4.text(0.5, 0.92, f"{result.score:.2f}", transform=ax4.transAxes,
             fontsize=52, fontweight="bold", color=cls_color, ha="center", va="top",
             fontfamily="monospace")
    ax4.text(0.5, 0.78, result.classification.value, transform=ax4.transAxes,
             fontsize=24, fontweight="bold", color=cls_color, ha="center", va="top")
    
    # Component bars
    comp_names = ["Amplitude", "Core Radius", "Mass", "Topology", "Gradient"]
    comp_vals = [result.components.amplitude, result.components.core_radius,
                 result.components.concentrated_mass, result.components.topology,
                 result.components.gradient]
    
    y_start = 0.62
    for i, (name, val) in enumerate(zip(comp_names, comp_vals)):
        y = y_start - i * 0.08
        ax4.text(0.05, y, name, transform=ax4.transAxes, fontsize=10, color="#888888", va="center")
        ax4.text(0.95, y, f"{val:.2f}", transform=ax4.transAxes, fontsize=10, 
                 color="#cccccc", va="center", ha="right", fontfamily="monospace")
        # Bar
        bar_width = min(val / 2.0, 1.0) * 0.45
        bar_color = "#44cc44" if val > 0.8 else "#ccaa00" if val > 0.4 else "#cc4400"
        ax4.barh(y, bar_width, height=0.025, left=0.42, transform=ax4.transAxes,
                 color=bar_color, alpha=0.7)
    
    # Stats
    stats_y = 0.18
    stats = [
        f"Drones: {result.drone_count}",
        f"Components: {result.connected_components}",
        f"Core candidates: {len(result.protected_core_candidates)}",
        f"Overload zones: {len(result.overload_hotspots)}",
    ]
    for i, s in enumerate(stats):
        ax4.text(0.05, stats_y - i * 0.05, s, transform=ax4.transAxes,
                 fontsize=9, color="#666666")
    
    # Recommendations
    if result.recommendations:
        ax4.text(0.55, stats_y, "Recommendations:", transform=ax4.transAxes,
                 fontsize=9, color="#ccaa00", fontweight="bold")
        for i, rec in enumerate(result.recommendations[:3]):
            ax4.text(0.55, stats_y - (i + 1) * 0.045, f"• {rec[:45]}",
                     transform=ax4.transAxes, fontsize=8, color="#888888")
    
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    plt.savefig(output_path, dpi=150, facecolor="#0a0a1a", bbox_inches="tight")
    plt.close()
    return output_path


def print_report(result: GSMResult):
    """Print a text-based seed score report to stdout."""
    cls_name = result.classification.value
    bar = "█" * int(min(result.score, 2.0) * 20) + "░" * (40 - int(min(result.score, 2.0) * 20))
    
    print(f"\n{'═' * 56}")
    print(f"  SWARM DEPLOYMENT COMPILER — SEED SCORE")
    print(f"{'═' * 56}")
    print(f"  Score:  {result.score:.3f}  [{bar}]")
    print(f"  Class:  {cls_name}")
    print(f"{'─' * 56}")
    print(f"  Components:")
    print(f"    Amplitude (A):        {result.components.amplitude:.3f}")
    print(f"    Core Radius (R):      {result.components.core_radius:.3f}")
    print(f"    Concentrated Mass (M):{result.components.concentrated_mass:.3f}")
    print(f"    Topology (T):         {result.components.topology:.3f}")
    print(f"    Gradient (G):         {result.components.gradient:.3f}")
    print(f"{'─' * 56}")
    print(f"  Drones:              {result.drone_count}")
    print(f"  Connected groups:    {result.connected_components}")
    print(f"  Largest group:       {result.largest_component_size}")
    print(f"  Core candidates:     {len(result.protected_core_candidates)}")
    print(f"  Overload hotspots:   {len(result.overload_hotspots)}")
    print(f"{'─' * 56}")
    
    if result.strengths:
        print(f"  ✅ Strengths:")
        for s in result.strengths:
            print(f"     + {s}")
    
    if result.weaknesses:
        print(f"  ⚠️  Weaknesses:")
        for w in result.weaknesses:
            print(f"     - {w}")
    
    if result.recommendations:
        print(f"  💡 Recommendations:")
        for r in result.recommendations:
            print(f"     → {r}")
    
    print(f"{'═' * 56}\n")
