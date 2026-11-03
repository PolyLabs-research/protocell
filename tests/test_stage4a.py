"""Stage 4a (docs/prereg/stage4.md): the world, the parameter choice, the checks U1-U4 on made-up numbers, the runner."""

from __future__ import annotations

import json
import math

import protocell  # noqa: F401
import numpy as np

from experiments import stage4a
from protocell.config import CAVE


def test_the_world_is_the_translucent_pool_with_the_sweep_and_the_lower_gain() -> None:
    cfg = stage4a.world()
    assert cfg.cave_sweep and cfg.cave_cycle and cfg.shade_floor == 1.0 and cfg.cave_falloff == 600.0
    assert cfg.eta == CAVE.eta * 0.55 and not math.isfinite(cfg.damage_threshold) and cfg.cloud_shade == 1.0
    assert cfg.cave_path == "mouth"


def test_a_rule_is_tuned_on_the_selection_starts_and_ties_go_to_the_first() -> None:
    sel = np.arange(2)
    runs = {("B5", "tau=3"): {"fitness": np.array([0.5, 0.5, 0.9, 0.9]), "survived": np.array([1, 0, 1, 1])},
            ("B5", "tau=10"): {"fitness": np.array([0.5, 0.5, 0.1, 0.1]), "survived": np.array([1, 1, 0, 0])},
            ("B5", "tau=30"): {"fitness": np.array([0.5, 0.5, 0.0, 0.0]), "survived": np.array([1, 1, 0, 0])}}
    assert stage4a.choose(runs, "B5", sel)[0] == "tau=10"  # equal fitness there; more survived; the first of the two ties


def _checks(b0_survival, ceiling_survival, head, low, perfect, random_survival):
    rep = np.arange(4)
    b0 = {"fitness": np.full(4, 0.2), "survived": np.array([1.0 if i < b0_survival * 4 else 0.0 for i in range(4)])}
    ceiling = {"fitness": np.full(4, 0.7), "survived": np.array([1.0 if i < ceiling_survival * 4 else 0.0 for i in range(4)])}
    chosen = {"B5": {"report_fitness": 0.7 - head, "report_survival": 0.8}, "B6 perfect": {"report_fitness": perfect}}
    random_rows = [{"mode": m, "survival": random_survival, "mean_fitness": 0.2} for m in ("uniform", "fourier1") for _ in range(10)]
    return stage4a.read_checks(b0, ceiling, chosen, "B5", (head, low, head + 0.05), random_rows, {"pass": True}, rep)


def test_the_checks_read_their_thresholds() -> None:
    good = _checks(0.0, 1.0, 0.15, 0.10, 0.65, 0.0)
    assert all(good[c]["pass"] for c in ("U1", "U2", "U3", "U4", "U5"))
    assert abs(good["U2"]["share_of_room"] - 0.15 / 0.5) < 1e-12 and abs(good["U3"]["recovered_share"] - 0.1 / 0.15) < 1e-12
    assert not _checks(0.25, 1.0, 0.15, 0.10, 0.65, 0.0)["U1"]["pass"]  # sitting survives a quarter of starts
    assert not _checks(0.0, 0.75, 0.15, 0.10, 0.65, 0.0)["U1"]["pass"]  # the ceiling dies on a quarter
    assert not _checks(0.0, 1.0, 0.09, 0.06, 0.65, 0.0)["U2"]["pass"]  # too little room
    assert not _checks(0.0, 1.0, 0.15, 0.04, 0.65, 0.0)["U2"]["pass"]  # the interval reaches below 0.05
    assert not _checks(0.0, 1.0, 0.15, 0.10, 0.60, 0.0)["U3"]["pass"]  # perfect reading recovers a third
    assert not _checks(0.0, 1.0, 0.15, 0.10, 0.65, 0.9)["U4"]["pass"]  # random genomes survive as well as the bar


def test_the_quick_run_writes_its_tables_and_reads_its_checks(tmp_path) -> None:
    summary = stage4a.main(["--quick", "--workers", "2", "--out", str(tmp_path)])
    assert {"grid.csv", "per_start.csv", "random_genomes.csv", "summary.json", "manifest.json"} <= {p.name for p in tmp_path.iterdir()}
    assert set(summary["checks"]) == {"U1", "U2", "U3", "U4", "U5"} and [p["number"] for p in summary["predictions"]] == list(range(1, 7))
    assert summary["bar"]["rule"] in stage4a.SIMPLE and summary["checks"]["U5"]["pass"]
    assert set(summary["rules"]) >= {"U2203", "F3202", "B6 perfect", "B0", "B7"}
    assert json.loads((tmp_path / "manifest.json").read_text())["settings"]["seed"] == 18
