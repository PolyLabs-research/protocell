"""Stage 4's thrift probe (docs/decisions.md D21): its worlds, free beating, the ledger, the verdict, the runner."""

from __future__ import annotations

import json
import math

import protocell  # noqa: F401
import numpy as np

from experiments import stage3, stage4_thrift as thrift, stage4a
from protocell.config import CAVE
from protocell.evolve import NOISE_CELL_ID
from protocell.sim import simulate
from protocell.world import sample_starts


def test_the_worlds_run_from_the_champions_home_to_stage_4as_world() -> None:
    assert thrift.world(*thrift.STAGE4A) == stage4a.world()
    assert thrift.world(*thrift.HOME) == stage3.configure()
    assert thrift.world(False, 0.8).eta == CAVE.eta * 0.8 and not thrift.world(False, 0.8).cave_sweep
    assert thrift.world_name(True, 0.55) == "sweep x0.55" and thrift.world_name(False, 1.0) == "fixed x1"


def test_the_starts_are_the_same_in_every_world() -> None:
    first = sample_starts(thrift.world(*thrift.STAGE4A, quick=True), "cave", 6, thrift.SEED)
    for sweep in thrift.SWEEPS:
        for gain in thrift.GAINS:
            other = sample_starts(thrift.world(sweep, gain, quick=True), "cave", 6, thrift.SEED)
            for name in ("pos", "heading", "phase", "source", "index"):
                assert np.array_equal(getattr(first, name), getattr(other, name))


def test_free_beating_leaves_every_move_the_same() -> None:
    cfg = thrift.world(*thrift.STAGE4A, quick=True)
    starts = sample_starts(cfg, "cave", 3, thrift.SEED)
    runs = [simulate(c, starts, thrift.cell_spec(c, "U2203", 3), seed=thrift.SEED, cell_ids=[NOISE_CELL_ID] * 3, ticks=400, record=True)
            for c in (cfg, cfg.but(c1=0.0))]
    assert runs[0].survived.all() and runs[1].survived.all()
    assert np.array_equal(runs[0].trajectory["pos"], runs[1].trajectory["pos"])
    assert np.array_equal(runs[0].trajectory["beat"], runs[1].trajectory["beat"])
    assert (runs[1].trajectory["energy"] >= runs[0].trajectory["energy"]).all()  # only the cost is gone
    assert (runs[1].trajectory["energy"] > runs[0].trajectory["energy"]).any()


def test_the_ledger_counts_what_the_simulation_counts() -> None:
    cfg = thrift.world(False, 1.0, quick=True)
    starts = sample_starts(cfg, "cave", 4, thrift.SEED)
    ledger = thrift.Ledger(cfg, 4)
    r = simulate(cfg, starts, thrift.cell_spec(cfg, "B8", 4), seed=thrift.SEED, cell_ids=[NOISE_CELL_ID] * 4, observe=ledger)
    ok = r.survived.astype(bool)
    assert ok.any()
    assert np.array_equal((ledger.day_ticks + ledger.night_ticks)[ok], r.lifetime[ok])
    assert np.allclose(ledger.day_soak[ok], (r.light_soaked * r.lifetime)[ok], rtol=1e-12, atol=0.0)
    assert np.allclose((ledger.day_beat + ledger.night_beat)[ok], (r.mean_beat * r.lifetime)[ok], rtol=1e-12, atol=0.0)


def test_the_break_even_light_rises_as_the_gain_falls() -> None:
    assert math.isclose(thrift.break_even_day_light(thrift.world(False, 1.0)), 1.0 / 3.0)
    assert math.isclose(thrift.break_even_day_light(thrift.world(True, 0.55)), 1.0 / (3.0 * 0.55))


def _table(free_u: float, free_f: float) -> dict:
    cells = {c: {cost: {"survival": 0.0, "day_light": 0.1} for cost in thrift.COSTS} for c in thrift.CELLS}
    table = {thrift.world_name(s, g): json.loads(json.dumps(cells)) for s in thrift.SWEEPS for g in thrift.GAINS}
    here = table[thrift.world_name(*thrift.STAGE4A)]
    here["U2203"]["free"]["survival"], here["F3202"]["free"]["survival"] = free_u, free_f
    return table


def test_the_verdict_reads_survival_with_beating_free() -> None:
    v = thrift.verdicts(_table(0.85, 0.3))
    assert v["U2203"]["verdict"] == "spending" and v["F3202"]["verdict"] == "finding"
    assert thrift.verdicts(_table(0.8, 0.5))["U2203"]["verdict"] == "spending"
    assert thrift.verdicts(_table(0.79, 0.5))["F3202"]["verdict"] == "both"


def test_the_quick_run_writes_its_tables_and_reads_its_verdicts(tmp_path) -> None:
    summary = thrift.main(["--quick", "--workers", "2", "--out", str(tmp_path)])
    assert {"per_start.csv", "table.csv", "summary.json", "manifest.json"} <= {p.name for p in tmp_path.iterdir()}
    assert set(summary["worlds"]) == {thrift.world_name(s, g) for s in thrift.SWEEPS for g in thrift.GAINS}
    assert set(summary["verdicts"]) == {"U2203", "F3202"} and [p["number"] for p in summary["predictions"]] == [1, 2, 3, 4]
    b0 = summary["worlds"]["sweep x0.55"]["B0"]
    assert b0["paid"] == b0["free"] and b0["paid"]["day_beat"] == 0.0
    assert json.loads((tmp_path / "manifest.json").read_text())["settings"]["seed"] == 23
