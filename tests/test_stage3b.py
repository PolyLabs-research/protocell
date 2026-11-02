"""Stage 3b (docs/prereg/stage3b.md): the time-constant removals, the seeds, the runner's verdicts."""

from __future__ import annotations

import csv

import protocell  # noqa: F401
import numpy as np
import pytest

from experiments.stage3b import DELTA, REMOVALS, SEEDS, VALIDATION_SEED, ga_for, main, seed_for
from protocell.cell import TIME_REMOVALS, apply_removal, decode, random_genomes
from protocell.config import CAVE
from protocell.rng import stream

N = CAVE.n_wall


def test_the_time_removals_make_the_wall_or_the_core_fast_and_touch_nothing_else() -> None:
    p = decode(CAVE, "fourier1", random_genomes(CAVE, "fourier1", 2, stream(6, "genomes")))
    wall = apply_removal(CAVE, p, "wall_fast")
    core = apply_removal(CAVE, p, "core_fast")
    assert (wall.tau[:, :N] == 1.0).all() and np.array_equal(wall.tau[:, N:], p.tau[:, N:]) and np.array_equal(wall.W, p.W)
    assert (core.tau[:, N:] == 1.0).all() and np.array_equal(core.tau[:, :N], p.tau[:, :N]) and np.array_equal(core.W, p.W)
    assert set(TIME_REMOVALS) <= set(REMOVALS) and "loop" not in REMOVALS


def test_the_seeds_are_the_preregistered_ones() -> None:
    assert SEEDS["pilot"] == {"uniform": (1101,), "fourier1": (1102,)} and seed_for("confirm", "uniform", 3) == 2103
    assert ga_for(False).validation_seed == VALIDATION_SEED == 10 and ga_for(False).generations == 100 and DELTA == 0.011
    with pytest.raises(SystemExit):
        seed_for("pilot", "uniform", 2)


def test_runs_then_the_test_read_the_criteria(tmp_path) -> None:
    for mode in ("uniform", "fourier1"):
        main(["--phase", "confirm", "--mode", mode, "--replicate", "1", "--quick", "--workers", "2", "--out", str(tmp_path)])
    summary = main(["--phase", "test", "--quick", "--workers", "2", "--out", str(tmp_path)])
    assert set(summary["verdicts"]) == {"uniform", "fourier1"}
    v = summary["verdicts"]["fourier1"]
    assert {"Q1", "Q3", "Q2_needed", "finds_comparison_over_time"} <= set(v)
    assert {"intact - (wall_fast)", "intact - (core_fast)", "intact - (hold core_drive)"} <= set(v["Q2_breaks"])
    rows = list(csv.DictReader(open(tmp_path / "test" / "comparisons.csv")))
    assert len(rows) == 2 * (2 + len(REMOVALS) + 3)
    assert {"B5", "B2r", "still at the best point"} <= set(summary["rows"])
