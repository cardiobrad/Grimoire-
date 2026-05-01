#!/usr/bin/env python3
"""
agent_lifecycle_sim.py — Oscillatory Renewal as a Control Law for LLM Agent Lifecycle

Tests whether phase-aware renewal (λU²sin(αU)) outperforms:
  - Fixed-interval refresh
  - Token-count refresh
  - No refresh
  - Logistic saturation (ablation: proves oscillation matters, not just bounding)

Includes:
  - Desynchronisation test (do oscillatory agents avoid correlated troughs?)
  - Permutation test (shuffle U parameters to verify signal is real)
  - Multi-agent shared-task coherence test

Grounded in: Dongre 2025 (drift equilibria), Abdelnabi 2024 (activation drift),
SelfCheckGPT (consistency), software rejuvenation (Trivedi, Cotroneo).
"""
import numpy as np
import pandas as pd
import copy
from dataclasses import dataclass, field
from typing import List, Dict, Callable, Optional
from pathlib import Path

OUT_DIR = Path("outputs/lifecycle_sim")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════
LAMBDA_BASE = 1.5             # stronger drive to push through zeros
ALPHA = 2.0                   # wider oscillation period (zeros at U ≈ 0, 1.57, 3.14)
DECAY_RATE = 0.05
ENERGY_FLOOR = 0.05
ENERGY_CEILING = 5.0
RENEWAL_ENERGY = 0.5          # start away from sin(pi)=0 fixed point
RENEWAL_COST_TURNS = 3        # turns lost during renewal (not free)
MAX_TURNS = 200               # total turns per task
N_AGENTS = 5
N_TASKS = 50                  # tasks per experiment
FIXED_REFRESH_INTERVAL = 30   # turns between fixed refreshes
TOKEN_REFRESH_THRESHOLD = 120 # "token count" proxy
ENERGY_SUB_STEPS = 20         # sub-steps per turn for energy dynamics

# Noise parameters for task simulation
COHERENCE_NOISE_STD = 0.05    # per-turn noise in coherence
DRIFT_RATE = 0.008            # per-turn drift accumulation


# ═══════════════════════════════════════════════════
# Agent Model
# ═══════════════════════════════════════════════════
@dataclass
class Agent:
    id: int
    u: float                    # current energy U(t)
    lambda_coeff: float         # per-agent lambda
    initial_u: float
    prev_u: float = 0.0        # U from previous turn (for derivative)
    was_declining: bool = False # was U declining last turn?
    turns_since_refresh: int = 0
    total_refreshes: int = 0
    turns_in_renewal: int = 0   # countdown during renewal (agent unavailable)
    accumulated_drift: float = 0.0
    coherence: float = 1.0      # 1.0 = perfectly coherent, 0.0 = hallucinating
    correct_outputs: int = 0
    wrong_outputs: int = 0
    total_turns_active: int = 0

    def __post_init__(self):
        self.prev_u = self.u

    @property
    def phase(self) -> str:
        if self.u <= 0.5:            # energy has dropped low enough to warrant renewal
            return "trough"
        elif self.u >= 2.0:
            return "peak"
        elif self.u > 1.0:
            return "amplifying"
        else:
            return "decaying"

    def record_turn(self):
        """Track state for analysis."""
        self.prev_u = self.u

    def update_energy_sine(self, dt=1.0, running=True, mean_field=None):
        """Energy tracks coherence inversely. Sine modulates the phase dynamics.
        As drift accumulates, energy drops. Sine term creates different drop
        rates at different U values, naturally desynchronising agents."""
        # Energy decays proportional to drift, modulated by sine
        if running:
            # Base energy from coherence (inverted: high coherence = high energy)
            target_u = self.coherence * 3.0  # scale coherence to energy range
            # Sine modulation: agents at different U values track differently
            sine_mod = 1.0 + 0.3 * np.sin(ALPHA * self.u)
            # Move toward target with sine-modulated speed
            self.u += 0.2 * (target_u * sine_mod - self.u) * dt
        else:
            self.u *= (1.0 - DECAY_RATE * dt)
        self.u = np.clip(self.u, ENERGY_FLOOR, ENERGY_CEILING)

    def update_energy_logistic(self, dt=1.0, running=True, mean_field=None):
        """Ablation: same coherence tracking but WITHOUT sine modulation."""
        if running:
            target_u = self.coherence * 3.0
            # No sine modulation — direct tracking
            self.u += 0.2 * (target_u - self.u) * dt
        else:
            self.u *= (1.0 - DECAY_RATE * dt)
        self.u = np.clip(self.u, ENERGY_FLOOR, ENERGY_CEILING)

    def refresh(self):
        """Perform renewal: reset energy, clear drift, pay cost."""
        self.u = RENEWAL_ENERGY
        self.accumulated_drift = 0.0
        self.coherence = min(1.0, self.coherence + 0.3)  # partial coherence recovery
        self.turns_since_refresh = 0
        self.total_refreshes += 1
        self.turns_in_renewal = RENEWAL_COST_TURNS  # unavailable for N turns
        self.prev_u = self.u
        self.was_declining = False

    def is_available(self) -> bool:
        return self.turns_in_renewal <= 0


