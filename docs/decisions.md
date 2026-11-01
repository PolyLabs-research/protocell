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

## D3 — The world from stage 1 on: a cave pool on a 24-hour cycle, its parts as switches, checked in order

**Date:** 2026-11-01  
**Why:** the owner's direction on reading D2: "imagine a cave with a small flat pool at the bottom, the cave is south
facing and runs on a 24 hr cycle; the lifetime will need to survive at least a night." Put to the owner as a world
that holds the plan's stages 1 to 4 at once (seeking; management with damage; comparing over time, since a pool is
thousands of radii across and distance can only be read from brightness over time; and changing light), with the
consequence that the preregistered reflex, beating on noise all night, cannot survive one; the owner: "agree with
your suggestions, let's go with a 1 s tick, a random phase, widened."

### Decided
1. **The cave pool replaces both of stage 0's worlds from stage 1 on.** The lamp was the cave at a fixed hour and
   passed; the spot is dropped, so D2 E1's choice about the spot is overtaken.
2. **Its parts are built as switches and checked one at a time, in order:** the pool at noon; then the day, the
   night, the random phase and the matching reserve; then damage; then the sun's sweep along the mouth. Each run is
   minutes, so an interaction between parts shows where it enters (the quantum-rat lesson).
3. **A tick is 1 s**, with stage 0's per-tick quantities rescaled, not reset (`docs/prereg/cave.md` §1).
4. **A random phase**, with the reserve set to match it (the reserve of a cell that fills by day and rests by night),
   and the lifetime running to the second sunrise, so every cell comes through a night on what it gathered.
5. **The time constants widened** to a second to an hour, so slow integration and a clock are within reach.
6. **The bar is a reflex that rests in the dark** (and, with damage, one that also retreats), since the preregistered
   reflex dies every night.
7. **The open numbers are set by rules and a probe before the build** (`experiments/cave_geometry.py`, fresh points,
   no simulation): the falloff length is the largest at which a still cell survives from at most a tenth of the pool
   (750 R), the damage rate the one at which an hour at the noon mouth kills.

**Read from the probe, before the build:** with the sweep on, no fixed point in the pool keeps a still cell alive at
every phase (sitting fails everywhere); and the damage rule's lethal contour lies well inside the threshold's (a still
cell is killed only within about 400 R of the mouth, where the noon light is above 7.6, while the threshold's contour
is at 919 R), which the owner is asked to rule on.

**Impact:** `docs/prereg/cave.md` (the draft, with its open points for the owner in §12 and the probe's table in
§14); `experiments/cave_geometry.py`; this entry; `README.md`. Nothing of the world is built until the draft is
agreed.

## D4 — The cave pool built and checked: all four configurations pass K1–K7 after one amendment to the bar

