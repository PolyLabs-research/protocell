# Preregistration draft: the cave pool — the world from stage 1 on, and its checks

**Written:** 2026-11-01, before any of it is built (`docs/decisions.md` D3). The owner's direction after stage 0 (D2):
"imagine a cave with a small flat pool at the bottom, the cave is south facing and runs on a 24 hr cycle; the lifetime
will need to survive at least a night"; then "agree with your suggestions, let's go with a 1 s tick, a random phase,
widened." This world replaces both of stage 0's (the lamp was the cave at a fixed hour, and passed; the spot is
dropped). It holds the plan's stages 1 to 4 at once, so its parts are built as switches and checked in order, one
part at a time, before any cell is evolved in it: first the pool at noon, then the day and the night, then damage,
then the sun's sweep. Every number below is set by a stated rule, the open ones by the probe of §13, which ran before
this draft was finished and whose table is in §14.

## 1. Units and scales

The cell's radius R stays the unit of length (5 µm). **A tick is 1 s** (stage 0's was 0.1 s): a day is 86,400 ticks,
sunrise at 0, sunset at 43,200 (an equinox: twelve hours of each). What stage 0 set per tick is rescaled, not reset:

| quantity | stage 0, per 0.1 s | here, per 1 s | rule |
|---|---|---|---|
| v_max | 1 R | **10 R** | the same 50 µm/s |
| ω_max | 0.5 rad | **1 rad** | a straight rescale gives 5 rad a tick, nearly a full turn, which a 1 s step cannot resolve; a cell that turns a radian a second reorients in a few seconds, as a phototactic cell does. *A decision for the owner.* |
| rotational noise, sd | 0.05 rad | **0.158 rad** | the same diffusion, 0.025 rad² a second |
| sensor noise, sd per node | 0.01 | **0.00316** | the same white noise averaged over ten times the window |
| τ, the time constants | 1–20 ticks | **1–3,600 ticks** (log-uniform) | "widened": a second to an hour, so slow integration and the makings of a clock are within evolution's reach. A random genome now has a quarter of its neurons slower than six minutes. |

## 2. The pool

A disc of radius **5,000 R** (2.5 cm, "a small flat pool"); the cell's centre is kept within 4,999 R (it slides along
the edge). The cell crosses it in 1,000 ticks (17 min), so it can move far faster than the light changes. The pool is
flat: light does not vary with depth.

## 3. The light: the mouth, the day, the sweep

The mouth is a point on the pool's southern edge (x east, y north; due south is the angle −90°). Light enters from it
and falls off with distance d:

I(p, t) = I_mouth · daylight(t) / (1 + (d / d₀)²), with no background: the night is dark.

- **I_mouth = 10** half-saturations at the mouth at noon: about half of full sun (which is near 20), as a cave mouth
  gets. *Rule: a stated fraction of full sun.*
- **daylight(t)** = sin(π t / 43,200) from sunrise to sunset, 0 at night. **Switch `cycle`:** off, it is 1 at every
  hour (the pool at noon, forever).
- **d₀ = 750 R**, the falloff length. *Rule (§13 R1): the largest at which a still cell survives a lifetime from at
  most a tenth of the pool.* So the back of the pool, 10,000 R from the mouth, gets 0.56% of the mouth's light
  (I = 0.056 at noon). The soak region (I ≥ 1 at the centre) at noon is within 2,250 R of the mouth, a tenth of the
  pool; the pool is mostly a dark floor around a lit mouth.
