"""The cilia and motion (docs/prereg/stage0.md §3): the summed pull, the summed torque, the noise, the edge."""

from __future__ import annotations

import math

import protocell  # noqa: F401
import numpy as np
import pytest

from protocell.config import STAGE0 as cfg
from protocell.motion import cilia_motion, move

N = cfg.n_wall


def test_half_the_ring_beating_fully_on_one_side_moves_the_cell_at_about_v_max() -> None:
    beats = np.zeros((1, N))
    beats[0, [13, 14, 15, 0, 1, 2, 3]] = 1.0  # the nodes within a quarter turn of the heading
    v, omega = cilia_motion(cfg, beats, np.zeros(1), np.zeros(1))
    assert v[0, 0] == pytest.approx(cfg.v_max, rel=0.02) and v[0, 1] == pytest.approx(0.0, abs=1e-12)
    assert omega[0] == 0.0  # alpha = 0: no torque
    turned = cilia_motion(cfg, beats, np.array([math.pi / 2]), np.zeros(1))[0]  # the heading turns the pull with it
    assert turned[0, 0] == pytest.approx(0.0, abs=1e-12) and turned[0, 1] == pytest.approx(v[0, 0])


def test_a_node_pulls_toward_its_own_side_at_alpha_0_and_away_at_alpha_pi() -> None:
    beats = np.zeros((1, N))
    beats[0, 4] = 1.0  # node 4 sits at +y
    v, _ = cilia_motion(cfg, beats, np.zeros(1), np.zeros(1))
    assert v[0, 1] == pytest.approx(cfg.v_max * math.pi / N) and v[0, 0] == pytest.approx(0.0, abs=1e-12)
    v_back, _ = cilia_motion(cfg, beats, np.zeros(1), np.array([math.pi]))
    assert v_back[0, 1] == pytest.approx(-v[0, 1])


def test_the_torque_is_the_summed_beat_times_sin_alpha() -> None:
    beats = np.ones((1, N))
    for alpha in (0.0, math.pi / 2, -math.pi / 6):
        v, omega = cilia_motion(cfg, beats, np.zeros(1), np.array([alpha]))
        assert np.allclose(v, 0.0, atol=1e-12)  # all beating: the pulls cancel
        assert omega[0] == pytest.approx(cfg.omega_max * math.sin(alpha))
    half = np.full((1, N), 0.5)
    assert cilia_motion(cfg, half, np.zeros(1), np.array([math.pi / 2]))[1][0] == pytest.approx(0.5 * cfg.omega_max)


def test_moving_adds_the_rotational_noise_and_keeps_the_cell_in_the_dish() -> None:
    pos, heading = np.array([[43.5, 0.0]]), np.array([0.2])
    v, omega = np.array([[1.0, 0.0]]), np.array([0.1])
    new_pos, new_heading = move(cfg, pos, heading, v, omega, np.array([0.03]))
    assert new_heading[0] == pytest.approx(0.33)
    assert np.hypot(new_pos[0, 0], new_pos[0, 1]) == pytest.approx(cfg.clamp_radius)
    quiet_pos, quiet_heading = move(cfg, pos, heading, v, omega, None)
    assert quiet_heading[0] == pytest.approx(0.3) and np.array_equal(quiet_pos, new_pos)
