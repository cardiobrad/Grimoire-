# FairField FPGA Arbiter
## GRIMOIRE SIN Engine in Silicon

### What This Is

A fixed-point hardware implementation of the GRIMOIRE reaction-diffusion
update law as a **bus arbiter / resource scheduler**. Eight nodes in a ring
topology, each running the locked equation in Q8.8 arithmetic with a 256-entry
sine lookup table and single-cycle local coupling.

Includes a Deficit Round-Robin (DRR) comparator running the exact same
workload for head-to-head fairness measurement.

### Target Hardware

- Lattice iCE40 HX1K/HX8K (£8–25)
- Any small FPGA with ~1500 LUTs
- Toolchain: Yosys + nextpnr + icestorm (free, open source)

### Files

| File | What |
|------|------|
| fairfield_arbiter.v | Complete Verilog: all 7 modules |
| sin_lut_values.txt | Auto-generated LUT (paste into sin_lut module) |

### Modules

1. **sin_lut** — 256-entry sin(πU) lookup, Q1.8 signed
2. **fairfield_node** — Single arbiter node with GRIMOIRE update law
3. **fairfield_ring** — N nodes in ring topology with local coupling
4. **drr_arbiter** — Standard Deficit Round-Robin for comparison
5. **workload_gen** — LFSR-based request generator (uniform/hotspot/sweep)
6. **fairness_meter** — Jain's Fairness Index over configurable window
7. **fairfield_testbench** — Top-level harness running both arbiters

### Build (iCE40)

```bash
# Synthesize
yosys -p "read_verilog fairfield_arbiter.v; synth_ice40 -top fairfield_testbench -json fairfield.json"

# Place and route
nextpnr-ice40 --hx8k --json fairfield.json --pcf pins.pcf --asc fairfield.asc

# Pack bitstream
icepack fairfield.asc fairfield.bin

# Upload
iceprog fairfield.bin
```

### What It Tests

**Binary outcome:**

PASS: FairField nodes converge to stable states under fixed-point Q8.8
arithmetic with 1-cycle coupling delay. Jain's Index matches or exceeds DRR.

FAIL: Nodes enter limit cycles (jitter between adjacent quantization levels)
or delay-induced oscillation destabilises convergence. Parking state at U=1
collapses.

### Kill Conditions

From Gemma 4 Gate-2 crucible:

1. If fixed-point quantization causes limit cycles at the parking state → DEAD
2. If 1-cycle coupling delay induces sustained oscillation → DEAD
3. If DRR achieves higher Jain's Index under all workload modes → DEAD
4. If control-plane bandwidth (coupling signals) exceeds 10% of data bandwidth → DEAD

### The Novel Claim

If it passes, FairField is a **Momentum-Preserving Scheduler** — a new class
of arbiter where nodes maintain a "primed" standby state (U=1) that enables
faster response than cold-start (U=0), with a natural nucleation barrier that
prevents noise from triggering false grants.

No existing arbiter (RR, WRR, DRR, credit-based, age-based) has:
- A nonlinear multi-well potential governing state transitions
- A metastable standby state with faster wake-up than cold start
- A nucleation barrier that naturally filters transient noise
- Decentralized local-only coupling with no global state

---

## Use Cases If Successful

### Tier 1: Direct Hardware Applications (Nearest)

**Network-on-Chip (NoC) Arbitration**
Multi-core processors need arbiters deciding which core gets access to shared
cache (LLC) or memory bus each cycle. Current: round-robin or priority-based.
FairField advantage: decentralised, no central arbiter, graceful degradation
when cores are added/removed. The parking state means idle cores consume
near-zero arbiter resources but respond faster than cold-allocated cores.

Market: every multi-core chip has this problem. Intel, AMD, ARM, RISC-V
designers are the audience. Even a 2% improvement in fairness-weighted
throughput at the LLC level translates to measurable performance gains.

**PCIe / CXL Bus Arbitration**
CXL (Compute Express Link) connects CPUs, GPUs, and memory expanders on a
shared bus. Arbitration is credit-based. FairField could replace the credit
management with local coupling — each device only talks to its bus neighbors.
The nucleation barrier prevents a single GPU from monopolising the bus during
burst computation, while the parking state keeps idle devices primed.

