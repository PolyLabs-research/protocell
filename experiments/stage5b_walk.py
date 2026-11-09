"""Stage 5b's walk calculator (disclosed in docs/data/stage5b/fourier1/notebook.md): a calculator, not the world.

A radial walk in the cave's light field. The cell's distance d to the mouth changes by v cos(phi) a tick, v = v_max times
its forward pull and phi its heading off the light, which diffuses at the world's rotation noise. Every wall node sees
I(d) = scale / (1 + (d / cave_falloff)^2) plus the sensors' noise; there is no shading, no across-body contrast, no sweep
and no energy. It answers one question about a design: how strongly do its runs favour the light's direction in the far
field, where stage 5b's cells were lost? It is a probe in the sense of stage4e.md section 4 (the network alone on inputs
the writer chooses), with the inputs following the cell's own motion.

    .venv/bin/python -m experiments.stage5b_walk crossing DESIGN.json B5:30      # time to the soak region from d0
    .venv/bin/python -m experiments.stage5b_walk selectivity DESIGN.json B5:30   # running share and run length by heading

Its noise comes from numpy's default generator seeded 0, 1, ... (one walk a seed), as in the scratch scripts whose
numbers the notebook quotes.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from experiments import stage5b
from experiments.stage4e import genome
from protocell.cell import decode
from protocell.config import Config
from protocell.sim import Network
from protocell.world import node_angles

TICKS, SEEDS = 14_400, 8  # four hours, eight walks
HOLD_EVERY = 50  # selectivity: d is put back to d0 this often, so the level stays near I(d0)


class Rule:
    """B5's rule (stage3.md section 3) on the mean sensed light: the front half beats fully while the light is above its
    exponential average (tau ticks), nothing below ``rest_below``."""

    def __init__(self, cfg: Config, tau: float, rest_below: float = 0.01) -> None:
        theta = node_angles(cfg)
        self.front = (np.cos(theta) > 1e-9).astype(float)
        self.tau, self.rest_below, self.m = float(tau), float(rest_below), None
        self.alpha, self.running = 0.0, False

    def beats(self, sensed: np.ndarray, tick: int) -> np.ndarray:
        mean = float(sensed.mean())
        if self.m is None:
            self.m = mean
        self.running = mean > self.m and mean >= self.rest_below
        self.m += (mean - self.m) / self.tau
        return self.front * self.running


class Cell:
    """A design's network, stepped as the simulation steps it; running = its R2 above one half (stage 5b's designs)."""

    def __init__(self, cfg: Config, design: Dict[str, Any]) -> None:
        p = decode(cfg, design["mode"], genome(cfg, design)[None])
        self.net, self.alpha, self.n = Network(cfg, p), float(p.alpha[0]), cfg.n_wall
        names = [c.get("name", f"c{j}") for j, c in enumerate(design.get("core", []))]
        self.i_run = names.index("R2") if "R2" in names else None
        self.running = False

    def beats(self, sensed: np.ndarray, tick: int) -> np.ndarray:
        b = self.net.beats(sensed[None], tick)[0]
        self.running = bool(self.net.output[0, self.n + self.i_run] > 0.5) if self.i_run is not None else bool(b.mean() > 0.2)
        return b


def controller(cfg: Config, spec: str) -> Tuple[str, Callable[[], Any]]:
    """``B5:tau`` or a design's path: a label and a maker of fresh controllers."""
    if spec.startswith("B5:"):
        tau = float(spec[3:])
        return f"B5 tau {tau:g}", lambda: Rule(cfg, tau)
    design = json.loads(Path(spec).read_text())
    return Path(spec).stem, lambda: Cell(cfg, design)


def walk(cfg: Config, make: Callable[[], Any], d0: float, scale: float, seed: int, ticks: int = TICKS,
         stop_at_goal: bool = True, hold_every: int = 0) -> Dict[str, Any]:
    """One walk from d0. Returns the tick the soak region (I >= 1) was reached (None: not within ``ticks``), the mean beat
    and, per tick, cos(phi) and whether the controller ran."""
    rng = np.random.default_rng(seed)
    c = make()
    n = cfg.n_wall
    theta = node_angles(cfg)
    goal = cfg.cave_falloff * math.sqrt(max(scale - 1.0, 0.0))
    d, phi = float(d0), rng.uniform(-math.pi, math.pi)
    heading, running, beat_sum = [], [], 0.0
    for t in range(ticks):
        light = scale / (1.0 + (d / cfg.cave_falloff) ** 2)
        b = c.beats(light + rng.normal(0.0, cfg.sensor_noise_sd, size=n), t)
        fwd = (math.pi / n) * float((b * np.cos(theta + c.alpha)).sum())
        beat_sum += float(b.mean())
        heading.append(math.cos(phi))
        running.append(c.running)
        d = min(max(d - cfg.v_max * fwd * math.cos(phi), 1.0), 2.0 * cfg.dish_radius)
        phi += rng.normal(0.0, cfg.rotation_noise_sd)
        if hold_every and t % hold_every == 0:
            d = float(d0)
        if stop_at_goal and d <= goal:
            return {"reached": t, "beat": beat_sum / (t + 1), "cos": np.array(heading), "run": np.array(running)}
    return {"reached": None, "beat": beat_sum / ticks, "cos": np.array(heading), "run": np.array(running)}


