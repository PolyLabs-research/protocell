"""The climbing probe: its cells are D61's circling generalists, its motion is the simulation's, and it runs end to end."""

import math

import numpy as np

from experiments import circle_read as read, stage8
from protocell.motion import cilia_motion


def test_its_speed_and_turning_are_the_simulations():
    cfg = stage8.world("home", True)
    rng = np.random.default_rng(3)
    beats = rng.random((5, cfg.n_wall))
    alpha = 0.7
    m = read.motion(cfg, beats, alpha)
    v, omega = cilia_motion(cfg, beats, np.zeros(5), np.full(5, alpha))
    assert np.allclose(m["speed"] * cfg.v_max, np.hypot(v[:, 0], v[:, 1])) and np.allclose(m["turning"], omega)
    assert np.allclose(m["curvature"], np.abs(omega) / np.hypot(v[:, 0], v[:, 1]))
    assert read.motion(cfg, np.ones((1, cfg.n_wall)), alpha)["speed"][0] < 1e-12  # an even beat pulls nowhere


def test_the_cells_are_d61s_circlers():
    cells = read.genomes()
    assert list(cells) == ["8102 at 800", "8103 at 800", "8104 at 800", "8202", "8210"] and len({g.tobytes() for g in cells.values()}) == 5
    assert read.SEED not in (48, 54, 55, 65, 66, 67, 70, 71, 72, 73, 75, 76)


def test_quick_probe_end_to_end(tmp_path):
    s = read.main(["--quick", "--out", str(tmp_path)])
    assert set(s["closed"]) == set(read.CELLS) and [p["number"] for p in s["predictions"]] == [1, 2, 3, 4]
    for c in s["closed"].values():
        assert set(c["thirds"]) == {"falling", "middle", "rising"} and c["ticks"] > 0
        assert c["thirds"]["falling"]["trend"] < c["thirds"]["rising"]["trend"] and math.isfinite(c["climb"])
    assert (tmp_path / "closed.csv").read_text().count("\n") == 1 + 3 * 5 and (tmp_path / "open.csv").read_text().count("\n") == 1 + 5 * 2 * 2
