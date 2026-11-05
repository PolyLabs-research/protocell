"""Stage 4d (docs/prereg/stage4d.md): the record's windows, the recorder, the open-loop cell, the fit's genomes, the
judge's share and verdict, the runner."""

from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor

import protocell  # noqa: F401
import numpy as np

from experiments import stage4d, stage4_thrift as thrift
from protocell.cell import MODES, decode, layout, random_genomes
from protocell.cmaes import to_genomes
from protocell.evolve import NOISE_CELL_ID
from protocell.rng import stream
from protocell.sim import AimAndRun, Network, simulate
from protocell.world import daylight, lifetimes, sample_starts


def test_the_windows_lie_within_each_life_and_most_begin_in_daylight() -> None:
    cfg, sizes = stage4d.world(quick=True), stage4d.Sizes.quick()
    starts = sample_starts(cfg, "cave", 3, stage4d.SEED)
    windows = stage4d.draw_windows(cfg, starts, sizes)
    assert windows == stage4d.draw_windows(cfg, starts, sizes)  # the same draws every time
    ends = lifetimes(cfg, starts)
    per = sizes.day_windows + sizes.any_windows
    assert len(windows) == 3 * per
    for row in range(3):
        mine = [t for r, t in windows if r == row]
        assert len(mine) == per and all(0 <= t <= ends[row] - sizes.window for t in mine)
        lit = sum(daylight(cfg, np.array([starts.phase[row] + t]))[0] > 0.0 for t in mine)
        assert lit >= sizes.day_windows


def test_the_recorder_keeps_what_b8_sensed_and_how_it_beat() -> None:
    cfg = stage4d.world(quick=True)
    starts = sample_starts(cfg, "cave", 2, stage4d.SEED)
    rec = stage4d.Recorder([(0, 0), (1, 0), (1, 30)], 60, cfg.n_wall)
    simulate(cfg, starts, thrift.cell_spec(cfg, "B8", 2), seed=stage4d.SEED, cell_ids=[NOISE_CELL_ID] * 2, ticks=100, observe=rec)
    assert rec.lived.all()
    b8 = AimAndRun(cfg, 2, thrift.B8_TAU, 10.0, cfg.rest_below)  # B8 again, from its first tick, on what it sensed
    for t in range(60):
        g = b8.beats(np.stack([rec.sensed[0, t], rec.sensed[1, t]]), t)
        assert np.array_equal(g[0], rec.beats[0, t]) and np.array_equal(g[1], rec.beats[1, t])
    assert np.array_equal(rec.sensed[2, :30], rec.sensed[1, 30:])  # windows overlap where their ticks do


def test_the_open_loop_cell_steps_as_the_simulations_network() -> None:
    cfg = stage4d.world(quick=True)
    for mode in MODES:
        genome = random_genomes(cfg, mode, 1, stream(5, "test"))[0]
        sensed = stream(6, "test").uniform(0.0, 3.0, size=(3, 40, cfg.n_wall))
        beats = stage4d.open_loop(cfg, mode, genome, sensed)
        net = Network(cfg, decode(cfg, mode, np.repeat(genome[None], 3, axis=0)))
        for t in range(40):
            assert np.allclose(net.beats(sensed[:, t], t), beats[:, t], rtol=1e-12, atol=1e-14)


def test_the_error_and_the_match_read_against_a_cell_that_never_beats() -> None:
    target = np.zeros((2, 10, 4))
    target[:, 5:, :2] = 1.0
    assert stage4d.match(0.0, target, 3) == 1.0
    zero_err = float(np.mean(target[:, 3:] ** 2))
    assert abs(stage4d.match(zero_err, target, 3)) < 1e-15 and stage4d.match(zero_err / 2, target, 3) == 0.5


def test_the_fit_leaves_out_the_cilium_angle_and_fixes_it_at_zero() -> None:
    cfg = stage4d.world()
    for mode in MODES:
        n = layout(cfg, mode).length
        samples = stream(7, "test").normal(0.5, 0.3, size=(5, n - 1))
        genomes = to_genomes(cfg, mode, stage4d.with_alpha_zero(cfg, mode, samples))
        assert genomes.shape == (5, n) and np.all(genomes[:, layout(cfg, mode).alpha.start] == 0.0)


