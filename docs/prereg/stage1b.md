# Preregistration: stage 1b — what the evolved cells' parts compute

**Written:** 2026-11-02, before any of it is built (`docs/decisions.md` D7 D2, D8). Stage 1's test found that
zeroing the core, the core's recurrence or the ring's links breaks every confirmatory champion. Zeroing a part
removes two things at once: what it computes from moment to moment, and the steady drive it gives the neurons it
feeds. A wall neuron that received a constant push from the core has its operating point shifted when the core is
cut, whatever the core was computing. Stage 1b separates the two. It holds each part's input at its average instead
of zeroing it. Nothing is evolved; the champions are stage 1's.

## 1. The method: holding a pathway at its average

Three pathways, each a block of the weight matrix and the input it carries to the neurons it feeds:

| pathway | the weights | what receives its input |
|---|---|---|
| the core's drive to the wall | core → wall, `W[wall, core]` | each wall neuron |
| the core's recurrence | core → core, `W[core, core]`, self links included | each core neuron |
| the ring's links | each wall neuron's two neighbours, `W[i, i±1]` | each wall neuron |

**Held at its average** means the pathway's weights are set to zero and each receiving neuron gets instead a
constant input. That constant is the pathway's mean input to that neuron in the intact champion: Σⱼ W[i, j] oⱼ,
averaged over the champion's living ticks on stage 1's 24 validation starts (seed 4, noise key (0, start)). Neuroscience
calls this mean ablation. The neuron keeps its average operating point and loses only the pathway's fluctuations.
The averages come from the validation starts, so the test starts are not used to set them.

## 2. The champions and the test

- **The champions:** stage 1's six confirmatory champions, which carry the verdicts, and its two pilot champions,
  which are reported.
- **The test:** stage 1's 100 test starts (seed 5), with the same noise for every version on a start.
- **The versions:** each champion is run intact, with each of the three pathways held at its average, and with each
  zeroed again as in stage 1.
- **A check:** the intact and zeroed versions must reproduce stage 1's test rows bit for bit. It is the same code
  path on the same platform.

## 3. The measures and criteria

- **The drop:** the intact champion's fitness minus the held version's, per start, averaged. Its 95% bootstrap
  interval over the starts uses 10,000 resamples from stream `bootstrap` at seed 7.
- **δ = 0.007**, as in stage 1.
- **Held at its average breaks a champion** if the drop's lower bound is above δ.
- **A part computes, for a champion,** if holding it at its average breaks the champion: its moment-to-moment
  activity matters, not only its average.
- **A part supplies steady drive only** if zeroing it broke the champion in stage 1 and holding it at its average
  does not.
- **A part computes in a spoke mode** if holding it at its average breaks at least 2 of the mode's 3 champions.
- **Reported beside the criteria:**
  - the share of the zeroed drop that holding at the average recovers;
  - each held version's beating at night, effort per unit light, survival, and time to reach the soak region.

## 4. Predictions (written before the build)

1. **The check holds:** the intact and zeroed versions reproduce stage 1's test bit for bit.
2. **The core's drive to the wall computes in both modes.** Holding it at its average breaks at least 2 of 3
   champions in each mode. The core is where the whole wall's light is summed, so it is the natural place for the
   day-and-night switch the champions show.
3. **Its beating at night rises** above the intact champion's when the core's drive is held at its average: the wall
   no longer hears that it is night.
4. **The core's recurrence computes in both modes.** Holding it at its average breaks at least 2 of 3 champions in
   each mode. A switch that holds its state needs recurrence.
5. **The ring's links supply steady drive only.** Holding them at their average breaks no champion. Zeroing them
   cost only 0.012–0.062 in stage 1, and a neighbour's signal changes slowly as the cell turns.

## 5. What follows

The result is read into the next decisions entry and into stage 3's design.
- **If the core and its recurrence compute:** the evolved cells use their core's dynamics, not only its drive.
  Stage 3 keeps the whole network, and its removals hold parts at their average from the start.
- **If neither computes:** the zeroed removals of stage 1 measured steady drive, and D7's reading of Q2 is corrected
  by a dated note.

## 6. What would change this document

Nothing after the run. Clarifications during the build are recorded here as dated notes, before the run.
