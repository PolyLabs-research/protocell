"""Evolution (protocell/evolve.py; docs/prereg/stage1.md §4) and the removals (§7)."""

from __future__ import annotations

import json
import math

import protocell  # noqa: F401
import numpy as np
import pytest

from experiments.cave import configure
from protocell.cell import REMOVALS, apply_removal, decode, genome_ranges, layout, random_genomes, topology_mask
from protocell.config import CAVE
from protocell.evolve import (GA, evaluate, initial_population, mutate, next_population, reflect, run, training_starts,
                              validation_starts, wrap_angle)
from protocell.rng import stream
from protocell.sim import simulate
from protocell.world import sample_starts

QUICK = configure("day", quick=True).but(day_ticks=500)  # a short day: these tests check the algorithm, not the cell
N, K = CAVE.n_wall, CAVE.n_core


def test_reflect_and_wrap_keep_values_in_range() -> None:
    lo, hi = np.array([0.0, -1.0]), np.array([1.0, 1.0])
    x = np.array([[1.3, -1.5], [-0.2, 3.5], [2.6, 0.2]])
    y = reflect(x, lo, hi)
    assert np.allclose(y, [[0.7, -0.5], [0.2, -0.5], [0.6, 0.2]])
    assert np.allclose(wrap_angle(np.array([math.pi, -math.pi, 3 * math.pi / 2, 0.1])), [-math.pi, -math.pi, -math.pi / 2, 0.1])


@pytest.mark.parametrize("mode", ["uniform", "fourier1"])
def test_mutation_stays_in_the_ranges_and_alpha_wraps(mode: str) -> None:
    lo, hi = genome_ranges(CAVE, mode)
    parents = random_genomes(CAVE, mode, 50, stream(0, "genomes"))
    children = mutate(CAVE, mode, parents, 0.5, stream(0, "evolution"))
    a = layout(CAVE, mode).alpha.start
    inside = np.delete(np.arange(lo.shape[0]), a)
    assert (children[:, inside] >= lo[inside]).all() and (children[:, inside] <= hi[inside]).all()
    assert (children[:, a] >= -math.pi).all() and (children[:, a] < math.pi).all()
    small = mutate(CAVE, mode, parents, 0.02, stream(0, "evolution"))
    step = np.abs(small - parents)[:, inside] / (hi - lo)[inside]
    assert 0.01 < np.median(step) < 0.02  # the median of |N(0, 0.02)| is 0.0135


def test_the_next_generation_keeps_the_elites_and_breeds_from_the_top() -> None:
    ga = GA.quick()
    pop = initial_population(QUICK, "uniform", ga, seed=7)
    fitness = np.array([0.1, 0.9, 0.5, 0.9, 0.3, 0.2, 0.8, 0.0])
    nxt = next_population(QUICK, "uniform", ga, pop, fitness, seed=7, generation=1)
    assert nxt.shape == pop.shape
    assert np.array_equal(nxt[0], pop[1]) and np.array_equal(nxt[1], pop[3])  # ties keep the earlier genome
    top = {1, 3, 6, 2}
    for child in nxt[ga.elites:]:
        nearest = int(np.argmin(np.abs(pop - child).sum(axis=1)))
        assert nearest in top
    assert np.array_equal(nxt, next_population(QUICK, "uniform", ga, pop, fitness, seed=7, generation=1))
    assert not np.array_equal(nxt, next_population(QUICK, "uniform", ga, pop, fitness, seed=7, generation=2))
    with pytest.raises(ValueError):
        next_population(QUICK, "uniform", ga, pop, fitness, seed=7, generation=0)


def test_training_starts_are_fresh_each_generation_and_numbered_uniquely() -> None:
    ga = GA()
    a, b = training_starts(CAVE, ga, 11, 0), training_starts(CAVE, ga, 11, 1)
    assert a.index.tolist() == list(range(1, 9)) and b.index.tolist() == list(range(9, 17))
    assert not np.array_equal(a.pos, b.pos) and np.array_equal(a.pos, training_starts(CAVE, ga, 11, 0).pos)
    assert not np.array_equal(a.pos, training_starts(CAVE, ga, 12, 0).pos)
    v = validation_starts(CAVE, ga)
    assert len(v) == 24 and np.array_equal(v.pos, sample_starts(CAVE, "cave", 24, 4).pos)
    assert not np.array_equal(a.pos, sample_starts(CAVE, "cave", 8, 11).pos)  # stream train, not stream starts


