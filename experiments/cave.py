"""The cave pool's checks K1–K7 (docs/prereg/cave.md §9–§10) in its four configurations, in order.

    .venv/bin/python -W error::RuntimeWarning -m experiments.cave --config all --workers 16
    .venv/bin/python -m experiments.cave --config burn --quick --out /tmp/cave-smoke     # the smoke test's sizes, not a result

Per configuration (`noon`, `day`, `burn`, `sweep`): starts 1–100 from stream ``starts`` (seed 2); K2 and K3 from the
starts' geometry; B0 on every start and at the probe's best fixed point (K1); B1 (K4's clause); B2r's gain chosen on
starts 1–50 and reported on 51–100 (K4, the bar), B2rr likewise where damage is on (K7); 1,000 random genomes per
spoke mode on starts 51–70 (K5); K6 on short batches. Every batch is a job in the process pool. The tables,
``summary.json`` and ``manifest.json`` go to ``docs/data/cave/<configuration>/``.
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

from experiments.cave_geometry import Cave, probe
from experiments.stage0 import (B3_COLUMNS, K_GRID, Sizes, _fmt, _json_default, b3_job, numbers, reach_summary, share, write_csv)
from protocell.cell import MODES, STREAM_GENOMES, genome_length, random_genomes
from protocell.config import CAVE, Config
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.rng import stream
from protocell.sim import BURNT, NOISE_CHUNK, STREAM_BEATS, STREAM_MOTION, STREAM_SENSORS, RunResult, simulate
from protocell.world import (Starts, centre_light, daylight, lifetimes, mouth_position, sample_starts, soak_distance, soak_radius,
                             source_distance)

SEED = 2  # the cave's starts and genomes (cave.md §6): fresh
DEFAULT_OUT = Path("docs/data/cave")
CONFIGURATIONS: Dict[str, Dict[str, Any]] = {
    "noon": {"cave_cycle": False, "damage_threshold": math.inf, "cave_sweep": False},
    "day": {"cave_cycle": True, "damage_threshold": math.inf, "cave_sweep": False},
    "burn": {"cave_cycle": True, "damage_threshold": 4.0, "cave_sweep": False},
    "sweep": {"cave_cycle": True, "damage_threshold": 4.0, "cave_sweep": True},
}
RUN_COLUMNS = ("start", "cell", "phase", "lifetime", "start_distance", "survived", "fitness", "light_soaked", "mean_beat",
               "effort_per_light", "reach_tick", "death_tick", "death_cause", "final_energy", "final_damage", "min_energy",
               "min_sunset_energy", "night_beat", "burn_share", "soak_share")
STARTS_COLUMNS = ("start", "phase", "pos_x", "pos_y", "heading", "mouth_distance", "noon_light", "noon_contrast", "contrast_ge_3sd_noon",
                  "dawn1_light", "dawn1_contrast", "contrast_ge_3sd_dawn1", "noon_light_1000_nearer", "rise_ge_3sd", "soak_distance",
                  "soak_ticks", "within_hour")


def configure(name: str, quick: bool) -> Config:
    cfg = CAVE.but(**CONFIGURATIONS[name])
    if quick:
        cfg = cfg.but(day_ticks=2000, lifetime=4000)
    return cfg


def cave_for(cfg: Config) -> Cave:
    """The probe's view of this configuration."""
    return Cave(pool_radius=cfg.dish_radius, mouth_light=cfg.mouth_light, falloff=cfg.cave_falloff, shade_floor=cfg.shade_floor,
                sweep_deg=cfg.cave_sweep_deg, sweep=cfg.cave_sweep, cycle=cfg.cave_cycle, damage=math.isfinite(cfg.damage_threshold),
                damage_threshold=cfg.damage_threshold if math.isfinite(cfg.damage_threshold) else 4.0, damage_rate=cfg.damage_rate,
                damage_repair=cfg.damage_repair, c0=cfg.c0, c1=cfg.c1, eta=cfg.eta, sensor_sd=cfg.sensor_noise_sd,
                energy_fill=1.0 - cfg.c0 * (cfg.day_ticks / 2))


