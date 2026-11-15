# Stages 4 to 6: a world with room, a cell that can use it, and cells that beat every simple rule

**Written:** 2026-11-13, at the owner's request (D31 C1), from the decisions log and the data under `docs/data/`; stage 6
added on 2026-11-14 (D33 C1) and stage 6b on 2026-11-15 (D37 C1). It adds no result; each number is from the entry named beside it.

## The question

The hypothesis is that behaviour emerges from the interaction of parts. Its strong sense: interacting parts do better
than every simple mechanism. Through stage 3 the strong sense could not be tested, because in every world a simple rule
sat within 2–3% of the best any cell could do (D11).

Stages 4 to 6 asked four things in turn:
1. Is there a world where the simple rules leave room?
2. Can the cell do the best simple rule's job there at all?
3. Can a cell of interacting parts beat it?
4. Does such a cell emerge from random genomes?

## The short answer

| question | answer | where |
|---|---|---|
| a world with room | Yes: with a tighter economy, the best simple rule (B8) sits 0.118 below the ceiling | D16, D17 |
| does evolution reach a working cell there | No: two searches, three pilots, all end at the still cell's level | D18–D20 |
| can the cell hold B8's job, as built | No: a fit to B8's beats and two hand-written cells all fail | D23, D25 |
| with relative sensing | Yes: a hand-written cell closes 0.91 of the gap to B8 | D26, D27 |
| does a search from that cell beat B8 | Yes, in 2 of 3 runs, on fresh starts | D28, D29 |
| what the search changed | A retuning of the hand-written mechanism, mostly the core's links | D31 |
| does it emerge from random genomes | In fourier1 mode: 2 of 3 runs do B8's job and 1 beats B8. The uniform mode fails | D33 |
| how reliably, and with more time | 4 of 5 runs do B8's job; 2 of 5 beat B8; every run is better at 400 generations than at 200 | D37 |

## 1. A world with room (stage 4a; D16, D17)

- **Changing light alone left no room.** Clouds, a sweeping mouth and a circling spot added 0.02–0.07 above the simple
  rules. The reason was the economy: the reserve was full most of the day, so finding light faster earned nothing.
- **A tighter economy does.** Stage 4a's world is stage 3's translucent pool with the mouth sweeping 120° through the
  day and photosynthesis at 0.55 of the cave's gain.
- **The bar is B8,** a rule that runs while its light rises over the last 10 s and aims each run by what it sensed
  while resting. It scores 0.576 and survives 90% of its starts. Sitting still starves. The ceiling is 0.694.
- **What the world asks** (D27 A.4): each dawn the light rises up to about 8,000 body radii away, a full reserve lasts
  about 5 hours after a night, and waiting for the sweep takes about 9. The cell has to cross the dark pool.

## 2. Evolution from nothing did not get there (stages 4b, 4c; D18–D20)

- **Three pilots, two searches, the same shape.** The genetic algorithm, with the world eased in together and then one
  change at a time, and CMA-ES on the second path. Each built working cells while the world was generous and lost them
  as the economy tightened. Each ended at the still cell's level, 0.15–0.24 against the bar's 0.576.
- **The cells died by finding too little light,** about half of B8's, not mainly by spending (the thrift probe, D22).

## 3. The cell, as built, could not hold B8's job (stages 4d, 4e; D23, D25)

- **A fit to B8's beats stalled** at a match of 0.31 and did not carry B8.
- **Two cells written by hand did not either:** 13 designs, all at the still cell's level.
- **The notebooks named the blockers in the wiring:**
  - the core senses light only through the wall's beats, so the cell's own runs flood its memory;
  - there is no gain control, across light that spans three decades;
  - eight core neurons are few.

## 4. One change to the cell: relative sensing (stage 5; D26, D27)

- **The change:** each wall node takes in the log of its light over the wall's recent mean (a 10 s average), with
  floors so that darkness reads as dark. Fixed constants, no new genes, off by default so earlier results keep their
  bits.