**Date:** 2026-11-01  
**Why:** the owner on the cave's open points (D3, `docs/prereg/cave.md` §12): "for this run go with what makes
sense." I ruled on all seven as drafted, with my reasons, in a dated note in §12 before the build; three pre-run
clarifications followed during the build, also before any check ran. Built on branch `cave-world` (code `f1fd82f`;
a crash in the runner's full-size path fixed in `c01b8ff` before any result). Run 1, as preregistered
(`c01b8ff`, clean tree, warnings as errors, 94 min on 16 workers, 162,900 cells): noon and day passed; burn and
sweep failed through B2rr. Amendment A1 (§17, `ce46f4e`) with a geometric reason and a probe on fresh starts; run 2
of burn and sweep (`ce46f4e`, 47 min, 81,800 cells): every check passes. Alongside, at the owner's request, a
replay viewer and an interactive page of the network (B below).

### A. Built
The cave as a light kind beside the spot and the lamp (`protocell/world.py`): a mouth on the pool's southern edge,
its light falling as 1/(1 + (d/750)²), a half-sine day and a dark night, the sun's sweep along the mouth, starts with a
phase and lifetimes to the second sunrise. Damage live by its rule (`energy.py`, k_D = 1.58 × 10⁻⁴); the reserve
matched to the phase. Each cell's own time and end, a death's cause, the night and burn measures, the reflexes that
rest in the dark and also retreat (`sim.py`). The 1 s tick's constants (`config.py`, `CAVE`). The runner of K1–K7 in
four configurations (`experiments/cave.py`), and the retreat probe (`experiments/cave_retreat_probe.py`). 76 tests,
among them that the built light equals the probe's formulas and that stage 0's recorded hashes still come out.

### B. Tools for looking at the cell (the owner's request, mid-run)
- **A replay viewer** (`tools/replay.py`): reruns up to three cells from one start with the checks' code, seed and
  noise, and writes a page that plays their lifetimes back. It shows the pool with its light and each cell's track,
  the chosen cell's body, and its reserve and damage over the lifetime. It reads stage 1's evolved genomes from a
  `.npy` file. To support it, `simulate` takes an observer that only reads (tested: the same bits with one attached).
- **The network page** (`docs/network.html`, from `tools/network_doc.py`): generated from the code. It shows who
  connects to whom, the mask, which genome number sets which weight in each spoke mode (found by moving each number
  and decoding), example genomes, and one tick with a cilia demo.

### C. Measured

| check | noon (run 1) | day (run 1) | burn (run 2, A1) | sweep (run 2, A1) |
|---|---|---|---|---|
| K1 sitting fails: B0 survives ≤ 10%; full at each sunset at the best fixed point | recorded, not judged: 38% (probe 26%) | passes: 6% (probe 6.3%); best point full on 100% | passes: 6% (probe 6.1%); best point (424 R out) full on 100% | passes: 2%; the second clause, read on B2rr, 100% |
| K2 the light can be sensed: contrast ≥ 3 × noise at noon, an hour after sunrise; the rise 1,000 R nearer | passes: 100%, 100%, 100% | passes: the same | passes: the same | passes: the same |
| K3 the noon soak region within an hour | passes: the farthest start 760 s away | passes | passes | passes |
| K4 the bar | B2r k = 100: survival 100%, fitness 0.991 | **B2r k = 100: survival 100%, fitness 0.698**, no beating at night | B2r k = 1: survival 0%, fitness 0.199 (it burns; the bar is B2rr) | B2r k = 100: survival 0%, fitness 0.202 |
| K4 motion without sensing: B1 survives < 50% | passes: 19% | passes: 0% | passes: 0% | passes: 0% |
| K5 random genomes matching the bar's survival < 5% | passes: uniform 2.7%, fourier1 2.0% | passes: 0.0%, 0.0% | passes: 0.0%, 0.0% against B2rr | passes: 0.0%, 0.0% against B2rr |
| K5, the same against the bar's fitness | 0% and 0% (best random 0.979 against 0.991) | 0%, 0% (best 0.452) | 0%, 0% (best 0.329) | 0%, 0% (best 0.444) |
| K6 determinism | passes | passes | passes | passes |
| K7 damage bites: B2r burnt on ≥ half; B2rr survives most | not judged | not judged | **passes: B2r burnt on 100%; B2rr k = 100 survives 100%, fitness 0.688** | **passes: 100%; B2rr k = 100 survives 100%, fitness 0.685** |

Run 1's burn and sweep, as preregistered (`docs/data/cave/as-preregistered/`): K1–K4 and K6 as in run 2, but **B2rr
burnt on every report start at every gain** (burn k = 10, fitness 0.323; sweep k = 100, 0.330), so **K7 failed**; K5
was vacuous ("100%" of genomes matched B2r's zero survival); sweep's K1 failed through B2rr. Run 2 reproduced every
table but B2rr's two byte for byte.

### D. Reading
1. **The world works as built; the bar did not.** In every configuration the light can be sensed and reached,
   sitting fails, random beating dies, and random wiring never reaches the bar's fitness. What failed in run 1 was
   B2rr's rule. It backed out when its wall's mean light passed the threshold. But damage counts each node, and the
   cell's own shading makes the mean 0.52 of its lit side. So it held at noon 411 R from the mouth with its lit nodes
   near 7.7, where damage settles at 1.08. That is the lethal contour the probe had already found. Backing out on its
   brightest node holds it 920 R out, on the threshold's own contour (the burn replay shows it riding that contour at
   noon).
2. **Damage costs a well-behaved reflex almost nothing.** B2rr scores 0.688 in burn against B2r's 0.698 in day
   without damage. The safe edge has enough light to fill the reserve, so stage 2's question is whether evolution
   finds the edge, not whether the edge pays.
3. **Noon alone is too easy to test much.** Without a night, sitting in dim light pays (38% of still cells survive),
   random beating survives 19%, and the best random genome comes within 0.012 of the reflex's fitness. The night is
   what makes the task.
4. **The best random genome parks; it does not seek.** Uniform genome 694 is the best random genome in both day and
   burn (survival 65% and 35% of its 20 starts). In the day replay it sits on the pool's edge near the mouth, beating
   every cilium almost fully, so the pulls cancel and it barely moves. It keeps beating at night, so its reserve falls
   faster than the resting reflex's.
5. **My errors.** The runner's full-size path called the probe with no phases and crashed at the first configuration
   of the first launch (no result; fixed in `c01b8ff`; the smoke test never reached that path). B2rr's rule was mine
   (D3, §8), and I wrote it on the mean without checking it against the per-node damage law. The amendment corrects
   that.
6. **Predictions (§11):**
   - (1) K1 passes in day, burn and sweep ✓ (6%, 6%, 2%). About a quarter of starts survive sitting in noon ✗: 38%.
   - (2) K2 passes everywhere ✓.
   - (3) K3 passes trivially ✓.
   - (4) B1 survives no start with the cycle on ✓ (0%), and few in noon ✓ (19%).
   - (5) B2r survives most starts in day with fitness near 0.7 ✓ (100%, 0.698). In burn B2r dies on most starts ✓
     (all). B2rr survives most ✗ as preregistered (0%), ✓ under A1 (100%).
   - (6) K5 passes everywhere ✓, under A1 for burn and sweep. The uniform mode's share is lower than fourier1's ✗:
     in noon it was higher (2.7% against 2.0%), and elsewhere both are 0. Burn lowers both further ✓ (to 0). No random
     genome matches the bar's fitness ✓.
   - (7) The sweep changes B2r's and B2rr's fitness little ✓ (0.199 against 0.202; 0.688 against 0.685).
   - (8) K6 passes ✓.
   - (9) The reflex idles at dim places in the morning: not measured. The checks have no measure for it. A replay can
     show it, and stage 1 should measure it if comparing over time is to be tested.

### E. Clarifications and the amendment
- **The open points, decided by me** under the owner's "what makes sense" (§12's dated note): ω_max = 1 rad a tick;
  τ from 1 s to an hour; d₀ = 750 R by its rule; the damage rule "an hour at the noon mouth kills"; the lifetime to the
  second sunrise with the matching reserve; B2r's rest threshold 0.01; seed 2. One number added: the reserve rule's
  fill light, I = 4 in every configuration.
