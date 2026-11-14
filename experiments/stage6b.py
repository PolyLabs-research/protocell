"""Stage 6b (docs/prereg/stage6b.md): how reliably evolution from nothing does B8's job and beats B8, at 400 generations.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage6b --phase confirm --mode fourier1 --replicate 1 --workers 16
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage6b --phase test --workers 1
    .venv/bin/python -m experiments.stage6b --phase read          # the readings again from the test's files
    .venv/bin/python -m experiments.stage6b --phase confirm --mode fourier1 --quick --out /tmp/s6b   # the smoke test: not a result

A run is a stage 6 fourier1 run (experiments/stage6.py) with 400 generations where stage 6 had 200, on five fresh seeds.
Each run also keeps its champion as it stood at generation 200 (``champion-at-200.json``). A run writes
``docs/data/stage6b/confirm/fourier1-<seed>/``.

The test is stage 6's, on 100 fresh starts at seed 40 (bootstrap 41): each run's champion at 400 generations, and at
200 as a cell of its own, beside design 16, stage 5c's champion 3603 and stage 6's champion 6301. Read here: Q0 (the
share of the gap from B0 to B8 closed), Q1 (beats B8), Q2 (each run's champion at 400 less its champion at 200), and
§5's predictions.
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

from experiments import stage4a, stage4b, stage4e, stage5b, stage5c, stage6
from experiments.stage1 import _jsonable, bootstrap_ci, find_champions
from experiments.stage4d import verdict
from protocell.cell import genome_length
from protocell.cmaes import CMA, run
from protocell.manifest import build_manifest, finish_manifest, write_manifest

MODE = stage5c.MODE
SEEDS = {"confirm": {MODE: (6401, 6402, 6403, 6404, 6405)}}
FACTOR = 2  # 400 generations where stage 6 had 200
TEST_SEED, BOOTSTRAP_SEED = 40, 41  # fresh
NEED_CARRY, NEED_BEAT, NEED_TIME = 4, 3, 4  # §4: of the five runs
REFERENCES = {"champion3603": Path("docs/data/stage5c/confirm/fourier1-3603/champion.npy"),
              "champion6301": Path("docs/data/stage6/confirm/fourier1-6301/champion.npy")}
DEFAULT_OUT = Path("docs/data/stage6b")


def cma_for(quick: bool) -> CMA:
    base = stage6.cma_for(quick)
    return base.but(generations=FACTOR * base.generations)


def half(quick: bool) -> int:
    """The generation at which each run's champion is also kept: stage 6's length."""
    return stage6.cma_for(quick).generations


def seed_for(phase: str, mode: str, replicate: int) -> int:
    if mode != MODE:
        raise SystemExit(f"stage 6b runs in {MODE} mode only")
    seeds = SEEDS[phase][mode]
    if not 1 <= replicate <= len(seeds):
        raise SystemExit(f"{phase} has {len(seeds)} runs")
    return seeds[replicate - 1]


def run_phase(phase: str, mode: str, replicate: int, out_root: Path, workers: int, quick: bool, stop_after: Optional[int]) -> Path:
    cfg = stage5b.world(quick)
    cma = cma_for(quick)
    seed = seed_for(phase, mode, replicate)
    out = out_root / phase / f"{mode}-{seed}"
    fade, tighten = stage4b.path_generations(quick)
    champion_from = fade + tighten + 1
    manifest = build_manifest(protocol=f"stage6b/{phase}", settings={**cfg.as_dict(), "world": "stage 4a, stage 5's cell", "mode": mode,
                                                                     "genome_length": genome_length(cfg, mode), "search": "CMA-ES", "cma": cma.as_dict(),
                                                                     "path": "stage 4b's A1", "fade_generations": fade, "tighten_generations": tighten,
                                                                     "shade_start": stage4b.SHADE_START, "gain_end": stage4a.GAIN_SCALE,
                                                                     "champion_from": champion_from, "keep_at": half(quick), "quick": quick},
                              seeds=[seed], extra={"out": str(out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:8.1f}s [{mode}-{seed}] {msg}", flush=True)

    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        state = run(cfg, mode, cma, seed, out, pool.map, log=log, stop_after=stop_after,
                    world_for=lambda g: stage4b.training_world(cfg, g, fade, tighten), champion_from=champion_from, keep_at=(half(quick),))
    if state["next_generation"] >= cma.generations:
        finish_manifest(manifest, wall_seconds=time.time() - t0, generations=cma.generations, workers=workers)
        write_manifest(out / "manifest.json", manifest)
        info = state["champion_info"] or {}
        log(f"done: champion from generation {info.get('generation')}, validation fitness {info.get('validation_fitness')}, "
            f"survival {info.get('validation_survival')}")
    return out


# --- the test (§3) ----------------------------------------------------------------------------------------------------------

def at_half(out_root: Path, quick: bool) -> List[Dict[str, Any]]:
    """Each run's champion as it stood at stage 6's length, as a cell of its own (phase ``at200``)."""
    cells = []
    for path in sorted((out_root / "confirm").glob(f"*/champion-at-{half(quick)}.json")):
        info = json.loads(path.read_text())
        cells.append({"phase": "at200", "run": f"{path.parent.name}@{half(quick)}", "mode": info["mode"], "seed": info["seed"],
                      "genome": np.asarray(info["genome"], dtype=np.float64), "generation": info.get("generation"),
                      "validation_fitness": info.get("validation_fitness"), "of": path.parent.name})
    return cells


def reference_cells(cfg: Any, quick: bool) -> List[Dict[str, Any]]:
    cells = [{"phase": "reference", "run": "design16", "mode": MODE, "seed": None, "genome": stage4e.genome(cfg, stage4e.load(stage5c.SEED_DESIGN)),
              "generation": 0, "validation_fitness": None}]
    if not quick:
        cells += [{"phase": "reference", "run": name, "mode": MODE, "seed": None, "genome": np.load(path).reshape(-1), "generation": None,
                   "validation_fitness": None} for name, path in REFERENCES.items() if path.exists()]
    return cells


def _no_score(*_: Any) -> List[Dict[str, Any]]:
    return []


def test_phase(out_root: Path, workers: int, quick: bool) -> Dict[str, Any]:
    cfg = stage5b.world(quick)
    extra = [{k: v for k, v in c.items() if k != "of"} for c in at_half(out_root, quick)] + reference_cells(cfg, quick)
    summary = stage4b.test_phase(out_root, workers, quick, score=_no_score, world=stage5b.world, test_seed=TEST_SEED,
                                 bootstrap_seed=BOOTSTRAP_SEED, validation=(stage6.VALIDATION_SEED, stage6.VALIDATION_STARTS), extra_cells=extra,
                                 protocol="stage6b/test")
    return {**summary, "stage6b": read_test(out_root, quick)}


def read_test(out_root: Path, quick: bool) -> Dict[str, Any]:
    """Stage 6b's readings from the test's files: Q0, Q1, Q2 and §5's predictions. Writes ``test/stage6b.json``."""
    out = out_root / "test"
    per: Dict[str, List[float]] = {}
    with (out / "per_start.csv").open() as f:
        for r in csv.DictReader(f):
            per.setdefault(r["label"], []).append(float(r["fitness"]))
    fit = {k: np.array(v) for k, v in per.items()}
    with (out / "comparisons.csv").open() as f:
        beats_b8 = {x["run"]: stage5c._yes(x["verdict"]) for x in csv.DictReader(f) if x["compared"] == "champion - B8"}
    resamples = 200 if quick else stage4b.RESAMPLES
    champions = find_champions(out_root)
    halves = {c["of"]: c["run"] for c in at_half(out_root, quick)}
    runs = []
    for i, c in enumerate(champions):
        name = c["run"]
        share, lo, hi = stage4e._gap_share(fit[name], fit["B8"], fit["B0"], resamples, 40_000 + i, BOOTSTRAP_SEED)
        info = json.loads((out_root / c["phase"] / name / "champion.json").read_text())
        row = {"run": name, "fitness": float(fit[name].mean()), "gap_share": share, "low": lo, "high": hi, "verdict": verdict(share),
               "beats_B8": bool(beats_b8.get(name)), "works": (info.get("validation_survival") or 0.0) >= 0.5, "champion_generation": info.get("generation")}
        if name in halves:
            h = halves[name]
            d, dlo, dhi = bootstrap_ci(fit[name] - fit[h], 41_000 + i, resamples, seed=BOOTSTRAP_SEED)
            hs = stage4e._gap_share(fit[h], fit["B8"], fit["B0"], resamples, 42_000 + i, BOOTSTRAP_SEED)[0]
            row["at_half"] = {"run": h, "fitness": float(fit[h].mean()), "gap_share": hs, "verdict": verdict(hs), "beats_B8": bool(beats_b8.get(h)),
                              "later_less_earlier": {"mean": d, "low": dlo, "high": dhi}}
        runs.append(row)
    carry = [r["run"] for r in runs if r["verdict"] == "carries B8"]
    beat = [r["run"] for r in runs if r["beats_B8"]]
    work = [r["run"] for r in runs if r["works"]]
    later = [r["run"] for r in runs if "at_half" in r and r["at_half"]["later_less_earlier"]["mean"] > 0.0]
    beat_half = [r["run"] for r in runs if "at_half" in r and r["at_half"]["beats_B8"]]
    result = {"runs": runs, "Q0": len(carry) >= NEED_CARRY, "carrying_B8": carry, "Q1": len(beat) >= NEED_BEAT, "beating_B8": beat,
              "Q2": len(later) >= NEED_TIME, "later_better": later, "working": work, "beating_B8_at_half": beat_half,
              "fitness": {k: float(v.mean()) for k, v in fit.items() if " " not in k}, "quick": quick}
    predictions = [
        (1, "at least 3 of the 5 runs work", len(work) >= 3, {"working": work}),
        (2, "Q0 fails narrowly: exactly 3 of 5 carry B8", len(carry) == 3, {"carrying": carry}),
        (3, "Q1 holds: at least 3 of 5 beat B8 at 400 generations", result["Q1"], {"beating": beat}),
        (4, "Q2 holds: the champion at 400 scores above the champion at 200 in at least 4 of 5 runs", result["Q2"], {"later_better": later}),
        (5, "at 200 generations, at most 2 of the 5 champions beat B8", len(beat_half) <= 2, {"beating_at_200": beat_half}),
    ]
    result["predictions"] = [{"number": n, "text": t, "holds": bool(h), "values": v} for n, t, h, v in predictions]
    (out / "stage6b.json").write_text(json.dumps(result, indent=1, sort_keys=True, default=_jsonable) + "\n")
    for r in runs:
        tail = ""
        if "at_half" in r:
            d = r["at_half"]["later_less_earlier"]
            tail = f"; at half {r['at_half']['fitness']:.3f}, later less earlier {d['mean']:+.3f} [{d['low']:+.3f}, {d['high']:+.3f}]"
        print(f"{r['run']:16s} {r['fitness']:.3f}: closes {r['gap_share']:.3f} [{r['low']:.3f}, {r['high']:.3f}] ({r['verdict']}); "
              f"beats B8 {r['beats_B8']}{tail}", flush=True)
    print(f"Q0 (at least {NEED_CARRY} carry B8): {result['Q0']} ({len(carry)}/{len(runs)}); Q1 (at least {NEED_BEAT} beat B8): {result['Q1']} "
          f"({len(beat)}/{len(runs)}); Q2 (later better in at least {NEED_TIME}): {result['Q2']} ({len(later)}/{len(runs)})", flush=True)
    for q in result["predictions"]:
        print(f"prediction {q['number']}: {'✓' if q['holds'] else '✗'} {q['text']}", flush=True)
    return result


def main(argv: Optional[Sequence[str]] = None) -> Any:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--phase", required=True, choices=["confirm", "test", "read"])
    parser.add_argument("--mode", choices=[MODE], default=MODE)
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
    return run_phase(args.phase, args.mode, args.replicate, args.out, args.workers, args.quick, args.stop_after)


if __name__ == "__main__":
    main(sys.argv[1:])
