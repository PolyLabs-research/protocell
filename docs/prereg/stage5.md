# Preregistration draft: stage 5 — a cell that senses light relative to its recent level

**Written:** 2026-11-07, after stage 4e (`docs/decisions.md` D25, D26), before any code. The owner: "Agree, 1, proceed".

## 1. The question

Stage 4e's notebooks named three things in the cell's wiring that blocked B8's job (D25). Relative sensing answers two of
them:
- **No gain control.** A sensor that responds to the ratio of light to its recent level is the same at light 0.05 and at
  light 5, so no gain has to be traded between the far field and the mouth.
- **No memory across motion.** If the sensor keeps the recent level itself, the comparison of "light now" with "light
  just before", B5's comparison, happens in the sensor, before the beats. The sensor's memory averages the light it
  senses, not the wall's outputs, so the cell's own runs cannot flood it.

The third blocker, eight core neurons, stays.

**The question:** with this one change to the cell, can a cell written by hand do B8's job in stage 4a's world? If it can,
evolution follows, as the owner's call.

## 2. The change

- **Each tick:**
  - Each node's sensed light (the world's light plus the sensors' noise, as before) is floored at zero: x_i.
  - The cell keeps one adaptation level A, an exponential average of the wall's mean x with time constant tau_A. It
    starts at the first reading.
  - Each wall node's input is the sensory gain times log((x_i + k) / (A + k)), with A from the ticks before; then A is
    updated.
- **So the input is:**
  - zero in steady, even light at any level;
  - positive at a node brighter than the recent mean, whether brighter in space (the light's direction) or in time (a
    rise);
  - negative where darker.
- **tau_A = 10 s,** B8's memory.
- **k = 0.1, a floor.** Below about 0.1 the sensor loses its relative scale, which keeps the night's noise at the wall to
  about 0.03 per node per tick before the gain.
- **These are fixed constants, not genes:** one change at a time. The genome stays at 103 and 135 numbers.
- **Nothing else changes:**
  - the world, the noise, the beats and the costs;
  - the simple rules, which read the light directly.
- **It is off by default** (`sensing = "absolute"`), so every earlier result stays the same bits.

## 3. Stage 5a: checks before any writing

| check | what | passes when |
|---|---|---|
| C1 | absolute sensing unchanged | the full suite passes, the platform's pinned hash included |
| C2 | relative to the level | after adapting, light 2 and light 20 give the same input to a 1% step, within the floor's effect (5%) |
| C3 | a rise reads as a rise | a steady rise of r a tick gives a mean input near log(1 + tau_A r), within 5%; a fall gives a negative one |
| C4 | determinism | a run is the same bits twice, and a batch equals its cells run alone |
| C5 | the simple rules untouched | B8's and B0's numbers on stage 4e's validation starts are unchanged |

## 4. Stage 5b: the hand-writing test on the new cell

Stage 4e's test, exactly, on the cell of §2 (`docs/prereg/stage4e.md` §3–§6):
- the same tool, rules and notebook;
- 50 world checks per mode, fourier1 first, then uniform;
- the checks on stage 4b's 24 validation starts (seed 20);
- the judge on fresh starts 1–100 at seed 29, with B8 and B0, and a bootstrap at seed 30;
- the same verdict thresholds (carries B8 from 0.9 of the gap, partly from 0.5).

## 5. Predictions (written before any code or weight)

1. **The fourier1 cell closes at least half the gap** ("partly" or better). B5's comparison is now in the sensor, where
   the cell's runs cannot spoil it, and B5 closes about nine tenths of the gap in stage 4a's checks.
2. **It does not beat B8.**
3. **The uniform cell closes at least a quarter of the gap, but less than the fourier1 cell.**
4. **Within 15 checks, a fourier1 design closes at least half the gap on the validation starts.**

## 6. Compute

Everything runs here, as one process, as stage 4e did. Nothing on RunPod.

## 7. The draft's choices, open to the owner

The owner said "proceed", so these defaults stand unless changed:
- the form of the change (a log ratio to one adapting mean for the whole wall);
- tau_A = 10 s and k = 0.1, as fixed constants;
- stage 5b's budget of 50 checks per mode.

**Stage 5a's outcome (2026-11-07, before stage 5b).**
- **The build:** `sensing`, `adapt_tau` and `sense_floor` in `protocell/config.py`, and the transduction in
  `protocell/sim.py`'s Network.
- **The tool:** stage 5b reuses stage 4e's (`experiments/stage5b.py` over `experiments/stage4e.py`). Stage 4e's test,
  seeds and folder are unchanged.

| check | outcome |
|---|---|
| C1 | ✓ the full suite passes with sensing absolute (178 tests), the pinned hash among them |
| C2 | ✓ a 1% step after adapting gives the same input at light 2 and 20, within 5% (`tests/test_stage5.py`) |
| C3 | ✓ a steady rise of 0.004 a tick gives a mean input within 5% of log(1 + 10 x 0.004); a fall gives a negative one |
| C4 | ✓ a relative run is the same bits twice, and each cell alone matches the batch |
| C5 | ✓ in the quick world, B8's and B0's per-start numbers are the same with the relative cell as without (`tests/test_stage5b.py`); the full-size reference is compared at stage 5b's first check |

The light across the body also reads as a direction: the brightest node gets the most input (tested).

## 8. What would change this document

The owner's changes to §7, and the 5a checks' outcome, as dated notes before stage 5b. 5b's outcome after its judge.
