"""Stage 3c (docs/prereg/stage3c.md): the goggles and the flat pool, or how a cell with no front finds the light.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage3c --workers 16
    .venv/bin/python -m experiments.stage3c --quick --out /tmp/s3c --workers 2   # the smoke test: not a result

Part 1, the goggles (§3.1): the champion (uniform 2203), the other working champion (fourier1 3202), B5, B6 and B7
in stage 3's translucent pool with the senses as they are (G1), the direction removed (G0), mirrored (G-1), magnified
(G10) and with the sensor noise off (Gq); B0 in G1. Part 2, the lesions (§4): the champion with no body spin (L1),
its ring made symmetric (L2), and both (L3), in G1. Parts 1 and 2 run on starts 1-100 at seed 14 with shared noise,
each run's movement read by stage 3c's probe's observer. Part 3, the flat pool (§3.2): the five cells held in place
in even light, settled 2 hours at 0.3 or 1, then stepped up (x1.25) or down (x0.8) for 30 minutes; 16 replicates each,
the step staggered 7 s per replicate, each replicate's sensor noise from stream ``tether`` (the same for every cell).
Reads the criteria C1-C5 (§7) and scores the predictions (§8); writes ``docs/data/stage3c/test/``.
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

from experiments import stage3c_probe as probe
from experiments.cave import RUN_COLUMNS, run_summary
from experiments.stage3 import configure, runwait
from protocell.cell import decode, layout
from protocell.config import Config
from protocell.evolve import NOISE_CELL_ID
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.rng import stream
from protocell.sim import CellNoise, build_controller, simulate
from protocell.tables import write_csv
from protocell.world import Starts, node_angles, sample_starts

SEED = 14  # the starts, the noise, B7's directions and the flat pool's noise: fresh
BOOTSTRAP_SEED = 15
RESAMPLES = 10_000
WORLDS: Dict[str, Dict[str, float]] = {"G1": {}, "G0": {"sense_contrast": 0.0}, "G-1": {"sense_contrast": -1.0},
                                       "G10": {"sense_contrast": 10.0}, "Gq": {"sensor_noise_sd": 0.0}}
CELLS = ("U2203", "F3202", "B5", "B6", "B7")
LESIONS = ("L1", "L2", "L3")
CHAMPION = "U2203"
CYCLE, RUN, STILL_ABOVE = 100, 36, 4.5  # B6 and B7 (§5)
B5_TAU = 30.0
ONSET_LIGHT = (0.3, 3.0)  # the onset bias counts the runs that begin in this light (§7)
FLAT_LEVELS = (0.3, 1.0)
FLAT_STEPS = {"up": 1.25, "down": 0.8}
FLAT_REPLICATES, FLAT_SETTLE, FLAT_HOLD, FLAT_STAGGER = 16, 7200, 1800, 7
BEFORE, EARLY, LATE = 600, 120, (1200, 1800)  # the flat pool's windows, ticks before and after the step
C5_MIN = 1.0  # R/s
DEFAULT_OUT = Path("docs/data/stage3c/test")


def onset_bands() -> List[int]:
    lo, hi = ONSET_LIGHT
    return [b for b in range(len(probe.BANDS) - 1) if probe.BANDS[b] >= lo and probe.BANDS[b + 1] <= hi]


def world_cfg(base: Config, world: str) -> Config:
    return base.but(**WORLDS[world]) if WORLDS[world] else base


def lesioned(cfg: Config, which: str) -> np.ndarray:
    """The champion's genome with one part changed (§4): L1 the cilium angle 0; L2 both neighbour links at their mean;
    L3 both."""
    mode, path = probe.CHAMPIONS[CHAMPION]
    g = np.load(path).reshape(-1).copy()
    lay = layout(cfg, mode)
    r0 = lay.ring.start  # ring_self, ring_from_cw, ring_from_ccw, ...
    if which in ("L1", "L3"):
        g[lay.alpha.start] = 0.0
    if which in ("L2", "L3"):
        mean = 0.5 * (g[r0 + 1] + g[r0 + 2])
        g[r0 + 1] = g[r0 + 2] = mean
    if which not in LESIONS:
        raise ValueError(which)
    return g


def readrun(cfg: Config, aim: str) -> Dict[str, Any]:
    return {"controller": "readrun", "aim": aim, "cycle": CYCLE, "run": RUN, "rest_below": cfg.rest_below, "still_above": STILL_ABOVE}


def cell_spec(cfg: Config, cell: str, n: int) -> Tuple[Dict[str, Any], np.ndarray]:
    """A cell's controller spec for n rows and its cilium angle per row."""
    if cell == "B0":
        return {"controller": "still"}, np.zeros(n)
    if cell == "B5":
        return runwait(cfg, B5_TAU), np.zeros(n)
    if cell in ("B6", "B7"):
        return readrun(cfg, "read" if cell == "B6" else "random"), np.zeros(n)
    if cell in probe.CHAMPIONS:
        mode, path = probe.CHAMPIONS[cell]
        genome = np.load(path).reshape(-1)
    elif cell in LESIONS:
        mode, genome = probe.CHAMPIONS[CHAMPION][0], lesioned(cfg, cell)
    else:
        raise ValueError(f"unknown cell {cell!r}")
    genomes = np.repeat(genome[None], n, axis=0)
    return {"controller": "network", "mode": mode, "genomes": genomes}, decode(cfg, mode, genomes[:1]).alpha.repeat(n)