**Data Centre Network Switch Scheduling**
Top-of-rack switches arbitrate between 32–64 ports. Current: virtual output
queuing with iSLIP or similar. FairField advantage: under asymmetric "incast"
traffic (many-to-one, common in MapReduce), the nonlinear barrier naturally
dampens the incast while the multi-well potential distributes bandwidth more
fairly than linear schedulers.

### Tier 2: Systems-Level Applications (Medium term)

**Battery Management System (BMS) Cell Balancing**
Lithium-ion packs need to balance charge across cells. Current: top-balancing
or active balancing with switched capacitors. FairField mapping: each cell is
a node, U = state of charge, coupling = balancing current between adjacent
cells. The parking state (U=1) is the target balanced voltage. The nucleation
barrier prevents small SoC differences from triggering unnecessary balancing
(reducing wear). The pinning boundary determines maximum cell spacing before
balancing can't propagate.

Advantage over existing: no central BMS controller needed. Each cell's
balancing circuit runs the same update law using only its neighbors' voltage.
Truly decentralised. Scales to any pack size without redesigning the
controller.

**Microgrid Load Balancing**
Distributed energy resources (solar, battery, EV chargers) on a local grid
need to balance load without a central utility controller. FairField: each
DER is a node, U = local demand/supply ratio, coupling = electrical
interconnection impedance. The parking state is "balanced." The barrier
prevents transient demand spikes from cascading into grid instability.

This is the islanding problem: when the main grid disconnects, can the
microgrid self-organise? FairField's local-only coupling means it works
identically whether the main grid is connected or not.

### Tier 3: Novel / Research (Longer term)

**Neuromorphic Compute Fabric**
Intel Loihi and IBM NorthPole are building chips where artificial neurons
communicate locally. The fundamental design question: how densely should
neurons be interconnected? Too dense = seizure (global cascade). Too sparse
= no coordination. The pinning boundary D/dx² ≈ 1.5–2.0 gives a
quantitative answer: interconnect density must exceed this ratio for signals
to propagate, but the multi-well potential prevents runaway cascade.

FairField on an FPGA IS a small neuromorphic fabric. Each node is an
artificial neuron with a sine-modulated activation function, local synaptic
coupling, and a built-in refractory period (the barrier at U=2). If 8 nodes
work, scaling to 64 or 256 is straightforward on a larger FPGA.

**Multi-LLM Inference Scheduling**
Running multiple LLM queries on shared GPU/TPU resources. Each query is a
node, U = resource demand intensity. The barrier prevents a single large
query from starving smaller ones. The parking state keeps queued queries
primed (KV cache warm) so they can resume faster than cold-start queries.

This maps directly to Roemmele's JouleWork framework: each query's "wage"
(useful work per joule) is optimised by the FairField scheduler ensuring
fair resource distribution across concurrent inference tasks.

**Drone Swarm Resource Allocation**
Not swarm movement coordination (that's Scale 3, unproven), but rather
shared-resource allocation: bandwidth, battery, sensor time. Each drone is a
node on a local radio mesh. The arbiter decides who transmits, who charges,
who scans. Local coupling only — each drone talks to its radio neighbors.
The barrier prevents one drone from hogging the channel during a burst.

---

## What Success Does NOT Prove

- Does not prove GRIMOIRE works for swarm movement coordination
- Does not prove the PDE is the "correct" model for anything
- Does not prove FairField beats DRR under all workloads
- Does not validate any claims about diamond CVD, gene drives, or satellites
- Does not prove the equation is a physical law

It proves one thing: the GRIMOIRE update law, implemented in fixed-point
hardware with real delays, can function as a competitive resource scheduler.
That is a narrow, specific, valuable engineering result.

---

## Budget

| Item | Cost |
|------|------|
| Lattice iCE40 HX8K breakout | £15–25 |
| USB logic analyser | £15 |
| Yosys/nextpnr/icestorm | Free |
| Total | ~£40 |

## Timeline

| Week | Task |
|------|------|
| 1 | Build PC, install toolchain |
| 2 | Paste LUT, synthesise, debug timing |
| 3 | Run workload tests, measure Jain's Index |
| 4 | Head-to-head vs DRR, write up results |

---

Locked parameters: D=0.12, λ=0.45, α=π
These are baked into the Verilog as Q8.8 constants.
Do not change without new ablation evidence.
