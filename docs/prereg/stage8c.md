# Preregistration: stage 8c — the rate at which a generalist emerges

**Written:** 2026-11-25, after stage 8b (`docs/decisions.md` D58) and the owner's decision on it (D59), before any run.

## 1. The question

Stage 8b found that a generalist is not an accident of one run: 6 of 15 runs gave one at 400 generations. But 6 of
15 leaves the rate anywhere from 20% to 64%, and two of stage 8b's criteria held by a single run.

Stage 8c makes thirty more fresh runs of the same design, to say what the rate is.

- **The rate at 400 generations from random genomes,** over all forty-five runs.
- **E1, a half:** do at least 15 of the 30 new runs give a generalist? (Stage 8b's bar for its ten fresh runs.)
- **E2, three in five:** do at least 18 of the 30? (Stage 8's bar, 3 of 5.)

A generalist is what stage 8 called one: a cell that does the best simple rule's job in all four worlds it was
trained in.

## 2. The runs

Thirty runs, seeds 8211 to 8240, each exactly one of stage 8b's fresh runs: the cell (fourier1, relative sensing),
CMA-ES and its settings, the eased-in path over generations 1 to 100, then 8 training starts a generation, 2 from
each of home, flicker, spot and shaded; 400 generations; the validation of 12 fixed starts in each world (seed 44);
the champion the best mean over those 48 from generation 101 on. On the compiled life (`docs/prereg/fast.md`), as
stage 8b's were.

## 3. The test

Stage 8's, unchanged but for its seeds (65 for the starts, 66 for the intervals: fresh), on the reference, on this
machine: the nine worlds, four trained in and five held back; in each the simple rules tuned on starts 1 to 50 and the
best the bar; every cell reported on starts 51 to 150. The cells: each run's champion, with champion 8102 (stage 8's
generalist) and champion 6402 (home's specialist) for reference.

## 4. Criteria, and what is reported

- **E1:** at least 15 of the 30 runs' champions are generalists.
- **E2:** at least 18 of the 30 are.
- **Reported with no criterion:** the rate over these 30 and over all 45 runs made at 400 generations (stage 8's 5,
  stage 8b's 10 and these), each with a 95% interval; how many of the new generalists travel (do the job in at least 3
  of the 5 held-back worlds); the worlds in which each beats the bar; how many runs end as a still cell.

Stage 8b's fresh runs are not counted twice: its 6 generalists in 15 runs enter only the forty-five.

## 5. Predictions

1. E1 fails: fewer than 15 of the 30 give a generalist.
2. E2 fails: fewer than 18 do.
3. Between 8 and 16 of the 30 are generalists.
4. The rate over all 45 runs lies between 30% and 50%.
5. At least nine in ten of the new generalists travel.
6. At least one of the 30 runs ends as a still cell (it does the job in no world).
7. The references stand as before: champion 8102 a generalist, champion 6402 not.

## 6. Where it runs, and what it costs

- **RunPod, on the compiled life:** six cpu5c pods of 16 vCPUs at $0.56 an hour, five runs a pod one after another,
  each pod deleted 2.8 hours after its launch: **at most $9.41**. Expected about $7 and about two hours (stage 8b's
  fresh runs took 20 to 24 minutes each on such a pod).
- **The test** on this machine, one process: about 7.5 hours (stage 8b's took 36 minutes a world for 22 cells).

## 7. The owner's answers (2026-11-25), before any run

- On D58: "Merged, please write up then continue as you suggest with the cheap runs".
- Asked whether that meant the thirty runs, with these terms (six pods at $0.56 an hour, each deleted 2.8 hours after
  its launch, at most $9.41): **"Yes, 30 runs (Recommended)"**.

## 8. Outcome (2026-11-26; D62, D63)

- **The runs:** thirty, on six pods, 97 to 117 minutes a pod, $6.44 (the ceiling was $9.41).
- **E1 fails and E2 fails:** 7 of the 30 fresh runs give a generalist (15 and 18 were asked for).
- **The rate at 400 generations:** 7 of these 30 (12% to 41%); 13 of all 45 runs, which is 29% (18% to 43%).
- **Eight more runs** do the bar's job in three of the four trained worlds and close 0.83 to 0.89 of the gap under
  flicker, where 0.9 is the line. Three runs end as still cells.
- **Every generalist travels** (4 or 5 of the 5 held-back worlds).
- **Predictions:** 1, 2, 5, 6 and 7 hold; 3 and 4 fail (I expected 8 to 16 generalists, and a rate over the 45 runs
  between 30% and 50%).
