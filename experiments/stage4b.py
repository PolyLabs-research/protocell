"""Stage 4b (docs/prereg/stage4b.md): evolution in stage 4a's world against the bar, then the test.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage4b --phase pilot --mode fourier1 --workers 16
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage4b --phase confirm --mode uniform --replicate 2 --workers 16
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage4b --phase test --workers 16
    .venv/bin/python -m experiments.stage4b --phase pilot --mode uniform --quick --out /tmp/s4b   # the smoke test: not a result

A run uses stage 1's algorithm unchanged (protocell/evolve.py) for 150 generations. Over generations 1-50 the
training world eases into stage 4a's (§3): the shading fades from the cave's 0.3 to none and the photosynthetic gain
falls from the cave's to 0.55 of it, both in straight lines. Generations 51-150 train in stage 4a's world, and the
champion is chosen from generation 51 by validation there (24 starts at seed 20). A run writes
``docs/data/stage4b/<phase>/<mode>-<seed>/``.

The test (§6) scores every champion found there on 100 starts at seed 21 with shared noise: against the bar (B8) and
B5, B6, the ceiling and B0, as stage 4a chose them; with each removal and each hold; with the direction across the body
removed and mirrored (stage 3c's goggles, the runs' onset bias read); and in stage 3c's flat pool. It reads §7's
criteria and scores §8's predictions. Bootstrap intervals at seed 22.
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

from experiments import stage3c, stage3c_probe, stage4_probe, stage4a
from experiments.stage1 import _jsonable, bootstrap_ci, find_champions, summarise, test_job
from experiments.stage1b import means_job
from protocell.cell import MODES, PATHWAYS, decode, genome_length
from protocell.config import CAVE, Config
from protocell.evolve import GA, NOISE_CELL_ID, run, validation_starts
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.sim import simulate
from protocell.tables import write_csv
from protocell.world import Starts, sample_starts

SEEDS = {"pilot": {"uniform": (1301,), "fourier1": (1302,)},
         "confirm": {"uniform": (2301, 2302, 2303), "fourier1": (3301, 3302, 3303)}}
GENERATIONS = 150
PATH_GENERATIONS = 50  # §3: the training world eases into stage 4a's over generations 1-50
SHADE_START = 0.3  # the cave's shaded cell
GAIN_START = 1.0  # the cave's photosynthetic gain, as a share of itself
VALIDATION_SEED = 20
TEST_SEED = 21
BOOTSTRAP_SEED = 22
TEST_STARTS = 100
RESAMPLES = 10_000
DELTA = 0.012  # a tenth of stage 4a's headroom above the bar (0.118)
REMOVALS = ("blind", "ring_links", "core", "core_recurrence", "wall_fast", "core_fast")  # §6: R0, R1, R3, R4, R5, R6
GOGGLES = {"G1": 1.0, "G0": 0.0, "G-1": -1.0}
DEFAULT_OUT = Path("docs/data/stage4b")
STAGE4A_SUMMARY = Path("docs/data/stage4a/summary.json")
DEFAULT_CHOICES = {"B8": "tau=10", "B5": "tau=3", "B6": "cycle=50,run=18"}  # stage 4a's choices (docs/data/stage4a/summary.json)


def ga_for(quick: bool) -> GA:
    return GA.quick().but(validation_seed=VALIDATION_SEED) if quick else GA().but(validation_seed=VALIDATION_SEED, generations=GENERATIONS)


def path_generations(quick: bool) -> int:
    return 2 if quick else PATH_GENERATIONS


def path_for(generation: int, path: int) -> Tuple[float, float]:
    """§3: the training world's shading floor and photosynthetic gain (as a share of the cave's) in a generation
    (1-based): from the cave's (0.3, 1) at generation 1 in straight lines to stage 4a's (1, 0.55) after ``path``
    generations, and stage 4a's from then on."""
    if generation <= path:
        f = (generation - 1) / path
        return SHADE_START + (1.0 - SHADE_START) * f, GAIN_START + (stage4a.GAIN_SCALE - GAIN_START) * f
    return 1.0, stage4a.GAIN_SCALE


def training_world(cfg: Config, generation: int, path: int) -> Config:
    shade, gain = path_for(generation, path)
    return cfg.but(shade_floor=shade, eta=CAVE.eta * gain)


def seed_for(phase: str, mode: str, replicate: int) -> int:
    seeds = SEEDS[phase][mode]
    if not 1 <= replicate <= len(seeds):
        raise SystemExit(f"{phase} has {len(seeds)} run(s) per mode")
    return seeds[replicate - 1]