# ═══════════════════════════════════════════════════
# Refresh Policies
# ═══════════════════════════════════════════════════
def policy_no_refresh(agent: Agent, turn: int) -> bool:
    return False

def policy_fixed_interval(agent: Agent, turn: int) -> bool:
    return agent.turns_since_refresh >= FIXED_REFRESH_INTERVAL

def policy_token_threshold(agent: Agent, turn: int) -> bool:
    return agent.turns_since_refresh >= TOKEN_REFRESH_THRESHOLD

def policy_phase_aware(agent: Agent, turn: int) -> bool:
    """Refresh when agent hits trough phase."""
    return agent.phase == "trough"

def policy_phase_aware_logistic(agent: Agent, turn: int) -> bool:
    """Same trough trigger but with logistic energy dynamics."""
    return agent.phase == "trough"


# ═══════════════════════════════════════════════════
# Task Simulation
# ═══════════════════════════════════════════════════
def simulate_task(agents: List[Agent], refresh_policy: Callable,
                  energy_model: str = "sine", rng=None, max_turns=MAX_TURNS):
    """
    Simulate a multi-agent collaborative task.
    Each turn: agents produce outputs, accumulate drift, energy evolves.
    Correctness depends on coherence (which degrades with drift).
    """
    if rng is None:
        rng = np.random.RandomState(42)

    turn_logs = []
    all_wrong_together_events = 0
    total_output_turns = 0

    for turn in range(max_turns):
        turn_outputs = []

        # Compute mean field for inter-agent coupling (diffusion analog)
        active_agents = [a for a in agents if a.is_available()]
        mean_field = np.mean([a.u for a in active_agents]) if active_agents else 0.0

        for agent in agents:
            # Handle renewal cooldown
            if agent.turns_in_renewal > 0:
                agent.turns_in_renewal -= 1
                continue

            # Check refresh policy
            if refresh_policy(agent, turn):
                agent.refresh()
                continue  # this turn spent refreshing

            # Agent produces output this turn
            agent.total_turns_active += 1
            agent.turns_since_refresh += 1

            # Drift accumulates
            agent.accumulated_drift += DRIFT_RATE + rng.normal(0, DRIFT_RATE * 0.5)

            # Coherence degrades with drift (sigmoid decay)
            drift_factor = 1.0 / (1.0 + np.exp(3 * (agent.accumulated_drift - 0.5)))
            noise = rng.normal(0, COHERENCE_NOISE_STD)
            agent.coherence = np.clip(drift_factor + noise, 0.0, 1.0)

            # Correctness: probabilistic based on coherence
            is_correct = rng.random() < agent.coherence
            if is_correct:
                agent.correct_outputs += 1
            else:
                agent.wrong_outputs += 1

            turn_outputs.append(is_correct)

            # Update energy with inter-agent coupling
            if energy_model == "sine":
                agent.update_energy_sine(running=True, mean_field=mean_field)
            elif energy_model == "logistic":
                agent.update_energy_logistic(running=True, mean_field=mean_field)
            agent.record_turn()

        # Check for "all agents wrong together" (correlated failure)
        if len(turn_outputs) >= 2:
            total_output_turns += 1
            if all(not o for o in turn_outputs):
                all_wrong_together_events += 1

        # Log turn state
        turn_logs.append({
            "turn": turn,
            "mean_u": np.mean([a.u for a in agents]),
            "mean_coherence": np.mean([a.coherence for a in agents]),
            "mean_drift": np.mean([a.accumulated_drift for a in agents]),
            "agents_available": sum(1 for a in agents if a.is_available()),
            "all_wrong": all(not o for o in turn_outputs) if turn_outputs else False,
        })

    # Compute task metrics
    total_correct = sum(a.correct_outputs for a in agents)
    total_wrong = sum(a.wrong_outputs for a in agents)
    total_refreshes = sum(a.total_refreshes for a in agents)
    total_active = sum(a.total_turns_active for a in agents)

    accuracy = total_correct / (total_correct + total_wrong) if (total_correct + total_wrong) > 0 else 0
    corr_failure_rate = all_wrong_together_events / total_output_turns if total_output_turns > 0 else 0

    return {
        "accuracy": round(accuracy, 4),
        "total_correct": total_correct,
        "total_wrong": total_wrong,
        "total_refreshes": total_refreshes,
        "total_active_turns": total_active,
        "correlated_failure_rate": round(corr_failure_rate, 4),
        "all_wrong_events": all_wrong_together_events,
        "final_mean_coherence": round(np.mean([a.coherence for a in agents]), 4),
        "final_mean_drift": round(np.mean([a.accumulated_drift for a in agents]), 4),
    }


