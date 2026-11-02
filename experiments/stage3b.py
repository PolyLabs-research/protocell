"""Stage 3b (docs/prereg/stage3b.md): evolution in stage 3a's translucent world against B5, then the test.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage3b --phase pilot --mode fourier1 --workers 16
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage3b --phase confirm --mode uniform --replicate 2 --workers 16
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage3b --phase test --workers 16
    .venv/bin/python -m experiments.stage3b --phase pilot --mode uniform --quick --out /tmp/s3b   # the smoke test: not a result

A run uses stage 1's algorithm unchanged (protocell/evolve.py), with the validation starts at seed 10, and writes
``docs/data/stage3b/<phase>/<mode>-<seed>/``. The test scores every champion found there on 100 starts at seed 11 with
shared noise, against B5, B2r and the still cell at the best point, intact, with each removal of §6 and with each
pathway held at its average, and reads the criteria of §7. Bootstrap intervals at seed 12.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from experiments import stage3
from experiments.stage1 import _jsonable, bootstrap_ci, find_champions, summarise, test_job
from experiments.stage1b import means_job
from protocell.cell import MODES, PATHWAYS, genome_length
from protocell.config import Config
from protocell.evolve import GA, run, validation_starts
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.tables import write_csv
from protocell.world import sample_starts

# amendment A1's run seeds (stage3b.md §13); the preregistered pilot's (1101, 1102) are in pilot-as-preregistered/
SEEDS = {"pilot": {"uniform": (1201,), "fourier1": (1202,)},
         "confirm": {"uniform": (2201, 2202, 2203), "fourier1": (3201, 3202, 3203)}}
SEEDS_AS_PREREGISTERED = {"pilot": {"uniform": (1101,), "fourier1": (1102,)},
                          "confirm": {"uniform": (2101, 2102, 2103), "fourier1": (3101, 3102, 3103)}}
FADE_GENERATIONS = 50  # amendment A1: the shading fades over generations 1-50
SHADE_START = 0.3  # the cave's shaded cell
VALIDATION_SEED = 10
TEST_SEED = 11
BOOTSTRAP_SEED = 12
TEST_STARTS = 100
RESAMPLES = 10_000
DELTA = 0.011  # half B5's headroom below the still cell at the best point in stage 3a (0.021)
REMOVALS = ("blind", "ring_links", "core", "core_recurrence", "wall_fast", "core_fast")  # §6: R0, R1, R3, R4, R5, R6
DEFAULT_OUT = Path("docs/data/stage3b")
STAGE3_SUMMARY = Path("docs/data/stage3/summary.json")


def ga_for(quick: bool) -> GA:
    return (GA.quick() if quick else GA()).but(validation_seed=VALIDATION_SEED)


def fade_generations(quick: bool) -> int:
    return 2 if quick else FADE_GENERATIONS


def shade_floor_for(generation: int, fade: int) -> float:
    """Amendment A1: the training cell's shading floor in a generation (1-based), from the cave's 0.3 at generation 1
    rising in a straight line to fully translucent (1) after ``fade`` generations."""
    if generation <= fade:
        return SHADE_START + (1.0 - SHADE_START) * (generation - 1) / fade
    return 1.0


def seed_for(phase: str, mode: str, replicate: int) -> int:
    seeds = SEEDS[phase][mode]
    if not 1 <= replicate <= len(seeds):
        raise SystemExit(f"{phase} has {len(seeds)} run(s) per mode")
    return seeds[replicate - 1]


def stage3a_choices() -> Dict[str, Any]:
    """B5's time constant, B2r's gain and the best fixed point, as stage 3a chose them (30 s, 100, the probe's point)."""
    if STAGE3_SUMMARY.exists():
        s = json.loads(STAGE3_SUMMARY.read_text())
        probe = s["checks"]["T1"]["probe"]
        return {"tau": float(s["bar"]["tau"]), "k": float(s["checks"]["T4"]["b2r"]["k"]), "best": [probe["best_x"], probe["best_y"]]}
    return {"tau": 30.0, "k": 100.0, "best": None}


def run_phase(phase: str, mode: str, replicate: int, out_root: Path, workers: int, quick: bool, stop_after: Optional[int]) -> Path:
    cfg = stage3.configure(quick)
    ga = ga_for(quick)
    seed = seed_for(phase, mode, replicate)
    out = out_root / phase / f"{mode}-{seed}"
    fade = fade_generations(quick)
    manifest = build_manifest(protocol=f"stage3b/{phase}", settings={**cfg.as_dict(), "world": "stage 3a, translucent", "mode": mode,
                                                                     "genome_length": genome_length(cfg, mode), "ga": ga.as_dict(), "quick": quick,
                                                                     "amendment": "A1: the shading fades", "fade_generations": fade,
                                                                     "shade_start": SHADE_START, "champion_from": fade + 1},
                              seeds=[seed], extra={"out": str(out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:8.1f}s [{mode}-{seed}] {msg}", flush=True)

    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        state = run(cfg, mode, ga, seed, out, pool.map, log=log, stop_after=stop_after,
                    world_for=lambda g: cfg.but(shade_floor=shade_floor_for(g, fade)), champion_from=fade + 1)
    if state["next_generation"] >= ga.generations:
        finish_manifest(manifest, wall_seconds=time.time() - t0, generations=ga.generations, workers=workers)
        write_manifest(out / "manifest.json", manifest)
        info = state["champion_info"] or {}
        log(f"done: champion from generation {info.get('generation')}, validation fitness {info.get('validation_fitness')}")
    return out


def test_phase(out_root: Path, workers: int, quick: bool) -> Dict[str, Any]:
    cfg = stage3.configure(quick)
    ga = ga_for(quick)
    n = 4 if quick else TEST_STARTS
    resamples = 200 if quick else RESAMPLES
    starts = sample_starts(cfg, "cave", n, TEST_SEED)
    chosen = stage3a_choices()
    point = np.array(chosen["best"]) if (chosen["best"] is not None and not quick) else np.array([0.0, -cfg.clamp_radius])
    champions = find_champions(out_root)
    if not champions:
        raise SystemExit(f"no champions under {out_root}")
    vstarts = validation_starts(cfg, ga)
    t0 = time.time()
    common = {"cfg": cfg, "starts": starts, "seed": TEST_SEED}
    jobs = [{**common, "label": "B5", "spec": stage3.runwait(cfg, chosen["tau"])},
            {**common, "label": "B2r", "spec": stage3.reflex(cfg, chosen["k"])},
            {**common, "label": "still at the best point", "spec": {"controller": "still"}, "pos": point}]
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        means = {m["run"]: m for m in pool.map(means_job, [{"cfg": cfg, "mode": c["mode"], "genome": c["genome"], "starts": vstarts,
                                                              "seed": VALIDATION_SEED, "run": c["run"]} for c in champions])}
        for c in champions:
            base = {"controller": "network", "mode": c["mode"]}
            jobs.append({**common, "label": c["run"], "spec": base, "genome": c["genome"]})
            for rm in REMOVALS:
                jobs.append({**common, "label": f"{c['run']} -{rm}", "spec": {**base, "removal": rm}, "genome": c["genome"]})
            for p in PATHWAYS:
                jobs.append({**common, "label": f"{c['run']} hold {p}", "genome": c["genome"],
                             "spec": {**base, "hold": {"pathway": p, "means": means[c["run"]]["means"][p]}}})
        results = {r["label"]: r for r in pool.map(test_job, jobs)}
    out = out_root / "test"
    rows = [{"label": label, "start": int(r["start"][i]), "fitness": r["fitness"][i], "survived": r["survived"][i], "mean_beat": r["mean_beat"][i],
             "light_soaked": r["light_soaked"][i], "night_beat": r["night_beat"][i], "reach_tick": int(r["reach_tick"][i])}
            for label, r in results.items() for i in range(n)]
    write_csv(out / "per_start.csv", ("label", "start", "fitness", "survived", "mean_beat", "light_soaked", "night_beat", "reach_tick"), rows)
    b5, b2r = results["B5"]["fitness"], results["B2r"]["fitness"]
    half_gap = float(b5.mean() - b2r.mean()) / 2.0
    comparisons: List[Dict[str, Any]] = []
    key = 0

    def ci(diff: np.ndarray):
        nonlocal key
        key += 1
        return bootstrap_ci(diff, key, resamples, seed=BOOTSTRAP_SEED)

    for c in champions:
        f = results[c["run"]]["fitness"]
        d, lo, hi = ci(f - b2r)
        comparisons.append({"run": c["run"], "phase": c["phase"], "mode": c["mode"], "compared": "champion - B2r", "mean": d, "low": lo, "high": hi,
                            "criterion": half_gap, "verdict": lo >= half_gap})
        d, lo, hi = ci(f - b5)
        comparisons.append({"run": c["run"], "phase": c["phase"], "mode": c["mode"], "compared": "champion - B5", "mean": d, "low": lo, "high": hi,
                            "criterion": -DELTA, "verdict": lo > -DELTA})
        for label in [f"-{rm}" for rm in REMOVALS] + [f"hold {p}" for p in PATHWAYS]:
            d, lo, hi = ci(f - results[f"{c['run']} {label}"]["fitness"])
            comparisons.append({"run": c["run"], "phase": c["phase"], "mode": c["mode"], "compared": f"intact - ({label.lstrip('-')})", "mean": d,
                                "low": lo, "high": hi, "criterion": DELTA, "verdict": lo > DELTA})
    write_csv(out / "comparisons.csv", ("run", "phase", "mode", "compared", "mean", "low", "high", "criterion", "verdict"), comparisons)
    verdicts: Dict[str, Any] = {}
    for mode in MODES:
        mine = [x for x in comparisons if x["mode"] == mode and x["phase"] == "confirm"]
        runs = sorted({x["run"] for x in mine})
        if not runs:
            continue
        need = len(runs) // 2 + 1
        count = lambda name: sum(bool(x["verdict"]) for x in mine if x["compared"] == name)  # noqa: E731
        verdicts[mode] = {"champions": len(runs), "finds_comparison_over_time": count("champion - B2r"), "reaches_b5": count("champion - B5"),
                          "Q1": count("champion - B2r") >= need, "Q3": count("champion - B5") >= need,
                          "Q2_breaks": {name: count(name) for name in sorted({x["compared"] for x in mine if x["compared"].startswith("intact")})}}
        verdicts[mode]["Q2_needed"] = {name: v >= need for name, v in verdicts[mode]["Q2_breaks"].items()}
    summary = {"delta": DELTA, "half_gap": half_gap, "n_starts": n, "b5_tau": chosen["tau"], "b2r_k": chosen["k"], "verdicts": verdicts,
               "rows": {label: summarise(r) for label, r in results.items()},
               "champions": [{k: v for k, v in c.items() if k != "genome"} for c in champions],
               "means": {r_: {"living_ticks": m["living_ticks"], **m["means"]} for r_, m in means.items()}, "quick": quick}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=_jsonable) + "\n")
    manifest = build_manifest(protocol="stage3b/test", settings={**cfg.as_dict(), "delta": DELTA, "n_starts": n, "resamples": resamples, "quick": quick},
                              seeds=[TEST_SEED, VALIDATION_SEED, BOOTSTRAP_SEED])
    finish_manifest(manifest, wall_seconds=time.time() - t0, jobs=len(jobs), workers=workers)
    write_manifest(out / "manifest.json", manifest)
    print(f"B5 {b5.mean():.3f}, B2r {b2r.mean():.3f}: half the gap {half_gap:.3f}", flush=True)
    for mode, v in verdicts.items():
        print(f"{mode}: finds comparison over time {v['finds_comparison_over_time']}/{v['champions']}, reaches B5 {v['reaches_b5']}/{v['champions']}; "
              f"needed: {', '.join(k for k, need in v['Q2_needed'].items() if need) or 'none'}", flush=True)
    return summary


def main(argv: Optional[Sequence[str]] = None) -> Any:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--phase", required=True, choices=["pilot", "confirm", "test"])
    parser.add_argument("--mode", choices=list(MODES))
    parser.add_argument("--replicate", type=int, default=1)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--stop-after", type=int, default=None)
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    if args.phase == "test":
        return test_phase(args.out, args.workers, args.quick)
    if args.mode is None:
        raise SystemExit("a run needs --mode")
    return run_phase(args.phase, args.mode, args.replicate, args.out, args.workers, args.quick, args.stop_after)


if __name__ == "__main__":
    main(sys.argv[1:])
