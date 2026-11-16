# Preregistration draft: stage 8 — evolution in several worlds at once

**Written:** 2026-11-15, after stage 7 (`docs/decisions.md` D40), before any run. The owner on D40 C: "Merged and move
on as recommended" (D41).

## 1. The question

Stage 7 found that cells made in one world beat the best simple rule there and mostly not elsewhere, while the simple
rules, re-tuned for each world, hold up everywhere. One evolved cell (champion 6402) held up in every world without
having met six of them, so a cell that copes with all of them exists.

Stage 8 asks whether evolution finds such cells when it is asked to:
- **G1, a generalist emerges:** does a cell evolved from random genomes in four different worlds at once do each
  world's best simple rule's job in all four?
- **G2, it travels:** does such a cell also do the job in worlds held back from its evolution?
- **G3, the strong sense across worlds:** in how many worlds does it beat that world's best simple rule?
- **The cost of generality:** at home, how far is it below the home specialists?

## 2. The worlds

All are stage 3's translucent pool with stage 5's sensor on the cells, as in stage 7.

| | world | what it is |
|---|---|---|
| trained in | home | the mouth sweeping, gain 0.55 of the cave's |
| trained in | flicker | the mouth fixed; clouds, sun for 2 minutes and shade at 0.3 for 1 minute on average |
| trained in | spot | a spot circling the pool's centre at 2,500 R every 2 hours, gain 0.45 |
| trained in | shaded | home, with the cell shading itself (the far side gets 0.3 of the light) |
| held back | fixed mouth | home without the sweep |
| held back | tighter | home at gain 0.45 |
| held back | sweep and flicker | home with flicker's clouds |
| held back | slow clouds | home with slower clouds, sun for 10 minutes and shade for 5 |
| held back | slow spot | the spot circling every 6 hours, gain 0.45 |

The four trained in are the ones stage 7's cells failed in differently. The first three held back were stage 7's; the
last two are new and no cell has run in them.

## 3. The runs

Stage 6b's runs, with one change: from generation 101 the training starts come from the four worlds.

- **The same:** the cell, fourier1 mode, CMA-ES from a random mean (first step 0.05, 96 genomes), 8 training starts a
  generation with shared noise, 400 generations, the champion from generation 101 and also kept at generation 200.
- **Generations 1–100:** stage 4b's amended path, unchanged, so a run begins exactly as a stage 6b run with its seed
  would.
- **From generation 101:** each generation's 8 starts are 2 from each of the four worlds. A genome's score is its mean
  fitness over the 8.
- **Validation,** every 10 generations: 12 fixed starts in each of the four worlds (48 in all, seed 44). The champion
  is the candidate with the best mean over the 48.
- **Five runs,** seeds 8101–8105. **The first two are the pilot.**

## 4. The pilot's rule

