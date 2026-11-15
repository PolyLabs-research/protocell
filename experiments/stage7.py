"""Stage 7 (docs/prereg/stage7.md): the cells in worlds they never saw.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage7
    .venv/bin/python -m experiments.stage7 --quick --out /tmp/s7   # the smoke test: not a result

Every champion so far was evolved, searched or written in one world: stage 4a's (translucent, the mouth sweeping,
photosynthesis at 0.55 of the cave's gain). Here five cells run in that world and in six others, unchanged: design 16
(written by hand), stage 5c's champion 3603 (a search from it), and three evolved from random genomes (stage 6's 6301,
stage 6b's 6402 and 6405). In each world the simple rules run over their parameter grids as stage 4's probe ran them;
the bar is the rule and parameter with the best mean fitness on starts 1-50, and everything is reported on starts
51-150 at seed 42 with shared noise and sky (bootstrap at seed 43). Per cell and world: its fitness less the bar's,
and the share of the gap from sitting still to the bar that it closes (stage 4d's verdicts). One process. Writes
docs/data/stage7/.
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

from experiments import stage4_probe as probe
from experiments import stage4e, stage5b, stage5c
from experiments.stage1 import bootstrap_ci
from experiments.stage4d import verdict
from protocell.config import CAVE, Config
from protocell.evolve import NOISE_CELL_ID
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.sim import simulate
from protocell.tables import write_csv
from protocell.world import sample_starts

SEED, BOOTSTRAP_SEED = 42, 43  # fresh
SELECT, REPORT = (1, 50), (51, 150)
RESAMPLES = 10_000
MODE = stage5c.MODE
FLICKER = probe.WORLDS["flicker"]
# name -> (what differs from stage 3's translucent pool, the gain as a share of the cave's)
WORLDS: Dict[str, Tuple[Dict[str, Any], float]] = {
    "home": ({"cave_sweep": True}, 0.55),  # stage 4a's world: where every cell was made
    "fixed mouth": ({}, 0.55),
    "tighter": ({"cave_sweep": True}, 0.45),
    "flicker": (dict(FLICKER), 0.55),
    "sweep and flicker": ({"cave_sweep": True, **FLICKER}, 0.55),
    "spot": (dict(probe.WORLDS["spot_2h"]), 0.45),
    "shaded": ({"cave_sweep": True, "shade_floor": 0.3}, 0.55),
}
UNSEEN = tuple(w for w in WORLDS if w != "home")
CELLS: Dict[str, Optional[Path]] = {
    "design16": None,
    "champion3603": Path("docs/data/stage5c/confirm/fourier1-3603/champion.npy"),
    "champion6301": Path("docs/data/stage6/confirm/fourier1-6301/champion.npy"),
    "champion6402": Path("docs/data/stage6b/confirm/fourier1-6402/champion.npy"),
    "champion6405": Path("docs/data/stage6b/confirm/fourier1-6405/champion.npy"),
}
CHAMPIONS = ("champion3603", "champion6301", "champion6402", "champion6405")
EVOLVED = ("champion6301", "champion6402", "champion6405")
DEFAULT_OUT = Path("docs/data/stage7")
ROW_COLUMNS = ("world", "cell", "fitness", "survival", "bar", "bar_fitness", "less_bar", "low", "high", "beats", "gap_share", "gap_low", "gap_high",
               "verdict")


def world_cfg(name: str, quick: bool) -> Config:
    """The world as the cells meet it: stage 3's translucent pool with the world's changes and gain, and stage 5's sensor
    (the simple rules read the light directly, so the sensor does not touch them)."""
    changes, gain = WORLDS[name]
    base = probe.configure(quick).but(**changes).but(eta=CAVE.eta * gain)
    return base.but(sensing="relative", adapt_tau=stage5b.ADAPT_TAU, sense_floor=stage5b.SENSE_FLOOR, level_floor=stage5b.LEVEL_FLOOR)


def genomes(cfg: Config, quick: bool) -> Dict[str, np.ndarray]:
    g0 = stage4e.genome(cfg, stage4e.load(stage5c.SEED_DESIGN))
    if quick:  # the smoke test: design 16 stands in for every cell
        return {name: g0 for name in CELLS}
    return {name: (g0 if path is None else np.load(path).reshape(-1)) for name, path in CELLS.items()}


def gap_share(cell: np.ndarray, bar: np.ndarray, still: np.ndarray, resamples: int, key: int) -> Tuple[float, float, float]:
    def share(idx: np.ndarray) -> np.ndarray:
        lo, hi = still[idx].mean(axis=-1), bar[idx].mean(axis=-1)
        return (cell[idx].mean(axis=-1) - lo) / (hi - lo)
    from protocell.rng import stream
    point = float(share(np.arange(cell.shape[0])))
    boot = share(stream(BOOTSTRAP_SEED, "bootstrap", (key,)).integers(0, cell.shape[0], size=(resamples, cell.shape[0])))
    return point, float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))


def run_world(name: str, quick: bool, cells: Mapping[str, np.ndarray], log: Any, key0: int) -> Dict[str, Any]:
    cfg = world_cfg(name, quick)
    select, report = ((1, 4), (5, 8)) if quick else (SELECT, REPORT)
    n = report[1]
    resamples = 200 if quick else RESAMPLES
    starts = sample_starts(cfg, "cave", n, SEED)
    sel, rep = np.arange(select[0] - 1, select[1]), np.arange(report[0] - 1, report[1])
    rules: Dict[Tuple[str, str], Dict[str, np.ndarray]] = {}
    for rule, param, sensed, spec in probe.rules(cfg):
        if rule not in (*probe.SIMPLE, "B0"):
            continue
        r = simulate(sensed, starts, spec, seed=SEED, cell_ids=[NOISE_CELL_ID] * n)
        rules[(rule, param)] = {"fitness": np.asarray(r.fitness, dtype=float), "survived": np.asarray(r.survived, dtype=float)}
    still = rules[("B0", "-")]["fitness"]
    simple = {k: v for k, v in rules.items() if k[0] in probe.SIMPLE}
    bar_key = max(simple, key=lambda k: (simple[k]["fitness"][sel].mean(), simple[k]["survived"][sel].mean()))
    bar = simple[bar_key]["fitness"]
    ceiling, _ = probe.always_brightest(cfg, starts, SEED)
    best_each = {rule: max((k for k in simple if k[0] == rule), key=lambda k: simple[k]["fitness"][sel].mean()) for rule in probe.SIMPLE}
    out: Dict[str, Any] = {"bar": f"{bar_key[0]} ({bar_key[1]})", "bar_fitness": float(bar[rep].mean()), "bar_survival": float(simple[bar_key]["survived"][rep].mean()),
                           "still": float(still[rep].mean()), "ceiling": float(ceiling[rep].mean()),
                           "rules": {rule: {"param": k[1], "fitness": float(simple[k]["fitness"][rep].mean())} for rule, k in best_each.items()},
                           "cells": {}}
    log(f"{name}: the bar is {out['bar']} at {out['bar_fitness']:.3f}; sitting still {out['still']:.3f}; the ceiling {out['ceiling']:.3f}")
    for i, (cell, g) in enumerate(cells.items()):
        r = simulate(cfg, starts, {"controller": "network", "mode": MODE, "genomes": np.repeat(g[None], n, axis=0)}, seed=SEED, cell_ids=[NOISE_CELL_ID] * n)
        f = np.asarray(r.fitness, dtype=float)
        d, lo, hi = bootstrap_ci(f[rep] - bar[rep], key0 + 2 * i, resamples, seed=BOOTSTRAP_SEED)
        room = out["bar_fitness"] - out["still"]
        share = gap_share(f[rep], bar[rep], still[rep], resamples, key0 + 2 * i + 1) if room > 0.02 else (math.nan, math.nan, math.nan)
        out["cells"][cell] = {"fitness": float(f[rep].mean()), "survival": float(np.asarray(r.survived, dtype=float)[rep].mean()), "less_bar": d, "low": lo,
                              "high": hi, "beats": lo > 0.0, "gap_share": share[0], "gap_low": share[1], "gap_high": share[2],
                              "verdict": verdict(share[0]) if math.isfinite(share[0]) else "no gap to close"}
        c = out["cells"][cell]
        log(f"  {cell}: {c['fitness']:.3f} ({c['survival']:.0%}), {c['less_bar']:+.3f} [{c['low']:+.3f}, {c['high']:+.3f}] against the bar; closes "
            f"{c['gap_share']:.2f}: {c['verdict']}")
    return out


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--worlds", nargs="+", choices=list(WORLDS), help="only these worlds (the smoke test); default all")
    args = parser.parse_args(argv)
    names = [w for w in WORLDS if not args.worlds or w in args.worlds]
    cells = genomes(world_cfg("home", args.quick), args.quick)
    manifest = build_manifest(protocol="stage7", settings={"worlds": {w: {"changes": WORLDS[w][0], "gain": WORLDS[w][1]} for w in names}, "cells": list(cells),
                                                           "select": SELECT, "report": REPORT, "home": world_cfg("home", args.quick).as_dict(),
                                                           "quick": args.quick}, seeds=[SEED, BOOTSTRAP_SEED], extra={"out": str(args.out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:7.0f}s {msg}", flush=True)

    worlds = {name: run_world(name, args.quick, cells, log, 1000 * (list(WORLDS).index(name) + 1)) for name in names}
    rows = [{"world": w, "cell": c, "bar": v["bar"], "bar_fitness": v["bar_fitness"], **x} for w, v in worlds.items() for c, x in v["cells"].items()]
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "cells.csv", ROW_COLUMNS, rows)
    unseen = [w for w in names if w in UNSEEN]

    def count(cell: str, what: str) -> int:
        return sum((worlds[w]["cells"][cell]["verdict"] == "carries B8") if what == "carries" else bool(worlds[w]["cells"][cell]["beats"]) for w in unseen)

    carries = {c: count(c, "carries") for c in cells}
    beats = {c: count(c, "beats") for c in cells}

    def carry_in(world: str, who: Sequence[str]) -> List[str]:
        return [c for c in who if world in worlds and worlds[world]["cells"][c]["verdict"] == "carries B8"]

    home = worlds.get("home", {"cells": {}})["cells"]
    predictions = [
        (1, "at home, all four champions beat the bar again", bool(home) and all(home[c]["beats"] for c in CHAMPIONS),
         {c: home[c]["less_bar"] for c in CHAMPIONS} if home else {}),
        (2, "with the mouth fixed and with the tighter economy, every champion still does the bar's job",
         all(len(carry_in(w, CHAMPIONS)) == len(CHAMPIONS) for w in ("fixed mouth", "tighter")),
         {w: carry_in(w, CHAMPIONS) for w in ("fixed mouth", "tighter")}),
        (3, "under the circling spot, no cell does the bar's job", not carry_in("spot", list(cells)), {"carry": carry_in("spot", list(cells))}),
        (4, "under flickering clouds no champion beats the bar, and at most half of the champion-and-world pairs do its job",
         not any(worlds[w]["cells"][c]["beats"] for w in ("flicker", "sweep and flicker") if w in worlds for c in CHAMPIONS)
         and sum(len(carry_in(w, CHAMPIONS)) for w in ("flicker", "sweep and flicker")) <= len(CHAMPIONS),
         {w: carry_in(w, CHAMPIONS) for w in ("flicker", "sweep and flicker")}),
        (5, "as a shaded cell, no champion does the bar's job", not carry_in("shaded", CHAMPIONS), {"carry": carry_in("shaded", CHAMPIONS)}),
        (6, "the searched cell holds up in at least as many unseen worlds as the best evolved cell",
         carries["champion3603"] >= max(carries[c] for c in EVOLVED), carries),
    ]
    summary = {"worlds": worlds, "unseen_worlds": unseen, "carries_in_unseen": carries, "beats_in_unseen": beats,
               "predictions": [{"number": k, "text": t, "holds": bool(h), "values": v} for k, t, h, v in predictions], "quick": args.quick}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0)
    write_manifest(args.out / "manifest.json", manifest)
    for c in cells:
        log(f"{c}: does the bar's job in {carries[c]} of {len(unseen)} unseen worlds, beats it in {beats[c]}")
    for q in summary["predictions"]:
        log(f"prediction {q['number']}: {'holds' if q['holds'] else 'FAILS'}: {q['text']}")
    return summary


if __name__ == "__main__":
    main(sys.argv[1:])
