"""Stage 1 (docs/prereg/stage1.md): evolving the cell in the cave's day configuration, then the test.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage1 --phase pilot --mode uniform --workers 16
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage1 --phase confirm --mode fourier1 --replicate 2 --workers 16
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage1 --phase test --workers 16
    .venv/bin/python -m experiments.stage1 --phase pilot --mode uniform --quick --out /tmp/s1   # the smoke test: not a result

A run (§4–§5) writes ``docs/data/stage1/<phase>/<mode>-<seed>/``: its generations, its validations, its champion,
its final population, a checkpoint it resumes from if interrupted, and its manifest. The test (§6–§9) reads every
champion found under ``docs/data/stage1/`` and writes ``docs/data/stage1/test/``. It scores each champion intact and
with each removal, and B2r and the still cell at the day's best fixed point, all on 100 test starts that share their
noise, plus the swept day, and it reads the criteria of §9.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from experiments.cave import configure
from protocell.cell import MODES, REMOVALS, genome_length
from protocell.config import Config
from protocell.evolve import GA, run
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.rng import stream
from protocell.sim import simulate
from protocell.tables import write_csv
from protocell.world import Starts, sample_starts

CONFIGURATION = "day"  # D5: stage 1 evolves in the cave's day configuration
SEEDS = {"pilot": {"uniform": (1001,), "fourier1": (1002,)},
         "confirm": {"uniform": (2001, 2002, 2003), "fourier1": (3001, 3002, 3003)}}
TEST_SEED = 5
TEST_STARTS = 100
BOOTSTRAP_SEED = 6
BOOTSTRAP_RESAMPLES = 10_000
DELTA = 0.007  # half the day's headroom (stage1.md §9; docs/data/stage1/budget/headroom.csv)
BAR_K_FALLBACK = 100.0
DEFAULT_OUT = Path("docs/data/stage1")
CAVE_DAY_SUMMARY = Path("docs/data/cave/day/summary.json")


def ga_for(quick: bool) -> GA:
    return GA.quick() if quick else GA()


def seed_for(phase: str, mode: str, replicate: int) -> int:
    seeds = SEEDS[phase][mode]
    if not 1 <= replicate <= len(seeds):
        raise SystemExit(f"{phase} has {len(seeds)} run(s) per mode")
    return seeds[replicate - 1]


# --- a run --------------------------------------------------------------------------------------------------------------

def run_phase(phase: str, mode: str, replicate: int, out_root: Path, workers: int, quick: bool, stop_after: Optional[int]) -> Path:
    cfg = configure(CONFIGURATION, quick)
    ga = ga_for(quick)
    seed = seed_for(phase, mode, replicate)
    out = out_root / phase / f"{mode}-{seed}"
    manifest = build_manifest(protocol=f"stage1/{phase}", settings={**cfg.as_dict(), "configuration": CONFIGURATION, "mode": mode,
                                                                    "genome_length": genome_length(cfg, mode), "ga": ga.as_dict(), "quick": quick},
                              seeds=[seed], extra={"out": str(out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:8.1f}s [{mode}-{seed}] {msg}", flush=True)

    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        state = run(cfg, mode, ga, seed, out, pool.map, log=log, stop_after=stop_after)
    if state["next_generation"] >= ga.generations:
        finish_manifest(manifest, wall_seconds=time.time() - t0, generations=ga.generations, workers=workers)
        write_manifest(out / "manifest.json", manifest)
        info = state["champion_info"] or {}
        log(f"done: champion from generation {info.get('generation')}, validation fitness {info.get('validation_fitness')}")
    return out


# --- the test -------------------------------------------------------------------------------------------------------------

def bar_k() -> float:
    if CAVE_DAY_SUMMARY.exists():
        return float(json.loads(CAVE_DAY_SUMMARY.read_text())["checks"]["K4"]["bar"]["k"])
    return BAR_K_FALLBACK


def best_point(cfg: Config) -> np.ndarray:
    """The day's best fixed point, as the cave's check K1 found it (its probe's coordinates)."""
    if cfg.day_ticks == 86_400 and CAVE_DAY_SUMMARY.exists():
        probe = json.loads(CAVE_DAY_SUMMARY.read_text())["checks"]["K1"]["probe"]
        return np.array([probe["best_x"], probe["best_y"]])
    return np.array([0.0, -cfg.clamp_radius])


def find_champions(root: Path) -> List[Dict[str, Any]]:
    out = []
    for path in sorted(root.glob("*/*/champion.json")):
        info = json.loads(path.read_text())
        out.append({"phase": path.parent.parent.name, "run": path.parent.name, "mode": info["mode"], "seed": info["seed"],
                    "genome": np.asarray(info["genome"], dtype=np.float64), "generation": info.get("generation"),
                    "validation_fitness": info.get("validation_fitness")})
    return out


def test_job(job: Mapping[str, Any]) -> Dict[str, Any]:
    starts: Starts = job["starts"]
    n = len(starts)
    spec = dict(job["spec"])
    if spec["controller"] == "network":
        spec["genomes"] = np.repeat(np.asarray(job["genome"])[None], n, axis=0)
    st = starts.with_pos(np.repeat(job["pos"][None], n, axis=0)) if job.get("pos") is not None else starts
    r = simulate(job["cfg"], st, spec, seed=job.get("seed", TEST_SEED), cell_ids=[0] * n)
    return {"label": job["label"], "fitness": r.fitness, "survived": r.survived, "mean_beat": r.mean_beat, "light_soaked": r.light_soaked,
            "night_beat": r.night_beat, "reach_tick": r.reach_tick, "start": starts.index}


def bootstrap_ci(diff: np.ndarray, key: int, resamples: int, seed: int = BOOTSTRAP_SEED) -> Tuple[float, float, float]:
    rng = stream(seed, "bootstrap", (key,))
    idx = rng.integers(0, diff.shape[0], size=(resamples, diff.shape[0]))
    means = diff[idx].mean(axis=1)
    return float(diff.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def summarise(r: Mapping[str, Any]) -> Dict[str, Any]:
    light = float(np.sum(r["light_soaked"]))
    nights = ~np.isnan(r["night_beat"])
    reached = r["reach_tick"] > 0
    return {"fitness": float(np.mean(r["fitness"])), "survival": float(np.mean(r["survived"])), "light_soaked": float(np.mean(r["light_soaked"])),
            "mean_beat": float(np.mean(r["mean_beat"])), "effort_per_light": float(np.sum(r["mean_beat"]) / light) if light > 0 else None,
            "night_beat": float(np.mean(r["night_beat"][nights])) if nights.any() else None,
            "median_reach_tick": float(np.median(r["reach_tick"][reached])) if reached.any() else None}


def test_phase(out_root: Path, workers: int, quick: bool) -> Dict[str, Any]:
    cfg = configure(CONFIGURATION, quick)
    swept = cfg.but(cave_sweep=True)
    n = 4 if quick else TEST_STARTS
    resamples = 200 if quick else BOOTSTRAP_RESAMPLES
    starts = sample_starts(cfg, "cave", n, TEST_SEED)
    k = bar_k()
    b2r = {"controller": "reflex", "k": k, "rest_below": cfg.rest_below}
    champions = find_champions(out_root)
    if not champions:
        raise SystemExit(f"no champions under {out_root}")
    jobs = [{"label": "B2r", "cfg": cfg, "starts": starts, "spec": b2r},
            {"label": "B2r swept", "cfg": swept, "starts": starts, "spec": b2r},
            {"label": "still at the best point", "cfg": cfg, "starts": starts, "spec": {"controller": "still"}, "pos": best_point(cfg)}]
    for c in champions:
        base = {"controller": "network", "mode": c["mode"]}
        jobs.append({"label": f"{c['run']}", "cfg": cfg, "starts": starts, "spec": base, "genome": c["genome"]})
        jobs.append({"label": f"{c['run']} swept", "cfg": swept, "starts": starts, "spec": base, "genome": c["genome"]})
        for rm in REMOVALS:
            jobs.append({"label": f"{c['run']} -{rm}", "cfg": cfg, "starts": starts, "spec": {**base, "removal": rm}, "genome": c["genome"]})
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        results = {r["label"]: r for r in pool.map(test_job, jobs)}
    out = out_root / "test"
    rows = []
    for label, r in results.items():
        for i in range(n):
            rows.append({"label": label, "start": int(r["start"][i]), "fitness": r["fitness"][i], "survived": r["survived"][i],
                         "mean_beat": r["mean_beat"][i], "light_soaked": r["light_soaked"][i], "night_beat": r["night_beat"][i],
                         "reach_tick": int(r["reach_tick"][i])})
    write_csv(out / "per_start.csv", ("label", "start", "fitness", "survived", "mean_beat", "light_soaked", "night_beat", "reach_tick"), rows)
    comparisons, key = [], 0
    bar = results["B2r"]["fitness"]
    verdicts: Dict[str, Any] = {}
    for c in champions:
        intact = results[c["run"]]["fitness"]
        key += 1
        d, lo, hi = bootstrap_ci(intact - bar, key, resamples)
        comp = {"run": c["run"], "phase": c["phase"], "mode": c["mode"], "compared": "champion - B2r", "mean": d, "low": lo, "high": hi,
                "reaches": lo > -DELTA, "beats": lo > 0.0, "breaks": None}
        comparisons.append(comp)
        for rm in REMOVALS:
            key += 1
            drop, lo, hi = bootstrap_ci(intact - results[f"{c['run']} -{rm}"]["fitness"], key, resamples)
            comparisons.append({"run": c["run"], "phase": c["phase"], "mode": c["mode"], "compared": f"intact - {rm}", "mean": drop, "low": lo,
                                "high": hi, "reaches": None, "beats": None, "breaks": lo > DELTA})
    for mode in MODES:
        mine = [x for x in comparisons if x["mode"] == mode and x["phase"] == "confirm"]
        heads = [x for x in mine if x["compared"] == "champion - B2r"]
        if not heads:
            continue
        need = (len(heads) // 2) + 1
        verdicts[mode] = {"champions": len(heads), "reach": sum(x["reaches"] for x in heads), "beat": sum(x["beats"] for x in heads),
                          "Q1_reaches_the_bar": sum(x["reaches"] for x in heads) >= need, "Q3_beats_the_bar": sum(x["beats"] for x in heads) >= need,
                          "Q2_parts_needed": {rm: sum(bool(x["breaks"]) for x in mine if x["compared"] == f"intact - {rm}") >= need for rm in REMOVALS}}
    write_csv(out / "comparisons.csv", ("run", "phase", "mode", "compared", "mean", "low", "high", "reaches", "beats", "breaks"), comparisons)
    summary = {"delta": DELTA, "test_seed": TEST_SEED, "n_starts": n, "bar_k": k, "rows": {label: summarise(r) for label, r in results.items()},
               "champions": [{k2: v for k2, v in c.items() if k2 != "genome"} for c in champions], "verdicts": verdicts, "quick": quick}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=_jsonable) + "\n")
    manifest = build_manifest(protocol="stage1/test", settings={**cfg.as_dict(), "delta": DELTA, "n_starts": n, "resamples": resamples, "quick": quick},
                              seeds=[TEST_SEED, BOOTSTRAP_SEED])
    finish_manifest(manifest, wall_seconds=time.time() - t0, jobs=len(jobs), workers=workers)
    write_manifest(out / "manifest.json", manifest)
    for mode, v in verdicts.items():
        print(f"{mode}: reaches the bar {v['reach']}/{v['champions']}, beats it {v['beat']}/{v['champions']}; parts needed: "
              + ", ".join(rm for rm, need in v["Q2_parts_needed"].items() if need), flush=True)
    return summary


def _jsonable(value: Any) -> Any:
    if isinstance(value, (np.floating, np.integer, np.bool_)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, float) and math.isnan(value):
        return None
    return str(value)


def main(argv: Optional[Sequence[str]] = None) -> Any:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--phase", required=True, choices=["pilot", "confirm", "test"])
    parser.add_argument("--mode", choices=list(MODES))
    parser.add_argument("--replicate", type=int, default=1)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--stop-after", type=int, default=None, help="stop after this many generations (the run resumes from its checkpoint)")
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
