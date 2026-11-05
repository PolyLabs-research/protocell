"""Stage 4's thrift probe (docs/decisions.md D20 C1, D21): do stage 3b's working cells die in stage 4a's world by
spending or by finding too little?

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage4_thrift --workers 16
    .venv/bin/python -m experiments.stage4_thrift --quick --out /tmp/s4t --workers 2   # the smoke test: not a result

Both of stage 4's searches build cells that find the light while the world is generous, and lose them as the economy
tightens (D20). The cells here are stage 3b's two working champions, uniform 2203 and fourier1 3202, beside B0, B5
(tau 3 s) and B8 (tau 10 s), stage 4a's choices. The worlds are stage 3's translucent pool, with the mouth fixed and
sweeping, at 1, 0.8, 0.65 and 0.55 of the cave's photosynthetic gain: the champions' home world, the gain's fall along
stage 4b's path, and stage 4a's world (sweeping, 0.55).

Each cell runs twice in each world: as the world is, and with beating free (c1 = 0). No cell senses its reserve, so
free beating leaves every move the same while the cell lives; only what beating costs is gone. A cell that still
starves found too little light. On fresh starts 1-100 at seed 23, with shared noise. Measured per start, over the ticks
the cell lived: the light it soaked per daylight tick, its beat by day and by night, survival, fitness and when it
died. D21's verdict and predictions are read at the end. Writes docs/data/stage4/thrift/.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from experiments import stage3c_probe
from experiments import stage4_probe as probe
from experiments import stage4a
from experiments.stage3 import configure
from protocell.config import CAVE, Config
from protocell.energy import photosynthesis
from protocell.evolve import NOISE_CELL_ID
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.sim import simulate
from protocell.tables import write_csv
from protocell.world import Starts, daylight, sample_starts

SEED = 23  # fresh: the starts and the noise
GAINS = (1.0, 0.8, 0.65, 0.55)  # the photosynthetic gain as a share of the cave's: home, stage 4b's path, stage 4a
SWEEPS = (False, True)
B5_TAU, B8_TAU = 3.0, 10.0  # stage 4a's choices (docs/data/stage4a/summary.json)
CELLS = ("B0", "B5", "B8", *stage3c_probe.CHAMPIONS)
COSTS = ("paid", "free")  # beating at the world's cost c1, or free (c1 = 0)
HOME, STAGE4A = (False, 1.0), (True, 0.55)
STAGE3B_SURVIVAL = {"U2203": 0.50, "F3202": 0.63}  # at home, on stage 3b's test (docs/data/stage3b/test/summary.json)
SPENDING_SURVIVAL, FINDING_SURVIVAL = 0.8, 0.5  # D21's verdict: free beating survives at least 0.8 / below 0.5
CHUNK = 50
ROW_COLUMNS = ("world", "sweep", "gain", "cell", "cost", "start", "phase", "lifetime", "survived", "fitness", "death_tick",
               "died_at_night", "day_ticks_lived", "night_ticks_lived", "day_light", "day_beat", "night_beat")
DEFAULT_OUT = Path("docs/data/stage4/thrift")


def world(sweep: bool, gain: float, quick: bool = False) -> Config:
    """Stage 3's translucent pool, the mouth fixed or sweeping, at ``gain`` of the cave's photosynthetic gain."""
    return configure(quick).but(cave_sweep=sweep, eta=CAVE.eta * gain)


def world_name(sweep: bool, gain: float) -> str:
    return f"{'sweep' if sweep else 'fixed'} x{gain:g}"


def cell_spec(cfg: Config, cell: str, n: int) -> Dict[str, Any]:
    if cell == "B0":
        return {"controller": "still"}
    if cell == "B5":
        return {"controller": "runwait", "tau": B5_TAU, "rest_below": cfg.rest_below}
    if cell == "B8":
        return {"controller": "aimrun", "tau": B8_TAU, "aim_tau": probe.B8_AIM_TAU, "rest_below": cfg.rest_below}
    return stage4a.champion_spec(cell, n)


class Ledger:
    """An observer for ``simulate``: each cell's ticks lived by day and by night, the light it soaked by day (P(I)
    over the wall, as ``energy_step`` counts it) and its beat by day and by night. A tick is lived if the cell was alive
    at its start and within its lifetime; daylight is above zero."""

    def __init__(self, cfg: Config, n: int) -> None:
        self.cfg = cfg
        self.day_ticks, self.night_ticks = np.zeros(n, dtype=np.int64), np.zeros(n, dtype=np.int64)
        self.day_soak, self.day_beat, self.night_beat = np.zeros(n), np.zeros(n), np.zeros(n)

    def __call__(self, t: int, state: Mapping[str, Any]) -> None:
        lived = state["active"]
        day = daylight(self.cfg, state["time"]) > 0.0
        by_day, by_night = lived & day, lived & ~day
        soak = photosynthesis(state["light"]).mean(axis=1)
        beat = state["beats"].mean(axis=1)
        self.day_ticks += by_day
        self.night_ticks += by_night
        self.day_soak += np.where(by_day, soak, 0.0)
        self.day_beat += np.where(by_day, beat, 0.0)
        self.night_beat += np.where(by_night, beat, 0.0)


def _per(total: np.ndarray, ticks: np.ndarray) -> np.ndarray:
    out = np.full(total.shape, math.nan)
    np.divide(total, ticks, out=out, where=ticks > 0)
    return out


def sim_job(job: Mapping[str, Any]) -> Dict[str, Any]:
    cfg: Config = job["cfg"]
    starts: Starts = job["starts"]
    ledger = Ledger(cfg, len(starts))
    r = simulate(cfg, starts, job["spec"], seed=SEED, cell_ids=[NOISE_CELL_ID] * len(starts), observe=ledger)
    died = r.death_tick >= 0
    at_night = died & (daylight(cfg, starts.phase + np.maximum(r.death_tick, 1) - 1) == 0.0)
    day_light, day_beat = _per(ledger.day_soak, ledger.day_ticks), _per(ledger.day_beat, ledger.day_ticks)
    night_beat = _per(ledger.night_beat, ledger.night_ticks)
    rows = [{"world": job["world"], "sweep": int(job["sweep"]), "gain": job["gain"], "cell": job["cell"], "cost": job["cost"],
             "start": int(starts.index[i]), "phase": int(starts.phase[i]), "lifetime": int(r.lifetime[i]), "survived": int(r.survived[i]),
             "fitness": float(r.fitness[i]), "death_tick": int(r.death_tick[i]), "died_at_night": int(at_night[i]),
             "day_ticks_lived": int(ledger.day_ticks[i]), "night_ticks_lived": int(ledger.night_ticks[i]), "day_light": float(day_light[i]),
             "day_beat": float(day_beat[i]), "night_beat": float(night_beat[i])} for i in range(len(starts))]
    return {"first": job["first"], "key": (job["world"], job["cell"], job["cost"]), "rows": rows}


def _mean(values: Sequence[float]) -> Optional[float]:
    v = np.array([x for x in values if not math.isnan(x)], dtype=np.float64)
    return float(v.mean()) if v.size else None


def summarise(rows: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """One cell's runs in one world at one cost: its shares and means over the starts (the light and the beats over the
    starts on which the cell lived such ticks)."""
    dead = [r for r in rows if not r["survived"]]
    return {"n": len(rows), "survival": float(np.mean([r["survived"] for r in rows])), "fitness": float(np.mean([r["fitness"] for r in rows])),
            "day_light": _mean([r["day_light"] for r in rows]), "day_beat": _mean([r["day_beat"] for r in rows]),
            "night_beat": _mean([r["night_beat"] for r in rows]),
            "died_at_night_share": float(np.mean([r["died_at_night"] for r in dead])) if dead else None,
            "median_death_hour": float(np.median([r["death_tick"] for r in dead])) / 3600.0 if dead else None}


def break_even_day_light(cfg: Config) -> float:
    """The light a still cell must soak, on average over the daylight, to pay its resting cost for a whole day: the
    resting cost over the day, c0 day_ticks, against eta over the daylight's half of it."""
    return 2.0 * cfg.c0 / cfg.eta


