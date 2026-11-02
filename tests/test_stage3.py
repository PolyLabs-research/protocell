"""Stage 3a (docs/prereg/stage3.md): the translucent cell, B5 (run and wait), the runner."""

from __future__ import annotations

import json
import math

import protocell  # noqa: F401
import numpy as np
import pytest

from experiments.stage3 import FALLOFF, configure, main, runwait, starts_table
from protocell.sim import RunAndWait, simulate
from protocell.world import Starts, cave_falloff, mouth_position, node_light, node_normals, sample_starts

CFG = configure()
N = CFG.n_wall


def test_the_cell_is_translucent_and_the_falloff_is_the_rules() -> None:
    assert CFG.shade_floor == 1.0 and CFG.cave_falloff == FALLOFF == 600.0 and CFG.cave_cycle and not CFG.cave_sweep
    assert not math.isfinite(CFG.damage_threshold)
    pos, heading, noon = np.array([[300.0, -2000.0]]), np.array([0.7]), np.array([CFG.day_ticks // 4])
    light = node_light(CFG, "cave", np.zeros((1, 2)), pos, heading, noon)[0]
    nx, ny = node_normals(CFG, heading)
    s = mouth_position(CFG, noon)[0]
    d = np.hypot(pos[0, 0] + nx[0] - s[0], pos[0, 1] + ny[0] - s[1])
    assert np.allclose(light, CFG.mouth_light * cave_falloff(CFG, d))  # each node gets the field at its own place, unshaded


def test_b5_rests_in_the_dark_runs_on_a_rising_light_and_waits_otherwise() -> None:
    b5 = RunAndWait(CFG, 2, tau=10.0, rest_below=0.01)
    front = np.flatnonzero(b5.front[0]).tolist()
    assert front == [0, 1, 2, 3, 13, 14, 15]  # the node at 90 degrees is not on the front half
    first = b5.beats(np.full((2, N), 0.5), 0)
    assert (first == 0).all() and np.allclose(b5.memory, 0.5)  # the first reading only sets the memory
    rising = b5.beats(np.array([[0.6] * N, [0.4] * N]), 1)
    assert rising[0].tolist() == b5.front[0].tolist() and (rising[1] == 0).all()
    assert np.allclose(b5.memory[:, 0], [0.5 + 0.1 / 10, 0.5 - 0.1 / 10])
    dark = b5.beats(np.full((2, N), 0.005), 2)
    assert (dark == 0).all()
    with pytest.raises(ValueError):
        RunAndWait(CFG, 1, tau=0.5, rest_below=0.01)


def test_b5_climbs_toward_the_mouth_at_noon() -> None:
    noon = CFG.day_ticks // 4
    starts = Starts("cave", np.array([[0.0, -CFG.dish_radius]]), np.array([[0.0, -3000.0]]), np.array([-math.pi / 2]),
                    np.array([1]), np.array([noon]))
    r = simulate(CFG, starts, runwait(CFG, 30.0), seed=8, ticks=600, record=True)
    d = lambda p: math.hypot(p[0], p[1] + CFG.dish_radius)  # noqa: E731
    assert d(r.trajectory["pos"][0, -1]) < d(starts.pos[0]) - 500.0  # more than 500 R nearer in 10 minutes
    assert 0.1 < r.trajectory["beat"][0].mean() < 0.5  # it runs part of the time and waits the rest


def test_the_starts_table_reads_t2_and_t3() -> None:
    starts = sample_starts(CFG, "cave", 30, 8)
    rows, t2, t3 = starts_table(CFG, starts)
    assert len(rows) == 30 and t2["share_spread_ge_3sd"] <= 0.2 and t3["share_rise_ge_3sd"] > 0.3


def test_the_quick_run_writes_its_checks(tmp_path) -> None:
    summary = main(["--quick", "--workers", "2", "--out", str(tmp_path)])
    assert set(summary["checks"]) == {"T1", "T2", "T3", "T4", "T5", "T6", "T7"} and summary["bar"]["controller"] == "b5"
    names = {p.name for p in tmp_path.iterdir()}
    assert {"starts.csv", "b5_select.csv", "b5_report.csv", "b2r_report.csv", "b3_uniform.csv", "summary.json", "manifest.json"} <= names
    assert json.loads((tmp_path / "manifest.json").read_text())["settings"]["shade_floor"] == 1.0
