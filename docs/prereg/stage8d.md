# Preregistration: stage 8d — does time carry the near-misses over?

**Written:** 2026-11-26, after stage 8c (`docs/decisions.md` D63) and the owner's decisions on it (D64), before any
run.

## 1. The question

Stage 8c's thirty fresh runs gave 7 generalists and 8 near-misses: runs that do the bar's job in three of the four
trained worlds and fall short only under the flickering clouds, closing 0.83 to 0.89 of the gap where 0.9 is the
line. In stage 8b two runs (8103 and 8104), circling already at 400 generations and failing under flicker and the
spot, became generalists when carried on to 800 (D58, D61).

- **N1, time carries the near-misses over:** at 800 generations, are at least 5 of the 8 generalists?
- **N2, and not every run:** at 800 generations, is at most 1 of 4 runs that do not follow the spot a generalist?

## 2. The runs

Twelve of stage 8c's runs, carried on from their checkpoints at generation 400 to generation 800, as stage 8b
carried stage 8's runs on (its §3), on the compiled life throughout:

- **The eight near-misses:** 8213, 8218, 8219, 8224, 8231, 8233, 8235, 8237.
- **The four controls,** by D64's rule (of stage 8c's runs that neither follow the spot nor are still cells, the four
  with the highest mean fitness over the four trained worlds on stage 8c's test): 8212, 8226, 8230, 8225.

Everything else is stage 8b's carried-on runs': the search goes on from its saved state; four worlds; validation of
12 fixed starts in each (seed 44); the champion kept at generation 600 too. Before generation 401 each run's champion
is validated again on the compiled life, as stage 8b did; stage 8c's runs were made on the same engine, so that
number should be stage 8c's own, and both are kept.

## 3. The test

Stage 8's, on the reference, on this machine, unchanged but for its seeds (70 for the starts, 71 for the intervals:
fresh): the nine worlds, four trained in and five held back. The cells: each run's champion at 800 generations and at
400 (its stage 8c champion), and champions 8102 and 6402 for reference: 26 cells.

## 4. Criteria, and what is reported

- **N1:** at least 5 of the 8 near-misses' champions are generalists at 800 generations.
- **N2:** at most 1 of the 4 controls' champions is a generalist at 800 generations.
- **Reported with no criterion:** each run's champion at 800 less its champion at 400, in fitness over the four trained
  worlds' reporting starts, with an interval; each near-miss's share of the gap under flicker at 400 and at 800; which
  champions at 400 are generalists on these fresh starts; the held-back worlds and the worlds in which each beats the
  bar.

## 5. Predictions

1. N1 holds.
2. N2 holds.
3. All 12 runs are better at 800 generations than at 400 over the trained worlds.
4. On these fresh starts none of the twelve champions at 400 generations is a generalist (as stage 8c found).
5. No control does the bar's job under the spot at 800 generations.
6. Every near-miss that becomes a generalist also travels (at least 3 of the 5 held-back worlds).

## 6. Where it runs, and what it costs

- **RunPod, on the compiled life:** four cpu5c pods of 16 vCPUs at $0.56 an hour, three runs a pod one after another
  (pod k: runs k, k + 4 and k + 8 of the twelve), each pod deleted 2.2 hours after its launch: at most $4.93. Expected
  about $3.50 and an hour and a half (stage 8b's carried-on runs took 3.8 to 4.8 s a generation). The terms are put
  to the owner before the launch.
- **The test** on this machine, one process: about 6 hours.

## 7. The reading of the fifteen (a probe: no criterion)

`experiments/stage8d_read.py`, seed 72, one process here: the champions at 400 generations of stage 8c's fifteen runs
that follow the spot (its seven generalists, 8211, 8215, 8220, 8223, 8227, 8238, 8240, and the eight near-misses), on
60 fresh starts in each trained world, with stage 8b's probe's movement measures (D61): the share of the day running,
the turning during runs, the running and the speed toward the light in dim light, the fresh onsets a life. A circler is
D44's: at home it runs more than 80% of the day and turns more than 0.03 rad a tick during runs.

Predictions:
1. All 15 are circlers at home.
2. Under flicker the eight's running breaks more often: their median fresh onsets a life is above the seven's.
3. Under flicker the eight run less of the day: their median share of the day running is below the seven's.
4. At home too the eight's running breaks more often: their median fresh onsets a life is above the seven's.
5. Under the spot all 15 run more than 80% of the day.

What I know going in: these runs' validation (D62) and test (D63) numbers, and D61's reading of stage 8b's cells,
where the two runs that time made generalists differed from themselves later mainly in how often their running broke.
Nothing about how these fifteen move.

## 8. The owner's answers

- On D63: "Yes to all" (D64): carry the eight on, with runs that do not follow the spot as a control; read the
  fifteen.
- On the launch, put to him with its terms (four cpu5c pods of 16 vCPUs at $0.56 an hour, three runs each, each pod
  deleted 2.2 hours after its launch, at most $4.93): **"Launch, 12 runs (Recommended)"**. Given before the launch;
  recorded here after it (D67).
