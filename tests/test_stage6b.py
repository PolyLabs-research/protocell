"""Stage 6b (docs/prereg/stage6b.md): the seeds and settings, the champion kept at half way, a quick run and test."""

from __future__ import annotations

import csv
import json

import protocell  # noqa: F401
import pytest

from experiments import stage6, stage6b


def test_the_seeds_and_the_search_are_stage_6s_but_for_the_generations() -> None:
    assert [stage6b.seed_for("confirm", "fourier1", r) for r in range(1, 6)] == [6401, 6402, 6403, 6404, 6405]
    cma, six = stage6b.cma_for(False), stage6.cma_for(False)
    assert cma.generations == 400 and stage6b.half(False) == 200
    assert cma.but(generations=six.generations) == six
    with pytest.raises(SystemExit):
        stage6b.seed_for("confirm", "fourier1", 6)
    with pytest.raises(SystemExit):
        stage6b.seed_for("confirm", "uniform", 1)


def test_a_runs_first_half_is_a_stage_6_run_and_the_test_reads_the_criteria(tmp_path) -> None:
    for replicate in ("1", "2"):
        stage6b.main(["--phase", "confirm", "--replicate", replicate, "--quick", "--workers", "2", "--out", str(tmp_path)])
    run = tmp_path / "confirm" / "fourier1-6401"
    both = list(csv.DictReader(open(run / "generations.csv")))
    half = stage6b.half(True)
    assert len(both) == 2 * half and (run / f"champion-at-{half}.json").exists()
    kept = json.loads((run / f"champion-at-{half}.json").read_text())
    assert kept["generation"] <= half and len(kept["genome"]) == 135
    # keeping the champion at half way changes nothing else: a plain run of the first half is the same generations
    from experiments import stage4b, stage5b
    from protocell.cmaes import run as plain
    cfg = stage5b.world(True)
    fade, tighten = stage4b.path_generations(True)
    state = plain(cfg, "fourier1", stage6.cma_for(True), 6401, tmp_path / "plain", map, log=lambda _: None,
                  world_for=lambda g: stage4b.training_world(cfg, g, fade, tighten), champion_from=fade + tighten + 1)
    same = [k for k in both[0] if k != "seconds"]
    assert [[str(r[k]) for k in same] for r in both[:half]] == [[r[k] for k in same] for r in csv.DictReader(open(tmp_path / "plain" / "generations.csv"))]
    assert state["champion_info"]["validation_fitness"] == kept["validation_fitness"]
    summary = stage6b.main(["--phase", "test", "--quick", "--workers", "2", "--out", str(tmp_path)])
    mine = summary["stage6b"]
    assert [r["run"] for r in mine["runs"]] == ["fourier1-6401", "fourier1-6402"] and all("at_half" in r for r in mine["runs"])
    assert [p["number"] for p in mine["predictions"]] == [1, 2, 3, 4, 5] and "design16" in mine["fitness"]
    assert f"fourier1-6401@{half}" in mine["fitness"]
    assert stage6b.main(["--phase", "read", "--quick", "--out", str(tmp_path)]) == mine
