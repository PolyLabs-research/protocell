"""Stage 0's checks W1–W6 (docs/prereg/stage0.md §6–§7), for both light kinds; nothing is evolved.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage0 --workers 16
    .venv/bin/python -m experiments.stage0 --quick --out /tmp/stage0-smoke      # the smoke test's sizes, not a result

Per light kind: starts 1–100 from stream ``starts`` (seed 0, §8); W2 and W3 from the starts' geometry; B0 on every
start and at each layout's brightest point (W1); B1 on every start (W4's clause); B2's gain chosen on starts 1–50 and
reported on 51–100 (W4, the bar); 1,000 random genomes per spoke mode on starts 51–70 (W5, §11 C7). W6 runs the
determinism checks on short batches. The tables, ``summary.json`` and ``manifest.json`` go to ``docs/data/stage0/``
(``--out`` elsewhere). The B3 jobs run in a process pool; everything else is small and runs in this process.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from protocell.cell import MODES, STREAM_GENOMES, genome_length, random_genomes
from protocell.config import STAGE0, Config
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.rng import stream
from protocell.sim import NOISE_CHUNK, STREAM_BEATS, STREAM_MOTION, STREAM_SENSORS, RunResult, simulate
from protocell.world import Starts, brightest_point, node_light, sample_starts, soak_distance, soak_radius, source_distance

SEED = 0  # stage 0's seed (§8): its starts and genomes are never used to evaluate an evolved cell
STAGE0_KINDS = ("spot", "lamp")  # stage 0's two worlds (the cave, docs/prereg/cave.md, has its own runner)
K_GRID: Tuple[float, ...] = (1.0, 3.0, 10.0, 30.0, 100.0)
DEFAULT_OUT = Path("docs/data/stage0")


@dataclass(frozen=True)
class Sizes:
    """How much runs: the preregistered sizes, or the smoke test's."""

    n_starts: int = 100
    select: Tuple[int, int] = (1, 50)  # B2's gain is chosen on these starts (inclusive)
    report: Tuple[int, int] = (51, 100)  # and reported on these
    genome_starts: Tuple[int, int] = (51, 70)  # each random genome runs on these (§11 C7)
    n_genomes: int = 1000
    genomes_per_job: int = 50
    w6_cells: int = 5

    @staticmethod
    def quick() -> "Sizes":
        return Sizes(n_starts=10, select=(1, 5), report=(6, 10), genome_starts=(6, 7), n_genomes=6, genomes_per_job=4, w6_cells=3)


def numbers(span: Tuple[int, int]) -> List[int]:
    return list(range(span[0], span[1] + 1))


def write_csv(path: Path, columns: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(columns), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _fmt(row.get(k)) for k in columns})


