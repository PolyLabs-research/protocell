"""The stage 1 runner (experiments/stage1.py) at the smoke test's sizes: runs, the test, its verdicts."""

from __future__ import annotations

import csv
import json

import protocell  # noqa: F401
import numpy as np

from experiments.stage1 import DELTA, SEEDS, bootstrap_ci, main, seed_for


def test_the_seeds_are_the_preregistered_ones() -> None:
    assert SEEDS["pilot"] == {"uniform": (1001,), "fourier1": (1002,)}
    assert seed_for("confirm", "fourier1", 3) == 3003 and DELTA == 0.007


def test_the_bootstrap_interval_covers_the_mean() -> None:
    diff = np.linspace(-0.01, 0.03, 50)
    mean, lo, hi = bootstrap_ci(diff, 1, 2000)
    assert lo < mean < hi and abs(mean - 0.01) < 1e-12
    assert bootstrap_ci(diff, 1, 2000) == (mean, lo, hi)


def test_runs_then_the_test_write_their_tables_and_verdicts(tmp_path) -> None:
    for mode in ("uniform", "fourier1"):
        main(["--phase", "confirm", "--mode", mode, "--replicate", "1", "--quick", "--workers", "2", "--out", str(tmp_path)])
    run_dir = tmp_path / "confirm" / "uniform-2001"
    assert {"generations.csv", "validation.csv", "champion.npy", "champion.json", "population.npy", "manifest.json", "checkpoint.npz"} <= {p.name for p in run_dir.iterdir()}
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["seeds"] == [2001] and manifest["settings"]["ga"]["population"] == 8 and manifest["settings"]["quick"] is True
    summary = main(["--phase", "test", "--quick", "--workers", "2", "--out", str(tmp_path)])
    assert set(summary["verdicts"]) == {"uniform", "fourier1"}
    v = summary["verdicts"]["uniform"]
    assert v["champions"] == 1 and set(v["Q2_parts_needed"]) == {"blind", "ring_links", "loop", "core", "core_recurrence"}
    assert {"B2r", "B2r swept", "still at the best point", "uniform-2001", "uniform-2001 swept", "uniform-2001 -core"} <= set(summary["rows"])
    rows = list(csv.DictReader(open(tmp_path / "test" / "comparisons.csv")))
    assert len(rows) == 2 * 6 and {r["compared"] for r in rows} >= {"champion - B2r", "intact - blind"}
