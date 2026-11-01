"""The cave pool's geometry and economy, probed before anything is built (docs/prereg/cave.md §13): where a still
cell survives a lifetime, by position and phase; the best fixed point; where the light's direction can be sensed; how
big the burn zone and the soak zone are at noon; the damage rate the stated rule gives.

    .venv/bin/python -m experiments.cave_geometry

Standalone on purpose: the draft's field (§3) and economy (§5) are written out here as formulas, and the build will
tie ``protocell/world.py`` to them with a test. A still cell does not move, so its reserve depends only on its place
and the hour; the probe integrates the energy and damage equations for a grid of places at once, with a step of
``STEP`` ticks (the light changes over hours, so a minute's step loses nothing a check would notice); the build's
checks verify the share by exact simulation on the real starts. Probe points come from stream ``starts`` at seed 1,
never stage 0's or the cave's seed 0.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, replace
from typing import Dict, List, Sequence

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from protocell.rng import stream

DAY = 86_400  # ticks of 1 s
HALF = DAY // 2  # sunrise at 0, sunset at HALF
STEP = 60  # the probe's integration step, ticks
N_WALL = 16
PROBE_SEED = 1


@dataclass(frozen=True)
class Cave:
    """The draft's numbers (docs/prereg/cave.md §2–§5), the open ones at the values the probe is asked about."""

    pool_radius: float = 5000.0  # R
    mouth_light: float = 10.0  # at the mouth at noon, in half-saturations
    falloff: float = 2000.0  # d0 in I = mouth_light daylight / (1 + (d / d0)^2); the probe sets it
    shade_floor: float = 0.3
    sweep_deg: float = 60.0  # the source moves from 60 deg east of south at sunrise to 60 deg west at sunset
    sweep: bool = False
    cycle: bool = True  # False: noon all the time
    damage: bool = False
    damage_threshold: float = 4.0
    damage_rate: float = 0.0  # k_D, set by the rule "an hour at the noon mouth kills"
    damage_repair: float = 1.0 / 7200.0  # e-folds in two hours
    c0: float = 1.0 / 60_000.0  # a full reserve rests through 16.7 h
    c1: float = 1.0 / 60_000.0
    eta: float = 6.0 / 60_000.0  # at the safe contour at noon (P = 0.8) a cell fills 0.5 in 2.2 h
    sensor_sd: float = 0.01 / math.sqrt(10.0)  # stage 0's 0.01 per 0.1 s, averaged over the 1 s tick
    energy_fill: float = 1.0 - 1.0 / 60_000.0 * HALF  # what a cell that fills by day and rests by night holds at sunrise: 0.28


def daylight(cave: Cave, t: np.ndarray) -> np.ndarray:
    """A half sine from sunrise to sunset, zero at night; 1 all day long without the cycle."""
    if not cave.cycle:
        return np.ones_like(np.asarray(t, dtype=float))
    phase = np.asarray(t, dtype=float) % DAY
    return np.where(phase < HALF, np.sin(math.pi * phase / HALF), 0.0)


def source_angle(cave: Cave, t: np.ndarray) -> np.ndarray:
    """Where on the pool's edge the light comes from: due south (-90 deg) or, with the sweep, from 60 deg east of
    south at sunrise to 60 deg west of south at sunset (x east, y north)."""
    t = np.asarray(t, dtype=float)
    if not cave.sweep or not cave.cycle:
        return np.full_like(t, -math.pi / 2)
    phase = t % DAY
    frac = np.clip(phase / HALF, 0.0, 1.0)
    return -math.pi / 2 + math.radians(cave.sweep_deg) * (1.0 - 2.0 * frac)


def source_position(cave: Cave, t: np.ndarray) -> np.ndarray:
    a = source_angle(cave, t)
    return np.stack([cave.pool_radius * np.cos(a), cave.pool_radius * np.sin(a)], axis=-1)


def falloff(cave: Cave, d: np.ndarray) -> np.ndarray:
    q = d / cave.falloff
    return 1.0 / (1.0 + q * q)


def centre_light(cave: Cave, pos: np.ndarray, t: float) -> np.ndarray:
    """Unshaded, at the cell's centre, ``(P,)``."""
    s = source_position(cave, np.array(t))
    d = np.hypot(pos[:, 0] - s[0], pos[:, 1] - s[1])
    return cave.mouth_light * float(daylight(cave, np.array(t))) * falloff(cave, d)


