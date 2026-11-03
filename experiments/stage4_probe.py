"""Stage 4's design probe (docs/decisions.md D15): which changing light leaves real room above every simple rule.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage4_probe --workers 16
    .venv/bin/python -m experiments.stage4_probe --quick --out /tmp/s4p --workers 2   # the smoke test: not a result

The candidate worlds are stage 3's translucent pool (docs/prereg/stage3.md) with one change each: none (the
reference); clouds, spells of sun and of shade at 0.3 of the light, slow (means 10 and 5 minutes) or fast (2 and 1); the
mouth sweeping along the pool's edge through the day (the cave's sweep); a spot circling the pool's centre at 2,500 R,
once a day, every 6 hours or every 2 hours. In each, on fresh starts 1-100 at seed 16, with shared noise and sky:

- the simple rules, each parameter chosen on starts 1-50 by mean fitness and reported on starts 51-100: B2r, the reflex
  (its gain k); B5, run and wait (its memory tau); B6, read and run (its cycle and run); B8, B5's trigger with B6's aim
  (tau, its aim averaged over 10 s); and B0, still, and B7, run anywhere, as they are;
- B6 with perfect reading, the direction across the body magnified 10,000 times and the sensor noise off: what B6's
  timing reaches when it knows the direction exactly;
- the ceiling, a still cell put at the brightest point every tick: it gets the most light any cell can, pays nothing to
  move, and so bounds every strategy from above;
- 100 random genomes per spoke mode on starts 51-70.

The headroom is the ceiling less the best simple rule, start by start on starts 51-100, with a 95% bootstrap interval
(seed 17). Nothing here is a test; the probe chooses which world stage 4 preregisters. Writes docs/data/stage4/probe/.
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

from experiments.stage0 import B3_COLUMNS, K_GRID, b3_job
from experiments.stage3 import TAU_GRID, configure, reflex, runwait
from protocell.cell import MODES, STREAM_GENOMES, random_genomes
from protocell.config import Config
from protocell.energy import energy_step, start_energy
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.rng import stream
from protocell.sim import simulate
from protocell.tables import write_csv
from protocell.world import Sky, Starts, clamp, lifetimes, mouth_position, node_light, sample_starts

SEED = 16  # fresh: the starts, the noise, the sky and the random genomes
BOOTSTRAP_SEED = 17
RESAMPLES = 10_000
SPOT_RADIUS = 2500.0  # half the pool's radius: the spot stays well inside the pool, 2,500 R from its edge
WORLDS: Dict[str, Dict[str, Any]] = {
    "reference": {},
    "clouds": {"cloud_shade": 0.3, "cloud_sun_mean": 600.0, "cloud_shade_mean": 300.0},
    "flicker": {"cloud_shade": 0.3, "cloud_sun_mean": 120.0, "cloud_shade_mean": 60.0},
    "sweep": {"cave_sweep": True},
    "spot_day": {"cave_path": "circle", "path_radius": SPOT_RADIUS, "path_period": 86_400},
    "spot_6h": {"cave_path": "circle", "path_radius": SPOT_RADIUS, "path_period": 21_600},
    "spot_2h": {"cave_path": "circle", "path_radius": SPOT_RADIUS, "path_period": 7_200},
}
B6_GRID: Tuple[Tuple[int, int], ...] = ((20, 10), (50, 18), (100, 36), (200, 72))  # (cycle, run) s: stage 3c's B6 and its shorter and longer kin
B8_AIM_TAU = 10.0  # s: B8's aim averages the wall's first mode over about ten readings
STILL_ABOVE = 4.5  # B6 and B7 keep still from here (stage 3c's §5)
PERFECT = {"sense_contrast": 1e4, "sensor_noise_sd": 0.0}
SIMPLE = ("B2r", "B5", "B6", "B8")  # the rules whose best sets the bar
SELECT, REPORT, GENOME_STARTS = (1, 50), (51, 100), (51, 70)
N_GENOMES = 100
CHUNK = 50
DEFAULT_OUT = Path("docs/data/stage4/probe")


def world_cfg(name: str, quick: bool) -> Config:
    return configure(quick).but(**WORLDS[name])


def readrun(cfg: Config, aim: str, cycle: int, run: int) -> Dict[str, Any]:
    return {"controller": "readrun", "aim": aim, "cycle": cycle, "run": run, "rest_below": cfg.rest_below, "still_above": STILL_ABOVE}


def rules(cfg: Config) -> List[Tuple[str, str, Config, Dict[str, Any]]]:
    """Every rule and parameter the probe runs: (rule, parameter, the world as the cell senses it, its spec)."""
    out: List[Tuple[str, str, Config, Dict[str, Any]]] = [("B0", "-", cfg, {"controller": "still"}),
                                                          ("B7", "-", cfg, readrun(cfg, "random", 100, 36))]
    out += [("B2r", f"k={k:g}", cfg, reflex(cfg, k)) for k in K_GRID]
    out += [("B5", f"tau={tau:g}", cfg, runwait(cfg, tau)) for tau in TAU_GRID]
    out += [("B6", f"cycle={c},run={r}", cfg, readrun(cfg, "read", c, r)) for c, r in B6_GRID]
    out += [("B8", f"tau={tau:g}", cfg, {"controller": "aimrun", "tau": tau, "aim_tau": B8_AIM_TAU, "rest_below": cfg.rest_below})
            for tau in TAU_GRID]
    perfect = cfg.but(**PERFECT)
    out += [("B6 perfect", f"cycle={c},run={r}", perfect, readrun(perfect, "read", c, r)) for c, r in B6_GRID]
    return out


def sim_job(job: Mapping[str, Any]) -> Dict[str, Any]:
    starts: Starts = job["starts"]
    r = simulate(job["cfg"], starts, job["spec"], seed=SEED, cell_ids=[0] * len(starts))
    return {"world": job["world"], "rule": job["rule"], "param": job["param"], "first": job["first"], "fitness": r.fitness,
            "survived": r.survived, "mean_beat": r.mean_beat}


def always_brightest(cfg: Config, starts: Starts) -> Tuple[np.ndarray, np.ndarray]:
    """The ceiling: a still cell put at the brightest point every tick (the light's source, kept within the clamp radius),
    with each start's lifetime, reserve and sky, counted as ``simulate`` counts a cell (dead ticks 0). Damage is off in
    every candidate world. Returns each start's fitness and survival."""
    if math.isfinite(cfg.damage_threshold):
        raise ValueError("the ceiling is computed without damage")
    n = len(starts)
    ends = lifetimes(cfg, starts)
    sky = Sky(cfg, SEED, starts.index.tolist()) if cfg.cloud_shade != 1.0 else None
    energy, alive, total = start_energy(cfg, "cave", starts.phase), np.ones(n, dtype=bool), np.zeros(n)
    heading, still = starts.heading.copy(), np.zeros((n, cfg.n_wall))  # a still cell keeps its heading
    for t in range(int(ends.max())):
        when = starts.phase + t
        active = alive & (t < ends)
        light = node_light(cfg, "cave", starts.source, clamp(cfg, mouth_position(cfg, when)), heading, when)
        if sky is not None:
            light = light * sky.at(t)[:, None]
        new, _, _ = energy_step(cfg, energy, light, still)
        starved = active & (new <= 0.0)
        energy = np.where(active, np.where(starved, 0.0, new), energy)
        alive = alive & ~starved
        total += np.where(active, energy, 0.0)
    return total / ends, alive


def ceiling_job(job: Mapping[str, Any]) -> Dict[str, Any]:
    fitness, survived = always_brightest(job["cfg"], job["starts"])
    return {"world": job["world"], "fitness": fitness, "survived": survived}


def ci(diff: np.ndarray, key: int, resamples: int) -> Tuple[float, float, float]:
    idx = stream(BOOTSTRAP_SEED, "bootstrap", (key,)).integers(0, diff.shape[0], size=(resamples, diff.shape[0]))
    means = diff[idx].mean(axis=1)
    return float(diff.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def run(out: Path, workers: int, quick: bool, only: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    n_starts = 8 if quick else 100
    select, report = ((1, 4), (5, 8)) if quick else (SELECT, REPORT)
    genome_starts, n_genomes = ((5, 6), 4) if quick else (GENOME_STARTS, N_GENOMES)
    resamples = 200 if quick else RESAMPLES
    chunk = 4 if quick else CHUNK
    out.mkdir(parents=True, exist_ok=True)
    names = list(WORLDS) if not only else [w for w in WORLDS if w in only]
    cfgs = {w: world_cfg(w, quick) for w in names}
    settings = {"base": configure(quick).as_dict(), "worlds": {w: WORLDS[w] for w in names}, "seed": SEED, "bootstrap_seed": BOOTSTRAP_SEED, "resamples": resamples,
                "n_starts": n_starts, "select": select, "report": report, "k_grid": K_GRID, "tau_grid": TAU_GRID, "b6_grid": B6_GRID,
                "b8_aim_tau": B8_AIM_TAU, "still_above": STILL_ABOVE, "perfect": PERFECT, "genome_starts": genome_starts,
                "n_genomes": n_genomes, "quick": quick}
    manifest = build_manifest(protocol="stage4_probe", settings=settings, seeds=[SEED, BOOTSTRAP_SEED], extra={"out": str(out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:7.1f}s {msg}", flush=True)

    jobs, ceiling_jobs, genome_jobs = [], [], []
    for w, cfg in cfgs.items():
        starts = sample_starts(cfg, "cave", n_starts, SEED)
        for lo in range(0, n_starts, chunk):
            part = starts.take(range(lo, min(lo + chunk, n_starts)))
            jobs += [{"cfg": c, "starts": part, "spec": spec, "world": w, "rule": rule, "param": param, "first": lo}
                     for rule, param, c, spec in rules(cfg)]
            ceiling_jobs.append({"cfg": cfg, "starts": part, "world": w, "first": lo})
        chosen = starts.numbered(range(genome_starts[0], genome_starts[1] + 1))
        for mode in MODES:
            genomes = random_genomes(cfg, mode, n_genomes, stream(SEED, STREAM_GENOMES))
            for lo in range(0, n_genomes, 25):
                hi = min(lo + 25, n_genomes)
                genome_jobs.append({"cfg": cfg, "starts": chosen, "genomes": genomes[lo:hi], "numbers": np.arange(lo + 1, hi + 1),
                                    "mode": mode, "seed": SEED, "world": w})
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        ceiling_futures = [(j["world"], j["first"], pool.submit(ceiling_job, j)) for j in ceiling_jobs]
        sim_futures = [pool.submit(sim_job, j) for j in jobs]
        genome_futures = [(j["world"], pool.submit(b3_job, j)) for j in genome_jobs]
        ceilings = [(w, first, f.result()) for w, first, f in ceiling_futures]
        log("the ceilings done")
        results = [f.result() for f in sim_futures]
        log(f"{len(results)} rule runs done")
        genome_rows = [{**row, "world": w} for w, f in genome_futures for row in f.result()]
        log("the random genomes done")

    def gather(parts: Sequence[Mapping[str, Any]], key: str) -> np.ndarray:
        return np.concatenate([p[key] for p in sorted(parts, key=lambda p: p["first"])])

    sel = np.arange(select[0] - 1, select[1])
    rep = np.arange(report[0] - 1, report[1])
    grid_rows, per_start_rows, worlds_out, headroom_rows = [], [], {}, []
    key = 0
    for w in names:
        ceiling = gather([{"first": first, **c} for ww, first, c in ceilings if ww == w], "fitness")
        ceiling_alive = gather([{"first": first, **c} for ww, first, c in ceilings if ww == w], "survived")
        runs: Dict[Tuple[str, str], Dict[str, np.ndarray]] = {}
        for rule, param, _, _ in rules(cfgs[w]):
            mine = [r for r in results if r["world"] == w and r["rule"] == rule and r["param"] == param]
            runs[(rule, param)] = {k: gather(mine, k) for k in ("fitness", "survived", "mean_beat")}
        for (rule, param), r in runs.items():
            for name, idx in (("select", sel), ("report", rep)):
                grid_rows.append({"world": w, "rule": rule, "param": param, "starts": name, "mean_fitness": float(r["fitness"][idx].mean()),
                                  "survival": float(r["survived"][idx].mean()), "mean_beat": float(r["mean_beat"][idx].mean())})
            per_start_rows += [{"world": w, "rule": rule, "param": param, "start": i + 1, "fitness": float(r["fitness"][i]),
                                "survived": int(r["survived"][i])} for i in range(n_starts)]
        per_start_rows += [{"world": w, "rule": "ceiling", "param": "-", "start": i + 1, "fitness": float(ceiling[i]),
                            "survived": int(ceiling_alive[i])} for i in range(n_starts)]
        chosen: Dict[str, Dict[str, Any]] = {}
        for rule in ("B0", "B7", "B2r", "B5", "B6", "B8", "B6 perfect"):
            options = [(param, r) for (ru, param), r in runs.items() if ru == rule]
            best_i = max(range(len(options)), key=lambda i: (options[i][1]["fitness"][sel].mean(), options[i][1]["survived"][sel].mean(), -i))
            param, r = options[best_i]
            chosen[rule] = {"param": param, "fitness": r["fitness"][rep], "report_fitness": float(r["fitness"][rep].mean()),
                            "report_survival": float(r["survived"][rep].mean())}
        best_rule = max(SIMPLE, key=lambda ru: chosen[ru]["report_fitness"])
        key += 1
        head, lo, hi = ci(ceiling[rep] - chosen[best_rule]["fitness"], key, resamples)
        key += 1
        perfect_gain, plo, phi = ci(chosen["B6 perfect"]["fitness"] - chosen[best_rule]["fitness"], key, resamples)
        g = [row for row in genome_rows if row["world"] == w]
        best_random = max((float(row["mean_fitness"]) for row in g), default=math.nan)
        b0 = chosen["B0"]["report_fitness"]
        worlds_out[w] = {"ceiling": float(ceiling[rep].mean()), "ceiling_survival": float(ceiling_alive[rep].mean()),
                         "rules": {ru: {k: v for k, v in c.items() if k != "fitness"} for ru, c in chosen.items()},
                         "best_simple_rule": best_rule, "headroom": head, "headroom_low": lo, "headroom_high": hi,
                         "perfect_reading_gain": perfect_gain, "perfect_reading_low": plo, "perfect_reading_high": phi,
                         "best_random_genome": best_random, "random_share_above_b0": float(np.mean([float(row["mean_fitness"]) > b0 for row in g])) if g else math.nan}
        headroom_rows.append({"world": w, "ceiling": worlds_out[w]["ceiling"], "best_simple_rule": best_rule,
                              "its_param": chosen[best_rule]["param"], "its_fitness": chosen[best_rule]["report_fitness"],
                              "headroom": head, "headroom_low": lo, "headroom_high": hi, "B2r": chosen["B2r"]["report_fitness"],
                              "B5": chosen["B5"]["report_fitness"], "B6": chosen["B6"]["report_fitness"], "B8": chosen["B8"]["report_fitness"],
                              "B6_perfect": chosen["B6 perfect"]["report_fitness"], "B0": b0, "B7": chosen["B7"]["report_fitness"],
                              "best_random_genome": best_random})
        log(f"{w:9s} ceiling {worlds_out[w]['ceiling']:.3f}; best simple rule {best_rule} ({chosen[best_rule]['param']}) "
            f"{chosen[best_rule]['report_fitness']:.3f}; headroom {head:+.3f} [{lo:+.3f}, {hi:+.3f}]; B2r {chosen['B2r']['report_fitness']:.3f} "
            f"B5 {chosen['B5']['report_fitness']:.3f} B6 {chosen['B6']['report_fitness']:.3f} B8 {chosen['B8']['report_fitness']:.3f} "
            f"B6 perfect {chosen['B6 perfect']['report_fitness']:.3f}; B0 {b0:.3f} B7 {chosen['B7']['report_fitness']:.3f}; best random {best_random:.3f}")
    write_csv(out / "grid.csv", ("world", "rule", "param", "starts", "mean_fitness", "survival", "mean_beat"), grid_rows)
    write_csv(out / "per_start.csv", ("world", "rule", "param", "start", "fitness", "survived"), per_start_rows)
    write_csv(out / "headroom.csv", tuple(headroom_rows[0]), headroom_rows)
    write_csv(out / "random_genomes.csv", ("world", *B3_COLUMNS), genome_rows)
    summary = {"worlds": worlds_out, "quick": quick}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=_json) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0, workers=workers, rule_runs=len(jobs), genome_jobs=len(genome_jobs))
    write_manifest(out / "manifest.json", manifest)
    log(f"done, written to {out}")
    return summary


def _json(x: Any) -> Any:
    if isinstance(x, np.integer):
        return int(x)
    if isinstance(x, np.floating):
        return float(x)
    if isinstance(x, np.ndarray):
        return x.tolist()
    raise TypeError(type(x))


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
