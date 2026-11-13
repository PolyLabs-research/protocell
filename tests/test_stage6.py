"""Stage 6 (docs/prereg/stage6.md): the seeds and settings, a quick pilot, confirm and test end to end."""

from __future__ import annotations

import csv
import json

import protocell  # noqa: F401
import pytest

from experiments import stage6


def test_the_seeds_and_the_search_are_stage_4cs_but_for_validation() -> None:
    assert stage6.seed_for("pilot", "uniform", 1) == 6101 and stage6.seed_for("pilot", "fourier1", 1) == 6102
    assert stage6.seed_for("confirm", "uniform", 3) == 6203 and stage6.seed_for("confirm", "fourier1", 1) == 6301
    cma = stage6.cma_for(False)
    assert cma.population == 96 and cma.sigma0 == 0.05 and cma.generations == 200 and cma.train_starts == 8
    assert cma.validation_seed == 32 and cma.validation_starts == 48
    with pytest.raises(SystemExit):
        stage6.seed_for("pilot", "uniform", 2)


def test_runs_then_the_test_read_the_criteria(tmp_path) -> None:
    for phase in ("pilot", "confirm"):
        for mode in ("uniform", "fourier1"):
            stage6.main(["--phase", phase, "--mode", mode, "--replicate", "1", "--quick", "--workers", "2", "--out", str(tmp_path)])
    manifest = json.loads((tmp_path / "pilot" / "uniform-6101" / "manifest.json").read_text())
    assert manifest["settings"]["sensing"] == "relative"  # the one change from stage 4c
    history = list(csv.DictReader(open(tmp_path / "pilot" / "uniform-6101" / "generations.csv")))
    assert [r["shade_floor"] for r in history] == ["0.3", "1", "1"]  # stage 4b's amended path
    summary = stage6.main(["--phase", "test", "--quick", "--workers", "2", "--out", str(tmp_path)])
    mine = summary["stage6"]
    assert set(mine["modes"]) == {"uniform", "fourier1"} and [p["number"] for p in mine["predictions"]] == [1, 2, 3, 4, 5]
    assert "design16" in mine["fitness"] and len(mine["q0"]) == 4
    for mode, v in summary["verdicts"].items():  # stage 6's reading of Q1 agrees with stage 4b's
        assert len(mine["modes"][mode]["beating_B8"]) == v["beat_the_bar"]
    assert stage6.main(["--phase", "read", "--quick", "--out", str(tmp_path)]) == mine


def test_the_extension_carries_the_pilots_run_on(tmp_path) -> None:
    with pytest.raises(SystemExit):  # no pilot yet
        stage6.main(["--phase", "extend", "--mode", "fourier1", "--quick", "--workers", "2", "--out", str(tmp_path)])
    with pytest.raises(SystemExit):  # fourier1 only
        stage6.seed_for("extend", "uniform", 1)
    stage6.main(["--phase", "pilot", "--mode", "fourier1", "--quick", "--workers", "2", "--out", str(tmp_path)])
    stage6.main(["--phase", "extend", "--mode", "fourier1", "--quick", "--workers", "2", "--out", str(tmp_path)])
    first = list(csv.DictReader(open(tmp_path / "pilot" / "fourier1-6102" / "generations.csv")))
    both = list(csv.DictReader(open(tmp_path / "extend" / "fourier1-6102" / "generations.csv")))
    assert len(both) == 2 * len(first)
    same = [k for k in first[0] if k != "seconds"]
    assert [[r[k] for k in same] for r in both[:len(first)]] == [[r[k] for k in same] for r in first]  # the pilot's generations, unchanged
