"""The numbers stage 1's draft rests on (docs/prereg/stage1.md §2, §8), measured before it is written:

1. **Headroom:** how far each configuration's bar is below the best a cell could do. A still cell placed at the
   configuration's best fixed point pays no travel and no beating, so on the same starts it bounds what any cell that
   must first reach that place can score. Read from the cave's committed tables; nothing is simulated.
2. **Cost:** a network cell's cost a tick at the batch sizes evolution would use (this machine).

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage1_budget

Writes ``docs/data/stage1/budget/{headroom.csv, cost.csv, manifest.json}``.
"""

from __future__ import annotations

import csv
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from experiments.cave import configure
from experiments.stage0 import write_csv
from protocell.cell import random_genomes
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.rng import stream
from protocell.sim import simulate
from protocell.world import sample_starts

CAVE_DATA = Path("docs/data/cave")
OUT = Path("docs/data/stage1/budget")
BARS = {"day": "b2r_report.csv", "burn": "b2rr_report.csv", "sweep": "b2rr_report.csv"}
BATCHES = (24, 48, 96, 192)
TIMING_TICKS = 3000
PROBE_SEED = 1


def headroom(config: str) -> Dict[str, Any]:
    bar_rows = list(csv.DictReader(open(CAVE_DATA / config / BARS[config])))
    still = {int(r["start"]): r for r in csv.DictReader(open(CAVE_DATA / config / "b0_best.csv"))}
    bar = np.array([float(r["fitness"]) for r in bar_rows])
    best = np.array([float(still[int(r["start"])]["fitness"]) for r in bar_rows])
    night = np.array([int(r["phase"]) >= 43_200 for r in bar_rows])
    gap = best - bar
    return {"configuration": config, "bar": BARS[config].split("_")[0], "n": len(bar_rows), "bar_fitness": float(bar.mean()),
            "still_at_best_point": float(best.mean()), "still_survival": float(np.mean([int(still[int(r["start"])]["survived"]) for r in bar_rows])),
            "gap_mean": float(gap.mean()), "gap_sd": float(gap.std(ddof=1)), "gap_max": float(gap.max()),
            "gap_day_starts": float(gap[~night].mean()), "gap_night_starts": float(gap[night].mean())}


def cost(batch: int) -> Dict[str, Any]:
    cfg = configure("day", False)
    one = sample_starts(cfg, "cave", 1, seed=PROBE_SEED)
    genomes = random_genomes(cfg, "fourier1", batch, stream(PROBE_SEED, "genomes"))
    t0 = time.perf_counter()
    simulate(cfg, one.take([0] * batch), {"controller": "network", "mode": "fourier1", "genomes": genomes}, seed=PROBE_SEED,
             cell_ids=list(range(1, batch + 1)), ticks=TIMING_TICKS)
    dt = time.perf_counter() - t0
    return {"batch": batch, "us_per_tick": dt / TIMING_TICKS * 1e6, "us_per_cell_tick": dt / TIMING_TICKS / batch * 1e6}


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, List[Dict[str, Any]]]:
    manifest = build_manifest(protocol="stage1/budget", settings={"batches": BATCHES, "timing_ticks": TIMING_TICKS, "bars": BARS},
                              seeds=[PROBE_SEED])
    t0 = time.time()
    rooms = [headroom(c) for c in BARS]
    costs = [cost(b) for b in BATCHES]
    for r in rooms:
        print(f"{r['configuration']:5s}: bar ({r['bar']}) {r['bar_fitness']:.3f}; a still cell at the best point {r['still_at_best_point']:.3f} "
              f"(survives {r['still_survival']:.0%}); gap {r['gap_mean']:+.4f} (sd {r['gap_sd']:.4f}; day starts {r['gap_day_starts']:+.4f}, night {r['gap_night_starts']:+.4f})")
    for c in costs:
        print(f"batch {c['batch']:4d}: {c['us_per_tick']:6.1f} us a tick, {c['us_per_cell_tick']:5.2f} us a cell-tick")
    write_csv(OUT / "headroom.csv", tuple(rooms[0]), rooms)
    write_csv(OUT / "cost.csv", tuple(costs[0]), costs)
    finish_manifest(manifest, wall_seconds=time.time() - t0)
    write_manifest(OUT / "manifest.json", manifest)
    return {"headroom": rooms, "cost": costs}


if __name__ == "__main__":
    main(sys.argv[1:])
