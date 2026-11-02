"""Stage 1b (docs/prereg/stage1b.md): pathways held at their average, the mean inputs, the runner."""

from __future__ import annotations

import json

import protocell  # noqa: F401
import numpy as np
import pytest

from experiments.cave import configure
from experiments.stage1b import main, means_job
from protocell.cell import PATHWAYS, decode, hold_at_average, pathway_mask, random_genomes, topology_mask
from protocell.config import CAVE
from protocell.rng import stream
from protocell.sim import simulate
from protocell.world import sample_starts

N, K = CAVE.n_wall, CAVE.n_core
QUICK = configure("day", quick=True).but(day_ticks=400)


def test_each_pathway_is_its_block_of_the_mask() -> None:
    mask = topology_mask(CAVE)
    core_drive, recurrence, ring = (pathway_mask(CAVE, p) for p in PATHWAYS)
    assert core_drive.sum() == N * K and recurrence.sum() == K * K and ring.sum() == 2 * N
    assert not (core_drive & recurrence).any() and not (core_drive & ring).any() and ((core_drive | recurrence | ring) <= mask).all()
    assert core_drive[:N, N:].all() and recurrence[N:, N:].all() and ring[3, 2] and ring[3, 4] and not ring[3, 3]
    with pytest.raises(ValueError):
        pathway_mask(CAVE, "spokes_in")


def test_holding_a_pathway_zeroes_its_weights_and_feeds_its_mean() -> None:
    p = decode(CAVE, "fourier1", random_genomes(CAVE, "fourier1", 2, stream(1, "genomes")))
    means = np.zeros(N + K)
    means[:N] = np.linspace(-1, 1, N)
    held = hold_at_average(CAVE, p, "core_drive", means)
    assert (held.W[:, :N, N:] == 0).all() and np.array_equal(held.W[:, N:, :], p.W[:, N:, :]) and np.array_equal(held.W[:, :N, :N], p.W[:, :N, :N])
    assert held.extra.shape == (2, N + K) and np.array_equal(held.extra[0], means) and p.extra is None
    with pytest.raises(ValueError):
        hold_at_average(CAVE, p, "core_recurrence", means)  # that pathway feeds only the core


def test_holding_a_pathway_whose_input_never_changes_changes_nothing() -> None:
    # with the core's recurrence zero in the genome, its input is always 0, so its average is 0 and holding it is the intact cell
    g = random_genomes(QUICK, "uniform", 1, stream(2, "genomes"))
    g[0, :K * K] = 0.0
    starts = sample_starts(QUICK, "cave", 2, seed=3)
    m = means_job({"cfg": QUICK, "mode": "uniform", "genome": g[0], "starts": starts, "seed": 3, "run": "x"})
    assert m["living_ticks"] > 0 and np.allclose(m["means"]["core_recurrence"], 0.0)
    spec = {"controller": "network", "mode": "uniform", "genomes": np.repeat(g, 2, axis=0)}
    intact = simulate(QUICK, starts, spec, seed=3, record=True)
    held = simulate(QUICK, starts, {**spec, "hold": {"pathway": "core_recurrence", "means": m["means"]["core_recurrence"]}}, seed=3, record=True)
    assert intact.run_hash() == held.run_hash()


def test_the_means_are_the_pathways_average_input() -> None:
    g = random_genomes(QUICK, "fourier1", 1, stream(4, "genomes"))
    starts = sample_starts(QUICK, "cave", 1, seed=5)
    m = means_job({"cfg": QUICK, "mode": "fourier1", "genome": g[0], "starts": starts, "seed": 5, "run": "x"})
    W = decode(QUICK, "fourier1", g).W[0]
    seen = []
    simulate(QUICK, starts, {"controller": "network", "mode": "fourier1", "genomes": g}, seed=5,
             observe=lambda t, s: seen.append(s["controller"].output[0].copy()) if (s["alive"] & s["active"])[0] else None)
    direct = np.mean([(W * pathway_mask(QUICK, "ring_links")) @ o for o in seen], axis=0)
    assert np.allclose(m["means"]["ring_links"], direct) and m["living_ticks"] == len(seen)


def test_the_runner_writes_its_verdicts(tmp_path) -> None:
    from experiments.stage1 import main as stage1

    for mode in ("uniform", "fourier1"):
        stage1(["--phase", "confirm", "--mode", mode, "--replicate", "1", "--quick", "--workers", "2", "--out", str(tmp_path / "s1")])
    summary = main(["--quick", "--workers", "2", "--stage1", str(tmp_path / "s1"), "--out", str(tmp_path / "s1b")])
    assert set(summary["verdicts"]) == {"uniform", "fourier1"} and set(summary["verdicts"]["uniform"]) >= set(PATHWAYS)
    assert summary["reproduces_stage1"] is None  # no stage 1 test was run here
    back = json.loads((tmp_path / "s1b" / "summary.json").read_text())
    assert set(back["means"]) == {"uniform-2001", "fourier1-3001"} and len(back["means"]["uniform-2001"]["core_drive"]) == N + K
