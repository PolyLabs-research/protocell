# Preregistration draft: stage 6 — evolution from nothing on the cell with relative sensing

**Written:** 2026-11-13, after stage 5c and its explaining probe (`docs/decisions.md` D29, D31), before any run. The
owner on D31 C: "Agree, continue as suggested" (D32).

## 1. The question

Stage 5c showed that a cell of interacting parts can beat every simple rule tried in stage 4a's world. Its start was
written by hand. The hypothesis is about emergence, so the caveat matters: evolution from nothing failed there on the
old cell (stages 4b and 4c), and has not been tried on the new one.

Stage 4c's question, unchanged, on stage 5's cell:
- **Q1, the strong sense:** does evolution from random genomes find a cell that beats B8?
- **Q0, a step before it:** does it find a cell that does B8's job at all? Stage 4d's measure answers it: the share of
  the gap from sitting still to B8 that a champion closes (carries B8 from 0.9, partly from 0.5).
- **Q2, Q3:** which parts a champion needs, and how it manages, as stage 4b's test reads them.

## 2. One change from stage 4c: the sensor

Everything is stage 4c's as it ran (`docs/prereg/stage4c.md`, with revision R1), except the cell senses light relative
to its recent level (`docs/prereg/stage5.md` §2 with its amendment R1).

- **The world:** stage 4a's.
- **The cell:** both spoke modes, uniform (103 genes) and fourier1 (135).
- **The search:** CMA-ES, 96 genomes a generation, first step 0.05 of each range, the mean drawn at random, 8 fresh
  training starts a generation with shared noise, 200 generations.
- **The path:** stage 4b's amended one. Generations 1–50, the shading fades in the cave's economy; 51–100, the gain
  falls to 0.55 with the cell translucent; 101–200, stage 4a's world. The champion is chosen from generation 101.
- **Why keep the path and the search:** then the sensor is the only thing that differs from stage 4c's pilot, which
  ended at the still cell's level (0.149 and 0.160, surviving no validation start).

**Validation** moves to stage 5c's starts: 48 at seed 32, every 10 generations, the best three samples and the mean. On
those starts design 16 scores 0.527, B8 0.557 and stage 5c's champions 0.61–0.62, so a run's progress reads against
known cells.

## 3. Runs and seeds

- **Pilot:** one run per mode, seeds 6101 (uniform) and 6102 (fourier1).
- **Confirmatory:** three per mode, 6201–6203 and 6301–6303.
- **Validation** seed 32; **the test** on 100 starts at seed 37; **bootstrap** seed 38. The test's and the runs' seeds
  are fresh.

## 4. The pilot's rule

Stage 4b's: a mode goes on to its confirmatory runs if the pilot's champion survives at least half of the validation
starts. If neither mode's does, what follows is the owner's call (§8).

## 5. The test (each confirmatory champion, on the test starts)

Stage 4b's test on stage 5's cell, as stage 5c ran it, with two cells beside the champions for reference: design 16 and
stage 5c's champion 3603.

## 6. The criteria

δ = 0.012, as stage 4b's.

- **Q0, it does B8's job:** per champion, the share of the gap from B0 to B8 closed, with its interval; stage 4d's
  verdicts. A mode **carries B8** if at least 2 of its 3 champions do.
- **Q1, it beats B8:** a champion's fitness less B8's has its 95% interval above 0; a mode holds if at least 2 of 3 do.
- **Q2 and Q3** as stage 4b's §7, with stage 5c's note on the flat pool.

## 7. Predictions (written before any run)

1. **The pilot's champions validate above stage 4c's** (0.149 uniform, 0.160 fourier1) **in both modes.** The sensor
   makes dim light readable, which the old cell could not do.
2. **The pilot's rule is met in at most one mode.** Design 16's peak is narrow (D28), and a first step of 5% of each
   range is 25 times the step it stands; a search this coarse has to find a broader way to do the job.
3. **If a mode is confirmed, it does not carry B8:** fewer than 2 of its 3 champions close 0.9 of the gap.
4. **No confirmatory champion beats B8.**
5. **fourier1 does better than uniform:** its pilot champion validates higher. It has a front; the uniform cell has to
   make one (D27 B.4).

I predicted stage 5c would fail and it did not (D29), so these carry less weight than they read.

## 8. Decision table

| result | what follows |
|---|---|
| the pilot's rule is met in a mode | that mode's three confirmatory runs, with the owner's cost confirmed, then the test |
| it is met in neither, but prediction 1 holds | the sensor helps and the search still falls short; the owner's call: a finer or longer search, another path, or the write-up |
| it is met in neither, and prediction 1 fails | the sensor alone changes nothing for a search from nothing; the owner's call |
| the test: Q1 holds in a mode | the strong sense shown by evolution from nothing in this world; the champions read beside design 16 and champion 3603 |
| the test: Q0 holds, Q1 fails | evolution finds B8's job but not more; the owner's call: a search from its champions as stage 5c's |
| the test: Q0 fails | recorded; the owner's call |

## 9. Compute

