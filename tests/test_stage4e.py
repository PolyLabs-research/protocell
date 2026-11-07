"""Stage 4e (docs/prereg/stage4e.md): a written design becomes the network it names, out-of-range genes are refused, the
probe steps as the simulation does, the budget of world checks holds, and the judge runs once a mode."""

from __future__ import annotations

import json
import math

import protocell  # noqa: F401
import numpy as np
import pytest

from experiments import stage4e
from protocell.cell import decode
from protocell.sim import Network
from protocell.world import node_angles


def _design(mode="fourier1", **extra):
    d = {"mode": mode, "why": "a test",
         "wall": {"bias": -4.0, "tau": 2.0, "gain": 3.0, "self": 1.0, "from_cw": 0.5, "from_ccw": -0.5},
         "alpha": 0.25,
         "core": [{"name": "S", "bias": 1.0, "tau": 10.0, "in": [2.0, 0.5, -0.5] if mode == "fourier1" else 2.0,
                   "out": [-3.0, 1.0, 0.0] if mode == "fourier1" else -3.0},
                  {"name": "R", "bias": -2.0, "tau": 1.0}],
         "links": [["S", "R", -4.0], ["R", "R", 6.0]]}
    d.update(extra)
    return d


def test_a_design_becomes_the_network_it_names() -> None:
    cfg = stage4e.world()
    n = cfg.n_wall
    theta = node_angles(cfg)
    p = decode(cfg, "fourier1", stage4e.genome(cfg, _design())[None])
    assert p.gain[0] == 3.0 and p.alpha[0] == 0.25
    assert np.allclose(p.tau[0, :n], 2.0) and math.isclose(p.tau[0, n], 10.0) and math.isclose(p.tau[0, n + 1], 1.0)
    assert np.all(p.bias[0, :n] == -4.0) and p.bias[0, n] == 1.0 and p.bias[0, n + 1] == -2.0 and np.all(p.bias[0, n + 2:] == -8.0)
    assert p.W[0, 3, 3] == 1.0 and p.W[0, 3, 2] == 0.5 and p.W[0, 3, 4] == -0.5  # self, from the clockwise and anticlockwise neighbours
    assert np.allclose(p.W[0, n, :n], 2.0 + 0.5 * np.cos(theta) - 0.5 * np.sin(theta))  # S's spokes in
    assert np.allclose(p.W[0, :n, n], -3.0 + 1.0 * np.cos(theta))  # S's spokes out
    assert p.W[0, n + 1, n] == -4.0 and p.W[0, n + 1, n + 1] == 6.0 and p.W[0, n, n + 1] == 0.0  # to R from S; R's self link
    u = decode(cfg, "uniform", stage4e.genome(cfg, _design("uniform"))[None])
    assert np.allclose(u.W[0, n, :n], 2.0) and np.allclose(u.W[0, :n, n], -3.0)


def test_designs_out_of_range_or_without_a_reason_are_refused(tmp_path) -> None:
    cfg = stage4e.world()
    with pytest.raises(stage4e.DesignError, match="wall gain"):
        stage4e.genome(cfg, _design(wall={"gain": 25.0}))
    with pytest.raises(stage4e.DesignError, match="S log tau"):
        stage4e.genome(cfg, _design(core=[{"name": "S", "tau": 5000.0}], links=[]))
    with pytest.raises(stage4e.DesignError, match="no core neuron"):
        stage4e.genome(cfg, _design(links=[["S", "X", 1.0]]))
    path = tmp_path / "d.json"
    path.write_text(json.dumps({**_design(), "why": " "}))
    with pytest.raises(stage4e.DesignError, match="why"):
        stage4e.load(path)


def test_the_probe_steps_the_network_as_the_simulation_does() -> None:
    cfg = stage4e.world()
    design = _design()
    light = stage4e.light_scenario(cfg, "ramp", 0.5, 0.01, 0.002, 0.3, 60, 20)
    assert np.allclose(light[19].mean(), 0.5) and np.allclose(light[25].mean(), 0.5 * 1.01 ** 6)
    r = stage4e.run_probe(cfg, design, light, noise=False)
    net = Network(cfg, decode(cfg, "fourier1", stage4e.genome(cfg, design)[None]))
    for t in range(60):
        assert np.array_equal(net.beats(light[t][None], t)[0], r["beats"][t])
    again = stage4e.run_probe(cfg, design, light, noise=True)
    assert np.array_equal(again["beats"], stage4e.run_probe(cfg, design, light, noise=True)["beats"])  # its noise is its own stream


def _write(tmp_path, name, design):
    path = tmp_path / name
    path.write_text(json.dumps(design))
    return path


def test_the_world_checks_are_counted_written_down_and_capped(tmp_path) -> None:
    out = tmp_path / "out"
    path = _write(tmp_path, "d01.json", _design())
    first = stage4e.check(path, out, None, quick=True, budget=2, require_clean=False)
    assert first["check"] == 1 and first["remaining"] == 1
    second = stage4e.check(path, out, [1, 2], quick=True, budget=2, require_clean=False)
    assert second["starts"] == "1-2"
    with pytest.raises(SystemExit, match="all 2 world checks"):
        stage4e.check(path, out, None, quick=True, budget=2, require_clean=False)
    notebook = (out / "fourier1" / "notebook.md").read_text()
    assert notebook.count("**Why, written before it ran:** a test") == 2 and "Check 2 of 2" in notebook
    assert len(list((out / "fourier1" / "checks").glob("*.json"))) == 2 and (out / "fourier1" / "reference.json").exists()
    stage4e.note(out, "fourier1", "the lesson")
    assert "**Learnt" in (out / "fourier1" / "notebook.md").read_text()


def test_the_judge_runs_once_a_mode(tmp_path) -> None:
    out = tmp_path / "out"
    path = _write(tmp_path, "d.json", _design())
    s = stage4e.judge(path, out, quick=True, require_clean=False)
    assert s["verdict"] in ("carries B8", "partly", "does not") and set(s["cells"]) == {"written", "B8", "B0"}
    assert {"judge.csv", "submitted.json", "summary.json", "manifest.json"} <= {p.name for p in (out / "fourier1").iterdir()}
    assert json.loads((out / "fourier1" / "manifest.json").read_text())["settings"]["judge_seed"] == 27
    with pytest.raises(SystemExit, match="one submission"):
        stage4e.judge(path, out, quick=True, require_clean=False)
