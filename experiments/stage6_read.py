"""Stage 6's reading probe (docs/decisions.md D33 C2, D35): the evolved cell beside the hand-written one, and how
fresh runs come to begin aimed.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage6_read
    .venv/bin/python -m experiments.stage6_read --quick --out /tmp/s6r   # the smoke test: not a result

Four cells on 100 fresh starts at seed 39, in stage 4a's world with stage 5's cell, with shared noise, one process:
design 16 (written by hand), stage 5c's champion 3603 (a search from design 16), stage 6's champion 6301 (evolved from
random genomes), and champion 6301 with its ring's links cut.

For each: the budget by light band (stage 3c's observer), and every run's onset with what came before it: the idle
ticks before the run, the direction and length of the run before that, and how the light on the wall changed over the
10 ticks before the run began. From these, in light 0.3-3: the onset bias by the length of the rest before the run;
how far an onset's direction follows the previous run's; and the onset bias by whether the light was rising, level or
falling before it. The network alone (stage 4e's probes) for the three intact cells, and their wall's genes side by
side. Writes docs/data/stage6/read/. D35 holds the plan and the predictions, written before this ran.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from experiments import stage3c, stage3c_probe, stage4e, stage5b, stage5c
from experiments import stage5c_explain as explain
from protocell.cell import decode, layout
from protocell.cmaes import normalised, to_genomes
from protocell.config import Config
from protocell.evolve import NOISE_CELL_ID
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.sim import simulate
from protocell.tables import write_csv
from protocell.world import sample_starts

SEED = 39  # fresh
MODE = stage5c.MODE
STARTS = 100
GAPS = ((10, 30), (30, 100), (100, 300), (300, 10 ** 9))  # idle ticks before a fresh run
SHORT, LONG = (10, 100), (300, 10 ** 9)
RISE_TICKS, RISE_EDGE = 10, 0.02  # the light's change over the 10 ticks before a run; within 2% is level
CHAMPION_5C = Path("docs/data/stage5c/confirm/fourier1-3603/champion.npy")
CHAMPION_6 = Path("docs/data/stage6/confirm/fourier1-6301/champion.npy")
DEFAULT_OUT = Path("docs/data/stage6/read")
RING_GENES = ("self", "from_cw", "from_ccw", "bias", "log_tau", "gain")


class History(explain.GapTracker):
    """The runs, each onset also with the direction and the length of the run before it."""

    def __init__(self, population: int) -> None:
        super().__init__(population)
        self.current = np.full(population, np.nan)
        self.last_cos = np.full(population, np.nan)
        self.last_ticks = np.zeros(population, dtype=np.int64)
        self.onset_prev_cos: List[float] = []
        self.onset_prev_ticks: List[int] = []
        # added after the first look (D36): the previous run's direction at its last tick, not only at its onset
        self.heading_now = np.full(population, np.nan)
        self.last_end_cos = np.full(population, np.nan)
        self.onset_prev_end_cos: List[float] = []
        # added after the second look (D36): every start of running, however short, with its first tick's direction
        self.start_cos = np.full(population, np.nan)
        self.starts: List[tuple] = []  # (label, the first tick's cosine to the target, ticks it lasted, idle ticks before)

    def step(self, running: np.ndarray, label: np.ndarray, direction: np.ndarray, target: np.ndarray) -> None:
        before = len(self.onsets)
        begin = running & (self.length == 0)
        self.start_cos[begin] = np.cos(direction - target)[begin]
        super().step(running, label, direction, target)
        for cell, _, angle in self.onsets[before:]:
            self.onset_prev_cos.append(float(self.last_cos[cell]))
            self.onset_prev_ticks.append(int(self.last_ticks[cell]))
            self.onset_prev_end_cos.append(float(self.last_end_cos[cell]))
            self.current[cell] = math.cos(angle)
        self.heading_now[running] = np.cos(direction - target)[running]

    def _close(self, which: np.ndarray) -> None:
        for cell in np.flatnonzero(which & (self.length > 0)).tolist():
            self.starts.append((int(self.label[cell]), float(self.start_cos[cell]), int(self.length[cell]), int(self.gap[cell])))
        done = which & (self.length >= stage3c_probe.MIN_RUN)
        self.last_cos[done] = self.current[done]
        self.last_ticks[done] = self.length[done]
        self.last_end_cos[done] = self.heading_now[done]
        super()._close(which)


class Reader(stage3c_probe.Movement):
    """Stage 3c's observer, each onset also with the change in the wall's mean light over the ticks before its run."""

    def __init__(self, cfg: Config, starts: Any, alpha: np.ndarray) -> None:
        super().__init__(cfg, starts, alpha)
        self.runs = History(len(starts))
        self.lights: List[np.ndarray] = []
        self.onset_rise: List[float] = []

    def __call__(self, t: int, s: Mapping[str, Any]) -> None:
        before = len(self.runs.onsets)
        super().__call__(t, s)
        lag = stage3c_probe.MIN_RUN  # an onset is read at the run's third tick: the tick before the run is 3 back
        for cell, _, _ in self.runs.onsets[before:]:
            if len(self.lights) >= lag + RISE_TICKS:
                a, b = self.lights[-lag][cell], self.lights[-lag - RISE_TICKS][cell]
                self.onset_rise.append(math.log((a + 1e-4) / (b + 1e-4)))
            else:
                self.onset_rise.append(math.nan)
        self.lights.append(s["light"].mean(axis=1).copy())
        if len(self.lights) > lag + RISE_TICKS:
            self.lights.pop(0)


def _bias(cos: np.ndarray) -> Dict[str, Any]:
    return {"runs": int(cos.size), "bias": float(cos.mean()) if cos.size else math.nan,
            "se": float(cos.std(ddof=1) / math.sqrt(cos.size)) if cos.size > 1 else math.nan}


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    ok = np.isfinite(a) & np.isfinite(b)
    return float(np.corrcoef(a[ok], b[ok])[0, 1]) if ok.sum() > 2 and a[ok].std() > 0 and b[ok].std() > 0 else math.nan


def onset_reading(obs: Reader) -> Dict[str, Any]:
    """In light 0.3-3: the onset bias by the rest before the run, how an onset follows the previous run, and the bias by
    the light's change before it. Fresh onsets only (10 or more idle ticks), but for the totals."""
    bands = set(stage3c.onset_bands())
    keep = np.array([lab in bands for _, lab, _ in obs.runs.onsets], dtype=bool)
    cos = np.array([math.cos(a) for _, _, a in obs.runs.onsets])
    gap = np.array(obs.runs.onset_gaps, dtype=np.int64)
    prev = np.array(obs.runs.onset_prev_cos)
    prev_ticks = np.array(obs.runs.onset_prev_ticks, dtype=np.int64)
    prev_end = np.array(obs.runs.onset_prev_end_cos)

    def mean(x: np.ndarray) -> float:
        return float(x[np.isfinite(x)].mean()) if np.isfinite(x).any() else math.nan
    rise = np.array(obs.onset_rise)
    fresh = keep & (gap >= explain.RESUME_GAP)
    out: Dict[str, Any] = {"all": _bias(cos[keep]), "fresh": _bias(cos[fresh]), "by_rest": {}, "follows": {}, "by_light_before": {}}
    for lo, hi in GAPS:
        sel = fresh & (gap >= lo) & (gap < hi)
        name = f"{lo}-{hi}" if hi < 10 ** 9 else f"{lo}+"
        out["by_rest"][name] = {**_bias(cos[sel]), "follows_previous": _corr(prev[sel], cos[sel]), "previous_onset_bias": mean(prev[sel]),
                                "previous_end_bias": mean(prev_end[sel]), "follows_previous_end": _corr(prev_end[sel], cos[sel]),
                                "previous_ticks": float(prev_ticks[sel].mean()) if sel.any() else math.nan}
    for name, (lo, hi) in (("short", SHORT), ("long", LONG)):
        sel = fresh & (gap >= lo) & (gap < hi)
        out["follows"][name] = {**_bias(cos[sel]), "follows_previous": _corr(prev[sel], cos[sel]),
                                "previous_bias": float(prev[sel][np.isfinite(prev[sel])].mean()) if np.isfinite(prev[sel]).any() else math.nan,
                                "previous_ticks": float(prev_ticks[sel].mean()) if sel.any() else math.nan}
    st = np.array(obs.runs.starts, dtype=np.float64).reshape(-1, 4)
    mine = np.isin(st[:, 0], list(bands)) & (st[:, 3] >= explain.RESUME_GAP)
    out["starts_by_length"] = {}
    for name, lo, hi in (("every start", 1, 10 ** 9), ("1-2 ticks", 1, 3), ("3-9 ticks", 3, 10), ("10-29 ticks", 10, 30), ("30+ ticks", 30, 10 ** 9)):
        sel = mine & (st[:, 2] >= lo) & (st[:, 2] < hi)
        out["starts_by_length"][name] = {**_bias(st[sel, 1]), "share": float(sel.sum() / mine.sum()) if mine.any() else math.nan}
    known = fresh & np.isfinite(rise)
    for name, sel in (("rising", known & (rise > RISE_EDGE)), ("level", known & (np.abs(rise) <= RISE_EDGE)), ("falling", known & (rise < -RISE_EDGE))):
        out["by_light_before"][name] = {**_bias(cos[sel]), "share": float(sel.sum() / known.sum()) if known.any() else math.nan}
    # added after the third look (D36): the same by the sign of the change alone, however small, and by its size
    out["by_sign_before"] = {}
    for name, sel in (("rising at all", known & (rise > 0.0)), ("falling at all", known & (rise < 0.0))):
        out["by_sign_before"][name] = {**_bias(cos[sel]), "share": float(sel.sum() / known.sum()) if known.any() else math.nan,
                                       "median_change": float(np.median(rise[sel])) if sel.any() else math.nan}
    out["follows_light_before"] = _corr(rise[known], cos[known])
    return out


