"""The world (docs/prereg/stage0.md §1–§2): the fields, the shading, the starts, the dish's edge."""

from __future__ import annotations

import math

import protocell  # noqa: F401
import numpy as np
import pytest

from protocell.config import STAGE0 as cfg
from protocell.world import (brightest_point, centre_light, clamp, lamp_intensity, node_light, sample_starts, soak_distance,
                             soak_radius, source_distance, spot_intensity)

ORIGIN = np.zeros((1, 2))


def test_the_spot_peaks_at_its_centre_and_its_soak_region_is_33_r() -> None:
    assert spot_intensity(cfg, 0.0, 0.0, 0.0, 0.0) == pytest.approx(4.02)
    r = soak_radius(cfg, "spot")
    assert 33.0 < r < 34.0
    assert spot_intensity(cfg, r, 0.0, 0.0, 0.0) == pytest.approx(1.0)
    assert spot_intensity(cfg, 42.0, 0.0, 0.0, 0.0) < 0.5  # §2: a start's light does not pay for resting


def test_the_lamp_falls_off_with_distance_and_its_soak_region_is_35_r() -> None:
    assert lamp_intensity(cfg, 45.0, 0.0, 45.0, 0.0) == pytest.approx(4.02)
    assert lamp_intensity(cfg, 25.0, 0.0, 45.0, 0.0) == pytest.approx(2.02)
    d = soak_radius(cfg, "lamp")
    assert 35.0 < d < 35.5
    assert lamp_intensity(cfg, 45.0 - d, 0.0, 45.0, 0.0) == pytest.approx(1.0)


def test_the_cell_shades_itself_from_the_lamp() -> None:
    lamp = np.array([[45.0, 0.0]])
    light = node_light(cfg, "lamp", lamp, ORIGIN, np.zeros(1))[0]
    raw = lamp_intensity(cfg, np.cos(2 * np.pi * np.arange(16) / 16), np.sin(2 * np.pi * np.arange(16) / 16), 45.0, 0.0)
    assert light[0] == pytest.approx(raw[0])  # facing the lamp: unshaded
    assert light[8] == pytest.approx(0.3 * raw[8])  # the far side: 30%
    assert light[4] == pytest.approx(0.3 * raw[4]) and light[12] == pytest.approx(0.3 * raw[12])  # side on
    assert light[2] == pytest.approx(raw[2] * (0.3 + 0.7 * math.cos(math.pi / 4)))
    assert light.max() - light.min() > 0.6 * raw.max()  # §9: a contrast of about 0.7 of the light


def test_the_spot_is_read_at_each_nodes_own_place() -> None:
    centre = np.array([[0.0, 0.0]])
    pos = np.array([[-42.0, 0.0]])  # the spot is at +x
    light = node_light(cfg, "spot", centre, pos, np.zeros(1))[0]
    assert light[0] > light[8]  # node 0 faces +x
    assert light[0] == pytest.approx(spot_intensity(cfg, -41.0, 0.0, 0.0, 0.0))
    assert centre_light(cfg, "spot", centre, pos)[0] == pytest.approx(spot_intensity(cfg, -42.0, 0.0, 0.0, 0.0))


@pytest.mark.parametrize("kind", ["spot", "lamp"])
def test_starts_obey_the_stated_geometry_and_are_a_fixed_sequence(kind: str) -> None:
    starts = sample_starts(cfg, kind, 40, seed=0)
    assert len(starts) == 40 and starts.index.tolist() == list(range(1, 41))
    assert (np.hypot(starts.pos[:, 0], starts.pos[:, 1]) <= cfg.clamp_radius).all()
    d = source_distance(starts.source, starts.pos)
    if kind == "spot":
        assert (np.hypot(starts.source[:, 0], starts.source[:, 1]) <= cfg.spot_centre_within).all()
        assert (d >= cfg.spot_start_min).all()
    else:
        assert np.allclose(np.hypot(starts.source[:, 0], starts.source[:, 1]), cfg.dish_radius)
        assert (d >= cfg.lamp_start_min).all()
    assert (np.abs(starts.heading) <= math.pi).all() and len(set(starts.heading.round(6).tolist())) == 40
    again = sample_starts(cfg, kind, 40, seed=0)
    assert np.array_equal(again.pos, starts.pos) and np.array_equal(again.source, starts.source)
    prefix = sample_starts(cfg, kind, 7, seed=0)  # start k is the k-th drawn whatever n
    assert np.array_equal(prefix.pos, starts.pos[:7]) and np.array_equal(prefix.heading, starts.heading[:7])
    other = sample_starts(cfg, kind, 7, seed=1)
    assert not np.array_equal(other.pos, prefix.pos)


def test_starts_can_be_picked_by_number_and_repositioned() -> None:
    starts = sample_starts(cfg, "spot", 10, seed=0)
    picked = starts.numbered([7, 3])
    assert picked.index.tolist() == [7, 3] and np.array_equal(picked.pos[0], starts.pos[6])
    moved = picked.with_pos(np.zeros((2, 2)))
    assert (moved.pos == 0).all() and np.array_equal(moved.heading, picked.heading)


def test_the_brightest_point_and_the_soak_distance() -> None:
    starts = sample_starts(cfg, "lamp", 5, seed=0)
    bright = brightest_point(cfg, "lamp", starts.source)
    assert np.allclose(np.hypot(bright[:, 0], bright[:, 1]), cfg.clamp_radius)
    assert np.allclose(source_distance(starts.source, bright), cfg.dish_radius - cfg.clamp_radius)
    assert (soak_distance(cfg, "lamp", starts.source, bright) == 0).all()
    assert (soak_distance(cfg, "lamp", starts.source, starts.pos) >= cfg.lamp_start_min - soak_radius(cfg, "lamp") - 1e-9).all()
    spot = sample_starts(cfg, "spot", 5, seed=0)
    assert np.array_equal(brightest_point(cfg, "spot", spot.source), spot.source)


def test_the_centre_is_kept_within_44_r_and_untouched_inside() -> None:
    inside = np.array([[10.0, -3.0], [43.999, 0.0]])
    assert np.array_equal(clamp(cfg, inside), inside)
    out = clamp(cfg, np.array([[50.0, 0.0], [-30.0, 40.0]]))
    assert np.allclose(np.hypot(out[:, 0], out[:, 1]), cfg.clamp_radius)
    assert out[1, 0] < 0 < out[1, 1]  # it slides, keeping its direction
