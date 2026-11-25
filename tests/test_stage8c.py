"""Stage 8c (docs/prereg/stage8c.md): thirty more fresh runs under their own seeds, and the test's reading of the rate."""

from __future__ import annotations

import json

import protocell  # noqa: F401
import pytest

pytest.importorskip("numba")

from experiments import stage8, stage8b, stage8c  # noqa: E402


def test_the_runs_their_seeds_and_the_bars() -> None:
    seeds = stage8c.SEEDS["fresh"]
    assert seeds == tuple(range(8211, 8241)) and len(seeds) == 30
    assert not set(seeds) & (set(stage8b.SEEDS["fresh"]) | set(stage8b.SEEDS["extend"]))
    assert stage8c.seed_for("fresh", 1) == 8211 and stage8c.seed_for("fresh", 30) == 8240
    with pytest.raises(SystemExit):
        stage8c.seed_for("fresh", 31)
    assert (stage8c.NEED_HALF, stage8c.NEED_BAR) == (15, 18) and stage8c.EARLIER == (6, 15)
    used = {stage8.TEST_SEED, stage8.BOOTSTRAP_SEED, stage8.VALIDATION_SEED, stage8b.TEST_SEED, stage8b.BOOTSTRAP_SEED}
    assert {stage8c.TEST_SEED, stage8c.BOOTSTRAP_SEED}.isdisjoint(used)
    assert all(path.exists() for path in stage8c.REFERENCES.values())


def test_a_run_is_stage_8bs_fresh_run_under_its_own_seed_and_the_test_reads_the_rate(tmp_path) -> None:
    out = tmp_path / "stage8c"
    stage8c.main(["--phase", "fresh", "--replicate", "1", "2", "--quick", "--workers", "2", "--out", str(out)])
    run = out / "fresh" / "fourier1-8211"
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["protocol"] == "stage8c/fresh" and manifest["seeds"] == [8211] and "compiled life" in manifest["settings"]["engine"]
    # the same runner and settings as stage 8b's fresh runs: only the seed differs
    stage8b.main(["--phase", "fresh", "--replicate", "1", "--quick", "--workers", "2", "--out", str(tmp_path / "stage8b")])
    other = json.loads((tmp_path / "stage8b" / "fresh" / "fourier1-8201" / "manifest.json").read_text())
    assert {k: v for k, v in manifest["settings"].items()} == {k: v for k, v in other["settings"].items()}
    assert json.loads((run / "champion.json").read_text())["genome"] != json.loads((tmp_path / "stage8b" / "fresh" / "fourier1-8201" / "champion.json").read_text())["genome"]

    rows = stage8c.main(["--phase", "status", "--quick", "--out", str(out)])
    assert [r["seed"] for r in rows if r["generation"]] == [8211, 8212] and len(rows) == 30

    summary = stage8c.main(["--phase", "test", "--quick", "--workers", "2", "--out", str(out), "--worlds", "home", "spot", "tighter"])
    assert list(summary["reading"]) == ["8211", "8212"] and summary["runs"] == 2
    assert [p["number"] for p in summary["predictions"]] == [1, 2, 3, 4, 5, 6, 7]
    assert summary["rate_pooled"]["of"] == 2 + 15 and summary["rate_pooled"]["count"] == len(summary["generalists"]) + 6
    assert summary["E1"] is False and summary["E2"] is False  # two runs cannot reach fifteen
    for c in summary["reading"]:
        assert set(summary["reading"][c]) >= {"trained", "held", "beats", "generalist", "travels", "still"}
    assert (out / "test" / "cells.csv").read_text().splitlines()[0].startswith("kind,world,cell")
