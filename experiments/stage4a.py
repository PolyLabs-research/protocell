"""Stage 4a (docs/prereg/stage4.md): a world with room above every simple rule, checked by U1-U5.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage4a --workers 16
    .venv/bin/python -m experiments.stage4a --quick --out /tmp/s4a --workers 2   # the smoke test: not a result

The world (§2): stage 3's translucent pool with the mouth sweeping along the edge through the day and photosynthesis
at 0.55 of the cave's gain. On starts 1-100 at seed 18, with shared noise: B0 and B7; the ceiling, a still cell put at
the brightest point every tick; the simple rules B2r, B5, B6 and B8 with stage 4's probes' grids, each parameter chosen
on starts 1-50 by mean fitness and reported on starts 51-100, the bar the best of them there; B6 with perfect reading,
likewise; the stage 3b champions, uniform 2203 and fourier1 3202, as they are; 1,000 random genomes per spoke mode on
starts 51-70; determinism on short batches (U5). Reads U1-U5 (§5), scores the predictions (§6), and writes
docs/data/stage4a/.
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

from experiments import stage3c_probe
from experiments import stage4_probe as probe
from experiments.cave import RUN_COLUMNS, check_k6, run_summary
from experiments.stage0 import B3_COLUMNS, b3_job
from experiments.stage3 import configure
from protocell.cell import MODES, STREAM_GENOMES, random_genomes
from protocell.config import CAVE, Config
from protocell.evolve import NOISE_CELL_ID
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.rng import stream
from protocell.sim import simulate
from protocell.tables import write_csv
from protocell.world import Starts, sample_starts

SEED = 18  # fresh: the starts, the noise and the random genomes
BOOTSTRAP_SEED = 19
RESAMPLES = 10_000
GAIN_SCALE = 0.55  # the photosynthetic gain as a share of the cave's (§2)
SELECT, REPORT, GENOME_STARTS = (1, 50), (51, 100), (51, 70)
N_GENOMES, GENOMES_PER_JOB, W6_CELLS = 1000, 25, 5
CHUNK = 50
SIMPLE = probe.SIMPLE  # B2r, B5, B6, B8: the bar is the best of them
U1_B0_SURVIVAL, U1_CEILING_SURVIVAL = 0.10, 0.90
U2_HEADROOM, U2_LOW, U2_ROOM = 0.10, 0.05, 0.20
U3_RECOVERED = 0.5
U4_SHARE = 0.05
DEFAULT_OUT = Path("docs/data/stage4a")


def world(quick: bool = False) -> Config:
    """§2's world."""
    return configure(quick).but(cave_sweep=True, eta=CAVE.eta * GAIN_SCALE)


def champion_spec(name: str, n: int) -> Dict[str, Any]:
    mode, path = stage3c_probe.CHAMPIONS[name]
    return {"controller": "network", "mode": mode, "genomes": np.repeat(np.load(path).reshape(1, -1), n, axis=0)}


def sim_job(job: Mapping[str, Any]) -> Dict[str, Any]:
    starts: Starts = job["starts"]
    r = simulate(job["cfg"], starts, job["spec"], seed=SEED, cell_ids=[NOISE_CELL_ID] * len(starts))
    return {"rule": job["rule"], "param": job["param"], "first": job["first"], "fitness": r.fitness, "survived": r.survived,
            "mean_beat": r.mean_beat, "rows": r.rows(starts, rule=job["rule"], param=job["param"]), "result": r}


def ceiling_job(job: Mapping[str, Any]) -> Dict[str, Any]:
    cfg: Config = job["cfg"]
    if cfg.cloud_shade != 1.0:
        raise ValueError("stage 4a's world has no clouds; the probe's ceiling would draw its sky at the probe's seed")
    fitness, survived = probe.always_brightest(cfg, job["starts"])
    return {"first": job["first"], "fitness": fitness, "survived": survived}


