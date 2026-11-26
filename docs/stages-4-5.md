# Stages 4 to 8c: a world with room, a cell that can use it, cells that beat every simple rule there, and how far that travels

**Written:** 2026-11-13, at the owner's request (D31 C1), from the decisions log and the data under `docs/data/`; stage 6
added on 2026-11-14 (D33 C1) stage 6b on 2026-11-15 (D37 C1) stage 7 the same day (D40 C1) stage 8 on 2026-11-16 (D42 C1) the reading of champion 8102 on 2026-11-24 (D45 C1) and the compiled life and stage 8b on 2026-11-25 (D58 C2); the rate of generalists corrected on 2026-11-26 from stage 8c (D63), and stage 8c and the reading of stage 8b's cells added the same day (D64). It adds no result; each number is from the entry named beside it.

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
| does it hold in worlds the cells never saw | Mostly where the world is like home; one evolved cell holds up in all six | D40 |
| does a generalist emerge when evolution is given several worlds | In 1 run of 5; that cell beats the best simple rule in 5 of 9 worlds | D42 |
| how the generalist does it | Two ways of moving in one network: it circles where its body gives no direction, and steers by its own shading where it does | D45 |
| can the searches run faster | Yes: the same model as compiled code, 11.7 times faster on a core; a run costs about 25 cents on a pod | D47–D49, D57 |
| is a generalist an accident of one run | No. At 400 generations 13 of 45 runs give one, about three in ten (stage 8b's 15 runs had suggested a half; stage 8c's 30 corrected it). At 800 generations, 3 of 5 | D58, D63 |
| what the generalists are | One kind of cell, found by five runs from five random beginnings: a circler where the body gives no direction, a steerer by its own shading where it does | D61 |

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

## 10. Worlds the cells never saw (stage 7; D40)

- **The design:** five cells, unchanged, in their home world and six others: a fixed mouth, a tighter economy,
  flickering clouds with and without the sweep, a spot circling the pool, and a cell that shades itself. In each world
  the simple rules were re-tuned over their parameter grids on separate starts, and the best one set the bar.
- **The share of the gap from sitting still to each world's best simple rule** (bold: the cell beats the rule):

  | world | design 16 | champion 3603 | champion 6301 | champion 6402 | champion 6405 |
  |---|---|---|---|---|---|
  | home | 0.97 | **1.16** | **1.16** | **1.26** | **1.21** |
  | fixed mouth | 0.83 | 0.93 | 0.93 | 1.00 | 0.97 |
  | tighter economy | 0.89 | **1.24** | 0.99 | **1.40** | **1.26** |
  | flicker | 0.22 | 0.29 | 0.36 | 0.95 | 0.63 |
  | sweep and flicker | 0.12 | 0.17 | 0.22 | 0.93 | 0.52 |
  | circling spot | 0.04 | 0.02 | 0.30 | 0.82 | 0.84 |
  | shaded cell | **1.04** | **1.05** | 0.87 | 0.81 | −0.04 |

- **At home every champion beats the rule again.** Away from home the four champions do the rule's job in 11 of 24
  cases and beat it in 4, three of them in the tighter economy.
- **The two lines fail in different places:** the hand-written line under clouds and the spot, the evolved cells when
  shaded and, for two of three, under clouds.
- **Champion 6402 closes at least 0.81 of the gap in every world.**

## 11. Evolution in several worlds at once (stage 8; D42)

- **The design:** stage 6b's runs from random genomes, with each generation's starts drawn from four worlds after the
  eased-in path: home, flickering clouds, the circling spot and the shaded cell. Five more worlds were held back. The
  test is stage 7's, in all nine, against each world's re-tuned best simple rule.
- **The criteria, set beforehand, are not met:** 1 of 5 champions does the rule's job in all four trained worlds (3
  were asked for), and 2 of 5 do it in at least three of the five held back.
- **The one generalist, champion 8102:** it closes at least 0.89 of the gap in all nine worlds, does the rule's job in
  eight, and beats the rule in five: home, the spot, the shaded cell, and two worlds it never met (the tighter economy
  and a slower spot). At home it is 0.017 below the home specialist.
- **The others are partial.** All five handle the shaded world and most handle home; two never find the spot, and
  those two are the worst elsewhere too.
- **Champion 6402, made at home only, does the rule's job in seven of the nine worlds.**

## 12. How the generalist does it (D45)

- **The probe:** champion 8102 on 60 fresh starts in each of its four trained worlds, beside champion 6402 and a
  stage 8 run that failed (8105). It explains a result and sets no criterion.
- **Translucent, it circles.** At home, under flickering clouds and under the spot it runs 82–95% of the day, turning
  about −0.08 rad a tick, as champion 6301 did. There it needs its ring's links (0.31–0.43 of fitness lost without
  them) and its core, and loses nothing when the direction across its body is taken away.
- **Shaded, it steers.** It runs 62% of the day and hardly turns (−0.011 rad a tick). There it loses 0.14 without the
  direction across its body, and nothing without its ring's links or the core's own loops.