PROBE_KEYS = ("sitter_share", "sitter_share_any_phase", "best_distance_to_mouth", "best_noon_light", "best_mean_reserve",
              "burn_share_noon", "soak_share_noon", "best_x", "best_y")


def best_fixed_point(cfg: Config, n_points: int, phases: Optional[Sequence[int]]) -> Tuple[np.ndarray, Dict[str, Any]]:
    """K1's best fixed point for this configuration, from the probe (cave.md §13; its default phases unless given),
    with the probe's shares. The quick run's day is not the probe's, so there B0 is placed one radius from the mouth."""
    if cfg.day_ticks != 86_400:
        return np.array([0.0, -cfg.clamp_radius]), {k: None for k in PROBE_KEYS}
    r = probe(cave_for(cfg), n_points=n_points, **({"phases": tuple(phases)} if phases else {}))
    return np.array([r["best_x"], r["best_y"]]), {k: r[k] for k in PROBE_KEYS}


def run_summary(result: RunResult) -> Dict[str, Any]:
    out = {"n": len(result), "survival": share(result.survived), "mean_fitness": float(result.fitness.mean()),
           "mean_light_soaked": float(result.light_soaked.mean()), "mean_beat": float(result.mean_beat.mean()),
           "effort_per_light": float(result.mean_beat.sum() / result.light_soaked.sum()) if result.light_soaked.sum() > 0 else None,
           "burnt_share": share(result.death_cause == BURNT), "starved_share": share(result.death_cause == 1),
           "mean_burn_share": float(result.burn_share.mean()), "mean_soak_share": float(result.soak_share.mean()),
           "min_sunset_energy_ge_095_share": share(result.min_sunset_energy >= 0.95), **reach_summary(result)}
    nights = ~np.isnan(result.night_beat)
    out["night_beat"] = float(result.night_beat[nights].mean()) if nights.any() else None
    return out


# --- the geometric checks -------------------------------------------------------------------------------------------

