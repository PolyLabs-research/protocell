"""Stage 5c's explaining probe (docs/decisions.md D29 C1, D30): what the search changed in design 16, and how the
champion's runs come to start aimed.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage5c_explain
    .venv/bin/python -m experiments.stage5c_explain --quick --out /tmp/s5x   # the smoke test: not a result

The subject is champion 3603, stage 5c's best, beside design 16, on 100 fresh starts at seed 35 in stage 4a's world with
stage 5's cell, with shared noise. One process. Three parts:

A. The genes. The champion is design 16 with every gene nudged about 1% of its range. For each of the seven groups of
   genes, two hybrids: design 16 given the champion's group, and the champion with design 16's group put back. The
   line through the two cells at 0.25, 0.5, 0.75 and 1.5 of the way. The other two champions, the cosines between
   the three champions' moves away from design 16, and a cell at their mean move.
B. The movement, for design 16 and the champion: by light band, the share of ticks parked, running and idle, the speed
   and the speed toward the mouth; the runs, with each onset's angle to the mouth, its length, and the idle ticks
   before it began. An onset after fewer than ``RESUME_GAP`` idle ticks is a run resumed; the others are fresh.
C. The network alone (stage 4e's probes, with noise): how much each cell runs in steady light at several levels, and
   while the light rises and falls by 0.25% a tick.

Writes docs/data/stage5c/explain/. D30 holds the plan and the predictions, written before this ran.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from experiments import stage3c, stage3c_probe, stage4e, stage5b, stage5c
from experiments import stage4_thrift as thrift
from experiments.stage1 import bootstrap_ci
from protocell.cell import decode, layout
from protocell.cmaes import normalised, to_genomes
from protocell.config import Config
from protocell.evolve import NOISE_CELL_ID
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.sim import simulate
from protocell.tables import write_csv
from protocell.world import sample_starts

SEED, BOOTSTRAP_SEED = 35, 36  # fresh
MODE = stage5c.MODE
SUBJECT = 3603
CHAMPIONS = (3601, 3602, 3603)
LINE = (0.25, 0.5, 0.75, 1.5)
RESUME_GAP = 10  # idle ticks: an onset after fewer is a run resumed
STARTS, RESAMPLES = 100, 10_000
HOLD_LEVELS = (0.0, 0.03, 0.1, 1.0, 5.0)
SLOPE_LEVELS, SLOPE = (0.05, 1.0), 0.0025
HOLD_TICKS, SLOPE_TICKS, SLOPE_BEFORE = 6000, 900, 300
DEFAULT_OUT = Path("docs/data/stage5c/explain")
CELL_COLUMNS = ("cell", "fitness", "survival", "light_soaked", "mean_beat", "less_design16", "low", "high", "share_of_gain")


class GapTracker(stage3c_probe.RunTracker):
    """Stage 3c's runs, each also with the idle ticks before it began."""

    def __init__(self, population: int) -> None:
        super().__init__(population)
        self.idle = np.full(population, 10 ** 9, dtype=np.int64)  # ticks since the cell last ran; a first run is fresh
        self.gap = np.zeros(population, dtype=np.int64)
        self.onset_gaps: List[int] = []

    def step(self, running: np.ndarray, label: np.ndarray, direction: np.ndarray, target: np.ndarray) -> None:
        begin = running & (self.length == 0)
        self.gap[begin] = self.idle[begin]
        before = len(self.onsets)
        super().step(running, label, direction, target)
        for cell, _, _ in self.onsets[before:]:
            self.onset_gaps.append(int(self.gap[cell]))
        self.idle[running] = 0
        self.idle[~running] += 1


def champion(seed: int) -> np.ndarray:
    return np.load(Path("docs/data/stage5c/confirm") / f"{MODE}-{seed}" / "champion.npy").reshape(-1)


