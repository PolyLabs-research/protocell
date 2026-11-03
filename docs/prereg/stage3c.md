# Preregistration draft: stage 3c — the goggles: how a cell with no front finds the light

**Written:** 2026-11-03, after stage 3c's design probe (`docs/decisions.md` D13), before anything is built.

D11 found that uniform champion 2203 reaches the light and stays (fitness 0.397 at stage 3b's test, above the reflex).
A uniform cell has no front: its core sees only the wall's total light and drives every wall node alike. I had
predicted such a cell could not hold a course. The owner asked for a world that exposes how it manages (D12).

Stage 3c evolves nothing. It runs fixed cells, the champion among them, in worlds built so that the candidate
mechanisms predict different behaviour, with a simple rule for each mechanism beside them as a positive control. The
open points for the owner are in §10.

## 1. What the probe found

Stage 3c's design probe (`experiments/stage3c_probe.py`; `docs/data/stage3c/probe/`): stage 3's translucent world,
fresh starts 1–100 at seed 13, and the champion's network held in place and fed controlled light.

**Its runs start toward the light.** The champion alternates runs and pauses. A *run* is at least 3 ticks in which its
beating pulls one way; its direction is read at its third tick. The runs' direction against the direction to the
mouth, by the light where they began:

| light where the run began | runs | mean cosine to the mouth (SE) |
|---|---|---|
| night, below 0.01 | 42,430 | −0.004 (0.003) |
| 0.01–0.1 | 7,024 | +0.031 (0.008) |
| 0.1–0.3 | 2,332 | +0.206 (0.014) |
| 0.3–1 | 1,674 | +0.483 (0.014) |
| 1–3 | 3,573 | +0.708 (0.007) |

**Held in place, its network is a relaxation oscillator.** In even light below 3 it is quiet, then three or four
neighbouring wall nodes beat together for 35–49 s, then quiet again: 27–37 runs an hour, more in brighter light. At
light 3–4 the patch beats without a break. From 5 every node beats, the pulls cancel, and it parks.

**Fed light slightly brighter on one side, its runs start toward that side.** The light at node i was L(1 + ε cos(θᵢ −
φ)). In the pool ε runs from 0.0002 at the far side to 0.0017 near the mouth. The per-tick signal is that pattern's
amplitude Lε against the noise of the wall's first Fourier mode.

| light L | ε = 0 | 0.0005 | 0.001 | 0.002 | 0.005 | 0.01 |
|---|---|---|---|---|---|---|
| 0.3 | −0.03 | **+0.37** (signal 0.13 of the noise) | +0.62 (0.27) | +0.87 | +0.95 | +0.98 |
| 1 | +0.00 | +0.77 (0.45) | +0.94 | +0.98 | +0.99 | +1.00 |
| 2 | −0.01 | +0.94 (0.89) | +0.98 | +0.99 | +1.00 | +1.00 |

(mean cosine between a run's direction at its third tick and the brighter side; 769–1,067 runs per condition, from
8 replicates, each with its own direction)

These biases match a reader that sums the wall's first mode over 7–21 ticks. At noon the per-tick signal reaches 0.13
of the noise on 27% of the probe's starts; by stage 3a's T2 criterion the direction is readable at once on 2% of
them (D13 C2).

**During runs the body spins and the beating creeps back.** The cilium angle (−10°) turns the body clockwise at −0.037
rad/s. The beating patch moves anticlockwise around the wall at +0.024 rad/s, because the ring's link from the
clockwise neighbour is stronger (7.44 against 6.35). The run turns at −0.013 rad/s, a third of the spin.

**The fourier1 champion (3202) works another way.** Held in place, it is a switch by the light's level. It is idle
below 0.03, swims without a break from 0.1 to 1, and parks from 2. It swims in tight circles, turning at −0.17 rad/s,
a radius of about 45 R. Few of its runs begin in the light where the champion aims best, and their aim is mixed
(mean cosine −0.36 to +0.17 by band).

**An exploratory peek, disclosed.** Before writing the probe I ran cells with their senses changed, and with single
parameters changed, in scratch code outside the repository. These runs used stage 3a's report starts 51–100 at seed 8,
so stage 3c's test starts are untouched. They are not results. They are disclosed because they shape §8.

| cell | senses as they are | direction removed | direction mirrored | direction ×10 | sensor noise off |
|---|---|---|---|---|---|
| uniform 2203 | 0.361 | 0.189 | 0.141 | 0.555 | 0.634 |
| fourier1 3202 | 0.458 | 0.462 | 0.455 | 0.487 | 0.471 |
| B5, run and wait | 0.709 | 0.709 | 0.709 | 0.709 | 0.693 |
| B6, read and run (§5) | 0.463 | 0.197 | 0.141 | 0.702 | — |
| B7, run anywhere (§5) | 0.205 | 0.205 | 0.205 | 0.205 | — |

The champion with single parameters changed: intact 0.361; no body spin (α = 0) 0.326; the ring made symmetric (no
creep) 0.300; both 0.399.

## 2. The hypothesis and its rivals

**H, the ring reads the direction at each run's start.**
1. **Release.** A slow loop through the core releases the wall about every 2 minutes.
2. **Placement.** The ring's strong links between neighbours, with the core's even feedback, let one patch of
   neighbours win. The patch forms where the light is brightest: while the wall is held, the slightly brighter side
   gets ahead, and the ring amplifies its lead. The patch pulls the cell toward its own side.
3. **Course.** The patch's creep cancels part of the body's spin, so a run bends less. The rotational noise bends it
   more, and the next run reads again. Many weakly aimed runs add up to an approach.
4. **Stopping.** From light about 5, every node is driven, the pulls cancel, and the cell parks where it is bright.

**The rivals:**
- **T, comparing over time** (B5's way): a run is started or lengthened when the light rises.
- **K, kinesis and a trap:** runs go anywhere, and the cell stops where it is bright.

T and K do not use the light's direction across the body. H does.

## 3. The worlds

### 3.1 The goggles
Stage 3's translucent pool, unchanged (`docs/prereg/stage3.md` §1), except for what each node senses. With Ī the
wall's mean of the true light, node i senses Ī + k (Iᵢ − Ī) plus its noise. The energy uses the true light.

| world | k | what it does |
|---|---|---|
| G1 | 1 | the pool as it is |
| G0, frosted | 0 | every node senses the wall's mean: the direction is gone; the level and its change over time are kept |
| G−1, mirrored | −1 | the pattern across the body reversed: the brighter side is sensed where the dimmer side is |
| G10, magnified | 10 | the pattern ten times stronger; the noise unchanged |
| Gq, quiet | 1 | the sensor noise off |

Each keeps the wall's mean exactly. So a cell that reads only the level or its change over time senses the same in
G0, G−1 and G10 as in G1; only a cell that reads the direction across its body is changed.

### 3.2 The flat pool
The light is the same everywhere and at every node, so where the cell is does not matter. It is held in place, its
heading fixed. It settles for 2 hours at a level L, then the light steps to 1.25 L (up) or 0.8 L (down) and holds
for 30 minutes.
- **L:** 0.3 and 1, inside every cell's working range.
- **16 replicates per cell, level and step:** the step's time is staggered by 7 s per replicate, so B6's and B7's
  100-s cycles meet it at every phase. Each replicate has its own sensor noise (stream `tether`).
- **The pull:** the speed the cell's beating would give it, v_max (π/N)|m₁|.

A cell that compares over time changes its pull right after a step, and the change fades as it adapts. B5 runs
throughout the first two minutes after a step up and waits after a step down. A cell that follows the level shows
its change late, after its lag, and holds it. So the measure compares the early change with the late one:
D_early is the pull in the 2 minutes after the step less the pull in the 10 minutes before it. D_late is the same for
minutes 20–30 after. The transient is T = |D_early| − |D_late|.

## 4. The cells

- **The champion:** uniform 2203 (`docs/data/stage3b/confirm/uniform-2203/champion.npy`).
- **The other working champion:** fourier1 3202, as a comparison.
- **B5, run and wait** (τ = 30 s, stage 3a's choice): the control for T.
- **B6, read and run (new):** the control for H. **B7, run anywhere (new):** the control for K. (§5)
- **B0, still:** the floor, in G1 only.
- **The lesions**, the champion with one part changed, without re-evolving:
  - L1: the cilium angle set to 0 (no spin; the creep alone bends a run anticlockwise).
  - L2: the ring made symmetric, both neighbour links at their mean (no creep; the spin alone bends a run).
  - L3: both.

## 5. The two new controls

Both are the champion's timing as the probe measured it, with one rule each. Both have α = 0.

- **In the dark** (the wall's mean sensed light below 0.01), they rest, as B2r and B5 do.
- **In bright light** (at least 4.5), they keep still. The tethered champion still runs at 4 and is parked at 5.
- **Otherwise they cycle every 100 s** from their first tick: idle for 64 s, then a run of 36 s. The tethered
  champion's runs last 35–36 s at light 0.3–1, 32–37 an hour.
  - **During a run**, the half of the wall facing a direction ψ (in the body's frame) beats fully, the rest not at
    all.
  - **B6** takes ψ from its sensed light: the direction of the wall's first Fourier mode summed over the idle phase.
  - **B7** draws ψ uniformly from stream `walk`, keyed by cell and start.

B6 is the simple rule built on H: periodic runs, each aimed by reading the wall. B7 is the same without the reading,
which is K.

## 6. Starts, seeds, sizes

- **Starts:** 1–100 at seed 14, fresh; every cell on every start, with shared noise.
- **Bootstrap:** seed 15, 10,000 resamples of starts.
- **Streams:** `walk` (B7) and `tether` (the flat pool's noise), both at seed 14.

## 7. The measures and the criteria

**Measures, for each cell in each world:**
- **Fitness and survival.** Differences are paired start by start, with 95% bootstrap intervals over starts.
- **The onset bias:** the mean cosine to the mouth of the runs beginning in light 0.3–3, with an interval from
  resampling starts. 0.3–3 is where the probe's champion aimed best; together these bands gave 5,247 of its runs.
- **During runs:** the body's spin, the beating's creep and the turning of the pull (the lesions).
- **The flat pool:** D_early, D_late and T for each cell, level and step, with intervals over replicates.

**Criteria:**
- **C1, it reads the direction.** The onset bias is above 0 in G1 (interval above 0). In G0 its mean lies within
  ±0.1. The fitness drop from G1 to G0 is above 0 (interval above 0).
- **C2, it follows what it reads.** The onset bias is below 0 in G−1 (interval below 0). It is higher in G10 than in
  G1 (interval of the difference above 0).
- **C3, the worlds separate the mechanisms.** B6 meets C1 and C2. B5 and B7 change by less than 0.01 in mean fitness
  in G0, G−1 and G10.
- **C4, the creep holds the course.** L1 and L2 each lower the champion's fitness (interval of the drop above 0). L3
  does not (interval of the drop includes 0 or lies below it).
- **C5, comparing over time.** A cell compares over time if, at some level, T exceeds 1 R/s with its interval above
  0, after the step up and after the step down. B5 must meet C5 at both levels, or the flat pool does not work.

H's reading (parts 1, 2 and 4) is confirmed if C1 and C2 hold for the champion and C3 holds. Its course (part 3) is
confirmed if C4 holds.

## 8. Predictions (written before the build)

The champion in the goggles:
1. **G0:** its onset bias's mean falls to within ±0.1 (from about 0.6 in G1), and its fitness drops by more than
   0.10.
2. **G−1:** its onset bias falls below −0.3, and its fitness drops by more than 0.15. It flees the light.
3. **G10:** its onset bias rises above 0.85, and its fitness rises by more than 0.10.
4. **Gq:** its fitness rises by more than 0.15. Its reading is limited by the noise.

The controls:

5. **B6** drops by more than 0.15 in G0 and G−1 and rises by more than 0.15 in G10.
6. **B5 and B7** change by less than 0.01 in G0, G−1 and G10.
7. **F3202** changes by less than 0.05 in each goggles world. It does not read the direction across its body.
8. **B7 scores within 0.02 of the still cell (B0).** Running anywhere and stopping where it is bright does not find
   the light in this world, so K cannot explain the champion.

The lesions:

9. **L1 and L2 each lower the champion's fitness, and L3 does not** (C4).
   - During runs, L1 turns at about +0.024 rad/s, L2 at about −0.037, and L3 at about 0.

The flat pool:

10. **B5 compares over time** (C5): T above 2 R/s in all four cases.
11. **The champion, F3202, B6 and B7 do not** (T below 0.5 R/s in every case).
    - For F3202 this is my guess from the probe: its states follow the level.
    - If F3202 does compare over time, D11's reading of stage 3b stands for it.

The simple rule:

12. **B6 beats the champion in G1** by more than 0.05, **and falls below B5.**

## 9. Decision table

| result | what follows |
|---|---|
| C3 or B5's C5 fails | the worlds or the controls are wrong: fixed, with a dated note, before the champions are read |
| C1, C2 and C3 hold | H's reading confirmed: the cell with no front reads the light's direction across its body at each run's start (D11 B.4 answered); stage 3a's T2 correction (`stage3.md` §12) stands |
| C1 holds, C2 does not | it uses the direction, but not as H says; its runs examined in the goggles worlds |
| C1 fails | H is rejected; the probe's onset bias needs another explanation, examined before anything else |
| C4 holds | the creep's role confirmed |
| C5 fails for both champions | D11's reading B.1 ("comparing over time evolved only sometimes and partly") corrected by a dated note: neither working champion compares over time |
| C5 holds for a champion | D11's reading stands for it |

None of these changes stage 3b's measured numbers, only what they were taken to mean.

## 10. Open for the owner

1. **The worlds:** the goggles and the flat pool (recommended). The alternative is physical worlds, such as a pool lit
   evenly with light changing in time, or a sharp-edged bright patch. Those mix the cues that the goggles separate.
2. **The controls B6 and B7**, timed from the probe as in §5 (recommended).
3. **The lesions L1–L3** (recommended).
4. **Where it runs:** this machine, about 10 minutes (recommended). No cloud.

## 11. Compute

About 10 minutes on this machine:
- **The goggles and the lesions:** 5 cells in 5 worlds, B0, and 3 lesions, each on 100 starts.
- **The flat pool:** 320 tethered runs of 2.5 hours.

## 12. What would be built

- **A setting for the senses** in `protocell/config.py`, k, default 1. In `protocell/sim.py` it is applied to the light
  before the sensor noise and skipped when k is 1, so every earlier run is the same bits (tested against stage 0's
  pinned hashes).
- **B6 and B7** as controllers (stream `walk`).
- **The runner** `experiments/stage3c.py`, writing `docs/data/stage3c/test/`. It reuses the probe's observer and its
  tethered cell, generalised to any controller.
- **A per-cell senses option in the replay** (`tools/replay.py`), so the goggles can be watched.
- **Tests for each.**

## 13. What would change this document

The owner's answers, as dated notes before the build. After the run, nothing but the record that it ran.