def verdicts(table: Mapping[str, Mapping[str, Mapping[str, Mapping[str, Any]]]]) -> Dict[str, Dict[str, Any]]:
    """D21's verdict per champion, in stage 4a's world: with beating free, survival at least 0.8 means the cell dies
    by spending; below 0.5, by finding too little; between, both."""
    here = table[world_name(*STAGE4A)]
    out = {}
    for cell in stage3c_probe.CHAMPIONS:
        free = here[cell]["free"]["survival"]
        kind = "spending" if free >= SPENDING_SURVIVAL else "finding" if free < FINDING_SURVIVAL else "both"
        out[cell] = {"free_survival": free, "paid_survival": here[cell]["paid"]["survival"], "verdict": kind}
    return out


def score_predictions(table: Mapping[str, Mapping[str, Mapping[str, Mapping[str, Any]]]]) -> List[Dict[str, Any]]:
    """D21's predictions."""
    home, here = table[world_name(*HOME)], table[world_name(*STAGE4A)]
    champions = list(stage3c_probe.CHAMPIONS)
    p1 = {c: home[c]["paid"]["survival"] for c in champions}
    p2 = {c: here[c]["free"]["survival"] for c in champions}
    b8 = here["B8"]["paid"]["day_light"]
    p3 = {"B8": b8, **{c: here[c]["paid"]["day_light"] for c in champions}}
    sweep_home = table[world_name(True, 1.0)]
    fixed_low = table[world_name(False, 0.55)]
    p4 = {c: {"sweep_costs": home[c]["paid"]["survival"] - sweep_home[c]["paid"]["survival"],
              "gain_costs": home[c]["paid"]["survival"] - fixed_low[c]["paid"]["survival"]} for c in champions}
    out = [
        (1, "at home each champion survives within 15 points of stage 3b's test (U2203 50%, F3202 63%)",
         all(abs(p1[c] - STAGE3B_SURVIVAL[c]) <= 0.15 for c in champions), p1),
        (2, "in stage 4a's world, with beating free, both champions survive fewer than half the starts",
         all(p2[c] < 0.5 for c in champions), p2),
        (3, "in stage 4a's world each champion soaks less than half B8's light per daylight tick lived",
         b8 is not None and all(p3[c] is not None and p3[c] < 0.5 * b8 for c in champions), p3),
        (4, "for each champion the gain's fall to 0.55 costs more survival than the sweep does",
         all(p4[c]["gain_costs"] > p4[c]["sweep_costs"] for c in champions), p4),
    ]
    return [{"number": n, "text": text, "holds": bool(holds), "values": values} for n, text, holds, values in out]