def test_a_fit_stopped_and_resumed_is_the_same_bits_whatever_the_workers(tmp_path) -> None:
    cfg, sizes, mode = stage4d.world(quick=True), stage4d.Sizes.quick(), "uniform"
    with ProcessPoolExecutor(2) as pool:
        data = stage4d.record(cfg, sizes, pool)
    sensed, target = data["train"]

    def fitted(workers, path, stop_after=None):
        with ProcessPoolExecutor(workers, initializer=stage4d._load_data, initargs=(cfg, mode, sensed, target, sizes.warmup)) as pool:
            return stage4d.fit(cfg, mode, sizes, data, pool, workers, lambda m: None, path, stop_after=stop_after)

    def rows(result):
        return [{k: v for k, v in row.items() if k != "seconds"} for row in result["history"]]

    straight = fitted(2, tmp_path / "straight.npz")
    stopped = fitted(1, tmp_path / "stopped.npz", stop_after=3)  # after one validation, on another number of workers
    assert len(stopped["history"]) == 3
    resumed = fitted(2, tmp_path / "stopped.npz")
    assert rows(resumed) == rows(straight) and resumed["validation"] == straight["validation"]
    assert np.array_equal(resumed["strategy"].mean, straight["strategy"].mean) and resumed["strategy"].sigma == straight["strategy"].sigma
    assert np.array_equal(resumed["fitted"]["genome"], straight["fitted"]["genome"])
    other = {**data, "digest": "another record"}
    with ProcessPoolExecutor(1, initializer=stage4d._load_data, initargs=(cfg, mode, sensed, target, sizes.warmup)) as pool:
        try:
            stage4d.fit(cfg, mode, sizes, other, pool, 1, lambda m: None, tmp_path / "stopped.npz")
        except ValueError as e:
            assert "another record" in str(e)
        else:
            raise AssertionError("a checkpoint from another record must not resume")


def test_the_pod_scripts_can_name_and_find_the_runs(tmp_path) -> None:
    assert stage4d.seed_for("fit", "uniform", 1) == 2701 and stage4d.seed_for("fit", "fourier1", 1) == 2702
    assert stage4d.run_dir(tmp_path, "uniform") == tmp_path / "fit" / "uniform-2701"  # cloud/campaign.sh looks there
    for bad in (("pilot", "uniform", 1), ("fit", "uniform", 2)):
        try:
            stage4d.seed_for(*bad)
        except SystemExit:
            continue
        raise AssertionError(f"{bad} is not a stage 4d run")


def test_the_gap_share_and_its_verdict() -> None:
    b0, b8 = np.full(4, 0.2), np.full(4, 0.6)
    point, lo, hi = stage4d.gap_share(np.full(4, 0.56), b8, b0, 100, 1)
    assert abs(point - 0.9) < 1e-12 and abs(lo - 0.9) < 1e-12 and abs(hi - 0.9) < 1e-12
    assert stage4d.verdict(0.9) == "carries B8" and stage4d.verdict(0.89) == "partly"
    assert stage4d.verdict(0.5) == "partly" and stage4d.verdict(0.49) == "does not"


def test_the_predictions_read_both_modes() -> None:
    def mode_summary(share, fitness, held):
        return {"judge": {"gap_share": share, "cells": {"fitted": {"fitness": fitness}, "B8": {"fitness": 0.55}}}, "fitted": {"held_out_match": held}}
    p = stage4d.score_predictions({"uniform": mode_summary(0.3, 0.3, 0.2), "fourier1": mode_summary(0.7, 0.45, 0.6)})
    assert [x["holds"] for x in p] == [True, True, True, True]
    p = stage4d.score_predictions({"uniform": mode_summary(0.8, 0.6, 0.2), "fourier1": mode_summary(0.4, 0.4, 0.4)})
    assert [x["holds"] for x in p] == [False, False, False, False]


def test_the_quick_runs_write_their_tables_and_the_predictions_are_scored(tmp_path) -> None:
    for mode in MODES:
        summary = stage4d.main(["--mode", mode, "--quick", "--workers", "2", "--out", str(tmp_path)])
        out = stage4d.run_dir(tmp_path, mode)
        assert {"generations.csv", "validation.csv", "windows.csv", "judge.csv", "champion.npy", "champion.json", "summary.json",
                "manifest.json", "checkpoint.npz"} <= {p.name for p in out.iterdir()}
        assert summary["judge"]["verdict"] in ("carries B8", "partly", "does not")
        assert json.loads((out / "manifest.json").read_text())["settings"]["seed"] == 24
        fitted = np.load(out / "champion.npy")
        assert fitted[0, layout(stage4d.world(True), mode).alpha.start] == 0.0
    scored = stage4d.main(["--score", "--out", str(tmp_path)])
    assert [p["number"] for p in scored["predictions"]] == [1, 2, 3, 4]
    assert (tmp_path / stage4d.PHASE / "summary.json").exists()
    a = json.loads((stage4d.run_dir(tmp_path, "uniform") / "summary.json").read_text())["record"]["digest"]
    b = json.loads((stage4d.run_dir(tmp_path, "fourier1") / "summary.json").read_text())["record"]["digest"]
    assert a == b  # both modes fit the same record