def cells(cfg: Config, quick: bool) -> Dict[str, np.ndarray]:
    """Every network cell of part A by name, as genomes."""
    g0 = stage4e.genome(cfg, stage4e.load(stage5c.SEED_DESIGN))
    lay = layout(cfg, MODE)
    if quick:  # the smoke test has no champions on disk: stand-ins a little way from design 16, inside the ranges
        champs = {s: to_genomes(cfg, MODE, normalised(cfg, MODE, g0)[None] + 0.004 * np.sin(np.arange(g0.size) + s)[None])[0] for s in CHAMPIONS}
    else:
        champs = {s: champion(s) for s in CHAMPIONS}
    g1 = champs[SUBJECT]
    out = {"design16": g0, **{f"champion{s}": g for s, g in champs.items()}}
    for group in stage5c.GENE_GROUPS:
        sl = getattr(lay, group)
        give, take = g0.copy(), g1.copy()
        give[sl], take[sl] = g1[sl], g0[sl]
        out[f"give {group}"], out[f"take {group}"] = give, take
    u0 = normalised(cfg, MODE, g0)
    moves = {s: displacement(cfg, g0, g) for s, g in champs.items()}
    for t in LINE:
        out[f"line {t:g}"] = to_genomes(cfg, MODE, (u0 + t * moves[SUBJECT])[None])[0]
    out["consensus"] = to_genomes(cfg, MODE, (u0 + np.mean([moves[s] for s in CHAMPIONS], axis=0))[None])[0]
    return out


def displacement(cfg: Config, g0: np.ndarray, g: np.ndarray) -> np.ndarray:
    """A cell's move away from design 16 in shares of each gene's range, the cilium angle the short way round."""
    d = normalised(cfg, MODE, g) - normalised(cfg, MODE, g0)
    a = layout(cfg, MODE).alpha.start
    d[a] = (d[a] + 0.5) % 1.0 - 0.5
    return d


def run_cell(cfg: Config, starts, spec: Dict[str, Any], alpha: Optional[float]) -> Dict[str, Any]:
    n = len(starts)
    obs = None
    if alpha is not None:
        obs = stage3c_probe.Movement(cfg, starts, np.full(n, alpha))
        obs.runs = GapTracker(n)
    r = simulate(cfg, starts, spec, seed=SEED, cell_ids=[NOISE_CELL_ID] * n, observe=obs)
    out = {"fitness": np.asarray(r.fitness, dtype=float), "survived": np.asarray(r.survived, dtype=float),
           "light_soaked": np.asarray(r.light_soaked, dtype=float), "mean_beat": np.asarray(r.mean_beat, dtype=float)}
    if obs is not None:
        obs.runs.finish()
        out["movement"] = obs
    return out


def movement_rows(cell: str, obs: Any) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """A cell's budget by light band, and its runs by band and by kind (fresh, resumed)."""
    bands = stage3c_probe.BANDS
    budget, runs = [], []
    living = float(obs.ticks.sum())
    gaps = np.array(obs.runs.onset_gaps, dtype=np.int64)
    labels = np.array([lab for _, lab, _ in obs.runs.onsets], dtype=np.int64)
    cos = np.array([math.cos(a) for _, _, a in obs.runs.onsets])
    for b in range(len(bands) - 1):
        n_b = float(obs.ticks[:, b].sum())
        row: Dict[str, Any] = {"cell": cell, "band": stage3c_probe.band_label(b), "share_of_life": n_b / living if living else math.nan}
        for k, name in enumerate(stage3c_probe.STATES):
            row[name] = float(obs.ticks[:, b, k].sum()) / n_b if n_b else math.nan
        row["speed"] = float(obs.moved[:, b].sum()) / n_b if n_b else math.nan
        row["toward_mouth"] = float(obs.toward[:, b].sum()) / n_b if n_b else math.nan
        budget.append(row)
        for kind, sel in (("all", labels == b), ("fresh", (labels == b) & (gaps >= RESUME_GAP)), ("resumed", (labels == b) & (gaps < RESUME_GAP))):
            c = cos[sel]
            runs.append({"cell": cell, "band": stage3c_probe.band_label(b), "kind": kind, "runs": int(c.size),
                         "runs_an_hour": c.size / (n_b / 3600.0) if n_b else math.nan,
                         "onset_cos_mean": float(c.mean()) if c.size else math.nan,
                         "onset_cos_se": float(c.std(ddof=1) / math.sqrt(c.size)) if c.size > 1 else math.nan})
    for row in budget:
        b = [stage3c_probe.band_label(i) for i in range(len(bands) - 1)].index(row["band"])
        dur = np.array([d for _, lab, d in obs.runs.durations if lab == b], dtype=float)
        row["mean_run_ticks"] = float(dur.mean()) if dur.size else math.nan
    return budget, runs