def node_light(cave: Cave, pos: np.ndarray, heading: np.ndarray, t: float) -> np.ndarray:
    """At the wall nodes, after the cell's self-shading (stage 0's rule: the direction to the source from the cell's
    centre), ``(P, N)``."""
    s = source_position(cave, np.array(t))
    theta = heading[:, None] + 2.0 * math.pi * np.arange(N_WALL)[None, :] / N_WALL
    nx, ny = np.cos(theta), np.sin(theta)
    x, y = pos[:, 0:1] + nx, pos[:, 1:2] + ny
    raw = cave.mouth_light * float(daylight(cave, np.array(t))) * falloff(cave, np.hypot(x - s[0], y - s[1]))
    tx, ty = s[0] - pos[:, 0:1], s[1] - pos[:, 1:2]
    tn = np.maximum(np.hypot(tx, ty), 1e-300)
    cos_beta = (nx * tx + ny * ty) / tn
    return raw * (cave.shade_floor + (1.0 - cave.shade_floor) * np.maximum(0.0, cos_beta))


def photosynthesis(light: np.ndarray) -> np.ndarray:
    return light / (1.0 + light)


def start_reserve(cave: Cave, phase: float) -> float:
    """E0 at a phase (ticks after sunrise): what a cell that fills at the safe contour by day and rests by night holds
    then (§6): from ``energy_fill`` at sunrise it rises at the safe contour's net rate until full, holds 1 to sunset,
    and falls at the resting cost through the night."""
    if phase < HALF:
        safe_net = cave.eta * photosynthesis(np.array(cave.damage_threshold))[()] - cave.c0
        return min(1.0, cave.energy_fill + safe_net * phase)
    return 1.0 - cave.c0 * (phase - HALF)


def lifetime(phase: float) -> int:
    """From the start to the second sunrise after it (§6): 24 to 48 hours."""
    return int(2 * DAY - phase)


def sitters(cave: Cave, pos: np.ndarray, phase: float) -> Dict[str, np.ndarray]:
    """Still cells at these places, started at this phase with the matching reserve, through their lifetime, with the
    probe's step: survived, the final reserve, the least reserve, the mean reserve, the final damage."""
    n = pos.shape[0]
    heading = np.zeros(n)
    energy = np.full(n, start_reserve(cave, phase))
    damage = np.zeros(n)
    alive = np.ones(n, dtype=bool)
    least, total = energy.copy(), np.zeros(n)
    steps = 0
    for t in range(int(phase), int(phase) + lifetime(phase), STEP):
        light = node_light(cave, pos, heading, t + STEP / 2)
        gain = cave.eta * photosynthesis(light).mean(axis=1) * STEP
        energy = np.clip(energy + gain - cave.c0 * STEP, 0.0, 1.0)
        if cave.damage:
            above = np.maximum(0.0, light - cave.damage_threshold).mean(axis=1)
            damage = np.maximum(0.0, damage + (cave.damage_rate * above - cave.damage_repair * damage) * STEP)
        alive &= (energy > 0.0) & (damage < 1.0)
        energy = np.where(alive, energy, 0.0)
        least = np.minimum(least, energy)
        total += energy
        steps += 1
    return {"survived": alive, "final": energy, "least": least, "mean": total / steps, "damage": damage}


def probe_points(cave: Cave, n: int = 1000) -> np.ndarray:
    rng = stream(PROBE_SEED, "starts")
    r = cave.pool_radius * np.sqrt(rng.random(n))
    a = 2.0 * math.pi * rng.random(n)
    return np.stack([r * np.cos(a), r * np.sin(a)], axis=1)


PHASES = tuple(int(DAY * k / 8) for k in range(8))  # every three hours from sunrise


def probe(cave: Cave, n_points: int = 1000, phases: Sequence[int] = PHASES) -> Dict[str, float]:
    """The sitter-survivable share of the pool (mean over phases), the best fixed point's mean reserve and where it
    is, and the zones at noon."""
    pos = probe_points(cave, n_points)
    survived = np.zeros(len(pos))
    mean_reserve = np.zeros(len(pos))
    for phase in phases:
        out = sitters(cave, pos, phase)
        survived += out["survived"]
        mean_reserve += out["mean"]
    survived /= len(phases)
    mean_reserve /= len(phases)
    best = int(np.argmax(mean_reserve))
    noon = HALF // 2
    s = source_position(cave, np.array(noon))
    d = np.hypot(pos[:, 0] - s[0], pos[:, 1] - s[1])
    at_noon = centre_light(cave, pos, noon)
    contrast_noon = 0.7 * at_noon  # the shading's spread across the wall, lit side to far side
    contrast_dawn1 = 0.7 * centre_light(cave, pos, 3600)
    return {"falloff": cave.falloff, "sitter_share": float((survived == 1.0).mean()), "sitter_share_any_phase": float((survived > 0).mean()),
            "best_mean_reserve": float(mean_reserve[best]), "best_distance_to_mouth": float(d[best]), "best_noon_light": float(at_noon[best]),
            "burn_share_noon": float((at_noon >= cave.damage_threshold).mean()), "soak_share_noon": float((at_noon >= 1.0).mean()),
            "direction_sensible_noon": float((contrast_noon >= 3 * cave.sensor_sd).mean()),
            "direction_sensible_dawn_plus_1h": float((contrast_dawn1 >= 3 * cave.sensor_sd).mean()),
            "back_light_noon": float(cave.mouth_light * falloff(cave, np.array(2 * cave.pool_radius)))}