- **One run a pod,** on cpu5c with 16 vCPUs at $0.56 an hour, as stage 5c's confirmatory runs: a generation's 16 jobs
  fill 16 workers, about 53 s a generation, about 3.1 hours a run.
- **The pilot:** two pods, about $3.50; at most $5.04 with 4.5-hour caps.
- **The confirmatory runs:** three pods a mode, about $5.25 a mode; at most $7.56 a mode.
- **No cpu3c pods:** their CPU type varies, and a slow one cannot finish inside a cap (stage 5c's note).
- **The test** runs here as one process, about 70 minutes a mode.

## 10. What would be built

- **`experiments/stage6.py`:** stage 4c's runner pointed at stage 5's cell, with these seeds and validation; the test
  is stage 5c's parametrisation of stage 4b's, with the two reference cells and Q0's share of the gap.
- **Tests:** the seeds and settings; a quick pilot, confirm and test end to end; stage 4c's results unchanged.

## 11. Open for the owner

1. **The design in §2: stage 4c with only the sensor changed** (recommended), so the comparison is clean.
   - Or a finer first step (0.02) or more generations, which would change two things at once.
2. **Both modes in the pilot** (recommended), or fourier1 only at half the cost.
3. **The criteria and the pilot's rule** in §4 and §6.
4. **The pilot's cost:** two cpu5c 16-vCPU pods, about $3.50, at most $5.04. The balance is $59.06 on 2026-11-13.

**The owner's answers (2026-11-13, before the pilot).** "Continue as recommended":
- the design in §2, stage 4c with only the sensor changed;
- both modes in the pilot;
- the criteria and the pilot's rule in §4 and §6;
- the pilot's pods: two cpu5c pods of 16 vCPUs at $0.56 an hour with 4.5-hour caps, at most $5.04.

The runner and the test were built after the draft and before these answers (`experiments/stage6.py`).

**The pilot's outcome (2026-11-13, before any confirmatory run).**

The data are in `docs/data/stage6/pilot/`. Each run had its own cpu5c pod (16 vCPUs, $0.56 an hour), at code `9e494e1`,
from a clean tree with warnings as errors, after the pod's test suite passed. About 3.1 hours a run and about $3.90 for
both; the campaigns pulled both runs and the pods deleted themselves.

| run | champion's validation fitness | validation survival | the champion's generation |
|---|---|---|---|
| uniform, seed 6101 | 0.152 | 0% of 48 | 180 |
| fourier1, seed 6102 | 0.516 | 85% of 48 | 200 |

On these validation starts design 16 scores 0.527 (83%), B8 0.557 (98%) and the still cell 0.152.

**The rule (§4) is met in the fourier1 mode and not in the uniform.**

- **fourier1 built a working cell from nothing and carried it into stage 4a's world.**
  - As in stage 4c, the run lost most of what it had built while the gain fell (the best of each generation averaged
    0.57 over generations 1–50 and 0.36 over 51–100).
  - Unlike stage 4c, something survived: by generation 40–50 a candidate already survived a quarter of the validation
    starts, and from generation 140 on the best candidate survives 46–85%.
  - It was still climbing when the run ended: the best validation rose from 0.28 at generation 130 to 0.52 at 200, the
    last validation being the highest.
  - The step size fell from 0.15 to 0.10 over the run.
- **The uniform run ended as stage 4c's did.** It built working cells while shaded (a peak of 0.74), lost them as the
  gain fell, and from generation 60 its best candidate is the still cell (0.152, the same number as B0 on these starts,
  with no beating at all). Its step size grew to 0.26.

**The predictions so far:**

| prediction | outcome |
|---|---|
| 1. both pilot champions validate above stage 4c's | ✓ by the letter (0.152 against 0.149; 0.516 against 0.160). For the uniform mode it means nothing: both numbers are the still cell on different starts |
| 2. the pilot's rule is met in at most one mode | ✓ fourier1 only |
| 5. fourier1's champion validates higher than uniform's | ✓ |

**Next:** §8's first row for the fourier1 mode: its three confirmatory runs (seeds 6301–6303), with the owner's cost
confirmed. The uniform mode stops here unless the owner chooses otherwise.

**The owner's answer on what follows the pilot (2026-11-13, before the runs).** "Go on both":
1. **The fourier1 mode's three confirmatory runs,** seeds 6301–6303, as preregistered: three cpu5c pods of 16 vCPUs at
   $0.56 an hour with 4.5-hour caps, about $5.25, at most $7.56.
2. **An extension, not preregistered and descriptive only:** the pilot's fourier1 run (seed 6102) carried on from its
   last checkpoint for 200 more generations in stage 4a's world, 400 in all, because it was still climbing at 200.
   - Everything else is the run's own: its seed, its search state, validation every 10 generations.
   - It writes `docs/data/stage6/extend/fourier1-6102/`; the pilot's files stay as they are.
   - Its champion is tested beside the others and stays outside every criterion and every prediction.
   - One cpu5c pod as above, about $1.75, at most $2.52.

## 12. What would change this document

The owner's answers, as a dated note before the pilot. The pilot's outcome and any amendment, as dated notes before the
confirmatory runs. The test's outcome after it. After those, nothing.
