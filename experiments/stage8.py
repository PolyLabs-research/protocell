"""Stage 8 (docs/prereg/stage8.md): evolution from random genomes in several worlds at once.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage8 --phase pilot --mode fourier1 --replicate 1 --workers 16
    .venv/bin/python -m experiments.stage8 --phase outcome                 # the pilot's rule, read
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage8 --phase test
    .venv/bin/python -m experiments.stage8 --phase pilot --mode fourier1 --quick --out /tmp/s8   # the smoke test: not a result

A run is a stage 6b run (400 generations, the champion also kept at 200) with one change: after stage 4b's path
(generations 1-100) each generation's 8 training starts are 2 from each of four worlds (home, flicker, spot, shaded),
and validation is 12 fixed starts in each (seed 44); the champion is the best mean over the 48. The pilot is runs 1 and
2 (seeds 8101, 8102); runs 3 to 5 are phase ``confirm``. A run writes ``docs/data/stage8/<phase>/fourier1-<seed>/``.

The test is stage 7's (``experiments.stage7.run_world``) in nine worlds, the four trained in and five held back, at
seed 46 (bootstrap 47): each run's champion, and champions 6402 and 3603 for reference. Read here: G1 (does the job in
all four trained worlds), G2 (in at least 3 of the 5 held back), G3 (the worlds in which it beats the bar), the cost
of generality at home, and §7's predictions.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from experiments import stage4_probe as probe
from experiments import stage4a, stage4b, stage5c, stage6b, stage7
from experiments.stage1 import bootstrap_ci, find_champions
from protocell.cell import genome_length
from protocell.cmaes import CMA, run
from protocell.config import Config
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.tables import write_csv
from protocell.world import sample_starts

MODE = stage5c.MODE
FLICKER, CLOUDS = probe.WORLDS["flicker"], probe.WORLDS["clouds"]
WORLDS: Dict[str, Tuple[Dict[str, Any], float]] = {
    "home": ({"cave_sweep": True}, 0.55),
    "flicker": (dict(FLICKER), 0.55),
    "spot": (dict(probe.WORLDS["spot_2h"]), 0.45),
    "shaded": ({"cave_sweep": True, "shade_floor": 0.3}, 0.55),
    "fixed mouth": ({}, 0.55),
    "tighter": ({"cave_sweep": True}, 0.45),
    "sweep and flicker": ({"cave_sweep": True, **FLICKER}, 0.55),
    "slow clouds": ({"cave_sweep": True, **CLOUDS}, 0.55),
    "slow spot": (dict(probe.WORLDS["spot_6h"]), 0.45),
}
TRAINED = ("home", "flicker", "spot", "shaded")
HELD = ("fixed mouth", "tighter", "sweep and flicker", "slow clouds", "slow spot")
SEEDS = {"pilot": {MODE: (8101, 8102)}, "confirm": {MODE: (8103, 8104, 8105)}}
VALIDATION_SEED, VALIDATION_EACH = 44, 12  # 12 fixed starts in each trained world
TEST_SEED, BOOTSTRAP_SEED = 46, 47  # fresh
NEED = 3  # §6: of the five champions
TRAVELS = 3  # §6: of the five held-back worlds
REFERENCES = {"champion6402": Path("docs/data/stage6b/confirm/fourier1-6402/champion.npy"),
              "champion3603": Path("docs/data/stage5c/confirm/fourier1-3603/champion.npy")}
SPECIALIST = "champion6402"
DEFAULT_OUT = Path("docs/data/stage8")


def world(name: str, quick: bool = False) -> Config:
    return stage7.world_cfg(name, quick, WORLDS)


def cma_for(quick: bool) -> CMA:
    base = stage6b.cma_for(quick).but(validation_seed=VALIDATION_SEED)
    return base.but(train_starts=len(TRAINED)) if quick else base  # the smoke test: one start a world


def seed_for(phase: str, mode: str, replicate: int) -> int:
    if mode != MODE:
        raise SystemExit(f"stage 8 runs in {MODE} mode only")
    seeds = SEEDS[phase][mode]
    if not 1 <= replicate <= len(seeds):
        raise SystemExit(f"{phase} has {len(seeds)} runs")
    return seeds[replicate - 1]


def validation_worlds(quick: bool) -> List[Tuple[str, Config, Any]]:
    return [(w, world(w, quick), sample_starts(world(w, quick), "cave", 2 if quick else VALIDATION_EACH, VALIDATION_SEED)) for w in TRAINED]


def run_phase(phase: str, mode: str, replicate: int, out_root: Path, workers: int, quick: bool, stop_after: Optional[int]) -> Path:
    home = world("home", quick)
    cma = cma_for(quick)
    seed = seed_for(phase, mode, replicate)
    out = out_root / phase / f"{mode}-{seed}"
    fade, tighten = stage4b.path_generations(quick)
    eased = fade + tighten
    mix = [world(w, quick) for w in TRAINED]
    manifest = build_manifest(protocol=f"stage8/{phase}", settings={**home.as_dict(), "world": "stage 4b's path, then four worlds at once", "mode": mode,
                                                                    "genome_length": genome_length(home, mode), "search": "CMA-ES", "cma": cma.as_dict(),
                                                                    "trained": list(TRAINED), "worlds": {w: {"changes": WORLDS[w][0], "gain": WORLDS[w][1]} for w in TRAINED},
                                                                    "fade_generations": fade, "tighten_generations": tighten, "gain_end": stage4a.GAIN_SCALE,
                                                                    "champion_from": eased + 1, "keep_at": stage6b.half(quick),
                                                                    "validation_each": 2 if quick else VALIDATION_EACH, "quick": quick},
                              seeds=[seed], extra={"out": str(out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:8.1f}s [{mode}-{seed}] {msg}", flush=True)

    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        state = run(home, mode, cma, seed, out, pool.map, log=log, stop_after=stop_after,
                    world_for=lambda g: stage4b.training_world(home, g, fade, tighten) if g <= eased else mix,
                    champion_from=eased + 1, keep_at=(stage6b.half(quick),), validation_worlds=validation_worlds(quick))
    if state["next_generation"] >= cma.generations:
        finish_manifest(manifest, wall_seconds=time.time() - t0, generations=cma.generations, workers=workers)
        write_manifest(out / "manifest.json", manifest)
        info = state["champion_info"] or {}
        log(f"done: champion from generation {info.get('generation')}, validation fitness {info.get('validation_fitness')}, "
            f"survival {info.get('validation_survival')}")
    return out


def champion_by_world(path: Path) -> Dict[str, Dict[str, float]]:
    """A finished run's champion on each trained world's validation starts."""
    info = json.loads((path / "champion.json").read_text())
    with (path / "validation_worlds.csv").open() as f:
        rows = [r for r in csv.DictReader(f) if int(r["generation"]) == info["generation"] and int(r["rank"]) == info["rank"]]
    return {r["world"]: {"fitness": float(r["validation_fitness"]), "survival": float(r["validation_survival"])} for r in rows}


def pilot_outcome(out_root: Path) -> Dict[str, Any]:
    """§4's rule: a pilot run works if its champion survives at least half of the validation starts in at least three of
    the four worlds."""
    runs = {}
    for seed in SEEDS["pilot"][MODE]:
        path = out_root / "pilot" / f"{MODE}-{seed}"
        if (path / "champion.json").exists():
            by = champion_by_world(path)
            ok = [w for w, v in by.items() if v["survival"] >= 0.5]
            runs[seed] = {"by_world": by, "surviving_worlds": ok, "works": len(ok) >= 3}
            print(f"{MODE}-{seed}: " + "; ".join(f"{w} {v['fitness']:.3f} ({v['survival']:.0%})" for w, v in by.items())
                  + f" -> {'works' if runs[seed]['works'] else 'does not work'}", flush=True)
    go = any(r["works"] for r in runs.values())
    print("the other three runs follow" if go else "neither pilot run works: the owner's call", flush=True)
    return {"runs": runs, "go": go}


# --- the test (§5) ----------------------------------------------------------------------------------------------------------

def test_cells(out_root: Path, quick: bool) -> Dict[str, np.ndarray]:
    cells = {c["run"]: c["genome"] for c in find_champions(out_root) if c["phase"] in SEEDS}
    if not cells:
        raise SystemExit(f"no champions under {out_root}")
    if not quick:
        cells.update({name: np.load(path).reshape(-1) for name, path in REFERENCES.items()})
    return cells


def test_phase(out_root: Path, quick: bool, only: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    cells = test_cells(out_root, quick)
    names = [w for w in WORLDS if not only or w in only]
    manifest = build_manifest(protocol="stage8/test", settings={"worlds": {w: {"changes": WORLDS[w][0], "gain": WORLDS[w][1]} for w in names},
                                                                "trained": list(TRAINED), "held": list(HELD), "cells": list(cells),
                                                                "select": stage7.SELECT, "report": stage7.REPORT, "quick": quick},
                              seeds=[TEST_SEED, BOOTSTRAP_SEED], extra={"out": str(out_root / "test")})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:7.0f}s {msg}", flush=True)

    worlds = {w: stage7.run_world(w, quick, cells, log, 1000 * (list(WORLDS).index(w) + 1), WORLDS, TEST_SEED, BOOTSTRAP_SEED, per_start=True)
              for w in names}
    out = out_root / "test"
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "cells.csv", stage7.ROW_COLUMNS,
              [{"world": w, "cell": c, "bar": v["bar"], "bar_fitness": v["bar_fitness"], **{k: x[k] for k in x if k != "report_fitness"}}
               for w, v in worlds.items() for c, x in v["cells"].items()])
    champions = [c for c in cells if c not in REFERENCES]
    resamples = 200 if quick else stage7.RESAMPLES

    def does(cell: str, w: str) -> bool:
        return w in worlds and worlds[w]["cells"][cell]["verdict"] == "carries B8"

    def beats(cell: str, w: str) -> bool:
        return w in worlds and bool(worlds[w]["cells"][cell]["beats"])

    reading = {}
    for i, c in enumerate(cells):
        row = {"trained": [w for w in TRAINED if does(c, w)], "held": [w for w in HELD if does(c, w)], "beats": [w for w in worlds if beats(c, w)]}
        row["generalist"] = len(row["trained"]) == len(TRAINED)
        row["travels"] = len(row["held"]) >= TRAVELS
        if "home" in worlds and SPECIALIST in cells and c != SPECIALIST:
            mine, other = (np.array(worlds["home"]["cells"][k]["report_fitness"]) for k in (c, SPECIALIST))
            d, lo, hi = bootstrap_ci(mine - other, 50_000 + i, resamples, seed=BOOTSTRAP_SEED)
            row["home_less_specialist"] = {"mean": d, "low": lo, "high": hi}
        reading[c] = row
    generalists = [c for c in champions if reading[c]["generalist"]]
    travellers = [c for c in champions if reading[c]["travels"]]
    pilot = pilot_outcome(out_root) if (out_root / "pilot").exists() else {"runs": {}, "go": False}
    costs = [reading[c].get("home_less_specialist") for c in champions]
    predictions = [
        (1, "at least one pilot run works", pilot["go"], {str(k): v["works"] for k, v in pilot["runs"].items()}),
        (2, "G1 fails: fewer than 3 of the 5 champions do the job in all four trained worlds", len(generalists) < NEED, {"generalists": generalists}),
        (3, "no champion beats the bar in more than two of the nine worlds", all(len(reading[c]["beats"]) <= 2 for c in champions),
         {c: reading[c]["beats"] for c in champions}),
        (4, "every champion scores below champion 6402 at home, with the interval below 0", bool(costs) and all(x is not None and x["high"] < 0.0 for x in costs),
         {c: reading[c].get("home_less_specialist") for c in champions}),
        (5, "the best stage 8 champion does the job in at least 4 of the 5 held-back worlds", max((len(reading[c]["held"]) for c in champions), default=0) >= 4,
         {c: reading[c]["held"] for c in champions}),
    ]
    for v in worlds.values():
        for x in v["cells"].values():
            x.pop("report_fitness", None)
    summary = {"worlds": worlds, "reading": reading, "G1": len(generalists) >= NEED, "generalists": generalists, "G2": len(travellers) >= NEED,
               "travellers": travellers, "champions": champions,
               "predictions": [{"number": k, "text": t, "holds": bool(h), "values": v} for k, t, h, v in predictions], "quick": quick}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0)
    write_manifest(out / "manifest.json", manifest)
    for c in cells:
        r = reading[c]
        log(f"{c}: does the job in {len(r['trained'])}/{len(TRAINED)} trained worlds and {len(r['held'])}/{len(HELD)} held back; beats the bar in "
            f"{len(r['beats'])}: {', '.join(r['beats']) or 'none'}")
    log(f"G1 (at least {NEED} generalists): {summary['G1']} ({len(generalists)}/{len(champions)}); G2 (at least {NEED} travel): {summary['G2']} "
        f"({len(travellers)}/{len(champions)})")
    for q in summary["predictions"]:
        log(f"prediction {q['number']}: {'holds' if q['holds'] else 'FAILS'}: {q['text']}")
    return summary


def main(argv: Optional[Sequence[str]] = None) -> Any:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--phase", required=True, choices=["pilot", "confirm", "outcome", "test"])
    parser.add_argument("--mode", choices=[MODE], default=MODE)
    parser.add_argument("--replicate", type=int, default=1)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--stop-after", type=int, default=None)
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--worlds", nargs="+", choices=list(WORLDS), help="the test in only these worlds (the smoke test)")
    args = parser.parse_args(argv)
    if args.phase == "outcome":
        return pilot_outcome(args.out)
    if args.phase == "test":
        return test_phase(args.out, args.quick, args.worlds)
    return run_phase(args.phase, args.mode, args.replicate, args.out, args.workers, args.quick, args.stop_after)


if __name__ == "__main__":
    main(sys.argv[1:])