def run(out: Path, workers: int, quick: bool) -> Dict[str, Any]:
    n_starts = 8 if quick else 100
    chunk = 4 if quick else CHUNK
    worlds = {world_name(s, g): (s, g, world(s, g, quick)) for s in SWEEPS for g in GAINS}
    out.mkdir(parents=True, exist_ok=True)
    settings = {"base": configure(quick).as_dict(), "cave_eta": CAVE.eta, "gains": GAINS, "sweeps": SWEEPS, "cells": CELLS, "costs": COSTS,
                "b5_tau": B5_TAU, "b8_tau": B8_TAU, "b8_aim_tau": probe.B8_AIM_TAU, "seed": SEED, "n_starts": n_starts, "chunk": chunk,
                "verdict": {"spending_at_least": SPENDING_SURVIVAL, "finding_below": FINDING_SURVIVAL}, "stage3b_survival": STAGE3B_SURVIVAL,
                "champions": {k: str(p) for k, (_, p) in stage3c_probe.CHAMPIONS.items()}, "quick": quick}
    manifest = build_manifest(protocol="stage4_thrift", settings=settings, seeds=[SEED], extra={"out": str(out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:7.1f}s {msg}", flush=True)

    starts = sample_starts(worlds[world_name(*STAGE4A)][2], "cave", n_starts, SEED)  # the same in every world (tested)
    chunks = [(lo, starts.take(range(lo, min(lo + chunk, n_starts)))) for lo in range(0, n_starts, chunk)]
    jobs = []
    for name, (sweep, gain, cfg) in worlds.items():
        for cell in CELLS:
            for cost in COSTS:
                if cell == "B0" and cost == "free":
                    continue  # B0 never beats: free beating changes nothing
                c = cfg if cost == "paid" else cfg.but(c1=0.0)
                jobs += [{"cfg": c, "starts": part, "spec": cell_spec(c, cell, len(part)), "world": name, "sweep": sweep, "gain": gain,
                          "cell": cell, "cost": cost, "first": lo} for lo, part in chunks]
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        results = list(pool.map(sim_job, jobs))
    log(f"{len(results)} runs done")

    rows: List[Dict[str, Any]] = []
    for key in dict.fromkeys(r["key"] for r in results):
        rows += [row for p in sorted((r for r in results if r["key"] == key), key=lambda p: p["first"]) for row in p["rows"]]
    table: Dict[str, Dict[str, Dict[str, Dict[str, Any]]]] = {}
    flat = []
    for name, (sweep, gain, cfg) in worlds.items():
        table[name] = {}
        for cell in CELLS:
            table[name][cell] = {}
            for cost in COSTS:
                mine = [r for r in rows if r["world"] == name and r["cell"] == cell and r["cost"] == (cost if cell != "B0" else "paid")]
                table[name][cell][cost] = summarise(mine)
                flat.append({"world": name, "sweep": int(sweep), "gain": gain, "cell": cell, "cost": cost, **table[name][cell][cost]})
        log(f"{name:11s} break-even daylight soak {break_even_day_light(cfg):.3f}; " + "; ".join(
            f"{c} {table[name][c]['paid']['survival']:.0%}/{table[name][c]['free']['survival']:.0%} "
            f"light {table[name][c]['paid']['day_light'] or 0:.3f} beat {table[name][c]['paid']['day_beat'] or 0:.3f}" for c in CELLS))
    found = verdicts(table)
    predictions = score_predictions(table)
    for cell, v in found.items():
        log(f"{cell}: in stage 4a's world survives {v['paid_survival']:.0%}, with beating free {v['free_survival']:.0%}: {v['verdict']}")
    for p in predictions:
        log(f"prediction {p['number']}: {'✓' if p['holds'] else '✗'} {p['text']}")
    write_csv(out / "per_start.csv", ROW_COLUMNS, rows)
    write_csv(out / "table.csv", tuple(flat[0]), flat)
    summary = {"worlds": table, "break_even_day_light": {n: break_even_day_light(w[2]) for n, w in worlds.items()},
               "verdicts": found, "predictions": predictions, "quick": quick}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=probe._json) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0, workers=workers, runs=len(jobs))
    write_manifest(out / "manifest.json", manifest)
    log(f"done, written to {out}")
    return summary


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    args = parser.parse_args(argv)
    return run(args.out, args.workers, args.quick)


if __name__ == "__main__":
    main(sys.argv[1:])
