# Decisions log

One entry per decision, numbered D1, D2, ... Each says what was decided, why, what it rests on, and what it changed.
Results are reported as they came out, including failed predictions and errors; an entry is not rewritten after the
fact, it is corrected by a dated note.

## D1 — The project founded: a single cell that manages light, evolved first

**Date:** 2026-11-01  
**Why:** the owner's direction after quantum-rat's part 2 (its `docs/decisions.md` G58–G62): "simplify and go with my
first-principles build approach. The beginning is single-cell life." The organism, as the owner described it: a body
that is a string of neural nodes daisy-chained in a closed loop like a cell wall, each node connected into a central
network, so that brain and wall are one structure; the wall nodes feed light intensity in; the network optimises for
light and moves to soak up more of it. The plan (`docs/plan.md`) was put to the owner with six decisions and agreed in
full ("agree on all").

### Decided
1. **Optimiser: evolution first**, over the network's weights; learning within a lifetime later; gradient-based
   training only as a performance ceiling.
2. **The goal: light as food, with damage above a threshold**, so the cell manages its exposure rather than only
   maximising it.
3. **Movement: the wall nodes drive cilia**; the core steers by feeding back into the wall. (The core driving speed and
   turn directly is kept as a comparison.)
4. **The membrane: repeated identical units**, the same wiring tiled around the ring.
5. **The repository:** `PolyLabs-research/protocell`, private.
6. **The build:** quantum-rat's stack and discipline: Python 3.11, numpy, pytest, GitHub Actions; preregistration, design
   probes on fresh seeds, this log, bit-for-bit determinism, runs from a clean tree with numerical warnings as errors.

**Impact:** `docs/plan.md`, this log, `docs/prereg/stage0.md` (draft), the repository's scaffolding.

## D2 — Stage 0 built and checked: the world passes W1–W6 after one geometric amendment to the spot

**Date:** 2026-11-01  
**Why:** stage 0's preregistration (`docs/prereg/stage0.md`, D1) asked for the world, the cell, its energy and the
baselines to be built and checked before anything is evolved. Built on branch `stage0-build` as preregistered, with
the points the preregistration left open fixed in its §11 as pre-run clarifications C1–C12 before any check ran
(code `e4799c4`). Run 1, as preregistered (`docs/data/stage0/as-preregistered/`, `e4799c4`, clean tree, warnings as
errors, 60 s on 16 workers, 81,200 cells): the lamp passed everything, the spot failed W1 and W5. Amendment A1
(§11; `78c4c38`): the spot narrowed from σ = 20 to 16 R and its starts moved from 42 to at least 38 R, for the
geometric reasons below; nothing else changed. Run 2 (`docs/data/stage0/`, `78c4c38`, the same discipline, 60 s):
every check passes in both worlds, and the lamp's results are bit for bit run 1's.

### A. Built
The dish, the spot and the lamp with the cell's self-shading, starts from stream `starts` (`protocell/world.py`);
the cell as one CTRNN with the topology mask, the ring's shared unit, both spoke modes, and the genome of 103
(uniform) or 135 (fourier1) numbers with encode and decode (`cell.py`); the cilia without momentum (`motion.py`);
saturating photosynthesis, the two costs, death at E = 0, damage built and inert (`energy.py`); a whole population
at once, with B0–B2 and the network cell as controllers and the noise keyed per (cell, start) so a batch equals its
singles (`sim.py`); the runner of W1–W6 with a process pool for the random genomes (`experiments/stage0.py`); 51
tests, among them W6's three properties. A lifetime of 1,000 cells takes 4.4 s on one core; the whole of stage 0,
60 s on 16.

### B. Measured

