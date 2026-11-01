"""Energy and damage (docs/prereg/stage0.md §4)."""

from __future__ import annotations

import protocell  # noqa: F401
import numpy as np
import pytest

from protocell.config import STAGE0 as cfg
from protocell.energy import damage_step, energy_step, photosynthesis

N = cfg.n_wall


def test_photosynthesis_saturates() -> None:
    assert photosynthesis(np.array([0.0, 1.0, 4.0]))[1] == 0.5
    assert photosynthesis(np.array([4.0]))[0] == pytest.approx(0.8)


def test_a_cell_at_the_spots_peak_stays_fed_even_beating_hard() -> None:
    light = np.full((1, N), 4.0)
    fed, soaked, effort = energy_step(cfg, np.array([0.5]), light, np.ones((1, N)))
    assert soaked[0] == pytest.approx(0.8) and effort[0] == 1.0
    assert fed[0] == pytest.approx(0.5 + 2.4 / 1500 - 2.0 / 1500)
    resting, _, _ = energy_step(cfg, np.array([0.5]), light, np.zeros((1, N)))
    assert resting[0] == pytest.approx(0.5 + 2.4 / 1500 - 1.0 / 1500)
    full, _, _ = energy_step(cfg, np.array([0.9999]), light, np.zeros((1, N)))
    assert full[0] == 1.0  # the reserve is kept in [0, 1]


def test_a_dim_cell_loses_and_a_resting_cell_in_the_dark_starves_in_750_ticks() -> None:
    dim = np.full((1, N), 0.49)
    e, _, _ = energy_step(cfg, np.array([0.5]), dim, np.zeros((1, N)))
    assert e[0] < 0.5
    energy = np.array([cfg.energy_start])
    dark, still = np.zeros((1, N)), np.zeros((1, N))
    ticks = 0
    while energy[0] > 0:
        energy, _, _ = energy_step(cfg, energy, dark, still)
        ticks += 1
    assert 749 <= ticks <= 751


def test_beating_fully_doubles_the_resting_cost() -> None:
    dark = np.zeros((1, N))
    rest, _, _ = energy_step(cfg, np.array([0.5]), dark, np.zeros((1, N)))
    beat, _, _ = energy_step(cfg, np.array([0.5]), dark, np.ones((1, N)))
    assert (0.5 - beat[0]) == pytest.approx(2 * (0.5 - rest[0]))


def test_damage_is_built_but_inert_at_the_stated_threshold() -> None:
    bright = np.full((2, N), 4.02)  # every field's peak
    assert (damage_step(cfg, np.zeros(2), bright) == 0).all()
    above = np.full((1, N), 12.0)
    grown = damage_step(cfg, np.zeros(1), above)
    assert grown[0] == pytest.approx(2.0)
    repaired = damage_step(cfg, np.array([0.5]), np.zeros((1, N)))
    assert repaired[0] == pytest.approx(0.5 * (1 - cfg.damage_repair))