def damage_rate_rule(cave: Cave) -> float:
    """k_D such that an hour at the mouth at noon kills: the cell's centre one radius from the source, the excess over
    the threshold averaged over the wall."""
    s = source_position(cave, np.array(HALF // 2))
    pos = s[None, :] * ((cave.pool_radius - 1.0) / cave.pool_radius)
    light = node_light(cave.but(cycle=True), pos, np.zeros(1), HALF // 2)
    excess = float(np.maximum(0.0, light - cave.damage_threshold).mean())
    return 1.0 / (3600.0 * excess)


def _but(self: Cave, **changes) -> Cave:
    return replace(self, **changes)


Cave.but = _but  # type: ignore[attr-defined]


def main(argv: Sequence[str] = ()) -> None:
    base = Cave()
    print(f"economy: c0 {base.c0:.3g} a tick (a full reserve rests {1 / base.c0 / 3600:.1f} h), eta {base.eta:.3g}; "
          f"a night costs {base.c0 * HALF:.2f}; at the safe contour a cell fills 0.5 in "
          f"{0.5 / (base.eta * 0.8 - base.c0) / 3600:.1f} h; sunrise reserve {base.energy_fill:.2f}")
    print("E0 by phase (h after sunrise):", {h: round(start_reserve(base, h * 3600), 2) for h in (0, 3, 6, 9, 12, 15, 18, 21)})
    k_d = damage_rate_rule(base)
    print(f"damage rate by the rule (an hour at the noon mouth kills): k_D = {k_d:.3g} a tick per unit excess")
    print()
    print("cycle on, damage off:")
    print(" d0    | sitter share  any-phase | best: mean E, dist, noon I | burn%  soak%  (noon) | direction sensible: noon, dawn+1h | back I")
    rows: List[Dict[str, float]] = []
    for d0 in (4000, 3000, 2000, 1500, 1000, 750, 500):
        r = probe(base.but(falloff=float(d0)))
        rows.append(r)
        print(f" {d0:5d} | {r['sitter_share']:12.2f} {r['sitter_share_any_phase']:10.2f} | {r['best_mean_reserve']:6.2f} {r['best_distance_to_mouth']:7.0f} {r['best_noon_light']:6.2f} | "
              f"{r['burn_share_noon']:5.2f} {r['soak_share_noon']:6.2f} | {r['direction_sensible_noon']:5.2f} {r['direction_sensible_dawn_plus_1h']:5.2f} | {r['back_light_noon']:6.3f}")
    chosen = max((r for r in rows if r["sitter_share"] <= 0.10), key=lambda r: r["falloff"], default=None)
    if chosen is None:
        print("no falloff in the table keeps the sitter share at or under a tenth")
        return
    d0 = chosen["falloff"]
    print(f"\nthe rule picks the largest falloff with a sitter share <= 0.10: d0 = {d0:.0f} R")
    for label, cave in (("noon only", base.but(falloff=d0, cycle=False)),
                        ("cycle on, damage on", base.but(falloff=d0, damage=True, damage_rate=k_d)),
                        ("cycle on, damage on, sweep on", base.but(falloff=d0, damage=True, damage_rate=k_d, sweep=True))):
        r = probe(cave)
        print(f" {label:30s}: sitter share {r['sitter_share']:.2f} (any phase {r['sitter_share_any_phase']:.2f}); best mean E {r['best_mean_reserve']:.2f} "
              f"at {r['best_distance_to_mouth']:.0f} R from the mouth (noon I {r['best_noon_light']:.2f}); burn {r['burn_share_noon']:.2f}, soak {r['soak_share_noon']:.2f}")


if __name__ == "__main__":
    main(sys.argv[1:])
