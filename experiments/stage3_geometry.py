"""Stage 3's world, probed before anything is built (docs/prereg/stage3.md): the cave's day configuration with the cell
translucent (no self-shading), so that a node receives the field at its own place and nothing more.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage3_geometry

For each falloff d0: the share of the pool where a still cell survives at every phase (the cave's rule R1 asks at
most a tenth); the share of places where the light's direction can be read at once across one body (the spread of
the light over the wall at least 3 times the sensor noise, a random heading); and the share where its rise can be read
over time (moving 10 R, one tick at full speed, or 100 R toward the mouth raises the wall's mean light by at least 3
times the noise of that mean). At noon and an hour after sunrise. No simulation; 1,000 places from stream ``starts``
at seed 1, as the cave's probe.
"""

from __future__ import annotations

import math
import sys
from typing import Dict, List, Sequence

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from experiments.cave_geometry import HALF, PHASES, Cave, node_light, probe_points, sitters
from protocell.rng import stream

NOON, DAWN1 = HALF // 2, 3600
N_WALL = 16


def wall_mean(cave: Cave, pos: np.ndarray, t: float) -> np.ndarray:
    return node_light(cave, pos, np.zeros(pos.shape[0]), t).mean(axis=1)


def toward_mouth(pos: np.ndarray, cave: Cave, step: float) -> np.ndarray:
    mouth = np.array([0.0, -cave.pool_radius])
    d = mouth - pos
    n = np.maximum(np.hypot(d[:, 0], d[:, 1]), 1e-9)
    return pos + d * (np.minimum(step, n) / n)[:, None]


def probe(cave: Cave, n: int = 1000) -> Dict[str, float]:
    pos = probe_points(cave, n)
    heading = stream(1, "headings").uniform(-math.pi, math.pi, n)
    noise = 3.0 * cave.sensor_sd
    mean_noise = 3.0 * cave.sensor_sd / math.sqrt(N_WALL)
    out: Dict[str, float] = {"falloff": cave.falloff, "shade_floor": cave.shade_floor}
    for label, t in (("noon", NOON), ("dawn1", DAWN1)):
        light = node_light(cave, pos, heading, t)
        out[f"at_once_{label}"] = float(((light.max(axis=1) - light.min(axis=1)) >= noise).mean())
        here = wall_mean(cave, pos, t)
        for step in (10.0, 100.0):
            out[f"over_{int(step)}R_{label}"] = float(((wall_mean(cave, toward_mouth(pos, cave, step), t) - here) >= mean_noise).mean())
    survived = np.zeros(n)
    for phase in PHASES:
        survived += sitters(cave, pos, phase)["survived"]
    out["sitter_share"] = float((survived == len(PHASES)).mean())
    out["sitter_any_phase"] = float((survived > 0).mean())
    return out


def main(argv: Sequence[str] = ()) -> List[Dict[str, float]]:
    rows = [probe(Cave(shade_floor=0.3, falloff=750.0))]  # the cave as checked (shaded), for reference
    rows += [probe(Cave(shade_floor=1.0, falloff=d0)) for d0 in (750.0, 600.0, 500.0, 400.0)]
    print("shade  d0   | sitters: every phase, any | direction at once: noon, dawn+1h | rise over 10 R: noon, dawn+1h | over 100 R: noon, dawn+1h")
    for r in rows:
        print(f"{r['shade_floor']:4.1f} {r['falloff']:5.0f} | {r['sitter_share']:13.2f} {r['sitter_any_phase']:5.2f} | {r['at_once_noon']:22.2f} {r['at_once_dawn1']:7.2f} | "
              f"{r['over_10R_noon']:18.2f} {r['over_10R_dawn1']:7.2f} | {r['over_100R_noon']:16.2f} {r['over_100R_dawn1']:7.2f}", flush=True)
    return rows


if __name__ == "__main__":
    main(sys.argv[1:])
