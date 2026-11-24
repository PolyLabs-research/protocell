# Preregistration draft: stage 8b — how reliably a generalist emerges, with more time and with more runs

**Written:** 2026-11-24, after the reading of champion 8102 (`docs/decisions.md` D45) and the owner's decision D46
(the runs move from RunPod to his own machine), before any run. A draft: §8's points are the owner's.

## 1. The question

Stage 8 asked evolution for a cell that copes with four worlds at once. One run in five gave one (champion 8102), so
the criteria set beforehand were not met. That one result can be read two ways, and they call for different runs.

- **R1, more time makes generalists:** carried on to 800 generations, do stage 8's other runs become generalists?
  Stage 6b found that every run was better at 400 generations than at 200.
- **R2, time helps each run:** is each run better at 800 generations than it was at 400?
- **R3, the rate from nothing:** of ten fresh runs at 400 generations, how many give a generalist?

A generalist is what stage 8 called one (G1): a cell that does the best simple rule's job in all four worlds it was
trained in.

## 2. The runs

| | runs | from | to |
|---|---|---|---|
| carried on | stage 8's five, seeds 8101–8105 | their checkpoints at generation 400 | generation 800 |
| fresh | ten, seeds 8201–8210 | random genomes | generation 400 |

- **Everything else is stage 8's:** the cell (fourier1, relative sensing), CMA-ES and its settings, the eased-in path
  over generations 1–100, then 8 training starts a generation, 2 from each of home, flicker, spot and shaded; the
  validation of 12 fixed starts in each (seed 44); the champion the best mean over those 48 from generation 101 on.
- **A fresh run also keeps its champion at generation 200,** as stage 8's did; a carried-on run keeps its at 600.

## 3. The engine, and one consequence

These are the first runs made on the compiled life (`docs/prereg/fast.md`), which this stage depends on: it runs only
if that plan's check holds (D48).

- **A fresh run** is on the compiled life from its first generation: its training lives and its validation.
- **A carried-on run changes engine at generation 400.** Its champion so far was validated by the reference, on a
  pod. Before generation 401 that champion is validated again on the compiled life, on the same 48 starts, and that
  number is the one later candidates must beat. So every comparison after generation 400 is made on one engine. Both
  numbers are kept (`carried-on.json`); stage 8's own files are not touched.
- **The test is on the reference,** as always.

## 4. The test

Stage 8's, unchanged but for its seeds (54 for the starts, 55 for the intervals: fresh): the nine worlds, four
trained in and five held back; in each the simple rules tuned on starts 1–50 and the best the bar; every cell
reported on starts 51–150.

The cells: each carried-on run's champion at 800 generations beside its champion at 400 (stage 8's own), each fresh
run's champion, and champions 6402 and 3603 for reference. The worlds do not depend on each other, so they may run
side by side.

## 5. Criteria

- **R1:** at least 3 of the 5 carried-on runs' champions at 800 generations are generalists (stage 8's bar, 3 of 5).
- **R2:** at least 4 of the 5 are better at 800 than at 400: the champion at 800 less the champion at 400, in fitness
  over the four trained worlds' reporting starts, above 0 (stage 6b's rule for time).
- **R3:** at least 5 of the 10 fresh runs' champions are generalists (the same share as stage 8's bar).

Reported with no criterion: the rate of generalists at 400 generations over stage 8's five runs and the ten fresh ones
together, with a 95% interval; for every new champion, the held-back worlds it does the job in and the worlds in
which it beats the bar (stage 8's G2 and G3).

## 6. Predictions

1. R1 fails: fewer than 3 of the 5 are generalists at 800 generations.
2. R2 holds: at least 4 of the 5 are better at 800 than at 400.
3. More time makes at least one new generalist among runs 8101, 8103, 8104 and 8105.
4. R3 fails: between 1 and 3 of the 10 fresh runs give a generalist.
5. Some new champion beats the bar in at least 5 of the nine worlds, as champion 8102 did.
6. On the test's fresh starts stage 8's champions stand as they did: 8102 a generalist at 400 generations, the other
   four not.

## 7. Where it runs, and what it costs

- **The owner's machine,** not RunPod: no money.
- **Time, from this machine** (`docs/data/fast/speed/`, and a trial of this stage's runner at full size, not kept): a
  generation late in run 8102 took 9 s on 4 processes, where its pod took 109 s. So 400 generations are about an hour
  on 4 processes and half that on 8; the fifteen runs here, 6,000 generations, are 7 to 15 hours. The laptop's own
  figure comes from `laptop.sh`.
- **A run checkpoints after every generation;** the same command carries it on after a stop.
- **The test** is on the reference and is the slower part: about 7 hours as one process, under an hour with a
  process a world.

On the laptop, from a fresh clone of this branch (a clean tree, as every run that counts):

    bash laptop.sh                                   # once: set up, test, time the CPU and the GPU
    P=".venv/bin/python -W error::RuntimeWarning -m experiments.stage8b"
    systemd-inhibit $P --phase extend --replicate 1 2 3 4 5 --workers 8
    systemd-inhibit $P --phase fresh --replicate 1 2 3 4 5 6 7 8 9 10 --workers 8
    .venv/bin/python -m experiments.stage8b --phase status
    systemd-inhibit $P --phase test --workers 9
    git add docs/data/stage8b docs/data/fast && git commit -m "Stage 8b: the runs and the test, the data" && git push

`--workers` is the laptop's physical cores (8 and 16 divide a generation's 16 jobs evenly); `--device cuda` runs the
lives on the GPU instead, if `laptop.sh` shows it faster. `systemd-inhibit` keeps the machine awake.

## 8. For the owner

1. **Both kinds of run, or one?** Recommended: both. They answer different questions and together cost a night.
   Carried on alone is 2,000 generations; fresh alone 4,000.
2. **Ten fresh runs?** With stage 8's five that makes fifteen at 400 generations. Five would do less: one generalist
   in ten runs and three in ten are hard to tell apart with five.
3. **The criteria** in §5, each stage 8's or stage 6b's bar carried over.
4. **The carried-on runs' change of engine** (§3): the champion validated again before generation 401.
5. **CPU or GPU:** whichever `laptop.sh` shows faster on the laptop. The GPU form has not run on a GPU yet.
