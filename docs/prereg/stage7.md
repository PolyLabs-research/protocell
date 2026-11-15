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
