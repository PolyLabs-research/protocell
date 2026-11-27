"""How a circle climbs (docs/prereg/circle.md; D45 C3): what a circling cell does differently when the light it feels is
rising and when it is falling, so that its circles drift toward the light.

    .venv/bin/python -W error::RuntimeWarning -m experiments.circle_read
    .venv/bin/python -m experiments.circle_read --quick --out /tmp/circ   # the smoke test: not a result

Where the cell is translucent it reads nothing across its body (D45, D61), so a circler that climbs must use the light's
change in time, which its adapting senses feel. Two ways a circle can drift up a gradient: turn less (straighter) while
the light rises, or swim faster while it rises. Read here, for five circling generalists, on the reference, one
process:

A. Closed loop, at home, 60 fresh starts at seed 77: every daylight tick a cell is alive, its speed and its turning, both
   from its beats (the rotational noise left out), and the curvature (turning per unit of distance), sorted by the trend
   of the light it felt over the ten ticks before (the wall's mean light, now against ten ticks ago) into thirds, from
   most falling to most rising. And how fast it climbs: its velocity toward the light's source.
B. Open loop: each network alone, the light even across its wall and noiseless, held at a level, then rising or falling
   by 0.2% a tick (what a cell crossing the gradient at a few radii a tick feels), at a dim level and a bright one: its
   speed, turning and curvature on the ramp beside the steady light before it.

Writes docs/data/circle/. The plan and predictions are in docs/prereg/circle.md, written before this ran.
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

from experiments import stage4e, stage8
from protocell.cell import decode
from protocell.config import Config
from protocell.evolve import NOISE_CELL_ID
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.sim import simulate
from protocell.tables import write_csv
from protocell.world import daylight, mouth_position, node_angles, sample_starts

SEED = 77  # fresh
STARTS = 60
TREND = 10  # ticks: the felt trend is the wall's mean light now against this many ticks ago (the senses adapt over about ten)
MOVING = 0.1  # a tick counts when the cell's speed is above this share of full speed
ROOT = Path("docs/data")
CELLS = {"8102 at 800": ROOT / "stage8b/extend/fourier1-8102/champion.json",
         "8103 at 800": ROOT / "stage8b/extend/fourier1-8103/champion.json",
         "8104 at 800": ROOT / "stage8b/extend/fourier1-8104/champion.json",
         "8202": ROOT / "stage8b/fresh/fourier1-8202/champion.json",
         "8210": ROOT / "stage8b/fresh/fourier1-8210/champion.json"}  # D61's five circling generalists
LEVELS = (0.05, 1.0)  # part B: a dim light and a bright one
RAMP = 0.002  # part B: the light grows (or shrinks) by this share a tick
HOLD, RAMP_TICKS, SETTLE = 600, 200, 50  # part B: steady ticks, ramp ticks, and the ramp's first ticks left out
DEFAULT_OUT = ROOT / "circle"


def genomes() -> Dict[str, np.ndarray]:
    return {name: np.asarray(json.loads(path.read_text())["genome"], dtype=np.float64) for name, path in CELLS.items()}


def motion(cfg: Config, beats: np.ndarray, alpha: float) -> Dict[str, np.ndarray]:
    """From the beats ``(T, N)`` (or ``(P, N)``): the speed (share of full speed), the turning (rad a tick, without the
    rotational noise) and the curvature (rad a radius), as ``protocell.motion.cilia_motion`` makes them."""
    n = cfg.n_wall
    angle = node_angles(cfg) + alpha
    vx = (math.pi / n) * (beats * np.cos(angle)).sum(axis=-1)
    vy = (math.pi / n) * (beats * np.sin(angle)).sum(axis=-1)
    speed = np.hypot(vx, vy)
    turning = cfg.omega_max * beats.mean(axis=-1) * math.sin(alpha)
    curvature = np.abs(turning) / np.maximum(speed * cfg.v_max, 1e-12)
    return {"speed": speed, "turning": turning, "curvature": curvature}


class Recorder:
    """Part A's observer: for every daylight tick a cell is alive and moving, its felt trend, speed, turning, curvature
    and velocity toward the source."""

    def __init__(self, cfg: Config, starts: Any, alpha: float) -> None:
        self.cfg, self.starts, self.alpha = cfg, starts, alpha
        self.history: List[np.ndarray] = []
        self.rows: Dict[str, List[np.ndarray]] = {k: [] for k in ("trend", "speed", "turning", "curvature", "toward")}
        self.prev_pos: Optional[np.ndarray] = None

    def __call__(self, t: int, s: Mapping[str, Any]) -> None:
        light = s["light"].mean(axis=1)
        self.history.append(light.copy())
        if len(self.history) > TREND + 1:
            self.history.pop(0)
        pos = s["pos"]
        if self.prev_pos is not None and len(self.history) == TREND + 1:
            m = motion(self.cfg, s["beats"], self.alpha)
            src = mouth_position(self.cfg, s["time"])
            to = src - self.prev_pos
            dist = np.maximum(np.hypot(to[:, 0], to[:, 1]), 1e-9)
            moved = pos - self.prev_pos
            toward = (moved[:, 0] * to[:, 0] + moved[:, 1] * to[:, 1]) / dist
            keep = s["active"] & s["alive"] & (daylight(self.cfg, s["time"]) > 0.0) & (m["speed"] > MOVING)
            trend = np.log((self.history[-1] + 1e-6) / (self.history[0] + 1e-6))
            for k, v in (("trend", trend), ("speed", m["speed"]), ("turning", np.abs(m["turning"])), ("curvature", m["curvature"]), ("toward", toward)):
                self.rows[k].append(v[keep])
        self.prev_pos = pos.copy()

    def table(self) -> Dict[str, np.ndarray]:
        return {k: np.concatenate(v) if v else np.zeros(0) for k, v in self.rows.items()}


def closed_loop(cfg: Config, starts: Any, g: np.ndarray) -> Dict[str, Any]:
    n = len(starts)
    alpha = float(decode(cfg, stage8.MODE, g[None]).alpha[0])
    rec = Recorder(cfg, starts, alpha)
    r = simulate(cfg, starts, {"controller": "network", "mode": stage8.MODE, "genomes": np.repeat(g[None], n, axis=0)}, seed=SEED,
                 cell_ids=[NOISE_CELL_ID] * n, observe=rec)
    tab = rec.table()
    cuts = np.quantile(tab["trend"], [1 / 3, 2 / 3]) if tab["trend"].size else np.array([0.0, 0.0])
    third = np.digitize(tab["trend"], cuts)  # 0 falling, 1 middle, 2 rising
    out: Dict[str, Any] = {"fitness": float(np.mean(r.fitness)), "survival": float(np.mean(r.survived)), "ticks": int(tab["trend"].size),
                           "climb": float(tab["toward"].mean()) if tab["toward"].size else math.nan, "thirds": {}}
    for k, name in enumerate(("falling", "middle", "rising")):
        sel = third == k
        out["thirds"][name] = {"trend": float(tab["trend"][sel].mean()), **{q: float(tab[q][sel].mean()) for q in ("speed", "turning", "curvature", "toward")}}
    f, u = out["thirds"]["falling"], out["thirds"]["rising"]
    out["curvature_rising_over_falling"] = u["curvature"] / f["curvature"]
    out["speed_rising_over_falling"] = u["speed"] / f["speed"]
    out["turning_rising_over_falling"] = u["turning"] / f["turning"]
    return out


def open_loop(cfg: Config, g: np.ndarray, level: float) -> Dict[str, Any]:
    alpha = float(decode(cfg, stage8.MODE, g[None]).alpha[0])
    out: Dict[str, Any] = {}
    for kind in ("ramp", "fall"):
        light = stage4e.light_scenario(cfg, kind, level, RAMP, 0.0, 0.0, HOLD + RAMP_TICKS, HOLD)
        r = stage4e.run_probe_genome(cfg, stage8.MODE, g, light, False)
        m = motion(cfg, r["beats"], alpha)
        steady, moving = slice(HOLD // 2, HOLD), slice(HOLD + SETTLE, HOLD + RAMP_TICKS)
        out[kind] = {q: {"steady": float(np.mean(np.abs(m[q][steady]))), "ramp": float(np.mean(np.abs(m[q][moving])))} for q in ("speed", "turning", "curvature")}
        for q in ("speed", "turning", "curvature"):
            out[kind][q]["ratio"] = out[kind][q]["ramp"] / max(out[kind][q]["steady"], 1e-12)
    return out


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    quick = args.quick
    cfg = stage8.world("home", quick)
    cells = genomes()
    n = 4 if quick else STARTS
    manifest = build_manifest(protocol="circle/read", settings={"world": "home", "cells": {k: str(v) for k, v in CELLS.items()}, "starts": n,
                                                                "trend_ticks": TREND, "moving": MOVING, "levels": list(LEVELS), "ramp": RAMP,
                                                                "hold": HOLD, "ramp_ticks": RAMP_TICKS, "settle": SETTLE, "quick": quick},
                              seeds=[SEED], extra={"out": str(args.out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:6.0f}s {msg}", flush=True)

    starts = sample_starts(cfg, "cave", n, SEED)
    closed: Dict[str, Any] = {}
    opened: Dict[str, Any] = {}
    rows_a: List[Dict[str, Any]] = []
    rows_b: List[Dict[str, Any]] = []
    for name, g in cells.items():
        c = closed_loop(cfg, starts, g)
        closed[name] = c
        for third, v in c["thirds"].items():
            rows_a.append({"cell": name, "third": third, **v})
        log(f"{name}: climbs {c['climb']:+.3f} R a tick over {c['ticks']} ticks; rising against falling: curvature x{c['curvature_rising_over_falling']:.3f}, "
            f"speed x{c['speed_rising_over_falling']:.3f}, turning x{c['turning_rising_over_falling']:.3f}")
        opened[name] = {}
        for level in LEVELS:
            o = open_loop(cfg, g, level)
            opened[name][str(level)] = o
            for kind in ("ramp", "fall"):
                rows_b.append({"cell": name, "level": level, "kind": kind, **{f"{q}_{w}": o[kind][q][w] for q in ("speed", "turning", "curvature")
                                                                            for w in ("steady", "ramp", "ratio")}})
            log(f"  open loop at {level}: curvature on a rise x{o['ramp']['curvature']['ratio']:.3f}, on a fall x{o['fall']['curvature']['ratio']:.3f}; "
                f"speed on a rise x{o['ramp']['speed']['ratio']:.3f}, on a fall x{o['fall']['speed']['ratio']:.3f}")
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "closed.csv", ("cell", "third", "trend", "speed", "turning", "curvature", "toward"), rows_a)
    write_csv(args.out / "open.csv", tuple(rows_b[0]), rows_b)
    dim = str(LEVELS[0])
    straighter = [c for c in cells if closed[c]["curvature_rising_over_falling"] <= 0.9]
    same_speed = [c for c in cells if abs(closed[c]["speed_rising_over_falling"] - 1.0) <= 0.05]
    open_dir = [c for c in cells if opened[c][dim]["ramp"]["curvature"]["ratio"] < 1.0 < opened[c][dim]["fall"]["curvature"]["ratio"]]
    climbing = [c for c in cells if closed[c]["climb"] > 0.0]
    predictions = [
        (1, "at least 4 of the 5 turn less per unit distance when the light they feel is rising: curvature in the rising third at most 0.9 of that "
            "in the falling third", len(straighter) >= 4, {c: closed[c]["curvature_rising_over_falling"] for c in cells}),
        (2, "speed matters less: at least 3 of the 5 swim within 5% of the same speed in the rising and the falling third", len(same_speed) >= 3,
         {c: closed[c]["speed_rising_over_falling"] for c in cells}),
        (3, "open loop, in dim light, at least 4 of the 5 curve less on a rising ramp than in steady light and more on a falling one", len(open_dir) >= 4,
         {c: {"rise": opened[c][dim]["ramp"]["curvature"]["ratio"], "fall": opened[c][dim]["fall"]["curvature"]["ratio"]} for c in cells}),
        (4, "all five climb at home: their velocity toward the source while moving is positive on average", len(climbing) == len(cells),
         {c: closed[c]["climb"] for c in cells}),
    ]
    summary = {"closed": closed, "open": opened, "predictions": [{"number": k, "text": t, "holds": bool(h), "values": v} for k, t, h, v in predictions],
               "quick": quick}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0)
    write_manifest(args.out / "manifest.json", manifest)
    for q in summary["predictions"]:
        log(f"prediction {q['number']}: {'holds' if q['holds'] else 'FAILS'}: {q['text']}")
    return summary


if __name__ == "__main__":
    main(sys.argv[1:])
