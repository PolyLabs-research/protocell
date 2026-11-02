"""Stage 1b (docs/prereg/stage1b.md): stage 1's champions with each pathway held at its average.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage1b --workers 16
    .venv/bin/python -m experiments.stage1b --quick --stage1 /tmp/s1 --out /tmp/s1b --workers 2   # the smoke test: not a result

Reads the champions under ``docs/data/stage1/``. For each, it measures every pathway's mean input on stage 1's
validation starts, then runs the champion intact, with each pathway held at its average, and with each zeroed as in
stage 1, all on stage 1's test starts with shared noise. It checks that the intact and zeroed versions reproduce
stage 1's test rows, reads the criteria of §3, and writes ``docs/data/stage1b/``.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from experiments.cave import configure
from experiments.stage1 import (CONFIGURATION, DELTA, TEST_SEED, TEST_STARTS, _jsonable, bootstrap_ci, find_champions, summarise,
                                test_job)
from protocell.cell import MODES, PATHWAYS, pathway_mask
from protocell.config import Config
from protocell.evolve import GA, NOISE_CELL_ID, validation_starts
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.sim import simulate
from protocell.tables import fmt, write_csv
from protocell.world import Starts, sample_starts

BOOTSTRAP_SEED = 7
RESAMPLES = 10_000
# stage 1's removal that zeroes each pathway's effect: zeroing the core -> wall spokes is stage 1's "core" removal,
# since a core that cannot reach the wall cannot change it (stage 1 zeroed both directions)
ZEROED = {"core_drive": "core", "core_recurrence": "core_recurrence", "ring_links": "ring_links"}
DEFAULT_STAGE1 = Path("docs/data/stage1")
DEFAULT_OUT = Path("docs/data/stage1b")


def means_job(job: Mapping[str, Any]) -> Dict[str, Any]:
    """A champion's mean input along each pathway to each neuron, over its living ticks on the starts given."""
    cfg: Config = job["cfg"]
    starts: Starts = job["starts"]
    n = len(starts)
    masks = {p: pathway_mask(cfg, p) for p in PATHWAYS}
    sums = {p: np.zeros(cfg.n_wall + cfg.n_core) for p in PATHWAYS}
    state: Dict[str, Any] = {"count": 0, "weights": None}

    def observe(t: int, s: Mapping[str, Any]) -> None:
        live = s["alive"] & s["active"]
        if not live.any():
            return
        ctl = s["controller"]
        if state["weights"] is None:
            state["weights"] = {p: ctl.params.W * m for p, m in masks.items()}
        for p, w in state["weights"].items():
            sums[p] += np.einsum("pij,pj->pi", w, ctl.output)[live].sum(axis=0)
        state["count"] += int(live.sum())

    simulate(cfg, starts, {"controller": "network", "mode": job["mode"], "genomes": np.repeat(np.asarray(job["genome"])[None], n, axis=0)},
             seed=job["seed"], cell_ids=[NOISE_CELL_ID] * n, observe=observe)
    return {"run": job["run"], "living_ticks": state["count"], "means": {p: (sums[p] / max(1, state["count"])).tolist() for p in PATHWAYS}}


def reproduced(stage1_root: Path, results: Mapping[str, Mapping[str, Any]], labels: Sequence[str]) -> Optional[bool]:
    """Whether these versions' per-start fitness equals stage 1's test table, to the table's 12 significant digits."""
    path = stage1_root / "test" / "per_start.csv"
    if not path.exists():
        return None
    old = {(r["label"], int(r["start"])): r["fitness"] for r in csv.DictReader(open(path))}
    for label in labels:
        r = results[label]
        for start, f in zip(r["start"].tolist(), r["fitness"].tolist()):
            if old.get((label, int(start))) != fmt(f):
                return False
    return True


