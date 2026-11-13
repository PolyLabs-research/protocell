"""Stage 6 (docs/prereg/stage6.md): evolution from nothing on the cell with relative sensing.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage6 --phase pilot --mode fourier1 --workers 16
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage6 --phase confirm --mode uniform --replicate 2 --workers 16
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage6 --phase test --workers 1
    .venv/bin/python -m experiments.stage6 --phase read          # stage 6's readings again from the test's files
    .venv/bin/python -m experiments.stage6 --phase pilot --mode uniform --quick --out /tmp/s6   # the smoke test: not a result

A run is stage 4c's as it ran (CMA-ES from a random mean, first step 0.05, 200 generations on stage 4b's amended path,
the champion from generation 101), with one change: the cell senses light relative to its recent level (stage 5).
Validation is on stage 5c's starts (48 at seed 32). A run writes ``docs/data/stage6/<phase>/<mode>-<seed>/``.

The test is stage 4b's on stage 5's cell, as stage 5c ran it, on 100 fresh starts at seed 37 (bootstrap 38), with
design 16 and stage 5c's champion 3603 as reference cells. Added here: Q0, the share of the gap from B0 to B8 each
champion closes (stage 4d's measure and verdicts), and §7's predictions.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from experiments import stage4a, stage4b, stage4c, stage4e, stage5b, stage5c
from experiments.stage1 import _jsonable, find_champions
from experiments.stage4d import verdict
from protocell.cell import MODES, genome_length
from protocell.cmaes import CMA, run
from protocell.manifest import build_manifest, finish_manifest, write_manifest

SEEDS = {"pilot": {"uniform": (6101,), "fourier1": (6102,)},
         "confirm": {"uniform": (6201, 6202, 6203), "fourier1": (6301, 6302, 6303)}}
VALIDATION_SEED, VALIDATION_STARTS = stage5c.VALIDATION_SEED, stage5c.VALIDATION_STARTS  # stage 5c's: 48 starts at seed 32
TEST_SEED, BOOTSTRAP_SEED = 37, 38  # fresh
STAGE4C_PILOT = {"uniform": 0.149, "fourier1": 0.160}  # stage 4c's pilot champions' validation fitness (D20), on the old cell
REFERENCE_CHAMPION = Path("docs/data/stage5c/confirm/fourier1-3603/champion.npy")
DEFAULT_OUT = Path("docs/data/stage6")


def cma_for(quick: bool) -> CMA:
    base = CMA.quick() if quick else CMA().but(validation_starts=VALIDATION_STARTS)
    return base.but(validation_seed=VALIDATION_SEED, sigma0=stage4c.SIGMA0)


def seed_for(phase: str, mode: str, replicate: int) -> int:
    seeds = SEEDS[phase][mode]
    if not 1 <= replicate <= len(seeds):
        raise SystemExit(f"{phase} has {len(seeds)} run(s) per mode")
    return seeds[replicate - 1]


def run_phase(phase: str, mode: str, replicate: int, out_root: Path, workers: int, quick: bool, stop_after: Optional[int]) -> Path:
    cfg = stage5b.world(quick)
    cma = cma_for(quick)
    seed = seed_for(phase, mode, replicate)
    out = out_root / phase / f"{mode}-{seed}"
    fade, tighten = stage4b.path_generations(quick)
    champion_from = fade + tighten + 1
    manifest = build_manifest(protocol=f"stage6/{phase}", settings={**cfg.as_dict(), "world": "stage 4a, stage 5's cell", "mode": mode,
                                                                    "genome_length": genome_length(cfg, mode), "search": "CMA-ES", "cma": cma.as_dict(),
                                                                    "path": "stage 4b's A1", "fade_generations": fade, "tighten_generations": tighten,
                                                                    "shade_start": stage4b.SHADE_START, "gain_end": stage4a.GAIN_SCALE,
                                                                    "champion_from": champion_from, "quick": quick},
                              seeds=[seed], extra={"out": str(out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:8.1f}s [{mode}-{seed}] {msg}", flush=True)

    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        state = run(cfg, mode, cma, seed, out, pool.map, log=log, stop_after=stop_after,
                    world_for=lambda g: stage4b.training_world(cfg, g, fade, tighten), champion_from=champion_from)
    if state["next_generation"] >= cma.generations:
        finish_manifest(manifest, wall_seconds=time.time() - t0, generations=cma.generations, workers=workers)
        write_manifest(out / "manifest.json", manifest)
        info = state["champion_info"] or {}
        log(f"done: champion from generation {info.get('generation')}, validation fitness {info.get('validation_fitness')}, "
            f"survival {info.get('validation_survival')}")
    return out


# --- the test (§5) ----------------------------------------------------------------------------------------------------------

def _no_score(*_: Any) -> List[Dict[str, Any]]:
    return []  # stage 6 scores its own predictions, from the test's files


def reference_cells(cfg: Any, quick: bool) -> List[Dict[str, Any]]:
    """Design 16 and stage 5c's champion 3603, tested beside the champions and outside the modes' verdicts."""
    g0 = stage4e.genome(cfg, stage4e.load(stage5c.SEED_DESIGN))
    cells = [{"phase": "reference", "run": "design16", "mode": stage5c.MODE, "seed": None, "genome": g0, "generation": 0, "validation_fitness": None}]
    if not quick and REFERENCE_CHAMPION.exists():
        cells.append({"phase": "reference", "run": "champion3603", "mode": stage5c.MODE, "seed": 3603,
                      "genome": np.load(REFERENCE_CHAMPION).reshape(-1), "generation": None, "validation_fitness": None})
    return cells


def test_phase(out_root: Path, workers: int, quick: bool) -> Dict[str, Any]:
    cfg = stage5b.world(quick)
    summary = stage4b.test_phase(out_root, workers, quick, score=_no_score, world=stage5b.world, test_seed=TEST_SEED,
                                 bootstrap_seed=BOOTSTRAP_SEED, validation=(VALIDATION_SEED, VALIDATION_STARTS),
                                 extra_cells=reference_cells(cfg, quick), protocol="stage6/test")
    return {**summary, "stage6": read_test(out_root, quick)}


def read_test(out_root: Path, quick: bool) -> Dict[str, Any]:
    """Stage 6's own readings from the test's files: Q0 (the share of the gap closed), Q1, and §7's predictions.
    Writes ``test/stage6.json``."""
    out = out_root / "test"
    per: Dict[str, List[float]] = {}
    with (out / "per_start.csv").open() as f:
        for r in csv.DictReader(f):
            per.setdefault(r["label"], []).append(float(r["fitness"]))
    fit = {k: np.array(v) for k, v in per.items()}
    with (out / "comparisons.csv").open() as f:
        comparisons = list(csv.DictReader(f))
    champions = find_champions(out_root)
    resamples = 200 if quick else stage4b.RESAMPLES
    q0 = []
    for i, c in enumerate(champions):
        share, lo, hi = stage4e._gap_share(fit[c["run"]], fit["B8"], fit["B0"], resamples, 30_000 + i, BOOTSTRAP_SEED)
        q0.append({"run": c["run"], "phase": c["phase"], "mode": c["mode"], "fitness": float(fit[c["run"]].mean()), "gap_share": share, "low": lo,
                   "high": hi, "verdict": verdict(share)})
    modes: Dict[str, Dict[str, Any]] = {}
    for mode in MODES:
        mine = [x for x in q0 if x["mode"] == mode and x["phase"] == "confirm"]
        if not mine:
            continue
        need = len(mine) // 2 + 1
        carries = [x["run"] for x in mine if x["verdict"] == "carries B8"]
        beats = [x["run"] for x in comparisons if x["compared"] == "champion - B8" and x["phase"] == "confirm" and x["mode"] == mode
                 and stage5c._yes(x["verdict"])]
        modes[mode] = {"champions": len(mine), "carrying_B8": carries, "Q0": len(carries) >= need, "beating_B8": beats, "Q1": len(beats) >= need}
    pilots = {}
    for mode in MODES:
        path = out_root / "pilot" / f"{mode}-{SEEDS['pilot'][mode][0]}" / "champion.json"
        if path.exists():
            pilots[mode] = json.loads(path.read_text())
    above = {m: p.get("validation_fitness") for m, p in pilots.items()}
    met = [m for m, p in pilots.items() if (p.get("validation_survival") or 0.0) >= 0.5]
    predictions = [
        (1, "the pilot's champions validate above stage 4c's in both modes",
         len(above) == 2 and all(above[m] is not None and above[m] > STAGE4C_PILOT[m] for m in MODES), {"stage6": above, "stage4c": STAGE4C_PILOT}),
        (2, "the pilot's rule is met in at most one mode", len(met) <= 1, {"met": met}),
        (3, "no confirmed mode carries B8", not any(v["Q0"] for v in modes.values()), {m: v["carrying_B8"] for m, v in modes.items()}),
        (4, "no confirmatory champion beats B8", not any(v["beating_B8"] for v in modes.values()), {m: v["beating_B8"] for m, v in modes.items()}),
        (5, "fourier1's pilot champion validates higher than uniform's",
         len(above) == 2 and None not in above.values() and above["fourier1"] > above["uniform"], above),
    ]
    result = {"q0": q0, "modes": modes, "fitness": {k: float(v.mean()) for k, v in fit.items() if " " not in k},
              "predictions": [{"number": n, "text": t, "holds": bool(h), "values": v} for n, t, h, v in predictions], "quick": quick}
    (out / "stage6.json").write_text(json.dumps(result, indent=1, sort_keys=True, default=_jsonable) + "\n")
    for x in q0:
        print(f"{x['phase']:8s} {x['run']:16s} {x['fitness']:.3f}: closes {x['gap_share']:.3f} [{x['low']:.3f}, {x['high']:.3f}] of the gap: {x['verdict']}",
              flush=True)
    for mode, v in modes.items():
        print(f"{mode}: carries B8 {len(v['carrying_B8'])}/{v['champions']} (Q0 {v['Q0']}); beats B8 {len(v['beating_B8'])}/{v['champions']} (Q1 {v['Q1']})",
              flush=True)
    for q in result["predictions"]:
        print(f"prediction {q['number']}: {'✓' if q['holds'] else '✗'} {q['text']}", flush=True)
    return result


def main(argv: Optional[Sequence[str]] = None) -> Any:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--phase", required=True, choices=["pilot", "confirm", "test", "read"])
    parser.add_argument("--mode", choices=list(MODES))
    parser.add_argument("--replicate", type=int, default=1)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--stop-after", type=int, default=None)
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    if args.phase == "test":
        return test_phase(args.out, args.workers, args.quick)
    if args.phase == "read":
        return read_test(args.out, args.quick)
    if args.mode is None:
        raise SystemExit("a run needs --mode")
    return run_phase(args.phase, args.mode, args.replicate, args.out, args.workers, args.quick, args.stop_after)


if __name__ == "__main__":
    main(sys.argv[1:])