def ci(diff: np.ndarray, key: int, resamples: int) -> Tuple[float, float, float]:
    idx = stream(BOOTSTRAP_SEED, "bootstrap", (key,)).integers(0, diff.shape[0], size=(resamples, diff.shape[0]))
    means = diff[idx].mean(axis=1)
    return float(diff.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def choose(runs: Mapping[Tuple[str, str], Mapping[str, np.ndarray]], rule: str, sel: np.ndarray) -> Tuple[str, Mapping[str, np.ndarray]]:
    """A rule's parameter: the best mean fitness on the selection starts, then survival, then the first in the grid."""
    options = [(param, r) for (ru, param), r in runs.items() if ru == rule]
    i = max(range(len(options)), key=lambda i: (options[i][1]["fitness"][sel].mean(), options[i][1]["survived"][sel].mean(), -i))
    return options[i]


def read_checks(b0: Mapping[str, np.ndarray], ceiling: Mapping[str, np.ndarray], chosen: Mapping[str, Mapping[str, Any]], bar: str,
                headroom: Tuple[float, float, float], random_rows: Sequence[Mapping[str, Any]], k6: Mapping[str, Any],
                rep: np.ndarray) -> Dict[str, Any]:
    """U1-U5 (§5)."""
    u1 = {"b0_survival": float(b0["survived"].mean()), "ceiling_survival": float(ceiling["survived"].mean())}
    u1["pass"] = bool(u1["b0_survival"] <= U1_B0_SURVIVAL and u1["ceiling_survival"] >= U1_CEILING_SURVIVAL)
    head, lo, hi = headroom
    room = float(ceiling["fitness"][rep].mean() - b0["fitness"][rep].mean())
    u2 = {"bar": bar, "headroom": head, "low": lo, "high": hi, "room": room, "share_of_room": head / room if room > 0 else math.nan}
    u2["pass"] = bool(head >= U2_HEADROOM and lo > U2_LOW and u2["share_of_room"] >= U2_ROOM)
    recovered = (chosen["B6 perfect"]["report_fitness"] - chosen[bar]["report_fitness"]) / head if head > 0 else math.nan
    u3 = {"b6_perfect": chosen["B6 perfect"]["report_fitness"], "recovered_share": recovered, "pass": bool(recovered >= U3_RECOVERED)}
    bar_survival = chosen[bar]["report_survival"]
    u4: Dict[str, Any] = {"bar_survival": bar_survival}
    for mode in MODES:
        mine = [r for r in random_rows if r["mode"] == mode]
        survival = np.array([float(r["survival"]) for r in mine])
        fitness = np.array([float(r["mean_fitness"]) for r in mine])
        u4[mode] = {"n_genomes": len(mine), "share_matching_bar_survival": float(np.mean(survival >= bar_survival)) if mine else math.nan,
                    "best_fitness": float(fitness.max()) if mine else math.nan, "mean_survival": float(survival.mean()) if mine else math.nan}
    u4["pass"] = bool(all(u4[m]["share_matching_bar_survival"] < U4_SHARE for m in MODES))
    u5 = {**k6}
    return {"U1": u1, "U2": u2, "U3": u3, "U4": u4, "U5": u5}


def score_predictions(checks: Mapping[str, Any], chosen: Mapping[str, Mapping[str, Any]], champions: Mapping[str, float]) -> List[Dict[str, Any]]:
    """§6's predictions, on the reported means."""
    u2, u3, u4 = checks["U2"], checks["U3"], checks["U4"]
    bar = u2["bar"]
    best_random = max(u4[m]["best_fitness"] for m in MODES)
    out = [
        (1, "U1-U5 pass", all(checks[c]["pass"] for c in ("U1", "U2", "U3", "U4", "U5")), {c: checks[c]["pass"] for c in checks}),
        (2, "the bar is B5 or B8, with fitness 0.50-0.58", bar in ("B5", "B8") and 0.50 <= chosen[bar]["report_fitness"] <= 0.58,
         {"bar": bar, "fitness": chosen[bar]["report_fitness"]}),
        (3, "the headroom is 0.12-0.18, 25-33% of the room", 0.12 <= u2["headroom"] <= 0.18 and 0.25 <= u2["share_of_room"] <= 0.33,
         {"headroom": u2["headroom"], "share_of_room": u2["share_of_room"]}),
        (4, "B6 with perfect reading recovers 70-85% of the headroom", 0.70 <= u3["recovered_share"] <= 0.85, {"recovered": u3["recovered_share"]}),
        (5, "both stage 3b champions score below 0.40", all(v < 0.40 for v in champions.values()), dict(champions)),
        (6, "no random genome matches the bar's survival, and the best scores below 0.25",
         all(u4[m]["share_matching_bar_survival"] == 0.0 for m in MODES) and best_random < 0.25,
         {"best_random": best_random, **{m: u4[m]["share_matching_bar_survival"] for m in MODES}}),
    ]
    return [{"number": n, "text": text, "holds": bool(holds), "values": values} for n, text, holds, values in out]


def run(out: Path, workers: int, quick: bool) -> Dict[str, Any]:
    cfg = world(quick)
    n_starts = 8 if quick else 100
    select, report = ((1, 4), (5, 8)) if quick else (SELECT, REPORT)
    genome_starts, n_genomes, w6 = ((5, 6), 4, 2) if quick else (GENOME_STARTS, N_GENOMES, W6_CELLS)
    resamples = 200 if quick else RESAMPLES
    chunk = 4 if quick else CHUNK
    out.mkdir(parents=True, exist_ok=True)
    settings = {**cfg.as_dict(), "gain_scale": GAIN_SCALE, "seed": SEED, "bootstrap_seed": BOOTSTRAP_SEED, "resamples": resamples,
                "n_starts": n_starts, "select": select, "report": report, "k_grid": probe.K_GRID, "tau_grid": probe.TAU_GRID,
                "b6_grid": probe.B6_GRID, "b8_aim_tau": probe.B8_AIM_TAU, "still_above": probe.STILL_ABOVE, "perfect": probe.PERFECT,
                "genome_starts": genome_starts, "n_genomes": n_genomes, "w6_cells": w6,
                "thresholds": {"U1": [U1_B0_SURVIVAL, U1_CEILING_SURVIVAL], "U2": [U2_HEADROOM, U2_LOW, U2_ROOM], "U3": U3_RECOVERED,
                               "U4": U4_SHARE}, "quick": quick}
    manifest = build_manifest(protocol="stage4a", settings=settings, seeds=[SEED, BOOTSTRAP_SEED], extra={"out": str(out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:7.1f}s {msg}", flush=True)

    starts = sample_starts(cfg, "cave", n_starts, SEED)
    chunks = [(lo, starts.take(range(lo, min(lo + chunk, n_starts)))) for lo in range(0, n_starts, chunk)]
    jobs = [{"cfg": c, "starts": part, "spec": spec, "rule": rule, "param": param, "first": lo}
            for rule, param, c, spec in probe.rules(cfg) for lo, part in chunks]
    jobs += [{"cfg": cfg, "starts": part, "spec": champion_spec(name, len(part)), "rule": name, "param": "-", "first": lo}
             for name in stage3c_probe.CHAMPIONS for lo, part in chunks]
    chosen_starts = starts.numbered(range(genome_starts[0], genome_starts[1] + 1))
    genome_jobs = []
    for mode in MODES:
        genomes = random_genomes(cfg, mode, n_genomes, stream(SEED, STREAM_GENOMES))
        for lo in range(0, n_genomes, GENOMES_PER_JOB):
            hi = min(lo + GENOMES_PER_JOB, n_genomes)
            genome_jobs.append({"cfg": cfg, "starts": chosen_starts, "genomes": genomes[lo:hi], "numbers": np.arange(lo + 1, hi + 1),
                                "mode": mode, "seed": SEED})
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        ceiling_futures = [pool.submit(ceiling_job, {"cfg": cfg, "starts": part, "first": lo}) for lo, part in chunks]
        sim_futures = [pool.submit(sim_job, j) for j in jobs]
        genome_futures = [pool.submit(b3_job, j) for j in genome_jobs]
        ceiling_parts = [f.result() for f in ceiling_futures]
        results = [f.result() for f in sim_futures]
        log(f"the ceiling and {len(results)} rule runs done")
        random_rows = [row for f in genome_futures for row in f.result()]
        log(f"{len(random_rows)} random genomes done")

    def gather(parts: Sequence[Mapping[str, Any]], key: str) -> np.ndarray:
        return np.concatenate([p[key] for p in sorted(parts, key=lambda p: p["first"])])

    sel, rep = np.arange(select[0] - 1, select[1]), np.arange(report[0] - 1, report[1])
    runs: Dict[Tuple[str, str], Dict[str, np.ndarray]] = {}
    per_start: List[Dict[str, Any]] = []
    for rule, param in dict.fromkeys((r["rule"], r["param"]) for r in results):
        mine = [r for r in results if r["rule"] == rule and r["param"] == param]
        runs[(rule, param)] = {k: gather(mine, k) for k in ("fitness", "survived", "mean_beat")}
        per_start += [row for p in sorted(mine, key=lambda p: p["first"]) for row in p["rows"]]
    ceiling = {k: gather(ceiling_parts, k) for k in ("fitness", "survived")}
    per_start += [{"rule": "ceiling", "param": "-", "start": i + 1, "fitness": float(ceiling["fitness"][i]), "survived": int(ceiling["survived"][i])}
                  for i in range(n_starts)]
    grid = [{"rule": rule, "param": param, "starts": name, "mean_fitness": float(r["fitness"][idx].mean()), "survival": float(r["survived"][idx].mean()),
             "mean_beat": float(r["mean_beat"][idx].mean())} for (rule, param), r in runs.items() for name, idx in (("select", sel), ("report", rep))]
    chosen: Dict[str, Dict[str, Any]] = {}
    for rule in ("B0", "B7", *SIMPLE, "B6 perfect", *stage3c_probe.CHAMPIONS):
        param, r = choose(runs, rule, sel)
        chosen[rule] = {"param": param, "report_fitness": float(r["fitness"][rep].mean()), "report_survival": float(r["survived"][rep].mean()),
                        "report_mean_beat": float(r["mean_beat"][rep].mean())}
    bar = max(SIMPLE, key=lambda ru: chosen[ru]["report_fitness"])
    bar_runs = runs[(bar, chosen[bar]["param"])]
    headroom = ci(ceiling["fitness"][rep] - bar_runs["fitness"][rep], 1, resamples)
    bar_spec = next(spec for rule, param, _, spec in probe.rules(cfg) if rule == bar and param == chosen[bar]["param"])
    k6 = check_k6(cfg, starts.numbered(range(report[0], report[0] + w6)), bar_spec, w6, seed=SEED)
    log(f"U5 (determinism) {'passes' if k6['pass'] else 'FAILS'}")
    checks = read_checks(runs[("B0", "-")], ceiling, chosen, bar, headroom, random_rows, k6, rep)
    champions = {name: chosen[name]["report_fitness"] for name in stage3c_probe.CHAMPIONS}
    predictions = score_predictions(checks, chosen, champions)
    write_csv(out / "grid.csv", ("rule", "param", "starts", "mean_fitness", "survival", "mean_beat"), grid)
    write_csv(out / "per_start.csv", ("rule", "param", *RUN_COLUMNS), per_start)
    write_csv(out / "random_genomes.csv", B3_COLUMNS, random_rows)
    for line in (f"U1: B0 survives {checks['U1']['b0_survival']:.0%}, the ceiling {checks['U1']['ceiling_survival']:.0%}",
                 f"U2: the bar {bar} ({chosen[bar]['param']}) {chosen[bar]['report_fitness']:.3f}, survival {chosen[bar]['report_survival']:.0%}; "
                 f"the ceiling {ceiling['fitness'][rep].mean():.3f}; headroom {headroom[0]:+.3f} [{headroom[1]:+.3f}, {headroom[2]:+.3f}], "
                 f"{checks['U2']['share_of_room']:.0%} of the room",
                 f"U3: B6 with perfect reading {checks['U3']['b6_perfect']:.3f}, recovers {checks['U3']['recovered_share']:.0%}",
                 "U4: " + "; ".join(f"{m} {checks['U4'][m]['share_matching_bar_survival']:.1%} match the bar's survival, best {checks['U4'][m]['best_fitness']:.3f}"
                                    for m in MODES),
                 "rules: " + ", ".join(f"{ru} {chosen[ru]['report_fitness']:.3f} ({chosen[ru]['param']})" for ru in chosen),
                 ", ".join(f"{c} {'pass' if checks[c]['pass'] else 'FAIL'}" for c in checks)):
        log(line)
    for p in predictions:
        log(f"prediction {p['number']}: {'✓' if p['holds'] else '✗'} {p['text']}")
    summary = {"checks": checks, "verdict": {c: checks[c]["pass"] for c in checks}, "bar": {"rule": bar, **chosen[bar]}, "rules": chosen,
               "ceiling": {"report_fitness": float(ceiling["fitness"][rep].mean()), "survival": float(ceiling["survived"].mean())},
               "predictions": predictions, "run_summaries": {f"{ru} {p}": run_summary(_merge([r for r in results if r["rule"] == ru and r["param"] == p]))
                                                              for ru, p in ((ru, chosen[ru]["param"]) for ru in chosen)}, "quick": quick}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=probe._json) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0, workers=workers, rule_runs=len(jobs), genome_jobs=len(genome_jobs))
    write_manifest(out / "manifest.json", manifest)
    log(f"done, written to {out}")
    return summary


def _merge(parts: Sequence[Mapping[str, Any]]) -> Any:
    return stage3c_probe._merge([{"result": p["result"]} for p in sorted(parts, key=lambda p: p["first"])])


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    args = parser.parse_args(argv)
    return run(args.out, args.workers, args.quick)


if __name__ == "__main__":
    main(sys.argv[1:])