def cells(cfg: Config, quick: bool) -> Dict[str, Dict[str, Any]]:
    g0 = stage4e.genome(cfg, stage4e.load(stage5c.SEED_DESIGN))
    if quick:  # the smoke test: stand-ins near design 16
        near = lambda k: to_genomes(cfg, MODE, normalised(cfg, MODE, g0)[None] + 0.004 * np.sin(np.arange(g0.size) + k)[None])[0]  # noqa: E731
        g5, g6 = near(1), near(2)
    else:
        g5, g6 = np.load(CHAMPION_5C).reshape(-1), np.load(CHAMPION_6).reshape(-1)
    return {"design16": {"genome": g0}, "champion3603": {"genome": g5}, "champion6301": {"genome": g6},
            "champion6301 ring cut": {"genome": g6, "removal": "ring_links"}}


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    cfg = stage5b.world(args.quick)
    n = 4 if args.quick else STARTS
    starts = sample_starts(cfg, "cave", n, SEED)
    subjects = cells(cfg, args.quick)
    manifest = build_manifest(protocol="stage6/read", settings={"world": cfg.as_dict(), "mode": MODE, "cells": list(subjects), "starts": n,
                                                                "gaps": [list(g) for g in GAPS], "rise_ticks": RISE_TICKS, "rise_edge": RISE_EDGE,
                                                                "quick": args.quick}, seeds=[SEED], extra={"out": str(args.out)})
    t0 = time.time()
    lay = layout(cfg, MODE)
    summary: Dict[str, Any] = {"cells": {}, "quick": args.quick}
    budget: List[Dict[str, Any]] = []
    rest_rows: List[Dict[str, Any]] = []
    for name, c in subjects.items():
        g = c["genome"]
        spec = {"controller": "network", "mode": MODE, "genomes": np.repeat(g[None], n, axis=0)}
        if "removal" in c:
            spec["removal"] = c["removal"]
        obs = Reader(cfg, starts, np.full(n, float(decode(cfg, MODE, g[None]).alpha[0])))
        r = simulate(cfg, starts, spec, seed=SEED, cell_ids=[NOISE_CELL_ID] * n, observe=obs)
        obs.runs.finish()
        b, _ = explain.movement_rows(name, obs)
        budget += b
        reading = onset_reading(obs)
        pairs = int(obs.pairs.sum())
        summary["cells"][name] = {"fitness": float(np.mean(r.fitness)), "survival": float(np.mean(r.survived)), "onsets": reading,
                                  "runs": len(obs.runs.onsets), "running_ticks_paired": pairs,
                                  "spin_during_runs": float(obs.spin.sum() / pairs) if pairs else math.nan,
                                  "creep_during_runs": float(obs.creep.sum() / pairs) if pairs else math.nan,
                                  "ring": dict(zip(RING_GENES, (float(x) for x in g[lay.ring]))), "alpha": float(g[lay.alpha][0])}
        rest_rows += [{"cell": name, "rest": k, **v} for k, v in reading["by_rest"].items()]
        f = reading["follows"]
        print(f"{time.time() - t0:6.0f}s {name}: fitness {np.mean(r.fitness):.3f}; fresh onsets {reading['fresh']['runs']}, bias {reading['fresh']['bias']:+.2f}; "
              f"after short rests {f['short']['bias']:+.2f} (follows {f['short']['follows_previous']:+.2f}), after long {f['long']['bias']:+.2f}; "
              f"rising before {reading['by_light_before']['rising']['share']:.0%}", flush=True)
    intact = {k: v["genome"] for k, v in subjects.items() if "removal" not in v}
    loop = explain.open_loop(cfg, intact, args.quick)
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "budget.csv", ("cell", "band", "share_of_life", *stage3c_probe.STATES, "speed", "toward_mouth", "mean_run_ticks"), budget)
    write_csv(args.out / "onsets_by_rest.csv", ("cell", "rest", "runs", "bias", "se", "follows_previous", "previous_onset_bias", "previous_end_bias",
                                                  "follows_previous_end", "previous_ticks"), rest_rows)
    write_csv(args.out / "open_loop.csv", ("cell", "scenario", "level", "mean_beat", "forward", "running"), loop)
    s = summary["cells"]

    def gap(name: str) -> float:
        return s[name]["onsets"]["follows"]["short"]["bias"] - s[name]["onsets"]["follows"]["long"]["bias"]

    def follows(name: str) -> float:
        return s[name]["onsets"]["follows"]["short"]["follows_previous"]

    dim = {name: next(b for b in budget if b["cell"] == name and b["band"] == "[0.01, 0.1)")["running"] for name in s}
    rising = {name: s[name]["onsets"]["by_light_before"]["rising"]["share"] for name in ("champion3603", "champion6301")}
    cut, whole = s["champion6301 ring cut"]["onsets"]["fresh"], s["champion6301"]["onsets"]["fresh"]
    predictions = [
        (1, "champion 3603's fresh onsets are aimed more after short rests than after long ones, by more than 0.2",
         gap("champion3603") > 0.2, {"short_minus_long": gap("champion3603")}),
        (2, "after short rests an onset follows the previous run's direction: correlation above 0.3 for both champions",
         follows("champion3603") > 0.3 and follows("champion6301") > 0.3, {k: follows(k) for k in ("champion3603", "champion6301")}),
        (3, "the evolved cell does the same as the searched one: prediction 1's difference is also above 0.2 for champion 6301",
         gap("champion6301") > 0.2, {"short_minus_long": gap("champion6301")}),
        (4, "the light was rising before fewer than 60% of either champion's fresh onsets",
         all(v < 0.6 for v in rising.values()), rising),
        (5, "with its ring's links cut, champion 6301 runs for less of the time in dim light and its fresh onsets lose at least half their bias",
         dim["champion6301 ring cut"] < dim["champion6301"] and not (cut["bias"] > 0.5 * whole["bias"]),
         {"dim_running": {k: dim[k] for k in ("champion6301", "champion6301 ring cut")}, "bias": {"intact": whole["bias"], "cut": cut["bias"]}}),
    ]
    summary["predictions"] = [{"number": k, "text": t, "holds": bool(h), "values": v} for k, t, h, v in predictions]
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0)
    write_manifest(args.out / "manifest.json", manifest)
    for q in summary["predictions"]:
        print(f"prediction {q['number']}: {'holds' if q['holds'] else 'FAILS'}: {q['text']}", flush=True)
    return summary


if __name__ == "__main__":
    main(sys.argv[1:])