def starts_table(cfg: Config, starts: Starts) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    """K2 and K3 from the starts' places: the shading contrast (0.7 of the centre's light) at noon and an hour after
    sunrise against three times the sensor noise; the rise in the centre's light 1,000 R nearer the mouth at noon;
    the straight distance to the noon soak region."""
    noon = np.full(len(starts), cfg.day_ticks // 4)
    dawn1 = np.full(len(starts), 3600)
    threshold = 3.0 * cfg.sensor_noise_sd
    light_noon = centre_light(cfg, "cave", starts.source, starts.pos, noon)
    light_dawn1 = centre_light(cfg, "cave", starts.source, starts.pos, dawn1)
    mouth = mouth_position(cfg, noon)
    toward = mouth - starts.pos
    dist = np.sqrt(toward[:, 0] ** 2 + toward[:, 1] ** 2)
    step = np.minimum(1000.0, dist)
    nearer = starts.pos + toward * (step / np.maximum(dist, 1e-300))[:, None]
    light_nearer = centre_light(cfg, "cave", starts.source, nearer, noon)
    contrast_noon, contrast_dawn1, rise = 0.7 * light_noon, 0.7 * light_dawn1, light_nearer - light_noon
    distance = soak_distance(cfg, "cave", starts.source, starts.pos)
    ticks = distance / cfg.v_max
    rows = []
    for i in range(len(starts)):
        rows.append({"start": int(starts.index[i]), "phase": int(starts.phase[i]), "pos_x": starts.pos[i, 0], "pos_y": starts.pos[i, 1],
                     "heading": starts.heading[i], "mouth_distance": dist[i], "noon_light": light_noon[i], "noon_contrast": contrast_noon[i],
                     "contrast_ge_3sd_noon": contrast_noon[i] >= threshold, "dawn1_light": light_dawn1[i], "dawn1_contrast": contrast_dawn1[i],
                     "contrast_ge_3sd_dawn1": contrast_dawn1[i] >= threshold, "noon_light_1000_nearer": light_nearer[i],
                     "rise_ge_3sd": rise[i] >= threshold, "soak_distance": distance[i], "soak_ticks": ticks[i], "within_hour": ticks[i] <= 3600})
    k2 = {"threshold": threshold, "share_contrast_ge_3sd_noon": share(contrast_noon >= threshold),
          "share_contrast_ge_3sd_dawn1": share(contrast_dawn1 >= threshold), "share_rise_ge_3sd": share(rise >= threshold),
          "median_noon_light": float(np.median(light_noon)), "min_noon_light": float(light_noon.min())}
    k2["pass"] = bool(k2["share_contrast_ge_3sd_noon"] >= 0.9 and k2["share_contrast_ge_3sd_dawn1"] >= 0.5 and k2["share_rise_ge_3sd"] >= 0.9)
    k3 = {"soak_radius": soak_radius(cfg, "cave"), "max_soak_ticks": float(ticks.max()), "median_soak_ticks": float(np.median(ticks)),
          "pass": bool((ticks <= 3600).all())}
    return rows, k2, k3


# --- jobs -----------------------------------------------------------------------------------------------------------

def sim_job(job: Mapping[str, Any]) -> RunResult:
    return simulate(job["cfg"], job["starts"], job["spec"], seed=SEED, cell_ids=job.get("cell_ids"))


def reflex_spec(cfg: Config, k: float, retreat: bool) -> Dict[str, Any]:
    spec = {"controller": "reflex", "k": k, "rest_below": cfg.rest_below}
    if retreat:
        spec["retreat_above"] = cfg.damage_threshold
        spec["retreat_on"] = cfg.retreat_on
    return spec


def best_gain(by_k: Mapping[float, Mapping[str, Any]]) -> float:
    return max(K_GRID, key=lambda k: (by_k[k]["mean_fitness"], by_k[k]["survival"], -k))


# --- K6 ---------------------------------------------------------------------------------------------------------------

def check_k6(cfg: Config, starts: Starts, reflex: Mapping[str, Any], cells: int) -> Dict[str, Any]:
    """Same seed, same hash (B2r and a network cell, each run twice); a batch equals its singles; the streams are
    independent (stage 0's W6, on the cave's cells and lifetimes)."""
    mode = "fourier1"
    genomes = random_genomes(cfg, mode, cells, stream(SEED, STREAM_GENOMES))
    ids = list(range(1, cells + 1))
    net = {"controller": "network", "mode": mode, "genomes": genomes}
    same_reflex = simulate(cfg, starts, reflex, seed=SEED, record=True).run_hash() == simulate(cfg, starts, reflex, seed=SEED, record=True).run_hash()
    batch = simulate(cfg, starts, net, seed=SEED, cell_ids=ids, record=True)
    same_net = batch.run_hash() == simulate(cfg, starts, net, seed=SEED, cell_ids=ids, record=True).run_hash()
    singles_equal = True
    for i in range(cells):
        single = simulate(cfg, starts.take([i]), {**net, "genomes": genomes[i:i + 1]}, seed=SEED, cell_ids=ids[i:i + 1], record=True)
        assert single.trajectory is not None and batch.trajectory is not None
        own = int(single.lifetime[0])
        singles_equal &= all(np.array_equal(single.trajectory[n][0, :own], batch.trajectory[n][i, :own]) for n in ("pos", "heading", "energy", "beat"))
        singles_equal &= bool(single.survived[0] == batch.survived[i] and single.fitness[0] == batch.fitness[i]
                              and single.night_beat[0] == batch.night_beat[i] if not math.isnan(single.night_beat[0]) else True)
    both = batch.noise_digests
    no_sensors = simulate(cfg.but(sensor_noise_sd=0.0), starts, net, seed=SEED, cell_ids=ids)
    no_motion = simulate(cfg.but(rotation_noise_sd=0.0), starts, net, seed=SEED, cell_ids=ids)
    random_both = simulate(cfg, starts, {"controller": "random"}, seed=SEED)
    random_no_motion = simulate(cfg.but(rotation_noise_sd=0.0), starts, {"controller": "random"}, seed=SEED)
    still_on = simulate(cfg, starts, {"controller": "still"}, seed=SEED, record=True)
    still_off = simulate(cfg.but(sensor_noise_sd=0.0), starts, {"controller": "still"}, seed=SEED, record=True)
    independent = (no_sensors.noise_digests[STREAM_MOTION] == both[STREAM_MOTION]
                   and no_motion.noise_digests[STREAM_SENSORS] == both[STREAM_SENSORS]
                   and random_no_motion.noise_digests[STREAM_BEATS] == random_both.noise_digests[STREAM_BEATS]
                   and still_on.run_hash() == still_off.run_hash())
    out = {"same_seed_same_hash_reflex": bool(same_reflex), "same_seed_same_hash_network": bool(same_net),
           "batch_equals_singles": bool(singles_equal), "streams_independent": bool(independent),
           "network_run_hash": batch.run_hash(), "cells": cells}
    out["pass"] = all(v for k, v in out.items() if isinstance(v, bool))
    return out


# --- a configuration --------------------------------------------------------------------------------------------------

def run_configuration(name: str, cfg: Config, sizes: Sizes, out: Path, pool: ProcessPoolExecutor, log) -> Tuple[Dict[str, Any], int]:
    out.mkdir(parents=True, exist_ok=True)
    damage_on = math.isfinite(cfg.damage_threshold)
    starts = sample_starts(cfg, "cave", sizes.n_starts, SEED)
    rows, k2, k3 = starts_table(cfg, starts)
    write_csv(out / "starts.csv", STARTS_COLUMNS, rows)
    log(f"[{name}] K2 contrast >= 3 sd at noon on {k2['share_contrast_ge_3sd_noon']:.0%}, an hour after sunrise on {k2['share_contrast_ge_3sd_dawn1']:.0%}; "
        f"rise on {k2['share_rise_ge_3sd']:.0%}; K3 farthest {k3['max_soak_ticks']:.0f} ticks")

    full = sizes.n_genomes >= 100
    best_point, probed = best_fixed_point(cfg, 1000 if full else 40, None if full else (0, cfg.day_ticks // 2))
    select, report = numbers(sizes.select), numbers(sizes.report)
    chosen, reported = starts.numbered(select), starts.numbered(report)
    jobs: Dict[str, Dict[str, Any]] = {
        "b0": {"cfg": cfg, "starts": starts, "spec": {"controller": "still"}},
        "b0_best": {"cfg": cfg, "starts": starts.with_pos(np.repeat(best_point[None, :], len(starts), axis=0)), "spec": {"controller": "still"}},
        "b1": {"cfg": cfg, "starts": starts, "spec": {"controller": "random"}},
    }
    for k in K_GRID:
        jobs[f"b2r_k{k:g}"] = {"cfg": cfg, "starts": chosen, "spec": reflex_spec(cfg, k, False)}
        if damage_on:
            jobs[f"b2rr_k{k:g}"] = {"cfg": cfg, "starts": chosen, "spec": reflex_spec(cfg, k, True)}
    genome_starts = starts.numbered(numbers(sizes.genome_starts))
    b3_jobs: Dict[str, List[Dict[str, Any]]] = {}
    for mode in MODES:
        genomes = random_genomes(cfg, mode, sizes.n_genomes, stream(SEED, STREAM_GENOMES))
        b3_jobs[mode] = [{"cfg": cfg, "starts": genome_starts, "genomes": genomes[lo:min(lo + sizes.genomes_per_job, sizes.n_genomes)],
                          "numbers": np.arange(lo + 1, min(lo + sizes.genomes_per_job, sizes.n_genomes) + 1), "mode": mode, "seed": SEED}
                         for lo in range(0, sizes.n_genomes, sizes.genomes_per_job)]
    futures = {key: pool.submit(sim_job, job) for key, job in jobs.items()}
    b3_futures = {mode: [pool.submit(b3_job, job) for job in b3_jobs[mode]] for mode in MODES}
    results = {key: f.result() for key, f in futures.items()}
    cells = sum(len(r) for r in results.values())

    # K1
    b0, b0_best = results["b0"], results["b0_best"]
    write_csv(out / "b0.csv", RUN_COLUMNS, b0.rows(starts))
    write_csv(out / "b0_best.csv", RUN_COLUMNS, b0_best.rows(starts))
    best_ok = b0_best.survived & (b0_best.min_sunset_energy >= 0.95) if cfg.cave_cycle else b0_best.survived & (b0_best.final_energy > b0_best.fitness * 0 + 0.95)
    k1 = {"b0": run_summary(b0), "b0_survival": share(b0.survived), "probe": probed, "b0_best": run_summary(b0_best),
          "b0_best_survived_full_share": share(best_ok), "judged": bool(cfg.cave_cycle)}
    log(f"[{name}] K1 B0 survives on {k1['b0_survival']:.0%} (the probe's share by position {probed['sitter_share']}); at the best fixed point, "
        f"full at each sunset on {k1['b0_best_survived_full_share']:.0%}")

    # B2r, B2rr
    by_k = {k: run_summary(results[f"b2r_k{k:g}"]) for k in K_GRID}
    write_csv(out / "b2r_select.csv", ("k", *RUN_COLUMNS), [row for k in K_GRID for row in results[f"b2r_k{k:g}"].rows(chosen, k=k)])
    k_r = best_gain(by_k)
    second = {"b2r": pool.submit(sim_job, {"cfg": cfg, "starts": reported, "spec": reflex_spec(cfg, k_r, False)})}
    k_rr: Optional[float] = None
    if damage_on:
        by_k_rr = {k: run_summary(results[f"b2rr_k{k:g}"]) for k in K_GRID}
        write_csv(out / "b2rr_select.csv", ("k", *RUN_COLUMNS), [row for k in K_GRID for row in results[f"b2rr_k{k:g}"].rows(chosen, k=k)])
        k_rr = best_gain(by_k_rr)
        second["b2rr"] = pool.submit(sim_job, {"cfg": cfg, "starts": reported, "spec": reflex_spec(cfg, k_rr, True)})
    b2r = second["b2r"].result()
    cells += len(b2r)
    write_csv(out / "b2r_report.csv", RUN_COLUMNS, b2r.rows(reported))
    bar = {"k": k_r, "selection": {str(k): by_k[k] for k in K_GRID}, "report": run_summary(b2r)}
    b1 = results["b1"]
    write_csv(out / "b1.csv", RUN_COLUMNS, b1.rows(starts))
    k4 = {"b1": run_summary(b1), "b1_survival": share(b1.survived), "bar": bar, "pass": bool(share(b1.survived) < 0.5)}
    log(f"[{name}] K4 B2r k={k_r:g}: survival {bar['report']['survival']:.0%}, fitness {bar['report']['mean_fitness']:.3f}, "
        f"night beat {bar['report']['night_beat']}; B1 survival {k4['b1_survival']:.0%}")
    k7: Dict[str, Any] = {"judged": damage_on}
    if damage_on:
        b2rr = second["b2rr"].result()
        cells += len(b2rr)
        write_csv(out / "b2rr_report.csv", RUN_COLUMNS, b2rr.rows(reported))
        k7.update({"b2r_burnt_share": share(b2r.death_cause == BURNT), "b2rr": {"k": k_rr, "selection": {str(k): by_k_rr[k] for k in K_GRID},
                   "report": run_summary(b2rr)}, "b2rr_survival": share(b2rr.survived)})
        k7["pass"] = bool(k7["b2r_burnt_share"] >= 0.5 and k7["b2rr_survival"] >= 0.5)
        log(f"[{name}] K7 B2r burnt on {k7['b2r_burnt_share']:.0%}; B2rr k={k_rr:g} survives {k7['b2rr_survival']:.0%} at fitness {k7['b2rr']['report']['mean_fitness']:.3f}")
    if cfg.cave_sweep:  # K1's second clause is read on B2rr (the pre-run clarification)
        k1["b0_best_survived_full_share"] = k7["b2rr_survival"]
        k1["second_clause_read_on"] = "b2rr"
    k1["pass"] = bool(not cfg.cave_cycle or (k1["b0_survival"] <= 0.10 and k1["b0_best_survived_full_share"] >= 0.9))

    # K5: random genomes against the configuration's bar, B2r, or with damage on B2rr (§8 "stage 2's bar"; amendment A1)
    bar_name = "b2rr" if damage_on else "b2r"
    k5_bar = k7["b2rr"]["report"] if damage_on else bar["report"]
    k5: Dict[str, Any] = {"bar": bar_name}
    for mode in MODES:
        rows = [row for f in b3_futures[mode] for row in f.result()]
        cells += sizes.n_genomes * len(numbers(sizes.genome_starts))
        write_csv(out / f"b3_{mode}.csv", B3_COLUMNS, rows)
        survival = np.array([r["survival"] for r in rows])
        fitness = np.array([r["mean_fitness"] for r in rows])
        matched = survival >= k5_bar["survival"]
        k5[mode] = {"n_genomes": len(rows), "share_matching_bar_survival": share(matched), "share_matching_bar_fitness": share(fitness >= k5_bar["mean_fitness"]),
                    "mean_survival": float(survival.mean()), "share_any_survival": share(survival > 0), "mean_fitness": float(fitness.mean()),
                    "best_fitness": float(fitness.max()), "share_any_reach": share(np.array([r["reached_share"] for r in rows]) > 0),
                    "pass": bool(share(matched) < 0.05)}
        log(f"[{name}] K5 {mode}: {k5[mode]['share_matching_bar_survival']:.1%} of genomes match {bar_name.upper()}'s survival; mean survival {k5[mode]['mean_survival']:.1%}")
    k5["pass"] = all(k5[m]["pass"] for m in MODES)

    # K6
    few = reported.take(list(range(sizes.w6_cells)))
    k6 = check_k6(cfg, few, reflex_spec(cfg, k_r, False), sizes.w6_cells)
    log(f"[{name}] K6 {'passes' if k6['pass'] else 'FAILS'}")
    checks = {"K1": k1, "K2": k2, "K3": k3, "K4": k4, "K5": k5, "K6": k6, "K7": k7}
    judged = {c: checks[c]["pass"] for c in checks if checks[c].get("judged", True)}
    log(f"[{name}] " + ", ".join(f"{c} {'pass' if p else 'FAIL'}" for c, p in judged.items()))
    config_bar = (k7["b2rr"]["report"] | {"k": k_rr, "controller": "b2rr"}) if damage_on else (bar["report"] | {"k": k_r, "controller": "b2r"})
    return {"checks": checks, "bar": config_bar, "all_pass": all(judged.values())}, cells


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", nargs="+", default=["all"], choices=["all", *CONFIGURATIONS], help="one or more configurations, in order")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    args = parser.parse_args(argv)
    names = list(CONFIGURATIONS) if "all" in args.config else [c for c in CONFIGURATIONS if c in args.config]
    sizes = Sizes.quick() if args.quick else Sizes()
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:7.1f}s {msg}", flush=True)

    summaries: Dict[str, Any] = {}
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as pool:
        for name in names:
            cfg = configure(name, args.quick)
            out = args.out / name
            settings = {**cfg.as_dict(), "configuration": name, "seed": SEED, "sizes": sizes.__dict__, "k_grid": K_GRID, "modes": MODES,
                        "noise_chunk": NOISE_CHUNK, "genome_length": {m: genome_length(cfg, m) for m in MODES}, "quick": args.quick}
            manifest = build_manifest(protocol=f"cave/{name}", settings=settings, seeds=[SEED], extra={"out": str(out)})
            t1 = time.time()
            summary, cells = run_configuration(name, cfg, sizes, out, pool, log)
            summary["quick"] = args.quick
            (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=_json_default) + "\n")
            finish_manifest(manifest, wall_seconds=time.time() - t1, cells=cells, workers=args.workers)
            write_manifest(out / "manifest.json", manifest)
            summaries[name] = summary
            log(f"[{name}] done: {cells} cells, written to {out}")
    return summaries


if __name__ == "__main__":
    main(sys.argv[1:])
