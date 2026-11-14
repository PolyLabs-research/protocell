# Preregistration draft: stage 6b — how reliably, and does time close the gap?

**Written:** 2026-11-14, after stage 6 (`docs/decisions.md` D33), before any run. The owner on D33 C: "go on all" (D34).

## 1. The question

Stage 6 found that evolution from random genomes, on the cell with relative sensing in fourier1 mode, does B8's job in
2 of 3 runs and beats B8 in 1. Two things it could not say:

- **How reliable is that?** Three runs are few, and one of four (with the pilot) ended as the still cell.
- **Does more time close the gap?** One run, carried on from 200 to 400 generations, went from below B8 to above it. It
  was chosen for extending because it was climbing, so it counts for nothing as a test.

Stage 6b asks both with fresh runs fixed beforehand:
- **Q0:** how many of five runs do B8's job at 400 generations?
- **Q1:** how many beat B8?
- **Q2:** within each run, is the champion at 400 generations better than the champion at 200?

## 2. The runs

Stage 6's fourier1 runs, with one change: 400 generations where stage 6 had 200.

- **The same:** the cell (relative sensing), the world (stage 4a's), the search (CMA-ES from a random mean, first step
  0.05, 96 genomes, 8 training starts a generation), the path (generations 1–50 the shading fades, 51–100 the gain
  falls, then stage 4a's world), validation (48 starts at seed 32, every 10 generations), the champion chosen from
  generation 101.
- **Different:** 300 generations in stage 4a's world, where stage 6 had 100.
- **Each run also keeps its champion as it stood at generation 200,** so Q2 compares a run with itself. Up to
  generation 200 a run is what a stage 6 run with its seed would have been.
- **Five runs,** seeds 6401–6405. No pilot: stage 6 was the pilot.
- **fourier1 only.** The uniform mode failed at stage 6's pilot and is not part of this question.

## 3. The test

Stage 6's test, on 100 fresh starts at seed 40, bootstrap at seed 41: each run's champion at 400 generations and at 200,
beside B8, B5, B6, the ceiling, B0, and three reference cells (design 16, stage 5c's champion 3603, stage 6's champion
6301).

## 4. The criteria

- **A run works** if its champion at 400 survives at least half of the validation starts.
- **Q0, it does B8's job reliably:** at least 4 of the 5 champions at 400 close 0.9 of the gap from B0 to B8 (stage
  4d's "carries B8").
- **Q1, it beats B8:** a champion's fitness less B8's has its 95% interval above 0. The mode beats B8 if at least 3 of
  the 5 champions at 400 do: a majority, as stage 4b's 2 of 3 was.
- **Q2, time helps:** for each run, its champion at 400 less its champion at 200 on the test starts, with an interval.
  Time helps if the difference is above 0 in at least 4 of the 5 runs, by the mean; the intervals are reported.
- The removals, holds, goggles and flat pool are read for each champion at 400, as stage 6.

## 5. Predictions (written before any run)

1. **At least 3 of the 5 runs work.** Stage 6 had 3 of 4.
2. **Q0 fails narrowly: 3 of 5 carry B8,** not 4. A run in four or five ends as the still cell, and one more falls
   short.
3. **Q1 holds: at least 3 of 5 beat B8 at 400 generations.** I have predicted twice that nothing would beat B8 and
   been wrong twice; the extended run and champion 6301 both did.
4. **Q2 holds:** the champion at 400 scores above the champion at 200 in at least 4 of 5 runs.
5. **No champion at 200 generations beats B8 in more than 2 of the 5 runs.**

## 6. Decision table

| result | what follows |
|---|---|
| Q1 holds | the strong sense shown by evolution from random genomes in this world, by a criterion set beforehand; the write-up; the owner's call on the uniform mode and on other worlds |
| Q0 holds, Q1 fails | evolution reliably finds B8's job and sometimes more; the owner's call: a longer or finer search, or the write-up as it stands |
| Q0 fails | the search is unreliable from nothing; what the failed runs share is read from their records; the owner's call |

## 7. Compute

- **One run a pod,** cpu5c with 16 vCPUs at $0.56 an hour. A generation took 50–53 s on the faster CPU type that pool
  gives and 62 s on the slower, so 400 generations take about 6 to 7.2 hours with validation.
- **Each pod:** about $3.40–4.00; at most $4.48 with an 8-hour cap.
- **Five pods:** about $17–20; at most $22.40.
- **If a pod reaches its cap,** its checkpoints are already pulled and the run can be carried on, with the owner's OK.
- **The test** runs here as one process, about 2.5 hours for thirteen cells.
- **The balance** is $39.57 on 2026-11-14.

## 8. What would be built

- **`protocell/cmaes.py`:** a run may keep its champion as it stood at named generations
  (`champion-at-<generation>.json`); without the option a run is the same bits as before.
- **`experiments/stage6.py`:** a phase for these runs (400 generations, the seeds above, the champion at 200 kept), and
  the test pointed at them with the champions at 200 as cells and Q2's paired differences.
- **Tests:** the seeds and settings; a run's first half equals a plain run's; a quick run and test end to end.

## 9. Open for the owner

1. **Five runs at 400 generations** (recommended), or three at lower cost and less to say about reliability.
2. **The criteria in §4:** 4 of 5 for Q0, 3 of 5 for Q1.
3. **The cost in §7:** about $17–20, at most $22.40 with 8-hour caps. This is above the "about $18" I gave before the
   draft, because the slower CPU type takes longer.

**The owner's answers (2026-11-14, before the runs).** "happy with max possible so go":
- five runs at 400 generations, seeds 6401–6405;
- the criteria in §4;
- five cpu5c pods of 16 vCPUs at $0.56 an hour with 8-hour caps, at most $22.40.

The runner and the test were built after the draft and before these answers (`experiments/stage6b.py`, the kept
champion in `protocell/cmaes.py`).

## 10. What would change this document

The owner's answers, as a dated note before the runs. Any amendment, with its reason, before the test. The test's
outcome after it. After those, nothing.
