"""Stage 5b (docs/prereg/stage5.md §4): stage 4e's tool on the relative cell, and check C5 (the simple rules untouched)."""

from __future__ import annotations

import json

import protocell  # noqa: F401
import numpy as np

from experiments import stage4e, stage5b
from protocell.sim import Network
from tests.test_stage4e import _design, _write


def test_the_world_is_stage_4as_with_the_relative_cell() -> None:
    cfg = stage5b.world()
    assert cfg.sensing == "relative" and cfg.adapt_tau == 10.0 and cfg.sense_floor == 0.01 and cfg.level_floor == 0.015
    assert cfg.but(sensing="absolute", adapt_tau=10.0, sense_floor=0.1, level_floor=0.1) == stage4e.world()
    assert stage5b.STAGE5B.judge_seed == 29 and stage5b.STAGE5B.bootstrap_seed == 30


def test_the_probe_runs_the_relative_cell(tmp_path) -> None:
    cfg = stage5b.world()
    light = stage4e.light_scenario(cfg, "step", 2.0, 0.01, 0.0, 0.0, 40, 20)
    r = stage4e.run_probe(cfg, _design(), light, noise=False)
    net = Network(cfg, __import__("protocell.cell", fromlist=["decode"]).decode(cfg, "fourier1", stage4e.genome(cfg, _design())[None]))
    for t in range(40):
        assert np.array_equal(net.beats(light[t][None], t)[0], r["beats"][t])
    assert net.relative


def test_c5_the_simple_rules_are_untouched_and_the_tool_runs(tmp_path) -> None:
    path = _write(tmp_path, "d.json", _design())
    rel = stage4e.check(path, tmp_path / "rel", None, quick=True, budget=2, require_clean=False, stage=stage5b.STAGE5B)
    absol = stage4e.check(path, tmp_path / "abs", None, quick=True, budget=2, require_clean=False)
    ref_rel = json.loads((tmp_path / "rel" / "fourier1" / "reference.json").read_text())
    ref_abs = json.loads((tmp_path / "abs" / "fourier1" / "reference.json").read_text())
    assert ref_rel == ref_abs  # B8 and B0 never use the cell's senses
    assert rel["b8_fitness"] == absol["b8_fitness"] and rel["fitness"] != absol["fitness"]
    s = stage4e.judge(path, tmp_path / "rel", quick=True, require_clean=False, stage=stage5b.STAGE5B)
    assert json.loads((tmp_path / "rel" / "fourier1" / "manifest.json").read_text())["protocol"] == "stage5b"
    assert json.loads((tmp_path / "rel" / "fourier1" / "manifest.json").read_text())["settings"]["judge_seed"] == 29
    assert s["verdict"] in ("carries B8", "partly", "does not")
