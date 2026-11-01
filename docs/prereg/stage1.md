# Preregistration draft: stage 1 — light seeking, evolved

**Written:** 2026-11-01, before any of it is built (`docs/decisions.md` D5, D6). The owner decided in D5 that the
cave pool is stage 1's world, that stage 1 evolves in its day configuration against B2r, that it compares both spoke
modes, and that the bar is fitness. This draft adds one finding made while writing it (§1), which changes what stage 1
can show. Every number below has its reason; the open points for the owner are in §13. Nothing is built until the
owner agrees the draft.

## 1. The question, and what the cave allows

The plan's question for stage 1 is: does an evolved cell beat the reflex cell, including on layouts it never saw?

**In the cave, the reflex is close to the best any cell can do.** A still cell placed at the best fixed point pays
nothing to travel and nothing to beat. So on the same starts it bounds what any cell can score that must first get
there. On starts 51–100 of the checks (`docs/data/stage1/budget/headroom.csv`, read from D4's tables):

| configuration | the bar | the bar's fitness | a still cell at the best point | headroom |
|---|---|---|---|---|
| day | B2r, k = 100 | 0.698 | 0.712 | **0.014** (sd 0.008 across starts; 0.010 on day starts, 0.017 on night starts) |
| burn | B2rr, k = 100 | 0.688 | 0.707 | 0.020 |
| sweep | B2rr, k = 100 | 0.685 | 0.548: no fixed point keeps up with the moving sun | about 0.02 to burn's 0.707 |

The reason is that everything a cell needs is sensed in the moment. Its own shading gives the light's direction at
any distance, darkness says rest, and nothing is hidden that memory could recover. The reflex loses most where
nobody can see which way to go: night starts far from the mouth, where the light is too faint to steer by until well
after dawn. A network can beat the reflex here only by the last 2% of fitness: travelling to the mouth a little sooner
or a little more cheaply. The plan's stage 3 is where a reflex is expected to fail, when direction can no longer be
read across the body and must be compared over time.

So stage 1 asks three things, the first two primary (open point 1):
- **Q1, does evolution reach the reflex?** In each spoke mode, does an evolved cell score within δ of B2r on starts it
  never saw?
- **Q2, which parts does the evolved cell use?** The removals of the plan (§7), each on each evolved cell.
- **Q3, does an evolved cell beat the reflex?** Reported with the same statistics; predicted not to (§11).

## 2. The world, the cell, the bar

- **The world:** the cave's day configuration exactly as checked in D4 (`docs/prereg/cave.md`, `protocell.config.CAVE`
  with the cycle on, damage off and the sweep off): starts with a random phase and the matched reserve, lifetimes to
  the second sunrise, the noise on its named streams.
- **The cell:** as `cave.md` §4, in both spoke modes (103 or 135 numbers; τ from 1 s to an hour).
- **The bar:** B2r at k = 100, the gain the checks chose. It is scored again on stage 1's own test starts (§6),
  beside the still cell at the best fixed point as the ceiling's reference.

## 3. Fitness

The bar's measure (D5): a lifetime's mean reserve, dead time counting 0. Survival, light soaked, effort per unit
light, beating at night and the time to reach the soak region are reported beside it.

## 4. Evolution

A generational genetic algorithm with elitism and truncation selection, mutation only. Each number has its rule:

- **Population: 96 genomes.** Two jobs of 48 genomes on each of the 8 training starts fill the 16 workers (§10).
- **Training starts: 8 a generation, drawn fresh each generation** from stream `train`, keyed by the run and the
  generation, by the cave's start rule (phase, heading, position). Fresh starts each generation mean no genome can
  fit a fixed set; 8 is what fills the workers.
- **Shared luck:** on a start, every genome draws the same sensor and motion noise (noise key (0, start number), the
  start numbers unique within a run). Genomes are ranked on the same luck, so the ranking's noise is their
  difference's, not their sum's.
- **A genome's fitness in a generation:** its mean fitness over the 8 starts.
- **Selection:** the 4 best are kept unchanged (and scored again next generation, on its new starts, so luck does not
  keep them). The other 92 are children of parents drawn uniformly from the best 24 (the top quarter).