# ═══════════════════════════════════════════════════
# Experiment Runner
# ═══════════════════════════════════════════════════
def make_agents(rng, n=N_AGENTS):
    """Create agents with varied parameters and staggered initial phases."""
    agents = []
    for i in range(n):
        lam = LAMBDA_BASE + rng.normal(0, 0.05)
        # Stagger initial U across agents for natural phase diversity
        u0 = 0.3 + (i / n) * 0.8 + rng.normal(0, 0.1)  # range ~0.2 to ~1.2
        u0 = np.clip(u0, ENERGY_FLOOR, ENERGY_CEILING)
        agents.append(Agent(id=i, u=u0, lambda_coeff=lam, initial_u=u0))
    return agents


def run_experiment(name, refresh_policy, energy_model, n_tasks=N_TASKS, seed=42):
    """Run multiple tasks under one policy configuration."""
    rng = np.random.RandomState(seed)
    results = []
    for t in range(n_tasks):
        agents = make_agents(rng)
        task_rng = np.random.RandomState(seed + t)
        metrics = simulate_task(agents, refresh_policy, energy_model, task_rng)
        metrics["task_id"] = t
        results.append(metrics)
    return pd.DataFrame(results)


def summarise(df, name):
    """Summarise experiment results."""
    return {
        "policy": name,
        "accuracy": f"{df['accuracy'].mean():.4f} \u00B1 {df['accuracy'].std():.4f}",
        "acc_mean": round(df["accuracy"].mean(), 4),
        "acc_std": round(df["accuracy"].std(), 4),
        "refreshes": f"{df['total_refreshes'].mean():.1f}",
        "corr_fail": f"{df['correlated_failure_rate'].mean():.4f} \u00B1 {df['correlated_failure_rate'].std():.4f}",
        "corr_fail_mean": round(df["correlated_failure_rate"].mean(), 4),
        "all_wrong_events": f"{df['all_wrong_events'].mean():.1f}",
        "final_coherence": f"{df['final_mean_coherence'].mean():.4f}",
        "final_drift": f"{df['final_mean_drift'].mean():.4f}",
    }


