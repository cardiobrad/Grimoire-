#!/usr/bin/env python3
"""
scenarios.py — Run all three demo scenarios and print comparison table.

Usage:
    python scenarios.py
"""

import os
import sys
from swarm_compiler import load_scenario, score
from reporting import print_report


EXAMPLES = [
    "examples/search_rescue.json",
    "examples/surveillance_fragile.json",
    "examples/warehouse_edge_case.json",
]


def main():
    print("\n" + "\u2588" * 60)
    print("  SWARM DEPLOYMENT COMPILER LITE v0.1")
    print("  Good Seed Metric for Drone/Robot Formations")
    print("  Score the seed before you fly.")
    print("\u2588" * 60)
    
    results = []
    for path in EXAMPLES:
        if not os.path.exists(path):
            print(f"  [!] Missing: {path}")
            continue
        scenario = load_scenario(path)
        result = score(scenario)
        print_report(result)
        results.append(result)
    
    # Comparison table
    if results:
        print("\n" + "=" * 68)
        print("  COMPARISON SUMMARY")
        print("=" * 68)
        print(f"  {'Scenario':<35} {'Score':>7} {'Class':<15} {'Launch':<20}")
        print(f"  {'\u2500' * 64}")
        for r in results:
            print(f"  {r['scenario']:<35} {r['score']:>7.3f} {r['classification']:<15} {r['launch_recommendation']:<20}")
        print(f"  {'\u2500' * 64}")
        print(f"  Seeds beat noise. Topology beats headcount.")
        print(f"  Don't fly every formation. Score the seed first.")
        print("=" * 68 + "\n")


if __name__ == "__main__":
    main()
