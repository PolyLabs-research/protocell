"""Stage 8b (docs/prereg/stage8b.md): how reliably a generalist emerges, given more time and given more runs. The first
runs made on the compiled life (protocell/fast.py), on the owner's machine in place of RunPod.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage8b --phase extend --replicate 1 --workers 8
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage8b --phase fresh --replicate 1 2 3 --workers 8
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage8b --phase fresh --replicate 1 --device cuda
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage8b --phase test --workers 9
    .venv/bin/python -m experiments.stage8b --phase status           # where each run stands
    .venv/bin/python -m experiments.stage8b --phase fresh --quick --out /tmp/s8b   # the smoke test: not a result

``extend``: stage 8's five runs (seeds 8101-8105), each carried on from its checkpoint at generation 400 to generation
800. The run's champion at 400 was validated by the reference on a pod; before generation 401 it is validated again on
the compiled life, on the same starts, and that is the number later candidates must beat, so every comparison after
400 is made on one engine. ``fresh``: ten new runs of stage 8's design (seeds 8201-8210), 400 generations. A run
checkpoints after every generation and the same command carries it on. Runs write
``docs/data/stage8b/<phase>/fourier1-<seed>/``.

The test is stage 8's, on the reference, in its nine worlds, at seed 54 (bootstrap 55): each carried-on run's champion
at 800 beside its champion at 400, each fresh run's champion, and champions 6402 and 3603. Its worlds are independent,
so ``--workers`` runs them side by side. Read here: R1 (generalists at 800), R2 (each run at 800 less itself at 400),
R3 (generalists among the fresh runs), and §6's predictions.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from experiments import stage4a, stage4b, stage7, stage8
from experiments.stage1 import bootstrap_ci
from protocell import evolve, fast
from protocell.cell import genome_length
from protocell.cmaes import run
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.tables import write_csv

MODE = stage8.MODE
EXTENDED = {8101: "pilot", 8102: "pilot", 8103: "confirm", 8104: "confirm", 8105: "confirm"}  # the phase stage 8 ran each in
SEEDS = {"extend": tuple(EXTENDED), "fresh": tuple(range(8201, 8211))}
FACTOR = 2  # extend: 800 generations where stage 8 had 400
TEST_SEED, BOOTSTRAP_SEED = 54, 55  # fresh
NEED_GENERALISTS, NEED_TIME, NEED_FRESH = 3, 4, 5  # §5: R1 and R2 of the five carried on, R3 of the ten fresh
REFERENCES = stage8.REFERENCES
DEFAULT_OUT = Path("docs/data/stage8b")


def seed_for(phase: str, replicate: int) -> int:
    seeds = SEEDS[phase]
    if not 1 <= replicate <= len(seeds):
        raise SystemExit(f"{phase} has {len(seeds)} runs")
    return seeds[replicate - 1]


def generations(phase: str, quick: bool) -> int:
    base = stage8.cma_for(quick).generations
    return FACTOR * base if phase == "extend" else base


def mapper_for(device: str, pool: ProcessPoolExecutor) -> Any:
    """The searches' two jobs on the compiled life: in the pool's processes, or as one batch on the GPU."""
    if device == "cuda":
        ready, what = fast.cuda_ready()
        if not ready:
            raise SystemExit(f"no GPU: {what}")
        return fast.CudaMapper(pool.map)
    return fast.Mapper(pool.map)


def validate(genome: np.ndarray, quick: bool, seed: int, mapper: Any) -> Dict[str, float]:
    """A candidate's validation as ``protocell.cmaes.run`` reads it: the mean over every world's starts."""
    worlds = stage8.validation_worlds(quick)
    parts = list(mapper(evolve.validation_job, [{"cfg": wcfg, "mode": MODE, "seed": seed, "starts": wstarts, "genome": genome} for _, wcfg, wstarts in worlds]))
    sizes = np.array([len(wstarts) for _, _, wstarts in worlds], dtype=np.float64)
    return {k: float(np.dot([p[k] for p in parts], sizes) / sizes.sum()) for k in ("fitness", "survival", "mean_beat")}


def carry_on(source: Path, out: Path, quick: bool, mapper: Any, log: Any) -> Dict[str, Any]:
    """Begin a carried-on run: stage 8's checkpoint copied (stage 8's files are not touched), its champion kept as
    ``champion-at-<generation>.json``, and that champion validated again on the compiled life, the number written
    into the copy for later candidates to beat. What was done is kept in ``carried-on.json``."""
    out.mkdir(parents=True, exist_ok=True)
    with np.load(source / "checkpoint.npz", allow_pickle=False) as z:
        arrays = {k: z[k].copy() for k in z.files}
    meta = json.loads(str(arrays["meta"]))
    at = int(meta["next_generation"])
    if at != stage8.cma_for(quick).generations or meta["champion_info"] is None:
        raise SystemExit(f"{source} is not a finished stage 8 run with a champion (it stands at generation {at})")
    info = meta["champion_info"]
    again = validate(arrays["champion"], quick, stage8.cma_for(quick).validation_seed, mapper)
    record = {"source": str(source), "generation": at, "champion_generation": info["generation"],
              "reference_validation_fitness": info["validation_fitness"], "reference_validation_survival": info["validation_survival"],
              "compiled_validation_fitness": again["fitness"], "compiled_validation_survival": again["survival"]}
    meta["champion_info"] = {**info, "validation_fitness": again["fitness"], "validation_survival": again["survival"]}
    arrays["meta"] = np.array(json.dumps(meta))
    shutil.copyfile(source / "champion.json", out / f"champion-at-{at}.json")
    (out / "carried-on.json").write_text(json.dumps(record, indent=1) + "\n")
    tmp = out / "checkpoint.tmp.npz"
    np.savez(tmp, **arrays)
    os.replace(tmp, out / "checkpoint.npz")
    log(f"carried on from generation {at}: its champion (generation {info['generation']}) validated {info['validation_fitness']:.4f} on the reference, "
        f"{again['fitness']:.4f} on the compiled life")
    return record


def run_phase(phase: str, replicate: int, out_root: Path, workers: int, quick: bool, stop_after: Optional[int], device: str,
              source_root: Path) -> Path:
    home = stage8.world("home", quick)
    cma = stage8.cma_for(quick).but(generations=generations(phase, quick))
    seed = seed_for(phase, replicate)
    out = out_root / phase / f"{MODE}-{seed}"
    fade, tighten = stage4b.path_generations(quick)
    eased = fade + tighten
    mix = [stage8.world(w, quick) for w in stage8.TRAINED]
    half = stage8.cma_for(quick).generations // 2
    keep = (half,) if phase == "fresh" else (3 * half,)  # a fresh run's champion at 200, as stage 8 kept it; a carried-on run's at 600
    import numba

    manifest = build_manifest(protocol=f"stage8b/{phase}", settings={**home.as_dict(), "world": "stage 4b's path, then four worlds at once", "mode": MODE,
                                                                     "genome_length": genome_length(home, MODE), "search": "CMA-ES", "cma": cma.as_dict(),
                                                                     "engine": "the compiled life (protocell/fast.py)", "device": device, "numba": numba.__version__,
                                                                     "trained": list(stage8.TRAINED),
                                                                     "worlds": {w: {"changes": stage8.WORLDS[w][0], "gain": stage8.WORLDS[w][1]} for w in stage8.TRAINED},
                                                                     "fade_generations": fade, "tighten_generations": tighten, "gain_end": stage4a.GAIN_SCALE,
                                                                     "champion_from": eased + 1, "keep_at": list(keep), "validation_each": 2 if quick else stage8.VALIDATION_EACH,
                                                                     "quick": quick},
                              seeds=[seed], extra={"out": str(out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:8.1f}s [{MODE}-{seed}] {msg}", flush=True)

    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        mapper = mapper_for(device, pool)
        if phase == "extend" and not (out / "checkpoint.npz").exists():
            carry_on(source_root / EXTENDED[seed] / f"{MODE}-{seed}", out, quick, mapper, log)
        state = run(home, MODE, cma, seed, out, mapper, log=log, stop_after=stop_after,
                    world_for=lambda g: stage4b.training_world(home, g, fade, tighten) if g <= eased else mix,
                    champion_from=eased + 1, keep_at=keep, validation_worlds=stage8.validation_worlds(quick))
    if state["next_generation"] >= cma.generations:
        finish_manifest(manifest, wall_seconds=time.time() - t0, generations=cma.generations, workers=workers)
        write_manifest(out / "manifest.json", manifest)
        info = state["champion_info"] or {}
        log(f"done: champion from generation {info.get('generation')}, validation fitness {info.get('validation_fitness')}, "
            f"survival {info.get('validation_survival')}")
    return out


def status(out_root: Path, quick: bool) -> List[Dict[str, Any]]:
    """Where each run stands, from its checkpoint."""
    rows = []
    for phase, seeds in SEEDS.items():
        for seed in seeds:
            path = out_root / phase / f"{MODE}-{seed}" / "checkpoint.npz"
            row: Dict[str, Any] = {"phase": phase, "seed": seed, "generation": None, "of": generations(phase, quick), "champion": None}
            if path.exists():
                with np.load(path, allow_pickle=False) as z:
                    meta = json.loads(str(z["meta"]))
                row["generation"] = meta["next_generation"]
                if meta["champion_info"]:
                    row["champion"] = (meta["champion_info"]["generation"], round(meta["champion_info"]["validation_fitness"], 4),
                                       round(meta["champion_info"]["validation_survival"], 3))
            rows.append(row)
            done = "not begun" if row["generation"] is None else ("done" if row["generation"] >= row["of"] else f"at generation {row['generation']} of {row['of']}")
            print(f"{phase} {seed}: {done}" + (f"; champion from generation {row['champion'][0]}, validation {row['champion'][1]} "
                                              f"(survival {row['champion'][2]:.0%})" if row["champion"] else ""), flush=True)
    return rows


# --- the test (§4) ----------------------------------------------------------------------------------------------------------

def test_cells(out_root: Path, quick: bool) -> Tuple[Dict[str, np.ndarray], Dict[str, str]]:
    """The cells, and what each is: a carried-on run's champion (``<seed> at <generations>``) and the same run's at the
    generation stage 8 ended (``<seed> at <that>``), a fresh run's (``<seed>``), and, in a full test, the references."""
    cells: Dict[str, np.ndarray] = {}
    kind: Dict[str, str] = {}
    early, late = stage8.cma_for(quick).generations, generations("extend", quick)
    for seed in SEEDS["extend"]:
        path = out_root / "extend" / f"{MODE}-{seed}"
        if (path / "champion.json").exists():
            cells[f"{seed} at {late}"] = np.asarray(json.loads((path / "champion.json").read_text())["genome"], dtype=np.float64)
            kind[f"{seed} at {late}"] = "extended"
            cells[f"{seed} at {early}"] = np.asarray(json.loads((path / f"champion-at-{early}.json").read_text())["genome"], dtype=np.float64)
            kind[f"{seed} at {early}"] = "stage 8"
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


