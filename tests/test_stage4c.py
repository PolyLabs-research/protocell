"""Stage 4c (docs/prereg/stage4c.md): the seeds, the check, a quick pilot, confirm and test end to end."""

from __future__ import annotations

import csv
import json

import protocell  # noqa: F401
import pytest

from experiments import stage4c


def test_the_seeds_and_the_search() -> None:
    assert stage4c.seed_for("pilot", "uniform", 1) == 1501 and stage4c.seed_for("confirm", "fourier1", 3) == 3503
    assert stage4c.seed_for("check", "fourier1", 1) == 1598
    cma = stage4c.cma_for("pilot", False)
    assert cma.population == 96 and cma.sigma0 == 0.3 and cma.generations == 200 and cma.validation_seed == 20
    assert stage4c.cma_for("check", False).generations == 25
    with pytest.raises(SystemExit):
        stage4c.seed_for("pilot", "uniform", 2)


def test_runs_then_the_test_read_the_criteria(tmp_path) -> None:
    for phase in ("pilot", "confirm"):
        for mode in ("uniform", "fourier1"):
            stage4c.main(["--phase", phase, "--mode", mode, "--replicate", "1", "--quick", "--workers", "2", "--out", str(tmp_path)])
    info = json.loads((tmp_path / "pilot" / "uniform-1501" / "champion.json").read_text())
    assert info["generation"] == 3  # after the path (a generation each part in the smoke test)
    history = list(csv.DictReader(open(tmp_path / "pilot" / "uniform-1501" / "generations.csv")))
    assert [r["shade_floor"] for r in history] == ["0.3", "1", "1"] and all(float(r["sigma"]) > 0 for r in history)
    summary = stage4c.main(["--phase", "test", "--quick", "--workers", "2", "--out", str(tmp_path)])
    assert set(summary["verdicts"]) == {"uniform", "fourier1"} and [p["number"] for p in summary["predictions"]] == [2, 3, 4]
