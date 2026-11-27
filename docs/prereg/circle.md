# Plan: how a circle climbs

**Written:** 2026-11-27, after the owner's decision D71 ("carry on as recommended"; the third recommendation, D45 C3),
before the probe ran.

## 1. The question

Every generalist read so far swims in circles where its body gives it no direction (D45, D61, D66), and climbs toward
the light there all the same. Where it is translucent it reads nothing across its body (removing that costs nothing,
D45, D61), so whatever biases its circles must come from the light's change in time, which its adapting senses feel.

A circle can be made to drift up a gradient in two plain ways:
- **Curvature:** turn less (swim straighter) while the light rises, more while it falls. The sperm of sea urchins
  steer up a chemical gradient by modulating the curvature of their circles in this way.
- **Speed:** swim faster while the light rises.

Which, if either, do these cells do?

## 2. The probe (`experiments/circle_read.py`; it sets no criterion)

The five circling generalists D61 read: runs 8102, 8103 and 8104 at 800 generations, fresh runs 8202 and 8210 of stage
8b. On the reference, one process here.

- **A. Closed loop, at home,** 60 fresh starts at seed 77. Every daylight tick a cell is alive and moving (above a
  tenth of full speed): its speed and its turning, both from its beats (so the rotational noise is left out), the
  curvature (turning per radius travelled), and the trend of the light it felt (the wall's mean light now against ten
  ticks before). The ticks are sorted, cell by cell, into thirds by that trend, from most falling to most rising. And
  how fast it climbs: its velocity toward the light's source.
- **B. Open loop:** each network alone, the light even across its wall and without noise, held at a level for 600
  ticks, then rising (or falling) by 0.2% a tick for 200: about what a cell crossing the gradient at a few radii a tick
  feels. At a dim level (0.05) and a bright one (1.0). Its speed, turning and curvature on the ramp, from its 51st tick,
  beside the steady light's last 300 ticks.

## 3. Predictions

1. At least 4 of the 5 turn less per unit distance when the light they feel is rising: curvature in the rising third at
   most 0.9 of that in the falling third.
2. Speed matters less: at least 3 of the 5 swim within 5% of the same speed in the rising and the falling third.
3. Open loop, in dim light, at least 4 of the 5 curve less on a rising ramp than in steady light, and more on a falling
   one.
4. All five climb at home: their velocity toward the source while moving is positive on average.

## 4. What I had seen before writing this

The probe at the smoke test's size (four starts, a 2,000-tick day), to see that it runs: not a result, and its numbers
are not a guide to the real ones.

## 5. Part C: the oscillating light (planned after D75, before it ran)

`experiments/circle_wave.py`, no criterion. Steady ramps did not evoke the speed change the closed loop shows (D75 A.3),
but a circling cell feels the light rise and fall once a turn. So: each network alone, noiseless, the light even
across its wall, held for 600 ticks, then multiplied by exp(0.04 sin(2 pi t / P)) for 3,000 ticks. P is the cell's own
circle (2 pi over its mean turning in closed loop, middle third, from `docs/data/circle/`), and also half and twice
that; at the dim level (0.05) and the bright one (1.0). From the oscillation's 601st tick: speed, turning and
curvature in the thirds of the felt ten-tick trend, sorted as the closed loop sorted them.

Predictions (written before part C ran; its smoke test computes real numbers, so it is not run before this is
committed):
1. In dim light at its own circle's period, at least 4 of the 5 swim at least 10% faster in the rising third than in
   the falling one.
2. At least 4 of the 5 lean the same way open loop, at their own period in dim light, as in closed loop (faster while
   rising, or slower).
3. The curvature stays within 5% between the rising and the falling third, for at least 4 of the 5.
