"""The design probe behind amendment A1 to docs/prereg/cave.md: B2rr's retreat triggered by the wall's mean light (as
preregistered) or by its brightest node, at three gains, in the burn and sweep configurations, on fresh starts (seed
1 for the starts and the noise, never the cave's seed 2).

    .venv/bin/python -W error::RuntimeWarning -m experiments.cave_retreat_probe --workers 12

Writes ``docs/data/cave/retreat_probe/probe.csv`` and its ``manifest.json``. A probe decides an amendment's wording;
it is not one of the checks.
"""

from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

from experiments.cave import configure
from experiments.stage0 import write_csv
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.sim import BURNT, STARVED, simulate
from protocell.world import sample_starts

PROBE_SEED = 1
CONFIGS = ("burn", "sweep")
TRIGGERS = ("mean", "max")
GAINS = (1.0, 10.0, 100.0)
COLUMNS = ("configuration", "trigger", "k", "n", "survival", "burnt", "starved", "mean_fitness", "mean_burn_share", "mean_beat")
DEFAULT_OUT = Path("docs/data/cave/retreat_probe")


def jobs(n_starts: int = 20, quick: bool = False) -> List[Dict[str, Any]]:
    return [{"config": c, "trigger": t, "k": k, "n": n_starts, "quick": quick} for c in CONFIGS for t in TRIGGERS for k in GAINS]


def run_job(job: Dict[str, Any]) -> Dict[str, Any]:
    cfg = configure(job["config"], job["quick"])
    starts = sample_starts(cfg, "cave", job["n"], seed=PROBE_SEED)
    spec = {"controller": "reflex", "k": job["k"], "rest_below": cfg.rest_below, "retreat_above": cfg.damage_threshold,
            "retreat_on": job["trigger"]}
    r = simulate(cfg, starts, spec, seed=PROBE_SEED)
    return {"configuration": job["config"], "trigger": job["trigger"], "k": job["k"], "n": job["n"], "survival": float(r.survived.mean()),
            "burnt": float((r.death_cause == BURNT).mean()), "starved": float((r.death_cause == STARVED).mean()),
            "mean_fitness": float(r.fitness.mean()), "mean_burn_share": float(r.burn_share.mean()), "mean_beat": float(r.mean_beat.mean())}


def main(argv: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--starts", type=int, default=20)
    parser.add_argument("--quick", action="store_true", help="the smoke test's day: not a result")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    todo = jobs(args.starts, args.quick)
    manifest = build_manifest(protocol="cave/retreat_probe", settings={"jobs": todo, "seed": PROBE_SEED}, seeds=[PROBE_SEED])
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as pool:
        rows = list(pool.map(run_job, todo))
    for r in rows:
        print(f"{r['configuration']:5s} retreat on {r['trigger']:4s} k={r['k']:5g}: survived {r['survival']:.2f}, burnt {r['burnt']:.2f}, "
              f"starved {r['starved']:.2f}, fitness {r['mean_fitness']:.3f}, in the burn zone {r['mean_burn_share']:.3f}", flush=True)
    write_csv(args.out / "probe.csv", COLUMNS, rows)
    finish_manifest(manifest, wall_seconds=time.time() - t0, cells=sum(r["n"] for r in rows))
    write_manifest(args.out / "manifest.json", manifest)
    return rows


if __name__ == "__main__":
    main(sys.argv[1:])