- **Nothing switches between the two but the light.** The same network does both.
- **A cloud slows it and does not stop it.** Through a cloud's shadow its share of ticks moving falls from 0.98 to
  0.65; the hand-written line's champion (3603) falls from 1.00 to 0.00, every time.
- **Why the spot divides the runs:** a spot that crosses the pool has to be followed all day. The failed run rests
  most of the day (it runs 24% of it) and never became a circler.
- **Two of five predictions failed:** I expected the ring to matter in every world, and the generalist to ignore
  clouds.

## 13. A faster engine for the searches (the compiled life; D47–D49, D52, D54)

- **Why:** the simulation was NumPy on the CPU, a hundred small array operations a tick. A stage 8 run took 9 to 10
  hours on a 16-vCPU pod, most of it that per-tick overhead.
- **What:** one cell's life written as scalar code and compiled (Numba). The same model, operation for operation,
  with the reference's own noise, sky and light source. Only the library functions differ (`exp`, `log`, `sin`,
  `cos`), in a last bit now and then.
- **For the searches only.** Every test and reported number is still made by the reference.
- **The same model:** with both engines on the C library's functions, 24 whole lives are the reference's bit for bit.
- **The same outcomes, with one miss as I had written the criterion:** over 1,800 paired lives every cell-and-world
  pair's mean fitness is within 0.003, and the two engines rank a population alike (Spearman 0.977 and 0.991, against
  0.898 for the reference under two draws of luck). One pair's survival was 8 points apart where I had allowed 5:
  champion 6402 under the spot, whose lives part completely. On 600 more starts both engines had 152 lives survive,
  and the lives surviving in one engine only fell 82 each way. So the miss was the fall of parted lives; the
  criterion stays recorded as failed.
- **The speed:** 11.7 times faster on a core. A stage 8 generation takes 4.5 s on 8 processes on this machine and 2.3
  to 4.8 s on a 16-vCPU pod, where the reference took 83 to 111 s.
- **On a GPU** (the owner's laptop, an NVIDIA RTX 2000 Ada): the same model and the same outcomes, and too slow to
  help. The kernel is double precision, which that card does slowly: 75 whole lives take 36 to 40 s on it and 6 to 15 s
  on one of the laptop's CPU cores.

## 14. How reliably a generalist emerges (stage 8b; D55–D58)

- **The question:** stage 8 gave one generalist in five runs. An accident, a matter of time, or a rate?
- **The runs,** on the compiled life: stage 8's five runs carried on from generation 400 to 800, and ten fresh runs
  of stage 8's design at 400 generations. The test is stage 8's, on the reference, on fresh starts.
- **All three criteria hold, two of them exactly at their bar:**

  | criterion | result |
  |---|---|
  | at least 3 of the 5 carried-on runs are generalists at 800 generations | 3 (8102, 8103, 8104) |
  | at least 4 of the 5 are better at 800 generations than at 400 | 5, by +0.012 to +0.113 |
  | at least 5 of the 10 fresh runs give a generalist | 5 |

- **Time turned two runs into generalists.** At 400 generations runs 8103 and 8104 did the bar's job in two of their
  four worlds. At 800 they do it in all nine worlds and beat the bar in eight.
- **Two runs improved and did not arrive:** 8101 and 8105 still fail under flicker and the spot at 800 generations.
- **At 400 generations, from random genomes:** 6 generalists in 15 runs, 40% (95% interval 20% to 64%).
- **Every generalist travels:** each does the bar's job in 4 or 5 of the 5 held-back worlds and beats the bar in 5 to
  8 of the nine worlds.
- **Generality costs little at home:** five of the eight generalists score 0.629 to 0.637 there, the home specialist
  0.639, the bar 0.543.
- **The spot and the flickering clouds divide the runs:** every cell that is not a generalist fails under one or both.
- **The third criterion's bar was a half,** which I had wrongly called stage 8's share (D59). At stage 8's own, three
  in five, it would have needed 6 of the 10 and would not have held.
- **Two of six predictions failed:** I expected fewer than three generalists at 800 generations, and one to three
  among the ten fresh runs.

## 15. What the generalists are (D61)

- **The probe:** nine cells on 60 fresh starts in each trained world: the five strongest generalists (runs 8102, 8103
  and 8104 at 800 generations; fresh runs 8202 and 8210), runs 8103 and 8104 as they stood at 400 generations, and
  runs 8101 and 8105 at 800, which never survive the spot.
- **Five runs, from five random beginnings, found the same kind of cell** that champion 8102 is (§12). Where the body
  gives no direction it runs 93–98% of the day turning steadily, and needs its ring's links (0.25–0.46 of fitness lost
  without them). Where it shades itself it steers by the shading (0.12–0.15 lost without the direction across the
  body) and needs no ring. One of the five circles the other way.
- **Time did not give runs 8103 and 8104 the mechanism.** They circled already at 400 generations. At 800 their running
  is hardly ever broken: fresh starts of running a life at home fell from 600 to 11 and from 84 to 16. With that they
  follow the spot and outlast the clouds; that the one causes the other is not shown.