A pilot run **works** if its champion survives at least half of the validation starts in at least three of the four
worlds. If either pilot run works, the other three runs follow (the owner's cost confirmed) and the pilot's two count
as runs 1 and 2. If neither works, what follows is the owner's call (§8), and nothing more is spent.

## 5. The test

Stage 7's test, on fresh starts at seed 46 (bootstrap 47): in each of the nine worlds the simple rules are re-tuned on
starts 1–50 and the best sets the bar; every cell is reported on starts 51–150. The cells: each run's champion, and
for reference champion 6402 (stage 7's most robust cell) and champion 3603.

## 6. The criteria

A cell **does the job** in a world if it closes at least 0.9 of the gap from sitting still to that world's bar; it
**beats** the bar if its fitness less the bar's has its 95% interval above 0.

- **G1:** a champion is a generalist if it does the job in all four trained worlds. G1 holds if at least 3 of the 5
  champions are generalists.
- **G2:** a champion travels if it does the job in at least 3 of the 5 held-back worlds. G2 holds if at least 3 of the
  5 champions travel.
- **G3:** reported, with no threshold: for each champion, the number of worlds, of nine, in which it beats the bar.
- **The cost of generality:** each champion's fitness at home less champion 6402's, with its interval.

## 7. Predictions (written before any run)

1. **At least one pilot run works.**
2. **G1 fails:** fewer than 3 of the 5 champions do the job in all four trained worlds. The spot and the shaded cell
   ask for different things, and the typical champion drops one world.
3. **No champion beats the bar in more than two of the nine worlds.**
4. **Generality costs at home:** every champion scores below champion 6402 at home, with the interval below 0.
5. **The best stage 8 champion does the job in at least 4 of the 5 held-back worlds:** a cell shaped by four worlds
   travels better than cells shaped by one, of which the best (6402) did the job in 4 of stage 7's 6.

## 8. Decision table

| result | what follows |
|---|---|
| neither pilot run works | recorded; the owner's call: an easier mix (fewer worlds, or home first and the others eased in), or the write-up |
| G1 and G2 hold | generalists emerge and travel; the champions are read (how one cell handles clouds, a spot and shading); the owner's call on the strong sense across worlds |
| G1 holds, G2 fails | evolution fits the worlds it is given and no more; the owner's call |
| G1 fails | one search from nothing does not cover four worlds in 400 generations; the owner's call: more time, more runs, or the write-up |

## 9. Compute

- **A generation costs what stage 6b's did** (the same number of cells and ticks): about 50–60 s on a cpu5c pod with 16
  vCPUs at $0.56 an hour, so about 5.5 to 7 hours a run with validation.
- **The pilot:** two pods, about $6.50–8; at most $8.96 with 8-hour caps.
- **The other three runs:** about $10–12; at most $13.44.
- **In all:** about $17–20; at most $22.40. The balance is $20.95 on 2026-11-15, with a chess pod spending $0.89 an hour from it; the account reloads itself.
- **Launches are staggered** by a minute or more (stage 6b's note).
- **The test** runs here as one process, detached: nine worlds, about 4.5 hours.

## 10. What would be built

- **`protocell/evolve.py`:** a generation's training starts may come from several worlds; with one world, as before.
- **`protocell/cmaes.py`:** validation may be on several worlds' starts, with each world's numbers kept; with one
  world, as before.
- **`experiments/stage7.py`:** its run takes the cells and the worlds, so stage 8's test is stage 7's.
- **`experiments/stage8.py`:** the runs, the pilot's rule, the test and the criteria.
- **Tests:** a run's first 100 generations equal a stage 6b run's; earlier stages' results unchanged; a quick run and
  test end to end.

## 11. Open for the owner

1. **The four worlds trained in and the five held back** (§2), recommended as drafted.
2. **The mix:** two starts from each world every generation, from generation 101 (recommended). Or the other worlds
   eased in one at a time, which is gentler and changes more than one thing.
3. **The criteria** in §6 and the pilot's rule in §4.
4. **The pilot's cost:** two pods, about $6.50–8, at most $8.96.

**The owner's answers (2026-11-15, before the pilot).** "I'm happy to go with your recommendations here":
- the four worlds trained in and the five held back, as in §2;
- the mix: two starts from each world every generation, from generation 101;
- the criteria in §6 and the pilot's rule in §4;
- the pilot's pods: two cpu5c pods of 16 vCPUs at $0.56 an hour with 8-hour caps, at most $8.96. The account reloads
  itself.

The runner and the test were built after the draft and before these answers (`experiments/stage8.py`, the several
worlds in `protocell/evolve.py` and `protocell/cmaes.py`).

**The pilot's outcome (2026-11-16, before the other runs).**

The data are in `docs/data/stage8/pilot/`. Each run had its own cpu5c pod of 16 vCPUs at code `55c603c`, from a clean
tree with warnings as errors, after the pod's test suite passed: seed 8101 on an AMD EPYC 9575F (6.0 hours), seed 8102
on an EPYC 4564P (6.8 hours). The launches were 80 s apart; both runs were pulled and both pods deleted themselves.
About $7.55, within the $8.96 cap.

**Both pilot runs work** (§4). Each champion on the 12 validation starts of each world, fitness and survival:

| run | champion's generation | home | flicker | spot | shaded | mean of the 48 |
|---|---|---|---|---|---|---|
| seed 8101 | 400 | 0.569 (92%) | 0.397 (50%) | 0.164 (0%) | 0.640 (100%) | 0.443 |
| seed 8102 | 390 | 0.633 (100%) | 0.571 (92%) | 0.596 (100%) | 0.633 (100%) | 0.608 |

- **Seed 8102 survives nearly every validation start in all four worlds.** It reached home by generation 120, the
  spot between generations 160 and 200, and held all four from generation 240 on.
- **Seed 8101 works in three worlds and never finds the spot** (0% survive there throughout). It was still climbing at
  the end: its mean rose from 0.34 at generation 200 to 0.44 at 400.
- **Both start from the shaded cell,** the world most like the path's first generations: 100% survival there from
  generation 40 on in both runs, while the other three worlds were at the still cell's level.
- **Not a verdict:** these starts chose the champions, and the bars here are not measured on them. The test decides
  G1 to G3 on fresh starts, against each world's re-tuned best simple rule.

**The predictions so far:**

| prediction | outcome |
|---|---|
| 1. at least one pilot run works | ✓ both |

**Next:** §4: runs 3 to 5 (seeds 8103–8105), with the owner's cost confirmed; the pilot's two runs are runs 1 and 2.

## 12. What would change this document

The owner's answers, as a dated note before the pilot. The pilot's outcome and any amendment, before the other runs.
The test's outcome after it. After those, nothing.
