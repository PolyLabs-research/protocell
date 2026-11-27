"""How a circle climbs, part C (docs/prereg/circle.md §5; D75): the network alone under a light that rises and falls at
the period of the cell's own circling. Does its speed lock to the rising half, as it does in closed loop?

    .venv/bin/python -W error::RuntimeWarning -m experiments.circle_wave
    .venv/bin/python -m experiments.circle_wave --quick --out /tmp/cw   # the smoke test: not a result

In closed loop at home each circler swims faster while the light it feels rises (D75). A circling cell feels the light
rise and fall once a turn of its circle; steady ramps did not evoke the speed change. Here each of D61's five circling
generalists, open loop, noiseless, the light even across its wall: held at a level for 600 ticks, then multiplied by
exp(a sin(2 pi t / P)) for 3,000 ticks, with P the cell's own circle (2 pi over its mean turning in closed loop, from
docs/data/circle/) and also half and twice that, a = 0.04 (the felt ten-tick trend then reaches about what the closed
loop's rising and falling thirds felt), at a dim level and a bright one. From the oscillation's 601st tick on: the
speed, turning and curvature in the thirds of the felt trend (the wall's mean light now against ten ticks ago), as the
closed loop sorted them.
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

from experiments import circle_read, stage4e, stage8
from protocell.cell import decode
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.tables import write_csv

AMPLITUDE = 0.04
HOLD, WAVE, SKIP = 600, 3000, 600  # steady ticks; oscillating ticks; the oscillation's first ticks left out
FACTORS = (0.5, 1.0, 2.0)  # the period as a multiple of the cell's own circle
LEVELS = circle_read.LEVELS
CLOSED = circle_read.DEFAULT_OUT / "summary.json"
DEFAULT_OUT = circle_read.DEFAULT_OUT / "wave"


def own_period(closed: Dict[str, Any], cell: str) -> float:
    """2 pi over the cell's mean turning while moving in closed loop at home (the middle third: neither rising nor
    falling light)."""
    return 2.0 * math.pi / closed[cell]["thirds"]["middle"]["turning"]


def wave_light(cfg: Any, level: float, period: float, ticks: int, hold: int) -> np.ndarray:
    t = np.arange(ticks)
    mean = level * np.where(t < hold, 1.0, np.exp(AMPLITUDE * np.sin(2.0 * math.pi * (t - hold) / period)))
    return np.repeat(mean[:, None], cfg.n_wall, axis=1)


def respond(cfg: Any, g: np.ndarray, level: float, period: float) -> Dict[str, Any]:
    light = wave_light(cfg, level, period, HOLD + WAVE, HOLD)
    r = stage4e.run_probe_genome(cfg, stage8.MODE, g, light, False)
    m = circle_read.motion(cfg, r["beats"], float(decode(cfg, stage8.MODE, g[None]).alpha[0]))
    felt = np.log(light[:, 0])
    keep = np.arange(HOLD + SKIP, HOLD + WAVE)
    trend = felt[keep] - felt[keep - circle_read.TREND]
    cuts = np.quantile(trend, [1 / 3, 2 / 3])
    third = np.digitize(trend, cuts)
    out: Dict[str, Any] = {"period": period}
    for k, name in enumerate(("falling", "middle", "rising")):
        sel = keep[third == k]
        out[name] = {"trend": float(trend[third == k].mean()), **{q: float(np.mean(np.abs(m[q][sel]))) for q in ("speed", "turning", "curvature")}}
    out["speed_rising_over_falling"] = out["rising"]["speed"] / out["falling"]["speed"]
    out["curvature_rising_over_falling"] = out["rising"]["curvature"] / out["falling"]["curvature"]
    out["steady_speed"] = float(np.mean(m["speed"][HOLD // 2:HOLD]))
    return out


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--quick", action="store_true", help="the smoke test (one level, the cell's own period only): not a result")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--closed", type=Path, default=CLOSED, help="the closed-loop reading the periods come from")
    args = parser.parse_args(argv)
    cfg = stage8.world("home", args.quick)
    closed = json.loads(args.closed.read_text())["closed"]
    cells = circle_read.genomes()
    levels, factors = (LEVELS[:1], (1.0,)) if args.quick else (LEVELS, FACTORS)
    manifest = build_manifest(protocol="circle/wave", settings={"cells": list(cells), "amplitude": AMPLITUDE, "hold": HOLD, "wave": WAVE, "skip": SKIP,
                                                                "factors": list(factors), "levels": list(levels), "periods_from": str(args.closed),
                                                                "quick": args.quick}, seeds=[], extra={"out": str(args.out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:6.0f}s {msg}", flush=True)

    result: Dict[str, Any] = {}
    rows: List[Dict[str, Any]] = []
    for name, g in cells.items():
        base = own_period(closed, name)
        result[name] = {}
        for level in levels:
            for f in factors:
                r = respond(cfg, g, level, f * base)
                result[name][f"{level} x{f}"] = r
                rows.append({"cell": name, "level": level, "factor": f, "period": r["period"], "steady_speed": r["steady_speed"],
                             **{f"{third}_{q}": r[third][q] for third in ("falling", "middle", "rising") for q in ("speed", "curvature")},
                             "speed_rising_over_falling": r["speed_rising_over_falling"], "curvature_rising_over_falling": r["curvature_rising_over_falling"]})
                log(f"{name} at {level}, period {r['period']:.0f} ticks (x{f}): speed rising over falling x{r['speed_rising_over_falling']:.3f}, "
                    f"curvature x{r['curvature_rising_over_falling']:.3f}")
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "wave.csv", tuple(rows[0]), rows)
    own = {c: result[c][f"{LEVELS[0]} x1.0"] for c in cells}
    closed_ratio = {c: closed[c]["speed_rising_over_falling"] for c in cells}
    locks = [c for c in cells if own[c]["speed_rising_over_falling"] >= 1.1]
    same_side = [c for c in cells if (own[c]["speed_rising_over_falling"] - 1.0) * (closed_ratio[c] - 1.0) > 0]
    predictions = [
        (1, "in dim light at its own circle's period, at least 4 of the 5 swim at least 10% faster in the rising third than the falling one", len(locks) >= 4,
         {c: own[c]["speed_rising_over_falling"] for c in cells}),
        (2, "at least 4 of the 5 lean the same way open loop at their own period as in closed loop (faster rising, or slower)", len(same_side) >= 4,
         {c: {"open": own[c]["speed_rising_over_falling"], "closed": closed_ratio[c]} for c in cells}),
        (3, "the curvature stays within 5% between the rising and the falling third, for at least 4 of the 5", sum(abs(own[c]["curvature_rising_over_falling"] - 1) <= 0.05
                                                                                                             for c in cells) >= 4,
         {c: own[c]["curvature_rising_over_falling"] for c in cells}),
    ]
    summary = {"wave": result, "predictions": [{"number": k, "text": t, "holds": bool(h), "values": v} for k, t, h, v in predictions], "quick": args.quick}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0)
    write_manifest(args.out / "manifest.json", manifest)
    for q in summary["predictions"]:
        log(f"prediction {q['number']}: {'holds' if q['holds'] else 'FAILS'}: {q['text']}")
    return summary


if __name__ == "__main__":
    main(sys.argv[1:])
