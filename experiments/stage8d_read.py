"""Stage 8d's reading probe (docs/prereg/stage8d.md §7): the fifteen runs of stage 8c that follow the spot, read beside
each other. Are they all circlers, and does the running of the eight that fall short under flicker break more often
than the seven generalists'?

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage8d_read
    .venv/bin/python -m experiments.stage8d_read --quick --out /tmp/s8dr   # the smoke test: not a result

Each run's champion at 400 generations (stage 8c's), on 60 fresh starts in each of the four trained worlds at seed 72,
with shared noise, one process, on the reference, with stage 8b's probe's movement measures (D61): the share of the
day running, the turning during runs, the running and the speed toward the light in dim light, the fresh onsets a life.

Writes docs/data/stage8d/read/. The plan and predictions are in docs/prereg/stage8d.md §7, written before this ran.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from experiments import stage8, stage8b_read, stage8c
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.tables import write_csv
from protocell.world import sample_starts

SEED = 72  # fresh
STARTS = 60
GENERALISTS = (8211, 8215, 8220, 8223, 8227, 8238, 8240)  # D63 A.1
NEAR = (8213, 8218, 8219, 8224, 8231, 8233, 8235, 8237)  # D63 A.3
RUNS = stage8c.DEFAULT_OUT / "fresh"
DEFAULT_OUT = Path("docs/data/stage8d/read")


def genomes(root: Path = RUNS) -> Dict[str, np.ndarray]:
    return {str(s): np.asarray(json.loads((root / f"{stage8.MODE}-{s}" / "champion.json").read_text())["genome"], dtype=np.float64)
            for s in GENERALISTS + NEAR}


def median(rows: Dict[str, Dict[str, Any]], who: Sequence[int], key: str) -> float:
    return float(statistics.median(rows[str(s)][key] for s in who))


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    quick = args.quick
    worlds = {w: stage8.world(w, quick) for w in stage8.TRAINED}
    cells = genomes()
    n = 4 if quick else STARTS
    manifest = build_manifest(protocol="stage8d/read", settings={"worlds": list(worlds), "generalists": list(GENERALISTS), "near": list(NEAR), "starts": n,
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
            r = stage8b_read.run(cfg, starts, g, observe=True)
            m = stage8b_read.movement(name, w, r, n)
            m["group"] = "generalist" if int(name) in GENERALISTS else "near"
            moves.append(m)
            M[w][name] = m
            log(f"{w} {name} ({m['group']}): fitness {m['fitness']:.3f} ({m['survival']:.0%}); running by day {m['running_by_day']:.0%}, in dim light "
                f"{m['running_in_dim']:.0%}; turning {m['turning_during_runs']:+.3f} rad a tick; fresh onsets a life {m['fresh_onsets_a_life']:.1f}")
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "movement.csv", ("world", "cell", "group", "fitness", "survival", "running_by_day", "running_in_dim", "toward_in_dim",
                                          "turning_during_runs", "fresh_onsets_a_life"), moves)
    home, flicker, spot = M["home"], M["flicker"], M["spot"]
    circlers = [c for c in cells if stage8b_read.circles(home[c])]
    medians = {w: {g: {k: median(M[w], who, k) for k in ("running_by_day", "fresh_onsets_a_life", "turning_during_runs", "fitness")}
                   for g, who in (("generalists", GENERALISTS), ("near", NEAR))} for w in worlds}
    predictions = [
        (1, "all 15 are circlers at home: each runs more than 80% of the day and turns more than 0.03 rad a tick during runs", len(circlers) == len(cells),
         {c: {"running_by_day": home[c]["running_by_day"], "turning": home[c]["turning_during_runs"]} for c in cells}),
        (2, "under flicker the eight's running breaks more often: their median fresh onsets a life is above the seven's",
         medians["flicker"]["near"]["fresh_onsets_a_life"] > medians["flicker"]["generalists"]["fresh_onsets_a_life"],
         {g: medians["flicker"][g]["fresh_onsets_a_life"] for g in ("generalists", "near")}),
        (3, "under flicker the eight run less of the day: their median share of the day running is below the seven's",
         medians["flicker"]["near"]["running_by_day"] < medians["flicker"]["generalists"]["running_by_day"],
         {g: medians["flicker"][g]["running_by_day"] for g in ("generalists", "near")}),
        (4, "at home too the eight's running breaks more often: their median fresh onsets a life is above the seven's",
         medians["home"]["near"]["fresh_onsets_a_life"] > medians["home"]["generalists"]["fresh_onsets_a_life"],
         {g: medians["home"][g]["fresh_onsets_a_life"] for g in ("generalists", "near")}),
        (5, "under the spot all 15 run more than 80% of the day", all(spot[c]["running_by_day"] > 0.8 for c in cells),
         {c: spot[c]["running_by_day"] for c in cells}),
    ]
    summary = {"movement": M, "circlers": circlers, "medians": medians,
               "predictions": [{"number": k, "text": t, "holds": bool(h), "values": v} for k, t, h, v in predictions], "quick": quick}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0)
    write_manifest(args.out / "manifest.json", manifest)
    log(f"circlers at home: {len(circlers)} of {len(cells)}")
    for w in worlds:
        log(f"{w}: medians, generalists against near-misses: " + "; ".join(
            f"{k} {medians[w]['generalists'][k]:.3f} / {medians[w]['near'][k]:.3f}" for k in ("running_by_day", "fresh_onsets_a_life", "fitness")))
    for q in summary["predictions"]:
        log(f"prediction {q['number']}: {'holds' if q['holds'] else 'FAILS'}: {q['text']}")
    return summary


if __name__ == "__main__":
    main(sys.argv[1:])
