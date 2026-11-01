# Preregistration draft: stage 0 — the world, the cell, its energy, and the baselines

**Written:** 2026-11-01, before any code of what it describes (`docs/plan.md`; `docs/decisions.md` D1). Stage 0 builds
and checks; nothing is evolved. Its job is to establish, before stage 1 runs, that the world tests what stage 1 is for:
that moving pays, that the light can be sensed and reached, and how well cells with no evolved brain do. Every number
below is set from its stated reason before any run; a check that fails is answered by a dated amendment with a
geometric or economic reason, before stage 1.

## 1. Units and the dish

The cell's radius R is the unit of length (R = 1, about 5 µm, the size of a *Chlamydomonas* cell); a tick is 0.1 s. The
dish is a disc of radius **45 R**; the cell's centre is kept within 44 R of the dish's centre (it slides along the
edge). A lifetime is **3,000 ticks** (5 minutes).

## 2. Light

Two kinds of field, each a single source plus a dim background b = 0.02. Intensity is in units of the photosynthetic
half-saturation (§4), so I = 1 gives half the maximum rate.

- **Spot** (overhead, no direction): I(p) = 4 exp(−|p − c|² / (2 · 20²)) + b, its centre c drawn uniformly within 10 R
  of the dish's centre. The soak region (I ≥ 1) has a radius of 33 R.
- **Lamp** (lateral, directional): a point on the dish's edge at a random angle; I(p) = 4 / (1 + (d / 20)²) + b at
  distance d. The cell shades itself: a wall node receives I × (0.3 + 0.7 max(0, cos β)), β the angle between its
  outward normal and the direction to the lamp (the cell is translucent: the far side gets 30%).

**Starts:** uniform over the dish, a uniform random heading, at least **42 R** from a spot's centre (where I < 0.5:
the light there does not pay for resting, §4) or at least **60 R** from a lamp.

## 3. The cell

**The body.** N = **16** wall nodes on the circle of radius R, at angles θᵢ = 2πi/N from the cell's heading φ.

**The network** (one CTRNN; Beer 1995): N wall neurons and K = **8** core neurons, state y, each tick
y ← y + (1/τ)(−y + W σ(y + β) + S), with σ the logistic function, τ ≥ 1 tick, and S the sensory input, nonzero on
wall neurons only: Sᵢ = g · (Iᵢ + noise). W is masked to the organism's topology:

- **The ring** (repeated identical units, D1.4): every wall neuron has the same self weight, the same weight from its
  clockwise neighbour and the same from its anticlockwise neighbour (the two may differ, so the ring may have a
  chirality), the same bias, time constant and sensory gain g.
- **The spokes**, in one of two modes, a structural factor for stage 1:
  - **uniform** (strictly identical units): every wall neuron sends the same weight to core neuron j and receives the
    same weight from it. The core then sees only the ring's total, never the light's direction; steering must come
    from the wall's local reflexes, from a pattern the ring forms itself, or from the core comparing the total over
    time.
  - **fourier1**: a spoke's weight varies smoothly with the node's angle, aⱼ + bⱼ cos θᵢ + cⱼ sin θᵢ (each direction
    of each spoke has its own three numbers). The core can read and set the light's direction in the body's frame; the
    cell has a front.
- **The core:** fully recurrent, each neuron its own bias and time constant.

The genome: 103 numbers (uniform) or 135 (fourier1). Ranges, for random genomes and later for evolution: weights and
biases in [−8, 8]; log τ in [0, log 20]; g in [0, 20]; the cilium angle α (below) in [−π, π].

**The cilia.** Wall node i beats with gᵢ = σ(yᵢ + β_ring) ∈ (0, 1) and pulls the cell along uᵢ, the direction from the
cell's centre to node i turned by α (shared by all nodes; α = 0: a node pulls the cell toward its own side). No
momentum: velocity v = v_max (π/N) Σ gᵢ uᵢ, v_max = **1 R a tick** (50 µm/s); turning ω = ω_max (1/N) Σ gᵢ sin α,
ω_max = **0.5 rad a tick**. The factor π/N makes half the ring beating fully, all on one side, move the cell at about
v_max.

**Noise, every source listed and switchable:** sensor noise, Gaussian, sd **0.01** per node per tick (stream
`sensors`); rotational noise, Gaussian, sd **0.05 rad** per tick (stream `motion`; real cells diffuse in angle). Starts
and layouts come from stream `starts`, random genomes from `genomes`.

## 4. Energy and damage

A reserve E in [0, 1], starting at **0.5**. Each tick:

- gain η (1/N) Σ P(Iᵢ), with P(I) = I / (1 + I) the saturating rate of photosynthesis (Iᵢ after shading), η = **3/1500**;
- cost c₀ + c₁ (1/N) Σ gᵢ, c₀ = **1/1500** (resting from 0.5 starves in 750 ticks), c₁ = **1/1500** (every cilium
  beating fully doubles the cost).

So a cell at a spot's peak (P ≈ 0.8) gains 2.4/1500 a tick and stays fed even beating hard; one where I < 0.5 gains
less than its resting cost. Death at E = 0.

**Damage** (the mechanism only; inert in stages 0 and 1, its numbers set in stage 2's preregistration): D grows with
the light above a threshold I_d, (1/N) Σ max(0, Iᵢ − I_d), and is repaired at a rate proportional to D; death at D = 1.
In stages 0 and 1, I_d = 10, above every field's peak.

## 5. Measures

Per run: survival (alive at the lifetime's end); **fitness**, the mean of E over the lifetime with dead ticks counting
0 (it rewards staying alive and staying fed); light soaked, the mean of (1/N) Σ P(Iᵢ); **effort per unit light**, the
mean beat over the mean light soaked; the time to reach the soak region (I ≥ 1 at the centre).

## 6. Baselines

- **B0, still:** no cilium ever beats.
- **B1, random beating:** each gᵢ drawn uniformly from (0, 1) each tick (stream `motion`): motion without sensing.
- **B2, the reflex:** no network; gᵢ = σ(k (Iᵢ − Ī) / (Ī + 0.01)), Ī the mean over the wall, α = 0: the brighter side
  beats harder and pulls the cell toward the light. Its gain k is set at its best, so the bar is high: the best of k ∈
  {1, 3, 10, 30, 100} on starts 1–50, its score reported on starts 51–100.
- **B3, random genomes:** 1,000 genomes drawn uniformly over the ranges (§3), in each spoke mode, each on 20 starts.

## 7. The checks (each light kind)

- **W1, moving pays.** B0 dies before the lifetime's end on at least 90% of starts 1–100; B0 placed at the brightest
  point survives with E rising.
- **W2, the light can be sensed.** At the start, the spread of the noiseless sensed light over the wall (largest minus
  smallest) is at least 3 times the sensor noise on at least half of starts 1–100.
- **W3, the light can be reached.** From every start, the straight distance to the soak region at v_max takes at most
  10% of the lifetime.
- **W4, the bar, and motion without sensing.** B2's survival and fitness on starts 51–100 are recorded as stage 1's
  bar. If B1 survives on at least half the starts, light is found without sensing, and the world is changed before
  stage 1.
- **W5, random wiring rarely works.** The share of random genomes whose survival matches or beats B2's: expected under
  1%; at 5% or more, stage 1's task is too easy and is made harder before it runs.
- **W6, determinism.** The same seed gives the same trajectory hash; a batch of P cells reproduces P single-cell runs
  bit for bit; the named streams are independent.

## 8. Seeds

Starts 1–100 and genomes 1–1,000 are stage 0's and are never used to evaluate an evolved cell. Stage 1 evaluates on
fresh starts.

## 9. Predictions (written before any code)

W1 passes. W2 passes for the lamp (shading gives a contrast of about 0.7 of the light) and narrowly for the spot (its
gradient at 42–55 R is a few times the noise). W3 passes. B2 survives most spot starts near enough to sense the
gradient and most lamp starts; B1 survives rarely. W5 passes in the uniform mode and less clearly in the fourier1 mode,
where the core can wire a reflex of its own.

## 10. Decision table

| result | what follows |
|---|---|
| W1–W6 pass | stage 1's preregistration, with B2's score as its bar |
| W1, W2 or W3 fails | a dated amendment to the world (its geometry or economy, with the reason), the checks run again |
| W4's motion-without-sensing clause or W5 fails | the task made harder (a dated amendment), the checks run again |
| W6 fails | fixed before anything else |

## 11. What would change this document

Nothing after its checks have run, except dated amendments recorded here before stage 1.

### Pre-run clarifications (2026-11-01, written while building, before any check ran)

Points §1–§7 leave open, fixed here before the run. None changes a stated number.

- **C1, the tick.** Sense at the current pose → update the network → beats → move (velocity, rotation, rotational
  noise, the dish's edge) → energy (the gain from this tick's noiseless light at the nodes, the cost from this tick's
  beats) → damage → the death check. The network starts at y = 0; its output σ(y + β) is computed after each update
  and serves both as this tick's beats and as the next update's input. A cell dead at a tick's end counts 0 for that
  tick in every per-tick measure (E, light soaked, beat); dead cells do not move. The sensor noise enters the sensors
  only, never the energy.
- **C2, where light is read.** The field's intensity at each wall node's own place on the membrane (one radius out
  from the centre along its normal), for the spot and the lamp alike; the lamp's direction, for cos β, is taken from
  the cell's centre. "The brightest point" and "the soak region" use the unshaded intensity at the cell's centre,
  I ≥ 1: for the spot, within 33.5 R of its centre; for the lamp, within 35.1 R of it. The lamp's brightest reachable
  point is the centre at 44 R toward the lamp (one radius from it, the nearest the centre may be).
- **C3, the starts.** Uniform over the disc of radius 44 R (where the cell's centre may be), by rejection. For each
  start, in this order from stream `starts` at seed 0 (stage 0's seed): the layout (spot: its centre, uniform over
  the disc of radius 10; lamp: its angle, uniform), the heading (uniform), then positions until one is far enough.
  Start k is the k-th drawn, so starts 1–m are the same whatever n. Stage 1 uses another seed.
- **C4, the noise is keyed per run.** Streams `sensors` and `motion` are keyed by (cell, start), so a cell's draws are
  the same bits alone or in a batch (W6): the baselines B0–B2 use cell id 0 (so every baseline and every reflex gain
  sees the same noise on a start), random genome g uses id g. Draws are made in chunks of 250 ticks; chunking does not
  change a generator's sequence (tested).
- **C5, B1's beats have their own stream.** §3 put random beating under `motion`; it draws from its own stream `beats`
  instead, so that switching the rotational noise off leaves the beats as they were and the other way round (lesson 3
  of `docs/plan.md`). B1 and B2 use α = 0 (B2 as §6 states; B1 by the same reading: motion without sensing, no turn).
- **C6, the reflex.** Iᵢ is the sensed light with the same sensor noise a network cell has; Ī is the mean over the 16
  nodes of this tick's sensed light. Its gain k is the one with the best mean fitness on starts 1–50 (ties: the
  higher survival, then the smaller k).
- **C7, B3.** Each random genome runs on starts 51–70, the first twenty of the report starts, so its survival is
  compared with B2's on the same distribution; W5 compares a genome's survival rate over its 20 starts with B2's over
  starts 51–100. Genome g is the g-th drawn from stream `genomes` at seed 0, one sequence per spoke mode. In the
  fourier1 mode each of a spoke's three coefficients a, b, c lies in [−8, 8] (so a spoke weight can reach 8(1 + √2)).
- **C8, damage's repair constant** is 0.01 a tick as a placeholder, inert here (I_d = 10 is above every field's peak
  of 4.02, so D stays 0); stage 2's preregistration sets it.
- **C9, the measures of W1–W3.** W2's spread is the largest minus the smallest of the noiseless light at the 16 nodes
  at the start pose. W3 uses the straight distance from the start to the soak region's edge at v_max (the dish is
  convex, so the straight line stays inside it). W1's "E rising": the cell at the brightest point survives and ends
  the lifetime with more reserve than it started with.
