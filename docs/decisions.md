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

**Correction (2026-11-01, after this entry was pushed): CI was red from `f1fd82f` to `3929b03`, my error.** The
test I added to pin stage 0's recorded trajectory hashes (`tests/test_stage0_pinned.py`) failed on GitHub's runners.
There the spot hash comes out different, because numpy's vectorised exp, sin and cos depend on the CPU's instruction
set, and this machine has AVX-512. `docs/determinism.md` claims the same bits on the same platform only, so the test
overstated the claim. I had checked CI while `f1fd82f`'s run was still in progress and did not look again. No result is
affected: every run was made on this machine and checked by its own manifest, and the 76 tests passed here. The test
now runs only on the platform that recorded the hashes (machine, numpy version, SIMD extensions) and says why it skips
elsewhere. The observer's test compares runs with and without an observer, on any platform.

**Impact:** this entry; `docs/prereg/cave.md` (§12's rulings and clarifications, §17 run 1 and A1, §18 the record
that the checks ran); `protocell/` (world, energy, sim, config); `experiments/cave.py`,
`experiments/cave_retreat_probe.py`; `tools/` (replay, network page); `docs/network.html`; `docs/data/cave/` (noon
and day from run 1, burn and sweep from run 2, `as-preregistered/` run 1's burn and sweep, `retreat_probe/`);
`tests/`; `README.md`.

## D5 — The owner's decisions on D4: the cave is stage 1's world, evolved in day first, both spoke modes, fitness as the bar; merged

**Date:** 2026-11-01  
**Why:** the owner's answers to D4 F1–F6: "1. Yes 2. Agree 3. Yes 4. Yes 5. Confirm 6. Merge".

### Decided
1. **The cave pool, as checked in D4, is stage 1's world.**
2. **Stage 1 evolves in the day configuration**, against B2r at k = 100 (on starts 51–100 at seed 2: survival 100%,
   fitness 0.698). Burn and sweep are stage 2's, against B2rr (0.688 and 0.685).
3. **Stage 1 compares both spoke modes**, uniform and fourier1 (D2 E2 closed).
4. **The bar is fitness**, with survival and effort per unit light reported beside it (D2 E3 closed).
5. **The rulings made under "go with what makes sense" are confirmed**: the seven open points of
   `docs/prereg/cave.md` §12 and amendment A1 (§17, B2rr backs out on its brightest node).
6. **`stage0-build` and `cave-world` are merged to main.**

Not asked again in D4, and so still open from D2: E4, the starvation rule as a standing rule for later worlds (the
cave's falloff rule R1 used the same idea, a still cell surviving from at most a tenth of the pool), and E5, B1's own
`beats` stream (stage 0 clarification C5), which every run since has used.

**Impact:** this entry; `README.md`; main. Next: stage 1's preregistration, drafted before any of it is built.

## D6 — Stage 1 drafted: the reflex is within 2% of the ceiling in every cave configuration

**Date:** 2026-11-01  
**Why:** the owner's "proceed" on D5. While drafting stage 1 (`docs/prereg/stage1.md`), I checked how much better than
the bar any cell could do, which I had not checked when I recommended the day configuration in D4 F2. A still cell
placed at the best fixed point pays nothing to travel or beat, so on the same starts it bounds every cell that must
first get there. The probe (`experiments/stage1_budget.py`, `docs/data/stage1/budget/`, read from D4's tables):

| configuration | the bar | a still cell at the best point | headroom |
|---|---|---|---|
| day | B2r 0.698 | 0.712 | 0.014 |
| burn | B2rr 0.688 | 0.707 | 0.020 |
| sweep | B2rr 0.685 | 0.548 (no fixed point keeps up) | about 0.02 to burn's ceiling |

**Reading.** Everything the cave's cell needs is sensed in the moment: the light's direction through its own shading,
night through darkness. A reflex therefore does nearly as well as a cell can. The plan's question for stage 1, "does an
evolved cell beat the reflex", becomes a test of the last 2% of fitness. Where the plan expects the network to matter
is stage 3, when direction can no longer be read across the body.

**The draft** keeps D5's decisions (day, both spoke modes, fitness). Its primary questions are whether evolution
reaches the reflex (within half the headroom) and which parts the evolved cell uses (the plan's removals). Whether it
beats the reflex is reported, and predicted not to happen. The draft also covers a pilot run per mode, then three
confirmatory runs per mode, about 8 h of compute in all, and 7 predictions.

### Decisions this surfaces (the owner's; `stage1.md` §13)
1. **The question:** reaches the bar plus the removals as primary (recommended), or "beats the reflex" as primary.
2. **The budget:** eight runs, about 8 h here (recommended); fewer replicates; or RunPod, with the cost confirmed
   first.
3. **The optimiser:** a simple genetic algorithm (recommended), or CMA-ES.
4. **The swept day** as a light it never saw: kept as a description (recommended), or dropped.

**Impact:** this entry; `docs/prereg/stage1.md` (draft); `experiments/stage1_budget.py` and its data; `README.md`.

## D7 — Stage 1 ran: evolved cells survive but fall short of the reflex, and every one depends on its core, the core's recurrence and the ring's links

**Date:** 2026-11-02  
**Why:** the owner's answers to `docs/prereg/stage1.md` §13: "1. the first 2. runpod 3. agree 4. agree". Then the
owner's go for each launch: the pilot ("yes go", at most $8.96) and the confirmatory runs ("go on the three pods", at
most $10.08).

**Built.**
- The genetic algorithm and its runner (`protocell/evolve.py`, `experiments/stage1.py`; code `dccf0c3`). A resumed
  run is the same bits as one run straight through.
- The removals (`protocell.cell.apply_removal`).
- RunPod CPU pods under the chess project's lifecycle library (`cloud/`).

**Ran.**
- The pilot: one pod, both modes side by side, code `b5cdd84`, 83 min a run.
- The confirmatory runs: three pods, code `923e8d6`, 80–94 min a run. All four pods were AMD EPYC 9575F with
  32 vCPUs.
- The test: here, code `d7ef2ff`, 4.5 min.
- RunPod cost about $9 in all: the pilot's pod $3.45 (1.6 h of it idle before the job started, my delay), and the
  three confirmatory pods about $5.50.

### A. Measured (the test: 100 fresh starts at seed 5, every controller sharing the noise on a start)

| controller | fitness | against B2r (95% interval) | survival | effort per unit light | beat at night | median time to the soak region | swept day |
|---|---|---|---|---|---|---|---|
| B2r, k = 100 | 0.707 | — | 100% | 0.58 | 0 | 3,802 s | 0.702 |
| the still cell at the best point | 0.720 | — | 100% | — | — | — | — |
| uniform 2001 | 0.697 | −0.011 (−0.013, −0.008) | 100% | 1.08 | 0.012 | 5,464 s | 0.582 |
| uniform 2002 | 0.695 | −0.012 (−0.014, −0.010) | 100% | 1.24 | 0.017 | 4,557 s | 0.580 |
| uniform 2003 | 0.695 | −0.012 (−0.013, −0.011) | 100% | 1.29 | 0.013 | 5,128 s | 0.673 |
| fourier1 3001 | 0.671 | −0.037 (−0.048, −0.028) | 99% | 1.29 | 0.018 | 7,726 s | 0.645 |
| fourier1 3002 | 0.688 | −0.020 (−0.023, −0.017) | 100% | 1.38 | 0.014 | 5,621 s | 0.643 |
| fourier1 3003 | 0.686 | −0.022 (−0.024, −0.020) | 100% | 1.41 | 0.021 | 5,464 s | 0.654 |
| the pilot's uniform 1001 | 0.672 | −0.036 | 100% | 1.46 | 0.013 | 6,985 s | 0.605 |
| the pilot's fourier1 1002 | 0.690 | −0.017 | 100% | 1.31 | 0.013 | 5,473 s | 0.625 |

**The removals** (drop in fitness against the intact champion, the confirmatory champions; "breaks" = the interval's
lower bound above δ = 0.007):

| removal | uniform (3 champions) | fourier1 (3 champions) | breaks |
|---|---|---|---|
| R0, blind | 0.47–0.49 | 0.45–0.48 | all 6 |
| R1, the ring's links cut | 0.012–0.017 | 0.016–0.062 | all 6 (the pilot's fourier1: 0.008, just under) |
| R2, the loop opened | at most 0.001 | at most 0.003 | none |
| R3, the core removed | 0.19–0.53 | 0.09–0.54 | all 6 |
| R4, the core's recurrence removed | 0.08–0.19 | 0.31–0.33 | all 6 |

**The verdicts (§9).**
- **Q1 fails in both modes:** 0 of 3 champions reach the bar in either. The closest, uniform 2001, falls 0.011 short
  against δ = 0.007.
- **Q3 fails in both modes.**
- **Q2:** in both modes the ring's links, the core and the core's recurrence are needed, and the loop's closure is
  not.

### B. Reading
1. **Evolution gets close, not level.** From random wiring (fitness about 0.1, 1% surviving), 100 generations give
   cells that survive every test start and score within 1.5% of the reflex in the uniform mode (3–5% in fourier1).
   They lose the rest in two ways. They arrive later: the median time to the soak region is 4,600–7,700 s, against
   3,800. And they beat about twice as hard per unit of light, including a little at night. The replay shows why: a
   champion that has reached the mouth parks there and beats every cilium at once, and the pulls cancel. The
   reflex's own waste, pressing half its cilia against the edge, is smaller. Four of the six validation curves were
   still rising at generation 90–100.
2. **The evolved cells are built on the interaction of their parts.** Removing the core, the core's recurrence or
   the ring's links breaks every confirmatory champion. Only the loop's closure does nothing. Two cautions limit how
   far this goes:
   - Removing a part also removes its steady drive. A wall neuron that received a constant push from the core has
     its operating point shifted when the core is cut, whatever the core was computing. "Needed" here means the
     evolved solution is built on the part, not that the task requires it.
   - The reflex, with no core, no recurrence and no ring links, does better and generalises better.
3. **They generalise worse than the reflex.** When the sun sweeps along the mouth, a light they never saw in
   training, the champions lose 0.02–0.12 while the reflex loses 0.006. Whatever the evolved cells rely on is tuned
   to a fixed mouth. The reflex follows the light wherever it is.
4. **For the hypothesis:** this is the weak sense of "behaviour emerges from the interaction of parts". The evolved
   behaviour is a property of the interactions, since removing any internal part breaks it. It is not the strong
   sense, in which interacting parts do better than a simpler mechanism. D6 found that this world cannot show the
   strong sense, because the reflex is within 2% of the ceiling. The test confirms that evolution did not find a way
   around it.
5. **The uniform mode did better than fourier1** (0.695–0.697 against 0.671–0.688), as the cave's random genomes
   suggested.
6. **My errors.**
   - The pilot's pod idled 1.6 h before its job started (`cloud/launch_phase.sh` now chains every step).
   - Setup's cost line was mis-quoted, and the SSH call that started the pilot's job hung, harmlessly.
   - Most predictions about the removals and the effort were wrong (below).
   - The campaign's 10-minute pull interval left two pods up to 10 minutes after their jobs ended (about $0.40).
7. **Predictions (§11):**
   - (1) Evolution climbs ✓.
   - (2) Both modes reach the bar ✗ (0 of 3 in each).
   - (3) Neither beats it ✓.
   - (4) The removals:
     - R0 breaks every champion ✓.
     - R1 breaks none ✗ (it breaks all six).
     - R2 breaks none ✓.
     - R4 breaks none ✗ (it breaks all six).
     - R3 breaks fourier1 champions ✓ but not uniform ones ✗ (it breaks all three).
   - (5) The champions' effort per unit light is below B2r's ✗ (it is twice B2r's).
   - (6) The uniform champions are at least as fit as fourier1's ✓.
   - (7) The swept day costs each less than 0.02: ✓ for B2r (0.006), ✗ for the champions (0.02–0.12).

### C. Clarifications and amendments
- The owner's answers and the pre-pilot clarifications are recorded in `stage1.md`: RunPod CPU pods, two runs side by
  side, hourly pulls, the test on this machine, and the noise keys.
- No amendment was made after the pilot.

### D. Decisions this surfaces (the owner's)
1. **Whether stage 1 stands as it is, or the runs go longer.** The decision table (§12) leaves it to the owner.
   Running longer (300 generations, three pods, about 4.5 h, about $15) would show whether evolution closes the last
   1.5%. Recommended: stand as it is. Matching a reflex to the third decimal is not the project's question.
2. **A sharper reading of Q2 before it is used.** Repeat the removals with each part clamped at its average activity
   instead of zeroed. This separates what a part computes from the steady drive it supplies. It is cheap: the six
   champions, here, minutes, and needs no evolution. Recommended: yes, preregistered as a short stage 1b.
3. **The next world.** The plan puts damage next (stage 2: burn, then sweep). But there the reflex is again within 2%
   of the ceiling (D6), so stage 2 would show the same limit. Stage 3's question needs a world where direction cannot
   be read across the body and must be compared over time. That is the cave with the cell made translucent (no
   self-shading), and there a reflex should fail. Recommended: stage 3's world next; stage 2 after it, or folded in.
4. **Merging** `stage1-prereg` and `stage1-build` (which contains it) to main.

**Impact:** this entry; `docs/prereg/stage1.md` (the owner's answers, the clarifications, the pilot's outcome, §16);
`protocell/` (evolve, tables, cell, sim, world); `experiments/stage1.py`, `experiments/stage1_budget.py`; `cloud/`;
`tools/replay.py`; `docs/data/stage1/` (budget, pilot, confirm, test); `tests/`; `README.md`.

## D8 — The owner's decisions on D7: stage 1 stands, a clamped-removal stage 1b, stage 3's translucent cell next; merged

**Date:** 2026-11-02  
**Why:** the owner's answers to D7 D1–D4: "1. let it stand 2. agree 3. agree 4. yes merge".

### Decided
1. **Stage 1 stands as it ran.** No longer runs.
2. **Stage 1b:** the removals repeated with each part's input held at its average instead of zeroed, preregistered
   first (`docs/prereg/stage1b.md`), run here on the existing champions.
3. **The next world is stage 3's:** the cave with the cell made translucent, so the light's direction cannot be read
   across the body and must be compared over time. Stage 2 (damage) comes after it, or folded in.
4. **`stage1-build` (with `stage1-prereg`) is merged to main.**

**Impact:** this entry; main; next, `docs/prereg/stage1b.md` and stage 3's draft.

## D9 — Stage 1b: every pathway of the evolved cells computes; none can be replaced by its average

**Date:** 2026-11-02  
**Why:** D8 2. Preregistered in `docs/prereg/stage1b.md` (`9cee8a5`), before any build. Code `e293b37`, run here in
5 minutes (`docs/data/stage1b/`).

### A. Measured
Each pathway was held at its average: its weights set to zero, and each receiving neuron fed its mean input from the
intact champion's living ticks on stage 1's validation starts. The test used stage 1's 100 test starts, with shared
noise. The intact and zeroed versions reproduce stage 1's test bit for bit.

| pathway | drop when held, uniform (3) | drop when held, fourier1 (3) | breaks | drop when zeroed (stage 1) | held worse than zeroed |
|---|---|---|---|---|---|
| the core's drive to the wall | 0.37–0.41 | 0.27–0.33 | all 6 | 0.09–0.54 | 3 of 6 |
| the core's recurrence | 0.02–0.35 | 0.05–0.32 | all 6 | 0.08–0.33 | 2 of 6 |
| the ring's links | 0.05–0.29 | 0.02–0.05 | all 6 | 0.012–0.062 | 4 of 6 |

With the core's drive held at its average:
- The uniform champions barely beat (mean beat 0.07–0.10, against 0.30–0.35 intact). They never beat at night, and
  only 22–30% survive.
- Two fourier1 champions beat more at night (0.024 and 0.17, against 0.018 and 0.021 intact), and one stops
  altogether.

### B. Reading
1. **No part of the evolved networks can be replaced by a constant.** As registered, all three pathways compute in
   both modes. Their moment-to-moment signals matter, not only their averages. Stage 1's zeroed removals did not
   just measure lost steady drive.
2. **The averages are inputs the intact cells rarely see.** In half the cases, holding a pathway at its average hurt
   more than removing it. The pathways carry signals that differ sharply between the cell's states (day and night,
   near the mouth and far from it), and their average falls between the states. A neuron fed that average sits at
   an operating point the intact cell seldom visits. With the core's drive held, the uniform champions cannot switch
   their wall on by day. That suggests the core's drive is what turns the wall on in the light, though stage 1b does
   not show it directly.
3. **For the hypothesis:** stage 1b strengthens D7's weak sense. The evolved cells' behaviour depends on the
   time-varying interaction of their core, its recurrence and the ring. It still does not show the strong sense (D6,
   D7).
4. **A sharper probe, not run:** hold each pathway at its typical value in each state, its day average by day and its
   night average by night. That would show whether the pathways carry more than the day-and-night state. It is noted
   for a later design, not preregistered.
5. **Predictions (`stage1b.md` §4):**
   - (1) The check holds ✓.
   - (2) The core's drive computes in both modes ✓.
   - (3) Night beating rises when the core's drive is held ✗: it fell to zero in four champions and rose in two.
   - (4) The core's recurrence computes in both modes ✓.
   - (5) The ring's links supply steady drive only ✗: holding them breaks all six, worse than zeroing in four.

**Impact:** this entry; `docs/prereg/stage1b.md` (§7); `protocell/cell.py` (pathways, `hold_at_average`),
`protocell/sim.py`; `experiments/stage1b.py`; `docs/data/stage1b/`; `tests/test_stage1b.py`.

## D10 — Stage 3a: the translucent cell's world passes every check; comparing over time pays, and its simplest form is near the ceiling

**Date:** 2026-11-02  
**Why:** the owner's "agree on all, go" on `docs/prereg/stage3.md` §9: the falloff 600 R by the cave's rule, B5 as the
bar, the run here. Built at `55b0092`; checked in 27 minutes (`docs/data/stage3/`).

### A. Measured (starts 1–100 at seed 8; the bars on starts 51–100)

| | B0 | B1 | B2r, the spatial reflex (k = 100) | B5, run and wait (τₘ = 30 s) | the still cell at the best point |
|---|---|---|---|---|---|
| survival | 4% | 0% | 34% | 100% | 100% |
| fitness | — | — | 0.317 | 0.709 | 0.730 |
| effort per unit light | — | — | 1.08 | 0.06 | 0 |
| median time to the soak region | — | — | 20,577 s | 14,886 s | — |

- **The checks:** T1–T7 all pass.
  - T2: the direction is readable at once on 1% of starts.
  - T3: its rise over 100 R is readable on 65%.
  - T5: B5 is above B2r by 0.392, interval 0.323 to 0.459.
  - T6: no random genome of 2,000 matches B5. The best scores 0.18 (uniform) and 0.24 (fourier1).
- **B5's memory:** its choice of time constant hardly matters between 10 and 100 s (fitness 0.706–0.710). At 3 s and
  at 300 s it loses some starts.

### B. Reading
1. **The world tests what stage 3 asks.** Without its shading the cell cannot read the light's direction at once.
   The reflex that worked in the cave now survives only a third of its starts, and the simplest memory, one
   remembered number, takes every start. Comparing over time pays by 0.39 of fitness, about thirty times stage 1's
   whole headroom.
2. **The simplest comparator is again near the ceiling:** B5 is 0.021 below the still cell at the best point.
   It wins by thrift. It beats only while the light rises (2% of the time) and waits the rest, so it arrives slowly
   but spends almost nothing. As in stage 1, beating the bar is a last-2% question.
3. **What stage 3b can now show** is the one D6 found missing: a contrast a network has to work for. A cell with no
   memory (B2r) scores 0.32. A cell that compares over time can reach 0.71. Whether evolution finds comparison over
   time, and where in the network it puts it (the core's recurrence, or the slow time constants of the wall), is
   the plan's stage 3 question. It has a large signal here.
4. **Random wiring finds almost nothing.** Uniform random genomes all die, and in fourier1 0.4% of starts survive.
   Evolution starts from a harder place than in stage 1.
5. **Predictions (§5):**
   - (1) T1, T2, T3, T6 and T7 pass ✓.
   - (2) B2r survives under 30% ✗ (34%), with fitness under 0.35 ✓ (0.317).
   - (3) B5 survives over 80% ✓ (100%), fitness over 0.55 ✓ (0.709), τₘ at 30 or 100 s ✓ (30).
   - (4) T5 by more than 0.2 ✓ (0.392).
   - (5) B5's headroom over 0.05 ✗ (0.021).

### C. Decisions this surfaces (the owner's)
1. **Stage 3b's preregistration:** evolution in this world against B5, both spoke modes, with the removals. The
   primary questions:
   - does evolution find comparison over time (above B2r by a wide margin, and near B5)?
   - which parts carry it?
   A draft follows.
2. **Merging** `stage1b`, `stage3-prereg` and `stage3-build` (each contains the one before) to main.

**Impact:** this entry; `docs/prereg/stage3.md` (the owner's answers, §11); `protocell/sim.py` (`RunAndWait`);
`experiments/stage3.py`, `experiments/stage3_geometry.py`, `experiments/cave.py` (`check_k6`'s seed);
`docs/data/stage3/`; `tests/test_stage3.py`.

## D11 — Stage 3b: comparing over time evolved only sometimes and partly, and its best evolved form is far below a one-number memory

**Date:** 2026-11-02  
**Why:**
- The owner's go on stage 3b's draft ("Happy with all that, go") and on the pilot's pod ("Launch").
- After the pilot failed, the owner chose amendment A1, the shading fading, among three ("agree with 1. proceed").
- The owner then approved the confirmatory pods ("Yes, proceed").

**Ran.**
- Built at `841ff1f`; A1 built at `fca8740`.
- The pilots and the confirmatory runs on RunPod: about $9 for stage 3b (the failed pilot $2, A1's pilot $1.85, the
  three confirmatory pods $5.15).
- The test here at `8ae8f3f`, in 10 minutes.

### A. Measured
1. **The pilot as preregistered** collapsed onto still cells in both modes. In the translucent world every part of
   comparing over time scores below sitting still when it stands alone.
2. **Under A1** every run first built a working shaded cell: the best training fitness was 0.5–0.7 while shaded.
   Every run then lost most of it as the shading vanished near generation 50.
3. **The test** (100 fresh starts, seed 11):

| controller | fitness | survival | above B2r (95% interval) | share of B5's lead over B2r recovered | mean beat |
|---|---|---|---|---|---|
| B5, run and wait | 0.715 | 100% | — | — | 0.020 |
| B2r, the spatial reflex | 0.332 | 35% | — | — | 0.113 |
| the still cell at the best point | 0.733 | 100% | — | — | 0 |
| fourier1 3202 | 0.483 | 63% | +0.151 (0.111, 0.193) | 39% | 0.284 |
| uniform 2203 | 0.397 | 50% | +0.065 (0.023, 0.108) | 17% | 0.175 |
| fourier1 3201, 3203 | 0.263, 0.267 | 20–22% | below | — | 0.08–0.13 |
| uniform 2201, 2202 | 0.240, 0.242 | 11% | below, almost still | — | 0.01–0.02 |

4. **The verdicts:**
   - Q1 (recover at least half of B5's lead, 0.191) fails in both modes: 0 of 3 each.
   - Q3 fails.
   - Q2: in the fourier1 mode the sensors, the core, its recurrence, the core's slow decay (R6) and the core's drive
     held at its average are needed. In the uniform mode only the core is.
5. **The two working champions** lose 0.15–0.37 to each of the six removals and to two of the holds. Holding the
   core's recurrence at its average costs them only 0.03–0.05.

### B. Reading
1. **Comparing over time evolved only sometimes and partly.** The fading shading gave evolution its path: every run
   built a working shaded cell. Only 2 of 6 kept a working cell once the cue was gone, one per mode, recovering 39%
   and 17% of what memory is worth over the reflex. Two uniform runs sank to near stillness, and two fourier1 runs
   settled below the reflex. Which outcome a run reaches depends on its seed. Three runs per mode cannot say how
   often it succeeds.
2. **The working cells are not B5.** B5 beats 2% of the time and spends almost nothing. The evolved cells beat most
   of the day. In the replay they reach the mouth and park there, beating every cilium, as stage 1's champions did.
3. **Where their memory lives: everywhere.**
   - Making either the core or the wall fast breaks them.
   - So does zeroing the core's recurrence, cutting the ring's links, or removing the core.
   - Stage 3b asked whether memory sits in loops or in slow decay; the answer is both, and in the ring. Holding the
     recurrence at its average costs little, so its steady drive matters more than its fluctuations.
4. **My uniform-mode prediction was wrong.** A uniform cell with no front found a working strategy (2203, above the
   reflex). How it holds a course is not yet understood.
5. **For the hypothesis.** In the one world built so that memory pays, evolution sometimes found cells whose
   behaviour depends on all their interacting parts. The best of them scores 0.48, far below a one-number memory
   (0.715). The strong sense, interacting parts doing better than a simple mechanism, is still not shown.
   - In stage 1 the world gave it no room.
   - Here, too, the simple mechanism (B5) is within 0.02 of the ceiling, so there is no room above it either.
   - And evolution as configured does not reliably reach even the simple mechanism.
6. **A pattern across every world so far.** In the shaded cave, with damage, and in the translucent world, a simple
   rule sits within 2–3% of the ceiling:
   - the reflex in the shaded cave;
   - the reflex that backs out, with damage;
   - run and wait, in the translucent world.

   A world where interacting parts can beat every simple rule has not been built yet. Building one is a design
   question, to be probed before any more evolution.
7. **Predictions (§8):**
   - (1) The fourier1 pilot climbs ✗: as preregistered neither did, and under A1 the uniform one did.
   - (2) The uniform mode does not find comparison over time ✓ (0 of 3); the fourier1 mode does ✗ (0 of 3).
   - (3) Neither reaches B5 ✓.
   - (4) In the fourier1 mode:
     - R0 breaks every champion ✓.
     - Holding the core's drive breaks every champion ✗ (2 of 3).
     - R6 breaks at least 2 of 3 ✓.
     - R4 breaks fewer than R6 ✗ (2 and 2).
   - (5) The champions spend more than B5 ✓.
   - Under A1:
     - (1) ✗.
     - (2) ✗.
     - (3) training fitness falls with the shading and partly recovers ✓.
     - (4) ✗.

### C. A clarification
Q1's "exceeds B2r's by at least half the gap" was read as the interval's lower bound. The best champion's mean
(+0.151) is also below the 0.191 bar, so no reading of the criterion would have passed it.

### D. Decisions this surfaces (the owner's)
1. **Whether stage 3b stands as it ran.** Recommended: yes. Comparing over time is reachable by this evolution
   sometimes and partly; that is the result.
2. **What comes next.** Recommended: design a world where every simple rule leaves real room below the ceiling, and
   probe the baselines' headroom before any evolution, as D6 and stage 3a did.
   - Candidates come from the plan's stage 4: light that changes in ways a rule cannot follow. Examples are a sun
     whose track shifts from day to day, a mouth that moves, or damage that rises with the hour, so a cell has to
     anticipate rather than react.
   - The alternatives: more search in stage 3b's world (longer runs or more runs per mode, about $15–20), or a
     stronger optimiser (CMA-ES, deferred in D6). Neither would show the strong sense while B5 sits at the ceiling.
3. **Merging.** The branch chain is `stage1b` ⊂ `stage3-prereg` ⊂ `stage3-build` ⊂ `stage3b-prereg` ⊂
   `stage3b-build`. Merging the last brings everything to main.

**Impact:** this entry; `docs/prereg/stage3b.md` (the owner's answers, the pilot's outcome, A1, the amended pilot's
outcome, §14); `protocell/evolve.py` (a world per generation, the champion's first generation), `protocell/cell.py`
(the time removals); `experiments/stage3b.py`, `experiments/stage1.py` (seeds as options); `cloud/` (any stage);
`tools/replay.py` (the translucent world, B5); `docs/data/stage3b/`; `tests/`.

**Correction (2026-11-03, read in D14).**
- **Reading B.1 said comparing over time evolved, only sometimes and partly. That is wrong.** Stage 3c tested it
  (`docs/prereg/stage3c.md`, C5) and found that neither working champion compares over time as B5 does.
  - The uniform champion's lead over the reflex comes from reading the light's direction across its body with its
    ring (stage 3c's C1–C3).
  - The fourier1 champion's pull follows the light's level. It has a brief transient of about a minute after a step:
    when the light rises it slows more than the new level dictates. That transient is below C5's threshold and
    opposite in sign to B5's.
- **So stage 3b found no evolved comparison over time.** The numbers in B.1 stand, but the share of "what memory is
  worth" was not memory for comparing.
- **B.3 stands as measured.** Its slow parts and loops are needed, but in the uniform champion they serve the ring's
  timing and its reading, not a comparison.
- **B.4's open question is answered in D14.**

## D12 — The owner's decisions on D11: stage 3b stands; the next world is built to expose how a cell with no front navigates; merged

**Date:** 2026-11-03  
**Why:** the owner on D11's unexplained observation, that uniform champion 2203 found a working strategy although a
uniform cell has no front: "im always interested in observations we can't explain - lets have our next world try and
expose how its managing this. agree with your points, proceed".

### Decided
1. **Stage 3b stands as it ran.**
2. **The next world is built to expose how uniform 2203 reaches and holds the light** (stage 3c). It starts with a
   design probe that describes the champion's movement on fresh starts in its own world. Then a preregistration
   follows: worlds built so that the candidate mechanisms predict different behaviour, with a simple rule for each
   mechanism run beside the champion as a positive control.
3. **D11 D2's principle stands** for any world built for evolution: probe the baselines' headroom first. Stage 3c's
   worlds are for observation, not evolution.
4. **`stage3b-build` (with `stage1b`, `stage3-prereg`, `stage3-build` and `stage3b-prereg`) is merged to main.**

**Impact:** this entry; main; next, stage 3c's design probe and draft.

## D13 — Stage 3c's design probe: the cell with no front reads the light's direction with its ring

**Date:** 2026-11-03  
**Why:** D12, the owner's "lets have our next world try and expose how its managing this".  
**Ran:**
- The probe (`experiments/stage3c_probe.py`) at `fcc8f4c`, from a clean tree with warnings as errors, in 63 s on this
  machine. The data are at `c4cc055`.
- Stage 3's translucent world, fresh starts 1–100 at seed 13, and the champion's network held in place.

### A. Measured
1. **Movement in the pool:**

| cell | fitness | survival | parked | running | runs |
|---|---|---|---|---|---|
| uniform 2203 | 0.420 | 56% | 18% | 25% | 57,154 |
| fourier1 3202 | 0.456 | 59% | 27% | 8% | 2,217 |
| B5, run and wait | 0.708 | 100% | 0% | 4% | 19,526 |
| B2r, the spatial reflex | 0.349 | 39% | 0% | 10% | 107,199 |

2. **The champion's runs start toward the mouth, more so in brighter light.**

| light where the run began | mean cosine to the mouth |
|---|---|
| night | −0.004 |
| 0.1–0.3 | +0.206 |
| 0.3–1 | +0.483 |
| 1–3 | +0.708 |

3. **Held in place, the champion's network is a relaxation oscillator.**
   - In even light below 3, three or four neighbouring nodes beat together for 35–49 s, 27–37 times an hour.
   - At 3–4 they beat without a break.
   - From 5 every node beats, and the cell parks.
4. **Fed light slightly brighter on one side, its runs start toward that side.**
   - The mean cosine is +0.37 when the per-tick signal is 0.13 of the noise of the wall's first Fourier mode, at light
     0.3.
   - It is +0.94 at a signal of 0.89, at light 2.
   - With even light it is 0.
   - These match a reader that sums the first mode over 7–21 ticks.
5. **During runs the body spins and the beating creeps back.** The body spins at −0.037 rad/s from the cilium angle.
   The beating creeps around the wall at +0.024 rad/s, from the ring's stronger link from the clockwise neighbour. So a
   run turns at −0.013 rad/s.
6. **Readability at noon at the probe's starts:**
   - By stage 3a's T2 criterion, 2%.
   - By the first mode in one tick, 3%; over 10 ticks, 7%.
   - Where the per-tick signal is at least 0.13 of the noise, 27%.
7. **Held in place, the fourier1 champion is a switch by the light's level.**
   - It is idle below 0.03, swims without a break from 0.1 to 1, and parks from 2.
   - It swims in tight circles, turning at −0.17 rad/s, whether the light is rising or falling.
   - Its runs show no consistent aim toward the mouth.

### B. An exploratory peek, disclosed
Before writing the probe, I ran scratch code outside the repository on stage 3a's report starts 51–100 (seed 8). It
changed what the cells sense through a monkeypatch, changed single parameters, and tried two candidate controls. These
runs are not results. They shaped stage 3c's draft, so they are in `docs/prereg/stage3c.md` §1.
- **The champion without the direction:** with every node sensing the wall's mean, it fell from 0.361 to 0.189.
- **With the direction mirrored:** 0.141, and no survivor.
- **With the direction ten times stronger:** 0.555. With the sensor noise off: 0.634.
- **The other cells barely changed:** B5 and the fourier1 champion stayed within 0.03 of their score in every case.
- **The candidate controls:** a simple rule that reads the wall before each run moved as the champion did, 0.463 in
  the pool as it is. The same rule running in random directions scored 0.205, the still cell's level.

### C. Reading
1. **How the champion manages, as a hypothesis for stage 3c to test.**
   - It reads the light's direction across its body at the start of each run.
   - A slow loop through the core releases the wall every couple of minutes. The ring's strong links between
     neighbours, with the core's even feedback, let one patch of neighbours win.
   - The patch forms where the light is brightest and pulls the cell that way. Its creep cancels a third of the body's
     spin.
   - In bright light every node is driven and the cell parks.
   - No part has a front: the front forms in the ring each time, and the light decides where.
2. **Stage 3a's T2 understated how readable the direction is.** This is my design error. I built T2 around comparing
   two nodes in one tick. A cell can read all sixteen and add ticks, and many weakly aimed runs add up.
   - A dated correction is in `docs/prereg/stage3.md` §12.
   - So the translucent world does not leave comparing over time as the only way to find the light.
   - Any later world meant to hide the direction must be checked against a reader of the whole wall over several
     seconds.
3. **Why my stage 3b prediction was wrong.** I assumed a uniform cell has no front. It has none in its wiring, but
   its ring makes one.
4. **D11's reading B.1 is in doubt.** It said comparing over time evolved only sometimes and partly.
   - The working uniform champion reads the direction instead.
   - The fourier1 champion's turning does not follow the light's change, and held in place it follows the level.
   - Stage 3c's flat pool tests whether either compares over time. If neither does, a dated correction to D11 follows.
5. **The fourier1 champion's approach is not understood.** It circles tightly and, in the peek, does not use the
   direction across its body. Yet in dim light it drifts toward the mouth at 0.87 R/s. The dish's edge is not how: in
   a scratch recording of 20 starts it spent 6% of its life there, and none of its first parkings were there.
6. **For the owner's hypothesis.** The champion is emergence in a plain sense: a front that no part has, made by the
   parts together. The removals in D11 showed it needs the ring's links, the core, and the slow decay of both. In the
   peek, the simple rule built on the same principle scored above the champion: 0.463 against 0.361. Stage 3c tests
   that.

### D. Decisions this surfaces (the owner's)
Stage 3c's draft, `docs/prereg/stage3c.md` §10: the worlds (the goggles and the flat pool), the controls B6 and B7,
the lesions, and running here.

**Impact:**
- this entry;
- `docs/prereg/stage3.md` §12 (the correction) and `docs/prereg/stage3c.md` (the draft);
- `experiments/stage3c_probe.py` and its tests;
- `docs/data/stage3c/probe/`.

## D14 — Stage 3c: the cell with no front reads the light's direction with its ring; neither stage 3b champion compares over time

**Date:** 2026-11-03  
**Why:** the owner's "agree, go" on stage 3c's draft (D13 D).  
**Ran:**
- Built at `a3539fc`, with three pre-run clarifications in `docs/prereg/stage3c.md`.
- The run took 6.6 minutes here, from a clean tree with warnings as errors.
- The data are at `d4cdb78`; the tables are in `docs/prereg/stage3c.md` §14.

### A. Measured
1. **The champion with what it senses changed** (starts 1–100 at seed 14):

| world | fitness | survival | onset bias toward the mouth |
|---|---|---|---|
| the pool as it is | 0.364 | 43% | +0.657 |
| the direction removed | 0.233 | 14% | +0.006 |
| the direction mirrored | 0.155 | 0% | −0.435 |
| the direction ten times stronger | 0.596 | 88% | +0.810 |
| the sensor noise off | 0.651 | 98% | +0.723 |

2. **The controls behaved as designed.**
   - B6, which reads the wall before each run, moved as the champion did: 0.547, 0.226, 0.156 and 0.703 in those
     worlds.
   - B5 and B7 were unchanged to the last digit.
   - B7, which runs anywhere, scored 0.214, below the still cell's 0.240.
3. **The lesions:**
   - No spin: −0.021, interval through 0.
   - No creep: −0.054, interval below 0.
   - Both: −0.003.
4. **The flat pool:**
   - Only B5 compares over time, with T near 4.8 R/s at every level and step.
   - The champion's T lies between −0.08 and +0.01.
   - The fourier1 champion follows the level. After a rise at light 1 its pull falls from 8.13 to 5.31 R/s in the
     first minute, then settles at 6.77 (T = 0.79, below C5's 1).
5. **The verdicts:**
   - C1, C2 and C3 hold.
   - C4 fails.
   - C5 holds only for B5.
   - 8 of 12 predictions hold.

### B. Reading
1. **How the cell with no front manages: it reads the light's direction across its body.** H's reading is
   confirmed.
   - Without the direction it scores at the still cell's level.
   - With the direction mirrored it flees the light, and none survive.
   - With the direction magnified or its noise off, it comes within 0.06–0.12 of B5.
   - Its front is made by its ring at each run, where the light is brightest (D13).
2. **The course part of H is only partly supported, and C4 fails as preregistered.**
   - The creep does cancel part of the spin: a run turns at −0.013 rad/s against −0.037 without it.
   - Without the creep, the spin's bend costs 0.054.
   - The creep's bend alone costs too little to measure, and straight runs change nothing. The peek's gain for straight
     runs did not replicate.
3. **Neither champion compares over time.** D11's reading B.1 is corrected by a dated note there. In stage 3b's world,
   evolution found two other ways past the reflex:
   - the uniform champion reads the direction with a ring;
   - the fourier1 champion swims in tight circles while the light is dim and stops once it is bright. It has a brief
     transient and uses the direction weakly: magnified, it gains 0.021; mirrored, it loses 0.015.
4. **The translucent world rewards reading the direction too.**
   - B6, the simple rule that reads the wall before each run, scores 0.547 in the pool as it is, 0.164 below B5.
   - With the noise off it scores 0.718. That is above B5 with the noise off (0.675), and about B5's score in the
     pool as it is (0.711).
   - Stage 3a's premise, that the direction cannot be read, was wrong (D13 C2). Stage 3c shows how much a reader gains.
5. **For the owner's hypothesis.** The champion is emergence in the plain sense: a front that no part has, made at
   each run by the parts together. But the simple rule built on the same principle beats it by 0.183. Again the weak
   sense holds and the strong sense does not.
6. **My failed predictions and errors:**
   - Prediction 3: the onset bias with the direction magnified is 0.81, not above 0.85.
   - Prediction 8: running anywhere is worse than sitting still, not level with it.
   - Prediction 9: it failed on my own scoring rule, for a difference of 0.003. The three turning rates were as
     predicted.
   - Prediction 11: I did not expect the fourier1 champion's brief transient.
   - In D13 I called the fourier1 champion direction-blind on the strength of the peek. It uses the direction weakly.

### C. Decisions this surfaces (the owner's)
1. **Whether stage 3c stands as it ran.** Recommended: yes.
2. **Merging `stage3c` to main.** Recommended: yes.
3. **What comes next.**
   - Recommended: return to D11 D2. Design a world where every simple rule leaves real room below the ceiling, and
     probe the baselines' headroom before any evolution. Stage 3c adds B6 to the simple rules such a world must leave
     room for: reading the direction across the body is cheap and strong.
   - The alternative: explain how the fourier1 champion approaches, with a probe like D13's.

**Impact:**
- this entry, and a dated correction in D11;
- `docs/prereg/stage3c.md`: the owner's answers, the pre-run clarifications and §14;
- `protocell/config.py` (the senses), `protocell/sim.py` (the senses, B6 and B7) and `protocell/rng.py`;
- `experiments/stage3c.py`; `tools/replay.py` (`b6`, `b7`, `@K`); `tests/`;
- `docs/data/stage3c/test/`.

## D15 — The owner's decisions on D14: stage 3c stands; merged; next, a world with headroom for every simple rule

**Date:** 2026-11-03  
**Why:** the owner on D14 C: "agree - go for it".

### Decided
1. **Stage 3c stands as it ran.**
2. **`stage3c` is merged to main.**
3. **Next: a world where every simple rule leaves real room below the ceiling** (D11 D2), probed before any evolution.
   - The simple rules now include B6, the rule that reads the wall before each run, besides B2r and B5.
   - The plan's stage 4 names the direction: changing light, moving spots.
   - The design probe comes first, then a preregistration draft with the owner's open points.

**Impact:** this entry; main; next, stage 4's design probe and draft.

## D16 — Stage 4's design probes: changing light alone leaves no room above the simple rules; a tighter economy does

**Date:** 2026-11-03  
**Why:** D15 3, a world where every simple rule leaves real room below the ceiling, probed before any evolution.  
**Ran:**
- The first probe (`experiments/stage4_probe.py`) at `9eb1bde`, from a clean tree with warnings as errors: 28 minutes
  here, data at `222f36b`.
- A design check in scratch code (not a result, disclosed here) between the probes.
- The second probe (`experiments/stage4_economy.py`) at `331d0c2`: 21 minutes here, data at `8845d7b`.
- Both used fresh starts 1–100 at seed 16. Each simple rule had its parameter chosen on starts 1–50 and was reported on
  51–100.
- The ceiling is a still cell put at the brightest point every tick: no cell can get more light, and it pays nothing
  to move.

### A. Measured
1. **Changing light alone leaves little room.** The headroom is the ceiling less the best simple rule, start by start,
   with its 95% interval:

| world (stage 3's translucent pool with one change) | ceiling | best simple rule | headroom |
|---|---|---|---|
| none | 0.736 | B5, 0.716 | +0.020 (0.016, 0.025) |
| clouds, slow (sun 10 min, shade at 0.3 for 5) | 0.730 | B5, 0.700 | +0.030 |
| clouds, fast (2 and 1 min) | 0.730 | B5, 0.664 | +0.065 (0.042, 0.097) |
| the mouth sweeping along the edge through the day | 0.736 | B5, 0.686 | +0.049 |
| a spot circling the pool's centre at 2,500 R: daily, every 6 h, every 2 h | 0.736 | B8 or B6, 0.709–0.719 | +0.017 to +0.027 |

2. **The check between the probes.** B5 spent 68% of its daylight ticks with a full reserve. The ceiling survives every
   start down to 0.40 of the cave's photosynthetic gain, 44% at 0.35 and none at 0.30.
3. **A tighter economy opens room.** For each world, this is the mildest gain probed at which the best simple rule
   leaves about a quarter of the room or more between the still cell (B0) and the ceiling. The ceiling survives every
   start in each:

| world, gain | ceiling | best simple rule (survival) | headroom | share of the room | perfect reading recovers |
|---|---|---|---|---|---|
| the sweep, 0.55 | 0.692 | B5, 0.544 (88%) | +0.148 (0.114, 0.186) | 28% | 78% |
| fast clouds, 0.55 | 0.678 | B8, 0.545 (86%) | +0.134 (0.090, 0.184) | 26% | 84% |
| spot every 2 h, 0.45 | 0.659 | B6, 0.512 (80%) | +0.148 (0.131, 0.165) | 29% | 53% |
| spot every 6 h, 0.45 | 0.659 | B6, 0.535 (84%) | +0.124 (0.092, 0.162) | 24% | 66% |
| the fixed mouth, 0.40 | 0.588 | B5, 0.431 (66%) | +0.157 (0.128, 0.190) | 34% | 46% |

   - At 0.45 the sweep and the clouds leave about half the room, but their best rules survive only 40–50% of starts.
   - "Perfect reading" is B6 with the direction across the body magnified 10,000 times and no sensor noise. The
     column is the share of the headroom it recovers.
4. **Each kind of world has its own best simple rule.**
   - Comparing over time (B5) is best with the mouth, fixed or sweeping.
   - B5's trigger with B6's aim (B8) is best under clouds.
   - Reading the wall (B6) is best with the spot. With the spot circling every 2 hours, comparing over time fails:
     0.166 at 0.45.
5. **Running anywhere (B7) scores below sitting still** in every world and economy.

### B. Reading
1. **The ceiling problem was the economy, not the light.**
   - The reserve stops at full. In the cave's economy a few hours of good light fill it, and light after that is
     wasted.
   - So any rule that reaches good light for part of the day ends the day near the ceiling.
   - This is what D6 and D11 saw in every world: the reflex within 2% of the ceiling in the shaded cave, run and wait
     within 3% in the translucent one.
2. **When light is worth more, every hour counts, and room opens above every simple rule.** It opens most where the
   light moves, and differently in each kind of world.
3. **The room is mostly about information.** Perfect reading of the direction recovers 53–84% of it. A cell could
   claim it by reading the direction better than B6, as uniform 2203's ring does, or by combining reading with
   comparing over time better than B8 does.
4. **For the owner's hypothesis.** This is the first world built where no simple rule known here is near the ceiling.
   The strong sense, interacting parts doing better than every simple mechanism, can now be tested.
5. **A lesson.** I built the first probe's candidates around the light's dynamics, as D11 suggested. Checking first
   whether the reserve saturates would have saved a probe.

### C. Decisions this surfaces (the owner's)
Stage 4a's draft, `docs/prereg/stage4.md` §10:
- the world, with the sweep at 0.55 of the cave's gain recommended;
- the bar;
- the checks' thresholds;
- running here.

**Impact:**
- this entry and the draft;
- `protocell/config.py` and `protocell/world.py` (the circling spot, the clouds, the translucent cell's shading),
  `protocell/sim.py` (the sky, B8), `protocell/rng.py`;
- `experiments/stage4_probe.py` and `experiments/stage4_economy.py`; `tests/`;
- `docs/data/stage4/`.

## D17 — Stage 4a: the world with room above every simple rule passes its checks

**Date:** 2026-11-03  
**Why:** the owner on stage 4a's draft: "agree on all, proceed".  
**Ran:** built at `3f70b42`; the checks here in 26 minutes, from a clean tree with warnings as errors; data at
`0201ab2`. The world is stage 3's translucent pool, with the mouth sweeping along the edge through the day and
photosynthesis at 0.55 of the cave's gain. The starts are fresh: 1–100 at seed 18.

### A. Measured
**Every check passes** (`docs/prereg/stage4.md` §12):
- No still cell survives, and the ceiling survives every start.
- The bar is B8, run toward the light while it rises, at 0.576, surviving 90% of starts.
- The ceiling is 0.694, so the room above the bar is +0.118 (0.099, 0.139), 22% of the room between sitting still and
  the ceiling.
- B6 with perfect reading recovers 73% of that room.
- No random genome comes near the bar: the best of 2,000 scores 0.165, against the still cell's 0.162.
- Determinism holds.
- Five of six predictions hold. The headroom fell just below the range I predicted.

### B. Reading
1. **This is the world stage 4 asked for.** No simple rule known here comes near its ceiling. For the first time in the
   project, a cell that beats every simple rule has room to show it.
2. **On fresh starts the bar is B8,** which combines B5's trigger with B6's aim, ahead of B5 (0.540). In the probe it
   was the other way round. Both rules are close, and both are simple.
3. **The landscape is as deceptive as stage 3b's.** The best random genome is no better than sitting still, so evolution
   from random wiring will likely collapse onto still cells, as stage 3b's first pilot did. It will need a path.
4. **The stage 3b champions fail here:** 0.216 and 0.164. They beat their cilia for much of the day, which this economy
   cannot pay for.

### C. Decisions this surfaces (the owner's)
Stage 4b's draft, `docs/prereg/stage4b.md` §10:
- the path for evolution;
- the generations;
- the criteria;
- the cost on RunPod.

**Impact:** this entry; `docs/prereg/stage4.md` (the owner's answers, §12); `experiments/stage4a.py` and its tests;
`docs/data/stage4a/`; next, stage 4b's draft.

## D18 — Stage 4b's pilot: evolution does not climb in stage 4a's world; the amendment is the owner's

**Date:** 2026-11-03  
**Why:** the owner's "agree, go" on stage 4b's draft, the pilot pod confirmed at most $3.90.  
**Ran:**
- The pilot ran on one RunPod pod at `93c97b2`, 2.1 hours a run, about $2.58. The data are at `293faf9`.
- The outcome and its diagnosis are in `docs/prereg/stage4b.md`, "The pilot's outcome".

### A. Measured
1. **Neither mode climbs.** Both champions validate at the still cell's level and survive no validation start:
   uniform 0.148, fourier1 0.155.
2. **Both runs peaked in their first ten generations,** at 0.43 and 0.55. The world was then still close to the shaded,
   generous cave. Both declined from the moment the world began to tighten, and sat at the still cell's level through
   generations 51–150.
3. **The pull campaign stopped once on a failed status call** while the pod ran on. It was restarted and every run was
   pulled. The campaign now needs three misses in a row (`df75a63`).

### B. Reading
1. **The path failed.** Changing the shading and the economy together left no working cell to carry into stage 4a's
   world. In stage 3b, where only the shading faded, every run first built a working cell and two of six kept one.
2. **Stage 4a's world has no gradient for this search at the still cell's level.** A hundred generations there found
   nothing better. This is what stage 4a's random genomes showed (D17 B3).
3. **Prediction 1 (the pilot climbs in at least one mode) was wrong.** The other predictions wait for a test.

### C. Decisions this surfaces (the owner's)
1. **The amendment.** Each option changes the method, so it is the owner's choice:
   - **A1, one change at a time, slower (recommended).**
     - Generations 1–50: the shading fades in the cave's economy, as stage 3b's amendment A1.
     - Generations 51–100: the gain falls to 0.55 with the cell translucent.
     - Generations 101–200: stage 4a's world, with the champion from generation 101.
     - It keeps the preregistered method, from random wiring, and asks whether two changes at once were the failure.
     - About 2.9 hours a pod. The pilot about $3.20, at most $4.48 with a 4-hour cap.
   - **A2, start from stage 3b's working cells.** The population is seeded with mutants of uniform 2203 and fourier1
     3202, and only the gain eases in. Those cells already read the light without shading; what they lack is thrift.
     It no longer evolves from random wiring. About $2.70 for the pilot.
   - **A3, a stronger search,** CMA-ES or a larger population. It is a new method with its own draft and build.
   - **Stop here** and record that evolution as configured does not climb in this world.
2. **The balance:** $13.94. The chess project's pod is drawing $2.03 an hour from it. A1's pilot fits; its three
   confirmatory pods, at most about $13.40, would need a top-up.

**Impact:** this entry; `docs/prereg/stage4b.md` (the owner's answers, the pilot's outcome); `cloud/campaign.sh`;
`docs/data/stage4b/pilot/`.

## D19 — Stage 4b's amended pilot: still no climb; this search does not reach a working cell in stage 4a's world

**Date:** 2026-11-03  
**Why:** the owner's "go with option 1" (amendment A1, one change at a time).  
**Ran:**
- One RunPod pod at `91e2c5b`, 2.85 hours a run, about $3.36. The first launch found no instance; the retry got one.
- The data are at `c203bf8`. The outcome is in `docs/prereg/stage4b.md` §13.

### A. Measured
1. **Neither mode meets the pilot's rule.** Uniform validates at 0.155 and survives none of the validation starts.
   Fourier1 validates at 0.241 and survives a quarter.
2. **Both runs built working cells while the shading faded,** peaking at 0.65 and 0.56. They then lost most of it: as
   the shading went, and more as the gain fell.
3. **In stage 4a's world, uniform sat at the still cell's level.** Fourier1 climbed slowly to 0.241 by generation 160,
   then stopped.

### B. Reading
1. **One change at a time did not save the path.** The cells this search builds find the light, but they spend too much
   to live in stage 4a's economy. Over 50 generations of the economy tightening, it did not make them thrifty.
2. **Across the project, this search has never matched the best simple rule in any world:**
   - stage 1, 0.011 below the reflex;
   - stage 3b, 0.23 below B5;
   - here, 0.33 below B8.

   The world now leaves room. The search is what is missing.
3. **What the owner's hypothesis needs next is a cell that beats B8,** found by some means. Without one, the strong sense
   stays untested: this neither shows it false nor shows it true.

### C. Decisions this surfaces (the owner's)
1. **A stronger search (recommended).** CMA-ES, deferred in D6, adapts its steps to the landscape, where this search
   mutates every gene by the same small step. It needs its own draft and build, here first, then on RunPod with costs
   confirmed. The test, the criteria and stage 4a's world stay.
2. **Seed from stage 3b's working cells** and ease only the gain in. This is cheap, about $3, but A1's middle part
   suggests the same search will not make them thrifty either.
3. **Run the fourier1 line on** from its checkpoint, at about $3.20 for 200 more generations. Its champion stopped
   improving after generation 160.
4. **Stop stage 4b here** and record the result as it stands.

The balance is $52.56; it has been topped up.

**Impact:** this entry; `docs/prereg/stage4b.md` §13; `experiments/stage4b.py`, `tests/test_stage4b.py`;
`docs/data/stage4b/`.

## D20 — Stage 4c's pilot: CMA-ES does no better; neither search makes a working cell thrifty

**Date:** 2026-11-05  
**Why:** the owner's "happy with all" on stage 4c's draft with revision R1, and "go with 1" for the cpu3c pod.  
**Ran:**
- One RunPod pod (cpu3c, AMD EPYC 9965, 32 vCPUs, $0.96 an hour) at `e53a4f6`, 3.8 hours a run. It cost about $3.90,
  within the $5.76 cap.
- It launched at 20:26 UTC on the third night try, so the fallback to this machine was not used. The campaign pulled
  every run and the pod deleted itself.
- The data are at `4b5b4d8`. The outcome is in `docs/prereg/stage4c.md`, "The pilot's outcome".

### A. Measured
1. **Neither mode meets the pilot's rule.**
   - Uniform validates at 0.149 and fourier1 at 0.160.
   - Neither survives any of the 24 validation starts.
   - Both are below the GA's amended pilot (0.155 and 0.241), so prediction 2 fails. Prediction 3 holds.
2. **The fourier1 run built working cells while shaded,** peaking at 0.565, and lost most of them as the shading went and
   the gain fell, as the GA's runs did.
3. **The uniform run built little while shaded** (peak 0.494, mean 0.266, against the GA's 0.533). The second check's
   uniform run, on another seed, climbed to 0.575 over generations 16–25, so the seed matters and one run cannot say
   how much.
4. **While the gain fell, the uniform population went still and stayed still.**
   - The median equalled the best.
   - The step size grew to about 0.3 on that plateau.
   - Its champion barely beats (mean beat 0.001).
5. **Validation never moved in either run:** between 0.135 and 0.160 at all 20 validations.

### B. Reading
1. **A stronger search did not help.** Six pilot runs, two per pilot, now share one shape:
   - stage 4b's pilot and its amended pilot, with the GA;
   - this pilot, with CMA-ES.

   Every run builds or half-builds a working cell where the world is generous. It loses that cell as the economy
   tightens, and ends at or near the still cell's level in stage 4a's world. The one exception is the GA's fourier1
   amended run, at 0.241.
2. **The obstacle is the step from a working cell to a thrifty one.** The cells both searches build find the light but
   beat too much for stage 4a's economy. As the economy tightens, a cell that does less ranks better, so selection runs
   toward stillness. Neither search crossed from spending to thrift.
3. **A flat landscape defeats CMA-ES's adaptation.** On the uniform plateau, with each ranking resting on 8 noisy
   training starts, its step size widened instead of narrowing. It ended sampling near-random genomes, as in the first
   local check.
4. **Q1 stays unanswered.** There is still no cell to test against B8, so the strong sense is neither shown nor refuted.
   The weak sense stands from stages 1b and 3b (D9, D11).

### C. Decisions this surfaces (the owner's)
1. **A probe of thrift first (recommended).** It asks why the working cells fail before buying another search.
   - **The cells:** stage 3b's two working champions (uniform 2203, fourier1 3202).
   - **The worlds:** the translucent world, at gain 1.0, 0.8, 0.65 and 0.55 of the cave's, the last being stage 4a's world.
   - **Measured** beside B5 and B8 on the same starts:
     - where they die;
     - how much of the day they beat;
     - the light earned per unit of effort.
   - **What it shows:** whether they fail by spending (a small change, within a search's reach) or by finding too little
     (a different behaviour).
   - **Cost:** about an hour on this machine, nothing on RunPod. It needs a small probe script, with its own tests.
2. **Seed from working cells.**
   - **The run:** CMA-ES with its first mean at a stage 3b champion and a small first step, in the translucent world
     while only the gain falls (50 generations), then 100 generations in stage 4a's world.
   - **What it asks:** the narrow question every pilot has stalled on.
   - **The trade-off:** it no longer evolves from random wiring, so a cell it finds would answer Q1 only for staged
     evolution.
   - **Cost:** one pod, about 3 hours, about $3, at most about $4.50. It needs a small build: a run that starts from
     given genomes.
3. **Run the GA's fourier1 line on** from its checkpoint (D19 C3).
   - It is the only evolved cell above the still cell in this world.
   - Its champion stopped improving after generation 160.
   - About $3.20.
4. **Stop stage 4 here and record:** two searches and three paths do not reach a working cell in stage 4a's world from
   random wiring.

The balance is $18.22. A pod not of this project (`lattice-lab-census-4d`) is drawing $0.96 an hour from it, and was
left alone.

**Impact:** this entry; `docs/prereg/stage4c.md` ("The pilot's outcome"); `docs/data/stage4c/pilot/`.

## D21 — The owner's decision on D20: the thrift probe first; its plan and predictions, before it runs

**Date:** 2026-11-05  
**Why:** the owner on D20 C: "Agree, go", the recommended option 1.

### Decided
1. **The thrift probe runs here,** before any further search. It asks why the working cells die in stage 4a's world:
   by spending, beating more than the light they find repays, or by finding too little light.
2. **Nothing on RunPod.**

### The probe (`experiments/stage4_thrift.py`), written before it runs
- **The cells:**
  - stage 3b's two working champions, uniform 2203 and fourier1 3202, as they are;
  - beside them B0, B5 (τ 3 s) and B8 (τ 10 s), stage 4a's choices.
- **The worlds:** stage 3's translucent pool, with the mouth fixed and sweeping, at 1, 0.8, 0.65 and 0.55 of the cave's
  photosynthetic gain.
  - The fixed mouth at 1 is the champions' home, the world stage 3b tested them in.
  - The sweeping mouth at 0.8 and 0.65 is the gain's fall along stage 4b's path.
  - The sweeping mouth at 0.55 is stage 4a's world.
- **Free beating, the probe's lever.** Each cell runs twice in each world: as the world is, and with beating free
  (c1 = 0).
  - No cell senses its reserve, so free beating leaves every move the same while the cell lives (tested); only what
    beating costs is gone.
  - A cell that still starves with beating free found too little light.
- **Starts:** fresh starts 1–100 at seed 23, the same in every world, with shared noise.
- **Measured per start,** over the ticks the cell lived:
  - the light it soaked per daylight tick;
  - its beat by day and by night;
  - survival and fitness;
  - when it died, and whether by night.
- **Context:** the light a still cell must soak on average over the daylight to pay a day's resting cost. It is 0.33 at
  the cave's gain and 0.61 at 0.55.

### The verdict, per champion in stage 4a's world
| survival with beating free | the verdict | what it would mean |
|---|---|---|
| at least 80% | **spending** | it finds enough light; thrift is the missing part, a change a search might make |
| below 50% | **finding** | even beating for nothing it starves; it needs to find more light, a different behaviour |
| between | **both** | |

### Predictions (written before the run)
1. **At home, each champion survives within 15 points of stage 3b's test:** U2203 50%, F3202 63%.
2. **In stage 4a's world, with beating free, both champions survive fewer than half the starts.** Both verdicts are
   "finding". In stage 4a's checks they beat 2.7 and 3.7 times as much as B8, but soaked about a third of its light.
3. **In stage 4a's world each champion soaks less than half B8's light per daylight tick lived.**
4. **For each champion, the gain's fall to 0.55 costs more survival than the sweep does at the cave's gain.**

**Cost:** about 10 minutes here with 16 workers, from a clean tree with warnings as errors.

**Impact:** this entry; `experiments/stage4_thrift.py`, `tests/test_stage4_thrift.py`; next, `docs/data/stage4/thrift/`
and the probe's outcome.

## D22 — The thrift probe: the working cells die by finding too little light, not mainly by spending

**Date:** 2026-11-05  
**Why:** D21, the owner's choice of the thrift probe.  
**Ran:**
- `experiments/stage4_thrift.py` at `b085920`, from a clean tree with warnings as errors. It took 9 minutes here with
  16 workers.
- The data are at `2d97f91`, in `docs/data/stage4/thrift/`.

### A. Measured
Survival is shown as paid / free: with beating at the world's cost, and with beating free. The light is P(I) soaked
per daylight tick lived; the beat is the mean by day.

| world | cell | survival, paid / free | light per daylight tick | beat by day |
|---|---|---|---|---|
| home: the mouth fixed, the cave's gain (a still cell breaks even at 0.33) | B8 | 100% / 100% | 0.750 | 0.138 |
| | B5 | 91% / 93% | 0.649 | 0.097 |
| | U2203 | 50% / 54% | 0.345 | 0.348 |
| | F3202 | 64% / 80% | 0.434 | 0.657 |
| stage 4a's: the mouth sweeping, 0.55 of the gain (break-even 0.61) | B8 | 90% / 93% | 0.596 | 0.099 |
| | B5 | 79% / 84% | 0.537 | 0.073 |
| | U2203 | 12% / 43% | 0.314 | 0.271 |
| | F3202 | 0% / 19% | 0.287 | 0.538 |

1. **The verdict is "finding" for both champions.** With beating free, in stage 4a's world, U2203 survives 43% of the
   starts and F3202 19%, both below D21's 50%.
2. **The champions find about half of B8's light in every world:** between 0.40 and 0.58 of it per daylight tick
   lived, across all eight worlds. Their light hardly changes with the gain, since no cell senses its reserve.
3. **Spending is a real but smaller part.**
   - Beating free adds 31 points of survival to U2203 and 19 to F3202 in stage 4a's world, but leaves both below half.
   - By day they beat 2.7 and 5.4 times as much as B8, for half its light.
   - U2203 also beats at night, 0.10, when there is nothing to find.
4. **The gain's fall kills them, not the sweep.**
   - At the cave's gain, the sweep costs U2203 2 points of survival and F3202 24.
   - The fall to 0.55 with the mouth fixed costs them 42 and 63.
5. **The predictions:**

| prediction | outcome |
|---|---|
| 1. at home within 15 points of stage 3b's test | ✓: 50% and 64% |
| 2. with beating free, both below half in stage 4a's world | ✓: 43% and 19% |
| 3. less than half of B8's light in stage 4a's world | ✗ narrowly: U2203 0.53 of B8's, F3202 0.48 |
| 4. the gain's fall costs more than the sweep | ✓ |

### B. Reading
1. **The working cells fail mainly by finding too little.** Thrift alone would not save them: with beating free, most
   still starve. To live in stage 4a's world a cell must find light nearly as well as B8; stage 3b's champions find
   about half as much, even at home.
2. **This is why every pilot had the same shape (D20 B1).** A still cell breaks even at 0.33 at the cave's gain, and
   at 0.61 at 0.55. A cell finding half of B8's light lives on about half the starts in the generous world and dies as
   the gain falls.
   - Even at home, where half of them died, the champions' search did not find a better finder.
   - No search here has made a cell that finds more than about half of B8's light, in any world.
3. **Seeding from these cells (D20 C2) would need the search to double their light while the economy tightens.** That
   is the step every pilot failed, so it is unlikely to work.
4. **The open question is whether this cell can find light as well as B8 at all.** Either the cell is the limit, or the
   searches are. Nothing so far tells them apart.

### C. Decisions this surfaces (the owner's)
1. **A representation check: teach a cell B8's behaviour directly (recommended).**
   - **How:** fit a cell's genome so that its beats match B8's on B8's recorded senses, with CMA-ES on that match rather
     than on survival. Then run the cell in stage 4a's world beside B8.
   - **If it matches B8:** the cell can carry a good finder and the searches are what fail. Evolution can then start
     from it, and the strong sense gets a fair test: can the interacting parts improve on the best simple rule?
   - **If it cannot:** the cell's design is the limit, and that is the next thing to change.
   - **The trade-off:** a cell started from B8 no longer evolves from random wiring.
   - **The risk:** a match on recorded senses may drift once the cell's own moves change what it senses. The closed
     run in the world is the judge.
   - **Cost:** a short draft and a build, then a check here. Any RunPod pilot after it would be costed first.
2. **Seed from the champions** (D20 C2): about $3, now expected to fail.
3. **Stop stage 4 here and record** what it shows: the world has room, and the evolved cells find about half the light
   it takes to use it.

**Impact:** this entry; `docs/data/stage4/thrift/`.

## D23 — Stage 4d: this fit did not put B8 in the cell; whether the cell can hold it stays open

**Date:** 2026-11-05  
**Why:** the owner's "Agree with 1, proceed" on D22, then "go with the runpod" and "Ok switch to the new Pod now".  
**Ran:**
- **The first run, here** at `758c8e5`, 12 workers per mode: it crashed the host at 11:59 UTC, 26 minutes in, and left
  nothing (see A1).
- **Two RunPod pods:** `e4df26b` on an EPYC 7713, then `8688994` on an EPYC 7702P resuming from the first's checkpoints.
  About $2.82 in all. The fit's code is the same in both.
- The data are at `af5a563`. The plan, every note on the run and the outcome are in `docs/prereg/stage4d.md`.

### A. Measured
1. **This work crashed the host.** The two runs tripped the CPU's thermal limit.
   - In 23 logged boots, the reset register's thermal bit is set only after this crash and after the freeze of 10-27. It
     is not set after the freeze of 10-23.
   - The CPU holds 98°C under sustained load whatever the number of workers (4 and 8 in all were tried), as October's traces
     show too. Fewer workers do not cool it. So the standing limit of 24 workers is not safe on this machine.
   - The run moved to RunPod. Fits now checkpoint and resume, and a stopped and resumed fit is the same bits (tested).
2. **The verdict is "does not" in both modes.** The judged cells close -0.003 and -0.022 of the gap from B0 to B8.
   They score 0.142 and 0.135 against B8's 0.555, and survive no start.
3. **The match stalled at about 0.31 in both modes,** with the step size collapsed long before generation 8,000.
4. **No candidate survived a single start in any of the 128 validations.** The fit's rule judged early, nearly idle cells,
   since nothing beat them in the world.
5. **In the uniform mode a closer copy did worse in the world** (correlation -0.91 over the validations): 0.145 at a match
   of 0.16, 0.109 at 0.31. Fourier1 shows no such link (-0.11).
6. **Held-out and training matches agree** (0.150 and 0.158, 0.171 and 0.173), so this is not overfitting.
7. **Predictions 1, 2 and 4 fail; 3 holds.** I expected at least half the gap in the fourier1 mode. It closed none.

### B. Reading
1. **This does not answer D22's question.** Under `stage4d.md` §5, a low match means the fit failed before the world had
   a say. Stage 4d shows that CMA-ES on the beats could not put B8 in the cell. It does not show that the cell cannot
   hold B8.
2. **Copying a third of B8 is no use.** Running at the wrong moments costs energy and finds nothing, which fits D22: this
   world pays only for finding light nearly as well as B8.
3. **One explanation worth testing, not yet tested: the cell cannot read light relative to its level.**
   - B8 compares the light with its own recent average, and takes a direction from a ratio. Both work at any brightness.
   - The cell takes in its gain times the light, through sigmoids that saturate, with no gain control. The light runs over
     three orders of magnitude here (0.01 to 10), and the changes B8 acts on are about 2% a tick.
   - It would also account for the evolved cells' half measure of the light. That is a hypothesis, not a finding.

### C. Decisions this surfaces (the owner's)
1. **A stronger fit: gradient descent through the network (recommended).** The same record, the same cell and the same
   judge, with the fit changed.
   - **Why:** matching a known signal is what gradients do well, and CMA-ES has no gradient. It is the direct test D22 asked
     for: if the cell can hold B8, this should show it.
   - **If the match climbs and the gap closes:** the cell can hold B8 and the searches are what fail. Evolution can then
     start from that cell, as D22 C1 planned.
   - **If it stalls too:** the cell is the likely limit, and option 2 follows.
   - **Cost:** a short draft and a build, then one process on one core here, or a small pod if it needs more.
2. **Give the cell relative sensing,** a compressed or adapting input, then refit. It tests B3 directly and it is what
   real cells do, but it changes the organism, so it needs its own draft and new checks.
3. **Stop stage 4 here and record** what it shows: the world has room, and neither evolution nor fitting has put a good
   finder in this cell.

**Impact:** this entry; `docs/prereg/stage4d.md`; `experiments/stage4d.py`, `tests/test_stage4d.py`; `cloud/launch_phase.sh`
(`RESUME=1`); `docs/data/stage4d/fit/`.