def onset_summary(obs: Any) -> Dict[str, Any]:
    """The onset bias in light 0.3-3 (stage 3c's bands), for all onsets, the fresh and the resumed."""
    bands = set(stage3c.onset_bands())
    gaps = np.array(obs.runs.onset_gaps, dtype=np.int64)
    keep = np.array([lab in bands for _, lab, _ in obs.runs.onsets], dtype=bool)
    cos = np.array([math.cos(a) for _, _, a in obs.runs.onsets])
    out = {}
    for kind, sel in (("all", keep), ("fresh", keep & (gaps >= RESUME_GAP)), ("resumed", keep & (gaps < RESUME_GAP))):
        c = cos[sel]
        out[kind] = {"runs": int(c.size), "bias": float(c.mean()) if c.size else math.nan,
                     "se": float(c.std(ddof=1) / math.sqrt(c.size)) if c.size > 1 else math.nan}
    return out


def open_loop(cfg: Config, genomes: Mapping[str, np.ndarray], quick: bool) -> List[Dict[str, Any]]:
    """Part C: each cell's network alone, with the sensors' noise."""
    rows = []
    hold, slope_ticks, before = (300, 200, 100) if quick else (HOLD_TICKS, SLOPE_TICKS, SLOPE_BEFORE)
    for name, g in genomes.items():
        for level in HOLD_LEVELS:
            light = stage4e.light_scenario(cfg, "hold", level, 0.0, 0.0, 0.0, hold, 0)
            r = stage4e.run_probe_genome(cfg, MODE, g, light, True)
            sl = slice(hold // 6, hold)
            rows.append({"cell": name, "scenario": "hold", "level": level, "mean_beat": float(r["mean_beat"][sl].mean()),
                         "forward": float(r["forward"][sl].mean()), "running": float(np.mean(r["forward"][sl] > 0.25))})
        for level in SLOPE_LEVELS:
            for kind in ("ramp", "fall"):
                light = stage4e.light_scenario(cfg, kind, level, SLOPE, 0.0, 0.0, slope_ticks, before)
                r = stage4e.run_probe_genome(cfg, MODE, g, light, True)
                sl = slice(before, slope_ticks)
                rows.append({"cell": name, "scenario": kind, "level": level, "mean_beat": float(r["mean_beat"][sl].mean()),
                             "forward": float(r["forward"][sl].mean()), "running": float(np.mean(r["forward"][sl] > 0.25))})
    return rows


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    cfg = stage5b.world(args.quick)
    n = 4 if args.quick else STARTS
    resamples = 200 if args.quick else RESAMPLES
    genomes = cells(cfg, args.quick)
    subject = f"champion{SUBJECT}"
    starts = sample_starts(cfg, "cave", n, SEED)
    manifest = build_manifest(protocol="stage5c/explain", settings={"world": cfg.as_dict(), "mode": MODE, "subject": subject, "starts": n,
                                                                    "resume_gap": RESUME_GAP, "line": list(LINE), "quick": args.quick},
                              seeds=[SEED, BOOTSTRAP_SEED], extra={"out": str(args.out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:7.0f}s {msg}", flush=True)

    results: Dict[str, Dict[str, Any]] = {}
    for name in ("B8", "B0"):
        results[name] = run_cell(cfg, starts, thrift.cell_spec(cfg, name, n), None)
    for name, g in genomes.items():
        spec = {"controller": "network", "mode": MODE, "genomes": np.repeat(g[None], n, axis=0)}
        alpha = float(decode(cfg, MODE, g[None]).alpha[0]) if name in ("design16", subject) else None
        results[name] = run_cell(cfg, starts, spec, alpha)
        log(f"{name}: fitness {results[name]['fitness'].mean():.3f}, survival {results[name]['survived'].mean():.0%}")
    base, top = results["design16"]["fitness"], results[subject]["fitness"]
    gain = float((top - base).mean())
    rows = []
    for key, (name, r) in enumerate(results.items()):
        d, lo, hi = bootstrap_ci(r["fitness"] - base, key + 1, resamples, seed=BOOTSTRAP_SEED)
        rows.append({"cell": name, "fitness": float(r["fitness"].mean()), "survival": float(r["survived"].mean()),
                     "light_soaked": float(r["light_soaked"].mean()), "mean_beat": float(r["mean_beat"].mean()), "less_design16": d, "low": lo,
                     "high": hi, "share_of_gain": d / gain if gain else math.nan})
    g0 = genomes["design16"]
    moves = {s: displacement(cfg, g0, genomes[f"champion{s}"]) for s in CHAMPIONS}
    cosines = {f"{a}-{b}": float(moves[a] @ moves[b] / (np.linalg.norm(moves[a]) * np.linalg.norm(moves[b])))
               for i, a in enumerate(CHAMPIONS) for b in CHAMPIONS[i + 1:]}
    budget, runs, onsets = [], [], {}
    for name in ("design16", subject):
        b, r = movement_rows(name, results[name]["movement"])
        budget += b
        runs += r
        onsets[name] = onset_summary(results[name]["movement"])
    loop = open_loop(cfg, {"design16": g0, subject: genomes[subject]}, args.quick)
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "cells.csv", CELL_COLUMNS, rows)
    write_csv(args.out / "per_start.csv", ("cell", "start", "fitness", "survived"),
              [{"cell": name, "start": int(starts.index[i]), "fitness": float(r["fitness"][i]), "survived": int(r["survived"][i])}
               for name, r in results.items() for i in range(n)])
    write_csv(args.out / "budget.csv", ("cell", "band", "share_of_life", *stage3c_probe.STATES, "speed", "toward_mouth", "mean_run_ticks"), budget)
    write_csv(args.out / "runs.csv", ("cell", "band", "kind", "runs", "runs_an_hour", "onset_cos_mean", "onset_cos_se"), runs)
    write_csv(args.out / "open_loop.csv", ("cell", "scenario", "level", "mean_beat", "forward", "running"), loop)
    by = {r["cell"]: r for r in rows}
    gives = {g: by[f"give {g}"]["share_of_gain"] for g in stage5c.GENE_GROUPS}
    dim = {name: next(b for b in budget if b["cell"] == name and b["band"] == "[0.01, 0.1)") for name in ("design16", subject)}
    fresh = onsets[subject]["fresh"]
    predictions = [
        (1, "the gain is spread: at most one group, given to design 16 alone, carries half of it or more",
         sum(v >= 0.5 for v in gives.values()) <= 1, gives),
        (2, "the line is smooth: halfway along it the cell scores at least design 16 and at most the champion plus 0.01",
         by["design16"]["fitness"] <= by["line 0.5"]["fitness"] <= by[subject]["fitness"] + 0.01,
         {k: by[k]["fitness"] for k in ("design16", "line 0.25", "line 0.5", "line 0.75", subject, "line 1.5")}),
        (3, "the champions moved the same way: each pair's cosine is above 0.17, and the cell at their mean move scores at least the worst champion",
         all(c > 0.17 for c in cosines.values()) and by["consensus"]["fitness"] >= min(by[f"champion{s}"]["fitness"] for s in CHAMPIONS),
         {"cosines": cosines, "consensus": by["consensus"]["fitness"]}),
        (4, "the aimed onsets are runs resumed: the champion's fresh onsets in light 0.3-3 have a bias within 0.15 of 0",
         fresh["runs"] > 0 and abs(fresh["bias"]) < 0.15, onsets),
        (5, "in dim light (0.01-0.1) the champion runs for more of the time than design 16",
         dim[subject]["running"] > dim["design16"]["running"], {k: v["running"] for k, v in dim.items()}),
    ]
    result = {"gain": gain, "cells": by, "cosines": cosines, "move_size": {str(s): float(np.abs(m).mean()) for s, m in moves.items()},
              "onsets": onsets, "predictions": [{"number": k, "text": t, "holds": bool(h), "values": v} for k, t, h, v in predictions],
              "quick": args.quick}
    (args.out / "summary.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0)
    write_manifest(args.out / "manifest.json", manifest)
    for q in result["predictions"]:
        log(f"prediction {q['number']}: {'holds' if q['holds'] else 'FAILS'}: {q['text']}")
    return result


if __name__ == "__main__":
    main(sys.argv[1:])