- **C10, the genome's order and the ring's chirality.** Core weights (64, to j from l, row-major), core biases (8),
  core log τ (8), the ring (self weight, from the clockwise neighbour, from the anticlockwise neighbour, bias, log τ,
  g), α, spokes in (wall → core), spokes out (core → wall). Node i + 1 is anticlockwise of node i (θ increasing), so
  "from the clockwise neighbour" is from i − 1.
- **C11, the trajectory hash** (W6) is SHA-256 over the per-tick positions, headings and reserves, per cell and over
  the batch; "a batch equals its singles" compares every recorded per-tick array and every per-run measure as well.
- **C12, the sigmoid** is computed with its argument clipped to ±500, so the exponent cannot overflow under
  warnings-as-errors; the function is unchanged to double precision beyond ±37.

### Amendment A1 (2026-11-01, after run 1, before run 2): the spot narrowed to σ = 16 R, its starts at least 38 R away

**What run 1 found** (`docs/data/stage0/as-preregistered/`, code `e4799c4`, clean tree, warnings as errors, 60 s):
the lamp passes W1–W5, W6 passes, and the spot fails W1 and W5.

- **W1.** B0 survived on 51 of 100 spot starts: every start nearer than 45.1 R to the spot's centre, none farther.
  The reason is arithmetic. §2 put the starts where I < 0.5, "where the light does not pay for resting"; but at
  I = 0.5 the gain η P equals the resting cost c₀ exactly, so a still cell there never starves, and at the nearest
  allowed start (42 R, I = 0.46) it loses 0.053/1500 a tick and lives 14,000 ticks, nearly five lifetimes. To starve
  from E = 0.5 within a lifetime a still cell must lose at least 0.25/1500 a tick, so gain at most 0.75/1500: I ≤ 1/3,
  which the spot reaches only beyond 45.1 R. The lamp's starts pass because the cell shades itself: a still cell's
  mean shading factor is 0.3 + 0.7/π = 0.52, so at 60 R it gets 0.22 and starves in 1,600 ticks.
