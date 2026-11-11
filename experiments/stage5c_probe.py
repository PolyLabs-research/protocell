"""Stage 5c's design probe (docs/decisions.md D27 C1, D28): how much change does design 16 stand?

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage5c_probe
    .venv/bin/python -m experiments.stage5c_probe --quick --out /tmp/s5c   # the smoke test: not a result

Stage 5c would start a search at stage 5b's hand-written fourier1 cell (design 16). A search's first step moves every
gene at once, and the design's copies were calibrated to two decimal places, so the step's size has to be measured
before a draft names it. This probe is a calculator for that draft, not a result.

For each step size sigma, as a share of each gene's range, it draws 48 neighbours of design 16 as the searches would:
every gene moved by a normal step of that size, mirrored at its bounds, the cilium angle wrapping
(``protocell.cmaes.to_genomes``; the GA's mutation at 0.02 is the same draw). Each neighbour runs in stage 4a's world
with stage 5's cell on 8 fresh starts at seed 31 with shared noise, beside design 16 itself, B8 and B0. Reported per
step size: the neighbours' fitness and survival, the share of the gap from B0 to B8 they keep, how many score at
least design 16's, and the seconds a batch took (the draft's cost estimate). One process. Writes
docs/data/stage5c/probe/.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from experiments import stage4_thrift as thrift
from experiments import stage4e, stage5b
from protocell.cell import genome_ranges
from protocell.cmaes import to_genomes
from protocell.config import Config
from protocell.evolve import NOISE_CELL_ID
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.rng import stream
from protocell.sim import simulate
from protocell.tables import write_csv
from protocell.world import sample_starts

SEED = 31  # fresh: the starts, the noise and the neighbours
STREAM_NEIGHBOURS = "neighbours"
SIGMAS = (0.002, 0.005, 0.01, 0.02, 0.05)  # 0.02 is the GA's mutation; 0.05 is stage 4c's first step (revision R1)
NEIGHBOURS, STARTS = 48, 8  # half a generation's genomes, a generation's training starts
SEED_DESIGN = Path("docs/data/stage5b/fourier1/designs/s16.json")
DEFAULT_OUT = Path("docs/data/stage5c/probe")
ROW_COLUMNS = ("sigma", "neighbour", "fitness", "survival", "mean_beat", "light_soaked")
SUMMARY_COLUMNS = ("sigma", "mean_fitness", "median_fitness", "best_fitness", "mean_survival", "mean_gap_share", "median_gap_share",
                   "share_at_least_seed", "share_above_half_gap", "seconds_a_batch")


def neighbours(cfg: Config, mode: str, seed_genome: np.ndarray, sigma: float, n: int, index: int) -> np.ndarray:
    """``n`` genomes around ``seed_genome``, each gene a normal step of ``sigma`` of its range away, from stream
    ``neighbours`` keyed by the step size's place in the ladder."""
    lo, hi = genome_ranges(cfg, mode)
    centre = (seed_genome - lo) / (hi - lo)
    z = stream(SEED, STREAM_NEIGHBOURS, (index,)).standard_normal((n, centre.shape[0]))
    return to_genomes(cfg, mode, centre[None, :] + sigma * z)


def run_batch(cfg: Config, starts, spec: Dict[str, Any], n: int) -> Dict[str, np.ndarray]:
    """``n`` cells on every start, one batch a start with shared noise: ``(n, starts)`` matrices."""
    cols: Dict[str, List[np.ndarray]] = {"fitness": [], "survived": [], "mean_beat": [], "light_soaked": []}
    for s in range(len(starts)):
        r = simulate(cfg, starts.take([s] * n), spec, seed=SEED, cell_ids=[NOISE_CELL_ID] * n)
        for k in cols:
            cols[k].append(np.asarray(getattr(r, k), dtype=float))
    return {k: np.stack(v, axis=1) for k, v in cols.items()}


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    cfg = stage5b.world(args.quick)
    n, n_starts, sigmas = (4, 2, SIGMAS[1::3]) if args.quick else (NEIGHBOURS, STARTS, SIGMAS)
    design = stage4e.load(SEED_DESIGN)
    mode = design["mode"]
    g0 = stage4e.genome(cfg, design)
    starts = sample_starts(cfg, "cave", n_starts, SEED)
    manifest = build_manifest(protocol="stage5c/probe", settings={"world": cfg.as_dict(), "mode": mode, "design": SEED_DESIGN.name,
                                                                  "design_sha": stage4e.sha(design), "sigmas": list(sigmas), "neighbours": n,
                                                                  "starts": n_starts, "quick": args.quick},
                              seeds=[SEED], extra={"out": str(args.out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:7.0f}s {msg}", flush=True)

    refs = {}
    for name, spec in (("design 16", {"controller": "network", "mode": mode, "genomes": g0[None]}),
                       ("B8", thrift.cell_spec(cfg, "B8", 1)), ("B0", thrift.cell_spec(cfg, "B0", 1))):
        r = run_batch(cfg, starts, spec, 1)
        refs[name] = {"fitness": float(r["fitness"].mean()), "survival": float(r["survived"].mean()), "per_start": r["fitness"][0].tolist()}
        log(f"{name}: fitness {refs[name]['fitness']:.3f}, survival {refs[name]['survival']:.0%}")
    b0, b8, seed_fit = refs["B0"]["fitness"], refs["B8"]["fitness"], refs["design 16"]["fitness"]
    rows: List[Dict[str, Any]] = []
    summary: List[Dict[str, Any]] = []
    for index, sigma in enumerate(SIGMAS):
        if sigma not in sigmas:
            continue
        t1 = time.time()
        genomes = neighbours(cfg, mode, g0, sigma, n, index)
        r = run_batch(cfg, starts, {"controller": "network", "mode": mode, "genomes": genomes}, n)
        fit, surv = r["fitness"].mean(axis=1), r["survived"].mean(axis=1)
        share = (fit - b0) / (b8 - b0)
        rows += [{"sigma": sigma, "neighbour": i + 1, "fitness": float(fit[i]), "survival": float(surv[i]),
                  "mean_beat": float(r["mean_beat"][i].mean()), "light_soaked": float(r["light_soaked"][i].mean())} for i in range(n)]
        summary.append({"sigma": sigma, "mean_fitness": float(fit.mean()), "median_fitness": float(np.median(fit)), "best_fitness": float(fit.max()),
                        "mean_survival": float(surv.mean()), "mean_gap_share": float(share.mean()), "median_gap_share": float(np.median(share)),
                        "share_at_least_seed": float(np.mean(fit >= seed_fit)), "share_above_half_gap": float(np.mean(share >= 0.5)),
                        "seconds_a_batch": round((time.time() - t1) / n_starts, 1)})
        s = summary[-1]
        log(f"sigma {sigma}: mean {s['mean_fitness']:.3f}, median {s['median_fitness']:.3f}, best {s['best_fitness']:.3f}, survival "
            f"{s['mean_survival']:.0%}, gap share {s['mean_gap_share']:.2f}, at least the seed {s['share_at_least_seed']:.0%} "
            f"[{s['seconds_a_batch']:.0f} s a batch]")
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "neighbours.csv", ROW_COLUMNS, rows)
    write_csv(args.out / "summary.csv", SUMMARY_COLUMNS, summary)
    result = {"references": refs, "ladder": summary, "quick": args.quick}
    (args.out / "summary.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0)
    write_manifest(args.out / "manifest.json", manifest)
    return result


if __name__ == "__main__":
    main(sys.argv[1:])