- **The sweep** (`sweep`): the source moves along the edge from 60° east of south at sunrise to 60° west of south at
  sunset, linearly in time (the sun rises in the east: in the morning the light enters the mouth's eastern side).
  Off, it stays due south.
- **Self-shading** as stage 0 (§2 there; §11 C2): a node receives I × (0.3 + 0.7 max(0, cos β)), β between its normal
  and the direction from the cell's centre to the source; I read at the node's own place.

The gradient across one body (2 R out of thousands) is nothing; direction comes from the shading, which gives a
contrast of 0.7 of the light at any distance, and distance from the mouth can only be read from the brightness over
time, which also changes with the hour (§11, the ambiguity).

## 4. The cell

As stage 0's §3 and its clarifications (`stage0.md` §11 C1, C4–C6, C10–C12): N = 16 wall nodes, K = 8 core neurons,
one CTRNN with the topology mask, the ring's shared unit, both spoke modes (uniform, fourier1), the genome of 103 or
135 numbers with the ranges of stage 0 except τ (§1), the cilia without momentum, the noise on its named streams, the
tick order. Nothing in the cell changes but the two rescaled bounds and τ's range.

## 5. Energy and damage

- **Resting cost c₀ = 1/60,000 a tick.** *Rule: a full reserve rests through 16.7 h, so a night costs 0.72 and a cell
  must reach sunset with at least that.*
- **Beating cost c₁ = c₀:** every cilium beating fully doubles the cost, as stage 0.
- **Gain η = 6 c₀ = 1/10,000 a tick at full saturation**, gain = η (1/N) Σ P(Iᵢ), P(I) = I / (1 + I). *Rule: a cell at
  the damage threshold (P = 0.8) at noon fills from 0.5 to full in 2.2 h.* Resting pays where I > 0.2; over a day
  with a night, sitting pays only where the daytime mean of P exceeds about 0.27.
- **Damage (`damage`):** D ← D + k_D (1/N) Σ max(0, Iᵢ − I_d) − r_D D, death at D = 1. **I_d = 4** (where
  photoinhibition sets in for a *Chlamydomonas*-like cell, a few hundred µmol). **k_D = 1.58 × 10⁻⁴ a tick per unit
  excess.** *Rule: an hour at the mouth at noon kills* (the cell's centre one radius from the source; the wall's mean
  excess there is 1.76). **r_D = 1/7,200 a tick:** *repair e-folds in two hours in the dark.* Off, I_d = ∞. At noon
  the burn zone (I ≥ 4 at the centre) is within 919 R of the mouth, 2% of the pool; but a still cell is killed only
  within about 400 R, where I at noon is above 7.6 (§14): the lethal contour sits inside the threshold's. *A decision
  for the owner (§12).*
- **The reserve** E ∈ [0, 1], death at E = 0, as stage 0; a cell dead at a tick's end counts 0 thereafter.

## 6. Starts, the phase, and the lifetime

A start is a position uniform over the disc of radius 4,999 R, a heading uniform, and **a phase uniform over the
day** (ticks after sunrise), drawn in that order (phase, heading, position) from stream `starts` at **seed 2** (fresh:
stage 0 used 0, the probes 1).

**The reserve matches the phase.** E₀(φ) is what a cell that fills at the damage threshold by day and rests by night
holds at that hour: 0.28 at sunrise (1 − a night's cost), rising at that cell's net rate (3.8 c₀ a tick) to full
3.2 h after sunrise, 1 until sunset, then falling at c₀ a tick to 0.28 at the next sunrise. By the hour: 0.28, 0.96,
1, 1, 1 (sunset), 0.82, 0.64, 0.46. *Rule: a start at dusk with stage 0's 0.5 is unsurvivable even at rest; the
matching reserve makes every phase survivable by a cell that behaves well.*

**The lifetime runs to the second sunrise after the start:** 24 h for a start just before sunrise, 48 h for one just
after; every lifetime holds at least one whole day and one whole night and ends at dawn. *Rule: a lifetime that ends
at dusk lets a cell that starts at dusk with a full reserve survive anywhere without feeding; ending at sunrise, every
cell has to come through a night on what it gathered.* Under this rule a still cell survives, at any phase, roughly
where a day's net gain covers 0.44 (§14 checks this by position).

## 7. Measures

Per run, as stage 0 §5 (survival; fitness, the mean of E over the lifetime with dead ticks 0; light soaked; effort
per unit light; the first tick in the soak region), and new: **beating at night** (the mean beat while daylight is
0); **time in the burn zone** (the share of ticks with I ≥ I_d at the centre) and **damage at the end**; **time in the
soak zone**; the reserve at each sunset and sunrise.

## 8. Baselines

- **B0, still.** Also placed at its best fixed point (§14: where a still cell's mean reserve is highest).
- **B1, random beating**, each gᵢ uniform in (0, 1) each tick (stream `beats`).
- **B2r, the reflex that rests in the dark:** gᵢ = σ(k (Iᵢ − Ī) / (Ī + 0.01)) while Ī ≥ **0.01**, and 0 below (Ī the
  mean of the wall's sensed light; 0.01 is a hundredth of the half-saturation, where resting is sixty times cheaper
  than the gain and twelve times the noise of the mean). *Rule: the preregistered reflex beats on noise all night and
  cannot survive one; the bar must at least rest in the dark.* k the best of {1, 3, 10, 30, 100} on starts 1–50 by
  mean fitness, reported on 51–100.
- **B2rr, the reflex that rests and retreats:** B2r, with the sign of k reversed while Ī > I_d (the darker side beats
  harder: it backs out of the burn). Stage 2's bar; run only with `damage` on.
- **B3, random genomes:** 1,000 per spoke mode from stream `genomes` at seed 2, each on starts 51–70.

## 9. The configurations, in order

| name | `cycle` | `damage` | `sweep` | what it adds |
|---|---|---|---|---|
| noon | off | off | off | the pool at a fixed hour: stage 0's lamp at the new scale |
| day | on | off | off | the day, the night, the phase, the matching reserve |
| burn | on | on | off | damage live: the moving safe edge |
| sweep | on | on | on | the source moving along the mouth |

Each configuration runs every check of §10 that applies to it; a failure is read in its own configuration, so an
interaction between parts shows where it enters.

## 10. The checks (each configuration, each from the same starts)

- **K1, sitting fails.** With `cycle` on: B0 survives on at most 10% of starts 1–100 (the probe's share by position,
  at or under a tenth, confirmed by exact simulation on the real starts); B0 at its best fixed point survives with its
  reserve full at each sunset. In `noon` the share is recorded, not judged (the probe: a quarter of the pool; without a
  night, sitting in dim light pays).
- **K2, the light can be sensed.** The wall's contrast from shading (0.7 of the centre's light) is at least 3 times
  the sensor noise (0.0095) on at least 90% of starts at noon and on at least half an hour after sunrise; and moving
  1,000 R toward the mouth from a start raises the centre's light by at least that, at noon, on at least 90%: the
  distance can be read over time.
- **K3, the light can be reached.** From every start, the noon soak region is within an hour's swim at v_max
  (36,000 R; the pool's width is 10,000).
- **K4, the bar, and motion without sensing.** B2r's survival and fitness on starts 51–100 are recorded as stage 1's
  bar in each configuration. If B1 survives on at least half the starts, light is found without sensing and the
  world is changed before stage 1.
- **K5, random wiring rarely works.** The share of random genomes whose survival over their 20 starts matches or
  beats B2r's: under 5%, else the task is made harder; the share matching B2r's fitness is reported beside it.
- **K6, determinism.** Same seed, same trajectory hash; a batch of P cells reproduces P single runs bit for bit; the
  named streams are independent.
- **K7, damage bites** (`burn` and `sweep` only). B2r, which has no retreat, is killed by damage on at least half of
  starts 51–100 (it climbs into the mouth and sits there at noon); B2rr survives on most. If B2r survives the burn,
  damage is not live enough to make stage 2's question, and its rate is amended.

## 11. Predictions (written before the build)

1. K1 passes in `day`, `burn` and `sweep` (the probe: 6%, 6% and 0% of the pool; the sweep alone makes sitting fail
   everywhere, since no fixed point keeps the moving source). In `noon`, about a quarter of starts survive sitting.
2. K2 passes everywhere: direction is sensible over the whole pool at noon and an hour after sunrise (the probe:
   100% at d₀ = 750 R, 65% at 500 R).
3. K3 passes trivially.
4. B1 survives no start in any configuration with `cycle` on (a night at a mean beat of 0.5 costs 1.08 > 1), and
   few in `noon`.
5. B2r survives most starts in `day` with fitness near 0.7: it reaches the mouth within minutes, fills, rests at
   night. In `burn` it dies on most starts (K7), and B2rr survives most.
6. K5 passes in every configuration; the uniform mode's share is lower than fourier1's; `burn` lowers both further.
   No random genome matches B2r's fitness.
7. The sweep changes B2r's and B2rr's fitness little (they follow the light).
8. K6 passes.
9. **The ambiguity.** With `cycle` on, the reflex that rests in the dark spends part of each morning idle at a dim
   place where the light is still below its rest threshold, and starts later than a cell that reads the light's rise.
   Recorded as the first sign of where comparing over time would pay.

## 12. Decision table

| result | what follows |
|---|---|
| K1–K7 pass in all four configurations | stage 1's preregistration: evolution against B2r (and B2rr with damage) in this world, with the removals of `docs/plan.md` |
| K1, K2 or K3 fails | a dated amendment to the world (its geometry or economy, with the reason), the checks run again |
| K4's clause, K5 or K7 fails | the task made harder, or damage's rate amended (a dated amendment), the checks run again |
| K6 fails | fixed before anything else |
| after two rounds of amendment | the owner |

**Open for the owner before the build:** ω_max at 1 rad a tick (§1); τ to an hour (§1); d₀ = 750 R, which makes the
pool a dark floor around a lit tenth (§3); the damage rule, whose lethal contour lies inside the threshold's (§5); the
lifetime to the second sunrise and the matching reserve (§6); B2r's rest threshold 0.01 (§8); seed 2 (§6).

## 13. The probe, run before the build (`experiments/cave_geometry.py`)

Standalone, with the field of §3 and the economy of §5 written out as formulas; the build ties `protocell/world.py`
to them with a test. A still cell does not move, so its reserve depends only on its place and the hour; the probe
integrates the energy and damage equations for 1,000 places uniform over the pool (stream `starts`, seed 1) at eight
phases three hours apart, over each lifetime of §6, with a step of 60 ticks (the light changes over hours).

- **R1, the falloff:** the largest d₀ in {4,000, 3,000, 2,000, 1,500, 1,000, 750, 500} R at which the share of the
  pool from which a still cell survives at every phase is at most a tenth, with `cycle` on and `damage` off.
- **R2, the damage rate:** k_D from "an hour at the mouth at noon kills".
- Read beside them: the best fixed point, the burn and soak zones at noon, where direction is sensible, the back of
  the pool's light; then the chosen d₀ in `noon`, `burn` and `sweep`.

## 14. The probe's outcome (2026-11-01, 77 s)

Economy as §5: a night costs 0.72; at the threshold a cell fills 0.5 in 2.2 h; the sunrise reserve is 0.28; k_D by
R2 is 1.58 × 10⁻⁴ (the mean excess at the noon mouth 1.76).

`cycle` on, `damage` off:

| d₀ (R) | share of the pool where a still cell survives at every phase (at any phase) | best fixed point: mean reserve, distance from the mouth, noon light | burn zone at noon, soak zone at noon (share of the pool) | direction sensible at noon, at sunrise + 1 h | the back's noon light |
|---|---|---|---|---|---|
| 4,000 | 0.95 (1.00) | 0.72, 244 R, 9.96 | 0.38, 1.00 | 1.00, 1.00 | 1.38 |
| 3,000 | 0.67 (0.79) | 0.72, 244 R, 9.93 | 0.22, 0.93 | 1.00, 1.00 | 0.83 |
| 2,000 | 0.36 (0.42) | 0.72, 244 R, 9.85 | 0.12, 0.53 | 1.00, 1.00 | 0.39 |
| 1,500 | 0.21 (0.25) | 0.72, 244 R, 9.74 | 0.07, 0.33 | 1.00, 1.00 | 0.22 |
| 1,000 | 0.10 (0.13), just over a tenth | 0.72, 244 R, 9.44 | 0.03, 0.16 | 1.00, 1.00 | 0.099 |
| **750** | **0.06 (0.08)** | 0.72, 244 R, 9.04 | 0.02, 0.10 | 1.00, 1.00 | 0.056 |
| 500 | 0.03 (0.03) | 0.71, 244 R, 8.07 | 0.01, 0.04 | 1.00, 0.65 | 0.025 |

R1 picks **d₀ = 750 R**. At that d₀: `noon`, a still cell survives from 26% of the pool (44% at some phase; the
best point fills to 0.99); `burn`, 6% (7%), the best fixed point now 424 R from the mouth at a noon light of 7.6,
inside the threshold's contour, mean reserve 0.71; `sweep`, **0%** (6% at some phase), the best point 510 R out at
6.8, mean reserve 0.54. The best fixed point without damage is degenerate: every place that fills by sunset has the
same mean reserve, 0.72. Predictions 1 and 2 are written from this table.

## 15. Compute

At 1.5 µs a cell-tick (stage 0's rate) a mean lifetime of 36 h is 0.2 s a cell. The checks: 2 modes × 1,000 genomes
× 20 starts in each of four configurations, 160,000 lifetimes, about 35 min on 16 workers, plus the baselines (a few
minutes). Stage 1's evolution, at 200 genomes × 8 layouts × 200 generations, about an hour a run; held to one run at a
time and 16 workers, logged under the home directory, the machine's sleep inhibited.

## 16. What would change this document

Its open points (§12) by the owner before the build, as dated notes here; after its checks have run, nothing but
dated amendments recorded here before stage 1. The build adds to `protocell/`: a source whose position and intensity
depend on the tick, the three switches, damage's rate and repair, the phase in a start and its matching reserve, the
lifetime to the second sunrise, the night and burn measures, B2r and B2rr; and tests for each, including that
`world.py`'s cave equals this probe's formulas.
