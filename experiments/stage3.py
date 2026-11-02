"""Stage 3a (docs/prereg/stage3.md): the translucent cell's world and its baselines, checked by T1–T7.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage3 --workers 16
    .venv/bin/python -m experiments.stage3 --quick --out /tmp/s3 --workers 2   # the smoke test: not a result

The cave's day configuration with the cell translucent (the shading floor 1) and the falloff 600 R by the cave's rule
R1. Starts 1–100 at seed 8. T2 and T3 come from the starts' geometry; B0 on every start and at the best fixed point
(T1); B1 (T4's clause); B2r's gain and B5's time constant chosen on starts 1–50 and reported on 51–100 (T4, T5); 1,000
random genomes per spoke mode on starts 51–70 (T6); determinism on short batches (T7); B5's headroom below the still
cell at the best point. Writes ``docs/data/stage3/``.
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

from experiments.cave import RUN_COLUMNS, best_fixed_point, best_gain, check_k6, run_summary
from experiments.stage0 import B3_COLUMNS, K_GRID, Sizes, _json_default, b3_job, numbers, share
from protocell.cell import MODES, STREAM_GENOMES, genome_length, random_genomes
from protocell.config import CAVE, Config
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.rng import stream
from protocell.sim import NOISE_CHUNK, RunResult, simulate
from protocell.tables import write_csv
from protocell.world import Starts, mouth_position, node_light, sample_starts

SEED = 8  # stage 3's starts, genomes and noise (stage3.md §4): fresh
SHADE_FLOOR = 1.0  # the translucent cell: no self-shading (stage3.md §1)
FALLOFF = 600.0  # by the cave's rule R1 for a translucent cell (stage3.md §2; experiments/stage3_geometry.py)
TAU_GRID: Tuple[float, ...] = (3.0, 10.0, 30.0, 100.0, 300.0)  # B5's memory time constants, s
T5_MARGIN = 0.02
BOOTSTRAP_SEED = 9
RESAMPLES = 10_000
DEFAULT_OUT = Path("docs/data/stage3")
STARTS_COLUMNS = ("start", "phase", "pos_x", "pos_y", "heading", "mouth_distance", "noon_wall_mean", "noon_spread", "spread_ge_3sd",
                  "noon_wall_mean_100R_nearer", "rise", "rise_ge_3sd")


def configure(quick: bool = False) -> Config:
    cfg = CAVE.but(cave_cycle=True, damage_threshold=math.inf, cave_sweep=False, shade_floor=SHADE_FLOOR, cave_falloff=FALLOFF)
    return cfg.but(day_ticks=2000, lifetime=4000) if quick else cfg


def sim_job(job: Mapping[str, Any]) -> RunResult:
    return simulate(job["cfg"], job["starts"], job["spec"], seed=SEED)


def reflex(cfg: Config, k: float) -> Dict[str, Any]:
    return {"controller": "reflex", "k": k, "rest_below": cfg.rest_below}


def runwait(cfg: Config, tau: float) -> Dict[str, Any]:
    return {"controller": "runwait", "tau": tau, "rest_below": cfg.rest_below}


def starts_table(cfg: Config, starts: Starts) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    """T2 and T3 at noon from the starts' poses: the spread of the noiseless light over the wall against three times
    the sensor noise; the rise of the wall's mean light 100 R nearer the mouth against three times that mean's noise."""
    n = len(starts)
    noon = np.full(n, cfg.day_ticks // 4)
    light = node_light(cfg, "cave", starts.source, starts.pos, starts.heading, noon)
    spread = light.max(axis=1) - light.min(axis=1)
    mouth = mouth_position(cfg, noon)
    toward = mouth - starts.pos
    dist = np.sqrt(toward[:, 0] ** 2 + toward[:, 1] ** 2)
    nearer = starts.pos + toward * (np.minimum(100.0, dist) / np.maximum(dist, 1e-300))[:, None]
    mean_here = light.mean(axis=1)
    mean_nearer = node_light(cfg, "cave", starts.source, nearer, starts.heading, noon).mean(axis=1)
    rise = mean_nearer - mean_here
    t_spread, t_rise = 3.0 * cfg.sensor_noise_sd, 3.0 * cfg.sensor_noise_sd / math.sqrt(cfg.n_wall)
    rows = [{"start": int(starts.index[i]), "phase": int(starts.phase[i]), "pos_x": starts.pos[i, 0], "pos_y": starts.pos[i, 1],
             "heading": starts.heading[i], "mouth_distance": dist[i], "noon_wall_mean": mean_here[i], "noon_spread": spread[i],
             "spread_ge_3sd": spread[i] >= t_spread, "noon_wall_mean_100R_nearer": mean_nearer[i], "rise": rise[i], "rise_ge_3sd": rise[i] >= t_rise}
            for i in range(n)]
    t2 = {"threshold": t_spread, "share_spread_ge_3sd": share(spread >= t_spread), "median_spread": float(np.median(spread))}
    t2["pass"] = bool(t2["share_spread_ge_3sd"] <= 0.10)
    t3 = {"threshold": t_rise, "share_rise_ge_3sd": share(rise >= t_rise), "median_rise": float(np.median(rise))}
    t3["pass"] = bool(t3["share_rise_ge_3sd"] >= 0.5)
    return rows, t2, t3


def run(out: Path, workers: int, quick: bool) -> Dict[str, Any]:
    cfg = configure(quick)
    sizes = Sizes.quick() if quick else Sizes()
    resamples = 200 if quick else RESAMPLES
    out.mkdir(parents=True, exist_ok=True)
    settings = {**cfg.as_dict(), "seed": SEED, "sizes": sizes.__dict__, "k_grid": K_GRID, "tau_grid": TAU_GRID, "t5_margin": T5_MARGIN,
                "noise_chunk": NOISE_CHUNK, "genome_length": {m: genome_length(cfg, m) for m in MODES}, "quick": quick}
    manifest = build_manifest(protocol="stage3a", settings=settings, seeds=[SEED, BOOTSTRAP_SEED], extra={"out": str(out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:7.1f}s {msg}", flush=True)

    starts = sample_starts(cfg, "cave", sizes.n_starts, SEED)
    rows, t2, t3 = starts_table(cfg, starts)
    write_csv(out / "starts.csv", STARTS_COLUMNS, rows)
    log(f"T2 direction readable at once on {t2['share_spread_ge_3sd']:.0%}; T3 rise over 100 R readable on {t3['share_rise_ge_3sd']:.0%}")
    full = sizes.n_genomes >= 100
    point, probed = best_fixed_point(cfg, 1000 if full else 40, None if full else (0, cfg.day_ticks // 2))
    select, report = starts.numbered(numbers(sizes.select)), starts.numbered(numbers(sizes.report))
    jobs: Dict[str, Dict[str, Any]] = {
        "b0": {"cfg": cfg, "starts": starts, "spec": {"controller": "still"}},
        "b0_best": {"cfg": cfg, "starts": starts.with_pos(np.repeat(point[None, :], len(starts), axis=0)), "spec": {"controller": "still"}},
        "b1": {"cfg": cfg, "starts": starts, "spec": {"controller": "random"}},
    }
    for k in K_GRID:
        jobs[f"b2r_k{k:g}"] = {"cfg": cfg, "starts": select, "spec": reflex(cfg, k)}
    for tau in TAU_GRID:
        jobs[f"b5_tau{tau:g}"] = {"cfg": cfg, "starts": select, "spec": runwait(cfg, tau)}
    genome_starts = starts.numbered(numbers(sizes.genome_starts))
    b3_jobs = {mode: [{"cfg": cfg, "starts": genome_starts, "genomes": g[lo:lo + sizes.genomes_per_job], "mode": mode, "seed": SEED,
                       "numbers": np.arange(lo + 1, min(lo + sizes.genomes_per_job, sizes.n_genomes) + 1)}
                      for g in [random_genomes(cfg, mode, sizes.n_genomes, stream(SEED, STREAM_GENOMES))]
                      for lo in range(0, sizes.n_genomes, sizes.genomes_per_job)] for mode in MODES}
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {key: pool.submit(sim_job, job) for key, job in jobs.items()}
        b3_futures = {mode: [pool.submit(b3_job, j) for j in b3_jobs[mode]] for mode in MODES}
        results = {key: f.result() for key, f in futures.items()}
        b2r_sel = {k: run_summary(results[f"b2r_k{k:g}"]) for k in K_GRID}
        b5_sel = {tau: run_summary(results[f"b5_tau{tau:g}"]) for tau in TAU_GRID}
        k_r = best_gain(b2r_sel)
        tau_best = max(TAU_GRID, key=lambda tau: (b5_sel[tau]["mean_fitness"], b5_sel[tau]["survival"], -tau))
        second = {"b2r": pool.submit(sim_job, {"cfg": cfg, "starts": report, "spec": reflex(cfg, k_r)}),
                  "b5": pool.submit(sim_job, {"cfg": cfg, "starts": report, "spec": runwait(cfg, tau_best)})}
        b2r, b5 = second["b2r"].result(), second["b5"].result()
        b3 = {mode: [row for f in b3_futures[mode] for row in f.result()] for mode in MODES}
    cells = sum(len(r) for r in results.values()) + len(b2r) + len(b5) + sum(len(v) for v in b3.values()) * len(numbers(sizes.genome_starts))

    b0, b0_best, b1 = results["b0"], results["b0_best"], results["b1"]
    for name, r, st in (("b0", b0, starts), ("b0_best", b0_best, starts), ("b1", b1, starts), ("b2r_report", b2r, report), ("b5_report", b5, report)):
        write_csv(out / f"{name}.csv", RUN_COLUMNS, r.rows(st))
    write_csv(out / "b2r_select.csv", ("k", *RUN_COLUMNS), [row for k in K_GRID for row in results[f"b2r_k{k:g}"].rows(select, k=k)])
    write_csv(out / "b5_select.csv", ("tau", *RUN_COLUMNS), [row for tau in TAU_GRID for row in results[f"b5_tau{tau:g}"].rows(select, tau=tau)])
    full_share = share(b0_best.survived & (b0_best.min_sunset_energy >= 0.95))
    t1 = {"b0": run_summary(b0), "b0_survival": share(b0.survived), "probe": probed, "b0_best": run_summary(b0_best),
          "b0_best_survived_full_share": full_share}
    t1["pass"] = bool(t1["b0_survival"] <= 0.10 and full_share >= 0.9)
    log(f"T1 B0 survives on {t1['b0_survival']:.0%}; at the best fixed point full at each sunset on {full_share:.0%}")
    t4 = {"b1": run_summary(b1), "b1_survival": share(b1.survived), "b2r": {"k": k_r, "selection": {str(k): b2r_sel[k] for k in K_GRID},
          "report": run_summary(b2r)}, "b5": {"tau": tau_best, "selection": {str(t): b5_sel[t] for t in TAU_GRID}, "report": run_summary(b5)}}
    t4["pass"] = bool(t4["b1_survival"] < 0.5)
    log(f"T4 B2r k={k_r:g}: survival {t4['b2r']['report']['survival']:.0%}, fitness {t4['b2r']['report']['mean_fitness']:.3f}; "
        f"B5 tau={tau_best:g}: survival {t4['b5']['report']['survival']:.0%}, fitness {t4['b5']['report']['mean_fitness']:.3f}; B1 survival {t4['b1_survival']:.0%}")
    d, lo, hi = _ci(b5.fitness - b2r.fitness, 1, resamples)
    t5 = {"b5_minus_b2r": d, "low": lo, "high": hi, "margin": T5_MARGIN, "pass": bool(d >= T5_MARGIN and lo > 0.0)}
    log(f"T5 B5 - B2r {d:+.3f} [{lo:+.3f}, {hi:+.3f}]")
    report_idx = [int(i) - 1 for i in report.index]  # starts are numbered from 1 and b0_best ran on starts 1..n in order
    head, hlo, hhi = _ci(b0_best.fitness[report_idx] - b5.fitness, 2, resamples)
    headroom = {"still_at_best_point": float(b0_best.fitness[report_idx].mean()), "b5": float(b5.fitness.mean()), "gap": head, "low": hlo, "high": hhi}
    log(f"B5's headroom below the still cell at the best point {head:+.3f}")
    t6: Dict[str, Any] = {}
    for mode in MODES:
        write_csv(out / f"b3_{mode}.csv", B3_COLUMNS, b3[mode])
        survival = np.array([r["survival"] for r in b3[mode]])
        fitness = np.array([r["mean_fitness"] for r in b3[mode]])
        matched = survival >= t4["b5"]["report"]["survival"]
        t6[mode] = {"n_genomes": len(b3[mode]), "share_matching_b5_survival": share(matched), "share_matching_b5_fitness": share(fitness >= t4["b5"]["report"]["mean_fitness"]),
                    "mean_survival": float(survival.mean()), "best_fitness": float(fitness.max()), "pass": bool(share(matched) < 0.05)}
        log(f"T6 {mode}: {t6[mode]['share_matching_b5_survival']:.1%} of random genomes match B5's survival; best random fitness {t6[mode]['best_fitness']:.3f}")
    t6["pass"] = all(t6[m]["pass"] for m in MODES)
    t7 = check_k6(cfg, report.take(list(range(sizes.w6_cells))), runwait(cfg, tau_best), sizes.w6_cells, seed=SEED)
    log(f"T7 {'passes' if t7['pass'] else 'FAILS'}")
    checks = {"T1": t1, "T2": t2, "T3": t3, "T4": t4, "T5": t5, "T6": t6, "T7": t7}
    verdict = {c: checks[c]["pass"] for c in checks}
    log(", ".join(f"{c} {'pass' if p else 'FAIL'}" for c, p in verdict.items()))
    summary = {"checks": checks, "verdict": verdict, "headroom": headroom, "bar": {**t4["b5"]["report"], "tau": tau_best, "controller": "b5"},
               "quick": quick}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=_json_default) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0, cells=cells, workers=workers)
    write_manifest(out / "manifest.json", manifest)
    log(f"done: {cells} cells, written to {out}")
    return summary


def _ci(diff: np.ndarray, key: int, resamples: int) -> Tuple[float, float, float]:
    """The mean and its 95% percentile bootstrap interval over starts, from stream ``bootstrap`` at stage 3's seed 9."""
    rng = stream(BOOTSTRAP_SEED, "bootstrap", (key,))
    idx = rng.integers(0, diff.shape[0], size=(resamples, diff.shape[0]))
    means = diff[idx].mean(axis=1)
    return float(diff.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    args = parser.parse_args(argv)
    return run(args.out, args.workers, args.quick)


if __name__ == "__main__":
    main(sys.argv[1:])