def pool_job(job: Mapping[str, Any]) -> Dict[str, Any]:
    """One cell in one world on a chunk of starts, its movement read as in the probe."""
    cfg: Config = job["cfg"]
    starts: Starts = job["starts"]
    spec, alpha = cell_spec(cfg, job["cell"], len(starts))
    obs = probe.Movement(cfg, starts, alpha)
    result = simulate(cfg, starts, spec, seed=SEED, cell_ids=[NOISE_CELL_ID] * len(starts), observe=obs)
    obs.runs.finish()
    first = job["first"]
    return {"cell": job["cell"], "world": job["world"], "first": first, "result": result,
            "rows": result.rows(starts, cell_name=job["cell"], world=job["world"]),
            "ticks": obs.ticks, "moved": obs.moved, "toward": obs.toward, "spin": obs.spin, "creep": obs.creep, "pairs": obs.pairs,
            "onsets": [(c + first, b, a) for c, b, a in obs.runs.onsets], "durations": [(c + first, b, d) for c, b, d in obs.runs.durations]}


def flat_job(job: Mapping[str, Any]) -> Dict[str, Any]:
    """Part 3 for one cell, level and step: the replicates held in place in even light, each stepped at its own time;
    the pull, v_max (pi/N)|m1|, each tick from 10 minutes before its step to 30 after."""
    cfg: Config = job["cfg"]
    reps, settle, hold, stagger = job["replicates"], job["settle"], job["hold"], job["stagger"]
    keys = [(r, job["condition"]) for r in range(reps)]
    spec = job["spec"] if job.get("spec") is not None else cell_spec(cfg, job["cell"], reps)[0]  # a ready spec: stage 4b's champions
    ctl = build_controller(cfg, spec, reps, SEED, keys)
    noise = CellNoise(SEED, probe.STREAM_TETHER, keys, (cfg.n_wall,), "normal", cfg.sensor_noise_sd)
    step_at = settle + stagger * np.arange(reps)
    ticks = settle + stagger * (reps - 1) + hold
    theta = node_angles(cfg)
    lo, hi = job["level"], job["level"] * FLAT_STEPS[job["step"]]
    window = np.zeros((reps, BEFORE + hold))
    rows = np.arange(reps)
    for t in range(ticks):
        level = np.where(t >= step_at, hi, lo)
        beats = ctl.beats(np.repeat(level[:, None], cfg.n_wall, axis=1) + noise.at(t), t)
        pull = cfg.v_max * (math.pi / cfg.n_wall) * np.abs(probe.first_mode(beats, theta))
        k = t - step_at + BEFORE
        keep = (k >= 0) & (k < BEFORE + hold)
        window[rows[keep], k[keep]] = pull[keep]
    return {"cell": job["cell"], "level": job["level"], "step": job["step"], "window": window}