def _fmt(value: Any) -> Any:
    if isinstance(value, (bool, np.bool_)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return format(float(value), ".12g")
    if isinstance(value, np.integer):
        return int(value)
    return value


RUN_COLUMNS = ("start", "cell", "start_distance", "survived", "fitness", "light_soaked", "mean_beat", "effort_per_light",
               "reach_tick", "death_tick", "final_energy")


def share(mask: np.ndarray) -> float:
    return float(np.mean(mask)) if mask.size else math.nan


def reach_summary(result: RunResult) -> Dict[str, Any]:
    reached = result.reach_tick > 0
    return {"reached_share": share(reached),
            "median_reach_tick": float(np.median(result.reach_tick[reached])) if reached.any() else None}


def run_summary(result: RunResult) -> Dict[str, Any]:
    return {"n": len(result), "survival": share(result.survived), "mean_fitness": float(result.fitness.mean()),
            "mean_light_soaked": float(result.light_soaked.mean()), "mean_beat": float(result.mean_beat.mean()),
            "effort_per_light": float(result.mean_beat.sum() / result.light_soaked.sum()) if result.light_soaked.sum() > 0 else None,
            **reach_summary(result)}


# --- the geometric checks -------------------------------------------------------------------------------------------

def starts_table(cfg: Config, starts: Starts) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    """Per start: its geometry, W2's spread of the noiseless light over the wall, W3's straight distance to the soak
    region and the ticks it takes at v_max."""
    light = node_light(cfg, starts.kind, starts.source, starts.pos, starts.heading)
    spread = light.max(axis=1) - light.min(axis=1)
    threshold = 3.0 * cfg.sensor_noise_sd
    distance = soak_distance(cfg, starts.kind, starts.source, starts.pos)
    ticks = distance / cfg.v_max
    budget = 0.1 * cfg.lifetime
    rows = []
    for i in range(len(starts)):
        rows.append({"start": int(starts.index[i]), "source_x": starts.source[i, 0], "source_y": starts.source[i, 1],
                     "pos_x": starts.pos[i, 0], "pos_y": starts.pos[i, 1], "heading": starts.heading[i],
                     "source_distance": source_distance(starts.source, starts.pos)[i], "wall_light_mean": light[i].mean(), "wall_light_spread": spread[i], "spread_ge_3sd": spread[i] >= threshold,
                     "soak_distance": distance[i], "soak_ticks": ticks[i], "within_budget": ticks[i] <= budget})
    w2 = {"threshold": threshold, "share_spread_ge_3sd": share(spread >= threshold), "median_spread": float(np.median(spread)),
          "min_spread": float(spread.min()), "pass": bool(share(spread >= threshold) >= 0.5)}
    w3 = {"soak_radius": soak_radius(cfg, starts.kind), "budget_ticks": budget, "max_soak_ticks": float(ticks.max()),
          "median_soak_ticks": float(np.median(ticks)), "share_within_budget": share(ticks <= budget), "pass": bool((ticks <= budget).all())}
    return rows, w2, w3


STARTS_COLUMNS = ("start", "source_x", "source_y", "pos_x", "pos_y", "heading", "source_distance", "wall_light_mean",
                  "wall_light_spread", "spread_ge_3sd", "soak_distance", "soak_ticks", "within_budget")


# --- the baselines --------------------------------------------------------------------------------------------------

def run_b0(cfg: Config, starts: Starts) -> Tuple[RunResult, RunResult, Dict[str, Any]]:
    """W1: B0 on every start, and B0 at each layout's brightest point."""
    on_starts = simulate(cfg, starts, {"controller": "still"}, seed=SEED)
    brightest = simulate(cfg, starts.with_pos(brightest_point(cfg, starts.kind, starts.source)), {"controller": "still"}, seed=SEED)
    rose = brightest.survived & (brightest.final_energy > cfg.energy_start)
    dead_share = share(~on_starts.survived)
    w1 = {"b0": run_summary(on_starts), "b0_dead_share": dead_share,
          "b0_median_death_tick": float(np.median(on_starts.death_tick[on_starts.death_tick > 0])) if (~on_starts.survived).any() else None,
          "b0_brightest": run_summary(brightest), "b0_brightest_energy_rose_share": share(rose),
          "pass": bool(dead_share >= 0.9 and rose.all())}
    return on_starts, brightest, w1


def select_reflex(cfg: Config, starts: Starts, select: Sequence[int], report: Sequence[int]) -> Tuple[Dict[str, Any], List[Dict[str, Any]], RunResult]:
    """B2's gain k: the best mean fitness on the selection starts (ties: survival, then the smaller k, §11 C6); its
    score on the report starts is the bar."""
    rows: List[Dict[str, Any]] = []
    by_k: Dict[float, Dict[str, Any]] = {}
    chosen = starts.numbered(select)
    for k in K_GRID:
        r = simulate(cfg, chosen, {"controller": "reflex", "k": k}, seed=SEED)
        rows.extend(r.rows(chosen, k=k))
        by_k[k] = run_summary(r)
    best = max(K_GRID, key=lambda k: (by_k[k]["mean_fitness"], by_k[k]["survival"], -k))
    reported = simulate(cfg, starts.numbered(report), {"controller": "reflex", "k": best}, seed=SEED)
    bar = {"k": best, "selection": {str(k): by_k[k] for k in K_GRID}, "report": run_summary(reported)}
    return bar, rows, reported


def b3_job(job: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Some genomes, each on the genome starts, as one batch; a row per genome."""
    cfg: Config = job["cfg"]
    starts: Starts = job["starts"]
    genomes = np.asarray(job["genomes"])
    ids = np.asarray(job["numbers"])
    n_g, n_s = genomes.shape[0], len(starts)
    batch = starts.take(list(range(n_s)) * n_g)
    r = simulate(cfg, batch, {"controller": "network", "mode": job["mode"], "genomes": np.repeat(genomes, n_s, axis=0)},
                 seed=job["seed"], cell_ids=np.repeat(ids, n_s))
    rows = []
    for gi in range(n_g):
        sl = slice(gi * n_s, (gi + 1) * n_s)
        light_sum = float(r.light_soaked[sl].sum())
        rows.append({"genome": int(ids[gi]), "mode": job["mode"], "n_starts": n_s, "survival": share(r.survived[sl]),
                     "mean_fitness": float(r.fitness[sl].mean()), "mean_light_soaked": float(r.light_soaked[sl].mean()),
                     "mean_beat": float(r.mean_beat[sl].mean()),
                     "effort_per_light": float(r.mean_beat[sl].sum() / light_sum) if light_sum > 0 else math.nan,
                     "reached_share": share(r.reach_tick[sl] > 0), "median_death_tick": float(np.median(r.death_tick[sl])) })
    return rows


B3_COLUMNS = ("genome", "mode", "n_starts", "survival", "mean_fitness", "mean_light_soaked", "mean_beat", "effort_per_light",
              "reached_share", "median_death_tick")


def run_b3(cfg: Config, mode: str, starts: Starts, sizes: Sizes, pool: ProcessPoolExecutor) -> List[Dict[str, Any]]:
    """1,000 random genomes (§6 B3) from stream ``genomes``, genome g the g-th drawn, each on the genome starts."""
    genomes = random_genomes(cfg, mode, sizes.n_genomes, stream(SEED, STREAM_GENOMES))
    chosen = starts.numbered(numbers(sizes.genome_starts))
    jobs = []
    for lo in range(0, sizes.n_genomes, sizes.genomes_per_job):
        hi = min(lo + sizes.genomes_per_job, sizes.n_genomes)
        jobs.append({"cfg": cfg, "starts": chosen, "genomes": genomes[lo:hi], "numbers": np.arange(lo + 1, hi + 1), "mode": mode, "seed": SEED})
    rows: List[Dict[str, Any]] = []
    for part in pool.map(b3_job, jobs):
        rows.extend(part)
    return rows


def w5_summary(rows: Sequence[Mapping[str, Any]], bar: Mapping[str, Any]) -> Dict[str, Any]:
    survival = np.array([r["survival"] for r in rows])
    fitness = np.array([r["mean_fitness"] for r in rows])
    matched = survival >= bar["report"]["survival"]
    return {"n_genomes": len(rows), "share_matching_b2_survival": share(matched), "share_matching_b2_fitness": share(fitness >= bar["report"]["mean_fitness"]),
            "mean_survival": float(survival.mean()), "share_any_survival": share(survival > 0), "mean_fitness": float(fitness.mean()),
            "share_any_reach": share(np.array([r["reached_share"] for r in rows]) > 0), "pass": bool(share(matched) < 0.05)}


# --- W6 ---------------------------------------------------------------------------------------------------------------

def check_w6(cfg: Config, starts_by_kind: Mapping[str, Starts], bar_k: Mapping[str, float], sizes: Sizes) -> Dict[str, Any]:
    """Same seed, same hash (B2 and a network cell, each run twice); a batch equals its singles (network cells, each
    with its own genome and start); the streams are independent (switching one off leaves the others' draws, by their
    digests, as they were; B0 ignores the sensors, so its trajectory is the same with them on or off)."""
    out: Dict[str, Any] = {}
    mode = "fourier1"
    genomes = random_genomes(cfg, mode, sizes.w6_cells, stream(SEED, STREAM_GENOMES))
    ids = list(range(1, sizes.w6_cells + 1))
    for kind, starts in starts_by_kind.items():
        few = starts.numbered(numbers(sizes.report)[:sizes.w6_cells])
        reflex = {"controller": "reflex", "k": bar_k[kind]}
        net = {"controller": "network", "mode": mode, "genomes": genomes}
        same_reflex = simulate(cfg, few, reflex, seed=SEED, record=True).run_hash() == simulate(cfg, few, reflex, seed=SEED, record=True).run_hash()
        batch = simulate(cfg, few, net, seed=SEED, cell_ids=ids, record=True)
        same_net = batch.run_hash() == simulate(cfg, few, net, seed=SEED, cell_ids=ids, record=True).run_hash()
        singles_equal = True
        for i in range(sizes.w6_cells):
            single = simulate(cfg, few.take([i]), {**net, "genomes": genomes[i:i + 1]}, seed=SEED, cell_ids=ids[i:i + 1], record=True)
            assert single.trajectory is not None and batch.trajectory is not None
            singles_equal &= single.cell_hash(0) == batch.cell_hash(i)
            singles_equal &= all(np.array_equal(single.trajectory[n][0], batch.trajectory[n][i]) for n in ("pos", "heading", "energy", "beat"))
            singles_equal &= bool(single.survived[0] == batch.survived[i] and single.fitness[0] == batch.fitness[i])
        both = batch.noise_digests
        no_sensors = simulate(cfg.but(sensor_noise_sd=0.0), few, net, seed=SEED, cell_ids=ids)
        no_motion = simulate(cfg.but(rotation_noise_sd=0.0), few, net, seed=SEED, cell_ids=ids)
        random_both = simulate(cfg, few, {"controller": "random"}, seed=SEED)
        random_no_motion = simulate(cfg.but(rotation_noise_sd=0.0), few, {"controller": "random"}, seed=SEED)
        still_on = simulate(cfg, few, {"controller": "still"}, seed=SEED, record=True)
        still_off = simulate(cfg.but(sensor_noise_sd=0.0), few, {"controller": "still"}, seed=SEED, record=True)
        independent = (no_sensors.noise_digests[STREAM_MOTION] == both[STREAM_MOTION]
                       and no_motion.noise_digests[STREAM_SENSORS] == both[STREAM_SENSORS]
                       and random_no_motion.noise_digests[STREAM_BEATS] == random_both.noise_digests[STREAM_BEATS]
                       and random_no_motion.noise_digests[STREAM_SENSORS] == random_both.noise_digests[STREAM_SENSORS]
                       and still_on.run_hash() == still_off.run_hash()
                       and no_sensors.noise_digests.get(STREAM_SENSORS) is None)
        out[kind] = {"same_seed_same_hash_reflex": bool(same_reflex), "same_seed_same_hash_network": bool(same_net),
                     "batch_equals_singles": bool(singles_equal), "streams_independent": bool(independent),
                     "network_run_hash": batch.run_hash(), "cells": sizes.w6_cells}
    out["pass"] = all(all(v for k, v in d.items() if isinstance(v, bool)) for d in out.values() if isinstance(d, dict))
    return out


# --- the run ----------------------------------------------------------------------------------------------------------

def run_kind(cfg: Config, kind: str, sizes: Sizes, out: Path, pool: ProcessPoolExecutor, log) -> Tuple[Dict[str, Any], Starts, int]:
    starts = sample_starts(cfg, kind, sizes.n_starts, SEED)
    cells = 0
    rows, w2, w3 = starts_table(cfg, starts)
    write_csv(out / f"starts_{kind}.csv", STARTS_COLUMNS, rows)
    log(f"[{kind}] W2 spread >= 3 sd on {w2['share_spread_ge_3sd']:.0%} of starts; W3 farthest {w3['max_soak_ticks']:.0f} ticks")

    b0, b0_bright, w1 = run_b0(cfg, starts)
    cells += 2 * len(starts)
    write_csv(out / f"b0_{kind}.csv", RUN_COLUMNS, b0.rows(starts))
    write_csv(out / f"b0_brightest_{kind}.csv", RUN_COLUMNS, b0_bright.rows(starts))
    log(f"[{kind}] W1 B0 dead on {w1['b0_dead_share']:.0%}; at the brightest point E rose on {w1['b0_brightest_energy_rose_share']:.0%}")

    b1 = simulate(cfg, starts, {"controller": "random"}, seed=SEED)
    cells += len(starts)
    write_csv(out / f"b1_{kind}.csv", RUN_COLUMNS, b1.rows(starts))

    bar, select_rows, reported = select_reflex(cfg, starts, numbers(sizes.select), numbers(sizes.report))
    cells += len(K_GRID) * len(numbers(sizes.select)) + len(reported)
    write_csv(out / f"b2_select_{kind}.csv", ("k", *RUN_COLUMNS), select_rows)
    write_csv(out / f"b2_report_{kind}.csv", RUN_COLUMNS, reported.rows(starts.numbered(numbers(sizes.report))))
    w4 = {"b1": run_summary(b1), "b1_survival": share(b1.survived), "bar": bar, "pass": bool(share(b1.survived) < 0.5)}
    log(f"[{kind}] W4 B2 k={bar['k']:g}: survival {bar['report']['survival']:.0%}, fitness {bar['report']['mean_fitness']:.3f}; B1 survival {w4['b1_survival']:.0%}")

    w5: Dict[str, Any] = {}
    for mode in MODES:
        rows = run_b3(cfg, mode, starts, sizes, pool)
        cells += sizes.n_genomes * len(numbers(sizes.genome_starts))
        write_csv(out / f"b3_{kind}_{mode}.csv", B3_COLUMNS, rows)
        w5[mode] = w5_summary(rows, bar)
        log(f"[{kind}] W5 {mode}: {w5[mode]['share_matching_b2_survival']:.1%} of genomes match B2's survival; mean survival {w5[mode]['mean_survival']:.1%}")
    w5["pass"] = all(w5[m]["pass"] for m in MODES)
    return {"W1": w1, "W2": w2, "W3": w3, "W4": w4, "W5": w5}, starts, cells


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a short lifetime: not a result")
    args = parser.parse_args(argv)
    cfg = STAGE0.but(lifetime=60) if args.quick else STAGE0
    sizes = Sizes.quick() if args.quick else Sizes()
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    settings = {**cfg.as_dict(), "seed": SEED, "sizes": sizes.__dict__, "k_grid": K_GRID, "modes": MODES, "kinds": STAGE0_KINDS,
                "noise_chunk": NOISE_CHUNK, "genome_length": {m: genome_length(cfg, m) for m in MODES}, "quick": args.quick}
    manifest = build_manifest(protocol="stage0", settings=settings, seeds=[SEED], extra={"out": str(out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:7.1f}s {msg}", flush=True)

    checks: Dict[str, Any] = {}
    starts_by_kind: Dict[str, Starts] = {}
    cells = 0
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as pool:
        for kind in STAGE0_KINDS:
            checks[kind], starts_by_kind[kind], n = run_kind(cfg, kind, sizes, out, pool, log)
            cells += n
    w6 = check_w6(cfg, starts_by_kind, {k: checks[k]["W4"]["bar"]["k"] for k in STAGE0_KINDS}, sizes)
    log(f"W6 {'passes' if w6['pass'] else 'FAILS'}")
    for kind in STAGE0_KINDS:
        passed = {c: checks[kind][c]["pass"] for c in ("W1", "W2", "W3", "W4", "W5")}
        log(f"[{kind}] " + ", ".join(f"{c} {'pass' if p else 'FAIL'}" for c, p in passed.items()))
    summary = {"checks": checks, "W6": w6, "bar": {k: checks[k]["W4"]["bar"]["report"] | {"k": checks[k]["W4"]["bar"]["k"]} for k in STAGE0_KINDS},
               "quick": args.quick}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=_json_default) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0, cells=cells, cell_ticks=cells * cfg.lifetime, workers=args.workers)
    write_manifest(out / "manifest.json", manifest)
    log(f"done: {cells} cells, written to {out}")
    return summary


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    return str(value)


if __name__ == "__main__":
    main(sys.argv[1:])
