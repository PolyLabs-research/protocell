"""The compiled life against the reference (docs/prereg/fast.md): is it the same model, do the two agree in outcome,
and what does it cost.

    .venv/bin/python -m experiments.fastcheck --part same      # A: the same bits, under the C library's maths
    .venv/bin/python -W error::RuntimeWarning -m experiments.fastcheck --part agree   # B: outcomes on fresh starts
    .venv/bin/python -m experiments.fastcheck --part speed --workers 8                # C: the cost (describes; any machine)
    .venv/bin/python -m experiments.fastcheck --part gpu       # on a machine with an Nvidia GPU: the GPU's kernel beside the CPU's
    .venv/bin/python -m experiments.fastcheck --part same --quick --out /tmp/fc       # the smoke test: not a result

A (``same``): whole lives in the six worlds a stage 8 run meets, with numpy's exp, log, sin and cos replaced by the C
library's (the functions the compiled life calls) and the kernel in its strict form. Every number of every life must
be the reference's, bit for bit.

B (``agree``): the kernel as the searches use it, beside the reference as it is. Three cells on 100 fresh starts in
each of the six worlds, and a whole population on two generations' worth of training starts, as a search scores it.
Single lives part (a life is chaotic and the library functions differ in a last bit); the distributions and the
ranking must not. The criteria are §4 of the plan.

C (``speed``) and ``gpu`` describe; they set no criterion here. ``gpu`` is for a machine that has one.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from experiments import stage4b, stage8
from experiments.stage1 import bootstrap_ci
from protocell import evolve, fast
from protocell.config import Config
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.sim import simulate
from protocell.tables import write_csv
from protocell.world import Starts, sample_starts

MODE = stage8.MODE
SEED, BOOTSTRAP_SEED = 50, 51  # fresh: the starts of A and B, and B's intervals
LUCK_SEEDS = (52, 53)  # two generations' worth of training starts for the ranking
N_STARTS = 100
RESAMPLES = 10_000
CELLS = {"champion8102": Path("docs/data/stage8/pilot/fourier1-8102/champion.npy"),
         "champion6402": Path("docs/data/stage6b/confirm/fourier1-6402/champion.npy"),
         "champion8105": Path("docs/data/stage8/confirm/fourier1-8105/champion.npy")}
POPULATION = Path("docs/data/stage8/pilot/fourier1-8102/population.npy")  # the generalist's run at its end: from working cells to broken ones
PATH_GENERATIONS = (25, 75)  # a generation on each half of stage 4b's path
TOLERANCE, SURVIVAL_TOLERANCE, POOLED_TOLERANCE, MISSES_ALLOWED, RANK_NEED = 0.01, 0.05, 0.003, 2, 0.9  # §4
DEFAULT_OUT = Path("docs/data/fast")
SAME = ("fitness", "light_soaked", "mean_beat", "survived", "death_tick", "death_cause", "final_energy", "final_damage", "pos", "heading")


def worlds(quick: bool) -> Dict[str, Config]:
    """What a stage 8 run meets: its four worlds, and a generation from each half of the eased-in path before them."""
    home = stage8.world("home", quick)
    fade, tighten = stage4b.path_generations(False)
    out = {name: stage8.world(name, quick) for name in stage8.TRAINED}
    out.update({f"path {g}": stage4b.training_world(home, g, fade, tighten) for g in PATH_GENERATIONS})
    return out


def cells(quick: bool) -> Dict[str, np.ndarray]:
    return {name: np.load(path).reshape(-1) for name, path in (list(CELLS.items())[:2] if quick else CELLS.items())}


def population(quick: bool) -> np.ndarray:
    return np.load(POPULATION)[:8 if quick else None]


@contextmanager
def c_library_maths() -> Iterator[None]:
    """numpy's exp, log, sin and cos replaced by the C library's, element by element, for the block: under it the
    reference and the compiled life share every operation. The kernel is compiled first (Numba reads numpy's functions
    while it compiles)."""
    cfg = stage8.world("home", True)
    fast.simulate_network(cfg, sample_starts(cfg, "cave", 1, 1), MODE, population(True)[:1], seed=1, ticks=2, strict=True)

    def each(f: Any) -> Any:
        def g(x: Any, *args: Any, **kwargs: Any) -> np.ndarray:
            x = np.asarray(x, dtype=np.float64)
            return np.array([f(float(v)) for v in x.ravel()], dtype=np.float64).reshape(x.shape)
        return g

    kept = {name: getattr(np, name) for name in ("exp", "log", "sin", "cos")}
    try:
        for name in kept:
            setattr(np, name, each(getattr(math, name)))
        yield
    finally:
        for name, f in kept.items():
            setattr(np, name, f)


def reference(cfg: Config, starts: Starts, genomes: np.ndarray, seed: int, ticks: Optional[int] = None) -> Any:
    return simulate(cfg, starts, {"controller": "network", "mode": MODE, "genomes": genomes}, seed=seed,
                    cell_ids=[evolve.NOISE_CELL_ID] * len(starts), ticks=ticks)


# --- A: the same model -----------------------------------------------------------------------------------------------------

def same(out: Path, quick: bool, log: Any) -> Dict[str, Any]:
    """Two cells (the generalist, and a cell from the end of its run's population that does not cope) on two starts in
    each world, whole lives, both engines under the C library's maths."""
    two = np.stack([cells(quick)["champion8102"], population(quick)[-1]])
    rows = []
    with c_library_maths():
        for name, cfg in worlds(quick).items():
            pool = sample_starts(cfg, "cave", 8 if quick else 40, SEED)
            by_day = [i for i in range(len(pool)) if pool.phase[i] < cfg.day_ticks // 2][:1]
            by_night = [i for i in range(len(pool)) if pool.phase[i] >= cfg.day_ticks // 2][:1]
            starts = pool.take((by_day + by_night) * 2)
            genomes = np.repeat(two, 2, axis=0)
            t0 = time.time()
            ref = reference(cfg, starts, genomes, SEED)
            got = fast.simulate_network(cfg, starts, MODE, genomes, seed=SEED, strict=True)
            for i in range(len(starts)):
                differs = [k for k in SAME if not np.array_equal(getattr(got, k)[i], getattr(ref, k)[i])]
                rows.append({"world": name, "cell": ("champion8102", "population's last")[i // 2], "start": int(starts.index[i]),
                             "lifetime": int(ref.lifetime[i]), "fitness": float(ref.fitness[i]), "death_tick": int(ref.death_tick[i]),
                             "death_cause": int(ref.death_cause[i]), "identical": not differs, "differs": " ".join(differs)})
            log(f"{name}: {sum(r['identical'] for r in rows[-len(starts):])} of {len(starts)} lives identical in every number "
                f"(lifetimes {ref.lifetime.tolist()}, deaths at {ref.death_tick.tolist()}) [{time.time() - t0:.0f} s]")
    write_csv(out / "lives.csv", ("world", "cell", "start", "lifetime", "fitness", "death_tick", "death_cause", "identical", "differs"), rows)
    summary = {"lives": len(rows), "identical": sum(r["identical"] for r in rows), "A": all(r["identical"] for r in rows),
               "died": sum(r["death_tick"] > 0 for r in rows), "quick": quick}
    log(f"A (the same model): {summary['identical']} of {summary['lives']} whole lives identical, {summary['died']} of them deaths: "
        f"{'holds' if summary['A'] else 'FAILS'}")
    return summary


# --- B: the same outcomes --------------------------------------------------------------------------------------------------

def spearman(a: np.ndarray, b: np.ndarray) -> float:
    ra, rb = np.argsort(np.argsort(a, kind="stable"), kind="stable").astype(float), np.argsort(np.argsort(b, kind="stable"), kind="stable").astype(float)
    return float(np.corrcoef(ra, rb)[0, 1])


def step(genomes: np.ndarray, fitness: np.ndarray) -> np.ndarray:
    """Where a ranking would move the search's mean: CMA-ES's weighted mean of the better half, less the population's
    mean (in each gene's own units, which a cosine does not mind)."""
    lam = len(fitness)
    mu = lam // 2
    w = math.log((lam + 1) / 2.0) - np.log(np.arange(1, mu + 1))
    order = np.argsort(-fitness, kind="stable")[:mu]
    return (w / w.sum()) @ genomes[order] - genomes.mean(axis=0)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))


def agree(out: Path, quick: bool, log: Any) -> Dict[str, Any]:
    n = 6 if quick else N_STARTS
    resamples = 200 if quick else RESAMPLES
    mine = cells(quick)
    names = list(mine)
    pair_rows, life_rows = [], []
    pooled: List[np.ndarray] = []
    for w, (world, cfg) in enumerate(worlds(quick).items()):
        starts = sample_starts(cfg, "cave", n, SEED)
        every = starts.take(list(range(n)) * len(names))
        genomes = np.concatenate([np.repeat(mine[c][None], n, axis=0) for c in names])
        t0 = time.time()
        ref = reference(cfg, every, genomes, SEED)
        t1 = time.time()
        got = fast.simulate_network(cfg, every, MODE, genomes, seed=SEED)
        t2 = time.time()
        for c, cell in enumerate(names):
            rows = slice(c * n, (c + 1) * n)
            rf, ff = np.asarray(ref.fitness[rows], dtype=float), got.fitness[rows]
            d = ff - rf
            mean, low, high = bootstrap_ci(d, 1000 * (w + 1) + c, resamples, seed=BOOTSTRAP_SEED)
            pooled.append(d)
            pair_rows.append({"world": world, "cell": cell, "starts": n, "reference_fitness": float(rf.mean()), "compiled_fitness": float(ff.mean()),
                              "difference": mean, "low": low, "high": high, "reference_survival": float(ref.survived[rows].mean()),
                              "compiled_survival": float(got.survived[rows].mean()), "within_0.001": float((np.abs(d) < 0.001).mean()),
                              "within_0.01": float((np.abs(d) < 0.01).mean()), "largest": float(np.abs(d).max()),
                              "survival_flips": int((ref.survived[rows] != got.survived[rows]).sum())})
            life_rows += [{"world": world, "cell": cell, "start": int(starts.index[i]), "reference_fitness": float(rf[i]), "compiled_fitness": float(ff[i]),
                           "reference_survived": bool(ref.survived[rows][i]), "compiled_survived": bool(got.survived[rows][i]),
                           "reference_death_tick": int(ref.death_tick[rows][i]), "compiled_death_tick": int(got.death_tick[rows][i])} for i in range(n)]
            p = pair_rows[-1]
            log(f"{world}, {cell}: reference {p['reference_fitness']:.4f} ({p['reference_survival']:.0%}), compiled {p['compiled_fitness']:.4f} "
                f"({p['compiled_survival']:.0%}), difference {mean:+.4f} [{low:+.4f}, {high:+.4f}]; within 0.001 in {p['within_0.001']:.0%} of lives, "
                f"0.01 in {p['within_0.01']:.0%}; largest {p['largest']:.3f}")
        log(f"  [{world}: the reference {t1 - t0:.0f} s, the compiled life {t2 - t1:.1f} s, for {len(every)} lives]")
    write_csv(out / "pairs.csv", tuple(pair_rows[0]), pair_rows)
    write_csv(out / "lives.csv", tuple(life_rows[0]), life_rows)
    every_d = np.concatenate(pooled)
    pooled_mean, pooled_low, pooled_high = bootstrap_ci(every_d, 99, resamples, seed=BOOTSTRAP_SEED)

    # the ranking a search sees: a population on a generation's training starts, twice over (two draws of luck)
    pop = population(quick)
    mix = [stage8.world(wname, quick) for wname in stage8.TRAINED]
    ga = stage8.cma_for(quick).as_ga().but(population=len(pop), chunk=len(pop))
    scores: Dict[Tuple[str, int], np.ndarray] = {}
    seconds: Dict[Tuple[str, int], float] = {}
    for seed in LUCK_SEEDS:
        for engine, mapper in (("reference", map), ("compiled", fast.Mapper())):
            t0 = time.time()
            scores[(engine, seed)] = evolve.evaluate(mix, MODE, ga, pop, seed, 0, mapper)["fitness"]
            seconds[(engine, seed)] = time.time() - t0
        log(f"a generation's ranking under luck {seed}: the reference {seconds[('reference', seed)]:.0f} s, the compiled life "
            f"{seconds[('compiled', seed)]:.1f} s (one process each)")
    a, b = LUCK_SEEDS
    rank_rows = []
    for seed in LUCK_SEEDS:
        r, f = scores[("reference", seed)].mean(axis=1), scores[("compiled", seed)].mean(axis=1)
        rank_rows.append({"what": f"the two engines, luck {seed}", "spearman": spearman(r, f), "step_cosine": cosine(step(pop, r), step(pop, f)),
                          "top_half_shared": len(set(np.argsort(-r)[:len(r) // 2]) & set(np.argsort(-f)[:len(f) // 2])) / (len(r) // 2)})
    for engine in ("reference", "compiled"):
        x, y = scores[(engine, a)].mean(axis=1), scores[(engine, b)].mean(axis=1)
        rank_rows.append({"what": f"the {engine} under two draws of luck", "spearman": spearman(x, y), "step_cosine": cosine(step(pop, x), step(pop, y)),
                          "top_half_shared": len(set(np.argsort(-x)[:len(x) // 2]) & set(np.argsort(-y)[:len(y) // 2])) / (len(x) // 2)})
    write_csv(out / "ranking.csv", ("what", "spearman", "step_cosine", "top_half_shared"), rank_rows)
    np.savez(out / "ranking_scores.npz", **{f"{engine}_{seed}": v for (engine, seed), v in scores.items()})
    for r in rank_rows:
        log(f"ranking, {r['what']}: Spearman {r['spearman']:.3f}, the search's step agrees {r['step_cosine']:.3f}, top half shared {r['top_half_shared']:.0%}")

    engines = min(r["spearman"] for r in rank_rows[:2])
    luck = rank_rows[2]["spearman"]
    b1 = all(abs(p["difference"]) < TOLERANCE and abs(p["compiled_survival"] - p["reference_survival"]) <= SURVIVAL_TOLERANCE for p in pair_rows)
    misses = [f"{p['world']}, {p['cell']}" for p in pair_rows if not p["low"] <= 0.0 <= p["high"]]
    b2 = len(misses) <= MISSES_ALLOWED
    b3 = abs(pooled_mean) < POOLED_TOLERANCE
    b4 = engines >= RANK_NEED and engines > luck
    within = float((np.abs(every_d) < 0.001).mean())
    predictions = [
        (1, "B1 to B4 all hold", b1 and b2 and b3 and b4, {"B1": b1, "B2": b2, "B3": b3, "B4": b4}),
        (2, "single lives part: fewer than 90% of the paired lives agree to within 0.001 in fitness", within < 0.9, {"within_0.001": within}),
        (3, "and most do not part far: at least 80% agree to within 0.01", float((np.abs(every_d) < 0.01).mean()) >= 0.8,
         {"within_0.01": float((np.abs(every_d) < 0.01).mean())}),
        (4, "the two engines rank a population more alike (Spearman above 0.95) than one engine does under two draws of luck (below 0.9)",
         engines > 0.95 and luck < 0.9, {"engines": engines, "luck": luck}),
    ]
    summary = {"pairs": len(pair_rows), "lives": int(every_d.shape[0]), "pooled_difference": {"mean": pooled_mean, "low": pooled_low, "high": pooled_high},
               "largest_pair_difference": max(abs(p["difference"]) for p in pair_rows), "intervals_missing_zero": misses,
               "survival_flips": int(sum(p["survival_flips"] for p in pair_rows)), "within_0.001": within,
               "within_0.01": float((np.abs(every_d) < 0.01).mean()), "ranking": rank_rows, "ranking_seconds": {f"{e} {s}": v for (e, s), v in seconds.items()},
               "B1": b1, "B2": b2, "B3": b3, "B4": b4, "B": b1 and b2 and b3 and b4,
               "predictions": [{"number": k, "text": t, "holds": bool(h), "values": v} for k, t, h, v in predictions], "quick": quick}
    log(f"B1 (every pair's means within {TOLERANCE}, survival within {SURVIVAL_TOLERANCE:.0%}): {'holds' if b1 else 'FAILS'} "
        f"(largest {summary['largest_pair_difference']:.4f})")
    log(f"B2 (the interval holds 0 in all but {MISSES_ALLOWED} pairs at most): {'holds' if b2 else 'FAILS'} (misses: {misses or 'none'})")
    log(f"B3 (over all {summary['lives']} lives the mean difference within {POOLED_TOLERANCE}): {'holds' if b3 else 'FAILS'} "
        f"({pooled_mean:+.5f} [{pooled_low:+.5f}, {pooled_high:+.5f}])")
    log(f"B4 (the engines rank a population alike, Spearman at least {RANK_NEED} and above one engine's under two draws of luck): "
        f"{'holds' if b4 else 'FAILS'} ({engines:.3f} against {luck:.3f})")
    for q in summary["predictions"]:
        log(f"prediction {q['number']}: {'holds' if q['holds'] else 'FAILS'}: {q['text']}")
    return summary


# --- C: the cost -----------------------------------------------------------------------------------------------------------

def speed(out: Path, quick: bool, log: Any, workers: int, device: str) -> Dict[str, Any]:
    """One core: the reference and the compiled life on the same 48 cells of a population on one start. Then a whole
    generation as a search runs it (96 genomes on 8 starts, four worlds) with ``workers`` processes, or on the GPU."""
    pop = population(quick)
    cfg = stage8.world("home", quick)
    start = sample_starts(cfg, "cave", 1, SEED)
    batch = min(48, len(pop))
    ticks = 400 if quick else 4000
    genomes = pop[:batch]
    row = start.take([0] * batch)
    fast.simulate_network(cfg, row, MODE, genomes, seed=SEED, ticks=2)  # compiled before the clock starts
    t0 = time.perf_counter()
    reference(cfg, row, genomes, SEED, ticks)
    t1 = time.perf_counter()
    got = fast.simulate_network(cfg, row, MODE, genomes, seed=SEED, ticks=ticks)
    t2 = time.perf_counter()
    lived = int(np.where(got.death_tick > 0, got.death_tick, got.lifetime).sum())
    summary: Dict[str, Any] = {"batch": batch, "ticks": ticks, "reference_us_a_cell_tick": (t1 - t0) / (batch * ticks) * 1e6,
                               "compiled_us_a_cell_tick": (t2 - t1) / lived * 1e6, "workers": workers, "device": device, "quick": quick}
    summary["one_core_ratio"] = summary["reference_us_a_cell_tick"] / summary["compiled_us_a_cell_tick"]
    log(f"one core, {batch} cells on one start: the reference {summary['reference_us_a_cell_tick']:.2f} microseconds a cell-tick, the compiled life "
        f"{summary['compiled_us_a_cell_tick']:.2f}: {summary['one_core_ratio']:.1f} times faster")
    mix = [stage8.world(wname, quick) for wname in stage8.TRAINED]
    ga = stage8.cma_for(quick).as_ga().but(population=len(pop), chunk=min(48, len(pop)))
    if device == "cuda":
        ready, what = fast.cuda_ready()
        if not ready:
            raise SystemExit(f"no GPU to time: {what}")
        mapper: Any = fast.CudaMapper()
        evolve.evaluate(mix, MODE, ga.but(population=batch, chunk=batch), pop[:batch], SEED, 1, mapper)  # compiled before the clock starts
        t0 = time.perf_counter()
        ev = evolve.evaluate(mix, MODE, ga, pop, SEED, 0, mapper)
        summary["generation_seconds"] = time.perf_counter() - t0
        summary["gpu"] = what
    else:
        with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
            list(pool.map(_warm, range(max(1, workers))))
            t0 = time.perf_counter()
            ev = evolve.evaluate(mix, MODE, ga, pop, SEED, 0, fast.Mapper(pool.map))
            summary["generation_seconds"] = time.perf_counter() - t0
    summary["generation_lives"] = int(ev["fitness"].size)
    log(f"a generation ({summary['generation_lives']} lives, four worlds) on " + (f"the GPU ({summary.get('gpu')})" if device == "cuda" else f"{workers} processes")
        + f": {summary['generation_seconds']:.1f} s; 400 generations at that rate {summary['generation_seconds'] * 400 / 3600:.1f} h")
    return summary


def _warm(_: int) -> bool:
    """Compile (or load) the kernel in a worker before it is timed."""
    cfg = stage8.world("home", True)
    fast.simulate_network(cfg, sample_starts(cfg, "cave", 1, 1), MODE, population(True)[:1], seed=1, ticks=2)
    return True


# --- the GPU's kernel beside the CPU's -------------------------------------------------------------------------------------

def gpu(out: Path, quick: bool, log: Any) -> Dict[str, Any]:
    """For a machine with an Nvidia GPU. The GPU's kernel against the CPU's: the first ticks (the same model, to
    rounding), then whole lives (the same outcomes, in distribution), then the time. It describes; whether to search
    on the GPU is the owner's call once these numbers exist."""
    ready, what = fast.cuda_ready()
    if not ready:
        raise SystemExit(f"no GPU: {what}")
    log(f"the GPU: {what}")
    mine = cells(quick)
    names = list(mine)
    n = 4 if quick else 25
    rows = []
    early = 0.0
    pooled: List[np.ndarray] = []
    for world, cfg in worlds(quick).items():
        starts = sample_starts(cfg, "cave", n, SEED)
        every = starts.take(list(range(n)) * len(names))
        genomes = np.concatenate([np.repeat(mine[c][None], n, axis=0) for c in names])
        a = fast.simulate_network(cfg, every, MODE, genomes, seed=SEED, ticks=20 if quick else 100)
        b = fast.simulate_network(cfg, every, MODE, genomes, seed=SEED, ticks=20 if quick else 100, device="cuda")
        early = max(early, float(np.abs(a.pos - b.pos).max()))
        t0 = time.perf_counter()
        cpu = fast.simulate_network(cfg, every, MODE, genomes, seed=SEED)
        t1 = time.perf_counter()
        dev = fast.simulate_network(cfg, every, MODE, genomes, seed=SEED, device="cuda")
        t2 = time.perf_counter()
        for c, cell in enumerate(names):
            sl = slice(c * n, (c + 1) * n)
            d = dev.fitness[sl] - cpu.fitness[sl]
            pooled.append(d)
            rows.append({"world": world, "cell": cell, "starts": n, "cpu_fitness": float(cpu.fitness[sl].mean()), "gpu_fitness": float(dev.fitness[sl].mean()),
                         "difference": float(d.mean()), "cpu_survival": float(cpu.survived[sl].mean()), "gpu_survival": float(dev.survived[sl].mean()),
                         "within_0.01": float((np.abs(d) < 0.01).mean())})
        log(f"{world}: " + "; ".join(f"{r['cell']} {r['cpu_fitness']:.3f} on the CPU, {r['gpu_fitness']:.3f} on the GPU" for r in rows[-len(names):])
            + f" [{len(every)} lives: CPU {t1 - t0:.1f} s on one core, GPU {t2 - t1:.1f} s]")
    write_csv(out / "pairs.csv", tuple(rows[0]), rows)
    every_d = np.concatenate(pooled)
    summary = {"gpu": what, "largest_early_position_difference": early, "pooled_difference": float(every_d.mean()),
               "largest_pair_difference": max(abs(r["difference"]) for r in rows), "lives": int(every_d.shape[0]), "quick": quick}
    log(f"over the first ticks the two kernels' positions differ by at most {early:.2e} R; over {summary['lives']} whole lives the mean fitness differs by "
        f"{summary['pooled_difference']:+.4f} (largest for one cell in one world {summary['largest_pair_difference']:.4f})")
    return summary


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--part", required=True, choices=["same", "agree", "speed", "gpu"])
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, default=1, help="speed: the processes a generation is spread over")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu", help="speed: where the generation runs")
    parser.add_argument("--tag", default="", help="speed and gpu: a name for the machine, so each machine's numbers keep their own directory")
    args = parser.parse_args(argv)
    out = args.out / (args.part if not args.tag else f"{args.part}-{args.tag}")
    out.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(protocol=f"fastcheck/{args.part}", settings={"worlds": list(worlds(args.quick)), "cells": list(cells(args.quick)),
                                                                           "starts": N_STARTS, "luck_seeds": list(LUCK_SEEDS), "population": str(POPULATION),
                                                                           "tolerances": {"pair": TOLERANCE, "survival": SURVIVAL_TOLERANCE, "pooled": POOLED_TOLERANCE,
                                                                                          "misses": MISSES_ALLOWED, "rank": RANK_NEED},
                                                                           "workers": args.workers, "device": args.device, "quick": args.quick},
                              seeds=[SEED, BOOTSTRAP_SEED, *LUCK_SEEDS], extra={"out": str(out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:7.0f}s {msg}", flush=True)

    if args.part == "same":
        summary = same(out, args.quick, log)
    elif args.part == "agree":
        summary = agree(out, args.quick, log)
    elif args.part == "speed":
        summary = speed(out, args.quick, log, args.workers, args.device)
    else:
        summary = gpu(out, args.quick, log)
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0)
    write_manifest(out / "manifest.json", manifest)
    return summary


if __name__ == "__main__":
    main(sys.argv[1:])
