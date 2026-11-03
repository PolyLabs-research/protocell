"""Stage 4's second design probe: does a tighter economy leave room above every simple rule?

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage4_economy --workers 16
    .venv/bin/python -m experiments.stage4_economy --quick --out /tmp/s4e --workers 2   # the smoke test: not a result

Stage 4's first probe (experiments/stage4_probe.py) found every candidate world within 0.02-0.07 of its ceiling for
the best simple rule. In this economy a few hours of good light fill the reserve, and light beyond that is lost. A
check before this probe found B5 at a full reserve for 68% of its daylight ticks. This probe makes the light worth
more by scaling the photosynthetic gain eta down: to 0.55, 0.45 and 0.40 of the cave's. At 0.40 a still cell at the
brightest point still survives every start; at 0.35 it does not. The worlds are the first probe's reference, its
fast clouds, the sweep, and the spots circling every 6 and every 2 hours. Everything else is the first probe's: the
same starts and noise (seed 16), the same rules and grids chosen on starts 1-50 and reported on 51-100, the same
ceiling, and the headroom with its interval (seed 17). Also reported: the headroom as a share of the room between
the still cell (B0) and the ceiling. Writes docs/data/stage4/economy/.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from experiments import stage4_probe as first
from protocell.config import CAVE, Config
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.tables import write_csv
from protocell.world import sample_starts

WORLDS = ("reference", "flicker", "sweep", "spot_6h", "spot_2h")
SCALES = (0.55, 0.45, 0.40)
DEFAULT_OUT = Path("docs/data/stage4/economy")


def variant_cfg(world: str, scale: float, quick: bool) -> Config:
    return first.world_cfg(world, quick).but(eta=CAVE.eta * scale)


def run(out: Path, workers: int, quick: bool, only: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    n_starts = 8 if quick else 100
    select, report = ((1, 4), (5, 8)) if quick else (first.SELECT, first.REPORT)
    resamples = 200 if quick else first.RESAMPLES
    worlds = [w for w in WORLDS if not only or w in only]
    variants = {f"{w} eta x{s:g}": variant_cfg(w, s, quick) for w in worlds for s in SCALES}
    out.mkdir(parents=True, exist_ok=True)
    settings = {"base": first.configure(quick).as_dict(), "worlds": {w: first.WORLDS[w] for w in worlds}, "scales": SCALES, "cave_eta": CAVE.eta,
                "seed": first.SEED, "bootstrap_seed": first.BOOTSTRAP_SEED, "resamples": resamples, "n_starts": n_starts, "select": select,
                "report": report, "k_grid": first.K_GRID, "tau_grid": first.TAU_GRID, "b6_grid": first.B6_GRID, "b8_aim_tau": first.B8_AIM_TAU,
                "still_above": first.STILL_ABOVE, "perfect": first.PERFECT, "quick": quick}
    manifest = build_manifest(protocol="stage4_economy", settings=settings, seeds=[first.SEED, first.BOOTSTRAP_SEED], extra={"out": str(out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:7.1f}s {msg}", flush=True)

    jobs, ceiling_jobs = [], []
    for v, cfg in variants.items():
        starts = sample_starts(cfg, "cave", n_starts, first.SEED)
        jobs += [{"cfg": c, "starts": starts, "spec": spec, "world": v, "rule": rule, "param": param, "first": 0}
                 for rule, param, c, spec in first.rules(cfg)]
        ceiling_jobs.append({"cfg": cfg, "starts": starts, "world": v})
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        ceiling_futures = [pool.submit(first.ceiling_job, j) for j in ceiling_jobs]
        sim_futures = [pool.submit(first.sim_job, j) for j in jobs]
        ceilings = {f.result()["world"]: f.result() for f in ceiling_futures}
        log("the ceilings done")
        results = [f.result() for f in sim_futures]
        log(f"{len(results)} rule runs done")

    sel = np.arange(select[0] - 1, select[1])
    rep = np.arange(report[0] - 1, report[1])
    grid_rows, per_start_rows, headroom_rows, out_variants = [], [], [], {}
    key = 1000  # the bootstrap's keys, apart from the first probe's
    for v, cfg in variants.items():
        ceiling, ceiling_alive = ceilings[v]["fitness"], ceilings[v]["survived"]
        runs = {(r["rule"], r["param"]): r for r in results if r["world"] == v}
        for (rule, param), r in runs.items():
            for name, idx in (("select", sel), ("report", rep)):
                grid_rows.append({"variant": v, "rule": rule, "param": param, "starts": name, "mean_fitness": float(r["fitness"][idx].mean()),
                                  "survival": float(r["survived"][idx].mean()), "mean_beat": float(r["mean_beat"][idx].mean())})
            per_start_rows += [{"variant": v, "rule": rule, "param": param, "start": i + 1, "fitness": float(r["fitness"][i]),
                                "survived": int(r["survived"][i])} for i in range(n_starts)]
        per_start_rows += [{"variant": v, "rule": "ceiling", "param": "-", "start": i + 1, "fitness": float(ceiling[i]),
                            "survived": int(ceiling_alive[i])} for i in range(n_starts)]
        chosen: Dict[str, Dict[str, Any]] = {}
        for rule in ("B0", "B7", "B2r", "B5", "B6", "B8", "B6 perfect"):
            options = [(param, r) for (ru, param), r in runs.items() if ru == rule]
            i = max(range(len(options)), key=lambda i: (options[i][1]["fitness"][sel].mean(), options[i][1]["survived"][sel].mean(), -i))
            param, r = options[i]
            chosen[rule] = {"param": param, "fitness": r["fitness"][rep], "report_fitness": float(r["fitness"][rep].mean()),
                            "report_survival": float(r["survived"][rep].mean())}
        best = max(first.SIMPLE, key=lambda ru: chosen[ru]["report_fitness"])
        key += 1
        head, lo, hi = first.ci(ceiling[rep] - chosen[best]["fitness"], key, resamples)
        key += 1
        gain, glo, ghi = first.ci(chosen["B6 perfect"]["fitness"] - chosen[best]["fitness"], key, resamples)
        room = float(ceiling[rep].mean()) - chosen["B0"]["report_fitness"]
        out_variants[v] = {"ceiling": float(ceiling[rep].mean()), "ceiling_survival": float(ceiling_alive[rep].mean()),
                           "rules": {ru: {k: x for k, x in c.items() if k != "fitness"} for ru, c in chosen.items()}, "best_simple_rule": best,
                           "headroom": head, "headroom_low": lo, "headroom_high": hi, "share_of_room_left": head / room if room > 0 else None,
                           "perfect_reading_gain": gain, "perfect_reading_low": glo, "perfect_reading_high": ghi}
        headroom_rows.append({"variant": v, "ceiling": out_variants[v]["ceiling"], "ceiling_survival": out_variants[v]["ceiling_survival"],
                              "best_simple_rule": best, "its_param": chosen[best]["param"], "its_fitness": chosen[best]["report_fitness"],
                              "its_survival": chosen[best]["report_survival"], "headroom": head, "headroom_low": lo, "headroom_high": hi,
                              "share_of_room_left": out_variants[v]["share_of_room_left"], **{ru: chosen[ru]["report_fitness"] for ru in chosen}})
        log(f"{v:22s} ceiling {out_variants[v]['ceiling']:.3f} ({out_variants[v]['ceiling_survival']:.0%}); best {best} ({chosen[best]['param']}) "
            f"{chosen[best]['report_fitness']:.3f} ({chosen[best]['report_survival']:.0%}); headroom {head:+.3f} [{lo:+.3f}, {hi:+.3f}], "
            f"{out_variants[v]['share_of_room_left'] or 0:.0%} of the room; B5 {chosen['B5']['report_fitness']:.3f} B6 {chosen['B6']['report_fitness']:.3f} "
            f"B8 {chosen['B8']['report_fitness']:.3f} B6 perfect {chosen['B6 perfect']['report_fitness']:.3f} B0 {chosen['B0']['report_fitness']:.3f}")
    write_csv(out / "grid.csv", ("variant", "rule", "param", "starts", "mean_fitness", "survival", "mean_beat"), grid_rows)
    write_csv(out / "per_start.csv", ("variant", "rule", "param", "start", "fitness", "survived"), per_start_rows)
    write_csv(out / "headroom.csv", tuple(headroom_rows[0]), headroom_rows)
    summary = {"variants": out_variants, "quick": quick}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=first._json) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0, workers=workers, rule_runs=len(jobs))
    write_manifest(out / "manifest.json", manifest)
    log(f"done, written to {out}")
    return summary


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    parser.add_argument("--worlds", nargs="+", choices=list(WORLDS), help="only these worlds (the smoke test); default all")
    args = parser.parse_args(argv)
    return run(args.out, args.workers, args.quick, args.worlds)


if __name__ == "__main__":
    main(sys.argv[1:])
