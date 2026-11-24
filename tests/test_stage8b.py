"""Stage 8b (docs/prereg/stage8b.md): the runs and seeds, a run carried on from stage 8's checkpoint, a fresh run, and
the test's readings."""

from __future__ import annotations

import csv
import json

import numpy as np
import protocell  # noqa: F401
import pytest

pytest.importorskip("numba")

from experiments import stage8, stage8b  # noqa: E402


def test_the_runs_and_their_lengths() -> None:
    assert stage8b.SEEDS["extend"] == (*stage8.SEEDS["pilot"]["fourier1"], *stage8.SEEDS["confirm"]["fourier1"])
    assert stage8b.SEEDS["fresh"] == tuple(range(8201, 8211)) and not set(stage8b.SEEDS["fresh"]) & set(stage8b.SEEDS["extend"])
    assert stage8b.generations("extend", False) == 800 and stage8b.generations("fresh", False) == 400
    assert [stage8b.seed_for("extend", r) for r in (1, 5)] == [8101, 8105] and stage8b.seed_for("fresh", 10) == 8210
    with pytest.raises(SystemExit):
        stage8b.seed_for("fresh", 11)
    assert {stage8b.TEST_SEED, stage8b.BOOTSTRAP_SEED}.isdisjoint({stage8.TEST_SEED, stage8.BOOTSTRAP_SEED, stage8.VALIDATION_SEED})


def test_an_interval_for_a_rate() -> None:
    low, high = stage8b.wilson(1, 5)
    assert 0.03 < low < 0.04 and 0.62 < high < 0.63
    assert stage8b.wilson(0, 10)[0] == 0.0 and stage8b.wilson(10, 10)[1] == pytest.approx(1.0)
    assert all(np.isnan(v) for v in stage8b.wilson(0, 0))


def test_a_run_is_carried_on_a_fresh_run_is_made_and_the_test_reads_them(tmp_path) -> None:
    s8, out = tmp_path / "stage8", tmp_path / "stage8b"
    stage8.main(["--phase", "pilot", "--replicate", "1", "--quick", "--workers", "2", "--out", str(s8)])
    source = s8 / "pilot" / "fourier1-8101"
    before = (source / "checkpoint.npz").read_bytes()
    first = stage8.cma_for(True).generations

    # carried on, in two calls: the second resumes the first
    stage8b.main(["--phase", "extend", "--replicate", "1", "--quick", "--workers", "2", "--out", str(out), "--source", str(s8), "--stop-after", "2"])
    run = out / "extend" / "fourier1-8101"
    assert not (run / "champion.json").exists()
    stage8b.main(["--phase", "extend", "--replicate", "1", "--quick", "--workers", "2", "--out", str(out), "--source", str(s8)])
    assert (source / "checkpoint.npz").read_bytes() == before  # stage 8's files are as they were
    assert json.loads((run / f"champion-at-{first}.json").read_text()) == json.loads((source / "champion.json").read_text())
    record = json.loads((run / "carried-on.json").read_text())
    assert record["generation"] == first and 0.0 < record["compiled_validation_fitness"] < 1.0
    old, new = (list(csv.DictReader(open(p / "generations.csv"))) for p in (source, run))
    assert len(new) == 2 * first and [r["best_fitness"] for r in new[:first]] == [r["best_fitness"] for r in old]
    assert (run / f"champion-at-{3 * first // 2}.json").exists()
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["protocol"] == "stage8b/extend" and "compiled life" in manifest["settings"]["engine"] and manifest["settings"]["device"] == "cpu"

    # the same run straight through is the same run
    stage8b.main(["--phase", "extend", "--replicate", "1", "--quick", "--workers", "1", "--out", str(tmp_path / "again"), "--source", str(s8)])
    assert (tmp_path / "again" / "extend" / "fourier1-8101" / "champion.json").read_text() == (run / "champion.json").read_text()

    # a source that is not a finished run is refused
    stage8.main(["--phase", "pilot", "--replicate", "2", "--quick", "--workers", "2", "--out", str(s8), "--stop-after", "1"])
    with pytest.raises(SystemExit, match="not a finished"):
        stage8b.main(["--phase", "extend", "--replicate", "2", "--quick", "--workers", "1", "--out", str(out), "--source", str(s8)])

    stage8b.main(["--phase", "fresh", "--replicate", "1", "2", "--quick", "--workers", "2", "--out", str(out)])
    assert all((out / "fresh" / f"fourier1-{s}" / f"champion-at-{first // 2}.json").exists() for s in (8201, 8202))
    rows = stage8b.main(["--phase", "status", "--quick", "--out", str(out)])
    assert [(r["phase"], r["seed"], r["generation"]) for r in rows if r["generation"]] == [("extend", 8101, 2 * first), ("fresh", 8201, first), ("fresh", 8202, first)]

    summary = stage8b.main(["--phase", "test", "--quick", "--workers", "2", "--out", str(out), "--worlds", "home", "spot", "tighter"])
    cells = [f"8101 at {2 * first}", f"8101 at {first}", "8201", "8202"]
    assert list(summary["reading"]) == cells and set(summary["worlds"]) == {"home", "spot", "tighter"}
    assert [summary["reading"][c]["kind"] for c in cells] == ["extended", "stage 8", "fresh", "fresh"]
    assert [p["number"] for p in summary["predictions"]] == [1, 2, 3, 4, 5, 6] and len(summary["time"]) == 1
    assert summary["generalists_at_first_length"]["of"] == 3
    assert (out / "test" / "cells.csv").read_text().splitlines()[0].startswith("kind,world,cell")
