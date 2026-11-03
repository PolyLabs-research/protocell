"""Stage 3c's design probe (experiments/stage3c_probe.py): the states, the runs, the tethered cell, the readout."""

from __future__ import annotations

import json
import math

import protocell  # noqa: F401
import numpy as np

from experiments import stage3c_probe as probe
from experiments.stage3 import configure, runwait
from protocell.motion import cilia_motion
from protocell.sim import simulate
from protocell.world import node_angles, sample_starts

CFG = configure(quick=True)
N = CFG.n_wall
THETA = node_angles(CFG)


def test_the_thrust_points_along_heading_plus_alpha_plus_the_beats_first_mode() -> None:
    rng = np.random.default_rng(3)
    beats, heading, alpha = rng.random((5, N)), rng.uniform(-3, 3, 5), rng.uniform(-3, 3, 5)
    v, _ = cilia_motion(CFG, beats, heading, alpha)
    m1 = probe.first_mode(beats, THETA)
    assert np.allclose(probe.wrap(np.arctan2(v[:, 1], v[:, 0]) - (heading + alpha + np.angle(m1))), 0.0, atol=1e-12)
    assert np.allclose(np.hypot(v[:, 0], v[:, 1]), CFG.v_max * math.pi / N * np.abs(m1))


def test_parked_running_and_idle() -> None:
    bump = np.zeros(N)
    bump[[3, 4, 5]] = 1.0
    single = np.zeros(N)
    single[7] = 1.0
    beats = np.stack([np.ones(N), bump, np.full(N, 0.1), single])
    assert probe.classify(beats, probe.first_mode(beats, THETA)).tolist() == [0, 1, 2, 2]  # one node alone is not a run


def test_runs_are_three_ticks_or_more_read_at_their_third_tick() -> None:
    tracker = probe.RunTracker(2)
    seq = [(1, 0), (1, 1), (1, 1), (1, 1), (0, 0), (1, 1), (1, 1)]  # cell 0 runs 4 ticks; cell 1 runs 3, then 2 (open)
    for t, (a, b) in enumerate(seq):
        running = np.array([bool(a), bool(b)])
        tracker.step(running, np.array([t, 10 + t]), np.array([0.5, -0.5]), np.zeros(2))
    tracker.finish()
    assert sorted(tracker.durations) == [(0, 0, 4), (1, 11, 3)]  # cell 1's last run of 2 ticks was a flicker
    assert [(c, lab) for c, lab, _ in tracker.onsets] == [(0, 0), (1, 11)] and np.allclose([a for *_, a in tracker.onsets], [0.5, -0.5])


def test_the_observer_counts_every_living_tick_once() -> None:
    starts = sample_starts(CFG, "cave", 3, probe.SEED)
    obs = probe.Movement(CFG, starts, np.zeros(3))
    r = simulate(CFG, starts, runwait(CFG, probe.B5_TAU), seed=probe.SEED, ticks=600, observe=obs)
    assert obs.ticks.sum() == 600 * int(r.survived.sum()) + int(np.where(r.death_tick > 0, r.death_tick - 1, 0).sum())
    assert np.all(obs.toward <= obs.moved + 1e-9)


def test_the_tethered_champion_parks_in_bright_light_and_runs_toward_the_brighter_side() -> None:
    cfg = configure()
    mode, path = probe.CHAMPIONS["U2203"]
    genome = np.load(path)
    bright = probe.tether(cfg, mode, genome, np.full((1, N), 10.0), 600, 300, keys=None)
    assert bright["mean_beat"][0] > 0.99 and bright["shares"][0, 0] == 1.0
    light = 2.0 * (1.0 + 0.01 * np.cos(THETA - 1.0))[None, :]
    lean = probe.tether(cfg, mode, genome, light, 3600, 1800, keys=[(1000, 0)], target=np.array([1.0]))
    assert len(lean["cosines"][0]) >= 3 and np.mean(lean["cosines"][0]) > 0.5


def test_the_first_mode_reads_a_cosines_amplitude_and_direction() -> None:
    light = 0.7 + 0.002 * np.cos(THETA - 2.0)
    z = (2.0 / N) * probe.first_mode(light[None, :], THETA)[0]
    assert abs(abs(z) - 0.002) < 1e-15 and abs(probe.wrap(np.angle(z) - 2.0)) < 1e-9


def test_the_quick_run_writes_its_tables(tmp_path) -> None:
    summary = probe.main(["--quick", "--workers", "2", "--out", str(tmp_path)])
    names = {p.name for p in tmp_path.iterdir()}
    assert {"per_start.csv", "budget.csv", "runs.csv", "tether_levels.csv", "tether_onsets.csv", "readability.csv", "summary.json",
            "manifest.json"} <= names
    assert set(summary["movement"]) == {"U2203", "F3202", "B5", "B2r"} and summary["champion"]["mode"] == "uniform"
    assert json.loads((tmp_path / "manifest.json").read_text())["settings"]["seed"] == 13
