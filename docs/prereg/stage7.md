# Preregistration: stage 7 — the cells in worlds they never saw

**Written:** 2026-11-15, after stage 6b (`docs/decisions.md` D37), before any run. The owner on D37 C: "Go with 1 and 2
for now" (D38).

## 1. The question

Every champion so far was evolved, searched or written in one world, stage 4a's, and tested there. The plan asked of
stage 1 whether an evolved cell beats the simple rules "including on layouts it never saw". Stage 7 asks it now:

- **Do the cells still do the best simple rule's job in worlds they never met?**
- **Do they still beat it?**
- **Does the cell that came from a hand-written design hold up better or worse than the cells evolved from nothing?**

A cell that beats the best simple rule only at home is a narrower result than one that does it elsewhere too.

## 2. The cells

Five, each unchanged: design 16 (written by hand); stage 5c's champion 3603 (a search from design 16); and three evolved
from random genomes: stage 6's champion 6301 and stage 6b's 6402 and 6405, the three that beat B8 at home.

## 3. The worlds

Stage 3's translucent pool, with stage 5's sensor on the cells, and:

| world | what differs from home |
|---|---|
| home | nothing: stage 4a's world, the mouth sweeping, gain 0.55 of the cave's |
| fixed mouth | the mouth does not sweep |
| tighter | gain 0.45 |
| flicker | the mouth fixed; clouds, spells of sun (mean 2 minutes) and of shade at 0.3 of the light (mean 1 minute) |
| sweep and flicker | home with those clouds |
| spot | no mouth: a spot circling the pool's centre at 2,500 R every 2 hours; gain 0.45 |
| shaded | home, with the cell shading itself as in the cave (the far side gets 0.3 of the light) |

The clouds and the spot are stage 4's probe's; none of the six was used to make or choose any cell.

## 4. The bar in each world

The simple rules run in each world over their parameter grids, as in stage 4's probe: B2r (5 gains), B5 (5 memories),
B6 (4 timings), B8 (5 memories). The bar is the rule and parameter with the best mean fitness on starts 1–50. So each
world has its own best simple rule, tuned for it, where the cells are not.

## 5. The measures

On starts 51–150 at seed 42, shared noise and sky, bootstrap at seed 43:
- **It does the bar's job** if it closes at least 0.9 of the gap from sitting still to the bar (stage 4d's measure).
- **It beats the bar** if its fitness less the bar's has its 95% interval above 0.
- Reported: for each cell, in how many of the six unseen worlds it does each.

There is no pass or fail for the stage; the counts are the result.

## 6. Predictions (written before any run)

1. **At home, all four champions beat the bar again.**
2. **With the mouth fixed, and with the tighter economy, every champion still does the bar's job.** The geometry is
   the one they know.
3. **Under the circling spot, no cell does the bar's job.** The light moves across the pool every two hours, and
   nothing in these cells was shaped for that.
4. **Under flickering clouds no champion beats the bar, and at most half of the champion-and-world pairs do its job.**
   The searched cell starts runs on a rise and the evolved cell speeds up on any change (D36); a cloud passing is both.
5. **As a shaded cell, no champion does the bar's job.** The sensor's readings change, and the reflex, which uses the
   shading, becomes a strong simple rule.
6. **The searched cell holds up in at least as many unseen worlds as the best evolved cell.**

My predictions have failed about as often as they have held in stages 5c to 6b.

## 7. Compute

Here, one process, started detached; about 3 to 4 hours. Nothing on RunPod.

## 8. What would change this document

The outcome, after the run.

**The outcome (2026-11-15; `docs/decisions.md` D40).**

The run: here, one process, 2.8 hours, at code `cfb0c7a`, from a clean tree with warnings as errors; starts 51–150 at
seed 42. Data in `docs/data/stage7/`.

**Each cell's share of the gap from sitting still to the world's best simple rule** (1.00 is level with the rule; bold
where the cell beats the rule, its interval above 0):

| world | the best simple rule there | design 16 | champion 3603 | champion 6301 | champion 6402 | champion 6405 |
|---|---|---|---|---|---|---|
| home | B8 (tau 3), 0.540 | 0.97 | **1.16** | **1.16** | **1.26** | **1.21** |
| fixed mouth | B5 (tau 30), 0.655 | 0.83 | 0.93 | 0.93 | 1.00 | 0.97 |
| tighter | B8 (tau 3), 0.411 | 0.89 | **1.24** | 0.99 | **1.40** | **1.26** |
| flicker | B8 (tau 10), 0.562 | 0.22 | 0.29 | 0.36 | 0.95 | 0.63 |
| sweep and flicker | B8 (tau 10), 0.495 | 0.12 | 0.17 | 0.22 | 0.93 | 0.52 |
| spot | B6 (cycle 20, run 10), 0.504 | 0.04 | 0.02 | 0.30 | 0.82 | 0.84 |
| shaded | B6 (cycle 20, run 10), 0.591 | **1.04** | **1.05** | 0.87 | 0.81 | −0.04 |

**In the six unseen worlds:**

| cell | does the rule's job (0.9 or more) | beats the rule |
|---|---|---|
| design 16 (written by hand) | 1 | 1 |
| champion 3603 (a search from it) | 3 | 2 |
| champion 6301 (evolved) | 2 | 0 |
| champion 6402 (evolved) | 4 | 1 |
| champion 6405 (evolved) | 2 | 1 |

- **At home every champion beats the rule again,** on new starts and against a rule re-tuned there.
- **Where the geometry is the home's** (a fixed mouth, a tighter economy) every champion does the rule's job, and three
  of four beat it in the tighter economy. With the mouth fixed no cell beats B5, which sits 0.036 below the ceiling.
- **Flickering clouds break the hand-written line and stage 6's cell:** design 16, champion 3603 and champion 6301
  close 0.12 to 0.36 of the gap and mostly starve (3% to 33% survive). Champion 6402 holds at 0.93 to 0.95.
- **Under the circling spot** the hand-written line does nothing (0% survive); stage 6b's two champions close 0.82 and
  0.84, with a third of their starts surviving.
- **As shaded cells** the hand-written line beats the rule and survives every start; the evolved cells do not, and
  champion 6405 starves on every start.
- **Champion 6402 closes at least 0.81 of the gap in every world.** No other cell is above 0.5 in all of them.

**The predictions:**

| prediction | outcome |
|---|---|
| 1. at home, all four champions beat the bar again | ✓ |
| 2. fixed mouth and tighter: every champion does the bar's job | ✓ |
| 3. under the spot, no cell does the bar's job | ✓ (the best close 0.82 and 0.84) |
| 4. under flicker no champion beats the bar, and at most half the pairs do its job | ✓ (2 of 8 pairs, both champion 6402) |
| 5. shaded: no champion does the bar's job | ✗: champion 3603 does, and beats it |
| 6. the searched cell holds up in at least as many unseen worlds as the best evolved cell | ✗: 3 against champion 6402's 4 |
