"""Stage 8e (docs/prereg/stage8e.md): the rate of generalists at 800 generations from runs nobody chose. The other
eighteen of stage 8c's thirty runs carried on to 800 generations, as stage 8d carried twelve, so that all thirty are
there; then all thirty champions at 800 tested together.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage8e --phase extend --replicate 1 7 13 --workers 16
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage8e --phase test --workers 1
    .venv/bin/python -m experiments.stage8e --phase status
    .venv/bin/python -m experiments.stage8e --phase extend --quick --source /tmp/s8c/fresh --out /tmp/s8e   # the smoke test

Runs write ``docs/data/stage8e/extend/fourier1-<seed>/``. The test is stage 8's, on the reference, in its nine worlds,
at seed 75 (bootstrap 76): the thirty champions at 800 generations (eighteen from here, twelve from stage 8d), and
champions 8102 and 6402 for reference. Read here: H (at least 15 of the 30 are generalists at 800), the rate with its
interval, the forecast from each run's circling at 400 (§3), and §6's predictions.
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

from experiments import stage7, stage8, stage8b, stage8c, stage8d, stage8d_read, stage8e_read
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.tables import write_csv

MODE = stage8.MODE
GENERALISTS = stage8d_read.GENERALISTS  # stage 8c's generalists at 400 (D63)
NEAR = stage8d.NEAR  # carried on by stage 8d
CONTROL = stage8d.CONTROL  # carried on by stage 8d
SHADED, STILL = stage8e_read.SHADED, stage8e_read.STILL
SEEDS = {"extend": GENERALISTS + SHADED + STILL}  # the eighteen not carried on before
ALL = tuple(sorted(GENERALISTS + NEAR + CONTROL + SHADED + STILL))  # all thirty of stage 8c's runs
TEST_SEED, BOOTSTRAP_SEED = 75, 76  # fresh
NEED = 15  # §5: a half of the thirty
REFERENCES = stage8c.REFERENCES
SOURCE = stage8c.DEFAULT_OUT / "fresh"
EARLIER_RUNS = stage8d.DEFAULT_OUT / "extend"  # stage 8d's twelve
READING = stage8e_read.DEFAULT_OUT / "summary.json"
DEFAULT_OUT = Path("docs/data/stage8e")


def seed_for(phase: str, replicate: int) -> int:
    seeds = SEEDS[phase]
    if not 1 <= replicate <= len(seeds):
        raise SystemExit(f"{phase} has {len(seeds)} runs")
    return seeds[replicate - 1]


def group(seed: int) -> str:
    return ("generalist at 400" if seed in GENERALISTS else "near-miss" if seed in NEAR else "control" if seed in CONTROL
            else "shaded only" if seed in SHADED else "still")


def forecast(reading: Path = READING) -> Dict[int, bool]:
    """§3's forecast, from the reading at 400 generations: a run that followed the spot at 400 (stage 8c's generalists
    and near-misses) is a generalist at 800; a run that did not is one at 800 if and only if it circled at 400."""
    circlers = {int(c) for c in json.loads(reading.read_text())["circlers"] if c.isdigit() and int(c) in ALL}
    return {s: (s in GENERALISTS or s in NEAR or s in circlers) for s in ALL}


def run_phase(replicate: int, out_root: Path, workers: int, quick: bool, stop_after: Optional[int], device: str, chunk: Optional[int],
              source: Path) -> Path:
    seed = seed_for("extend", replicate)
    return stage8b.run_phase("extend", replicate, out_root, workers, quick, stop_after, device, stage8.DEFAULT_OUT, chunk, seed=seed,
                             protocol="stage8e", source_run=source / f"{MODE}-{seed}")


def status(out_root: Path, quick: bool) -> List[Dict[str, Any]]:
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


def test_cells(out_root: Path, earlier_root: Path, quick: bool) -> Tuple[Dict[str, np.ndarray], Dict[str, str]]:
    """Every run's champion at 800 generations that is there (``<seed> at 800``), from here or from stage 8d, and, in a
    full test, the references."""
    late = stage8b.generations("extend", quick)
    cells: Dict[str, np.ndarray] = {}
    kind: Dict[str, str] = {}
    for seed in ALL:
        root = out_root / "extend" if seed in SEEDS["extend"] else earlier_root
        path = root / f"{MODE}-{seed}" / "champion.json"
        if path.exists():
            cells[f"{seed} at {late}"] = np.asarray(json.loads(path.read_text())["genome"], dtype=np.float64)
            kind[f"{seed} at {late}"] = group(seed)
    if not cells:
        raise SystemExit(f"no finished runs under {out_root} or {earlier_root}")
    if not quick:
        for name, path in REFERENCES.items():
            cells[name] = np.load(path).reshape(-1)
            kind[name] = "reference"
    return cells, kind


def test_phase(out_root: Path, quick: bool, workers: int, earlier_root: Path = EARLIER_RUNS, reading: Path = READING,
               only: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    cells, kind = test_cells(out_root, earlier_root, quick)
    names = [w for w in stage8.WORLDS if not only or w in only]
    told = forecast(reading)
    manifest = build_manifest(protocol="stage8e/test", settings={"worlds": {w: {"changes": stage8.WORLDS[w][0], "gain": stage8.WORLDS[w][1]} for w in names},
                                                                 "trained": list(stage8.TRAINED), "held": list(stage8.HELD), "cells": kind,
                                                                 "forecast": {str(k): v for k, v in told.items()}, "select": stage7.SELECT,
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

    def does(cell: str, w: str) -> bool:
        return w in worlds and worlds[w]["cells"][cell]["verdict"] == "carries B8"

    reading_rows: Dict[str, Dict[str, Any]] = {}
    for c in cells:
        row: Dict[str, Any] = {"kind": kind[c], "trained": [w for w in stage8.TRAINED if does(c, w)], "held": [w for w in stage8.HELD if does(c, w)],
                               "beats": [w for w in worlds if worlds[w]["cells"][c]["beats"]]}
        row["generalist"] = len(row["trained"]) == len(stage8.TRAINED)
        row["travels"] = len(row["held"]) >= stage8.TRAVELS
        reading_rows[c] = row
    runs = [c for c in cells if kind[c] != "reference"]
    generalists = [c for c in runs if reading_rows[c]["generalist"]]
    k, n = len(generalists), len(runs)
    low, high = stage8b.wilson(k, n)
    seed_of = {c: int(c.split()[0]) for c in runs}
    right = {c: reading_rows[c]["generalist"] == told[seed_of[c]] for c in runs}
    non_followers = [c for c in runs if kind[c] in ("control", "shaded only", "still")]
    by_group = {g: {"runs": sum(kind[c] == g for c in runs), "generalists": sum(kind[c] == g and reading_rows[c]["generalist"] for c in runs)}
                for g in ("generalist at 400", "near-miss", "control", "shaded only", "still")}
    predictions = [
        (1, f"H holds: at least {NEED} of the 30 are generalists at 800 generations", k >= NEED, {"generalists": k, "of": n}),
        (2, "between 15 and 19 of the 30 are generalists at 800 generations", 15 <= k <= 19, {"generalists": k}),
        (3, "all 7 of stage 8c's generalists at 400 are generalists at 800", by_group["generalist at 400"]["generalists"] == len(GENERALISTS),
         by_group["generalist at 400"]),
        (4, "the forecast from circling is right for at least 13 of the 15 runs that did not follow the spot at 400",
         sum(right[c] for c in non_followers) >= 13, {c: {"forecast": told[seed_of[c]], "generalist": reading_rows[c]["generalist"]} for c in non_followers}),
        (5, "no still cell is a generalist at 800 generations", by_group["still"]["generalists"] == 0, by_group["still"]),
        (6, "every generalist at 800 travels", all(reading_rows[c]["travels"] for c in generalists), {c: reading_rows[c]["held"] for c in generalists}),
    ]
    for v in worlds.values():
        for x in v["cells"].values():
            x.pop("report_fitness", None)
    summary = {"worlds": worlds, "reading": reading_rows, "generalists": generalists, "runs": n, "H": k >= NEED,
               "rate": {"count": k, "of": n, "low": low, "high": high}, "by_group": by_group,
               "forecast": {c: {"forecast": told[seed_of[c]], "generalist": reading_rows[c]["generalist"], "right": right[c]} for c in runs},
               "forecast_right": sum(right.values()), "forecast_right_non_followers": sum(right[c] for c in non_followers),
               "predictions": [{"number": i, "text": t, "holds": bool(h), "values": v} for i, t, h, v in predictions], "quick": quick}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0)
    write_manifest(out / "manifest.json", manifest)
    for c in cells:
        r = reading_rows[c]
        log(f"{c} ({r['kind']}): does the job in {len(r['trained'])}/{len(stage8.TRAINED)} trained worlds and {len(r['held'])}/{len(stage8.HELD)} held back; "
            f"beats the bar in {len(r['beats'])}: {', '.join(r['beats']) or 'none'}")
    log(f"generalists at 800 generations: {k} of {n} ({low:.0%} to {high:.0%}); H (at least {NEED}): {summary['H']}; by group: "
        + "; ".join(f"{g} {v['generalists']}/{v['runs']}" for g, v in by_group.items()))
    log(f"the forecast from circling: right for {summary['forecast_right']} of {n}, and for {summary['forecast_right_non_followers']} of "
        f"{len(non_followers)} that did not follow the spot")
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
    parser.add_argument("--earlier", type=Path, default=EARLIER_RUNS, help="test: where stage 8d's carried-on runs are")
    parser.add_argument("--reading", type=Path, default=READING, help="test: the reading the forecast is made from")
    parser.add_argument("--worlds", nargs="+", choices=list(stage8.WORLDS), help="the test in only these worlds (the smoke test)")
    args = parser.parse_args(argv)
    if args.phase == "status":
        return status(args.out, args.quick)
    stage8b.stay_awake()
    if args.phase == "test":
        return test_phase(args.out, args.quick, args.workers, args.earlier, args.reading, args.worlds)
    return [run_phase(r, args.out, args.workers, args.quick, args.stop_after, args.device, args.chunk, args.source) for r in args.replicate]


if __name__ == "__main__":
    main(sys.argv[1:])