- **A hand-written fourier1 cell then carries B8, narrowly.** Design 16 scores 0.527 against B8's 0.563 on 100 fresh
  starts: 0.909 of the gap from sitting still, interval [0.850, 0.965]. It used 5 of its 50 world checks.
- **What it took:** a rise detector, an exploring rhythm that runs often in dim light and rarely in bright, a copy of
  the cell's own drive matched to the wall's response in time and by light level, and a drive strong enough to swim
  fast. All eight core neurons are used.
- **A hand-written uniform cell reaches "partly"** (0.618 of the gap). Without a front it has to make one with its
  ring, which fights the copy its comparison needs.

## 5. A search from the hand-written cell beats B8 (stage 5c; D28, D29)

- **The start is a narrow peak.** A step of 0.2% of each gene's range keeps 0.93 of its worth; the genetic algorithm's
  usual 2% keeps a tenth. The earlier searches' steps would have broken it at once.
- **The search:** CMA-ES with its mean started at design 16, first step 0.5% (chosen by a pilot's rule), 200
  generations in stage 4a's world, three runs.
- **The test,** on 100 fresh starts:

  | cell | fitness | survival | against B8 [95%] |
  |---|---|---|---|
  | the ceiling | 0.683 | 100% | |
  | champion 3603 | 0.610 | 100% | +0.053 [+0.039, +0.068] |
  | champion 3602 | 0.593 | 96% | +0.035 [+0.016, +0.055] |
  | champion 3601 | 0.574 | 93% | +0.016 [−0.009, +0.040] |
  | B8 | 0.557 | 95% | |
  | design 16 | 0.537 | 82% | |

- **Two of three champions beat B8,** the criterion set beforehand; all three improve on design 16.
- **It repeats** on a third set of starts (D31): champion 3603 at 0.605, B8 at 0.531.
- **I predicted it would fail.** The preregistered predictions said the search would polish the design without beating
  B8.

## 6. What the search changed (D31)

- **In behaviour, three things.** Champion 3603, beside design 16:
  - runs 61% of the time in dim light against 41%, and crosses the dark about twice as fast;
  - holds a run while the light rises 93% of the time against about 65%;
  - wanders less in bright light, and spends more of its life there.
- **In the genes:** every gene moved about 1% of its range. The core's links carry about two thirds of the gain alone.
  The retuned biases and inward spokes help only together with them.
- **Three independent runs moved the same way,** and the path from design 16 to the champion is a smooth slope.
- **Every part design 16 needs, the champions still need.** The search retuned the mechanism; it did not find another.

## 7. Evolution from nothing, on the new cell (stage 6; D33)

- **The design:** stage 4c exactly as it ran (the same search, eased-in path and world), with only the sensor changed.
- **The pilot:** the fourier1 run built a working cell and kept it through the tightening economy; the uniform run
  ended as the still cell, as before.
- **The test,** on 100 fresh starts, three confirmatory fourier1 runs:

  | cell | fitness | survival | against B8 [95%] | share of the gap to B8 closed |
  |---|---|---|---|---|
  | champion 6301 | 0.588 | 99% | +0.050 [+0.032, +0.069] | 1.13 |
  | B8 | 0.538 | 87% | | |
  | champion 6302 | 0.510 | 86% | −0.029 [−0.053, −0.004] | 0.92 |
  | champion 6303 | 0.165 | 0% | −0.373 | 0.00 |

  Beside them, stage 5c's champion 3603 scores 0.596 and design 16 scores 0.509.
- **Two of three do B8's job** (the criterion for "carries B8"); **one of three beats B8,** short of the two the
  criterion for "beats" asked.
- **More generations help, in the one run tried:** the pilot's run, carried on from 200 to 400 generations, goes from
  0.489 to 0.573, above B8. It was chosen for extending because it was still climbing, so it is descriptive.
- **The earlier failures were the sensor's.** Stage 4c ended at the still cell with this search, path and world.
- **Evolution built it another way:** the evolved cells need their ring's links, which design 16 does not use.

## 8. How reliably, and with more time (stage 6b; D37)

- **The design:** five fresh fourier1 runs from random genomes at 400 generations, each also keeping its champion as it
  stood at generation 200. The criteria were fixed beforehand: 4 of 5 to count as doing B8's job reliably, 3 of 5 to
  count as beating B8.
- **The test,** on 100 fresh starts (B8 0.558, the ceiling 0.689):

  | champion | fitness | against B8 [95%] | share of the gap closed | at 200 generations |
  |---|---|---|---|---|
  | 6402 | 0.642 | +0.084 [+0.069, +0.100] | 1.21 | 0.615 |
  | 6405 | 0.623 | +0.065 [+0.052, +0.080] | 1.17 | 0.574 |
  | 6401 | 0.569 | +0.011 [−0.008, +0.029] | 1.03 | 0.268 |
  | 6404 | 0.556 | −0.002 [−0.024, +0.020] | 0.99 | 0.431 |
  | 6403 | 0.425 | −0.133 [−0.168, −0.100] | 0.66 | 0.255 |

- **It does B8's job reliably:** 4 of 5, and no run ended as the still cell.
- **It beats B8 in 2 of 5,** one short of the criterion; two more are level with B8.
- **Every run is better at 400 generations than at 200.**
- **Champion 6402 is the best cell so far,** above the best from the hand-written start (0.611 on these starts).
- **Across stages 6 and 6b:** of 8 preregistered runs from random genomes, 6 do B8's job and 3 beat B8.

## 9. How the cells do it (D31, D36)

- **The cell found by search from the hand design** rests, drifts a little and turns at random, and starts a run when
  its drift is climbing: 86% of its fresh runs begin while the light is rising, against 51% for the hand-written cell.
  So its runs begin aimed at the light with nothing read across the body.
- **The cell evolved from random genomes** (champion 6301) does not rest. By day it swims in circles almost all the
  time and biases the circling toward the light, using its ring's links; at night it is still. How the circling is
  biased has not been shown.

## What this does and does not show

- **Shown:** in this world, a cell of interacting parts does better than every simple rule tried, on fresh starts: in
  two of three runs from a designed start, and in three of eight from random genomes. From random genomes a cell that
  does the best simple rule's job emerges reliably (four of five at 400 generations).
- **Not shown:**
  - that a cell beating B8 emerges from nothing in most runs: 2 of 5 did at 400 generations, where the criterion
    asked for 3; and the sensor and the eased-in path were designed by hand;
  - anything beyond one spoke mode (fourier1), one world and one sensor;
  - that no simple rule could sit higher than B8. B8 is the best of those tried.
- **Open:** how the champions' fresh runs come to begin aimed at the mouth without reading the direction across the
  body is answered for the searched cell (§9); how the evolved cell's circling is biased is not (D36 B.2).

## Cost and conduct

- **RunPod,** stages 4 to 6: about $52 in all (stage 4b $5.90, 4c $3.90, 4d $2.80, 5c $9.40, 6 $11.40, 6b $18.30), each launch confirmed by
  the owner first.
- **This machine** ran the checks, probes, hand-writing and tests as one process, after an all-core run tripped the
  CPU's thermal limit (D23).
- **Each stage** had a preregistration with predictions before it ran. The predictions that failed are recorded as
  failed in their documents; twice I predicted that no champion would beat B8, and twice one did.
- **Errors of mine, disclosed where they happened:** a campaign bug that stopped a pull loop (D18); probes that bypassed
  their log and a calculator with a wrong constant (D27); a scoring summary that misread a column (D29); a test that
  overwrote one champion's rows with another's (D33).

## Next

Whether the cells hold up in worlds they never saw (D37 C2).
