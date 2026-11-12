"""Stage 5c (docs/prereg/stage5c.md): a search that starts at stage 5b's hand-written cell, design 16.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage5c --phase pilot --mode fourier1 --replicate 1 --workers 16
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage5c --phase pilot --mode fourier1 --replicate 2 --workers 16
    .venv/bin/python -m experiments.stage5c --phase outcome                                  # the pilot's rule, read
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage5c --phase test --workers 1
    .venv/bin/python -m experiments.stage5c --phase read      # stage 5c's readings again from the test's files
    .venv/bin/python -m experiments.stage5c --phase pilot --mode fourier1 --quick --out /tmp/s5c   # the smoke test: not a result

A run is stage 4c's CMA-ES (protocell/cmaes.py) with its mean started at design 16's genome, for 200 generations in
stage 4a's world with stage 5's cell throughout (no path). Every 10 generations the best three samples and the mean are
validated on 48 fresh starts at seed 32; design 16 is validated there before generation 1; the champion is the best
candidate from generation 10 on. The pilot's two runs differ only in the first step: replicate 1 takes 0.002 of each
gene's range, replicate 2 takes 0.005 (§5). A run writes ``docs/data/stage5c/<phase>/<mode>-<seed>/``.

The pilot's rule (§5): a run holds the start if its mean at the last generation validates no lower than design 16 less
delta. The confirmatory runs' step is set from the pilot's outcome, as a dated note in the draft, before they run.

The test (§6) is stage 4b's (``experiments.stage4b.test_phase``) on stage 5's cell, on 100 fresh starts at seed 33 with
the bootstrap at seed 34 and the holds' averages from the validation starts: every champion, and design 16 as a cell of
its own, against B8, with the removals, the holds, the goggles and the flat pool. Added here: each champion against
design 16 (Q1b), which of design 16's needed parts the champions still need (Q2), how far each group of genes moved
from design 16, and §8's predictions 3-5. Writes ``docs/data/stage5c/test/``.
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

from experiments import stage4b, stage4e, stage5b
from experiments.stage1 import _jsonable, bootstrap_ci, find_champions
from protocell.cell import genome_length, genome_ranges, layout
from protocell.cmaes import CMA, run
from protocell.manifest import build_manifest, finish_manifest, write_manifest

MODE = "fourier1"  # §2: design 16's mode; the uniform mode is not part of this question
SEEDS = {"pilot": {MODE: (1601, 1602)}, "confirm": {MODE: (3601, 3602, 3603)}}
PILOT_STEPS = {1601: 0.002, 1602: 0.005}  # §3, §5: the first step as a share of each gene's range, from the probe (§4)
CONFIRM_STEP: Optional[float] = 0.005  # the pilot's outcome (§5, 2026-11-11): both runs held; 0.005's mean validated higher
VALIDATION_SEED, VALIDATION_STARTS = 32, 48  # fresh: seed 20's starts chose design 16
TEST_SEED, BOOTSTRAP_SEED = 33, 34  # fresh
CHAMPION_FROM = 10  # the first validation
DELTA = 0.012  # stage 4b's
HOLD_WINDOW = 5  # §5: if both pilot runs hold, the mean's validation over the last five validations decides
SEED_DESIGN = Path("docs/data/stage5b/fourier1/designs/s16.json")
DEFAULT_OUT = Path("docs/data/stage5c")


def seed_for(phase: str, mode: str, replicate: int) -> int:
    if mode != MODE:
        raise SystemExit(f"stage 5c runs in {MODE} mode only")
    seeds = SEEDS[phase][mode]
    if not 1 <= replicate <= len(seeds):
        raise SystemExit(f"{phase} has {len(seeds)} run(s)")
    return seeds[replicate - 1]


def step_for(phase: str, seed: int) -> float:
    if phase == "pilot":
        return PILOT_STEPS[seed]
    if CONFIRM_STEP is None:
        raise SystemExit("the confirmatory runs' step is set from the pilot's outcome first (stage5c.md §5)")
    return CONFIRM_STEP


def cma_for(phase: str, seed: int, quick: bool) -> CMA:
    base = CMA.quick() if quick else CMA().but(validation_starts=VALIDATION_STARTS)
    return base.but(validation_seed=VALIDATION_SEED, sigma0=step_for(phase, seed))


def run_phase(phase: str, mode: str, replicate: int, out_root: Path, workers: int, quick: bool, stop_after: Optional[int]) -> Path:
    cfg = stage5b.world(quick)
    seed = seed_for(phase, mode, replicate)
    cma = cma_for(phase, seed, quick)
    out = out_root / phase / f"{mode}-{seed}"
    design = stage4e.load(SEED_DESIGN)
    start = stage4e.genome(cfg, design)
    champion_from = 1 if quick else CHAMPION_FROM
    manifest = build_manifest(protocol=f"stage5c/{phase}", settings={**cfg.as_dict(), "world": "stage 4a, stage 5's cell", "mode": mode,
                                                                     "genome_length": genome_length(cfg, mode), "search": "CMA-ES", "cma": cma.as_dict(),
                                                                     "start": SEED_DESIGN.name, "start_sha": stage4e.sha(design), "path": "none",
                                                                     "champion_from": champion_from, "quick": quick},
                              seeds=[seed], extra={"out": str(out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:8.1f}s [{mode}-{seed}] {msg}", flush=True)

    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        state = run(cfg, mode, cma, seed, out, pool.map, log=log, stop_after=stop_after, champion_from=champion_from, start=start)
    if state["next_generation"] >= cma.generations:
        finish_manifest(manifest, wall_seconds=time.time() - t0, generations=cma.generations, workers=workers)
        write_manifest(out / "manifest.json", manifest)
        info = state["champion_info"] or {}
        log(f"done: champion from generation {info.get('generation')}, validation fitness {info.get('validation_fitness')}, "
            f"survival {info.get('validation_survival')}")
    return out


def read_run(path: Path, validate_top: int) -> Dict[str, Any]:
    """A finished run's validations: design 16's (generation 0), the mean's at each validation, the best candidate's,
    and the step size at the end."""
    with (path / "validation.csv").open() as f:
        rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(f)]
    with (path / "generations.csv").open() as f:
        gens = list(csv.DictReader(f))
    start = next(r for r in rows if r["generation"] == 0)
    means = sorted((r for r in rows if r["rank"] == validate_top + 1), key=lambda r: r["generation"])
    best = max((r for r in rows if r["generation"] > 0), key=lambda r: r["validation_fitness"])
    return {"start": start["validation_fitness"], "start_survival": start["validation_survival"],
            "mean_last": means[-1]["validation_fitness"], "mean_last_survival": means[-1]["validation_survival"],
            "mean_window": sum(r["validation_fitness"] for r in means[-HOLD_WINDOW:]) / len(means[-HOLD_WINDOW:]),
            "best": best["validation_fitness"], "best_generation": int(best["generation"]),
            "sigma_first": float(gens[0]["sigma"]), "sigma_last": float(gens[-1]["sigma"]), "generations": len(gens)}


def pilot_outcome(out_root: Path, quick: bool = False) -> Dict[str, Any]:
    """§5's rule on the pilot's finished runs: which hold the start, and the step the confirmatory runs take."""
    top = (CMA.quick() if quick else CMA()).validate_top
    runs = {}
    for seed in SEEDS["pilot"][MODE]:
        path = out_root / "pilot" / f"{MODE}-{seed}"
        if (path / "validation.csv").exists():
            r = read_run(path, top)
            runs[seed] = {**r, "step": PILOT_STEPS[seed], "holds": r["mean_last"] >= r["start"] - DELTA}
    holding = [s for s, r in runs.items() if r["holds"]]
    chosen = max(holding, key=lambda s: runs[s]["mean_window"]) if holding else None
    for seed, r in runs.items():
        print(f"{MODE}-{seed} (first step {r['step']}): design 16 validates {r['start']:.3f}; the mean at generation {r['generations']} "
              f"{r['mean_last']:.3f} ({'holds' if r['holds'] else 'does not hold'}); its last {HOLD_WINDOW} validations average "
              f"{r['mean_window']:.3f}; best candidate {r['best']:.3f} (generation {r['best_generation']}); step {r['sigma_first']:.4f} -> "
              f"{r['sigma_last']:.4f}", flush=True)
    print("the confirmatory runs' step: " + (f"{PILOT_STEPS[chosen]} (run {chosen})" if chosen else "none: neither run holds the start"), flush=True)
    return {"runs": runs, "holding": holding, "confirm_step": PILOT_STEPS[chosen] if chosen else None}


# --- the test (§6) --------------------------------------------------------------------------------------------------------

START = "design16"  # design 16's label in the test, tested as the champions are
GENE_GROUPS = ("ring", "alpha", "core_w", "core_bias", "core_log_tau", "spokes_in", "spokes_out")


def gene_movement(cfg: Any, start: np.ndarray, genome: np.ndarray) -> Dict[str, float]:
    """How far each group of genes sits from design 16's, as the mean absolute share of the gene's range (the cilium
    angle around its circle), and over all genes."""
    lay = layout(cfg, MODE)
    lo, hi = genome_ranges(cfg, MODE)
    d = np.abs(np.asarray(genome) - start) / (hi - lo)
    a = lay.alpha.start
    d[a] = min(d[a], 1.0 - d[a])
    out = {g: float(d[getattr(lay, g)].mean()) for g in GENE_GROUPS}
    out["all"] = float(d.mean())
    return out


def _no_score(*_: Any) -> List[Dict[str, Any]]:
    return []  # stage 5c scores its own predictions below, from the test's files


def test_phase(out_root: Path, workers: int, quick: bool) -> Dict[str, Any]:
    cfg = stage5b.world(quick)
    design = stage4e.load(SEED_DESIGN)
    start = stage4e.genome(cfg, design)
    extra = [{"phase": "start", "run": START, "mode": MODE, "seed": None, "genome": start, "generation": 0, "validation_fitness": None}]
    summary = stage4b.test_phase(out_root, workers, quick, score=_no_score, world=stage5b.world, test_seed=TEST_SEED,
                                 bootstrap_seed=BOOTSTRAP_SEED, validation=(VALIDATION_SEED, VALIDATION_STARTS), extra_cells=extra,
                                 protocol="stage5c/test")
    return {**summary, "stage5c": read_test(out_root, quick)}


def _yes(verdict: str) -> bool:
    return verdict in ("1", "True")  # the tables write a verdict as 1 or 0


def read_test(out_root: Path, quick: bool) -> Dict[str, Any]:
    """Stage 5c's own readings from the test's files (``--phase read`` does this alone, with no cell run again): Q1 and
    Q1b, the parts that survive, the genes' movement and predictions 3-5. Writes ``test/stage5c.json``."""
    cfg = stage5b.world(quick)
    start = stage4e.genome(cfg, stage4e.load(SEED_DESIGN))
    out = out_root / "test"
    with (out / "per_start.csv").open() as f:
        per: Dict[str, List[float]] = {}
        for r in csv.DictReader(f):
            per.setdefault(r["label"], []).append(float(r["fitness"]))
    fit = {k: np.array(v) for k, v in per.items()}
    with (out / "comparisons.csv").open() as f:
        comparisons = list(csv.DictReader(f))
    champions = find_champions(out_root)
    confirm = [c for c in champions if c["phase"] == "confirm"]
    resamples = 200 if quick else stage4b.RESAMPLES
    q1b = []
    for i, c in enumerate(champions):
        d, lo, hi = bootstrap_ci(fit[c["run"]] - fit[START], 20_000 + i, resamples, seed=BOOTSTRAP_SEED)
        q1b.append({"run": c["run"], "phase": c["phase"], "mean": d, "low": lo, "high": hi, "above_in_the_mean": d > 0.0, "verdict": lo > 0.0})
    need = len(confirm) // 2 + 1 if confirm else 1
    b8 = [x for x in comparisons if x["compared"] == "champion - B8" and x["phase"] == "confirm"]
    beats = [x["run"] for x in b8 if _yes(x["verdict"])]
    improves = [x["run"] for x in q1b if x["phase"] == "confirm" and x["verdict"]]
    above = [x["run"] for x in q1b if x["phase"] == "confirm" and x["above_in_the_mean"]]
    parts: Dict[str, Dict[str, Any]] = {}
    for x in comparisons:
        if x["compared"].startswith("intact") and x["phase"] in ("start", "confirm"):
            e = parts.setdefault(x["compared"], {"design16_needs": False, "champions_needing": 0})
            if x["phase"] == "start":
                e["design16_needs"] = _yes(x["verdict"])
            else:
                e["champions_needing"] += _yes(x["verdict"])
    for e in parts.values():
        e["needed_by_champions"] = e["champions_needing"] >= need
        e["survives"] = bool(e["design16_needs"] and e["needed_by_champions"])
    hand = [k for k, e in parts.items() if e["design16_needs"]]
    predictions = [
        (3, "at least 2 of the 3 champions score above design 16, and at most 1 has its interval above 0",
         len(above) >= need and len(improves) <= 1, {"above": above, "interval_above_0": improves}),
        (4, "Q1 fails: no champion beats B8", not beats, {"beat": beats}),
        (5, "every part design 16 needs, the champions still need", bool(confirm) and all(parts[k]["survives"] for k in hand),
         {k: parts[k] for k in hand}),
    ]
    result = {"Q1": len(beats) >= need and bool(confirm), "champions_beating_B8": beats, "Q1b": len(improves) >= need and bool(confirm),
              "champion_minus_design16": q1b, "parts": parts,
              "gene_movement": {c["run"]: gene_movement(cfg, start, c["genome"]) for c in champions},
              "fitness": {k: float(v.mean()) for k, v in fit.items() if " " not in k},
              "predictions": [{"number": n, "text": t, "holds": bool(h), "values": v} for n, t, h, v in predictions], "quick": quick}
    (out / "stage5c.json").write_text(json.dumps(result, indent=1, sort_keys=True, default=_jsonable) + "\n")
    for x in q1b:
        print(f"{x['phase']:8s} {x['run']:16s} less design 16: {x['mean']:+.3f} [{x['low']:+.3f}, {x['high']:+.3f}]", flush=True)
    print(f"Q1 (beats B8): {result['Q1']} ({len(beats)}/{len(confirm)}); Q1b (improves on design 16): {result['Q1b']} ({len(improves)}/{len(confirm)})", flush=True)
    for q in result["predictions"]:
        print(f"prediction {q['number']}: {'✓' if q['holds'] else '✗'} {q['text']}", flush=True)
    return result


def main(argv: Optional[Sequence[str]] = None) -> Any:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--phase", required=True, choices=["pilot", "confirm", "outcome", "test", "read"])
    parser.add_argument("--mode", choices=[MODE], default=MODE)
    parser.add_argument("--replicate", type=int, default=1)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--stop-after", type=int, default=None)
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    if args.phase == "outcome":
        return pilot_outcome(args.out, args.quick)
    if args.phase == "test":
        return test_phase(args.out, args.workers, args.quick)
    if args.phase == "read":
        return read_test(args.out, args.quick)
    return run_phase(args.phase, args.mode, args.replicate, args.out, args.workers, args.quick, args.stop_after)


if __name__ == "__main__":
    main(sys.argv[1:])
