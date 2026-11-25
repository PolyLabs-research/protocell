"""Stage 8b's reading probe (docs/decisions.md D58 C3, D59, D60): how the new generalists move, whether time made
circlers of the two runs it turned into generalists, and what the runs that never survive the spot lack.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage8b_read
    .venv/bin/python -m experiments.stage8b_read --quick --out /tmp/s8br   # the smoke test: not a result

Stage 8's reading (D45) found its one generalist, champion 8102, to be two mechanisms in one network: where its body
gives no direction it swims in circles, with its ring's links, and where it shades itself it steers by the shading.
Read here, as that probe read it, on 60 fresh starts in each of the four trained worlds at seed 67, with shared noise,
one process, on the reference:

A. How each cell moves: the share of the day it runs, its turning during runs, its running and its speed toward the
   light in dim light, its fresh onsets a life. The cells: the five strongest generalists (runs 8102, 8103 and 8104 at
   800 generations; fresh runs 8202 and 8210), runs 8103 and 8104 as they stood at 400 generations, before they were
   generalists, and runs 8101 and 8105 at 800 generations, which still never survive the spot.
B. For the five generalists, world by world: what removing the ring's links costs, and what removing the direction
   across the body costs (the goggles).

Writes docs/data/stage8b/read/. D60 holds the plan and the predictions, written before this ran.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from experiments import stage3c_probe, stage6_read, stage8
from experiments import stage5c_explain as explain
from protocell.cell import decode
from protocell.config import Config
from protocell.evolve import NOISE_CELL_ID
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.sim import simulate
from protocell.tables import write_csv
from protocell.world import sample_starts

SEED = 67  # fresh
MODE = stage8.MODE
STARTS = 60
ROOT = Path("docs/data/stage8b")
CELLS = {"8102 at 800": ROOT / "extend/fourier1-8102/champion.json",
         "8103 at 800": ROOT / "extend/fourier1-8103/champion.json",
         "8104 at 800": ROOT / "extend/fourier1-8104/champion.json",
         "8202": ROOT / "fresh/fourier1-8202/champion.json",
         "8210": ROOT / "fresh/fourier1-8210/champion.json",
         "8103 at 400": ROOT / "extend/fourier1-8103/champion-at-400.json",
         "8104 at 400": ROOT / "extend/fourier1-8104/champion-at-400.json",
         "8101 at 800": ROOT / "extend/fourier1-8101/champion.json",
         "8105 at 800": ROOT / "extend/fourier1-8105/champion.json"}
KNOWN = "8102 at 800"  # the run stage 8's reading read, carried on
NEW = ("8103 at 800", "8104 at 800", "8202", "8210")  # generalists not read before
GENERALISTS = (KNOWN, *NEW)
EARLIER = {"8103 at 800": "8103 at 400", "8104 at 800": "8104 at 400"}  # the two that time made generalists, and themselves before
LOST = ("8101 at 800", "8105 at 800")  # they never survive the spot
TRANSLUCENT = ("home", "flicker", "spot")
RUNS_ALL_DAY, TURNS = 0.8, 0.03  # a circler, as D44 put it: at home it runs more than this share of the day and turns more than this many rad a tick
DIM = "[0.01, 0.1)"
DEFAULT_OUT = ROOT / "read"


def genomes() -> Dict[str, np.ndarray]:
    return {name: np.asarray(json.loads(path.read_text())["genome"], dtype=np.float64) for name, path in CELLS.items()}


def run(cfg: Config, starts: Any, g: np.ndarray, removal: Optional[str] = None, observe: bool = False) -> Dict[str, Any]:
    n = len(starts)
    spec: Dict[str, Any] = {"controller": "network", "mode": MODE, "genomes": np.repeat(g[None], n, axis=0)}
    if removal:
        spec["removal"] = removal
    obs = stage6_read.Reader(cfg, starts, np.full(n, float(decode(cfg, MODE, g[None]).alpha[0]))) if observe else None
    r = simulate(cfg, starts, spec, seed=SEED, cell_ids=[NOISE_CELL_ID] * n, observe=obs)
    out: Dict[str, Any] = {"fitness": float(np.mean(r.fitness)), "survival": float(np.mean(r.survived))}
    if obs is not None:
        obs.runs.finish()
        out["obs"] = obs
    return out


def movement(name: str, world: str, r: Dict[str, Any], n: int) -> Dict[str, Any]:
    """A cell's movement in one world, as stage 8's reading measured it."""
    obs = r["obs"]
    b, _ = explain.movement_rows(name, obs)
    day = [row for row in b if row["band"] != stage3c_probe.band_label(0)]
    life = sum(row["share_of_life"] for row in day)
    pairs = int(obs.pairs.sum())
    fresh = int(np.sum(np.array(obs.runs.onset_gaps) >= explain.RESUME_GAP))
    return {"world": world, "cell": name, "fitness": r["fitness"], "survival": r["survival"],
            "running_by_day": sum(row["running"] * row["share_of_life"] for row in day if math.isfinite(row["running"])) / life if life else math.nan,
            "running_in_dim": next(row["running"] for row in b if row["band"] == DIM),
            "toward_in_dim": next(row["toward_mouth"] for row in b if row["band"] == DIM),
            "turning_during_runs": float((obs.spin.sum() + obs.creep.sum()) / pairs) if pairs else math.nan,
            "fresh_onsets_a_life": fresh / n}


def circles(m: Dict[str, Any]) -> bool:
    """D44's rule for a circler, read at home."""
    return bool(m["running_by_day"] > RUNS_ALL_DAY and abs(m["turning_during_runs"]) > TURNS)


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    quick = args.quick
    worlds = {w: stage8.world(w, quick) for w in stage8.TRAINED}
    cells = genomes()
    n = 4 if quick else STARTS
    manifest = build_manifest(protocol="stage8b/read", settings={"worlds": list(worlds), "cells": {k: str(v) for k, v in CELLS.items()}, "starts": n,
                                                                 "generalists": list(GENERALISTS), "lost": list(LOST), "circler": [RUNS_ALL_DAY, TURNS],
                                                                 "quick": quick},
                              seeds=[SEED], extra={"out": str(args.out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:6.0f}s {msg}", flush=True)

    moves: List[Dict[str, Any]] = []
    parts: List[Dict[str, Any]] = []
    M: Dict[str, Dict[str, Dict[str, Any]]] = {w: {} for w in worlds}
    P: Dict[str, Dict[str, Dict[str, float]]] = {w: {} for w in worlds}
    for w, cfg in worlds.items():
        starts = sample_starts(cfg, "cave", n, SEED)
        for name in CELLS:
            m = movement(name, w, run(cfg, starts, cells[name], observe=True), n)
            moves.append(m)
            M[w][name] = m
            log(f"{w} {name}: fitness {m['fitness']:.3f} ({m['survival']:.0%}); running by day {m['running_by_day']:.0%}, in dim light "
                f"{m['running_in_dim']:.0%}; turning {m['turning_during_runs']:+.3f} rad a tick; fresh onsets a life {m['fresh_onsets_a_life']:.1f}")
        for name in GENERALISTS:
            intact = M[w][name]["fitness"]
            cut = run(cfg, starts, cells[name], removal="ring_links")
            blind = run(cfg.but(sense_contrast=0.0), starts, cells[name])
            P[w][name] = {"ring_links": intact - cut["fitness"], "direction_removed": intact - blind["fitness"]}
            parts += [{"world": w, "cell": name, "change": "ring_links", "fitness": cut["fitness"], "survival": cut["survival"], "drop": intact - cut["fitness"]},
                      {"world": w, "cell": name, "change": "direction removed", "fitness": blind["fitness"], "survival": blind["survival"],
                       "drop": intact - blind["fitness"]}]
            log(f"{w} {name} without its ring's links {P[w][name]['ring_links']:+.3f}; without the direction across its body {P[w][name]['direction_removed']:+.3f}")
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "movement.csv", ("world", "cell", "fitness", "survival", "running_by_day", "running_in_dim", "toward_in_dim",
                                          "turning_during_runs", "fresh_onsets_a_life"), moves)
    write_csv(args.out / "parts.csv", ("world", "cell", "change", "fitness", "survival", "drop"), parts)

    home = M["home"]
    circlers = [c for c in CELLS if circles(home[c])]
    ring = [c for c in NEW if all(P[w][c]["ring_links"] > 0.1 for w in TRANSLUCENT) and P["shaded"][c]["ring_links"] < 0.05]
    steer = [c for c in NEW if P["shaded"][c]["direction_removed"] > 0.05 and P["home"][c]["direction_removed"] < 0.02]
    spot = M["spot"]
    predictions = [
        (1, "at least 3 of the 4 new generalists are circlers at home, as champion 8102 is: each runs more than 80% of the day and turns more than "
            "0.03 rad a tick during runs", sum(c in circlers for c in NEW) >= 3 and KNOWN in circlers,
         {c: {"running_by_day": home[c]["running_by_day"], "turning": home[c]["turning_during_runs"]} for c in GENERALISTS}),
        (2, "at least 3 of the 4 need their ring's links where the cell is translucent and not when it is shaded: more than 0.1 lost at home, under "
            "flicker and under the spot, less than 0.05 when shaded", len(ring) >= 3, {c: {w: P[w][c]["ring_links"] for w in worlds} for c in GENERALISTS}),
        (3, "at least 3 of the 4 read the direction across the body only when shaded: removing it costs more than 0.05 there and less than 0.02 at home",
         len(steer) >= 3, {c: {w: P[w][c]["direction_removed"] for w in worlds} for c in GENERALISTS}),
        (4, "time made circlers of runs 8103 and 8104: neither was one at 400 generations and both are at 800",
         all(later in circlers and earlier not in circlers for later, earlier in EARLIER.items()),
         {c: {"running_by_day": home[c]["running_by_day"], "turning": home[c]["turning_during_runs"]} for pair in EARLIER.items() for c in pair}),
        (5, "the two runs that never survive the spot are not circlers", not any(c in circlers for c in LOST),
         {c: {"running_by_day": home[c]["running_by_day"], "turning": home[c]["turning_during_runs"]} for c in LOST}),
        (6, "under the spot each of those two runs less than half as much of the day as champion 8102 does",
         all(spot[c]["running_by_day"] < 0.5 * spot[KNOWN]["running_by_day"] for c in LOST),
         {c: spot[c]["running_by_day"] for c in (KNOWN, *LOST)}),
    ]
    summary = {"movement": M, "parts": P, "circlers": circlers, "need_ring_when_translucent_only": ring, "steer_when_shaded_only": steer,
               "predictions": [{"number": k, "text": t, "holds": bool(h), "values": v} for k, t, h, v in predictions], "quick": quick}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0)
    write_manifest(args.out / "manifest.json", manifest)
    log(f"circlers at home: {', '.join(circlers) or 'none'}")
    for q in summary["predictions"]:
        log(f"prediction {q['number']}: {'holds' if q['holds'] else 'FAILS'}: {q['text']}")
    return summary


if __name__ == "__main__":
    main(sys.argv[1:])
