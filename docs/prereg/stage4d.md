# Preregistration: stage 4d — can the cell carry B8?

**Written:** 2026-11-05, after the thrift probe (`docs/decisions.md` D22), before any fit. The owner chose D22's option 1:
"Agree with 1, proceed".

## 1. The question

The thrift probe found that the evolved cells die in stage 4a's world because they find about half the light B8 finds.
No search in the project has made a better finder, in any world. Two explanations remain:
- **The cell is the limit:** this network cannot do what B8 does.
- **The searches are the limit:** it can, but evolving on survival does not find it.

Stage 4d tells them apart. It teaches a cell B8's behaviour directly, then judges the cell in stage 4a's world.

## 2. The teacher and its record

- **The teacher:** B8 as stage 4a chose it. It has a memory of τ = 10 s and an aim averaged over 10 s, and it rests in
  the dark.
- **The record:**
  - B8 runs in stage 4a's world on fresh starts 1–40 at seed 24, with shared noise.
  - The record keeps, tick by tick, what B8's nodes sensed (with their noise) and how B8 beat.
- **Windows:** the record is kept in windows of 500 ticks, eight per start, drawn from stream `windows` keyed by the
  start.
  - Six begin at a tick in daylight and two anywhere in the start's life; each lies wholly within the life.
  - A window counts only if B8 lived through all of it.
  - Starts 1–32 give the training windows; starts 33–40 give the held-out windows.

## 3. The fit

- **What is fitted:** a cell's genome, in each spoke mode, so that its beats match B8's beats on B8's record. The cell
  is run open loop: it senses what B8 sensed, whatever it would itself have done.
- **The cilium angle is fixed at 0,** as B8's is, so the same beats move the cell as they move B8.
- **Each window:**
  - The network starts at rest and senses the window's 500 ticks.
  - The first 200 ticks are a warm-up: B8's memories forget everything older within them (20 time constants).
  - The last 300 ticks are scored.
- **The error** is the mean squared difference between the cell's beats and B8's, over the scored ticks and the nodes.
  - The match is 1 less the error as a share of the error of a cell that never beats.
  - A match of 1 is B8 exactly; 0 is no better than never beating.
- **The search:** stage 4c's CMA-ES (`protocell/cmaes.py`) on the error, which is the same every generation because the
  windows are fixed.
  - The population is 96, the first step 0.1 of each range, the mean's start drawn at random.
  - Fit seeds are 2701 (uniform) and 2702 (fourier1).
  - The number of generations is set by §8's timing, before the run.
- **The fitted cell:**
  - Every 250 generations, the distribution's mean and the best sample run closed loop in stage 4a's world on stage
    4b's 24 validation starts (seed 20).
  - The fitted cell is the best of them there.
  - The held-out windows give its match, as a check against overfitting.

## 4. The judge

- **The runs:** the fitted cell, B8 and B0 run closed loop in stage 4a's world on fresh starts 1–100 at seed 25, with
  shared noise.
- **The measure:** the share of the gap from B0 to B8 that the cell closes, on mean fitness. A 95% bootstrap interval
  comes from resampling the starts, at seed 26.
- **Also reported:**
  - survival;
  - the light soaked per daylight tick lived, and the beat by day, as the thrift probe measured them;
  - the held-out match.

## 5. The verdict, per mode

| share of the gap from B0 to B8 closed | verdict | what follows |
|---|---|---|
| at least 0.9 | **carries B8** | the cell can find light as well as B8; the searches are what fail. Next, evolution from this cell, with the strong sense as its question |
| 0.5 to 0.9 | **partly** | the cell carries much of B8, short of all of it. The owner's call |
| below 0.5 | **does not** | this fit did not put B8 in the cell |

A "does not" leaves two readings open: the cell cannot hold B8, or this fit could not find how. The held-out match
helps tell them apart. A low match means the fit failed in open loop, before the world had a say. A high match with a
low share means the cell copies B8's beats but drifts once its own moves change what it senses.

## 6. Predictions (written before any fit)

1. **The fourier1 cell closes at least half the gap** ("partly" or better). It has a front, so it can run straight
   ahead when the light rises, as B5 does. B5 closes about nine tenths of the gap in stage 4a's checks (0.540 against
   B0's 0.162 and B8's 0.576).
2. **The uniform cell closes less of the gap than the fourier1 cell.** Without a front it must aim from the light
   across its body alone, which is faint in the translucent pool.
3. **Neither fitted cell beats B8** on mean fitness on the judge's starts.
4. **The held-out match is at least 0.5 in the fourier1 mode.**

## 7. What stays

The world, B8, B0, the cell and the two spoke modes are all as stage 4a has them. No evolution on survival happens in
this stage. The judge's starts are new to every stage.

## 8. Compute

Everything runs on this machine: the two modes side by side, 12 workers each, from a clean tree with warnings as
errors. Before the run, a timing check at full size (not a result) sets the generations so that each run takes about
an hour at most. It is recorded below as a dated note before the run.

