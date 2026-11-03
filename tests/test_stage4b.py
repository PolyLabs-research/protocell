"""Stage 4b (docs/prereg/stage4b.md): the path, the seeds, a quick pilot, confirm and test end to end."""

from __future__ import annotations

import csv
import json

import protocell  # noqa: F401
import numpy as np
import pytest

from experiments import stage4a, stage4b
from protocell.config import CAVE


def test_the_path_eases_from_the_shaded_cave_into_stage_4as_world() -> None:
    assert stage4b.path_for(1, 50) == pytest.approx((0.3, 1.0))
    assert stage4b.path_for(26, 50) == pytest.approx((0.3 + 0.7 * 0.5, 1.0 - 0.45 * 0.5))
    assert stage4b.path_for(50, 50) == pytest.approx((0.3 + 0.7 * 49 / 50, 1.0 - 0.45 * 49 / 50))
    assert stage4b.path_for(51, 50) == (1.0, 0.55) and stage4b.path_for(150, 50) == (1.0, 0.55)
    cfg = stage4a.world()
    first, last = stage4b.training_world(cfg, 1, 50), stage4b.training_world(cfg, 51, 50)
    assert first.shade_floor == pytest.approx(0.3) and first.eta == pytest.approx(CAVE.eta) and first.cave_sweep
    assert last == cfg  # from generation 51 the training world is stage 4a's


def test_the_seeds_and_the_algorithm() -> None:
    assert stage4b.seed_for("pilot", "fourier1", 1) == 1302 and stage4b.seed_for("confirm", "uniform", 3) == 2303
    ga = stage4b.ga_for(False)
    assert ga.generations == 150 and ga.validation_seed == 20 and ga.population == 96 and ga.sigma == 0.02
    with pytest.raises(SystemExit):
        stage4b.seed_for("pilot", "uniform", 2)


def test_runs_then_the_test_read_the_criteria(tmp_path) -> None:
    for phase in ("pilot", "confirm"):
        for mode in ("uniform", "fourier1"):
            stage4b.main(["--phase", phase, "--mode", mode, "--replicate", "1", "--quick", "--workers", "2", "--out", str(tmp_path)])
    info = json.loads((tmp_path / "pilot" / "uniform-1301" / "champion.json").read_text())
    assert info["generation"] == 3  # the champion comes after the path (2 generations in the smoke test)
    history = list(csv.DictReader(open(tmp_path / "pilot" / "uniform-1301" / "generations.csv")))
    assert [r["shade_floor"] for r in history] == ["0.3", "0.65", "1"]
    assert [float(r["eta"]) for r in history] == pytest.approx([CAVE.eta, CAVE.eta * 0.775, CAVE.eta * 0.55])  # the gain eases in too
    summary = stage4b.main(["--phase", "test", "--quick", "--workers", "2", "--out", str(tmp_path)])
    assert set(summary["verdicts"]) == {"uniform", "fourier1"} and {"Q1", "Q2_needed", "Q3_read_direction"} <= set(summary["verdicts"]["uniform"])
    assert set(summary["q3"]) == {"uniform-1301", "fourier1-1302", "uniform-2301", "fourier1-3301"}
    assert [p["number"] for p in summary["predictions"]] == [1, 2, 3, 4, 5]
    rows = list(csv.DictReader(open(tmp_path / "test" / "comparisons.csv")))
    assert len(rows) == 4 * (1 + len(stage4b.REMOVALS) + 3)
    assert {"B8", "B5", "B6", "B0", "ceiling"} <= set(summary["rows"])