def run(stage1_root: Path, out: Path, workers: int, quick: bool) -> Dict[str, Any]:
    cfg = configure(CONFIGURATION, quick)
    ga = GA.quick() if quick else GA()
    vstarts = validation_starts(cfg, ga)
    tstarts = sample_starts(cfg, "cave", 4 if quick else TEST_STARTS, TEST_SEED)
    resamples = 200 if quick else RESAMPLES
    champions = find_champions(stage1_root)
    if not champions:
        raise SystemExit(f"no champions under {stage1_root}")
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        means = {m["run"]: m for m in pool.map(means_job, [{"cfg": cfg, "mode": c["mode"], "genome": c["genome"], "starts": vstarts,
                                                              "seed": ga.validation_seed, "run": c["run"]} for c in champions])}
        jobs = []
        for c in champions:
            base = {"controller": "network", "mode": c["mode"]}
            jobs.append({"label": c["run"], "cfg": cfg, "starts": tstarts, "spec": base, "genome": c["genome"]})
            for p in PATHWAYS:
                jobs.append({"label": f"{c['run']} hold {p}", "cfg": cfg, "starts": tstarts, "genome": c["genome"],
                             "spec": {**base, "hold": {"pathway": p, "means": means[c["run"]]["means"][p]}}})
                jobs.append({"label": f"{c['run']} -{ZEROED[p]}", "cfg": cfg, "starts": tstarts, "genome": c["genome"],
                             "spec": {**base, "removal": ZEROED[p]}})
        results = {r["label"]: r for r in pool.map(test_job, jobs)}
    n = len(tstarts)
    rows = [{"label": label, "start": int(r["start"][i]), "fitness": r["fitness"][i], "survived": r["survived"][i], "mean_beat": r["mean_beat"][i],
             "light_soaked": r["light_soaked"][i], "night_beat": r["night_beat"][i], "reach_tick": int(r["reach_tick"][i])}
            for label, r in results.items() for i in range(n)]
    write_csv(out / "per_start.csv", ("label", "start", "fitness", "survived", "mean_beat", "light_soaked", "night_beat", "reach_tick"), rows)
    check = reproduced(stage1_root, results, [c["run"] for c in champions] + [f"{c['run']} -{ZEROED[p]}" for c in champions for p in PATHWAYS])
    comparisons, key = [], 0
    for c in champions:
        intact = results[c["run"]]["fitness"]
        for p in PATHWAYS:
            key += 1
            held, lo, hi = bootstrap_ci(intact - results[f"{c['run']} hold {p}"]["fitness"], key, resamples)
            zeroed = float(np.mean(intact - results[f"{c['run']} -{ZEROED[p]}"]["fitness"]))
            comparisons.append({"run": c["run"], "phase": c["phase"], "mode": c["mode"], "pathway": p, "held_drop": held, "held_low": lo,
                                "held_high": hi, "zeroed_drop": zeroed, "recovered": (zeroed - held) / zeroed if zeroed > 0 else None,
                                "held_breaks": lo > DELTA})
    write_csv(out / "comparisons.csv", ("run", "phase", "mode", "pathway", "held_drop", "held_low", "held_high", "zeroed_drop", "recovered",
                                        "held_breaks"), comparisons)
    verdicts: Dict[str, Any] = {}
    for mode in MODES:
        mine = [x for x in comparisons if x["mode"] == mode and x["phase"] == "confirm"]
        if not mine:
            continue
        runs = sorted({x["run"] for x in mine})
        need = len(runs) // 2 + 1
        verdicts[mode] = {"champions": len(runs), **{p: {"breaks": sum(x["held_breaks"] for x in mine if x["pathway"] == p),
                                                         "computes": sum(x["held_breaks"] for x in mine if x["pathway"] == p) >= need}
                                                     for p in PATHWAYS}}
    summary = {"delta": DELTA, "n_starts": n, "reproduces_stage1": check, "verdicts": verdicts,
               "rows": {label: summarise(r) for label, r in results.items()},
               "means": {run_: {"living_ticks": m["living_ticks"], **m["means"]} for run_, m in means.items()}, "quick": quick}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=_jsonable) + "\n")
    manifest = build_manifest(protocol="stage1b", settings={**cfg.as_dict(), "delta": DELTA, "n_starts": n, "resamples": resamples,
                                                            "validation_starts": len(vstarts), "quick": quick},
                              seeds=[TEST_SEED, ga.validation_seed, BOOTSTRAP_SEED])
    finish_manifest(manifest, wall_seconds=time.time() - t0, jobs=len(jobs), workers=workers)
    write_manifest(out / "manifest.json", manifest)
    print(f"reproduces stage 1's test: {check}", flush=True)
    for mode, v in verdicts.items():
        print(f"{mode}: " + "; ".join(f"{p} held breaks {v[p]['breaks']}/{v['champions']}" for p in PATHWAYS), flush=True)
    return summary


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    parser.add_argument("--stage1", type=Path, default=DEFAULT_STAGE1)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    return run(args.stage1, args.out, args.workers, args.quick)


if __name__ == "__main__":
    main(sys.argv[1:])