**The timing note (2026-11-05, before the run).** A timing check at full size, scratch code and not a result, recorded B8 in 24 seconds (254 of the 256 training windows whole). It ran a fourier1 generation in 0.20 seconds with 12 workers, and a closed-loop validation of the two candidates in 28 seconds. So each run has 8,000 generations, validated every 250: about 50 minutes with the two modes side by side. Nothing else changes.

**The host crash, and how the run goes on (2026-11-05, before the rerun).**
- **What happened:** the first run, at `758c8e5` with 12 workers per mode, died with the host at 11:59 UTC, 26 minutes in, at
  about generation 2,950 of 8,000. It wrote nothing, since this code had no checkpoint. Its logs are kept outside the
  repository.
- **Why:** the host's reset register reads "internal CPU thermal limit was tripped". In 23 logged boots, that bit is set
  only after this crash and the freeze of 10-27. So 24 workers is not a safe load on this machine.
- **What changes, none of it in the method:**
  - 4 workers per mode instead of 12.
  - A fit checkpoints every 50 generations and resumes. A test shows a stopped and resumed fit is the same bits as one
    run straight through, on a different number of workers.
  - A heat logger samples the CPU's temperature every 5 seconds, and stops the run if the heat stays high. It lives
    outside the repository.
- **What stays:** the record, the fit, the seeds, the 8,000 generations, the judge, the verdict and the predictions.
- **What I have seen:** the dead run's log, which is not a result. At generation 2,750, the last validated, the match was
  about 0.25 in both modes and the closed-loop validation fitness about 0.145 (uniform) and 0.13 (fourier1), with no
  survivors. The predictions stand as written; none is changed.
- **A check the rerun gets for free:** it should repeat the dead run's logged numbers, generation for generation.

**The rerun's first attempts (2026-11-05, after the crash note).** The rerun has not happened yet.
- **What happened:** the heat guard, set at 95°C held for 60 seconds, stopped the run at 4 workers per mode and again at
  2 per mode, each within a minute and before the first checkpoint. So the crash note's 4 workers do not stand.
- **Why:** the CPU holds 98°C under sustained load here however few workers run: at about 56 W with 4 workers per mode,
  and 37 W with 2. October's traces show the same: about 19 hours at 30–69 W, at a median of 97–98°C, never above 99°C.
  So a limit of 95°C cannot pass a run on this machine, and fewer workers do not lower the temperature.
- **What next:** how the run goes on is the owner's choice. The method, the seeds and the predictions do not change.
- **Also:** `systemd-inhibit` now refuses this session the sleep block, so these attempts used the idle block alone.

**Where the rerun runs (2026-11-05, before it).** The owner chose RunPod: "go with the runpod", at about an hour and
about $1, at most $1.92.
- **The pod:** cpu3c, 32 vCPUs, $0.96 an hour, a 2-hour cap, at most $1.92. If no cpu3c is free, cpu5c at $1.12 an hour with
  a 1.7-hour cap, at most $1.90, inside the same maximum. There is no fallback to this machine.
- **The runs:** both modes side by side, 16 workers each, from a clean tree with warnings as errors. §8's "on this
  machine", and the crash note's workers and heat logger, no longer apply.
- **For the pod's scripts:** the runs write `docs/data/stage4d/fit/<mode>-<seed>/`, and the fitted cell is `champion.json`
  and `champion.npy`. `--phase fit` and `--replicate 1` name the runs. None of this touches the method.
- **The crash note's free check weakens:** bits are the same only on the same platform. The pod has another CPU, so the
  rerun may leave the dead run's numbers after its first generations. A difference there says nothing about the code.
- **What stays:** the record, the fit, the seeds, the 8,000 generations, the judge, the verdict and the predictions.

**The first pod (2026-11-05, before any outcome).** Code `e4df26b`, cpu3c, launched at 17:15 UTC, $1.92 for its 2 hours.
- **What happened:** RunPod gave it an older CPU (AMD EPYC 7713), about 1.75 times slower than the cpu3c of stage 4c's pilot.
  The pod reached its deadline at 19:15 and deleted itself, with uniform at generation 6,450 and fourier1 at 5,700 of
  8,000. No judge ran, so there is no verdict.
- **What came home:** both runs' checkpoints, also kept outside the repository.
- **What the checkpoints show, not a result:**
  - The match has stalled at 0.31 in both modes, gaining 0.001 and 0.003 over the last 1,000 generations.
  - The step size has collapsed, to 0.00003 (uniform) and 0.0002 (fourier1).
  - No candidate survived a single start at any of the 94 closed-loop validations; their fitness was 0.11 to 0.145.
  - In the uniform mode a better match went with a worse closed-loop cell (correlation -0.89 over the validations).
- **The record** has the same hash on this machine and on the pod.
- **What next:** finishing means a second pod, resumed from these checkpoints with `RESUME=1`. That is the owner's call.
  The fit would then span two CPUs, which the outcome note would say. The method, the seeds and the predictions do not
  change.

## 9. What would change this document

The timing note, the crash note and any note on how the rerun goes, before it. The outcome as a dated note after it. Nothing else.
