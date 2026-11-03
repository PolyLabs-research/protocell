"""Stage 4c (docs/prereg/stage4c.md): stage 4b's question with CMA-ES, then stage 4b's test.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage4c --phase check --mode uniform --workers 12
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage4c --phase pilot --mode fourier1 --workers 16
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage4c --phase test --workers 16
    .venv/bin/python -m experiments.stage4c --phase pilot --mode uniform --quick --out /tmp/s4c   # the smoke test: not a result

A run is CMA-ES (protocell/cmaes.py) for 200 generations on stage 4b's amended path (stage4b.md §13): the shading
fades over generations 1-50 in the cave's economy, the gain falls over 51-100 with the cell translucent, 101-200 train
in stage 4a's world; validation every 10 generations at seed 20 in stage 4a's world, the champion from generation 101.
The local check (§5) runs the first 25 generations of the same path. A run writes
``docs/data/stage4c/<phase>/<mode>-<seed>/``; the test is stage 4b's (§6) on the champions found there.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

from experiments import stage4a, stage4b
from protocell.cell import MODES, genome_length
from protocell.cmaes import CMA, run
from protocell.manifest import build_manifest, finish_manifest, write_manifest

SEEDS = {"check": {"uniform": (1599,), "fourier1": (1598,)},
         "pilot": {"uniform": (1501,), "fourier1": (1502,)},
         "confirm": {"uniform": (2501, 2502, 2503), "fourier1": (3501, 3502, 3503)}}
CHECK_GENERATIONS = 25  # §5: the first 25 generations of the path
GA_PILOT = {"uniform": 0.155, "fourier1": 0.241}  # stage 4b's amended pilot: its champions' validation fitness (D19)
DEFAULT_OUT = Path("docs/data/stage4c")


def cma_for(phase: str, quick: bool) -> CMA:
    base = CMA.quick() if quick else CMA()
    base = base.but(validation_seed=stage4b.VALIDATION_SEED)
    return base.but(generations=min(CHECK_GENERATIONS, base.generations)) if phase == "check" and not quick else base


def seed_for(phase: str, mode: str, replicate: int) -> int:
    seeds = SEEDS[phase][mode]
    if not 1 <= replicate <= len(seeds):
        raise SystemExit(f"{phase} has {len(seeds)} run(s) per mode")
    return seeds[replicate - 1]


def run_phase(phase: str, mode: str, replicate: int, out_root: Path, workers: int, quick: bool, stop_after: Optional[int]) -> Path:
    cfg = stage4a.world(quick)
    cma = cma_for(phase, quick)
    seed = seed_for(phase, mode, replicate)
    out = out_root / phase / f"{mode}-{seed}"
    fade, tighten = stage4b.path_generations(quick)
    champion_from = fade + tighten + 1
    manifest = build_manifest(protocol=f"stage4c/{phase}", settings={**cfg.as_dict(), "world": "stage 4a", "mode": mode,
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


def score_predictions(out_root: Path, champions: Sequence[Mapping[str, Any]], verdicts: Mapping[str, Any], comparisons: Sequence[Mapping[str, Any]],
                      q3: Mapping[str, Any], rows: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """§6's predictions 2-4, from the pilots' champion.json and the test (prediction 1 is the local check's)."""
    pilots = {c["mode"]: json.loads((out_root / "pilot" / c["run"] / "champion.json").read_text()) for c in champions if c["phase"] == "pilot"}
    above = {m: pilots[m].get("validation_fitness") for m in pilots}
    met = [m for m in pilots if (pilots[m].get("validation_survival") or 0.0) >= 0.5]
    beat = [x["run"] for x in comparisons if x["compared"] == "champion - B8" and x["phase"] == "confirm" and x["verdict"]]
    out = [
        (2, "the pilot's champions validate above the GA's amended pilot in both modes",
         len(above) == 2 and all(above[m] is not None and above[m] > GA_PILOT[m] for m in GA_PILOT), {"cma": above, "ga": GA_PILOT}),
        (3, "the pilot's rule is met in at most one mode", len(met) <= 1, {"met": met}),
        (4, "no confirmatory champion beats B8", not beat, {"beat": beat}),
    ]
    return [{"number": n, "text": text, "holds": bool(holds), "values": values} for n, text, holds, values in out]


def main(argv: Optional[Sequence[str]] = None) -> Any:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--phase", required=True, choices=["check", "pilot", "confirm", "test"])
    parser.add_argument("--mode", choices=list(MODES))
    parser.add_argument("--replicate", type=int, default=1)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--stop-after", type=int, default=None)
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    if args.phase == "test":
        return stage4b.test_phase(args.out, args.workers, args.quick, score=score_predictions)
    if args.mode is None:
        raise SystemExit("a run needs --mode")
    return run_phase(args.phase, args.mode, args.replicate, args.out, args.workers, args.quick, args.stop_after)


if __name__ == "__main__":
    main(sys.argv[1:])