def run_phase(phase: str, mode: str, replicate: int, out_root: Path, workers: int, quick: bool, stop_after: Optional[int]) -> Path:
    cfg = stage4a.world(quick)
    ga = ga_for(quick)
    seed = seed_for(phase, mode, replicate)
    out = out_root / phase / f"{mode}-{seed}"
    path = path_generations(quick)
    manifest = build_manifest(protocol=f"stage4b/{phase}", settings={**cfg.as_dict(), "world": "stage 4a", "mode": mode,
                                                                     "genome_length": genome_length(cfg, mode), "ga": ga.as_dict(), "quick": quick,
                                                                     "path_generations": path, "shade_start": SHADE_START, "gain_start": GAIN_START,
                                                                     "gain_end": stage4a.GAIN_SCALE, "champion_from": path + 1},
                              seeds=[seed], extra={"out": str(out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:8.1f}s [{mode}-{seed}] {msg}", flush=True)

    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        state = run(cfg, mode, ga, seed, out, pool.map, log=log, stop_after=stop_after,
                    world_for=lambda g: training_world(cfg, g, path), champion_from=path + 1)
    if state["next_generation"] >= ga.generations:
        finish_manifest(manifest, wall_seconds=time.time() - t0, generations=ga.generations, workers=workers)
        write_manifest(out / "manifest.json", manifest)
        info = state["champion_info"] or {}
        log(f"done: champion from generation {info.get('generation')}, validation fitness {info.get('validation_fitness')}, "
            f"survival {info.get('validation_survival')}")
    return out


# --- the test ---------------------------------------------------------------------------------------------------------

def stage4a_choices() -> Dict[str, str]:
    """The parameters stage 4a chose for B8 (the bar), B5 and B6."""
    if STAGE4A_SUMMARY.exists():
        rules = json.loads(STAGE4A_SUMMARY.read_text())["rules"]
        return {r: rules[r]["param"] for r in DEFAULT_CHOICES}
    return dict(DEFAULT_CHOICES)


def spec_of(cfg: Config, rule: str, param: str) -> Dict[str, Any]:
    for r, p, _, spec in stage4_probe.rules(cfg):
        if r == rule and p == param:
            return spec
    raise ValueError(f"no {rule} with {param}")


def goggles_job(job: Mapping[str, Any]) -> Dict[str, Any]:
    """A champion with its senses set (k), its runs' onset read as in stage 3c: each start's fitness, and each start's
    sum of the cosines to the mouth of the runs beginning in light 0.3-3, and their count."""
    cfg: Config = job["cfg"].but(sense_contrast=job["k"]) if job["k"] != 1.0 else job["cfg"]
    starts: Starts = job["starts"]
    n = len(starts)
    genomes = np.repeat(np.asarray(job["genome"])[None], n, axis=0)
    spec = {"controller": "network", "mode": job["mode"], "genomes": genomes}
    obs = stage3c_probe.Movement(cfg, starts, decode(cfg, job["mode"], genomes[:1]).alpha.repeat(n))
    r = simulate(cfg, starts, spec, seed=TEST_SEED, cell_ids=[NOISE_CELL_ID] * n, observe=obs)
    obs.runs.finish()
    bands = stage3c.onset_bands()
    s, k = np.zeros(n), np.zeros(n)
    for start, band, angle in obs.runs.onsets:
        if band in bands:
            s[start] += math.cos(angle)
            k[start] += 1
    return {"run": job["run"], "world": job["world"], "fitness": r.fitness, "cos_sum": s, "count": k}


def flat_job(job: Mapping[str, Any]) -> Dict[str, Any]:
    reps = job["replicates"]
    spec = {"controller": "network", "mode": job["mode"], "genomes": np.repeat(np.asarray(job["genome"])[None], reps, axis=0)}
    return {**stage3c.flat_job({**job, "spec": spec, "cell": job["run"]}), "run": job["run"]}


def read_q3(run_name: str, fitness: Mapping[str, np.ndarray], onset: Mapping[str, Tuple[np.ndarray, np.ndarray]],
            flat: Mapping[Tuple[str, float, str], Mapping[str, Any]], key: int, resamples: int) -> Dict[str, Any]:
    """§7 Q3 for one champion: it reads the direction if removing it drops its fitness by more than delta (interval) and
    its onset bias is below 0 with the direction mirrored (interval); it compares over time if stage 3c's C5 holds."""
    drop = bootstrap_ci(fitness["G1"] - fitness["G0"], key, resamples, seed=BOOTSTRAP_SEED)
    mirrored = stage3c.ratio_ci([onset["G-1"][0]], [onset["G-1"][1]], key + 1, resamples)[0]
    plain = stage3c.ratio_ci([onset["G1"][0]], [onset["G1"][1]], key + 2, resamples)[0]
    frosted = stage3c.ratio_ci([onset["G0"][0]], [onset["G0"][1]], key + 3, resamples)[0]
    reads = bool(drop[1] > DELTA and mirrored["high"] < 0.0)
    compares = stage3c.compares_over_time(flat, run_name)
    return {"reads_direction": reads, "fitness_G1_minus_G0": {"mean": drop[0], "low": drop[1], "high": drop[2]},
            "onset_bias": {"G1": plain, "G0": frosted, "G-1": mirrored}, "compares_over_time": compares["any_level"], "flat_pool": compares}


def test_phase(out_root: Path, workers: int, quick: bool) -> Dict[str, Any]:
    cfg = stage4a.world(quick)
    ga = ga_for(quick)
    n = 4 if quick else TEST_STARTS
    resamples = 200 if quick else RESAMPLES
    reps, settle, hold = (4, 700, 1800) if quick else (stage3c.FLAT_REPLICATES, stage3c.FLAT_SETTLE, stage3c.FLAT_HOLD)
    starts = sample_starts(cfg, "cave", n, TEST_SEED)
    choices = stage4a_choices()
    champions = find_champions(out_root)
    if not champions:
        raise SystemExit(f"no champions under {out_root}")
    vstarts = validation_starts(cfg, ga)
    t0 = time.time()
    common = {"cfg": cfg, "starts": starts, "seed": TEST_SEED}
    jobs = [{**common, "label": rule, "spec": spec_of(cfg, rule, choices[rule])} for rule in ("B8", "B5", "B6")]
    jobs.append({**common, "label": "B0", "spec": {"controller": "still"}})
    flat_cases = [(lv, st) for lv in stage3c.FLAT_LEVELS for st in stage3c.FLAT_STEPS]
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        ceiling_future = pool.submit(stage4a.ceiling_job, {"cfg": cfg, "starts": starts, "first": 0})
        means = {m["run"]: m for m in pool.map(means_job, [{"cfg": cfg, "mode": c["mode"], "genome": c["genome"], "starts": vstarts,
                                                              "seed": VALIDATION_SEED, "run": c["run"]} for c in champions])}
        for c in champions:
            base = {"controller": "network", "mode": c["mode"]}
            jobs.append({**common, "label": c["run"], "spec": base, "genome": c["genome"]})
            jobs += [{**common, "label": f"{c['run']} -{rm}", "spec": {**base, "removal": rm}, "genome": c["genome"]} for rm in REMOVALS]
            jobs += [{**common, "label": f"{c['run']} hold {p}", "genome": c["genome"], "spec": {**base, "hold": {"pathway": p, "means": means[c["run"]]["means"][p]}}}
                     for p in PATHWAYS]
        goggle_futures = [pool.submit(goggles_job, {"cfg": cfg, "starts": starts, "k": k, "world": w, "run": c["run"], "mode": c["mode"], "genome": c["genome"]})
                          for c in champions for w, k in GOGGLES.items()]
        flat_futures = [pool.submit(flat_job, {"cfg": cfg, "run": c["run"], "mode": c["mode"], "genome": c["genome"], "level": lv, "step": st,
                                               "replicates": reps, "settle": settle, "hold": hold, "stagger": stage3c.FLAT_STAGGER,
                                               "condition": stage3c.FLAT_LEVELS.index(lv) * len(stage3c.FLAT_STEPS) + list(stage3c.FLAT_STEPS).index(st)})
                        for c in champions for lv, st in flat_cases]
        results = {r["label"]: r for r in pool.map(test_job, jobs)}
        ceiling = ceiling_future.result()
        goggles = [f.result() for f in goggle_futures]
        flats = [f.result() for f in flat_futures]
    out = out_root / "test"
    rows = [{"label": label, "start": int(r["start"][i]), "fitness": r["fitness"][i], "survived": r["survived"][i], "mean_beat": r["mean_beat"][i],
             "light_soaked": r["light_soaked"][i], "night_beat": r["night_beat"][i], "reach_tick": int(r["reach_tick"][i])}
            for label, r in results.items() for i in range(n)]
    rows += [{"label": "ceiling", "start": i + 1, "fitness": float(ceiling["fitness"][i]), "survived": bool(ceiling["survived"][i]), "mean_beat": 0.0,
              "light_soaked": math.nan, "night_beat": math.nan, "reach_tick": -1} for i in range(n)]
    write_csv(out / "per_start.csv", ("label", "start", "fitness", "survived", "mean_beat", "light_soaked", "night_beat", "reach_tick"), rows)
    bar = results["B8"]["fitness"]
    headroom = float(ceiling["fitness"].mean() - bar.mean())
    key = 0

    def ci(diff: np.ndarray) -> Tuple[float, float, float]:
        nonlocal key
        key += 1
        return bootstrap_ci(diff, key, resamples, seed=BOOTSTRAP_SEED)

    comparisons: List[Dict[str, Any]] = []
    q3: Dict[str, Any] = {}
    flat_by = {(f["run"], f["level"], f["step"]): stage3c.flat_reading(f["window"], 5000 + i, resamples) for i, f in enumerate(flats)}
    for index, c in enumerate(champions):
        f = results[c["run"]]["fitness"]
        d, lo, hi = ci(f - bar)
        comparisons.append({"run": c["run"], "phase": c["phase"], "mode": c["mode"], "compared": "champion - B8", "mean": d, "low": lo, "high": hi,
                            "criterion": 0.0, "verdict": lo > 0.0, "share_of_headroom": d / headroom if headroom > 0 else None})
        for label in [f"-{rm}" for rm in REMOVALS] + [f"hold {p}" for p in PATHWAYS]:
            d, lo, hi = ci(f - results[f"{c['run']} {label}"]["fitness"])
            comparisons.append({"run": c["run"], "phase": c["phase"], "mode": c["mode"], "compared": f"intact - ({label.lstrip('-')})", "mean": d,
                                "low": lo, "high": hi, "criterion": DELTA, "verdict": lo > DELTA, "share_of_headroom": None})
        mine = {g["world"]: g for g in goggles if g["run"] == c["run"]}
        q3[c["run"]] = read_q3(c["run"], {w: mine[w]["fitness"] for w in GOGGLES}, {w: (mine[w]["cos_sum"], mine[w]["count"]) for w in GOGGLES},
                               flat_by, 10_000 + 10 * index, resamples)  # Q3's bootstrap keys, apart from the comparisons'
    write_csv(out / "comparisons.csv", ("run", "phase", "mode", "compared", "mean", "low", "high", "criterion", "verdict", "share_of_headroom"), comparisons)
    flat_rows = [{"run": r, "level": lv, "step": st, **reading} for (r, lv, st), reading in flat_by.items()]
    write_csv(out / "flat_pool.csv", ("run", "level", "step", "before", "early", "late", "d_early", "d_late", "T", "T_low", "T_high"), flat_rows)
    verdicts: Dict[str, Any] = {}
    for mode in MODES:
        mine = [x for x in comparisons if x["mode"] == mode and x["phase"] == "confirm"]
        runs = sorted({x["run"] for x in mine})
        if not runs:
            continue
        need = len(runs) // 2 + 1
        count = lambda name: sum(bool(x["verdict"]) for x in mine if x["compared"] == name)  # noqa: E731
        breaks = {name: count(name) for name in sorted({x["compared"] for x in mine if x["compared"].startswith("intact")})}
        verdicts[mode] = {"champions": len(runs), "beat_the_bar": count("champion - B8"), "Q1": count("champion - B8") >= need,
                          "Q2_breaks": breaks, "Q2_needed": {name: v >= need for name, v in breaks.items()},
                          "Q3_read_direction": sum(q3[r]["reads_direction"] for r in runs), "Q3_compare_over_time": sum(q3[r]["compares_over_time"] for r in runs)}
    rows_summary = {label: summarise(r) for label, r in results.items()}
    rows_summary["ceiling"] = {"fitness": float(ceiling["fitness"].mean()), "survival": float(ceiling["survived"].mean())}
    predictions = score_predictions(out_root, champions, verdicts, comparisons, q3, rows_summary)
    summary = {"delta": DELTA, "n_starts": n, "choices": choices, "headroom": headroom, "verdicts": verdicts, "q3": q3, "rows": rows_summary,
               "champions": [{k: v for k, v in c.items() if k != "genome"} for c in champions],
               "means": {r_: {"living_ticks": m["living_ticks"], **m["means"]} for r_, m in means.items()}, "predictions": predictions, "quick": quick}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=_jsonable) + "\n")
    manifest = build_manifest(protocol="stage4b/test", settings={**cfg.as_dict(), "delta": DELTA, "n_starts": n, "resamples": resamples,
                                                                 "choices": choices, "flat": {"replicates": reps, "settle": settle, "hold": hold}, "quick": quick},
                              seeds=[TEST_SEED, VALIDATION_SEED, BOOTSTRAP_SEED])
    finish_manifest(manifest, wall_seconds=time.time() - t0, jobs=len(jobs), workers=workers)
    write_manifest(out / "manifest.json", manifest)
    print(f"B8 {bar.mean():.3f}, the ceiling {ceiling['fitness'].mean():.3f}: the headroom {headroom:.3f}", flush=True)
    for c in champions:
        x = next(x for x in comparisons if x["run"] == c["run"] and x["compared"] == "champion - B8")
        print(f"{c['phase']:8s} {c['run']:16s} {results[c['run']]['fitness'].mean():.3f}: {x['mean']:+.3f} [{x['low']:+.3f}, {x['high']:+.3f}] "
              f"against B8; reads the direction {q3[c['run']]['reads_direction']}, compares over time {q3[c['run']]['compares_over_time']}", flush=True)
    for mode, v in verdicts.items():
        print(f"{mode}: beat the bar {v['beat_the_bar']}/{v['champions']} (Q1 {v['Q1']}); needed: "
              f"{', '.join(k for k, need in v['Q2_needed'].items() if need) or 'none'}", flush=True)
    for p in predictions:
        print(f"prediction {p['number']}: {'✓' if p['holds'] else '✗'} {p['text']}", flush=True)
    return summary


