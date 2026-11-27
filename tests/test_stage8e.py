"""Stage 8e (docs/prereg/stage8e.md): the eighteen runs are the rest of stage 8c's, the forecast is the plan's rule, a
run is carried on from stage 8c's checkpoint, and the test reads all thirty."""

from __future__ import annotations

import json

import protocell  # noqa: F401
import pytest

pytest.importorskip("numba")

from experiments import stage8, stage8c, stage8d, stage8e  # noqa: E402


def test_the_eighteen_are_the_rest_of_stage_8c() -> None:
    assert set(stage8e.SEEDS["extend"]) == set(stage8c.SEEDS["fresh"]) - set(stage8d.SEEDS["extend"])
    assert len(stage8e.SEEDS["extend"]) == 18 and len(stage8e.ALL) == 30 and set(stage8e.ALL) == set(stage8c.SEEDS["fresh"])
    assert stage8e.seed_for("extend", 1) == 8211 and stage8e.seed_for("extend", 18) == 8228
    with pytest.raises(SystemExit):
        stage8e.seed_for("extend", 19)
    s = json.loads((stage8c.DEFAULT_OUT / "test" / "summary.json").read_text())
    assert sorted(int(c) for c in s["generalists"]) == sorted(stage8e.GENERALISTS)
    used = {48, 54, 55, 65, 66, 67, 70, 71, 72, 73}
    assert {stage8e.TEST_SEED, stage8e.BOOTSTRAP_SEED}.isdisjoint(used)
    assert all((stage8e.SOURCE / f"fourier1-{s}" / "checkpoint.npz").exists() for s in stage8e.SEEDS["extend"])


def test_the_forecast_is_the_plans_rule(tmp_path) -> None:
    reading = tmp_path / "summary.json"
    reading.write_text(json.dumps({"circlers": ["8212", "8221", "8101"]}))
    told = stage8e.forecast(reading)
    assert set(told) == set(stage8e.ALL)
    assert all(told[s] for s in stage8e.GENERALISTS + stage8e.NEAR)  # followed the spot at 400
    assert told[8212] and told[8221] and not told[8226] and not told[8217]  # did not: as they circled


def test_a_run_is_carried_on_and_the_test_reads_the_rate(tmp_path) -> None:
    s8c, out, earlier = tmp_path / "stage8c", tmp_path / "stage8e", tmp_path / "none"
    for seed in (8211, 8214):
        stage8c.main(["--phase", "fresh", "--replicate", str(seed - 8210), "--quick", "--workers", "2", "--out", str(s8c)])
    first = stage8.cma_for(True).generations
    stage8e.main(["--phase", "extend", "--replicate", "1", "8", "--quick", "--workers", "2", "--out", str(out), "--source", str(s8c / "fresh")])
    run = out / "extend" / "fourier1-8214"
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["protocol"] == "stage8e/extend" and manifest["seeds"] == [8214]
    assert len((run / "generations.csv").read_text().splitlines()) == 1 + 2 * first
    rows = stage8e.main(["--phase", "status", "--quick", "--out", str(out)])
    assert [(r["seed"], r["group"]) for r in rows if r["generation"]] == [(8211, "generalist at 400"), (8214, "shaded only")]
    reading = tmp_path / "reading.json"
    reading.write_text(json.dumps({"circlers": ["8214"]}))
    earlier.mkdir()
    summary = stage8e.main(["--phase", "test", "--quick", "--workers", "2", "--out", str(out), "--earlier", str(earlier), "--reading", str(reading),
                            "--worlds", "home", "flicker"])
    cells = [f"8211 at {2 * first}", f"8214 at {2 * first}"]
    assert list(summary["reading"]) == cells and summary["runs"] == 2
    assert summary["forecast"][cells[1]]["forecast"] is True and [p["number"] for p in summary["predictions"]] == [1, 2, 3, 4, 5, 6]
    assert summary["by_group"]["generalist at 400"]["runs"] == 1 and summary["by_group"]["shaded only"]["runs"] == 1
    assert (out / "test" / "cells.csv").read_text().splitlines()[0].startswith("kind,world,cell")
