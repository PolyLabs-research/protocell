# Preregistration draft: stage 3a — the translucent cell's world, checked

**Written:** 2026-11-02, before any of it is built (`docs/decisions.md` D7 D3, D8 3). Stage 1 found that in the cave
the reflex is within 2% of the ceiling, because the cell's own shading tells it the light's direction at any
distance (D6). Stage 3's question in the plan is whether comparing over time evolves when the light is too faint to
sense across the body. Its world is the cave with the cell made **translucent**: a node receives the field at its own
place, unshaded, so the light's direction across one body is buried in the sensor noise, and the cell must compare
what it senses as it moves.

Stage 3a builds and checks that world and its baselines, as stage 0 and the cave were checked. Nothing is evolved.
Evolution in it is stage 3b, preregistered after 3a's checks pass. Every number below has its reason. The open
points for the owner are in §9.

## 1. The world

- **The cave's day configuration as checked in D4** (`docs/prereg/cave.md`): the mouth, the day and night, starts with
  a random phase and the matched reserve, lifetimes to the second sunrise, damage off, the sweep off, the same
  noise.
- **One change to the cell:** the shading floor is 1. Each wall node receives the field at its own place, with no
  self-shading (`cave.md` §3 had 0.3).
- **One change to the world, by the cave's own rule:** the falloff d₀ is the largest at which a still cell survives
  from at most a tenth of the pool (`cave.md` §13, rule R1).
  - A translucent still cell gets almost twice a shaded one's light, so at 750 R it survives from 13% of the pool.
  - The probe (`experiments/stage3_geometry.py`, below) gives **d₀ = 600 R**: 9%.

## 2. What the probe found (no simulation; 1,000 places at seed 1)

| cell | d₀ | still cell survives at every phase | direction readable at once, noon (an hour after sunrise) | the rise readable over 10 R, noon | over 100 R, noon (an hour after sunrise) |
|---|---|---|---|---|---|
| shaded (the cave) | 750 R | 6% | 100% (100%) | 14% | 57% (26%) |
| translucent | 750 R | 13% | 2% (0%) | 21% | 79% (38%) |
| **translucent** | **600 R** | **9%** | **2% (0%)** | 17% | **63% (30%)** |
| translucent | 500 R | 6% | 1% (0%) | 14% | 53% (23%) |

"Readable at once" means the light's spread over the wall is at least three times the sensor noise. "Readable over
a distance" means moving that far toward the mouth raises the wall's mean light by at least three times that mean's
noise, from a single tick's reading. Averaging over time lowers the noise further, so those shares are lower bounds.

## 3. The baselines

- **B0, B1** as in the cave.
- **B2r, the reflex that rests in the dark**, as in the cave, its gain chosen on starts 1–50. With no shading, its
  contrast is mostly noise.
- **B5, run and wait (new):** the simplest cell that compares over time.
  - **Its memory:** one number, an exponential average m of the wall's mean sensed light, m ← m + (Ī − m)/τₘ,
    starting at the first reading.
  - **Each tick:**
    - In the dark (Ī < 0.01) it rests, as B2r does.
    - If the light is rising (Ī > m), it runs: the nodes on its front half (cos θᵢ > 0) beat fully, the rest not at
      all. With α = 0 it swims straight ahead at about v_max.
    - Otherwise it waits: nothing beats, and the rotational noise turns it (about a radian in 80 s).
  - **Its time constant** τₘ is the best of {3, 10, 30, 100, 300} s on starts 1–50 by mean fitness, reported on
    51–100.
  - A bacterium's run and tumble is the same idea. B5 is stage 3's bar.
- **The still cell at the best fixed point**, the ceiling's reference (D6).
- **B3, random genomes:** 1,000 per spoke mode on starts 51–70.

## 4. The checks (starts 1–100 at stage 3's seed 8)

- **T1, sitting fails:** B0 survives on at most 10% of starts, and B0 at the best fixed point is full at each sunset
  on at least 90%.
- **T2, the direction cannot be read at once:** the spread of the noiseless light over the wall is at least three
  times the sensor noise on at most 10% of starts, at noon. This is the property that defines stage 3.
- **T3, the rise can be read over time:** moving 100 R toward the mouth raises the wall's mean light by at least three
  times that mean's noise on at least half the starts, at noon.
- **T4, the bars:** B2r's and B5's survival and fitness on starts 51–100 are recorded. If B1 survives on at least half,
  light is found without sensing and the world is changed.
- **T5, comparing over time pays:** B5's fitness exceeds B2r's by at least 0.02 on starts 51–100, start by start
  with shared noise, the 95% interval's lower bound above 0. If not, the world does not reward what stage 3 asks
  about, and it is amended before stage 3b.
- **T6, random wiring rarely works:** under 5% of random genomes match B5's survival.
- **T7, determinism:** as K6.
- **Reported:** B5's headroom below the still cell at the best fixed point. Stage 3b needs room above its bar that
  stage 1 did not have.

## 5. Predictions (written before the build)

1. T1, T2, T3, T6 and T7 pass (the probe: 9%, 2%, 63%).
2. B2r survives on fewer than 30% of starts, and its fitness falls below 0.35. Its spatial contrast is noise, so by
   day it beats almost at random; it still rests at night, so the dark does not kill it.
3. B5 survives on more than 80% of starts, with fitness above 0.55. τₘ is chosen at 30 or 100 s.
4. T5 passes by a wide margin: B5 above B2r by more than 0.2.
5. B5's headroom below the still cell at the best point is more than 0.05. That is room for evolution to beat its
   bar, which stage 1 did not have (0.014).

## 6. Decision table

| result | what follows |
|---|---|
| T1–T7 pass | stage 3b's preregistration: evolution against B5, both spoke modes, with the removals; the core's recurrence is predicted to matter |
| T1, T2 or T3 fails | a dated amendment to the world (its falloff or noise, with the reason), the checks run again |
| T5 fails | the world amended so that comparing over time pays, the checks run again |
| T6 fails | the task made harder, the checks run again |
| T7 fails | fixed before anything else |

## 7. Compute

About 25 minutes on this machine, like one of the cave's configurations. No cloud.

## 8. What would be built

- The translucent cell as a setting (the shading floor) with its falloff.
- B5 as a controller with its memory.
- The checks T1–T7 as a runner writing `docs/data/stage3/`.
- Tests for each, including that B5 runs only on a rising light and rests in the dark.

## 9. Open for the owner

1. **The falloff:** 600 R by the cave's rule, so that sitting fails as in the cave (recommended). Or keep 750 R, the
   cave's geometry, with sitting surviving on 13% of the pool.
2. **B5 as stage 3's bar:** run and wait as defined in §3 (recommended). Or a variant that turns actively when the
   light falls (it would need a non-zero cilium angle).
3. **Where it runs:** on this machine, about 25 minutes (recommended), or on RunPod.

## 10. What would change this document

The owner's answers, as dated notes before the build. After the checks have run, nothing but dated amendments
before stage 3b.
