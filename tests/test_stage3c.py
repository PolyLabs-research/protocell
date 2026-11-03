"""Stage 3c (docs/prereg/stage3c.md): the senses, B6 and B7, the lesions, the flat pool, the runner."""

from __future__ import annotations

import json
import math

import protocell  # noqa: F401
import numpy as np
import pytest

from experiments import stage3c
from experiments import stage3c_probe as probe
from experiments.stage3 import configure
from protocell import sim
from protocell.cell import layout
from protocell.config import CAVE, STAGE0
from protocell.sim import STREAM_WALK, ReadAndRun, build_controller, sense, simulate
from protocell.world import node_angles, sample_starts

CFG = configure(quick=True)
N = CFG.n_wall
THETA = node_angles(CFG)


def test_the_senses_keep_the_walls_mean_and_scale_the_pattern_across_it() -> None:
    assert STAGE0.sense_contrast == CAVE.sense_contrast == 1.0
    light = np.stack([0.7 + 0.002 * np.cos(THETA - 1.3), 2.0 + 0.004 * np.cos(THETA + 0.4)])
    dev = light - light.mean(axis=1, keepdims=True)
    for k in (0.0, -1.0, 10.0):
        s = sense(CFG.but(sense_contrast=k), light)
        assert np.allclose(s.mean(axis=1), light.mean(axis=1), rtol=0.0, atol=1e-15)
        assert np.allclose(s - s.mean(axis=1, keepdims=True), k * dev, rtol=0.0, atol=1e-14)
    frosted = sense(CFG.but(sense_contrast=0.0), light)
    assert np.all(frosted == frosted[:, :1])  # every node senses the same
    mirrored = sense(CFG.but(sense_contrast=-1.0), light)
    z = probe.first_mode(mirrored - mirrored.mean(axis=1, keepdims=True), THETA)
    assert np.allclose(probe.wrap(np.angle(z) - np.array([1.3 + math.pi, -0.4 + math.pi])), 0.0, atol=1e-9)  # the brighter side swapped


def test_the_light_itself_passes_untouched_when_k_is_1(monkeypatch) -> None:
    starts = sample_starts(CFG, "cave", 2, stage3c.SEED)
    before = simulate(CFG, starts, {"controller": "reflex", "k": 30.0, "rest_below": 0.01}, seed=stage3c.SEED, ticks=50, record=True)

    def never(*args, **kwargs):  # pragma: no cover - failing is the point
        raise AssertionError("the senses were transformed at k = 1")

    monkeypatch.setattr(sim, "sense", never)
    after = simulate(CFG, starts, {"controller": "reflex", "k": 30.0, "rest_below": 0.01}, seed=stage3c.SEED, ticks=50, record=True)
    assert before.run_hash() == after.run_hash()


def test_the_nodes_sense_the_transform_and_the_cell_lives_on_the_true_light() -> None:
    starts = sample_starts(CFG, "cave", 3, stage3c.SEED)
    quiet = CFG.but(sensor_noise_sd=0.0)
    seen = {}

    def observe(t, s):
        if t == 5:
            seen["light"], seen["sensed"] = s["light"].copy(), s["sensed"].copy()

    mirrored = simulate(quiet.but(sense_contrast=-1.0), starts, {"controller": "still"}, seed=stage3c.SEED, ticks=10, observe=observe)
    assert np.allclose(seen["sensed"], sense(quiet.but(sense_contrast=-1.0), seen["light"]), rtol=0.0, atol=0.0)
    plain = simulate(quiet, starts, {"controller": "still"}, seed=stage3c.SEED, ticks=10)
    assert np.array_equal(mirrored.final_energy, plain.final_energy)  # the energy uses the light, not what is sensed


