"""The climbing probe's part C: the oscillating light is what the plan says, the periods come from the closed loop,
and the probe runs end to end."""

import math

import numpy as np

from experiments import circle_read, circle_wave as wave, stage8


def test_the_light_holds_then_oscillates_by_the_plans_amount():
    cfg = stage8.world("home", True)
    light = wave.wave_light(cfg, 0.05, 80.0, 1000, 600)
    assert light.shape == (1000, cfg.n_wall) and np.all(light == light[:, :1])  # even across the wall
    assert np.all(light[:600] == 0.05)
    swing = np.log(light[600:, 0] / 0.05)
    assert abs(swing.max() - wave.AMPLITUDE) < 1e-4 and abs(swing.min() + wave.AMPLITUDE) < 1e-4


def test_a_cells_own_period_is_its_circle():
    closed = {"x": {"thirds": {"middle": {"turning": 0.1}}}}
    assert wave.own_period(closed, "x") == math.tau / 0.1


def test_quick_probe_end_to_end(tmp_path):
    s = wave.main(["--quick", "--out", str(tmp_path)])
    assert set(s["wave"]) == set(circle_read.CELLS) and [p["number"] for p in s["predictions"]] == [1, 2, 3]
    for v in s["wave"].values():
        r = v[f"{circle_read.LEVELS[0]} x1.0"]
        assert r["falling"]["trend"] < r["rising"]["trend"] and r["period"] > 10
    assert (tmp_path / "wave.csv").read_text().count("\n") == 1 + 5