- **Pre-run clarifications** (§12): K1's second clause read on B2rr in sweep, where no fixed point survives; "killed
  by damage" as D reaching 1 first; K2's hours; integer phases; each cell frozen after its own lifetime; B2rr's gain
  chosen as B2r's; quick runs on a 2,000-tick day.
- **Amendment A1** (§17, after run 1): B2rr backs out while its *brightest node* is above I_d, not the wall's mean.
  K5, where damage is on, compares with B2rr, the configuration's bar. The world is unchanged. The probe on fresh
  starts: on the brightest node, every start survives in burn and sweep at every gain; on the mean, none.

### F. Decisions this surfaces (the owner's)
1. **Whether the cave, as checked, is stage 1's world.** Recommended: yes.
2. **Which configuration stage 1 evolves in.** Recommended: **day** first, against B2r (fitness 0.698). It holds
   stage 1's question (seek the light, then rest through the night on what was gathered). Then burn and sweep as stage
   2, against B2rr (0.688 and 0.685). Noon is too easy to train in (D3).
3. **Both spoke modes in stage 1** (D2 F2, still open). Recommended: yes. In these runs the best random genome was
   uniform, and uniform wiring is the strict reading of D1.4's repeated units.
4. **The bar is fitness**, with survival and effort per unit light beside it (D2 F3, still open). Recommended:
   yes. Survival is 100% for every bar here, so it cannot rank an evolved cell above one.
5. **Confirm or overturn the rulings I made for you:** the seven open points, and A1's brightest-node rule.
6. **Merging:** `stage0-build` and `cave-world` (which contains it) are pushed and unmerged. Merging to main is the
   owner's call.

**Impact:** this entry; `docs/prereg/cave.md` (§12's rulings and clarifications, §17 run 1 and A1, §18 the record
that the checks ran); `protocell/` (world, energy, sim, config); `experiments/cave.py`,
`experiments/cave_retreat_probe.py`; `tools/` (replay, network page); `docs/network.html`; `docs/data/cave/` (noon
and day from run 1, burn and sweep from run 2, `as-preregistered/` run 1's burn and sweep, `retreat_probe/`);
`tests/`; `README.md`.
