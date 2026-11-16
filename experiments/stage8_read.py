"""Stage 8's reading probe (docs/decisions.md D42 C2, D44): how the generalist handles four kinds of world.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage8_read
    .venv/bin/python -m experiments.stage8_read --quick --out /tmp/s8r   # the smoke test: not a result

Champion 8102 does each world's best simple rule's job in the four worlds it was evolved in. Read here, on 60 fresh
starts in each of those worlds at seed 48, with shared noise, one process:

A. How it moves, beside champion 6402 (the home specialist) and champion 8105 (a stage 8 run that failed): by light
   band the share of time running and the speed toward the light's source; the turning during runs; how often it rests.
B. Which parts it needs in each world: stage 4b's removals, world by world.
C. Whether it reads the direction across its body: the goggles (direction removed) in each world.
D. What a cloud does to it: its network alone through a cloud's shadow and the sun's return, beside champions 6402 and
   3603 (the hand-written line, which starves under clouds).

Writes docs/data/stage8/read/. D44 holds the plan and the predictions, written before this ran.
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

from experiments import stage3c_probe, stage4b, stage4e, stage5c, stage6_read, stage8
from experiments import stage5c_explain as explain
from protocell.cell import decode
from protocell.cmaes import normalised, to_genomes
from protocell.config import Config
from protocell.evolve import NOISE_CELL_ID
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.sim import simulate
from protocell.tables import write_csv
from protocell.world import sample_starts

SEED = 48  # fresh
MODE = stage5c.MODE
STARTS = 60
SUBJECT = "champion8102"
CELLS = {"champion8102": Path("docs/data/stage8/pilot/fourier1-8102/champion.npy"),
         "champion6402": Path("docs/data/stage6b/confirm/fourier1-6402/champion.npy"),
         "champion8105": Path("docs/data/stage8/confirm/fourier1-8105/champion.npy"),
         "champion3603": Path("docs/data/stage5c/confirm/fourier1-3603/champion.npy")}
MOVERS = ("champion8102", "champion6402", "champion8105")  # part A
CLOUDED = ("champion8102", "champion6402", "champion3603")  # part D
DIM = "[0.01, 0.1)"
SHADE = 0.3  # a cloud's shade, as the worlds'
CLOUD_LEVELS = (1.0, 0.1)
CLOUD_BEFORE, CLOUD_AFTER = 300, 60  # ticks of steady light before the change; the window read after it
MOVING = 0.25  # the network alone is moving when its pull is above this share of full speed, in any direction
DEFAULT_OUT = Path("docs/data/stage8/read")


def genomes(cfg: Config, quick: bool) -> Dict[str, np.ndarray]:
    if quick:  # the smoke test: stand-ins near design 16
        g0 = stage4e.genome(cfg, stage4e.load(stage5c.SEED_DESIGN))
        return {name: to_genomes(cfg, MODE, normalised(cfg, MODE, g0)[None] + 0.004 * np.sin(np.arange(g0.size) + k)[None])[0]
                for k, name in enumerate(CELLS)}
    return {name: np.load(path).reshape(-1) for name, path in CELLS.items()}


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


def cloud_rows(cfg: Config, cells: Dict[str, np.ndarray], quick: bool) -> List[Dict[str, Any]]:
    """Part D: each network alone in steady light, then through a cloud's shadow (the light falls to 0.3 of itself) and
    through the sun's return (it rises back): the share of ticks it is moving before, and in the window after."""
    before, after = (60, 30) if quick else (CLOUD_BEFORE, CLOUD_AFTER)
    rows = []
    for name, g in cells.items():
        for level in CLOUD_LEVELS:
            for event, start, rise in (("shadow", level, SHADE - 1.0), ("sun returns", level * SHADE, 1.0 / SHADE - 1.0)):
                light = stage4e.light_scenario(cfg, "step", start, rise, 0.0, 0.0, before + after, before)
                r = stage4e.run_probe_genome(cfg, MODE, g, light, True)
                pull = np.hypot(r["forward"], r["left"])
                steady, then = slice(before // 3, before), slice(before, before + after)
                rows.append({"cell": name, "event": event, "sunlit_level": level, "moving_before": float(np.mean(pull[steady] > MOVING)),
                             "moving_after": float(np.mean(pull[then] > MOVING)), "pull_before": float(pull[steady].mean()),
                             "pull_after": float(pull[then].mean())})
    return rows


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    quick = args.quick
    worlds = {w: stage8.world(w, quick) for w in stage8.TRAINED}
    cells = genomes(worlds["home"], quick)
    n = 4 if quick else STARTS
    manifest = build_manifest(protocol="stage8/read", settings={"worlds": list(worlds), "cells": list(cells), "starts": n, "subject": SUBJECT,
                                                                "removals": list(stage4b.REMOVALS), "quick": quick},
                              seeds=[SEED], extra={"out": str(args.out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:6.0f}s {msg}", flush=True)

    budget: List[Dict[str, Any]] = []
    moves: List[Dict[str, Any]] = []
    parts: List[Dict[str, Any]] = []
    summary: Dict[str, Any] = {"worlds": {}, "quick": quick}
    for w, cfg in worlds.items():
        starts = sample_starts(cfg, "cave", n, SEED)
        here: Dict[str, Any] = {"cells": {}, "removals": {}}
        for name in MOVERS:
            r = run(cfg, starts, cells[name], observe=True)
            obs = r.pop("obs")
            b, _ = explain.movement_rows(name, obs)
            budget += [{"world": w, **row} for row in b]
            day = [row for row in b if row["band"] != stage3c_probe.band_label(0)]
            life = sum(row["share_of_life"] for row in day)
            pairs = int(obs.pairs.sum())
            fresh = int(np.sum(np.array(obs.runs.onset_gaps) >= explain.RESUME_GAP))
            m = {"world": w, "cell": name, "fitness": r["fitness"], "survival": r["survival"],
                 "running_by_day": sum(row["running"] * row["share_of_life"] for row in day if math.isfinite(row["running"])) / life if life else math.nan,
                 "running_in_dim": next(row["running"] for row in b if row["band"] == DIM),
                 "toward_in_dim": next(row["toward_mouth"] for row in b if row["band"] == DIM),
                 "turning_during_runs": float((obs.spin.sum() + obs.creep.sum()) / pairs) if pairs else math.nan,
                 "fresh_onsets_a_life": fresh / n}
            moves.append(m)
            here["cells"][name] = m
            log(f"{w} {name}: fitness {m['fitness']:.3f} ({m['survival']:.0%}); running by day {m['running_by_day']:.0%}, in dim light "
                f"{m['running_in_dim']:.0%}; turning {m['turning_during_runs']:+.3f} rad a tick; fresh onsets a life {m['fresh_onsets_a_life']:.1f}")
        intact = here["cells"][SUBJECT]["fitness"]
        for rm in stage4b.REMOVALS:
            r = run(cfg, starts, cells[SUBJECT], removal=rm)
            here["removals"][rm] = intact - r["fitness"]
            parts.append({"world": w, "change": rm, "fitness": r["fitness"], "survival": r["survival"], "drop": intact - r["fitness"]})
        r = run(cfg.but(sense_contrast=0.0), starts, cells[SUBJECT])
        here["direction_removed"] = intact - r["fitness"]
        parts.append({"world": w, "change": "direction removed", "fitness": r["fitness"], "survival": r["survival"], "drop": intact - r["fitness"]})
        log(f"{w} {SUBJECT} without: " + ", ".join(f"{k} {v:+.3f}" for k, v in here["removals"].items()) + f"; direction {here['direction_removed']:+.3f}")
        summary["worlds"][w] = here
    clouds = cloud_rows(worlds["home"], {k: cells[k] for k in CLOUDED}, quick)
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "budget.csv", ("world", "cell", "band", "share_of_life", *stage3c_probe.STATES, "speed", "toward_mouth", "mean_run_ticks"), budget)
    write_csv(args.out / "movement.csv", ("world", "cell", "fitness", "survival", "running_by_day", "running_in_dim", "toward_in_dim",
                                          "turning_during_runs", "fresh_onsets_a_life"), moves)
    write_csv(args.out / "parts.csv", ("world", "change", "fitness", "survival", "drop"), parts)
    write_csv(args.out / "clouds.csv", ("cell", "event", "sunlit_level", "moving_before", "moving_after", "pull_before", "pull_after"), clouds)
    summary["clouds"] = clouds
    W = summary["worlds"]

    def jump(cell: str) -> float:  # the largest change in the share of ticks moving, over the cloud events and levels
        return max(abs(r["moving_after"] - r["moving_before"]) for r in clouds if r["cell"] == cell)

    home = W["home"]["cells"][SUBJECT]
    predictions = [
        (1, "champion 8102 is of the circling kind: by day at home it runs more than 80% of the time and turns more than 0.03 rad a tick",
         home["running_by_day"] > 0.8 and abs(home["turning_during_runs"]) > 0.03,
         {"running_by_day": home["running_by_day"], "turning": home["turning_during_runs"]}),
        (2, "it needs its ring's links in all four worlds: more than 0.1 lost in each", all(W[w]["removals"]["ring_links"] > 0.1 for w in W),
         {w: W[w]["removals"]["ring_links"] for w in W}),
        (3, "a cloud moves champion 3603 and not champion 8102: 3603's share of ticks moving changes by more than 0.3 at some event, 8102's by less than 0.15 at every one",
         jump("champion3603") > 0.3 and jump(SUBJECT) < 0.15, {c: jump(c) for c in CLOUDED}),
        (4, "it reads the direction across its body only when shaded: removing it costs more than 0.05 in the shaded world and less than 0.02 at home",
         W["shaded"]["direction_removed"] > 0.05 and W["home"]["direction_removed"] < 0.02, {w: W[w]["direction_removed"] for w in W}),
        (5, "under the spot, champion 8105 runs less than half as much of its time in dim light as champion 8102",
         W["spot"]["cells"]["champion8105"]["running_in_dim"] < 0.5 * W["spot"]["cells"][SUBJECT]["running_in_dim"],
         {c: W["spot"]["cells"][c]["running_in_dim"] for c in (SUBJECT, "champion8105")}),
    ]
    summary["predictions"] = [{"number": k, "text": t, "holds": bool(h), "values": v} for k, t, h, v in predictions]
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0)
    write_manifest(args.out / "manifest.json", manifest)
    for q in summary["predictions"]:
        log(f"prediction {q['number']}: {'holds' if q['holds'] else 'FAILS'}: {q['text']}")
    return summary


if __name__ == "__main__":
    main(sys.argv[1:])
