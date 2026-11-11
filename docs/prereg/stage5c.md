# Preregistration draft: stage 5c — a search that starts at the hand-written cell

**Written:** 2026-11-11, after stage 5b (`docs/decisions.md` D27) and a design probe of the start (D28), before any
search runs. The owner on D27 C: "Go with 1".

## 1. The question

The owner's hypothesis in its strong sense: interacting parts do better than every simple mechanism. Stage 4a's world
leaves room above the best simple rule, B8. Stages 4b and 4c could not test it, because neither search ever reached a
working cell there. Stage 5b wrote one by hand: on the cell with relative sensing, design 16 (fourier1) closes 0.909 of
the gap from sitting still to B8 on fresh starts.

Stage 4e's table sends a cell that carries B8 on to "evolution starting from this cell, with the strong sense as its
question". So:

- **Q1, the strong sense:** does a search that starts at design 16 find a cell that beats B8?
- **Q1b:** does it improve on design 16 at all?
- **Q2:** which parts does its champion need, and are they the parts that were written by hand?
- **Q3:** how does the champion manage, read with stage 3c's instruments?

A caveat that stands whatever the result (stage 4e §6): a champion found from here was not evolved from nothing. A pass
would show that the cell's parts can beat the best simple rule and that a search can get there from a designed start.

## 2. What stays

- **The world:** stage 4a's (`docs/prereg/stage4.md` §2): translucent, the mouth sweeping, photosynthesis at 0.55 of
  the cave's gain.
- **The cell:** stage 5's, with relative sensing as amended (`docs/prereg/stage5.md` §2, R1), in fourier1 mode, 135
  genes. Nothing about the cell changes.
- **The bar:** B8 (tau 10 s). Beside it: B5, B6, the ceiling, B0, and design 16 itself.
- **The search:** stage 4c's CMA-ES as revised (`docs/prereg/stage4c.md` §3): 96 genomes a generation, Hansen's
  constants, genes mirrored at their bounds, 8 fresh training starts a generation with shared noise, checkpoints that
  resume bit for bit, 200 generations.

## 3. What differs from stage 4c

- **The start.** The distribution's mean starts at design 16's genome, not at a random one.
- **No path.** Every generation trains in stage 4a's world. The start already works there, so nothing has to be eased
  in.
- **The first step,** from the probe (§4): 0.002 of each gene's range, with 0.005 beside it in the pilot.
- **Validation on fresh starts.** Design 16 was chosen among five checked designs on seed 20's 24 starts, and it scored
  higher there than on fresh ones, so those starts are spent.
  - 48 starts at seed 32, every 10 generations: the best three samples and the distribution's mean.
  - Design 16 is validated on the same starts before generation 1, as the reference.
  - The champion is the best candidate on validation, from generation 10 on.

## 4. The design probe (run before this draft; a calculator, not a result)

`experiments/stage5c_probe.py`, seed 31, one process here; data in `docs/data/stage5c/probe/`.

**How much change design 16 stands.** 48 neighbours at each step size, every gene moved at once as the searches move
them, on 8 fresh starts. On those starts design 16 scores 0.587, B8 0.589 and B0 0.179.

