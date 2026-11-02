"""The cave pool's probe (experiments/cave_geometry.py; docs/prereg/cave.md §13): the day, the sweep, the matching
reserve, the lifetime, the damage rule, and that the probe runs."""

from __future__ import annotations

import math

import protocell  # noqa: F401
import numpy as np
import pytest

from experiments.cave_geometry import (DAY, HALF, Cave, centre_light, damage_rate_rule, daylight, lifetime, node_light, probe,
                                       sitters, source_angle, start_reserve)


def test_daylight_is_a_half_sine_and_dark_at_night() -> None:
    cave = Cave()
    assert daylight(cave, np.array([0, HALF // 2, HALF, HALF + 100, DAY - 1])).tolist() == pytest.approx([0.0, 1.0, 0.0, 0.0, 0.0], abs=1e-6)
    assert daylight(cave.but(cycle=False), np.array([0, HALF + 100])).tolist() == [1.0, 1.0]


def test_the_source_sweeps_from_east_of_south_to_west_of_south() -> None:
    swept = Cave(sweep=True)
    assert source_angle(swept, np.array(0)) == pytest.approx(math.radians(-30))  # sunrise: east of south
    assert source_angle(swept, np.array(HALF // 2)) == pytest.approx(math.radians(-90))  # noon: south
    assert source_angle(swept, np.array(HALF)) == pytest.approx(math.radians(-150))  # sunset: west of south
    assert source_angle(Cave(), np.array(HALF // 4)) == pytest.approx(-math.pi / 2)


def test_the_light_falls_off_from_the_mouth_and_the_cell_shades_itself() -> None:
    cave = Cave()
    noon = HALF // 2
    at_mouth = centre_light(cave, np.array([[0.0, -4999.0]]), noon)[0]
    assert at_mouth == pytest.approx(10.0, rel=1e-4)
    at_d0 = centre_light(cave, np.array([[0.0, -5000.0 + cave.falloff]]), noon)[0]
    assert at_d0 == pytest.approx(5.0, rel=1e-3)
    nodes = node_light(cave, np.array([[0.0, 0.0]]), np.zeros(1), noon)[0]
    assert nodes[12] > nodes[4] and nodes[4] == pytest.approx(0.3 * nodes[12] * (1 + 0) , rel=0.01)  # node 12 faces south (the mouth)


def test_the_matching_reserve_and_the_lifetime() -> None:
    cave = Cave()
    assert start_reserve(cave, 0) == pytest.approx(0.28)
    assert start_reserve(cave, 6 * 3600) == 1.0 and start_reserve(cave, HALF) == 1.0
    assert start_reserve(cave, HALF + 6 * 3600) == pytest.approx(0.64)
    assert start_reserve(cave, DAY - 1) == pytest.approx(0.28, abs=1e-4)
    assert lifetime(0) == 2 * DAY and lifetime(DAY - 1) == DAY + 1


def test_the_damage_rule_and_a_still_cell_at_the_mouth() -> None:
    cave = Cave()
    k = damage_rate_rule(cave)
    assert 1e-4 < k < 2e-4
    burn = cave.but(damage=True, damage_rate=k)
    out = sitters(burn, np.array([[0.0, -4999.0], [0.0, 4000.0]]), phase=0)
    assert not out["survived"][0]  # at the mouth: burnt by the first noon
    assert not out["survived"][1]  # at the back: starved in the dark


def test_the_probe_runs_and_reports_shares() -> None:
    r = probe(Cave(), n_points=40, phases=(0, HALF))
    assert set(r) >= {"sitter_share", "best_distance_to_mouth", "burn_share_noon", "soak_share_noon", "direction_sensible_noon"}
    assert 0 <= r["sitter_share"] <= 1 and r["soak_share_noon"] < 0.6


def test_the_stage3_probe_reads_a_translucent_cell() -> None:
    from experiments.stage3_geometry import probe as probe3

    shaded = probe3(Cave(shade_floor=0.3), n=30)
    clear = probe3(Cave(shade_floor=1.0), n=30)
    assert shaded["at_once_noon"] > 0.9 and clear["at_once_noon"] < 0.2  # without shading the direction is lost at once
    assert clear["over_100R_noon"] > 0.3  # but the rise can be read by moving
