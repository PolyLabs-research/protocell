# Preregistration draft: stage 4c — the same question, a stronger search

**Written:** 2026-11-03, after stage 4b's two pilots (`docs/decisions.md` D18, D19), before any run. The owner chose a
stronger search: "Let's try 1 as you suggest".

## 1. The question

Stage 4b's question stands unchanged (`docs/prereg/stage4b.md` §1).
- **Q1:** does evolution find a cell that beats every simple rule in stage 4a's world?
- **Q2:** which of its parts does it need?
- **Q3:** how does it manage?

Stage 4b's genetic algorithm did not reach a working cell there, in either of its pilots. Across the project it has
never matched the best simple rule in any world (D19). Stage 4c asks the same question with CMA-ES, a search that
learns its own step sizes and directions.

## 2. What stays as stage 4b had it

- **The world:** stage 4a's (`docs/prereg/stage4.md` §2). It is stage 3's translucent pool, with the mouth sweeping
  through the day and photosynthesis at 0.55 of the cave's gain.
- **The cell,** in both spoke modes.
- **The bar:** B8 (τ = 10 s), 0.576 in stage 4a's checks.
- **The path:** amendment A1's, one change at a time (`docs/prereg/stage4b.md` §13).
  - Generations 1–50: the shading fades in the cave's economy.
  - Generations 51–100: the gain falls with the cell translucent.
  - Generations 101–200: stage 4a's world.
  - The champion is chosen from generation 101.
  - Keeping it means the search is the only thing that differs from stage 4b's amended pilot.
- **Evaluation:**
  - 8 fresh training starts a generation, with shared noise.
  - Validation every 10 generations on 24 starts at seed 20, in stage 4a's world.
  - The champion is the best on validation.
- **The pilot's rule** (stage 4b §5): the champion survives at least half of the validation starts.
- **The test, the criteria and the decision table** (stage 4b §6, §7, §9): on 100 starts at seed 21, bootstrap at
  seed 22.

## 3. The search: CMA-ES

The covariance matrix adaptation evolution strategy, as Hansen's tutorial (2016) sets it out, with its default
constants. It keeps a normal distribution over genomes: a mean, a step size and a covariance.
- **Each generation:**
  - It samples 96 genomes, the GA's population, so a generation costs the same.
  - It ranks them on the training starts and moves the mean toward the best 48, weighted by rank.
  - It adapts the step size from how consistently the mean has been moving, and the covariance from the steps that
    worked.
- **How it differs from the GA,** which mutates every gene by a fixed 2% of its range:
  - The step size is learnt.
  - The directions of search are learnt.
  - The best half is averaged rather than copied, which also smooths over the training starts' noise.
- **Genes:**
  - Each gene lives in normalised coordinates, 0 to 1 across its range.
  - The distribution is unbounded. A genome is read from a sample by mirroring each coordinate back into [0, 1]; the
    cilium angle wraps around its circle instead. So the updates never see a repaired point.
- **The start:** the mean is drawn uniformly over the ranges, from stream `cmaes` keyed by the run. The first step is
  0.3 of each range, about the spread of the GA's uniform first population (0.29).
- **Randomness:** each generation's samples come from stream `cmaes` keyed by the generation.
- **Checkpoints:** a run checkpoints after every generation and resumes bit for bit.
- **Validation:** every 10 generations, the best three samples and the distribution's mean.
- **200 generations.**

## 4. Runs and seeds

- **Run seeds, fresh:**
  - Pilot: one run per mode, 1501 (uniform) and 1502 (fourier1).
  - Confirmatory: 2501–2503 and 3501–3503.
- **Validation, test and bootstrap:** stage 4b's seeds 20, 21 and 22, so the champions meet the same starts.

## 5. The local check, before the pilot

The owner asked that the search be tested here first. Before the pilot, one run per mode goes on this machine for the
first 25 generations of the path, with seeds 1599 (uniform) and 1598 (fourier1). It is a check, not a result.
- **It shows** that the search runs at full size and how fast it climbs.
- **It is compared** with the GA's amended pilot over the same generations.
- **Its data and manifest are kept** in `docs/data/stage4c/check/`.

## 6. Predictions (written before any run)

1. **In the local check, CMA-ES climbs faster than the GA:** its mean best training fitness over generations 1–25 is
   above the GA's amended pilot's in both modes.
2. **In the pilot, CMA-ES's champions validate above the GA's amended pilot in both modes,** above 0.155 (uniform) and
   0.241 (fourier1).
3. **The pilot's rule is met in at most one mode.**
4. **If the confirmatory runs and the test happen, no champion beats B8.**

## 7. Decision table

| result | what follows |
|---|---|
| the local check fails to run, or does not climb at all | the search is fixed or the draft revised, before any pilot |
| the pilot meets its rule in a mode | the confirmatory runs, with the owner's cost confirmed |
| the pilot meets it in neither mode | recorded; the owner's call, as stage 4b's decision table |
| the test: Q1 holds in a mode | the strong sense shown in this world (stage 4b §9) |
| the test: Q1 fails | recorded; the owner's call |

## 8. Compute

- **The local check:** about 30 minutes here, the two runs side by side with 12 workers each.
- **The pilot:** one RunPod pod (cpu5c, 32 vCPUs, $1.12 an hour) for the two runs side by side, about 2.9 hours.
  About $3.30, at most $4.48 with a 4-hour cap.
- **The confirmatory runs:** three such pods, about $10, at most $13.44.

## 9. What would be built

- **`protocell/cmaes.py`:** the strategy, and a run as `protocell/evolve.py` runs the GA, reusing its evaluation,
  validation and champion choice.
- **`experiments/stage4c.py`:** stage 4b's runner with CMA-ES. Its test is stage 4b's, pointed at
  `docs/data/stage4c/`, with this draft's predictions.
- **Tests:**
  - the strategy on functions with known optima;
  - its reading of genomes and its bounds;
  - resuming bit for bit;
  - a quick pilot and test end to end.

## 10. Open for the owner

1. **The search as §3 sets it** (recommended): λ = 96 as the GA, standard constants, the first step 0.3, the mean's
   start drawn at random.
2. **Keeping amendment A1's path,** so the search is the only change (recommended).
3. **The local check first** (§5), then the pilot on RunPod at the cost in §8.

## 11. What would change this document

The owner's answers, and the local check's outcome, as dated notes before the pilot. The pilot's outcome and any
amendment, as dated notes before the confirmatory runs. After those, nothing.
