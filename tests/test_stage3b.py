"""Stage 3b (docs/prereg/stage3b.md): the time-constant removals, the seeds, the runner's verdicts."""

from __future__ import annotations

import csv

import protocell  # noqa: F401
import numpy as np
import pytest

from experiments.stage3b import (DELTA, FADE_GENERATIONS, REMOVALS, SEEDS, SEEDS_AS_PREREGISTERED, VALIDATION_SEED, ga_for, main,
                                 seed_for, shade_floor_for)
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


def test_the_seeds_are_amendment_a1s() -> None:
    assert SEEDS["pilot"] == {"uniform": (1201,), "fourier1": (1202,)} and seed_for("confirm", "uniform", 3) == 2203
    assert SEEDS_AS_PREREGISTERED["pilot"] == {"uniform": (1101,), "fourier1": (1102,)}
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


def test_the_shading_fades_over_fifty_generations() -> None:
    assert FADE_GENERATIONS == 50
    assert shade_floor_for(1, 50) == pytest.approx(0.3) and shade_floor_for(26, 50) == pytest.approx(0.65)
    assert shade_floor_for(50, 50) == pytest.approx(0.3 + 0.7 * 49 / 50) and shade_floor_for(51, 50) == 1.0 and shade_floor_for(100, 50) == 1.0
    assert [shade_floor_for(g, 2) for g in (1, 2, 3)] == pytest.approx([0.3, 0.65, 1.0])


def test_each_generation_trains_in_its_world_and_the_champion_comes_after_the_fade(tmp_path) -> None:
    import json

    from experiments import stage3
    from protocell.evolve import GA, run

    cfg = stage3.configure(quick=True).but(day_ticks=400)
    ga = GA.quick()
    world = lambda g: cfg.but(shade_floor=shade_floor_for(g, 2))  # noqa: E731
    straight = run(cfg, "fourier1", ga, 5, tmp_path / "a", map, log=lambda m: None, world_for=world, champion_from=3)
    assert [r["shade_floor"] for r in straight["history"]] == pytest.approx([0.3, 0.65, 1.0])
    assert straight["champion_info"]["generation"] == 3  # the checkpoints at generations 1 and 2 cannot supply it
    assert [v["champion"] for v in straight["validation"] if v["generation"] < 3] == [0, 0, 0, 0]
    first = run(cfg, "fourier1", ga, 5, tmp_path / "b", map, log=lambda m: None, world_for=world, champion_from=3, stop_after=1)
    resumed = run(cfg, "fourier1", ga, 5, tmp_path / "b", map, log=lambda m: None, world_for=world, champion_from=3)
    assert first["next_generation"] == 1 and np.array_equal(resumed["champion"], straight["champion"])
    assert (tmp_path / "a" / "population.npy").read_bytes() == (tmp_path / "b" / "population.npy").read_bytes()
    plain = run(cfg, "fourier1", ga, 5, tmp_path / "c", map, log=lambda m: None)
    assert [r["shade_floor"] for r in plain["history"]] == [1.0, 1.0, 1.0]  # without a world for each generation, the run's own
    assert json.loads((tmp_path / "a" / "champion.json").read_text())["generation"] == 3
