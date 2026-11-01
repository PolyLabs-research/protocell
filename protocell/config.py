"""Stage 0's numbers, each as docs/prereg/stage0.md states it (§1–§5). Nothing here is tuned: a change to a value is a
dated amendment to the preregistration, and the manifest records the values a run used.

Units: the cell's radius R is the unit of length, a tick (0.1 s) the unit of time, and light is in units of the
photosynthetic half-saturation (I = 1 gives half the maximum rate).
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from typing import Any, Dict, Tuple


@dataclass(frozen=True)
class Config:
    # §1 units and the dish
    dish_radius: float = 45.0  # the dish is a disc of this radius
    clamp_radius: float = 44.0  # the cell's centre is kept within this (it slides along the edge)
    lifetime: int = 3000  # ticks (5 minutes)

    # §2 light: each field a single source plus a dim background
    background: float = 0.02
    spot_peak: float = 4.0  # I(p) = spot_peak exp(-|p - c|^2 / (2 spot_sigma^2)) + background
    spot_sigma: float = 16.0  # amendment A1 (2026-11-01, after run 1): 20 as preregistered; the soak region 37% of the disc, not 58%
    spot_centre_within: float = 10.0  # the spot's centre is drawn uniformly within this of the dish's centre
    spot_start_min: float = 38.0  # amendment A1: 42 as preregistered; where a still cell starves within two thirds of the lifetime (I <= 0.26)
    lamp_peak: float = 4.0  # I(p) = lamp_peak / (1 + (d / lamp_scale)^2) + background at distance d from the lamp
    lamp_scale: float = 20.0
    lamp_start_min: float = 60.0  # a start is at least this far from the lamp
    shade_floor: float = 0.3  # self-shading: a node receives I (shade_floor + (1 - shade_floor) max(0, cos beta))

    # §3 the cell
    n_wall: int = 16  # wall nodes on the ring
    n_core: int = 8  # core neurons
    v_max: float = 1.0  # R a tick (50 um/s)
    omega_max: float = 0.5  # rad a tick
    weight_range: Tuple[float, float] = (-8.0, 8.0)  # weights and biases
    log_tau_range: Tuple[float, float] = (0.0, math.log(20.0))  # tau in [1, 20] ticks
    gain_range: Tuple[float, float] = (0.0, 20.0)  # the sensory gain g
    alpha_range: Tuple[float, float] = (-math.pi, math.pi)  # the cilium angle
    sensor_noise_sd: float = 0.01  # per node per tick (stream `sensors`); 0 switches it off
    rotation_noise_sd: float = 0.05  # rad per tick (stream `motion`); 0 switches it off

    # §4 energy and damage
    energy_start: float = 0.5
    eta: float = 3.0 / 1500.0  # gain = eta (1/N) sum P(I_i), P(I) = I / (1 + I)
    c0: float = 1.0 / 1500.0  # resting cost a tick (from 0.5, starving takes 750 ticks)
    c1: float = 1.0 / 1500.0  # cost of every cilium beating fully (doubles the resting cost)
    damage_threshold: float = 10.0  # I_d: above every field's peak in stages 0 and 1, so damage stays 0 (inert)
    damage_repair: float = 0.01  # the repair rate's constant, a placeholder while damage is inert (§11 C8); stage 2 sets it

    # §5 measures
    soak_threshold: float = 1.0  # the soak region: unshaded I at the cell's centre at least this

    # the cave pool (docs/prereg/cave.md §3, §5, §6, §8); inert for the spot and the lamp
    day_ticks: int = 86_400  # a day; sunrise at 0, sunset at half
    mouth_light: float = 10.0  # at the mouth at noon
    cave_falloff: float = 750.0  # d0 in I = mouth_light daylight / (1 + (d / d0)^2), by the probe's rule R1
    cave_sweep_deg: float = 60.0  # the source from this east of south at sunrise to this west of south at sunset
    cave_cycle: bool = True  # off: noon at every hour
    cave_sweep: bool = False  # off: the source stays due south
    damage_rate: float = 1.0  # k_D in D <- D + k_D (1/N) sum max(0, I_i - I_d) - r_D D; stage 0's law had none
    fill_light: float = 4.0  # the reserve rule's light (cave.md §6): E0 rises at the net rate of a cell at this light
    rest_below: float = 0.01  # B2r rests when the wall's mean sensed light is below this

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def but(self, **changes: Any) -> "Config":
        """A copy with some values changed (tests, the noise switches, amendments)."""
        return replace(self, **changes)


STAGE0 = Config()


def cave_damage_rate(mouth_light: float = 10.0, falloff: float = 750.0, floor: float = 0.3, threshold: float = 4.0, n: int = 16) -> float:
    """k_D by the rule "an hour at the mouth at noon kills" (cave.md §5): the cell's centre one radius from the
    source, due south of it, heading 0; the wall's mean excess over the threshold; a kill in 3,600 ticks."""
    excess = 0.0
    for i in range(n):
        th = 2.0 * math.pi * i / n
        d = math.sqrt(2.0 + 2.0 * math.sin(th))  # from the node to a source one radius south of the centre
        raw = mouth_light / (1.0 + (d / falloff) ** 2)
        excess += max(0.0, raw * (floor + (1.0 - floor) * max(0.0, -math.sin(th))) - threshold)
    return 1.0 / (3600.0 * excess / n)


# The cave pool (docs/prereg/cave.md §1–§5): a 1 s tick, stage 0's per-tick quantities rescaled, the economy of a
# night, damage live by its rule. `lifetime` is the longest lifetime (two days); each cell's own runs to its second
# sunrise (world.lifetimes).
CAVE = STAGE0.but(dish_radius=5000.0, clamp_radius=4999.0, lifetime=2 * 86_400, background=0.0,
                  v_max=10.0, omega_max=1.0, log_tau_range=(0.0, math.log(3600.0)),
                  sensor_noise_sd=0.01 / math.sqrt(10.0), rotation_noise_sd=0.05 * math.sqrt(10.0),
                  eta=6.0 / 60_000.0, c0=1.0 / 60_000.0, c1=1.0 / 60_000.0,
                  damage_threshold=4.0, damage_rate=cave_damage_rate(), damage_repair=1.0 / 7200.0)
