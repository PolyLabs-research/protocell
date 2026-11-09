"""Stage 5b's walk calculator: deterministic, a still cell never arrives, and B5 drifts toward the light."""

import math

from experiments import stage5b
from experiments.stage5b_walk import Rule, crossing, walk


def test_walk_is_deterministic_and_b5_drifts_toward_the_light():
    cfg = stage5b.world(False)
    make = lambda: Rule(cfg, 30.0)
    a = walk(cfg, make, 4000.0, 3.0, seed=1, ticks=3000)
    b = walk(cfg, make, 4000.0, 3.0, seed=1, ticks=3000)
    assert a["reached"] == b["reached"] and (a["cos"] == b["cos"]).all() and (a["run"] == b["run"]).all()
    r = walk(cfg, make, 4000.0, 3.0, seed=1, ticks=3000, stop_at_goal=False)
    cos, on = r["cos"], r["run"]
    assert on[cos > 0.7].mean() > on[cos < -0.7].mean() + 0.1  # B5 runs more while heading toward the light


def test_a_still_cell_never_arrives():
    cfg = stage5b.world(False)

    class Still:
        alpha, running = 0.0, False

        def beats(self, sensed, tick):
            return 0.0 * sensed

    r = walk(cfg, lambda: Still(), 4000.0, 3.0, seed=0, ticks=500)
    assert r["reached"] is None and r["beat"] == 0.0


def test_crossing_reports_hours_per_seed(tmp_path):
    cfg = stage5b.world(False)
    r = crossing(cfg, "B5:30", 2000.0, 3.0, seeds=2, ticks=2000)
    assert r["seeds"] == 2 and len(r["hours"]) == 2 and (r["reached"] == 0 or not math.isnan(r["median_h"]))