def test_b6_reads_the_brighter_side_over_its_idle_phase_then_runs_toward_it() -> None:
    b6 = ReadAndRun(CFG, 1, "read", 100, 36, 0.01, 4.5)
    light = (0.5 * (1.0 + 0.01 * np.cos(THETA - 2.0)))[None, :]
    assert all((b6.beats(light, t) == 0.0).all() for t in range(64))  # idle for 64 s
    g = b6.beats(light, 64)
    assert g.sum() == 8 and abs(probe.wrap(np.angle(probe.first_mode(g, THETA)[0]) - 2.0)) < math.pi / 16
    assert all(np.array_equal(b6.beats(light, t), g) for t in range(65, 100))  # it holds the direction for the run
    assert (b6.beats(light, 100) == 0.0).all()  # and the next cycle begins idle
    for level in (0.005, 5.0):  # it rests in the dark and keeps still in bright light, the cycle running on
        other = ReadAndRun(CFG, 1, "read", 100, 36, 0.01, 4.5)
        for t in range(65):
            out = other.beats(np.full((1, N), level), t)
        assert (out == 0.0).all()
    with pytest.raises(ValueError):
        ReadAndRun(CFG, 1, "random", 100, 36, 0.01, 4.5)  # B7 needs its stream


def test_b7_draws_its_directions_from_its_own_keyed_stream() -> None:
    starts = sample_starts(CFG, "cave", 3, stage3c.SEED)
    spec = stage3c.readrun(CFG, "random")
    batch = simulate(CFG, starts, spec, seed=stage3c.SEED, ticks=400, record=True)
    for i in range(3):
        alone = simulate(CFG, starts.take([i]), spec, seed=stage3c.SEED, ticks=400, record=True)
        assert alone.cell_hash(0) == batch.cell_hash(i)  # a batch equals its singles
    assert STREAM_WALK in batch.noise_digests
    b7 = build_controller(CFG, spec, 2, stage3c.SEED, [(0, 1), (0, 2)])
    light = np.full((2, N), 0.5)
    for t in range(64):
        b7.beats(light, t)
    g = b7.beats(light, 64)
    assert g.sum(axis=1).tolist() == [8.0, 8.0] and not np.array_equal(g[0], g[1])  # its own direction per cell


def test_the_lesions_change_one_part_each() -> None:
    mode, path = probe.CHAMPIONS["U2203"]
    g = np.load(path).reshape(-1)
    lay = layout(CFG, mode)
    r0, a = lay.ring.start, lay.alpha.start
    l1, l2, l3 = (stage3c.lesioned(CFG, x) for x in stage3c.LESIONS)
    assert l1[a] == 0.0 and np.array_equal(np.delete(l1, a), np.delete(g, a))
    assert l2[r0 + 1] == l2[r0 + 2] == 0.5 * (g[r0 + 1] + g[r0 + 2]) and l2[a] == g[a]
    assert np.array_equal(np.delete(l2, [r0 + 1, r0 + 2]), np.delete(g, [r0 + 1, r0 + 2]))
    assert l3[a] == 0.0 and l3[r0 + 1] == l3[r0 + 2] == l2[r0 + 1]


def test_the_flat_pool_reads_b5_as_comparing_over_time() -> None:
    for step in ("up", "down"):
        f = stage3c.flat_job({"cfg": CFG, "cell": "B5", "level": 0.3, "step": step, "replicates": 4, "settle": 700, "hold": 1800,
                              "stagger": 7, "condition": 0})
        r = stage3c.flat_reading(f["window"], 1, 200)
        assert r["T"] > 2.0 and r["T_low"] > 0.0 and abs(r["d_late"]) < 0.5
        assert (r["d_early"] > 0) == (step == "up")  # it runs on a rise and waits on a fall


def test_the_quick_run_writes_its_tables_and_reads_its_criteria(tmp_path) -> None:
    summary = stage3c.main(["--quick", "--workers", "2", "--out", str(tmp_path)])
    names = {p.name for p in tmp_path.iterdir()}
    assert {"per_start.csv", "budget.csv", "runs.csv", "comparisons.csv", "onset_bias.csv", "flat_pool.csv", "flat_curves.csv", "summary.json",
            "manifest.json"} <= names
    assert set(summary["criteria"]) == {"C1", "C2", "C3", "C4", "C5"} and [p["number"] for p in summary["predictions"]] == list(range(1, 13))
    assert summary["criteria"]["C5"]["B5"]["every_level"]  # the flat pool's control works even in the smoke test
    assert set(summary["fitness"]) >= {"U2203 G-1", "B6 G10", "B0 G1", "L3 G1"}
    assert json.loads((tmp_path / "manifest.json").read_text())["settings"]["seed"] == 14