| check | spot, run 1 (as preregistered) | spot, run 2 (A1) | lamp (both runs, bit for bit) |
|---|---|---|---|
| W1 still cell dies on ≥ 90% of starts; gains at the brightest point | **fails:** dies on 49% (every start nearer than 45.1 R survives); gains at the brightest point on 100% | passes: dies on 100% (median tick 1,227); gains on 100% | passes: dies on 100% (median tick 1,266); gains on 100% |
| W2 spread over the wall ≥ 3 × noise on ≥ half the starts | passes: 100% (spread 0.031–0.069) | passes: 69% (median spread 0.042, least 0.007) | passes: 100% (median 0.224) |
| W3 farthest start within 10% of the lifetime (300 ticks) at v_max | passes: 19 ticks | passes: 26 ticks (median 15) | passes: 53 ticks (median 36) |
| W4 the bar (B2 on starts 51–100) | k = 100: survival 100%, fitness 0.926 | **k = 100: survival 100%, fitness 0.924**, light soaked 0.797, beat 0.50, effort per unit light 0.63, soak region reached in 16 ticks (median) | **k = 30: survival 100%, fitness 0.857**, light 0.632, beat 0.40, effort 0.64, reached in 38 ticks |
| W4 motion without sensing (B1 survival < 50%) | passes: 10% (reached the soak region on 13%) | passes: 0% (reached on 2%) | passes: 0% (reached none) |
| W5 random genomes matching B2's survival < 5% (expected < 1%) | uniform 1.9% passes; **fourier1 12.6% fails** | uniform 0.0%; fourier1 4.4%, passes | uniform 3.6%; fourier1 1.4% |
| W5, the same against B2's fitness | 0% in both modes | 0% in both modes | 0% in both modes |
| W6 same seed same hash; batch = singles; streams independent | passes | passes | passes |

The reflex's selection is flat above k = 10 (spot: 0.914, 0.922, 0.924 for k = 10, 30, 100; lamp: 0.856, 0.857,
0.857); k = 1 is clearly worse (0.76, 0.74).

### C. Reading
1. **W1 failed by an arithmetic slip in the preregistration, not by the physics.** §2 put the spot's starts where
   I < 0.5, "where the light does not pay for resting"; that is the break-even light, at which a still cell loses
   nothing and never starves. At the nearest allowed start (42 R, I = 0.46) it lost 0.053/1500 a tick and would
   have lived 14,000 ticks. To starve within a lifetime from E = 0.5 it must lose 0.25/1500 a tick, so I ≤ 1/3, which
   the spot reached only beyond 45.1 R; run 1's survivors were exactly the starts nearer than that. The lamp's
   starts passed because the cell shades itself: a still cell's mean shading factor is 0.3 + 0.7/π = 0.52, which
   halves its light. (My first estimate missed the shading too.)
2. **W5 failed on the spot because the spot was too easy to find, not because random wiring works.** Each of the
   12.6% of fourier1 genomes that matched the reflex's survival had reached the soak region and soaked light at a
   mean P of 0.62 while beating at 0.75: movers, not still cells. The preregistered spot's soak region covered 58%
   of the disc the cell's centre may occupy, and a start was at most 11 R from its edge. In the fourier1 mode a
   random core-to-wall spoke gives the wall a pattern fixed in the body's frame, so the cell moves in a line or a
   circle and sweeps the dish; in the uniform mode every wall node gets the same core input and most random cells
   do not move (1.9%). The lamp's soak region covers 25% of the disc and there 1.4% matched.
3. **The Gaussian spot has a narrow window, as §9 half-foresaw ("narrowly for the spot").** A start must be dark
   enough that a still cell starves, the soak region small enough that moving at random does not find it, and the
   light's difference across one body at the start must beat the sensor noise; a Gaussian's relative gradient,
   2r/σ², is small where it is dark. The probe in A1's table (geometry only, fresh starts) shows W2 holding on at
   least two thirds of starts down to σ = 16 and failing below 15; the spot cannot be made as sparse as the lamp
   (25% of the disc) without W2 failing. Under A1 the spot is 37% of the disc, its W2 share 0.69 (the least spread
   0.007, under the noise: a third of the spot's starts cannot sense the gradient at once), and W5's fourier1 share
   is 4.4%, under the 5% rule but above the 1% expected. Every random genome that survives everything is still a
   hard mover (beat 0.87, light P 0.66, fitness 0.53).
4. **On fitness, random wiring never works.** No random genome in any mode or world matched the reflex's fitness
   (0.92 spot, 0.86 lamp; the best random fitness 0.79). Survival is a coarse measure in a world where the light is
   reachable in 20 ticks; fitness separates the reflex from the movers by a wide margin.
5. **The ring alone can be a reflex where the contrast is large.** In the uniform mode the core sees only the total,
   yet 3.6% of uniform genomes matched the reflex's survival at the lamp (0.0% at the spot after A1). A wall node's
   own sensory input raises its own beat (g ≥ 0), which is B2's rule built into the ring whenever the wall is not
   saturated and |α| < π/2; the lamp's shading gives a 70% contrast for it to work on, the spot's gradient a few
   percent. Stage 1's removals (the ring's links, the core) will have to reckon with this.
