"""Stage 5c (docs/prereg/stage5c.md): the seeds and steps, the start at design 16, a quick pilot and its rule."""

from __future__ import annotations

import csv
import json

import numpy as np
import protocell  # noqa: F401
import pytest

from experiments import stage4e, stage5b, stage5c
from protocell.cmaes import CMA, normalised, run, to_genomes


def test_the_seeds_the_steps_and_the_search() -> None:
    assert stage5c.seed_for("pilot", "fourier1", 1) == 1601 and stage5c.seed_for("pilot", "fourier1", 2) == 1602
    assert stage5c.seed_for("confirm", "fourier1", 3) == 3603
    cma = stage5c.cma_for("pilot", 1601, False)
    assert cma.population == 96 and cma.generations == 200 and cma.train_starts == 8
    assert cma.sigma0 == 0.002 and cma.validation_seed == 32 and cma.validation_starts == 48
    assert stage5c.cma_for("pilot", 1602, False).sigma0 == 0.005
    with pytest.raises(SystemExit):
        stage5c.seed_for("pilot", "uniform", 1)
    with pytest.raises(SystemExit):
        stage5c.seed_for("pilot", "fourier1", 3)
    assert stage5c.cma_for("confirm", 3601, False).sigma0 == 0.005  # the pilot's outcome


def test_a_genome_goes_to_the_strategys_coordinates_and_back() -> None:
    cfg = stage5b.world(True)
    g = stage4e.genome(cfg, stage4e.load(stage5c.SEED_DESIGN))
    u = normalised(cfg, "fourier1", g)
    assert u.min() >= 0.0 and u.max() <= 1.0
    assert np.allclose(to_genomes(cfg, "fourier1", u[None])[0], g, atol=1e-12)
    with pytest.raises(ValueError):
        normalised(cfg, "fourier1", g + 100.0)


def test_a_run_starts_at_design_16_and_resumes_to_the_same_bits(tmp_path) -> None:
    cfg = stage5b.world(True)
    g = stage4e.genome(cfg, stage4e.load(stage5c.SEED_DESIGN))
    cma = CMA.quick().but(sigma0=0.002, validation_seed=32)
    whole = run(cfg, "fourier1", cma, 7, tmp_path / "whole", map, log=lambda _: None, start=g)
    run(cfg, "fourier1", cma, 7, tmp_path / "parts", map, log=lambda _: None, start=g, stop_after=1)
    parts = run(cfg, "fourier1", cma, 7, tmp_path / "parts", map, log=lambda _: None, start=g)
    assert whole["validation"][0]["generation"] == 0 and whole["validation"][0]["champion"] == 0
    assert json.dumps(whole["validation"]) == json.dumps(parts["validation"])
    assert np.array_equal(whole["strategy"].mean, parts["strategy"].mean)
    first = to_genomes(cfg, "fourier1", np.load(tmp_path / "whole" / "checkpoint.npz")["samples"])
    span = np.ptp(np.stack([first.min(axis=0), first.max(axis=0), g]), axis=0)
    assert np.all(span <= 0.1 * (np.abs(g) + 20.0))  # the last samples sit around design 16, not around a random genome


def test_a_quick_pilot_and_its_rule(tmp_path) -> None:
    for replicate in ("1", "2"):
        stage5c.main(["--phase", "pilot", "--replicate", replicate, "--quick", "--workers", "2", "--out", str(tmp_path)])
    rows = list(csv.DictReader(open(tmp_path / "pilot" / "fourier1-1601" / "validation.csv")))
    assert rows[0]["generation"] == "0" and rows[0]["rank"] == "0"
    gens = list(csv.DictReader(open(tmp_path / "pilot" / "fourier1-1601" / "generations.csv")))
    assert all(r["shade_floor"] == "1" for r in gens) and abs(float(gens[0]["sigma"]) - 0.002) < 1e-12
    outcome = stage5c.main(["--phase", "outcome", "--quick", "--out", str(tmp_path)])
    assert set(outcome["runs"]) == {1601, 1602}
    assert outcome["confirm_step"] in (None, 0.002, 0.005)
    for r in outcome["runs"].values():
        assert r["holds"] == (r["mean_last"] >= r["start"] - stage5c.DELTA)


def test_runs_then_the_test_reads_the_criteria(tmp_path) -> None:
    stage5c.main(["--phase", "pilot", "--replicate", "1", "--quick", "--workers", "2", "--out", str(tmp_path)])
    for replicate in ("1", "2", "3"):
        stage5c.main(["--phase", "confirm", "--replicate", replicate, "--quick", "--workers", "2", "--out", str(tmp_path)])
    summary = stage5c.main(["--phase", "test", "--quick", "--workers", "2", "--out", str(tmp_path)])
    mine = summary["stage5c"]
    assert summary["verdicts"]["fourier1"]["champions"] == 3  # design 16 and the pilot's champion stay outside the verdict
    assert "design16" in mine["fitness"] and "B8" in mine["fitness"]
    assert len(mine["champion_minus_design16"]) == 4 and [p["number"] for p in mine["predictions"]] == [3, 4, 5]
    assert set(mine["gene_movement"]["fourier1-3601"]) == {*stage5c.GENE_GROUPS, "all"}
    assert all(0.0 <= v < 0.2 for v in mine["gene_movement"]["fourier1-3601"].values())  # a search this local stays near its start
    assert "intact - (core)" in mine["parts"] and (tmp_path / "test" / "stage5c.json").exists()
    # stage 5c's readings agree with stage 4b's on the same files (a misread verdict column once made them differ)
    v = summary["verdicts"]["fourier1"]
    assert len(mine["champions_beating_B8"]) == v["beat_the_bar"] and mine["Q1"] == v["Q1"]
    for part, needed in v["Q2_needed"].items():
        assert mine["parts"][part]["needed_by_champions"] == needed
    assert stage5c.main(["--phase", "read", "--quick", "--out", str(tmp_path)]) == mine
    assert stage5c._yes("1") and stage5c._yes("True") and not stage5c._yes("0") and not stage5c._yes("False")


def test_design_16_has_not_moved_from_itself() -> None:
    cfg = stage5b.world(True)
    g = stage4e.genome(cfg, stage4e.load(stage5c.SEED_DESIGN))
    assert all(v == 0.0 for v in stage5c.gene_movement(cfg, g, g).values())