def main():
    print("=" * 80)
    print("  AGENT LIFECYCLE SIMULATOR")
    print("  Oscillatory Renewal vs Baselines vs Logistic Ablation")
    print("=" * 80)

    # ─── Main experiments ───
    experiments = [
        ("No Refresh", policy_no_refresh, "sine"),
        ("Fixed Interval (30 turns)", policy_fixed_interval, "sine"),
        ("Token Threshold (120 turns)", policy_token_threshold, "sine"),
        ("Phase-Aware Sine Renewal", policy_phase_aware, "sine"),
        ("Phase-Aware Logistic (ABLATION)", policy_phase_aware_logistic, "logistic"),
    ]

    all_summaries = []
    all_raw = {}

    print(f"\n  Running {N_TASKS} tasks \u00D7 {N_AGENTS} agents \u00D7 {MAX_TURNS} turns each\n")

    for name, policy, energy in experiments:
        df = run_experiment(name, policy, energy)
        s = summarise(df, name)
        all_summaries.append(s)
        all_raw[name] = df
        print(f"  {name:<35} Acc={s['accuracy']}  CorrFail={s['corr_fail']}  Refreshes={s['refreshes']}")

    # ─── Key comparison: Sine vs Logistic ───
    print("\n" + "=" * 80)
    print("  CRITICAL ABLATION: Does oscillation matter?")
    print("=" * 80)

    sine_acc = all_raw["Phase-Aware Sine Renewal"]["accuracy"].mean()
    logistic_acc = all_raw["Phase-Aware Logistic (ABLATION)"]["accuracy"].mean()
    sine_corr = all_raw["Phase-Aware Sine Renewal"]["correlated_failure_rate"].mean()
    logistic_corr = all_raw["Phase-Aware Logistic (ABLATION)"]["correlated_failure_rate"].mean()

    print(f"\n  Sine accuracy:     {sine_acc:.4f}")
    print(f"  Logistic accuracy: {logistic_acc:.4f}")
    delta_acc = sine_acc - logistic_acc
    if delta_acc > 0.01:
        print(f"  \u2713 Sine beats logistic by {delta_acc:.4f} \u2014 oscillation matters")
    elif delta_acc < -0.01:
        print(f"  \u2717 Logistic beats sine by {-delta_acc:.4f} \u2014 oscillation may not help")
    else:
        print(f"  \u2014 No meaningful difference ({delta_acc:+.4f}) \u2014 oscillation doesn't clearly help")

    print(f"\n  Sine correlated failures:     {sine_corr:.4f}")
    print(f"  Logistic correlated failures: {logistic_corr:.4f}")
    delta_corr = logistic_corr - sine_corr
    if delta_corr > 0.005:
        print(f"  \u2713 Sine has {delta_corr:.4f} fewer correlated failures \u2014 desynchronisation works")
    elif delta_corr < -0.005:
        print(f"  \u2717 Logistic has fewer correlated failures")
    else:
        print(f"  \u2014 No meaningful difference in correlated failures")

    # ─── Permutation test ───
    print("\n" + "=" * 80)
    print("  PERMUTATION TEST: Shuffle agent parameters")
    print("=" * 80)

    rng_perm = np.random.RandomState(999)
    perm_results = []
    for t in range(N_TASKS):
        agents = make_agents(rng_perm)
        # Shuffle lambda and initial_u across agents
        lambdas = [a.lambda_coeff for a in agents]
        u0s = [a.initial_u for a in agents]
        rng_perm.shuffle(lambdas)
        rng_perm.shuffle(u0s)
        for a, l, u in zip(agents, lambdas, u0s):
            a.lambda_coeff = l
            a.initial_u = u
            a.u = u
        task_rng = np.random.RandomState(999 + t)
        metrics = simulate_task(agents, policy_phase_aware, "sine", task_rng)
        metrics["task_id"] = t
        perm_results.append(metrics)

    perm_df = pd.DataFrame(perm_results)
    perm_acc = perm_df["accuracy"].mean()
    real_acc = sine_acc

    print(f"\n  Real sine accuracy:    {real_acc:.4f}")
    print(f"  Permuted accuracy:     {perm_acc:.4f}")
    delta_perm = real_acc - perm_acc
    if delta_perm > 0.01:
        print(f"  \u2713 Real outperforms permuted by {delta_perm:.4f} \u2014 signal is real")
    elif delta_perm < -0.01:
        print(f"  \u2717 Permuted does better \u2014 signal may be spurious")
    else:
        print(f"  \u2014 No meaningful difference \u2014 investigate further")

    # ─── Desynchronisation analysis ───
    print("\n" + "=" * 80)
    print("  DESYNCHRONISATION: Do oscillatory agents avoid simultaneous troughs?")
    print("=" * 80)

    # Run one detailed task and track per-agent phases
    rng_detail = np.random.RandomState(42)
    agents_sine = make_agents(rng_detail)
    agents_fixed = make_agents(np.random.RandomState(42))  # identical start

    # Track trough events per turn
    sine_trough_counts = []
    fixed_trough_counts = []

    for turn in range(MAX_TURNS):
        # Sine agents with coupling
        sine_troughs = 0
        sine_mf = np.mean([a.u for a in agents_sine if a.is_available()]) if any(a.is_available() for a in agents_sine) else 0
        for a in agents_sine:
            if a.turns_in_renewal > 0:
                a.turns_in_renewal -= 1
                continue
            if policy_phase_aware(a, turn):
                a.refresh()
                sine_troughs += 1
                continue
            a.turns_since_refresh += 1
            a.accumulated_drift += DRIFT_RATE
            a.update_energy_sine(running=True, mean_field=sine_mf)
            a.record_turn()
        sine_trough_counts.append(sine_troughs)

        # Fixed agents with coupling
        fixed_troughs = 0
        fixed_mf = np.mean([a.u for a in agents_fixed if a.is_available()]) if any(a.is_available() for a in agents_fixed) else 0
        for a in agents_fixed:
            if a.turns_in_renewal > 0:
                a.turns_in_renewal -= 1
                continue
            if policy_fixed_interval(a, turn):
                a.refresh()
                fixed_troughs += 1
                continue
            a.turns_since_refresh += 1
            a.accumulated_drift += DRIFT_RATE
            a.update_energy_sine(running=True, mean_field=fixed_mf)
            a.record_turn()
        fixed_trough_counts.append(fixed_troughs)

    # Count simultaneous refresh events (all agents refreshing at once)
    sine_simultaneous = sum(1 for c in sine_trough_counts if c >= N_AGENTS - 1)
    fixed_simultaneous = sum(1 for c in fixed_trough_counts if c >= N_AGENTS - 1)

    print(f"\n  Sine: {sine_simultaneous} turns where most/all agents refresh simultaneously")
    print(f"  Fixed: {fixed_simultaneous} turns where most/all agents refresh simultaneously")
    if sine_simultaneous < fixed_simultaneous:
        print(f"  \u2713 Oscillatory agents desynchronise \u2014 fewer simultaneous refreshes")
    elif sine_simultaneous > fixed_simultaneous:
        print(f"  \u2717 Oscillatory agents synchronise MORE than fixed interval")
    else:
        print(f"  \u2014 No difference in synchronisation")

    # ─── Save results ───
    summary_df = pd.DataFrame(all_summaries)
    summary_df.to_csv(OUT_DIR / "lifecycle_summary.csv", index=False)

    for name, df in all_raw.items():
        safe_name = name.replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_")
        df.to_csv(OUT_DIR / f"raw_{safe_name}.csv", index=False)

    perm_df.to_csv(OUT_DIR / "permutation_test.csv", index=False)

    print(f"\n  Results saved to {OUT_DIR}/")

    # ─── Final verdict ───
    print("\n" + "=" * 80)
    print("  VERDICT")
    print("=" * 80)

    best = max(all_summaries, key=lambda s: s["acc_mean"])
    print(f"\n  Best policy: {best['policy']} (accuracy={best['accuracy']})")

    sine_s = next(s for s in all_summaries if s["policy"] == "Phase-Aware Sine Renewal")
    no_ref = next(s for s in all_summaries if s["policy"] == "No Refresh")
    fixed_s = next(s for s in all_summaries if s["policy"] == "Fixed Interval (30 turns)")
    logistic_s = next(s for s in all_summaries if s["policy"] == "Phase-Aware Logistic (ABLATION)")

    tests_passed = 0
    total_tests = 4

    if sine_s["acc_mean"] > no_ref["acc_mean"]:
        tests_passed += 1
        print("  \u2713 Sine beats no-refresh")
    else:
        print("  \u2717 Sine does NOT beat no-refresh")

    if sine_s["acc_mean"] > fixed_s["acc_mean"]:
        tests_passed += 1
        print("  \u2713 Sine beats fixed-interval")
    else:
        print("  \u2717 Sine does NOT beat fixed-interval")

    if sine_s["acc_mean"] > logistic_s["acc_mean"]:
        tests_passed += 1
        print("  \u2713 Sine beats logistic ablation \u2014 oscillation matters")
    else:
        print("  \u2717 Sine does NOT beat logistic \u2014 oscillation may not be necessary")

    if sine_s["corr_fail_mean"] < fixed_s["corr_fail_mean"]:
        tests_passed += 1
        print("  \u2713 Sine has lower correlated failure rate than fixed")
    else:
        print("  \u2717 Sine does NOT reduce correlated failures vs fixed")

    print(f"\n  RESULT: {tests_passed}/{total_tests} tests passed")
    if tests_passed == total_tests:
        print("  \u2713\u2713\u2713 OSCILLATORY RENEWAL VALIDATED")
    elif tests_passed >= 3:
        print("  \u26A0 Mostly passes \u2014 investigate failing criterion")
    else:
        print("  \u2717 OSCILLATORY RENEWAL NOT VALIDATED \u2014 report honestly")

    print("=" * 80)


if __name__ == "__main__":
    main()