6. **Determinism held across runs and a code change.** Run 2 reproduced run 1's lamp tables and hashes bit for
   bit while the spot's configuration changed between them; within a run, five-cell batches equal their singles, and
   switching one noise stream off left the others' digests unchanged.
7. **Predictions (§9):** W1 passes ✗ (the spot failed as preregistered; passes under A1). W2 passes for the lamp
   with a contrast of about 0.7 of the light ✓ (median spread 0.22 on an unshaded light of 0.32 at the start) and narrowly for
   the spot ✓ (100% as preregistered, 69% under A1). W3 passes ✓. B2 survives most spot starts and most lamp starts
   ✓ (all, in both). B1 survives rarely ✓ (10%, then 0%; lamp 0%). W5 passes in the uniform mode ✓ (1.9%, 0.0%,
   3.6%) and less clearly in fourier1 ✓ in direction (12.6% ✗ as preregistered; 4.4% under A1; lamp 1.4%), but the
   reason given, a reflex wired through the core, was not what the survivors did: they moved blindly. "Expected
   under 1%" ✗ for the spot's fourier1 (4.4%) and the lamp's uniform (3.6%).

### D. Clarifications and the amendment
- Pre-run clarifications C1–C12 (§11, before any run): the tick order; light read at each node's own place with
  the lamp's direction from the cell's centre; the brightest point and the soak region as the unshaded intensity at
  the centre, I ≥ 1; starts uniform over the 44 R disc by rejection, start k the k-th drawn; noise keyed per (cell,
  start) in chunks of 250 ticks; **B1's random beats on their own stream `beats` rather than `motion`** (the one
  clarification that alters a stated wiring, so that switching the rotational noise off leaves the beats as they
  were); the reflex's Ī as the mean of the sensed light and its gain chosen by mean fitness on starts 1–50; B3 on
  starts 51–70; damage's placeholder repair rate 0.01; the measures' definitions; the genome's order; the hash; the
  clipped sigmoid.
- **Amendment A1** (§11, after run 1): σ = 16 R, starts ≥ 38 R, derived from two rules on fresh starts (seed 1):
  a start is where a still cell starves within two thirds of the lifetime (I ≤ 0.263), and the spot is the narrowest
  at which the spread at such a start beats three times the sensor noise on at least two thirds of starts. Raising
  the resting cost instead would have fixed W1 but not W5's reason, and would have changed the lamp world, which
  passed.

### E. Decisions this surfaces (the owner's)
1. **Whether stage 0 is done on this world:** the lamp as preregistered, the spot under A1 (37% of the disc; a
   third of its starts below the noise at the first tick; 4.4% of random fourier1 genomes surviving everything).
   Recommended: yes, with stage 1's bar on fitness (C4), since survival is nearly saturated. The alternative is a
   spot with a steeper edge (a profile like the lamp's 1/(1 + (d/20)²), or a plateau with a rim), which would need
   its own geometric probe; or stage 1 on the lamp alone.
2. **Whether stage 1 compares both spoke modes.** Recommended: yes. They differ in what random wiring can do
   (fourier1 cells move blindly and sweep; uniform cells mostly cannot move, and can only steer by the ring's local
   reflex or by the core comparing the total over time), which is the structural question stage 1's removals ask.
3. **Stage 1's bar:** B2 at k = 100 on the spot (fitness 0.924, survival 100%, effort per unit light 0.63) and
   k = 30 on the lamp (0.857, 100%, 0.64), on starts 51–100. Recommended: the bar is fitness, with survival and
   effort per unit light reported beside it (plan lesson 4), and evaluation on fresh starts (§8).
4. **The rule for future worlds:** a start is where a still cell starves within two thirds of the lifetime, read
   off the economy before the geometry is fixed. Recommended as a standing rule for every later preregistration
   (stage 2's damage world, stage 3's shallow gradients).
5. **Clarification C5** (B1's own `beats` stream): to keep, or to revert to `motion` as §3 said.

**Impact:** this entry; `docs/prereg/stage0.md` (§11: C1–C12, A1, the record that the checks ran); `protocell/`
(config, world, cell, motion, energy, sim; rng keyed streams), `experiments/stage0.py`,
`experiments/stage0_geometry.py`, `tests/`; `docs/data/stage0/` (run 2) and `docs/data/stage0/as-preregistered/`
(run 1); `docs/determinism.md` (rule 3's mechanism); `README.md`.