- **The runs that never find the spot are the other kind:** they run a third of the day and do not circle, and starve
  under the spot.
- **One of six predictions failed:** I expected 8103 and 8104 not to have been circlers at 400 generations.

## 16. The rate, with thirty more runs (stage 8c; D62, D63)

- **The question:** stage 8b's 15 runs left the rate of generalists at 400 generations anywhere from 20% to 64%.
- **The runs:** thirty more fresh runs of stage 8's design, on the compiled life, on six pods, for $6.44. The test is
  stage 8's, on the reference, on fresh starts.
- **Both criteria fail:** 7 of the 30 give a generalist, where 15 (a half) and 18 (three in five) were asked for.
- **The rate at 400 generations, over all 45 runs made:** 13, which is 29% (95% interval 18% to 43%). About three runs
  in ten, not the half that stage 8b's runs had suggested.
- **What the thirty made:** 7 generalists; 8 that do the bar's job in three of the four trained worlds and fall short
  only under the flickering clouds (0.83 to 0.89 of the gap, where 0.9 is the line); 2 that cope at home and when
  shaded; 10 only when shaded; 3 still cells.
- **The line under flicker is thin.** The seven close 0.90 to 0.97 of the gap there and the eight 0.83 to 0.89. Counted
  after the fact, about half of all 45 runs do the bar's job under the spot (22).
- **Every generalist travels** to 4 or 5 of the 5 held-back worlds.
- **The runs' own validation lumped the fifteen together** (thirteen surviving everywhere, two nearly); the test
  divides them seven and eight.
- **Two of seven predictions failed:** I expected 8 to 16 generalists and a rate over the 45 runs between 30% and 50%.

## What this does and does not show

- **Shown:** in this world, a cell of interacting parts does better than every simple rule tried, on fresh starts: in
  two of three runs from a designed start, and in three of eight from random genomes. From random genomes a cell that
  does the best simple rule's job emerges reliably (four of five at 400 generations).
- **Shown, as a limit:** cells made in one world mostly beat the best simple rule only there; the simple rules, with
  one parameter re-tuned per world, hold up across worlds better (stage 7).
- **Shown:** evolved in four worlds at once, a cell that copes with all of them emerges in about three runs of ten at
  400 generations: 13 of 45 (18% to 43%; stages 8, 8b and 8c, D63). At 800 generations, 3 of 5 (stage 8b). Each such
  cell also copes with worlds it never met, and beats each world's re-tuned best simple rule in most of the nine
  worlds.
  *Corrected 2026-11-26:* after stage 8b this said "about half the runs", from 6 of 15. Stage 8c's thirty more runs
  gave 7.
- **Not shown:**
  - the rate at 800 generations beyond five runs, two of whose criteria held by one run;
  - that a cell beating B8 emerges from nothing in most runs at home alone: 2 of 5 did at 400 generations, where the
    criterion asked for 3; and the sensor and the eased-in path were designed by hand;
  - anything beyond one spoke mode (fourier1) and one sensor;
  - that no simple rule could sit higher than the bars. They are the best of those tried.
- **Shown:** the generalists from five runs are one kind of cell: a circler where the body gives no direction and a
  steerer by its own shading where it does (§15).
- **Open:** how the champions' fresh runs come to begin aimed at the mouth without reading the direction across the
  body is answered for the searched cell (§9); how the evolved cells' circling is biased toward the light is not
  (D36 B.2, D45 B.4, D61 B.5). Whether more time carries stage 8c's near-misses over, as it carried runs 8103 and 8104,
  is being tested (D64).

## Cost and conduct

- **RunPod,** stages 4 to 8: about $70 in all (stage 4b $5.90, 4c $3.90, 4d $2.80, 5c $9.40, 6 $11.40, 6b $18.30, 8 $18), each launch confirmed by
  the owner first. On the compiled life: stage 8b $3.74 for fifteen runs and stage 8c $6.44 for thirty, 21 to 25
  cents a run, where a stage 8 run cost about $3.60.
- **This machine** ran the checks, probes, hand-writing and tests as one process, after an all-core run tripped the
  CPU's thermal limit (D23).
- **Each stage** had a preregistration with predictions before it ran. The predictions that failed are recorded as
  failed in their documents; twice I predicted that no champion would beat B8, and twice one did.
- **Errors of mine, disclosed where they happened:** a campaign bug that stopped a pull loop (D18); probes that bypassed
  their log and a calculator with a wrong constant (D27); a scoring summary that misread a column (D29); a test that
  overwrote one champion's rows with another's (D33); a tolerance on survival set as if paired lives stayed paired
  (D48); a set-up script written for Linux when the owner's laptop was Windows, unasked (D51); a test that skipped on
  any error and so hid a real one (D52); a criterion's bar described as stage 8's share when it was a half (D59); a
  rate called "about half" from fifteen runs, which thirty more brought to three in ten (D63).

## Next

The owner on D63 (D64): stage 8c's eight near-misses carried on to 800 generations, with runs that do not follow the
spot as a control; the fifteen that follow the spot read beside each other; and a single-precision engine for the
GPU, with its own plan and check.