def test_a_generation_scores_the_same_whatever_the_jobs() -> None:
    ga = GA.quick()
    pop = initial_population(QUICK, "fourier1", ga, seed=3)
    one = evaluate(QUICK, "fourier1", ga, pop, 3, 0, map)
    other = evaluate(QUICK, "fourier1", ga.but(chunk=8), pop, 3, 0, map)
    assert np.array_equal(one["fitness"], other["fitness"]) and one["fitness"].shape == (8, 2)
    # every genome on a start shares the noise: two copies of one genome score alike
    twins = np.repeat(pop[:1], 8, axis=0)
    ev = evaluate(QUICK, "fourier1", ga, twins, 3, 0, map)
    assert (ev["fitness"] == ev["fitness"][0]).all()


def test_a_resumed_run_is_the_same_bits_as_one_run_straight_through(tmp_path) -> None:
    ga = GA.quick()
    straight = run(QUICK, "uniform", ga, 21, tmp_path / "a", map, log=lambda m: None)
    first = run(QUICK, "uniform", ga, 21, tmp_path / "b", map, log=lambda m: None, stop_after=2)
    assert first["next_generation"] == 2 and not (tmp_path / "b" / "champion.npy").exists()
    resumed = run(QUICK, "uniform", ga, 21, tmp_path / "b", map, log=lambda m: None)
    strip = lambda rows: [{k: v for k, v in r.items() if k != "seconds"} for r in rows]  # noqa: E731
    assert strip(resumed["history"]) == strip(straight["history"]) and resumed["validation"] == straight["validation"]
    assert np.array_equal(resumed["champion"], straight["champion"]) and np.array_equal(resumed["population"], straight["population"])
    for name in ("champion.npy", "population.npy", "validation.csv"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
    info = json.loads((tmp_path / "a" / "champion.json").read_text())
    assert info["mode"] == "uniform" and info["seed"] == 21 and len(info["genome"]) == 103


def test_each_removal_zeroes_exactly_its_weights() -> None:
    genomes = random_genomes(CAVE, "fourier1", 2, stream(5, "genomes"))
    p = decode(CAVE, "fourier1", genomes)
    mask = topology_mask(CAVE)
    expected = {"ring_links": [(i, (i + d) % N) for i in range(N) for d in (-1, 1)], "loop": [(0, N - 1), (N - 1, 0)],
                "core": [(i, j) for i in range(N + K) for j in range(N + K) if (i < N) != (j < N)],
                "core_recurrence": [(i, j) for i in range(N, N + K) for j in range(N, N + K)], "blind": []}
    for rm in REMOVALS:
        q = apply_removal(CAVE, p, rm)
        changed = {(int(i), int(j)) for i, j in zip(*np.nonzero((q.W != p.W).any(axis=0)))}
        assert changed == set(expected[rm]), rm
        assert all(mask[i, j] for i, j in changed)
        assert (q.W[:, [i for i, _ in expected[rm]], [j for _, j in expected[rm]]] == 0).all() if expected[rm] else True
        assert np.array_equal(q.gain, np.zeros(2) if rm == "blind" else p.gain)
        assert np.array_equal(p.W, decode(CAVE, "fourier1", genomes).W)  # the original is untouched
    with pytest.raises(ValueError):
        apply_removal(CAVE, p, "spokes")


def test_a_blind_cell_gets_no_light_in() -> None:
    starts = sample_starts(QUICK, "cave", 2, seed=1)
    genomes = random_genomes(QUICK, "uniform", 2, stream(5, "genomes"))
    # a sighted cell in a dark cave with no sensor noise gets no input either (the noise would still reach it)
    dark = simulate(QUICK.but(mouth_light=0.0, sensor_noise_sd=0.0), starts, {"controller": "network", "mode": "uniform", "genomes": genomes},
                    seed=1, ticks=200, record=True)
    blind = simulate(QUICK, starts, {"controller": "network", "mode": "uniform", "genomes": genomes, "removal": "blind"}, seed=1, ticks=200, record=True)
    assert np.array_equal(dark.trajectory["beat"], blind.trajectory["beat"])  # the beats do not depend on the light
