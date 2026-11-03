"""CMA-ES (protocell/cmaes.py): the strategy on functions with known optima, the genomes it reads, resuming."""

from __future__ import annotations

import math

import protocell  # noqa: F401
import numpy as np
import pytest

from experiments import stage4a
from protocell.cell import genome_ranges, layout
from protocell.cmaes import CMA, Strategy, run, to_genomes
from protocell.rng import stream


def _maximise(f, n: int, generations: int, population: int = 12, seed: int = 3) -> Strategy:
    s = Strategy(n, population, np.full(n, 0.2), 0.3)
    for g in range(1, generations + 1):
        x = s.ask(stream(seed, "cmaes", (g,)))
        s.tell(x, np.array([f(v) for v in x]))
    return s


def test_the_strategys_constants_follow_hansens_tutorial() -> None:
    s = Strategy(10, 10, np.zeros(10), 0.5)
    assert s.mu == 5 and abs(s.weights.sum() - 1.0) < 1e-12 and np.all(np.diff(s.weights) < 0)
    assert 3.1 < s.mueff < 3.3 and 0 < s.c1 < s.cmu < 1 and 0 < s.cs < 1 and s.ds > 1
    assert abs(s.chi - math.sqrt(10) * (1 - 1 / 40 + 1 / 2100)) < 1e-12


def test_it_finds_the_top_of_a_sphere_and_of_a_narrow_ridge() -> None:
    target = np.linspace(0.3, 0.8, 8)
    sphere = _maximise(lambda v: -float(np.sum((v - target) ** 2)), 8, 150)
    assert np.max(np.abs(sphere.mean - target)) < 1e-4 and sphere.sigma < 1e-3
    scales = 10.0 ** np.linspace(0, 3, 6)  # a hundred-thousand-to-one condition: the covariance must learn the shape
    ridge = _maximise(lambda v: -float(np.sum((scales * (v - 0.5)) ** 2)), 6, 400)
    assert float(np.sum((scales * (ridge.mean - 0.5)) ** 2)) < 1e-8


def test_a_sample_is_read_as_a_genome_by_mirroring_and_the_angle_wraps() -> None:
    cfg = stage4a.world(quick=True)
    lo, hi = genome_ranges(cfg, "uniform")
    a = layout(cfg, "uniform").alpha.start
    inside = np.full((1, lo.size), 0.25)
    assert np.allclose(to_genomes(cfg, "uniform", inside), lo + 0.25 * (hi - lo))
    outside = np.full((1, lo.size), 1.25)  # a quarter past the top mirrors to three quarters
    g = to_genomes(cfg, "uniform", outside)
    assert np.allclose(np.delete(g, a), np.delete(lo + 0.75 * (hi - lo), a)) and math.isclose(g[0, a], lo[a] + 0.25 * (hi[a] - lo[a]))
    below = to_genomes(cfg, "uniform", np.full((1, lo.size), -0.1))
    assert np.allclose(np.delete(below, a), np.delete(lo + 0.1 * (hi - lo), a)) and math.isclose(below[0, a], lo[a] + 0.9 * (hi[a] - lo[a]))
    assert np.all(g >= lo) and np.all(g <= hi)


def test_a_run_resumed_from_its_checkpoint_is_the_same_bits(tmp_path) -> None:
    cfg = stage4a.world(quick=True).but(day_ticks=400)
    cma = CMA.quick()
    straight = run(cfg, "fourier1", cma, 7, tmp_path / "a", map, log=lambda m: None)
    first = run(cfg, "fourier1", cma, 7, tmp_path / "b", map, log=lambda m: None, stop_after=1)
    resumed = run(cfg, "fourier1", cma, 7, tmp_path / "b", map, log=lambda m: None)
    assert first["next_generation"] == 1 and resumed["next_generation"] == cma.generations
    assert np.array_equal(straight["strategy"].mean, resumed["strategy"].mean) and straight["strategy"].sigma == resumed["strategy"].sigma
    assert np.array_equal(straight["strategy"].C, resumed["strategy"].C) and np.array_equal(straight["champion"], resumed["champion"])
    assert (tmp_path / "a" / "population.npy").read_bytes() == (tmp_path / "b" / "population.npy").read_bytes()
    assert straight["champion_info"]["candidate"] in {"sample 1", "sample 2", "mean"}
