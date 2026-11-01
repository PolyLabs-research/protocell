"""The stage 0 runner (experiments/stage0.py) at the smoke test's sizes: the files it writes and the shape of its
summary."""

from __future__ import annotations

import json

import protocell  # noqa: F401
import numpy as np

from experiments.stage0 import B3_COLUMNS, Sizes, b3_job, main, numbers
from experiments.stage0_geometry import probe, start_distance_for
from protocell.cell import random_genomes
from protocell.config import STAGE0
from protocell.rng import stream
from protocell.world import sample_starts


def test_the_quick_run_writes_every_table_and_a_summary(tmp_path) -> None:
    summary = main(["--quick", "--workers", "2", "--out", str(tmp_path)])
    names = {p.name for p in tmp_path.iterdir()}
    for kind in ("spot", "lamp"):
        assert {f"starts_{kind}.csv", f"b0_{kind}.csv", f"b0_brightest_{kind}.csv", f"b1_{kind}.csv", f"b2_select_{kind}.csv",
                f"b2_report_{kind}.csv", f"b3_{kind}_uniform.csv", f"b3_{kind}_fourier1.csv"} <= names
        checks = summary["checks"][kind]
        assert set(checks) == {"W1", "W2", "W3", "W4", "W5"} and all("pass" in checks[c] for c in checks)
        assert checks["W4"]["bar"]["k"] in (1, 3, 10, 30, 100)
        assert summary["bar"][kind]["n"] == 5
    assert summary["W6"]["pass"] is True
    back = json.loads((tmp_path / "summary.json").read_text())
    assert back["quick"] is True and back["W6"]["spot"]["batch_equals_singles"] is True
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["settings"]["quick"] is True and manifest["settings"]["lifetime"] == 60 and manifest["timing"]["cells"] > 0
    b3 = (tmp_path / "b3_spot_uniform.csv").read_text().splitlines()
    assert b3[0] == ",".join(B3_COLUMNS) and len(b3) == 1 + Sizes.quick().n_genomes


def test_a_b3_job_scores_each_genome_on_every_start() -> None:
    cfg = STAGE0.but(lifetime=30)
    starts = sample_starts(cfg, "lamp", 4, seed=0).numbered(numbers((2, 3)))
    genomes = random_genomes(cfg, "uniform", 3, stream(0, "genomes"))
    rows = b3_job({"cfg": cfg, "starts": starts, "genomes": genomes, "numbers": np.array([1, 2, 3]), "mode": "uniform", "seed": 0})
    assert [r["genome"] for r in rows] == [1, 2, 3] and all(r["n_starts"] == 2 for r in rows)
    assert all(0 <= r["survival"] <= 1 and 0 <= r["mean_fitness"] <= 1 for r in rows)


def test_the_geometry_probe_derives_the_amended_start_distance() -> None:
    assert start_distance_for(STAGE0, 16.0) == 38 and start_distance_for(STAGE0, 20.0) == 48
    row = probe(STAGE0, 16.0, 38.0, n=20)
    assert row["w2_share"] >= 0.5 and row["b0_starves_in"] < 2000 and row["soak_share"] < 0.4
    assert np.isnan(probe(STAGE0, 20.0, 48.0)["w2_share"])  # the preregistered width has no room for such a start


def test_the_stage1_budget_reads_the_headroom_from_the_cave_tables() -> None:
    from experiments.stage1_budget import headroom

    day = headroom("day")
    assert day["n"] == 50 and day["bar"] == "b2r" and 0.69 < day["bar_fitness"] < 0.71 and day["gap_mean"] > 0
