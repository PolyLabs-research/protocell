"""Stage 8d (docs/prereg/stage8d.md): the twelve runs and the rule that chose the controls, a run carried on from stage
8c's checkpoint, and the test's reading."""

from __future__ import annotations

import json

import protocell  # noqa: F401
import pytest

pytest.importorskip("numba")

from experiments import stage8, stage8b, stage8c, stage8d  # noqa: E402


def test_the_runs_are_stage_8cs_near_misses_and_the_controls_its_rule() -> None:
    s = json.loads((stage8c.DEFAULT_OUT / "test" / "summary.json").read_text())
    W, fresh = s["worlds"], {c: r for c, r in s["reading"].items() if r["kind"] == "fresh"}
    near = sorted(int(c) for c, r in fresh.items() if not r["generalist"] and len(r["trained"]) == 3 and "flicker" not in r["trained"])
    assert tuple(near) == stage8d.NEAR
    others = [c for c, r in fresh.items() if "spot" not in r["trained"] and r["trained"]]
    mean = {c: sum(W[w]["cells"][c]["fitness"] for w in stage8.TRAINED) / 4 for c in others}
    assert sorted(int(c) for c in sorted(mean, key=lambda c: -mean[c])[:4]) == sorted(stage8d.CONTROL)
    assert stage8d.SEEDS["extend"] == stage8d.NEAR + stage8d.CONTROL and stage8d.seed_for("extend", 9) == 8212
    with pytest.raises(SystemExit):
        stage8d.seed_for("extend", 13)
    used = {stage8.TEST_SEED, stage8.BOOTSTRAP_SEED, stage8b.TEST_SEED, stage8b.BOOTSTRAP_SEED, stage8c.TEST_SEED, stage8c.BOOTSTRAP_SEED, 67, 72}
    assert {stage8d.TEST_SEED, stage8d.BOOTSTRAP_SEED}.isdisjoint(used)
    assert all((stage8d.SOURCE / f"fourier1-{seed}" / "checkpoint.npz").exists() for seed in stage8d.SEEDS["extend"])


def test_a_run_is_carried_on_from_stage_8c_and_the_test_reads_it(tmp_path) -> None:
    s8c, out = tmp_path / "stage8c", tmp_path / "stage8d"
    for seed in (8213, 8212):
        stage8c.main(["--phase", "fresh", "--replicate", str(seed - 8210), "--quick", "--workers", "2", "--out", str(s8c)])
    first = stage8.cma_for(True).generations
    stage8d.main(["--phase", "extend", "--replicate", "1", "9", "--quick", "--workers", "2", "--out", str(out), "--source", str(s8c / "fresh")])
    run = out / "extend" / "fourier1-8213"
    assert json.loads((run / f"champion-at-{first}.json").read_text()) == json.loads((s8c / "fresh" / "fourier1-8213" / "champion.json").read_text())
    record = json.loads((run / "carried-on.json").read_text())
    assert record["generation"] == first and record["compiled_validation_fitness"] == pytest.approx(record["reference_validation_fitness"], abs=1e-12)
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["protocol"] == "stage8d/extend" and manifest["seeds"] == [8213]
    assert len((run / "generations.csv").read_text().splitlines()) == 1 + 2 * first
    rows = stage8d.main(["--phase", "status", "--quick", "--out", str(out)])
    assert [(r["seed"], r["group"]) for r in rows if r["generation"]] == [(8213, "near"), (8212, "control")]

    summary = stage8d.main(["--phase", "test", "--quick", "--workers", "2", "--out", str(out), "--worlds", "home", "flicker", "spot"])
    cells = [f"8213 at {2 * first}", f"8213 at {first}", f"8212 at {2 * first}", f"8212 at {first}"]
    assert list(summary["reading"]) == cells
    assert [summary["reading"][c]["kind"] for c in cells] == ["near", f"near at {first}", "control", f"control at {first}"]
    assert [p["number"] for p in summary["predictions"]] == [1, 2, 3, 4, 5, 6] and len(summary["time"]) == 2
    assert all("flicker_share_later" in r for r in summary["time"])
    assert (out / "test" / "cells.csv").read_text().splitlines()[0].startswith("kind,world,cell")
