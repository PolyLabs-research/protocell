"""Stage 8c (docs/prereg/stage8c.md): the rate at which a generalist emerges. Thirty more fresh runs of stage 8's
design, on the compiled life, to set beside the fifteen already made.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage8c --phase fresh --replicate 1 7 13 19 25 --workers 16
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage8c --phase test --workers 1
    .venv/bin/python -m experiments.stage8c --phase status
    .venv/bin/python -m experiments.stage8c --phase fresh --quick --out /tmp/s8c   # the smoke test: not a result

A run is one of stage 8b's fresh runs (``experiments.stage8b.run_phase``) under a new seed, 8211 to 8240: random
genomes, stage 4b's path, then four worlds at once, 400 generations. Runs write
``docs/data/stage8c/fresh/fourier1-<seed>/``.

The test is stage 8's, on the reference, in its nine worlds, at seed 65 (bootstrap 66): each run's champion, with
champions 8102 and 6402 for reference. Read here: how many of the thirty are generalists, E1 (at least half) and E2 (at
least three in five, stage 8's bar), the rate over all forty-five runs made at 400 generations, and §5's predictions.
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

from experiments import stage7, stage8, stage8b
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.tables import write_csv

MODE = stage8.MODE
SEEDS = {"fresh": tuple(range(8211, 8241))}
TEST_SEED, BOOTSTRAP_SEED = 65, 66  # fresh
EARLIER = (6, 15)  # the generalists at 400 generations among stage 8's five runs and stage 8b's ten (D58 A.5)
NEED_HALF, NEED_BAR = 15, 18  # §4: of the thirty, a half and stage 8's three in five
REFERENCES = {"champion8102": Path("docs/data/stage8/pilot/fourier1-8102/champion.npy"),
              "champion6402": Path("docs/data/stage6b/confirm/fourier1-6402/champion.npy")}
DEFAULT_OUT = Path("docs/data/stage8c")


def seed_for(phase: str, replicate: int) -> int:
    seeds = SEEDS[phase]
    if not 1 <= replicate <= len(seeds):
        raise SystemExit(f"{phase} has {len(seeds)} runs")
    return seeds[replicate - 1]


def run_phase(replicate: int, out_root: Path, workers: int, quick: bool, stop_after: Optional[int], device: str, chunk: Optional[int]) -> Path:
    return stage8b.run_phase("fresh", replicate, out_root, workers, quick, stop_after, device, stage8.DEFAULT_OUT, chunk,
                             seed=seed_for("fresh", replicate), protocol="stage8c")


def status(out_root: Path, quick: bool) -> List[Dict[str, Any]]:
    """Where each run stands, from its checkpoint."""
    rows = []
    of = stage8b.generations("fresh", quick)
    for seed in SEEDS["fresh"]:
        path = out_root / "fresh" / f"{MODE}-{seed}" / "checkpoint.npz"
        row: Dict[str, Any] = {"seed": seed, "generation": None, "of": of, "champion": None}
        if path.exists():
            with np.load(path, allow_pickle=False) as z:
                meta = json.loads(str(z["meta"]))
            row["generation"] = meta["next_generation"]
            if meta["champion_info"]:
                row["champion"] = (meta["champion_info"]["generation"], round(meta["champion_info"]["validation_fitness"], 4),
                                   round(meta["champion_info"]["validation_survival"], 3))
        rows.append(row)
        done = "not begun" if row["generation"] is None else ("done" if row["generation"] >= of else f"at generation {row['generation']} of {of}")
        print(f"fresh {seed}: {done}" + (f"; champion from generation {row['champion'][0]}, validation {row['champion'][1]} "
                                         f"(survival {row['champion'][2]:.0%})" if row["champion"] else ""), flush=True)
    return rows


def test_cells(out_root: Path, quick: bool) -> Tuple[Dict[str, np.ndarray], Dict[str, str]]:
    cells: Dict[str, np.ndarray] = {}
    kind: Dict[str, str] = {}
    for seed in SEEDS["fresh"]:
        path = out_root / "fresh" / f"{MODE}-{seed}" / "champion.json"
        if path.exists():
            cells[str(seed)] = np.asarray(json.loads(path.read_text())["genome"], dtype=np.float64)
            kind[str(seed)] = "fresh"
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
    manifest = build_manifest(protocol="stage8c/test", settings={"worlds": {w: {"changes": stage8.WORLDS[w][0], "gain": stage8.WORLDS[w][1]} for w in names},
                                                                 "trained": list(stage8.TRAINED), "held": list(stage8.HELD), "cells": kind,
                                                                 "select": stage7.SELECT, "report": stage7.REPORT, "earlier": list(EARLIER),
                                                                 "engine": "the reference (protocell.sim.simulate)", "workers": workers, "quick": quick},
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

    reading: Dict[str, Dict[str, Any]] = {}
    for c in cells:
        row: Dict[str, Any] = {"kind": kind[c], "trained": [w for w in stage8.TRAINED if does(c, w)], "held": [w for w in stage8.HELD if does(c, w)],
                               "beats": [w for w in worlds if worlds[w]["cells"][c]["beats"]]}
        row["generalist"] = len(row["trained"]) == len(stage8.TRAINED)
        row["travels"] = len(row["held"]) >= stage8.TRAVELS
        row["still"] = not row["trained"] and not row["held"]
        reading[c] = row
    fresh = [c for c in cells if kind[c] == "fresh"]
    generalists = [c for c in fresh if reading[c]["generalist"]]
    travelling = [c for c in generalists if reading[c]["travels"]]
    still = [c for c in fresh if reading[c]["still"]]
    k, n = len(generalists), len(fresh)
    pooled_k, pooled_n = k + EARLIER[0], n + EARLIER[1]
    here, pooled = stage8b.wilson(k, n), stage8b.wilson(pooled_k, pooled_n)
    predictions = [
        (1, "E1 fails: fewer than 15 of the 30 fresh runs give a generalist", k < NEED_HALF, {"generalists": k, "of": n}),
        (2, "E2 fails: fewer than 18 of the 30 do", k < NEED_BAR, {"generalists": k, "of": n}),
        (3, "between 8 and 16 of the 30 are generalists", 8 <= k <= 16, {"generalists": k}),
        (4, "the rate over all 45 runs lies between 30% and 50%", pooled_n > 0 and 0.30 <= pooled_k / pooled_n <= 0.50,
         {"generalists": pooled_k, "of": pooled_n}),
        (5, "at least nine in ten of the new generalists travel", bool(generalists) and len(travelling) >= 0.9 * len(generalists),
         {"travelling": len(travelling), "generalists": k}),
        (6, "at least one of the 30 runs ends as a still cell", bool(still), {"still": still}),
        (7, "the references stand as before: champion 8102 a generalist, champion 6402 not",
         "champion8102" in reading and reading["champion8102"]["generalist"] and not reading["champion6402"]["generalist"],
         {c: reading[c]["trained"] for c in REFERENCES if c in reading}),
    ]
    for v in worlds.values():
        for x in v["cells"].values():
            x.pop("report_fitness", None)
    summary = {"worlds": worlds, "reading": reading, "runs": n, "generalists": generalists, "travelling": travelling, "still": still,
               "E1": k >= NEED_HALF, "E2": k >= NEED_BAR, "rate_here": {"count": k, "of": n, "low": here[0], "high": here[1]},
               "rate_pooled": {"count": pooled_k, "of": pooled_n, "low": pooled[0], "high": pooled[1]},
               "predictions": [{"number": i, "text": t, "holds": bool(h), "values": v} for i, t, h, v in predictions], "quick": quick}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0)
    write_manifest(out / "manifest.json", manifest)
    for c in cells:
        r = reading[c]
        log(f"{c} ({r['kind']}): does the job in {len(r['trained'])}/{len(stage8.TRAINED)} trained worlds and {len(r['held'])}/{len(stage8.HELD)} held back; "
            f"beats the bar in {len(r['beats'])}: {', '.join(r['beats']) or 'none'}")
    log(f"generalists among these {n} fresh runs: {k} ({here[0]:.0%} to {here[1]:.0%}); E1 (at least {NEED_HALF} of 30): {summary['E1']}; "
        f"E2 (at least {NEED_BAR} of 30): {summary['E2']}")
    log(f"at 400 generations, with the {EARLIER[1]} runs made before: {pooled_k} of {pooled_n} (95% interval for the rate {pooled[0]:.0%} to {pooled[1]:.0%})")
    for q in summary["predictions"]:
        log(f"prediction {q['number']}: {'holds' if q['holds'] else 'FAILS'}: {q['text']}")
    return summary


def main(argv: Optional[Sequence[str]] = None) -> Any:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--phase", required=True, choices=["fresh", "test", "status"])
    parser.add_argument("--replicate", type=int, nargs="+", default=[1], help="one run, or several one after another")
    parser.add_argument("--workers", type=int, default=8, help="the processes a generation (or the test's worlds) is spread over")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu", help="where the compiled life runs")
    parser.add_argument("--chunk", type=int, default=None, help="the genomes in a job (default 48). It changes no result")
    parser.add_argument("--stop-after", type=int, default=None)
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--worlds", nargs="+", choices=list(stage8.WORLDS), help="the test in only these worlds (the smoke test)")
    args = parser.parse_args(argv)
    if args.phase == "status":
        return status(args.out, args.quick)
    stage8b.stay_awake()
    if args.phase == "test":
        return test_phase(args.out, args.quick, args.workers, args.worlds)
    return [run_phase(r, args.out, args.workers, args.quick, args.stop_after, args.device, args.chunk) for r in args.replicate]


if __name__ == "__main__":
    main(sys.argv[1:])
