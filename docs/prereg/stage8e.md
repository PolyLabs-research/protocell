# Preregistration: stage 8e — the rate of generalists at 800 generations, and whether circling foretells it

**Written:** 2026-11-27, after stage 8d (`docs/decisions.md` D69) and the owner's decisions on it (D71), before any
run.

## 1. The question

At 400 generations from random genomes, 13 of 45 runs give a generalist (D63). Stage 8d carried twelve of stage 8c's
runs on to 800: all eight near-misses arrived, and one of four runs that did not follow the spot (D69). Those twelve
were chosen, so no rate at 800 follows from them.

- **H, a half at 800:** with all thirty of stage 8c's runs carried on to 800 generations, are at least 15 of the 30
  generalists?
- **The rate at 800 generations from runs nobody chose,** with its interval.
- **Does a run's circling at 400 foretell it?** Stage 8b's two late arrivals were circlers at 400 and its two runs
  that never arrived were not (D61); the near-misses that all arrived were circlers (D66).

A generalist is what stage 8 called one: a cell that does the best simple rule's job in all four worlds it was trained
in. A circler is D44's: at home it runs more than 80% of the day and turns more than 0.03 rad a tick during runs.

## 2. The reading first (a probe; no criterion)

`experiments/stage8e_read.py`, seed 73, one process here, before any run: the circling at 400 generations of stage
8c's fifteen runs that did not follow the spot (the four controls stage 8d carried on: 8212, which crossed, and 8226,
8230 and 8225, which did not; its eight other runs that cope only when shaded: 8214, 8216, 8221, 8229, 8232, 8234,
8236, 8239; its three still cells: 8217, 8222, 8228), and stage 8b's runs 8101 and 8105 at 400. At home and under the
spot, 60 fresh starts each, with stage 8b's probe's movement measures.

Predictions:
1. Control 8212, the one that crossed, was a circler at 400 generations.
2. The three controls that did not cross were not circlers at 400.
3. Stage 8b's runs 8101 and 8105 were not circlers at 400.
4. At most two of the eight other runs that cope only when shaded are circlers at 400.
5. No still cell is a circler.

## 3. The forecast (written after the reading, before any run)

For each of the thirty runs, whether it will be a generalist at 800 generations: a run that followed the spot at 400
(stage 8c's seven generalists and eight near-misses) will be; a run that did not will be if and only if it circled at
400 in §2's reading. The list is added here, dated, once the reading is in and before the launch.

**The forecast, 2026-11-27, after the reading (D73) and before any run:**
- **Generalists at 800 (15):** 8211, 8213, 8215, 8218, 8219, 8220, 8223, 8224, 8227, 8231, 8233, 8235, 8237, 8238, 8240
  (the runs that followed the spot at 400).
- **Not generalists at 800 (15):** 8212, 8214, 8216, 8217, 8221, 8222, 8225, 8226, 8228, 8229, 8230, 8232, 8234, 8236,
  8239 (no run that did not follow the spot circled at 400 by D44's rule).
- **Said with it:** the rule as written puts run 8212 among the runs that do not circle (it runs 94% of the day at home
  but turns 0.018 rad a tick, under the rule's 0.03), though stage 8d's test found it a generalist at 800 (D69). The
  forecast for 8212 is likely to fail.
- **A second forecast, written after seeing the reading and so not a prediction:** a run is a generalist at 800 if it
  ran more than 80% of the day at home at 400. It differs from the registered one only for 8212, whose outcome at 800
  is already known.

## 4. The runs, and the test

- **The runs:** the eighteen of stage 8c's runs not carried on before (its seven generalists, the eight runs that cope
  only when shaded, the three still cells), carried on from 400 to 800 generations as stage 8d carried its twelve
  (stage 8b's runner, the compiled life, the champion validated again before generation 401 and kept at 600).
- **The test:** stage 8's, on the reference, on this machine, at seeds 75 and 76 (fresh): the thirty champions at 800
  generations (these eighteen and stage 8d's twelve) and champions 8102 and 6402 for reference, in the nine worlds.
  About seven hours.

## 5. Criterion, and what is reported

- **H:** at least 15 of the 30 runs' champions are generalists at 800 generations.
- **Reported with no criterion:** the rate at 800 with a 95% interval, beside the rate at 400 on stage 8c's test (7 of
  the same 30, on other starts); generalists at 800 by what each run was at 400; how often §3's forecast is right; the
  held-back worlds and the worlds in which each beats the bar.

## 6. Predictions

1. H holds: at least 15 of the 30 are generalists at 800 generations.
2. Between 15 and 19 of the 30 are.
3. All seven of stage 8c's generalists at 400 are generalists at 800.
4. The forecast from circling is right for at least 13 of the 15 runs that did not follow the spot at 400.
5. No still cell is a generalist at 800 generations.
6. Every generalist at 800 travels (at least 3 of the 5 held-back worlds).

## 7. Where it runs, and what it costs

- **RunPod, on the compiled life:** six cpu5c pods of 16 vCPUs at $0.56 an hour, three runs a pod one after another,
  each pod deleted 2.2 hours after its launch: at most $7.39. Expected about $5 and an hour and a half (stage 8d's
  carried-on runs took 4.0 to 4.9 s a generation). The terms are put to the owner before the launch.
- **The reading and the test** on this machine, one process each.

## 8. The owner's answers

- On D69: "merge, add stage 8, carry on as recommended" (D71).