| step (share of each range) | neighbours' mean fitness | survival | share of the gap kept | neighbours at least as good as design 16 |
|---|---|---|---|---|
| 0.002 | 0.561 | 92% | 0.93 | 31% |
| 0.005 | 0.436 | 57% | 0.63 | 6% |
| 0.01 | 0.289 | 23% | 0.27 | 2% |
| 0.02 (the GA's mutation) | 0.218 | 7% | 0.10 | 0% |
| 0.05 (stage 4c's first step) | 0.164 | 1% | −0.04 | 0% |

- **Design 16 is narrow.** A step of 2% of each range, the size the GA takes at every mutation, breaks it. At either
  earlier search's step, nearly every cell made from this start is a broken one.

**How well 8 starts rank close neighbours.** The same neighbours on 8 more starts, set against their score on the
first 8. Design 16 scores 0.538 on the second 8.

| step | correlation between the two sets of starts | the first set's better half, on the second set | all neighbours, on the second set |
|---|---|---|---|
| 0.002 | +0.42 | 0.516 | 0.505 |
| 0.005 | +0.92 | 0.497 | 0.406 |

- **At 0.002 the neighbours all work, and 8 starts tell them apart only weakly.** Selection has a signal, a small one.
- **At 0.005 the ranking is reliable, because half the neighbours are broken.** Selection mostly removes damage.
- **At neither step does the selected half beat design 16 itself** (0.538). A random step hurts on average; what the
  search has to find are the few directions that help.

## 5. Runs and seeds

- **The pilot:** two runs side by side on one pod, differing only in the first step.
  - Seed 1601: first step 0.002.
  - Seed 1602: first step 0.005.
- **The pilot's rule.** A run **holds the start** if its mean at generation 200 validates no lower than design 16 less
  δ (0.012, as stage 4b's).
  - If one run holds, the confirmatory runs use its step.
  - If both hold, they use the step whose mean validates higher, averaged over generations 160–200.
  - If neither holds, an amendment comes before any confirmatory run (§9).
- **Confirmatory:** three runs at the chosen step, seeds 3601–3603.
- **Validation** seed 32; **the test** on 100 starts at seed 33; **bootstrap** seed 34. All fresh.

## 6. The test (each confirmatory champion, on the test starts)

Stage 4b's test (`docs/prereg/stage4b.md` §6) on stage 5's cell, with design 16 added as a cell of its own:

1. **Against the bar:** each champion and design 16, beside B8, B5, B6, the ceiling and B0, start by start with shared
   noise.
2. **The removals and the holds,** on each champion and on design 16.
3. **What the search changed:** for each champion, how far each group of genes moved from design 16, in shares of the
   range (the wall, the cilium angle, the core's links, biases and time constants, the spokes in and out).
4. **How it manages:** the goggles (direction removed and mirrored) and the flat pool.

## 7. The criteria

δ = 0.012, as stage 4b's.

- **Q1, it beats B8.** A champion beats the bar if its fitness less B8's has its 95% interval above 0. Q1 holds if at
  least 2 of the 3 champions do.
- **Q1b, the search improves on the hand.** The same reading for a champion's fitness less design 16's.
- **Q2, a part is needed** if its removal or hold drops at least 2 of the 3 champions by more than δ (interval).
  Beside it, the same for design 16: a hand-written part **survives** if it is needed by design 16 and still needed by
  at least 2 champions.
- **Q3** as stage 4b's §7. One difference is expected and is not a finding: the sensor now compares over time itself,
  so any cell on it may meet stage 3c's flat-pool criterion.

## 8. Predictions (written before any search runs)

1. **The pilot's run at step 0.002 holds the start.**
2. **Neither pilot run's step size ends above 0.005.** Larger steps break the cell, so the search cannot use them.
3. **Q1b in the mean but not by the criterion:** at least 2 of the 3 champions score above design 16 on the test
   starts, and at most 1 has its interval above 0.
4. **Q1 fails: no champion beats B8.** Design 16 starts 0.036 below B8 on fresh starts. A champion has to make that up
   and about as much again for its interval to clear 0, through steps this small and a ranking this noisy.
5. **Every part design 16 needs, the champions still need.** The search polishes the design; it does not rebuild it.

## 9. Decision table

| result | what follows |
|---|---|
| neither pilot run holds the start | an amendment (a smaller step, or 16 training starts a generation), with its reason; the pilot again on fresh seeds |
| a pilot run holds | the confirmatory runs, with the owner's cost confirmed |
| Q1 holds | the strong sense shown in this world from a designed start; the champions' parts and mechanism read; the owner's call on evolving such a cell from nothing |
| Q1 fails, Q1b holds | the search can improve the cell but not past B8 in 200 generations; the owner's call: a longer run from the champions, or the write-up |
| Q1 and Q1b fail | design 16 is as far as this search goes; the owner's call |

## 10. Compute

- **A generation** is 16 batches of 48 cells, about 23 s each on one core here (the probe). On a pod, with two runs
  side by side at 16 workers each, stage 4c's generations took 68 s (cpu3c) and stage 4b's 50–67 s (cpu5c).
- **The pilot:** one pod, two runs, 200 generations: about 3–4 hours.
  - cpu5c, 32 vCPUs, $1.12 an hour: about $3.40–4.40; at most $5.04 with a 4.5-hour cap.
  - If no cpu5c is free, cpu3c at $0.96 an hour: about $3.90; at most $5.76 with a 6-hour cap.
- **The confirmatory runs:** one such pod for two runs and a 16-vCPU pod at half the rate for the third: about $6, at
  most $8.70.
- **The test** runs here as one process, about an hour.
- **Nothing heavy runs on this machine** (the CPU's thermal trips, D23).

## 11. What would be built

- **`protocell/cmaes.py`:** a run may be given its starting mean and a reference genome to validate before
  generation 1. Without them a run is the same bits as before (tested).
- **`experiments/stage5c.py`:** the runner (pilot, confirm) and the test, which is stage 4b's pointed at stage 5's
  cell, with design 16 as a cell and the genes' movement added.
- **Tests:** the start is design 16's genome; a quick pilot and test end to end; stage 4b's and 4c's results
  unchanged.

## 12. Open for the owner

1. **The search:** CMA-ES from design 16, both first steps in the pilot (recommended).
   - Or the second pilot run as the GA with its mutation cut to 0.002, which keeps its best four cells unchanged each
     generation.
   - Or the second run with 16 training starts a generation, at twice that run's time.
2. **fourier1 only** (recommended). A uniform run from design 6 ("partly") could be added later; it is not part of
   this question.
3. **The criteria** in §7 and the pilot's rule in §5.
4. **The pilot's pod and cost** in §10: cpu5c at most $5.04, or cpu3c at most $5.76 if no cpu5c is free.

**The owner's answers (2026-11-11, before the pilot).** "i approve all 4":
- the search: CMA-ES from design 16, the pilot's two runs at first steps 0.002 and 0.005;
- fourier1 only;
- the criteria in §7 and the pilot's rule in §5;
- the pilot's pod: cpu5c, 32 vCPUs at $1.12 an hour with a 4.5-hour cap, at most $5.04; if no cpu5c is free, cpu3c at
  $0.96 an hour with a 6-hour cap, at most $5.76.

The runner was built after the draft and before these answers (`experiments/stage5c.py`, the start in
`protocell/cmaes.py`); the test (§6) is built before the confirmatory runs.

**The pilot's outcome (2026-11-11, before any confirmatory run).**

The data are in `docs/data/stage5c/pilot/`.
- **Where it ran:** no cpu5c was free, so a cpu3c pod (AMD EPYC 9655P, 32 vCPUs, $0.96 an hour), at code `17d6766`, from
  a clean tree with warnings as errors. The pod's test suite passed first.
- **Time and cost:** both runs side by side, 16 workers each, 3.4 hours a run. The pod was up about 3.7 hours and cost
  about $3.50, within the $5.76 cap. The campaign pulled every run and the pod deleted itself.

**Both runs hold the start, and both climb above it.** On the 48 validation starts (seed 32) design 16 scores 0.527
(survival 83%).

| run | first step | the mean at generation 200 | its last five validations | best candidate (the champion) | step at the end |
|---|---|---|---|---|---|
| seed 1601 | 0.002 | 0.599 (98%) | 0.603 | 0.614, the mean at generation 90 | 0.0020 |
| seed 1602 | 0.005 | 0.613 (100%) | 0.606 | 0.622, a sample at generation 80 | 0.0042 |

- **The rule (§5):** both runs hold, so the step whose mean validates higher over generations 160–200 goes on:
  **0.005**, by 0.606 against 0.603. The margin is small; the rule was fixed beforehand.
- **Most of the gain came early.** The mean validated at 0.560 (step 0.002) and 0.587 (step 0.005) by generation 10,
  reached about 0.60 by generation 40–50, and stayed between 0.58 and 0.61 after.
- **Where the gain is:** survival. The means survive 96–100% of the validation starts from generation 30 on, against
  design 16's 83%.
- **The step sizes barely moved:** 0.002 stayed at 0.002 (at most 0.0023); 0.005 eased to 0.0042.
- **For context, not a criterion:** B8 scores 0.557 (survival 98%) on the same validation starts, computed after the
  pilot. Every validation of either run's mean from generation 20 on is above it. These starts chose the champions, so
  only the test's fresh starts can say whether a champion beats B8.

**The predictions so far:**

| prediction | outcome |
|---|---|
| 1. the run at step 0.002 holds the start | ✓ 0.599 against 0.527 less δ |
| 2. neither run's step ends above 0.005 | ✓ 0.0020 and 0.0042 |

**Next:** §9's second row: the confirmatory runs at first step 0.005 (seeds 3601–3603), with the owner's cost
confirmed, and the test built before them.

**The owner's answer on the confirmatory runs (2026-11-11, before they run).** "Go":
- three runs at first step 0.005, seeds 3601–3603;
- one 32-vCPU pod for two runs and one 16-vCPU pod for the third, about 3.7 hours;
- cpu5c with 4.5-hour caps (at most $5.04 and $2.52), or cpu3c with 6-hour caps if no cpu5c is free (at most $5.76 and
  $2.88): at most $8.64 in all.

The test was built before these runs (`experiments/stage5c.py --phase test`).

## 13. What would change this document

The owner's answers, as a dated note before the pilot. The pilot's outcome and any amendment, as dated notes before the
confirmatory runs. The test's outcome after it. After those, nothing.
