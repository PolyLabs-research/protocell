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

**After the checks (2026-11-04):** item 1 now reads with revision R1's first step, 0.05 of each range; the rest of
§3 stands.

**The owner's answers (2026-11-04, before the pilot).** "happy with all":
- the search as revised by R1;
- stage 4b's amended path kept;
- the pilot on RunPod at about $3.30, at most $4.48 with a 4-hour cap at $1.12 an hour.

The account reloads itself, so the balance is no bar to a launch.

**The pilot's pod (2026-11-04, before the pilot).** There was no cpu5c instance, at 32 or at 16 vCPUs, for two and a half
hours (about 19 attempts, nothing launched). The owner chose a cpu3c pod ("go with 1"): 32 vCPUs at $0.96 an hour,
older and likely slower CPUs, with a 6-hour cap, at most $5.76. Nothing else changes.

**Where the pilot runs (2026-11-04, before the pilot).** RunPod refused every CPU pod, of either type and at 32 or 16
vCPUs, from 12:53 to 18:32 UTC. The owner: "If pods aren't available by midnight let's run it on this machine".
- Until midnight (London, GMT) both approved pod shapes are tried every 30 minutes.
- If none launches, the pilot runs here from midnight: the two runs side by side with 12 workers each, from a clean tree
  with warnings as errors. Only where it runs changes.

**The local check's outcome (2026-11-04, before the owner's answers and before any pilot).**

The data are in `docs/data/stage4c/check-sigma0.3/`. The run used code `058ff1c`, on this machine, from a clean tree with
warnings as errors, and took 35 minutes for both runs side by side.

| mode | CMA-ES: mean of each generation's best, generations 1–25 | the GA's amended pilot, the same generations | CMA-ES's step at generation 25 |
|---|---|---|---|
| uniform | 0.315 | 0.477 | 0.309 |
| fourier1 | 0.335 | 0.407 | 0.303 |

- **Prediction 1 fails:** as drafted, CMA-ES climbs slower than the GA.
- **Why:** the step size never left its first 0.3, so for 25 generations CMA-ES sampled near-random genomes around a mean
  that drifted. Each generation's ranking rests on 8 fresh training starts, which makes it noisy. The step size's
  adaptation then has no consistent direction to follow.

**Revision R1 (2026-11-04, before the second check).**
- **The first step is 0.05 of each range,** instead of 0.3. CMA-ES then starts as a local search on the GA's scale,
  whose mutations are 0.02, and its adaptation can widen or narrow the step from there.
- **A second local check** runs as §5 on fresh check seeds, 1597 (uniform) and 1596 (fourier1), writing
  `docs/data/stage4c/check/`.
- **Its prediction:** the mean best over generations 1–25 is above the first check's in both modes.

**The second check's outcome (2026-11-04, before the owner's answers and before any pilot).**

The data are in `docs/data/stage4c/check/`. The run used code `84212de`, on this machine, from a clean tree with
warnings as errors.

| mode | second check (first step 0.05): mean best, generations 1–25 | the first check | the GA's amended pilot | the second check, generations 16–25 | the GA, generations 16–25 |
|---|---|---|---|---|---|
| uniform | 0.507 | 0.315 | 0.477 | 0.575 | 0.543 |
| fourier1 | 0.324 | 0.335 | 0.407 | 0.405 | 0.431 |

- **The step size now adapts.** It grew from 0.05 to about 0.08 in both modes, the sign of a search finding a
  consistent way up.
- **CMA-ES now climbs about as fast as the GA:** a little faster in the uniform mode, a little slower in the fourier1.
- **R1's prediction fails narrowly in the fourier1 mode:** 0.324 against the first check's 0.335, though its medians are
  higher (0.211 against 0.170).
- **What the checks cannot show** is the later part, where the GA failed: carrying a working cell through the shading's
  end and the economy's tightening. Only the pilot shows that.

**The pilot's outcome (2026-11-05, before any confirmatory run).**

The data are in `docs/data/stage4c/pilot/`.
- **Where it ran:** a cpu3c pod launched at 20:26 UTC on 2026-11-04 (AMD EPYC 9965, 32 vCPUs, $0.96 an hour), so the
  fallback to this machine was not needed.
- **Code and conditions:** code `e53a4f6`, from a clean tree with warnings as errors. The pod's test suite passed first.
- **Time and cost:** both runs side by side, 16 workers each, 3.8 hours a run. The pod was up about 4.0 hours and cost
  about $3.90, within the $5.76 cap.
- **Return:** the campaign pulled every run, and the pod deleted itself at 00:27 UTC.

**Neither mode meets the pilot's rule.**

| run | champion's validation fitness | validation survival | the champion's generation | its mean beat on validation |
|---|---|---|---|---|
| uniform, seed 1501 | 0.149 | 0% of 24 | 200 | 0.001 |
| fourier1, seed 1502 | 0.160 | 0% of 24 | 160 | 0.020 |

**The runs' records, against stage 4b's amended pilot (the GA) over the same path:**

| generations | the training world | uniform: CMA-ES | uniform: the GA | fourier1: CMA-ES | fourier1: the GA |
|---|---|---|---|---|---|
| 1–50 | the shading fades, the cave's economy | 0.266 (peak 0.494) | 0.533 (peak 0.651) | 0.333 (peak 0.565) | 0.414 (peak 0.555) |
| 51–100 | translucent, the gain falling | 0.210 | 0.245 | 0.238 | 0.310 |
| 101–200 | stage 4a's world | 0.154 | 0.165 | 0.188 | 0.246 |

The table gives the mean of each generation's best training fitness.

- **The uniform run built little while shaded.**
  - Its first mean was a cell that barely beats. Through generation 23, each generation's best sample had a mean beat
    of at most 0.03.
  - The second check's uniform run, on another seed, reached 0.575 over generations 16–25. One run per mode cannot say
    how much of this is the seed.
- **In generations 51–100 the uniform population went still.**
  - The median equalled the best, and the best cell's mean beat fell to 0.002.
  - The step size meanwhile grew to about 0.3, so CMA-ES was sampling widely on a flat plateau.
  - In stage 4a's world it stayed there. Its champion barely beats, at the still cell's level (0.162 in stage 4a's check,
    on other starts).
- **The fourier1 run built working cells while shaded and lost most of them, as the GA's did.**
  - It peaked at 0.565 in generation 15.
  - Its step size stayed near 0.12–0.15 throughout.
  - In stage 4a's world it held about 0.19, below the GA's 0.246, and its champion survives no validation start.
- **Validation never moved.**
  - Over all 20 validations the best candidate in each run stayed between 0.135 and 0.160.
  - The distribution's mean validated within 0.011 of the best sample every time.

**The predictions:**

| prediction | outcome |
|---|---|
| 2. both champions validate above the GA's amended pilot | ✗: 0.149 against 0.155, and 0.160 against 0.241 |
| 3. the pilot's rule is met in at most one mode | ✓: in neither |
| 4. no champion beats B8 | not reached: no test runs |

**Next:** the confirmatory runs do not go ahead. §7's third row applies: what follows is the owner's call.

## 11. What would change this document

The owner's answers, and the local check's outcome, as dated notes before the pilot. The pilot's outcome and any
amendment, as dated notes before the confirmatory runs. After those, nothing.
