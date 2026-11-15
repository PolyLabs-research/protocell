"""Stage 8 (docs/prereg/stage8.md): the worlds and seeds, the mix after the path, a quick pilot, its rule and the test."""

from __future__ import annotations

import csv

import numpy as np
import protocell  # noqa: F401
import pytest

from experiments import stage4b, stage6b, stage7, stage8
from protocell.cmaes import run as plain
from protocell.evolve import GA, training_worlds


def test_the_worlds_the_seeds_and_the_search() -> None:
    assert set(stage8.TRAINED) | set(stage8.HELD) == set(stage8.WORLDS) and not set(stage8.TRAINED) & set(stage8.HELD)
    for w in ("home", "flicker", "spot", "shaded", "fixed mouth", "tighter", "sweep and flicker"):  # stage 7's worlds, unchanged
        assert stage8.world(w) == stage7.world_cfg(w, False)
    assert stage8.world("slow clouds").cloud_sun_mean == 600.0 and stage8.world("slow spot").path_period == 21_600
    assert [stage8.seed_for("pilot", "fourier1", r) for r in (1, 2)] == [8101, 8102] and stage8.seed_for("confirm", "fourier1", 3) == 8105
    cma = stage8.cma_for(False)
    assert cma.but(validation_seed=stage6b.cma_for(False).validation_seed) == stage6b.cma_for(False) and cma.generations == 400
    assert [len(s) for _, _, s in stage8.validation_worlds(False)] == [12, 12, 12, 12]
    with pytest.raises(SystemExit):
        stage8.seed_for("pilot", "fourier1", 3)


def test_a_generations_starts_split_evenly_over_the_worlds_and_are_numbered_apart() -> None:
    worlds = [stage8.world(w, True) for w in stage8.TRAINED]
    plan = training_worlds(worlds, GA().but(train_starts=8), 5, 3)
    assert len(plan) == 8 and [p[0] for p in plan] == [w for w in worlds for _ in range(2)]
    numbers = [int(p[1].index[p[2]]) for p in plan]
    assert numbers == list(range(3 * 8 + 1, 3 * 8 + 9))
    with pytest.raises(ValueError):
        training_worlds(worlds, GA().but(train_starts=6), 5, 3)


def test_a_quick_pilot_starts_on_the_path_then_mixes_and_the_test_reads_the_criteria(tmp_path) -> None:
    for replicate in ("1", "2"):
        stage8.main(["--phase", "pilot", "--replicate", replicate, "--quick", "--workers", "2", "--out", str(tmp_path)])
    run = tmp_path / "pilot" / "fourier1-8101"
    gens = list(csv.DictReader(open(run / "generations.csv")))
    assert [r["shade_floor"] for r in gens[:2]] == ["0.3", "1"] and all(r["shade_floor"] == "nan" for r in gens[2:])
    # the path's generations are a single-world run's
    home = stage8.world("home", True)
    fade, tighten = stage4b.path_generations(True)
    plain(home, "fourier1", stage8.cma_for(True), 8101, tmp_path / "plain", map, log=lambda _: None, stop_after=fade + tighten,
          world_for=lambda g: stage4b.training_world(home, g, fade, tighten), champion_from=fade + tighten + 1)
    with np.load(tmp_path / "plain" / "checkpoint.npz") as z:
        import json
        early = json.loads(str(z["meta"]))["history"]
    assert [float(r["best_fitness"]) for r in gens[:fade + tighten]] == pytest.approx([r["best_fitness"] for r in early], rel=1e-10)
    by = stage8.champion_by_world(run)
    assert set(by) == set(stage8.TRAINED)
    outcome = stage8.main(["--phase", "outcome", "--out", str(tmp_path)])
    assert set(outcome["runs"]) == {8101, 8102}
    summary = stage8.main(["--phase", "test", "--quick", "--out", str(tmp_path), "--worlds", "home", "spot", "tighter"])
    assert set(summary["worlds"]) == {"home", "spot", "tighter"} and summary["champions"] == ["fourier1-8101", "fourier1-8102"]
    assert [p["number"] for p in summary["predictions"]] == [1, 2, 3, 4, 5]
    for c in summary["champions"]:
        assert set(summary["reading"][c]) >= {"trained", "held", "beats", "generalist", "travels"}
    assert (tmp_path / "test" / "cells.csv").exists()
