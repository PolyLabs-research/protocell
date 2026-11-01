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