- **W5.** 12.6% of random fourier1 genomes survived all 20 of their starts (uniform: 1.9%, which passes). Every one
  of them had reached the soak region, and they soaked light at a mean P of 0.62 with a mean beat of 0.75: not still
  cells but movers. The spot's soak region (I ≥ 1, radius 33.5 R) covers 58% of the disc the cell's centre may occupy,
  and a start is at most 11 R from its edge, so a cell that moves in any direction for a few seconds enters it, and a
  mover, once in, is in light more often than not. The lamp's soak region covers 25% of the disc, and there 1.4%
  (fourier1) and 3.6% (uniform) of random genomes matched the reflex.

**The reason for the amendment, geometric.** A start must be where a still cell starves within the lifetime (W1);
the soak region must be a smaller share of the dish (W5); and the light's difference across one body at the start
must still beat the sensor noise (W2). For a Gaussian spot the three pull against each other, because its relative
gradient, 2r/σ², is small where it is dark. `experiments/stage0_geometry.py` (no simulation; fresh starts, seed 1)
takes each width σ, puts the start where a still cell starves within two thirds of the lifetime (gain at most
c₀ − 0.5/2,000 a tick, so I ≤ 0.263; the third is margin for the rounding of the distance and the background's
gain), and reads W1–W3 off the geometry:

| σ (R) | start ≥ (R) | soak radius (R), share of the disc | I at the nearest start | B0 starves in (ticks) | W2: share of starts with spread ≥ 0.03 | W3: farthest start (ticks) |
|---|---|---|---|---|---|---|
| 20 as preregistered | 42 | 33.5, 58% | 0.461 | 14,049 | 1.00 | 19 |
| 20 | 48 | 33.5, 58% | no such start fits in the dish | | | |
| 18 | 43 | 30.2, 47% | 0.251 | 1,880 | 0.90 | 22 |
| 17 | 41 | 28.5, 42% | 0.238 | 1,774 | 0.71 | 24 |
| **16** | **38** | **26.8, 37%** | **0.258** | **1,953** | **0.69** | **24** |
| 15 | 36 | 25.2, 33% | 0.245 | 1,827 | 0.56 | 27 |
| 14 | 34 | 23.5, 28% | 0.230 | 1,705 | 0.47 | 27 |
| 13 | 31 | 21.8, 25% | 0.253 | 1,902 | 0.43 | 29 |
| 12 | 29 | 20.1, 21% | 0.236 | 1,753 | 0.35 | 31 |

At σ = 20 the rule asks for 48 R, which the dish cannot hold: the preregistered spot has no start region at all
where a still cell starves within two thirds of a lifetime. The width taken is the narrowest at which W2 holds with a
margin, on at least two thirds of fresh starts: **σ = 16 R, with starts at least 38 R from the spot's centre**
(I ≤ 0.26 there; a still cell starves in at most 1,950 ticks). The soak region's radius becomes 26.8 R, 37% of the
disc (from 58%); its bright core, I ≥ 2, 19% of the disc (from 29%). The spot cannot be made as small a share as the
lamp's (25%) without W2 failing. Nothing else changes: the economy of §4, the lamp (which passed), the cell, the
noise, the measures, the seeds. The spot's starts 1–100 are drawn by the same rule at the same seed, so they move;
the lamp's are untouched, and run 2 should reproduce run 1's lamp results bit for bit.

**Expected of run 2:** the spot passes W1 (every B0 start starves), W2 narrowly (about 0.69), W3 (at most 25
ticks); the reflex still survives every start; the spot's W5 comes down from 12.6% but may stay above 5% in the
fourier1 mode, since movers that found a spot covering 58% of the disc may still find one covering 37%. If it does,
that is the result, and what follows (stage 1 on the lamp alone, or another change to the spot) is the owner's call
(D2).

**Not taken:** raising the resting cost (c₀ = 1/1200 would starve a still cell at 42 R in 2,500 ticks) fixes W1 but
leaves the soak region's share, so W5's reason stands, and it changes the lamp world, which passed; a larger dish
fails W2 and W3 through the same gradient bind.
