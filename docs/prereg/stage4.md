# Preregistration draft: stage 4a — a world with room above every simple rule, checked

**Written:** 2026-11-03, after stage 4's two design probes (`docs/decisions.md` D16), before anything is built.

In every world so far a simple rule sat within 2–3% of the ceiling (D6, D11), so interacting parts could not show
that they do better than a simple mechanism. Stage 4's probes found why: the reserve stops at full, and in the cave's
economy a few hours of good light fill it. When light is worth more, room opens above every simple rule (D16).

Stage 4a builds and checks such a world, as stage 3a checked the translucent one. Nothing is evolved. Evolution in it
is stage 4b, preregistered after 4a's checks pass. Every number below has its reason. The open points for the owner
are in §10.

## 1. What the probes found

All on fresh starts at seed 16, each simple rule tuned on starts 1–50 and reported on 51–100. The ceiling is a still
cell put at the brightest point every tick: no cell can get more light, and it pays nothing to move.

| world | headroom over the best simple rule | share of the room between B0 and the ceiling |
|---|---|---|
| stage 3's translucent pool | +0.020 | 4% |
| with clouds, or the mouth sweeping, or a circling spot | +0.017 to +0.065 | 4–13% |
| **the sweep, photosynthesis at 0.55 of the cave's** | **+0.148 (0.114, 0.186)** | **28%** |
| fast clouds, 0.55 | +0.134 (0.090, 0.184) | 26% |
| a spot circling every 2 hours, 0.45 | +0.148 (0.131, 0.165) | 29% |

A check between the probes found B5 at a full reserve for 68% of its daylight ticks, with the cave's gain.

## 2. The world (recommended; §10 1 has the alternatives)

- **Stage 3's translucent pool** (`docs/prereg/stage3.md` §1): the cave's day, starts with a random phase and the
  matched reserve, lifetimes to the second sunrise, the cell translucent, the falloff 600 R, damage off, the same noise.
- **The mouth sweeps** along the pool's edge through the day. It moves from 60° east of south at sunrise to 60° west
  at sunset, as the cave's sweep configuration (`docs/prereg/cave.md` §3). The light moves, as the plan's stage 4 asks.
- **Photosynthesis at 0.55 of the cave's gain:** η = 3.3/60,000 a tick instead of 6/60,000. The start reserve's rule
  follows the new gain.
  - In the second probe, 0.55 was the mildest gain at which the best simple rule left over a quarter of the room in
    this world.
  - At 0.45 it left half, but the best rules survived only 40% of starts. So little survival would make the test about
    dying rather than about doing well.

## 3. The baselines and the bar

- **B0, still,** and **B7, run anywhere** (stage 3c's §5).
- **The ceiling:** the still cell at the brightest point every tick (the mouth's place, one radius in).
- **The simple rules,** each with its parameter chosen on starts 1–50 by mean fitness and reported on starts 51–100,
  with the probes' grids:
  - B2r, the reflex: k in {1, 3, 10, 30, 100}.
  - B5, run and wait: τ in {3, 10, 30, 100, 300} s.
  - B6, read and run: (cycle, run) in {(20, 10), (50, 18), (100, 36), (200, 72)} s.
  - B8, B5's trigger with B6's aim: τ in the same grid, the aim averaged over 10 s.
- **The bar:** the best of B2r, B5, B6 and B8 by mean fitness on starts 51–100.
- **Reported beside them:**
  - B6 with perfect reading: the direction magnified 10,000 times and the sensor noise off, with B6's grid.
  - The stage 3b champions, uniform 2203 and fourier1 3202, as they are.

## 4. Starts, seeds, sizes

- **Starts:** 1–100 at seed 18, fresh.
- **Noise:** every cell on a start shares the same noise.
- **Bootstrap:** seed 19, 10,000 resamples of starts.
- **Random genomes:** 1,000 per spoke mode on starts 51–70, as stage 3a's T6.

## 5. The checks

- **U1, sitting fails and the best place pays.** B0 survives on at most 10% of starts, and the ceiling on at least 90%.
- **U2, real room.**
  - The ceiling exceeds the bar by at least 0.10, start by start on starts 51–100, with the 95% interval's lower bound
    above 0.05.
  - The bar leaves at least a fifth of the room between B0 and the ceiling.
- **U3, the room is about information.** B6 with perfect reading recovers at least half of U2's headroom. Better
  information, which a cell can gather, is then worth most of the room.
- **U4, random wiring rarely works.** Under 5% of random genomes match the bar's survival.
- **U5, determinism,** as stage 3a's T7.

## 6. Predictions (written before the build)

1. **U1–U5 pass.**
2. **The bar is B5 or B8,** with fitness 0.50–0.58.
3. **The headroom is 0.12–0.18,** 25–33% of the room.
4. **B6 with perfect reading recovers 70–85%** of the headroom.
5. **Both stage 3b champions score below 0.40.** They beat for much of the day and spend what this economy cannot spare
   (D11, D14).
6. **No random genome matches the bar's survival,** and the best scores below 0.25.

## 7. Decision table

| result | what follows |
|---|---|
| U1–U5 pass | stage 4b's preregistration: evolution against the bar, both spoke modes, on RunPod with the cost confirmed |
| U2 fails | the gain lowered one step (0.45), with the reason, and the checks again |
| U1 fails because the ceiling dies | the gain raised one step (0.65) |
| U3 fails | recorded: the room is in timing rather than information; the owner's call before stage 4b |
| U4 fails | the task made harder |
| U5 fails | fixed before anything else |

Stage 4b will probably need a path for evolution, as stage 3b did. In stage 3b's world the pilot collapsed onto still
cells, and amendment A1 faded the shading in over 50 generations. That choice belongs to stage 4b's draft.

## 8. Compute

About 20 minutes on this machine. No cloud.

## 9. What would be built

- Almost nothing new: the sweep, the gain and every rule exist (stage 4's probes).
- **The runner,** `experiments/stage4a.py`, writing `docs/data/stage4a/`. It reuses the probes' rules and ceiling.
- **Tests.**

## 10. Open for the owner

1. **The world:** the sweep at 0.55 of the cave's gain (recommended).
   - The light moves, as the plan's stage 4 says. The world is the cave's own sweep. The bar is the strongest single
     rule, comparing over time. The best rules still survive most starts.
   - Alternatives from the probe: fast clouds at 0.55, where the bar is B8. Or a spot circling every 2 hours at 0.45,
     where comparing over time fails and reading the wall is the bar.
2. **The bar:** the best of B2r, B5, B6 and B8, each tuned (recommended).
3. **The thresholds:** U2 at 0.10 and a fifth of the room; U3 at half (recommended).
4. **Where it runs:** this machine, about 20 minutes (recommended).

## 11. What would change this document

The owner's answers, as dated notes before the build. After the checks have run, nothing but dated amendments before
stage 4b.