- **Mutation:** every number moves by a normal step with sd σ × (its range's width), **σ = 0.02**. A step past a
  bound is reflected back inside, and α wraps around the circle. Each number moves by about 2% of its range a
  generation, small enough that a good parent's child is usually close to it. The pilot can amend σ (§5).
- **No crossover.** The genome's blocks are not interchangeable between cells, and a part is added only when a test
  needs it (plan, lesson 1).
- **The first generation:** uniform over the ranges, from stream `evolution` keyed by the run (the cave's random
  genomes were drawn the same way, and in the day configuration 0.6–1.1% of them survived).
- **Generations: 100**, set by the budget (§10).
- **The champion:** at generations 10, 20, …, 100 the three best by training fitness are scored on 24 fixed
  validation starts (stream `starts` at seed 4). The run's champion is the best on validation across the run, so a
  lucky training score is not enough, and the test starts stay unseen until §6.

## 5. Runs and seeds

- **The pilot:** one run per spoke mode, run seeds 1001 (uniform) and 1002 (fourier1). It checks that evolution climbs
  and that the settings of §4 are sound before any confirmatory run. Its outcome is recorded in §15 before the
  confirmatory runs. An amendment to σ, the population or the generations is allowed after it, with its reason.
- **The confirmatory runs:** three per spoke mode, run seeds 2001–2003 (uniform) and 3001–3003 (fourier1).
- **Validation starts:** seed 4. **Test starts:** seed 5. **Bootstrap:** stream `bootstrap`, seed 6. None of these
  seeds has been used before. The cave's checks used seed 2 and the probes seed 1.

## 6. The test

On 100 test starts, each confirmatory champion, B2r and the still cell at the best fixed point run with the same
noise on each start (key (0, start)). For each champion, the per-start difference in fitness against B2r is averaged,
with a 95% bootstrap interval over the starts (10,000 resamples).

## 7. The removals (the plan's, on each confirmatory champion)

Each is applied to the champion as it is, without re-evolving, on the test starts, and compared start by start with
the intact champion:

| removal | what is set to zero |
|---|---|
| R0, blind (a control) | the sensory gain g: no light reaches the network |
| R1, the ring's links cut | the weights between ring neighbours, both directions (the self weights kept) |
| R2, the loop opened | the two weights between nodes 15 and 0: the ring becomes a chain |
| R3, the core removed | every spoke, both directions: the wall alone |
| R4, the core's recurrence removed | every core-to-core weight, self links included |

## 8. A light it never saw (reported, not judged)

The champions and B2r on the test starts in a swept day: the sun's sweep on, damage off. This configuration was
not among the four K1–K7 checked, so it is described, not judged.

## 9. The criteria

- **δ = 0.007**, half the day's headroom: a cell within half the gap between the bar and the ceiling has reached the
  bar.
- **Q1:** a champion reaches the bar if its interval's lower bound against B2r is above −δ. A spoke mode reaches it if
  at least 2 of its 3 champions do.
- **Q3:** a champion beats the bar if its interval's lower bound is above 0. A mode beats it if at least 2 of 3 do.
- **Q2:** a removal breaks a champion if the interval of its fitness drop has its lower bound above δ. A part is needed
  in a mode if removing it breaks at least 2 of the mode's 3 champions.
- **The modes compared:** described, champion by champion. Three against three supports no test.

## 10. Compute

From `docs/data/stage1/budget/cost.csv` (this machine): a batch of 48 network cells costs 192 µs a tick. A
generation is 16 jobs (8 starts × 2 halves of 48 genomes), each one start's lifetime: 24–48 h, 86,400–172,800 ticks,
so 17–33 s. All 16 run at once, so a generation takes about 35 s with validation. **A run of 100 generations takes
about an hour on 16 workers.** The pilot is 2 runs, about 2 h. The confirmatory runs are 6, about 6 h. The test and
the removals take about 15 min. Runs go one at a time, with sleep inhibited and the logs under the home directory.
The simulation's fixed cost of about 120 µs a tick could be lowered in the build, guarded by the bit-for-bit tests, which would shorten every run.

## 11. Predictions (written before the build)

1. **Evolution climbs.** Each pilot champion survives most validation starts by generation 100.
2. **Q1:** both spoke modes reach the bar.
3. **Q3:** neither mode beats it. The headroom is 0.014, and most of it is spent waiting for light that cannot be
   steered by.
4. **Q2:**
   - R0 breaks every champion.
   - R1, R2 and R4 break none: the task needs no memory and no pattern along the ring.
   - R3 breaks the fourier1 champions, whose steering runs through the spokes' front, but not the uniform ones, whose
     steering must be local because their core sees only the total light.
5. **Effort per unit light:** the champions' is below B2r's (0.58). Unlike the reflex, they need not keep beating
   against the pool's edge at the mouth.
6. **The modes:** the uniform champions are at least as fit as the fourier1 champions. The best random genome in the
   cave's checks was uniform.
7. **The swept day:** the champions and B2r each lose less than 0.02 against their day fitness.

## 12. Decision table

| result | what follows |
|---|---|
| the pilot does not climb (its champion survives fewer than half the validation starts) | an amendment to σ, the population or the generations, with its reason; the pilot again on fresh seeds |
| both modes reach the bar | stage 2's preregistration (burn, then sweep), with the removals' reading |
| a mode does not reach the bar | recorded; the owner's call whether that mode runs longer or larger before stage 2 |
| a mode beats the bar | recorded; its removals read for what it uses beyond a reflex |

## 13. Open for the owner

1. **The question.** Q1 (reaches the bar) and Q2 (the removals) primary, and Q3 (beats the bar) reported. Or Q3
   primary, as the plan worded it, knowing the headroom is 0.014. Recommended: Q1 and Q2 primary.
2. **The budget.** Eight runs, about 8 h on this machine, run one at a time. Two cheaper options: two confirmatory
   runs per mode (6 runs, about 6 h), or RunPod, with its cost confirmed before any launch. Recommended: as drafted,
   over two or three sittings.
3. **The optimiser.** The simple genetic algorithm drafted here, or CMA-ES. CMA-ES is usually more sample-efficient
   for about 100 continuous numbers, but it is a larger part to build and check. Recommended: the genetic algorithm,
   with CMA-ES kept for when a run is too slow.
4. **The swept day (§8):** kept as a description, or dropped. Recommended: kept. It is cheap, and it is the plan's
   "layouts it never saw" in the only form the cave has.

**The owner's answers (2026-11-01, before the build).**

The owner answered: "1. the first 2. runpod 3. agree 4. agree".

1. Q1 (reaches the bar) and Q2 (the removals) are primary, and Q3 (beats the bar) is reported.
2. The runs go on RunPod, with the owner confirming the cost of every launch before it.
3. The optimiser is the genetic algorithm of §4.
4. The swept day (§8) is kept as a description.

Running on RunPod has one consequence. Evolution runs on RunPod CPU pods, so its numbers are that platform's bits
(`docs/determinism.md`), and every run's manifest records the platform. The champions' genomes come back to this
machine. The test, the removals and the swept day (§6–§8) run here, B2r and the still cell included, so every
comparison of stage 1 is made on one platform.

## 14. What would be built

- `protocell/evolve.py`: the genetic algorithm, its streams, and the run's checkpoints and champion.
- `experiments/stage1.py`: the pilot, the confirmatory runs, and the test with its removals, all writing tables and
  manifests.
- The removals, as options on the network controller.
- Starts keyed by run and generation.
- Tests for each piece, including that a run resumes from a checkpoint bit for bit, and that the removals zero exactly
  the weights of §7.
- Possibly the speed-up of §10.

## 15. What would change this document

The owner's answers to §13, as dated notes before the build. After the build and before the pilot, clarifications as
dated notes. After the pilot, its outcome and any amendment as dated notes, before the confirmatory runs. After
those, nothing.