def score_predictions(out_root: Path, champions: Sequence[Mapping[str, Any]], verdicts: Mapping[str, Any], comparisons: Sequence[Mapping[str, Any]],
                      q3: Mapping[str, Any], rows: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """§8's predictions, on the reported numbers; the pilots' validation survival from their champion.json."""
    pilots = [c for c in champions if c["phase"] == "pilot"]
    pilot_survival = {c["run"]: json.loads((out_root / "pilot" / c["run"] / "champion.json").read_text()).get("validation_survival") for c in pilots}
    confirm = [c for c in champions if c["phase"] == "confirm"]
    b0 = rows["B0"]["fitness"]
    working = [c["run"] for c in confirm if rows[c["run"]]["fitness"] > b0]
    out = [
        (1, "the pilot climbs in at least one mode under the path", any(v is not None and v >= 0.5 for v in pilot_survival.values()), pilot_survival),
        (2, "Q1 fails in both modes: no champion beats B8", not any(v["Q1"] for v in verdicts.values()) and not any(
            x["verdict"] for x in comparisons if x["compared"] == "champion - B8" and x["phase"] == "confirm"), {m: v["beat_the_bar"] for m, v in verdicts.items()}),
        (3, "the best champion scores below B8", all(rows[c["run"]]["fitness"] < rows["B8"]["fitness"] for c in confirm),
         {c["run"]: rows[c["run"]]["fitness"] for c in confirm}),
        (4, "the champions that work read the direction, and none compares over time",
         bool(working) and all(q3[r]["reads_direction"] for r in working) and not any(q3[c["run"]]["compares_over_time"] for c in confirm),
         {r: {"reads": q3[r]["reads_direction"], "compares": q3[r]["compares_over_time"]} for r in (c["run"] for c in confirm)}),
        (5, "the core and the ring's links are needed in both modes",
         all(v["Q2_needed"].get("intact - (core)") and v["Q2_needed"].get("intact - (ring_links)") for v in verdicts.values()) and len(verdicts) == 2,
         {m: {k: v["Q2_needed"].get(k) for k in ("intact - (core)", "intact - (ring_links)")} for m, v in verdicts.items()}),
    ]
    return [{"number": n_, "text": text, "holds": bool(holds), "values": values} for n_, text, holds, values in out]


def main(argv: Optional[Sequence[str]] = None) -> Any:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--phase", required=True, choices=["pilot", "confirm", "test"])
    parser.add_argument("--mode", choices=list(MODES))
    parser.add_argument("--replicate", type=int, default=1)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--stop-after", type=int, default=None)
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    if args.phase == "test":
        return test_phase(args.out, args.workers, args.quick)
    if args.mode is None:
        raise SystemExit("a run needs --mode")
    return run_phase(args.phase, args.mode, args.replicate, args.out, args.workers, args.quick, args.stop_after)


if __name__ == "__main__":
    main(sys.argv[1:])