def crossing(cfg: Config, spec: str, d0: float, scale: float, seeds: int = SEEDS, ticks: int = TICKS) -> Dict[str, Any]:
    label, make = controller(cfg, spec)
    res = [walk(cfg, make, d0, scale, s, ticks) for s in range(seeds)]
    hours = [r["reached"] / 3600.0 if r["reached"] is not None else None for r in res]
    got = [h for h in hours if h is not None]
    return {"label": label, "d0": d0, "scale": scale, "reached": len(got), "seeds": seeds,
            "median_h": float(np.median(got)) if got else math.nan, "hours": hours, "beat": float(np.mean([r["beat"] for r in res]))}


def selectivity(cfg: Config, spec: str, d0: float, scale: float, seeds: int = 6, ticks: int = 12_000) -> Dict[str, Any]:
    """Running share by heading (toward cos > 0.7, side |cos| < 0.3, away cos < -0.7) and mean run length by the heading
    at the run's onset (toward > 0.5, away < -0.5), with d held near d0."""
    label, make = controller(cfg, spec)
    share = {"toward": [], "side": [], "away": []}
    lengths: Dict[str, List[int]] = {"toward": [], "side": [], "away": []}
    for s in range(seeds):
        r = walk(cfg, make, d0, scale, s, ticks, stop_at_goal=False, hold_every=HOLD_EVERY)
        cos, on = r["cos"], r["run"]
        share["toward"].append(on[cos > 0.7]); share["side"].append(on[np.abs(cos) < 0.3]); share["away"].append(on[cos < -0.7])
        up = np.flatnonzero(~on[:-1] & on[1:]) + 1
        dn = np.flatnonzero(on[:-1] & ~on[1:]) + 1
        for u in up:
            e = dn[dn > u]
            if e.size:
                lengths["toward" if cos[u] > 0.5 else ("away" if cos[u] < -0.5 else "side")].append(int(e[0] - u))
    return {"label": label, "d0": d0, "scale": scale,
            "share": {k: float(np.concatenate(v).mean()) for k, v in share.items()},
            "length": {k: float(np.mean(v)) if v else math.nan for k, v in lengths.items()}}


def main(argv: Optional[Sequence[str]] = None) -> List[Dict[str, Any]]:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("crossing", "selectivity"):
        p = sub.add_parser(name)
        p.add_argument("specs", nargs="+", help="design paths or B5:tau")
        p.add_argument("--d0", type=float, nargs="+", default=[6000.0, 4000.0] if name == "crossing" else [6000.0])
        p.add_argument("--scale", type=float, nargs="+", default=[5.0, 3.0] if name == "crossing" else [5.0])
    args = parser.parse_args(argv)
    if len(args.d0) != len(args.scale):
        raise SystemExit("one --scale for each --d0")
    cfg = stage5b.world(False)
    out = []
    for spec in args.specs:
        for d0, scale in zip(args.d0, args.scale):
            if args.command == "crossing":
                r = crossing(cfg, spec, d0, scale)
                print(f"{r['label']:10s} d0 {d0:5.0f} scale {scale:4.1f}: reached {r['reached']}/{r['seeds']}, median {r['median_h']:.2f} h, "
                      f"hours {[round(h, 2) if h is not None else None for h in r['hours']]}, beat {r['beat']:.3f}")
            else:
                r = selectivity(cfg, spec, d0, scale)
                print(f"{r['label']:10s} d0 {d0:5.0f}: running toward {r['share']['toward']:.0%}, side {r['share']['side']:.0%}, "
                      f"away {r['share']['away']:.0%}; run length toward {r['length']['toward']:.1f}, side {r['length']['side']:.1f}, "
                      f"away {r['length']['away']:.1f}")
            out.append(r)
    return out


if __name__ == "__main__":
    main(sys.argv[1:])