def _world(job: Mapping[str, Any]) -> Tuple[str, Dict[str, Any], List[str]]:
    lines: List[str] = []
    w = job["world"]
    out = stage7.run_world(w, job["quick"], job["cells"], lines.append, 1000 * (list(stage8.WORLDS).index(w) + 1), stage8.WORLDS, TEST_SEED, BOOTSTRAP_SEED,
                           per_start=True)
    return w, out, lines


def wilson(k: int, n: int, z: float = 1.959963984540054) -> Tuple[float, float]:
    """A 95% interval for a rate from k of n (Wilson's)."""
    if n == 0:
        return math.nan, math.nan
    p = k / n
    centre, half = p + z * z / (2 * n), z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - half) / (1 + z * z / n)), min(1.0, (centre + half) / (1 + z * z / n))


def test_phase(out_root: Path, quick: bool, workers: int, only: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    cells, kind = test_cells(out_root, quick)
    names = [w for w in stage8.WORLDS if not only or w in only]
    manifest = build_manifest(protocol="stage8b/test", settings={"worlds": {w: {"changes": stage8.WORLDS[w][0], "gain": stage8.WORLDS[w][1]} for w in names},
                                                                 "trained": list(stage8.TRAINED), "held": list(stage8.HELD), "cells": kind,
                                                                 "select": stage7.SELECT, "report": stage7.REPORT, "engine": "the reference (protocell.sim.simulate)",
                                                                 "workers": workers, "quick": quick},
                              seeds=[TEST_SEED, BOOTSTRAP_SEED], extra={"out": str(out_root / "test")})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:7.0f}s {msg}", flush=True)

    jobs = [{"world": w, "quick": quick, "cells": cells} for w in names]
    worlds: Dict[str, Dict[str, Any]] = {}
    with ProcessPoolExecutor(max_workers=max(1, min(workers, len(jobs)))) as pool:
        for w, result, lines in pool.map(_world, jobs):
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
    early, late = stage8.cma_for(quick).generations, generations("extend", quick)
    trained_here = [w for w in stage8.TRAINED if w in worlds]
    time_rows = []
    for i, seed in enumerate(SEEDS["extend"]):
        a, b = f"{seed} at {late}", f"{seed} at {early}"
        if a in cells and trained_here:
            d = np.concatenate([np.array(worlds[w]["cells"][a]["report_fitness"]) - np.array(worlds[w]["cells"][b]["report_fitness"]) for w in trained_here])
            mean, low, high = bootstrap_ci(d, 60_000 + i, resamples, seed=BOOTSTRAP_SEED)
            time_rows.append({"seed": seed, "later_less_earlier": mean, "low": low, "high": high, "generalist_earlier": reading[b]["generalist"],
                              "generalist_later": reading[a]["generalist"]})
    extended = [c for c in cells if kind[c] == "extended"]
    fresh = [c for c in cells if kind[c] == "fresh"]
    later_generalists = [c for c in extended if reading[c]["generalist"]]
    later_better = [r["seed"] for r in time_rows if r["later_less_earlier"] > 0.0]
    fresh_generalists = [c for c in fresh if reading[c]["generalist"]]
    earlier_generalists = [c for c in cells if kind[c] == "stage 8" and reading[c]["generalist"]]
    at_400 = len(fresh) + sum(kind[c] == "stage 8" for c in cells)
    rate = wilson(len(fresh_generalists) + len(earlier_generalists), at_400)
    new = [c for c in extended + fresh if c != f"8102 at {late}"]
    predictions = [
        (1, "R1 fails: fewer than 3 of the 5 carried-on runs' champions are generalists at 800 generations", len(later_generalists) < NEED_GENERALISTS,
         {"generalists": later_generalists}),
        (2, "R2 holds: at least 4 of the 5 are better at 800 generations than at 400", len(later_better) >= NEED_TIME, {"better": later_better}),
        (3, "more time makes at least one new generalist among runs 8101, 8103, 8104 and 8105", any(c != f"8102 at {late}" for c in later_generalists),
         {"generalists": later_generalists}),
        (4, "R3 fails: between 1 and 3 of the 10 fresh runs' champions are generalists", 1 <= len(fresh_generalists) <= 3, {"generalists": fresh_generalists}),
        (5, "some new champion beats the bar in at least 5 of the nine worlds, as champion 8102 did", any(len(reading[c]["beats"]) >= 5 for c in new),
         {c: len(reading[c]["beats"]) for c in new}),
        (6, "on these fresh starts stage 8's champions stand as they did: 8102 a generalist at 400 generations and the other four not",
         earlier_generalists == [f"8102 at {early}"], {"generalists": earlier_generalists}),
    ]
    for v in worlds.values():
        for x in v["cells"].values():
            x.pop("report_fitness", None)
    summary = {"worlds": worlds, "reading": reading, "time": time_rows, "R1": len(later_generalists) >= NEED_GENERALISTS, "generalists_later": later_generalists,
               "R2": len(later_better) >= NEED_TIME, "later_better": later_better, "R3": len(fresh_generalists) >= NEED_FRESH, "generalists_fresh": fresh_generalists,
               "generalists_at_first_length": {"count": len(fresh_generalists) + len(earlier_generalists), "of": at_400, "low": rate[0], "high": rate[1]},
               "travellers": [c for c in extended + fresh if reading[c]["travels"]],
               "predictions": [{"number": k, "text": t, "holds": bool(h), "values": v} for k, t, h, v in predictions], "quick": quick}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0)
    write_manifest(out / "manifest.json", manifest)
    for c in cells:
        r = reading[c]
        log(f"{c} ({r['kind']}): does the job in {len(r['trained'])}/{len(stage8.TRAINED)} trained worlds and {len(r['held'])}/{len(stage8.HELD)} held back; "
            f"beats the bar in {len(r['beats'])}: {', '.join(r['beats']) or 'none'}")
    for r in time_rows:
        log(f"run {r['seed']}: at {late} generations less at {early}, over the trained worlds, {r['later_less_earlier']:+.3f} [{r['low']:+.3f}, {r['high']:+.3f}]")
    log(f"R1 (at least {NEED_GENERALISTS} of the carried-on runs are generalists at {late}): {summary['R1']} ({len(later_generalists)}/{len(extended)}); "
        f"R2 (at least {NEED_TIME} better at {late} than at {early}): {summary['R2']} ({len(later_better)}/{len(time_rows)}); "
        f"R3 (at least {NEED_FRESH} of the fresh runs are generalists): {summary['R3']} ({len(fresh_generalists)}/{len(fresh)})")
    log(f"generalists at {early} generations, stage 8's runs and the fresh ones together: {summary['generalists_at_first_length']['count']} of {at_400} "
        f"(95% interval for the rate {rate[0]:.0%} to {rate[1]:.0%})")
    for q in summary["predictions"]:
        log(f"prediction {q['number']}: {'holds' if q['holds'] else 'FAILS'}: {q['text']}")
    return summary


def main(argv: Optional[Sequence[str]] = None) -> Any:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--phase", required=True, choices=["extend", "fresh", "test", "status"])
    parser.add_argument("--replicate", type=int, nargs="+", default=[1], help="one run, or several one after another")
    parser.add_argument("--workers", type=int, default=8, help="the processes a generation (or the test's worlds) is spread over")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu", help="where the compiled life runs")
    parser.add_argument("--stop-after", type=int, default=None)
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--source", type=Path, default=stage8.DEFAULT_OUT, help="extend: where stage 8's runs are")
    parser.add_argument("--worlds", nargs="+", choices=list(stage8.WORLDS), help="the test in only these worlds (the smoke test)")
    args = parser.parse_args(argv)
    if args.phase == "status":
        return status(args.out, args.quick)
    if args.phase == "test":
        return test_phase(args.out, args.quick, args.workers, args.worlds)
    return [run_phase(args.phase, r, args.out, args.workers, args.quick, args.stop_after, args.device, args.source) for r in args.replicate]


if __name__ == "__main__":
    main(sys.argv[1:])
