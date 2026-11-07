"""Stage 5a (docs/prereg/stage5.md §3): the relative-sensing cell. C1 is the full suite with sensing absolute; C2-C4
here; C5 in experiments.stage5b's tests."""

from __future__ import annotations

import math

import protocell  # noqa: F401
import numpy as np
import pytest

from experiments import stage4a
from protocell.cell import decode, random_genomes
from protocell.evolve import NOISE_CELL_ID
from protocell.rng import stream
from protocell.sim import Network, simulate
from protocell.world import node_angles, sample_starts


def _relative(**changes):
    return stage4a.world(quick=True).but(sensing="relative", **changes)


def _net(cfg, n=1, seed=3):
    g = random_genomes(cfg, "fourier1", 1, stream(seed, "test"))
    return Network(cfg, decode(cfg, "fourier1", np.repeat(g, n, axis=0)))


def _inputs(cfg, light):
    net = _net(cfg)
    return np.stack([net.relative_input(light[t][None])[0] for t in range(light.shape[0])])


def test_relative_sensing_is_off_by_default_and_checked() -> None:
    assert stage4a.world().sensing == "absolute"
    with pytest.raises(ValueError, match="sensing"):
        _net(stage4a.world().but(sensing="log"))
    with pytest.raises(ValueError, match="adapt_tau"):
        _net(_relative(adapt_tau=0.5))


def test_steady_even_light_gives_no_input_at_any_level() -> None:
    cfg = _relative()
    for level in (0.0, 0.05, 2.0, 20.0):
        u = _inputs(cfg, np.full((50, cfg.n_wall), level))
        assert np.allclose(u, 0.0, atol=1e-12)


def test_c2_the_input_is_relative_to_the_level() -> None:
    cfg = _relative()
    out = {}
    for level in (2.0, 20.0):
        light = np.full((200, cfg.n_wall), level)
        light[100:] *= 1.01  # a 1% step after adapting
        out[level] = _inputs(cfg, light)[100].mean()
    assert out[2.0] > 0 and abs(out[2.0] / out[20.0] - 1.0) < 0.05
    assert math.isclose(out[20.0], math.log((20.2 + 0.1) / (20.0 + 0.1)), rel_tol=1e-9)


def test_c3_a_rise_reads_as_a_rise_and_a_fall_as_a_fall() -> None:
    cfg = _relative()
    r = 0.004
    t = np.arange(600)
    up = (5.0 * (1 + r) ** np.maximum(0, t - 100))[:, None] * np.ones(cfg.n_wall)
    down = (5.0 * (1 - r) ** np.maximum(0, t - 100))[:, None] * np.ones(cfg.n_wall)
    steady = math.log(1 + cfg.adapt_tau * r)
    assert abs(_inputs(cfg, up)[400:].mean() / steady - 1.0) < 0.05
    assert _inputs(cfg, down)[400:].mean() < 0


def test_the_light_across_the_body_reads_as_a_direction() -> None:
    cfg = _relative()
    theta = node_angles(cfg)
    light = np.full((60, cfg.n_wall), 3.0) * (1 + 0.01 * np.cos(theta - 0.5))[None]
    u = _inputs(cfg, light)[-1]
    assert np.argmax(u) == np.argmin(np.abs(((theta - 0.5 + np.pi) % (2 * np.pi)) - np.pi))  # brightest node, most input


def test_c4_a_relative_run_is_deterministic_and_a_batch_equals_its_cells() -> None:
    cfg = _relative()
    starts = sample_starts(cfg, "cave", 3, 31)
    g = random_genomes(cfg, "fourier1", 3, stream(4, "test"))
    spec = {"controller": "network", "mode": "fourier1", "genomes": g}
    a = simulate(cfg, starts, spec, seed=31, cell_ids=[NOISE_CELL_ID] * 3, ticks=500, record=True)
    b = simulate(cfg, starts, spec, seed=31, cell_ids=[NOISE_CELL_ID] * 3, ticks=500, record=True)
    assert a.run_hash() == b.run_hash()
    for i in range(3):
        one = simulate(cfg, starts.take([i]), {**spec, "genomes": g[i:i + 1]}, seed=31, cell_ids=[NOISE_CELL_ID], ticks=500, record=True)
        assert one.cell_hash(0) == a.cell_hash(i)
    absolute = simulate(cfg.but(sensing="absolute"), starts, spec, seed=31, cell_ids=[NOISE_CELL_ID] * 3, ticks=500, record=True)
    assert absolute.run_hash() != a.run_hash()  # the change changes the cell