def flat_reading(window: np.ndarray, key: int, resamples: int) -> Dict[str, Any]:
    """D_early, D_late and T from the replicates' means, with T's 95% interval over resampled replicates (§7 and the
    pre-run clarification 1)."""
    before = window[:, :BEFORE].mean(axis=1)
    early = window[:, BEFORE:BEFORE + EARLY].mean(axis=1)
    late = window[:, BEFORE + LATE[0]:BEFORE + LATE[1]].mean(axis=1)
    d_early, d_late = early - before, late - before

    def t_of(idx: np.ndarray) -> np.ndarray:
        return np.abs(d_early[idx].mean(axis=-1)) - np.abs(d_late[idx].mean(axis=-1))

    n = window.shape[0]
    idx = stream(BOOTSTRAP_SEED, "bootstrap", (key,)).integers(0, n, size=(resamples, n))
    ts = t_of(idx)
    return {"before": float(before.mean()), "early": float(early.mean()), "late": float(late.mean()), "d_early": float(d_early.mean()),
            "d_late": float(d_late.mean()), "T": float(t_of(np.arange(n))), "T_low": float(np.percentile(ts, 2.5)),
            "T_high": float(np.percentile(ts, 97.5))}


def ci(diff: np.ndarray, key: int, resamples: int) -> Tuple[float, float, float]:
    """The mean and its 95% percentile bootstrap interval over starts (stream ``bootstrap`` at seed 15)."""
    idx = stream(BOOTSTRAP_SEED, "bootstrap", (key,)).integers(0, diff.shape[0], size=(resamples, diff.shape[0]))
    means = diff[idx].mean(axis=1)
    return float(diff.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def ratio_ci(s: Sequence[np.ndarray], n: Sequence[np.ndarray], key: int, resamples: int) -> List[Dict[str, float]]:
    """Pooled means sum(s)/sum(n) over starts for one or more paired arrays (per-start sums of cosines and counts), with
    95% intervals from one resampling of starts, and the interval of the last less the first when there are two."""
    m = s[0].shape[0]
    idx = stream(BOOTSTRAP_SEED, "bootstrap", (key,)).integers(0, m, size=(resamples, m))
    out, draws = [], []
    for si, ni in zip(s, n):
        num, den = si[idx].sum(axis=1), ni[idx].sum(axis=1)
        r = np.full(resamples, math.nan)
        np.divide(num, den, out=r, where=den > 0)
        draws.append(r)
        total = float(ni.sum())
        point = float(si.sum() / total) if total > 0 else math.nan
        fin = r[np.isfinite(r)]
        out.append({"mean": point, "runs": int(total), "low": float(np.percentile(fin, 2.5)) if fin.size else math.nan,
                    "high": float(np.percentile(fin, 97.5)) if fin.size else math.nan})
    if len(s) == 2:
        d = draws[1] - draws[0]
        fin = d[np.isfinite(d)]
        out.append({"mean": out[1]["mean"] - out[0]["mean"], "low": float(np.percentile(fin, 2.5)) if fin.size else math.nan,
                    "high": float(np.percentile(fin, 97.5)) if fin.size else math.nan})
    return out


def run(out: Path, workers: int, quick: bool) -> Dict[str, Any]:
    base = configure(quick)
    n_starts = 8 if quick else 100
    resamples = 200 if quick else RESAMPLES
    reps, settle, hold = (4, 700, 1800) if quick else (FLAT_REPLICATES, FLAT_SETTLE, FLAT_HOLD)
    out.mkdir(parents=True, exist_ok=True)
    runs = [(c, w) for c in CELLS for w in WORLDS] + [("B0", "G1")] + [(lesion, "G1") for lesion in LESIONS]
    settings = {**base.as_dict(), "seed": SEED, "bootstrap_seed": BOOTSTRAP_SEED, "resamples": resamples, "n_starts": n_starts,
                "worlds": WORLDS, "cells": CELLS, "lesions": LESIONS, "b6_b7": {"cycle": CYCLE, "run": RUN, "still_above": STILL_ABOVE},
                "b5_tau": B5_TAU, "onset_light": ONSET_LIGHT, "flat": {"levels": FLAT_LEVELS, "steps": FLAT_STEPS, "replicates": reps,
                "settle": settle, "hold": hold, "stagger": FLAT_STAGGER, "before": BEFORE, "early": EARLY, "late": LATE}, "c5_min": C5_MIN,
                "quick": quick}
    manifest = build_manifest(protocol="stage3c", settings=settings, seeds=[SEED, BOOTSTRAP_SEED], extra={"out": str(out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:7.1f}s {msg}", flush=True)

    starts = sample_starts(base, "cave", n_starts, SEED)
    chunks = [(lo, starts.take(range(lo, min(lo + probe.CHUNK, n_starts)))) for lo in range(0, n_starts, probe.CHUNK)]
    flat_cases = [(c, lv, st) for c in CELLS for lv in FLAT_LEVELS for st in FLAT_STEPS]
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        flat_futures = [pool.submit(flat_job, {"cfg": base, "cell": c, "level": lv, "step": st, "replicates": reps, "settle": settle, "hold": hold,
                                               "stagger": FLAT_STAGGER, "condition": FLAT_LEVELS.index(lv) * len(FLAT_STEPS) + list(FLAT_STEPS).index(st)})
                        for c, lv, st in flat_cases]
        pool_futures = [pool.submit(pool_job, {"cfg": world_cfg(base, w), "cell": c, "world": w, "starts": st, "first": lo})
                        for c, w in runs for lo, st in chunks]
        parts = [f.result() for f in pool_futures]
        log("parts 1 and 2: the goggles and the lesions done")
        flats = [f.result() for f in flat_futures]
        log("part 3: the flat pool done")

    bands = onset_bands()
    fitness: Dict[Tuple[str, str], np.ndarray] = {}
    cos_sum: Dict[Tuple[str, str], np.ndarray] = {}
    count: Dict[Tuple[str, str], np.ndarray] = {}
    per_start, budget, onset_rows, overall, summaries = [], [], [], {}, {}
    for c, w in runs:
        mine = sorted((p for p in parts if p["cell"] == c and p["world"] == w), key=lambda p: p["first"])
        per_start += [row for p in mine for row in p["rows"]]
        fitness[(c, w)] = np.concatenate([p["result"].fitness for p in mine])
        s, k = np.zeros(n_starts), np.zeros(n_starts)
        for p in mine:
            for start, band, angle in p["onsets"]:
                if band in bands:
                    s[start] += math.cos(angle)
                    k[start] += 1
        cos_sum[(c, w)], count[(c, w)] = s, k
        alpha = float(cell_spec(base, c, 1)[1][0])
        b, r, o = probe.movement_tables(c, mine, alpha)
        budget += [{**row, "world": w} for row in b]
        onset_rows += [{**row, "world": w} for row in r]
        survived = np.concatenate([p["result"].survived for p in mine])
        overall[f"{c} {w}"] = {**o, "mean_fitness": float(fitness[(c, w)].mean()), "survival": float(survived.mean())}
        summaries[f"{c} {w}"] = run_summary(probe._merge(mine))
    write_csv(out / "per_start.csv", ("cell_name", "world", *RUN_COLUMNS), per_start)
    write_csv(out / "budget.csv", ("cell", "world", "band", "share_of_life", *probe.STATES, "speed", "toward_mouth"), budget)
    write_csv(out / "runs.csv", ("cell", "world", "band", "runs", "onset_cos_mean", "onset_cos_se", "toward_share", "median_duration",
                                 "mean_duration"), onset_rows)

    key = 0
    comparisons: List[Dict[str, Any]] = []

    def compare(name: str, a: Tuple[str, str], b: Tuple[str, str]) -> Dict[str, Any]:
        nonlocal key
        key += 1
        mean, low, high = ci(fitness[a] - fitness[b], key, resamples)
        row = {"name": name, "a": f"{a[0]} {a[1]}", "b": f"{b[0]} {b[1]}", "mean": mean, "low": low, "high": high}
        comparisons.append(row)
        return row

    change = {(c, w): compare(f"{c}: {w} - G1", (c, w), (c, "G1")) for c in CELLS for w in WORLDS if w != "G1"}
    lesion = {lz: compare(f"{CHAMPION}: {lz} - intact", (lz, "G1"), (CHAMPION, "G1")) for lz in LESIONS}
    b6_vs_champion = compare("B6 - U2203 in G1", ("B6", "G1"), (CHAMPION, "G1"))
    b5_vs_b6 = compare("B5 - B6 in G1", ("B5", "G1"), ("B6", "G1"))
    b7_vs_b0 = compare("B7 - B0 in G1", ("B7", "G1"), ("B0", "G1"))
    write_csv(out / "comparisons.csv", ("name", "a", "b", "mean", "low", "high"), comparisons)

    bias: Dict[Tuple[str, str], Dict[str, float]] = {}
    bias_rows = []
    for c in CELLS + ("B0",) + LESIONS:
        for w in WORLDS:
            if (c, w) not in fitness:
                continue
            key += 1
            bias[(c, w)] = ratio_ci([cos_sum[(c, w)]], [count[(c, w)]], key, resamples)[0]
            bias_rows.append({"cell": c, "world": w, **bias[(c, w)]})
    g10_gain: Dict[str, Dict[str, float]] = {}
    for c in CELLS:
        key += 1
        g10_gain[c] = ratio_ci([cos_sum[(c, "G1")], cos_sum[(c, "G10")]], [count[(c, "G1")], count[(c, "G10")]], key, resamples)[2]
        bias_rows.append({"cell": c, "world": "G10 - G1", "runs": None, **g10_gain[c]})
    write_csv(out / "onset_bias.csv", ("cell", "world", "runs", "mean", "low", "high"), bias_rows)

    flat: Dict[Tuple[str, float, str], Dict[str, Any]] = {}
    flat_rows, curve_rows = [], []
    for f in flats:
        key += 1
        reading = flat_reading(f["window"], key, resamples)
        flat[(f["cell"], f["level"], f["step"])] = reading
        flat_rows.append({"cell": f["cell"], "level": f["level"], "step": f["step"], "replicates": f["window"].shape[0], **reading})
        mean_pull = f["window"].mean(axis=0)
        for minute in range(-(BEFORE // 60), hold // 60):
            lo = BEFORE + 60 * minute
            curve_rows.append({"cell": f["cell"], "level": f["level"], "step": f["step"], "minute": minute, "pull": float(mean_pull[lo:lo + 60].mean())})
    write_csv(out / "flat_pool.csv", ("cell", "level", "step", "replicates", "before", "early", "late", "d_early", "d_late", "T", "T_low",
                                      "T_high"), flat_rows)
    write_csv(out / "flat_curves.csv", ("cell", "level", "step", "minute", "pull"), curve_rows)

    criteria, verdicts = read_criteria(change, lesion, bias, g10_gain, flat)
    predictions = score_predictions(change, lesion, bias, flat, overall, b6_vs_champion, b5_vs_b6, b7_vs_b0)
    for line in describe(criteria, verdicts):
        log(line)
    for p in predictions:
        log(f"prediction {p['number']}: {'✓' if p['holds'] else '✗'} {p['text']}")
    fitness_table = {f"{c} {w}": {"mean_fitness": float(fitness[(c, w)].mean()), "survival": overall[f"{c} {w}"]["survival"]} for c, w in runs}
    summary = {"criteria": criteria, "verdicts": verdicts, "predictions": predictions, "fitness": fitness_table,
               "onset_bias": {f"{c} {w}": v for (c, w), v in bias.items()}, "onset_bias_g10_gain": g10_gain,
               "flat_pool": {f"{c} {lv:g} {st}": v for (c, lv, st), v in flat.items()}, "movement": overall, "run_summaries": summaries,
               "comparisons": comparisons, "quick": quick}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=probe._json) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0, workers=workers)
    write_manifest(out / "manifest.json", manifest)
    log(f"done, written to {out}")
    return summary


def reads_direction(change: Mapping, bias: Mapping, cell: str) -> Dict[str, Any]:
    """C1 for one cell: its onset bias above 0 in G1 (interval), its mean within 0.1 of 0 in G0, and its fitness lower
    in G0 than in G1 (interval of the change below 0)."""
    g1, g0, drop = bias[(cell, "G1")], bias[(cell, "G0")], change[(cell, "G0")]
    holds = bool(g1["low"] > 0.0 and abs(g0["mean"]) <= 0.1 and drop["high"] < 0.0)
    return {"holds": holds, "bias_G1": g1, "bias_G0": g0, "fitness_G0_minus_G1": drop}


def follows_reading(bias: Mapping, g10_gain: Mapping, cell: str) -> Dict[str, Any]:
    """C2 for one cell: its onset bias below 0 in G-1 (interval) and higher in G10 than in G1 (interval)."""
    mirrored, gain = bias[(cell, "G-1")], g10_gain[cell]
    return {"holds": bool(mirrored["high"] < 0.0 and gain["low"] > 0.0), "bias_G-1": mirrored, "bias_G10_minus_G1": gain}


def compares_over_time(flat: Mapping, cell: str) -> Dict[str, Any]:
    """C5 for one cell: at some level, T above C5_MIN with its interval above 0 after the step up and after the step
    down."""
    by_level = {}
    for lv in FLAT_LEVELS:
        cases = [flat[(cell, lv, st)] for st in FLAT_STEPS]
        by_level[f"{lv:g}"] = bool(all(c["T"] > C5_MIN and c["T_low"] > 0.0 for c in cases))
    return {"any_level": any(by_level.values()), "every_level": all(by_level.values()), "by_level": by_level}


def read_criteria(change: Mapping, lesion: Mapping, bias: Mapping, g10_gain: Mapping, flat: Mapping) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    c1 = {c: reads_direction(change, bias, c) for c in (CHAMPION, "B6")}
    c2 = {c: follows_reading(bias, g10_gain, c) for c in (CHAMPION, "B6")}
    unchanged = {c: {w: change[(c, w)]["mean"] for w in ("G0", "G-1", "G10")} for c in ("B5", "B7")}
    c3 = {"B6_reads_and_follows": bool(c1["B6"]["holds"] and c2["B6"]["holds"]),
          "B5_B7_unchanged": bool(all(abs(v) < 0.01 for d in unchanged.values() for v in d.values())), "changes": unchanged}
    c3["holds"] = bool(c3["B6_reads_and_follows"] and c3["B5_B7_unchanged"])
    drops = {lz: {"mean": -lesion[lz]["mean"], "low": -lesion[lz]["high"], "high": -lesion[lz]["low"]} for lz in LESIONS}
    c4 = {"drops": drops, "holds": bool(drops["L1"]["low"] > 0.0 and drops["L2"]["low"] > 0.0 and not drops["L3"]["low"] > 0.0)}
    c5 = {c: compares_over_time(flat, c) for c in CELLS}
    c5_control = c5["B5"]["every_level"]
    criteria = {"C1": c1, "C2": c2, "C3": c3, "C4": c4, "C5": c5}
    verdicts = {
        "controls_work": bool(c3["holds"] and c5_control),
        "H_reading_confirmed": bool(c1[CHAMPION]["holds"] and c2[CHAMPION]["holds"] and c3["holds"]),
        "H_course_confirmed": c4["holds"],
        "flat_pool_works": c5_control,
        "champion_compares_over_time": c5[CHAMPION]["any_level"],
        "F3202_compares_over_time": c5["F3202"]["any_level"],
    }
    return criteria, verdicts


def _iv(d: Mapping[str, Any]) -> str:
    return f"{d['mean']:+.3f} [{d['low']:+.3f}, {d['high']:+.3f}]"


def describe(criteria: Mapping[str, Any], verdicts: Mapping[str, Any]) -> List[str]:
    """One line per criterion and cell, for the log."""
    lines = []
    for c, v in criteria["C1"].items():
        lines.append(f"C1 {c}: {'holds' if v['holds'] else 'fails'}; onset bias G1 {_iv(v['bias_G1'])}, G0 {v['bias_G0']['mean']:+.3f}; "
                     f"fitness G0 - G1 {_iv(v['fitness_G0_minus_G1'])}")
    for c, v in criteria["C2"].items():
        lines.append(f"C2 {c}: {'holds' if v['holds'] else 'fails'}; onset bias G-1 {_iv(v['bias_G-1'])}; G10 - G1 {_iv(v['bias_G10_minus_G1'])}")
    c3 = criteria["C3"]
    lines.append(f"C3: {'holds' if c3['holds'] else 'fails'}; B6 reads and follows {c3['B6_reads_and_follows']}; B5 and B7 unchanged "
                 f"{c3['B5_B7_unchanged']} {c3['changes']}")
    c4 = criteria["C4"]
    lines.append(f"C4: {'holds' if c4['holds'] else 'fails'}; drops " + "; ".join(f"{k} {_iv(d)}" for k, d in c4["drops"].items()))
    for c, v in criteria["C5"].items():
        lines.append(f"C5 {c}: compares over time at {[lv for lv, ok in v['by_level'].items() if ok] or 'no level'}")
    lines.append("verdicts: " + ", ".join(f"{k} {v}" for k, v in verdicts.items()))
    return lines


def score_predictions(change: Mapping, lesion: Mapping, bias: Mapping, flat: Mapping, overall: Mapping, b6_vs_champion: Mapping,
                      b5_vs_b6: Mapping, b7_vs_b0: Mapping) -> List[Dict[str, Any]]:
    """§8's predictions, scored on means (the pre-run clarifications 2 and 3)."""
    ch = lambda c, w: change[(c, w)]["mean"]  # noqa: E731
    out = []

    def add(number: int, text: str, holds: bool, values: Mapping[str, Any]) -> None:
        out.append({"number": number, "text": text, "holds": bool(holds), "values": dict(values)})

    u = CHAMPION
    add(1, "G0: the champion's onset bias within 0.1 of 0 and its fitness down by more than 0.10",
        abs(bias[(u, "G0")]["mean"]) <= 0.1 and ch(u, "G0") < -0.10, {"bias": bias[(u, "G0")]["mean"], "change": ch(u, "G0")})
    add(2, "G-1: the champion's onset bias below -0.3 and its fitness down by more than 0.15",
        bias[(u, "G-1")]["mean"] < -0.3 and ch(u, "G-1") < -0.15, {"bias": bias[(u, "G-1")]["mean"], "change": ch(u, "G-1")})
    add(3, "G10: the champion's onset bias above 0.85 and its fitness up by more than 0.10",
        bias[(u, "G10")]["mean"] > 0.85 and ch(u, "G10") > 0.10, {"bias": bias[(u, "G10")]["mean"], "change": ch(u, "G10")})
    add(4, "Gq: the champion's fitness up by more than 0.15", ch(u, "Gq") > 0.15, {"change": ch(u, "Gq")})
    add(5, "B6 down by more than 0.15 in G0 and G-1, up by more than 0.15 in G10",
        ch("B6", "G0") < -0.15 and ch("B6", "G-1") < -0.15 and ch("B6", "G10") > 0.15,
        {"G0": ch("B6", "G0"), "G-1": ch("B6", "G-1"), "G10": ch("B6", "G10")})
    six = {f"{c} {w}": ch(c, w) for c in ("B5", "B7") for w in ("G0", "G-1", "G10")}
    add(6, "B5 and B7 change by less than 0.01 in G0, G-1 and G10", all(abs(v) < 0.01 for v in six.values()), six)
    seven = {w: ch("F3202", w) for w in ("G0", "G-1", "G10", "Gq")}
    add(7, "F3202 changes by less than 0.05 in each goggles world", all(abs(v) < 0.05 for v in seven.values()), seven)
    add(8, "B7 within 0.02 of B0", abs(b7_vs_b0["mean"]) <= 0.02, {"B7 - B0": b7_vs_b0["mean"]})
    turning = {lz: overall[f"{lz} G1"]["turning_during_runs"] for lz in LESIONS}
    nine = (lesion["L1"]["mean"] < 0.0 and lesion["L2"]["mean"] < 0.0 and lesion["L3"]["mean"] >= 0.0
            and turning["L1"] > 0.015 and turning["L2"] < -0.025 and abs(turning["L3"]) <= 0.010)
    add(9, "L1 and L2 lower the champion's fitness, L3 does not; L1 turns above +0.015, L2 below -0.025, L3 within 0.010 of 0",
        nine, {**{f"{lz} - intact": lesion[lz]["mean"] for lz in LESIONS}, **{f"{lz} turning": v for lz, v in turning.items()}})
    b5_t = {f"{lv:g} {st}": flat[("B5", lv, st)]["T"] for lv in FLAT_LEVELS for st in FLAT_STEPS}
    add(10, "B5's T above 2 R/s in all four cases", all(v > 2.0 for v in b5_t.values()), b5_t)
    others = {f"{c} {lv:g} {st}": flat[(c, lv, st)]["T"] for c in ("U2203", "F3202", "B6", "B7") for lv in FLAT_LEVELS for st in FLAT_STEPS}
    add(11, "the champion, F3202, B6 and B7: T below 0.5 R/s in every case", all(v < 0.5 for v in others.values()), others)
    add(12, "B6 beats the champion in G1 by more than 0.05 and falls below B5",
        b6_vs_champion["mean"] > 0.05 and b5_vs_b6["mean"] > 0.0, {"B6 - U2203": b6_vs_champion["mean"], "B5 - B6": b5_vs_b6["mean"]})
    return out


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    args = parser.parse_args(argv)
    return run(args.out, args.workers, args.quick)


if __name__ == "__main__":
    main(sys.argv[1:])
