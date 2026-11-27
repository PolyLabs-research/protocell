"""Stage 8e's reading (docs/prereg/stage8e.md §2): the circling at 400 generations of the runs that did not follow the
spot, read before stage 8e's runs, so that each run's outcome at 800 can be foretold from it.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage8e_read
    .venv/bin/python -m experiments.stage8e_read --quick --out /tmp/s8er   # the smoke test: not a result

The cells, each as it stood at 400 generations: stage 8c's fifteen runs that do not follow the spot (the four that
stage 8d carried on as a control, its eight other runs that cope only when shaded, its three still cells), and stage
8b's runs 8101 and 8105, which never followed it. Read at home, where D44's rule for a circler is set, and under the
spot, on 60 fresh starts at seed 73, one process, on the reference, with stage 8b's probe's measures (D61).

Writes docs/data/stage8e/read/. The plan and predictions are in docs/prereg/stage8e.md §2, written before this ran.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from experiments import stage8, stage8b_read, stage8c, stage8d
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.tables import write_csv
from protocell.world import sample_starts

SEED = 73  # fresh
STARTS = 60
WORLDS = ("home", "spot")
CONTROL = stage8d.CONTROL  # carried on by stage 8d: 8212 crossed, the other three did not
SHADED = (8214, 8216, 8221, 8229, 8232, 8234, 8236, 8239)  # stage 8c's other runs that cope only when shaded
STILL = (8217, 8222, 8228)
EARLIER = {"8101": Path("docs/data/stage8b/extend/fourier1-8101/champion-at-400.json"),  # stage 8's, never followed the spot
           "8105": Path("docs/data/stage8b/extend/fourier1-8105/champion-at-400.json")}
DEFAULT_OUT = Path("docs/data/stage8e/read")


def genomes() -> Dict[str, np.ndarray]:
    root = stage8c.DEFAULT_OUT / "fresh"
    cells = {str(s): np.asarray(json.loads((root / f"{stage8.MODE}-{s}" / "champion.json").read_text())["genome"], dtype=np.float64)
             for s in CONTROL + SHADED + STILL}
    cells.update({k: np.asarray(json.loads(p.read_text())["genome"], dtype=np.float64) for k, p in EARLIER.items()})
    return cells


def group(name: str) -> str:
    seed = int(name)
    return "control" if seed in CONTROL else "shaded" if seed in SHADED else "still" if seed in STILL else "stage 8"


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    quick = args.quick
    worlds = {w: stage8.world(w, quick) for w in WORLDS}
    cells = genomes()
    n = 4 if quick else STARTS
    manifest = build_manifest(protocol="stage8e/read", settings={"worlds": list(worlds), "cells": {c: group(c) for c in cells}, "starts": n,
                                                                 "circler": [stage8b_read.RUNS_ALL_DAY, stage8b_read.TURNS], "quick": quick},
                              seeds=[SEED], extra={"out": str(args.out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:6.0f}s {msg}", flush=True)

    moves: List[Dict[str, Any]] = []
    M: Dict[str, Dict[str, Dict[str, Any]]] = {w: {} for w in worlds}
    for w, cfg in worlds.items():
        starts = sample_starts(cfg, "cave", n, SEED)
        for name, g in cells.items():
            m = stage8b_read.movement(name, w, stage8b_read.run(cfg, starts, g, observe=True), n)
            m["group"] = group(name)
            moves.append(m)
            M[w][name] = m
            log(f"{w} {name} ({m['group']}): fitness {m['fitness']:.3f} ({m['survival']:.0%}); running by day {m['running_by_day']:.0%}; turning "
                f"{m['turning_during_runs']:+.3f} rad a tick; fresh onsets a life {m['fresh_onsets_a_life']:.1f}")
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "movement.csv", ("world", "cell", "group", "fitness", "survival", "running_by_day", "running_in_dim", "toward_in_dim",
                                          "turning_during_runs", "fresh_onsets_a_life"), moves)
    home = M["home"]
    circlers = [c for c in cells if stage8b_read.circles(home[c])]
    shaded_circlers = [c for c in circlers if group(c) == "shaded"]
    predictions = [
        (1, "control 8212, the one that crossed, was a circler at 400 generations", "8212" in circlers,
         {"8212": {"running_by_day": home["8212"]["running_by_day"], "turning": home["8212"]["turning_during_runs"]}}),
        (2, "the three controls that did not cross were not circlers at 400", not any(str(s) in circlers for s in CONTROL if s != 8212),
         {str(s): {"running_by_day": home[str(s)]["running_by_day"], "turning": home[str(s)]["turning_during_runs"]} for s in CONTROL if s != 8212}),
        (3, "stage 8b's runs 8101 and 8105 were not circlers at 400", not any(k in circlers for k in EARLIER),
         {k: {"running_by_day": home[k]["running_by_day"], "turning": home[k]["turning_during_runs"]} for k in EARLIER}),
        (4, "at most two of stage 8c's eight other runs that cope only when shaded are circlers at 400", len(shaded_circlers) <= 2,
         {"circlers": shaded_circlers}),
        (5, "no still cell is a circler", not any(str(s) in circlers for s in STILL), {str(s): home[str(s)]["running_by_day"] for s in STILL}),
    ]
    summary = {"movement": M, "circlers": circlers, "predictions": [{"number": k, "text": t, "holds": bool(h), "values": v} for k, t, h, v in predictions],
               "quick": quick}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0)
    write_manifest(args.out / "manifest.json", manifest)
    log(f"circlers at home: {', '.join(circlers) or 'none'}")
    for q in summary["predictions"]:
        log(f"prediction {q['number']}: {'holds' if q['holds'] else 'FAILS'}: {q['text']}")
    return summary


if __name__ == "__main__":
    main(sys.argv[1:])
