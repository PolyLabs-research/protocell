"""The spot's geometry, probed without any simulation (docs/prereg/stage0.md §11, amendment A1): for each width
sigma, the start distance that follows the starvation rule, and what W1–W3 would say of it on fresh starts (seed 1,
never stage 0's seed 0).

    .venv/bin/python -m experiments.stage0_geometry

The starvation rule: a start is where a still cell (B0) starves within two thirds of the lifetime, so its gain is at
most c0 - 0.5 E / (2/3 lifetime) a tick. The soak region's share is of the disc the cell's centre may occupy.
"""

from __future__ import annotations

import math
import sys
from typing import Dict, List, Sequence

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from protocell.config import STAGE0, Config
from protocell.energy import photosynthesis
from protocell.world import node_light, sample_starts, soak_distance, soak_radius, spot_intensity

PROBE_SEED = 1
STARVE_WITHIN = 2.0 / 3.0  # of the lifetime


def starvation_light(cfg: Config) -> float:
    """The unshaded intensity at which a still cell's reserve falls from its start to 0 in ``STARVE_WITHIN`` of the
    lifetime: eta P(I) = c0 - E0 / (STARVE_WITHIN lifetime), inverted through P(I) = I / (1 + I)."""
    gain = cfg.c0 - cfg.energy_start / (STARVE_WITHIN * cfg.lifetime)
    p = gain / cfg.eta
    return p / (1.0 - p)


def start_distance_for(cfg: Config, sigma: float) -> float:
    """Where the spot of this width falls to the starvation light, rounded up to a whole radius."""
    light = starvation_light(cfg)
    return math.ceil(sigma * math.sqrt(2.0 * math.log(cfg.spot_peak / (light - cfg.background))))


def probe(cfg: Config, sigma: float, start_min: float, n: int = 100) -> Dict[str, float]:
    c = cfg.but(spot_sigma=float(sigma), spot_start_min=float(start_min))
    if start_min > c.clamp_radius:  # a spot at the dish's centre leaves no start that far away
        return {"sigma": sigma, "start_min": start_min, "soak_radius": soak_radius(c, "spot"),
                "soak_share": min(1.0, (soak_radius(c, "spot") / c.clamp_radius) ** 2), "light_at_start": math.nan,
                "b0_starves_in": math.nan, "w2_share": math.nan, "median_spread": math.nan, "w3_max_ticks": math.nan}
    starts = sample_starts(c, "spot", n, seed=PROBE_SEED)
    light = node_light(c, "spot", starts.source, starts.pos, starts.heading)
    spread = light.max(axis=1) - light.min(axis=1)
    at_start = spot_intensity(c, float(start_min), 0.0, 0.0, 0.0)
    net = c.eta * float(photosynthesis(np.array([at_start]))[0]) - c.c0
    radius = soak_radius(c, "spot")
    return {"sigma": sigma, "start_min": start_min, "soak_radius": radius, "soak_share": min(1.0, (radius / c.clamp_radius) ** 2),
            "light_at_start": at_start, "b0_starves_in": c.energy_start / -net if net < 0 else math.inf,
            "w2_share": float((spread >= 3 * c.sensor_noise_sd).mean()), "median_spread": float(np.median(spread)),
            "w3_max_ticks": float((soak_distance(c, "spot", starts.source, starts.pos) / c.v_max).max())}


def table(cfg: Config = STAGE0, sigmas: Sequence[float] = (20, 18, 17, 16, 15, 14, 13, 12)) -> List[Dict[str, float]]:
    rows = [probe(cfg, 20.0, 42.0)]  # as preregistered
    rows += [probe(cfg, s, start_distance_for(cfg, s)) for s in sigmas]
    return rows


def main(argv: Sequence[str] = ()) -> None:
    print(f"starvation light (a still cell starves within {STARVE_WITHIN:.2f} of the lifetime): I <= {starvation_light(STAGE0):.3f}")
    print("sigma  start | soak radius  share | I(start) B0 starves in | W2 share  median spread | W3 max ticks")
    for r in table():
        print(f"{r['sigma']:5.0f} {r['start_min']:6.0f} | {r['soak_radius']:11.1f} {r['soak_share']:6.2f} | {r['light_at_start']:8.3f} "
              f"{r['b0_starves_in']:14.0f} | {r['w2_share']:8.2f} {r['median_spread']:13.4f} | {r['w3_max_ticks']:12.1f}")


if __name__ == "__main__":
    main(sys.argv[1:])
