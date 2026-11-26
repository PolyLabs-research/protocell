"""Stage 8d (docs/prereg/stage8d.md): does time carry stage 8c's near-misses over, as it carried runs 8103 and 8104?

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage8d --phase extend --replicate 1 5 9 --workers 16
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage8d --phase test --workers 1
    .venv/bin/python -m experiments.stage8d --phase status
    .venv/bin/python -m experiments.stage8d --phase extend --quick --source /tmp/s8c/fresh --out /tmp/s8d   # the smoke test

Twelve of stage 8c's runs carried on from generation 400 to 800 on the compiled life, as stage 8b carried stage 8's
on (``experiments.stage8b.run_phase``): the eight near-misses, which do the bar's job in every trained world but
flicker, and four runs that do not follow the spot, as a control (D64's rule). Runs write
``docs/data/stage8d/extend/fourier1-<seed>/``.

The test is stage 8's, on the reference, in its nine worlds, at seed 70 (bootstrap 71): each run's champion at 800
generations and at 400, and champions 8102 and 6402 for reference. Read here: N1 (at least 5 of the 8 near-misses are
generalists at 800), N2 (at most 1 of the 4 controls is), each run at 800 less at 400, and §5's predictions.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from experiments import stage7, stage8, stage8b, stage8c
from experiments.stage1 import bootstrap_ci
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.tables import write_csv

MODE = stage8.MODE
NEAR = (8213, 8218, 8219, 8224, 8231, 8233, 8235, 8237)  # D63 A.3: every trained world but flicker
CONTROL = (8212, 8226, 8230, 8225)  # D64's rule: neither follow the spot nor are still, highest mean fitness on stage 8c's test
SEEDS = {"extend": NEAR + CONTROL}
TEST_SEED, BOOTSTRAP_SEED = 70, 71  # fresh
NEED_NEAR, MOST_CONTROL = 5, 1  # §4
REFERENCES = stage8c.REFERENCES
SOURCE = stage8c.DEFAULT_OUT / "fresh"
DEFAULT_OUT = Path("docs/data/stage8d")


def seed_for(phase: str, replicate: int) -> int:
    seeds = SEEDS[phase]
    if not 1 <= replicate <= len(seeds):
        raise SystemExit(f"{phase} has {len(seeds)} runs")
    return seeds[replicate - 1]


def group(seed: int) -> str:
    return "near" if seed in NEAR else "control"


def run_phase(replicate: int, out_root: Path, workers: int, quick: bool, stop_after: Optional[int], device: str, chunk: Optional[int],
              source: Path) -> Path:
    seed = seed_for("extend", replicate)
    return stage8b.run_phase("extend", replicate, out_root, workers, quick, stop_after, device, stage8.DEFAULT_OUT, chunk, seed=seed,
                             protocol="stage8d", source_run=source / f"{MODE}-{seed}")


def status(out_root: Path, quick: bool) -> List[Dict[str, Any]]:
    """Where each run stands, from its checkpoint."""
    rows = []
    of = stage8b.generations("extend", quick)
    for seed in SEEDS["extend"]:
        path = out_root / "extend" / f"{MODE}-{seed}" / "checkpoint.npz"
        row: Dict[str, Any] = {"seed": seed, "group": group(seed), "generation": None, "of": of, "champion": None}
        if path.exists():
            with np.load(path, allow_pickle=False) as z:
                meta = json.loads(str(z["meta"]))
            row["generation"] = meta["next_generation"]
            if meta["champion_info"]:
                row["champion"] = (meta["champion_info"]["generation"], round(meta["champion_info"]["validation_fitness"], 4),
                                   round(meta["champion_info"]["validation_survival"], 3))
        rows.append(row)
        done = "not begun" if row["generation"] is None else ("done" if row["generation"] >= of else f"at generation {row['generation']} of {of}")
        print(f"extend {seed} ({row['group']}): {done}" + (f"; champion from generation {row['champion'][0]}, validation {row['champion'][1]} "
                                                          f"(survival {row['champion'][2]:.0%})" if row["champion"] else ""), flush=True)
    return rows


def test_cells(out_root: Path, quick: bool) -> Tuple[Dict[str, np.ndarray], Dict[str, str]]:
    """Each carried-on run's champion at the end (``<seed> at <generations>``) and at the generation stage 8c ended
    (``<seed> at <that>``, kept by the carry-on), and, in a full test, the references."""
    cells: Dict[str, np.ndarray] = {}
    kind: Dict[str, str] = {}
    early, late = stage8.cma_for(quick).generations, stage8b.generations("extend", quick)
    for seed in SEEDS["extend"]:
        path = out_root / "extend" / f"{MODE}-{seed}"
        if (path / "champion.json").exists():
            cells[f"{seed} at {late}"] = np.asarray(json.loads((path / "champion.json").read_text())["genome"], dtype=np.float64)
            kind[f"{seed} at {late}"] = group(seed)
            cells[f"{seed} at {early}"] = np.asarray(json.loads((path / f"champion-at-{early}.json").read_text())["genome"], dtype=np.float64)
            kind[f"{seed} at {early}"] = f"{group(seed)} at {early}"
    if not cells:
        raise SystemExit(f"no finished runs under {out_root}")
    if not quick:
        for name, path in REFERENCES.items():
            cells[name] = np.load(path).reshape(-1)
            kind[name] = "reference"
    return cells, kind


def test_phase(out_root: Path, quick: bool, workers: int, only: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    cells, kind = test_cells(out_root, quick)
    names = [w for w in stage8.WORLDS if not only or w in only]
    manifest = build_manifest(protocol="stage8d/test", settings={"worlds": {w: {"changes": stage8.WORLDS[w][0], "gain": stage8.WORLDS[w][1]} for w in names},
                                                                 "trained": list(stage8.TRAINED), "held": list(stage8.HELD), "cells": kind,
                                                                 "near": list(NEAR), "control": list(CONTROL), "select": stage7.SELECT,
                                                                 "report": stage7.REPORT, "engine": "the reference (protocell.sim.simulate)",
                                                                 "workers": workers, "quick": quick},
                              seeds=[TEST_SEED, BOOTSTRAP_SEED], extra={"out": str(out_root / "test")})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:7.0f}s {msg}", flush=True)

    jobs = [{"world": w, "quick": quick, "cells": cells, "seed": TEST_SEED, "bootstrap": BOOTSTRAP_SEED} for w in names]
    worlds: Dict[str, Dict[str, Any]] = {}
    with ProcessPoolExecutor(max_workers=max(1, min(workers, len(jobs)))) as pool:
        for w, result, lines in pool.map(stage8b._world, jobs):  # noqa: SLF001 - stage 8b's job, with this stage's seeds
            worlds[w] = result
            for line in lines:
                log(line)
    out = out_root / "test"
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "cells.csv", ("kind", *stage7.ROW_COLUMNS),
              [{"world": w, "cell": c, "kind": kind[c], "bar": v["bar"], "bar_fitness": v["bar_fitness"], **{k: x[k] for k in x if k != "report_fitness"}}
               for w, v in worlds.items() for c, x in v["cells"].items()])
    resamples = 200 if quick else stage7.RESAMPLES

    def does(cell: str, w: str) -> bool:
        return w in worlds and worlds[w]["cells"][cell]["verdict"] == "carries B8"

    reading: Dict[str, Dict[str, Any]] = {}
    for c in cells:
        row: Dict[str, Any] = {"kind": kind[c], "trained": [w for w in stage8.TRAINED if does(c, w)], "held": [w for w in stage8.HELD if does(c, w)],
                               "beats": [w for w in worlds if worlds[w]["cells"][c]["beats"]]}
        row["generalist"] = len(row["trained"]) == len(stage8.TRAINED)
        row["travels"] = len(row["held"]) >= stage8.TRAVELS
        reading[c] = row
    early, late = stage8.cma_for(quick).generations, stage8b.generations("extend", quick)
    trained_here = [w for w in stage8.TRAINED if w in worlds]
    time_rows = []
    for i, seed in enumerate(SEEDS["extend"]):
        a, b = f"{seed} at {late}", f"{seed} at {early}"
        if a in cells and trained_here:
            d = np.concatenate([np.array(worlds[w]["cells"][a]["report_fitness"]) - np.array(worlds[w]["cells"][b]["report_fitness"]) for w in trained_here])
            mean, low, high = bootstrap_ci(d, 70_000 + i, resamples, seed=BOOTSTRAP_SEED)
            row = {"seed": seed, "group": group(seed), "later_less_earlier": mean, "low": low, "high": high,
                   "generalist_earlier": reading[b]["generalist"], "generalist_later": reading[a]["generalist"]}
            if "flicker" in worlds:
                row["flicker_share_earlier"] = worlds["flicker"]["cells"][b]["gap_share"]
                row["flicker_share_later"] = worlds["flicker"]["cells"][a]["gap_share"]
            time_rows.append(row)
    near_later = [f"{s} at {late}" for s in NEAR if f"{s} at {late}" in cells]
    control_later = [f"{s} at {late}" for s in CONTROL if f"{s} at {late}" in cells]
    near_generalists = [c for c in near_later if reading[c]["generalist"]]
    control_generalists = [c for c in control_later if reading[c]["generalist"]]
    earlier_generalists = [c for c in cells if kind[c].endswith(f"at {early}") and reading[c]["generalist"]]
    better = [r["seed"] for r in time_rows if r["later_less_earlier"] > 0.0]
    predictions = [
        (1, "N1 holds: at least 5 of the 8 near-misses are generalists at 800 generations", len(near_generalists) >= NEED_NEAR,
         {"generalists": near_generalists}),
        (2, "N2 holds: at most 1 of the 4 controls is a generalist at 800 generations", len(control_generalists) <= MOST_CONTROL,
         {"generalists": control_generalists}),
        (3, "all 12 runs are better at 800 generations than at 400 over the trained worlds", len(better) == len(SEEDS["extend"]), {"better": better}),
        (4, "on these fresh starts none of the twelve champions at 400 generations is a generalist", not earlier_generalists,
         {"generalists": earlier_generalists}),
        (5, "no control does the bar's job under the spot at 800 generations", not any("spot" in reading[c]["trained"] for c in control_later),
         {c: reading[c]["trained"] for c in control_later}),
        (6, "every near-miss that becomes a generalist also travels", all(reading[c]["travels"] for c in near_generalists),
         {c: reading[c]["held"] for c in near_generalists}),
    ]
    for v in worlds.values():
        for x in v["cells"].values():
            x.pop("report_fitness", None)
    summary = {"worlds": worlds, "reading": reading, "time": time_rows, "N1": len(near_generalists) >= NEED_NEAR, "near_generalists": near_generalists,
               "N2": len(control_generalists) <= MOST_CONTROL, "control_generalists": control_generalists, "earlier_generalists": earlier_generalists,
               "predictions": [{"number": k, "text": t, "holds": bool(h), "values": v} for k, t, h, v in predictions], "quick": quick}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0)
    write_manifest(out / "manifest.json", manifest)
    for c in cells:
        r = reading[c]
        log(f"{c} ({r['kind']}): does the job in {len(r['trained'])}/{len(stage8.TRAINED)} trained worlds and {len(r['held'])}/{len(stage8.HELD)} held back; "
            f"beats the bar in {len(r['beats'])}: {', '.join(r['beats']) or 'none'}")
    for r in time_rows:
        log(f"run {r['seed']} ({r['group']}): at {late} generations less at {early}, over the trained worlds, {r['later_less_earlier']:+.3f} "
            f"[{r['low']:+.3f}, {r['high']:+.3f}]")
    log(f"N1 (at least {NEED_NEAR} of the near-misses are generalists at {late}): {summary['N1']} ({len(near_generalists)}/{len(near_later)}); "
        f"N2 (at most {MOST_CONTROL} of the controls are): {summary['N2']} ({len(control_generalists)}/{len(control_later)})")
    for q in summary["predictions"]:
        log(f"prediction {q['number']}: {'holds' if q['holds'] else 'FAILS'}: {q['text']}")
    return summary


def main(argv: Optional[Sequence[str]] = None) -> Any:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--phase", required=True, choices=["extend", "test", "status"])
    parser.add_argument("--replicate", type=int, nargs="+", default=[1], help="one run, or several one after another")
    parser.add_argument("--workers", type=int, default=8, help="the processes a generation (or the test's worlds) is spread over")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu", help="where the compiled life runs")
    parser.add_argument("--chunk", type=int, default=None, help="the genomes in a job (default 48). It changes no result")
    parser.add_argument("--stop-after", type=int, default=None)
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--source", type=Path, default=SOURCE, help="extend: where stage 8c's runs are")
    parser.add_argument("--worlds", nargs="+", choices=list(stage8.WORLDS), help="the test in only these worlds (the smoke test)")
    args = parser.parse_args(argv)
    if args.phase == "status":
        return status(args.out, args.quick)
    stage8b.stay_awake()
    if args.phase == "test":
        return test_phase(args.out, args.quick, args.workers, args.worlds)
    return [run_phase(r, args.out, args.workers, args.quick, args.stop_after, args.device, args.chunk, args.source) for r in args.replicate]


if __name__ == "__main__":
    main(sys.argv[1:])
