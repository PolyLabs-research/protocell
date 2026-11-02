"""Replays: run up to three cells from one start of the cave pool and write a self-contained HTML page that plays
their lifetimes back. The page shows the pool with its light and each cell's track, the chosen cell's body (the light
at each wall node, each cilium's beat, the core's activity), and the reserve and damage over the lifetime.

    .venv/bin/python -m tools.replay --config burn --start 51 --cells b0 b2r b2rr
    .venv/bin/python -m tools.replay --config day --start 57 --cells b2r genome:fourier1:17 --stride 5

Cells:
  b0                 the still cell
  b1                 random beating
  b2:K               the plain reflex at gain K
  b5[:TAU]           run and wait (stage 3a's bar), its memory's time constant TAU s (default: stage 3a's choice)
  b2r[:K], b2rr[:K]  the reflex that rests in the dark, and the one that also retreats above the damage threshold;
                     without K, the gain the checks chose for the configuration (docs/data/cave/<config>/summary.json)
  genome:MODE:G      random genome G (1-based) of the cave's B3 at its seed, MODE uniform or fourier1
  file:MODE:PATH[:ROW]  a genome from a .npy file (one genome per row): stage 1's evolved cells

A replay reruns the cells with the code, seed and noise keys the checks use, so a cell's outcome is its row in the
checks' tables. It is a record to look at, not a result, and is written to ``replays/`` (untracked). Open the page in
a browser; nothing else is needed.
"""

from __future__ import annotations

import argparse
import base64
import json
import math
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from experiments.cave import CONFIGURATIONS, SEED, configure
from protocell.cell import STREAM_GENOMES, genome_length, random_genomes
from protocell.config import Config
from protocell.manifest import git_state
from protocell.rng import stream
from protocell.sim import BURNT, STARVED, simulate
from protocell.world import Starts, daylight, lifetimes, mouth_angle, sample_starts
from tools import pages

MAX_CELLS = 3  # the pool view's colours are validated for three at once
DEFAULT_STRIDE = 10
DATA_DIR = Path("docs/data/cave")
OUT_DIR = Path("replays")
REPLAY_VERSION = 1


@dataclass(frozen=True)
class CellSpec:
    """One cell to replay: its label, its controller spec, the id that keys its noise, and what it is."""

    label: str
    short: str
    spec: Dict[str, Any] = field(hash=False)
    cell_id: int
    kind: str


TRANSLUCENT = "translucent"  # stage 3's world (docs/prereg/stage3.md): the cave's day with the cell translucent
STAGE3_SUMMARY = Path("docs/data/stage3/summary.json")


def world(config: str, quick: bool) -> "tuple[Config, int]":
    """The world a replay runs in and the seed of its starts and noise: one of the cave's four configurations (the
    cave's starts, seed 2), or the translucent cell's (stage 3a's starts, seed 8)."""
    if config == TRANSLUCENT:
        from experiments import stage3

        return stage3.configure(quick), stage3.SEED
    return configure(config, quick), SEED


def _checks_gain(config: str, which: str, data_dir: Path) -> float:
    if config == TRANSLUCENT:
        if not STAGE3_SUMMARY.exists():
            raise SystemExit(f"stage 3a's checks have not run ({STAGE3_SUMMARY} is missing): give the value, as {which}:X")
        s = json.loads(STAGE3_SUMMARY.read_text())
        if which == "b5":
            return float(s["bar"]["tau"])
        if which == "b2r":
            return float(s["checks"]["T4"]["b2r"]["k"])
        raise SystemExit(f"{which} does not run in the translucent world")
    path = data_dir / config / "summary.json"
    if not path.exists():
        raise SystemExit(f"no checks have run for {config!r} ({path} is missing): give the gain, as {which}:K")
    checks = json.loads(path.read_text())["checks"]
    if which == "b2r":
        return float(checks["K4"]["bar"]["k"])
    if "b2rr" not in checks["K7"]:
        raise SystemExit(f"B2rr does not run in {config!r}, where damage is off")
    return float(checks["K7"]["b2rr"]["k"])


def parse_cell(text: str, cfg: Config, config: str, *, seed: int = SEED, data_dir: Path = DATA_DIR) -> CellSpec:
    """A cell from its command-line form (see the module's docstring)."""
    parts = text.split(":")
    head = parts[0]
    if head == "b0" and len(parts) == 1:
        return CellSpec("B0 still", "B0", {"controller": "still"}, 0, "still")
    if head == "b1" and len(parts) == 1:
        return CellSpec("B1 random beating", "B1", {"controller": "random"}, 0, "random")
    if head == "b2" and len(parts) == 2:
        k = float(parts[1])
        return CellSpec(f"B2 reflex, k = {k:g}", "B2", {"controller": "reflex", "k": k}, 0, "reflex")
    if head in ("b2r", "b2rr") and len(parts) <= 2:
        k = float(parts[1]) if len(parts) == 2 else _checks_gain(config, head, data_dir)
        spec: Dict[str, Any] = {"controller": "reflex", "k": k, "rest_below": cfg.rest_below}
        if head == "b2rr":
            if not math.isfinite(cfg.damage_threshold):
                raise SystemExit(f"B2rr retreats above the damage threshold, and {config!r} has none")
            spec["retreat_above"] = cfg.damage_threshold
            spec["retreat_on"] = cfg.retreat_on
            return CellSpec(f"B2rr rests and retreats, k = {k:g}", "B2rr", spec, 0, "reflex")
        return CellSpec(f"B2r rests in the dark, k = {k:g}", "B2r", spec, 0, "reflex")
    if head == "b5" and len(parts) <= 2:
        tau = float(parts[1]) if len(parts) == 2 else _checks_gain(config, "b5", data_dir)
        return CellSpec(f"B5 run and wait, memory {tau:g} s", "B5", {"controller": "runwait", "tau": tau, "rest_below": cfg.rest_below}, 0, "runwait")
    if head == "genome" and len(parts) == 3:
        mode, g = parts[1], int(parts[2])
        if g < 1:
            raise SystemExit("genomes are numbered from 1")
        genome = random_genomes(cfg, mode, g, stream(seed, STREAM_GENOMES))[g - 1:g]
        return CellSpec(f"random {mode} genome {g}", f"G{g}", {"controller": "network", "mode": mode, "genomes": genome}, g, "network")
    if head == "file" and len(parts) in (3, 4):
        mode, path = parts[1], Path(parts[2])
        row = int(parts[3]) if len(parts) == 4 else 0
        genomes = np.load(path)
        genome = np.asarray(genomes[row:row + 1], dtype=np.float64)
        if genome.shape != (1, genome_length(cfg, mode)):
            raise SystemExit(f"{path} row {row}: not a {mode} genome of {genome_length(cfg, mode)} numbers")
        if path.stem == "champion":  # a stage 1 run's champion: named by its run (docs/data/stage1/PHASE/MODE-SEED/)
            label, short = f"evolved {path.parent.name} ({path.parent.parent.name})", f"{mode[0].upper()}{path.parent.name.rsplit('-', 1)[-1]}"
        else:
            label, short = f"{path.stem} row {row} ({mode})", f"E{row}"
        return CellSpec(label, short, {"controller": "network", "mode": mode, "genomes": genome}, row + 1, "network")
    raise SystemExit(f"cannot read the cell {text!r}; see --help")


class Frames:
    """An observer that keeps every ``stride``-th tick of a one-cell run, and its last tick."""

    def __init__(self, cfg: Config, stride: int, last: int) -> None:
        self.n_wall = cfg.n_wall
        self.stride = stride
        self.last = last
        self.rows: Dict[str, List[Any]] = {k: [] for k in ("tick", "x", "y", "heading", "energy", "damage", "beats", "light", "core", "alive")}

    def __call__(self, t: int, s: Mapping[str, Any]) -> None:
        if t % self.stride and t != self.last:
            return
        r = self.rows
        r["tick"].append(t)
        r["x"].append(float(s["pos"][0, 0]))
        r["y"].append(float(s["pos"][0, 1]))
        r["heading"].append(float(s["heading"][0]))
        r["energy"].append(float(s["energy"][0]))
        r["damage"].append(float(s["damage"][0]))
        r["beats"].append(np.array(s["beats"][0], dtype=np.float64))
        r["light"].append(np.array(s["light"][0], dtype=np.float64))
        output = getattr(s["controller"], "output", None)
        r["core"].append(None if output is None else np.array(output[0, self.n_wall:], dtype=np.float64))
        r["alive"].append(bool(s["alive"][0]))


def _b64(values: Any, dtype: str) -> str:
    return base64.b64encode(np.ascontiguousarray(values, dtype=dtype).tobytes()).decode("ascii")


def _finite(x: float) -> Optional[float]:
    return None if x is None or not math.isfinite(x) else float(x)


def record(cfg: Config, config: str, starts: Starts, cells: Sequence[CellSpec], *, seed: int = SEED, stride: int = DEFAULT_STRIDE,
           ticks: Optional[int] = None) -> Dict[str, Any]:
    """Run each cell alone from the one start and keep its frames; the replay's data, ready for the page."""
    if len(starts) != 1 or starts.kind != "cave":
        raise ValueError("a replay is one start of the cave")
    if not 1 <= len(cells) <= MAX_CELLS:
        raise ValueError(f"a replay holds one to {MAX_CELLS} cells")
    if stride < 1:
        raise ValueError("the stride is at least one tick")
    lifetime = int(lifetimes(cfg, starts)[0]) if ticks is None else int(ticks)
    light_scale = cfg.mouth_light / 65535.0
    out_cells: List[Dict[str, Any]] = []
    tick = None
    for c in cells:
        frames = Frames(cfg, stride, lifetime - 1)
        result = simulate(cfg, starts, c.spec, seed=seed, cell_ids=[c.cell_id], ticks=ticks, observe=frames)
        r = frames.rows
        if tick is None:
            tick = np.array(r["tick"], dtype=np.int64)
        beats = np.clip(np.rint(np.array(r["beats"]) * 255.0), 0, 255)
        light = np.clip(np.rint(np.array(r["light"]) / light_scale), 0, 65535)
        core = None if r["core"][0] is None else _b64(np.clip(np.rint(np.array(r["core"]) * 255.0), 0, 255), "u1")
        cause = {0: None, STARVED: "starved", BURNT: "burnt"}[int(result.death_cause[0])]
        out_cells.append({
            "label": c.label, "short": c.short, "kind": c.kind, "cell_id": c.cell_id,
            "alpha": _alpha_of(cfg, c),
            "x": _b64(r["x"], "<f4"), "y": _b64(r["y"], "<f4"), "heading": _b64(r["heading"], "<f4"),
            "energy": _b64(r["energy"], "<f4"), "damage": _b64(r["damage"], "<f4"), "alive": _b64(r["alive"], "u1"),
            "beats": _b64(beats, "u1"), "light": _b64(light, "<u2"), "core": core,
            "summary": {"survived": bool(result.survived[0]), "death_tick": int(result.death_tick[0]), "death_cause": cause,
                        "fitness": float(result.fitness[0]), "light_soaked": float(result.light_soaked[0]),
                        "mean_beat": float(result.mean_beat[0]), "night_beat": _finite(float(result.night_beat[0])),
                        "burn_share": float(result.burn_share[0]), "soak_share": float(result.soak_share[0]),
                        "final_energy": float(result.final_energy[0]), "final_damage": float(result.final_damage[0])},
        })
    assert tick is not None
    times = starts.phase[0] + tick
    git = git_state()
    return {
        "version": REPLAY_VERSION, "configuration": config,
        "world": {"pool_radius": cfg.dish_radius, "clamp_radius": cfg.clamp_radius, "mouth_light": cfg.mouth_light,
                  "falloff": cfg.cave_falloff, "cycle": cfg.cave_cycle, "sweep": cfg.cave_sweep, "sweep_deg": cfg.cave_sweep_deg,
                  "day_ticks": cfg.day_ticks, "damage_threshold": _finite(cfg.damage_threshold), "soak_threshold": cfg.soak_threshold,
                  "shade_floor": cfg.shade_floor, "n_wall": cfg.n_wall, "n_core": cfg.n_core, "v_max": cfg.v_max,
                  "omega_max": cfg.omega_max, "rest_below": cfg.rest_below},
        "start": {"number": int(starts.index[0]), "phase": int(starts.phase[0]), "x": float(starts.pos[0, 0]),
                  "y": float(starts.pos[0, 1]), "heading": float(starts.heading[0]), "lifetime": lifetime},
        "frames": int(tick.shape[0]), "stride": stride, "light_scale": light_scale,
        "tick": _b64(tick, "<i4"), "daylight": _b64(daylight(cfg, times), "<f4"), "mouth_angle": _b64(mouth_angle(cfg, times), "<f4"),
        "cells": out_cells,
        "provenance": {"seed": seed, "sha": git["sha"], "dirty": git["dirty"], "command": " ".join(sys.argv),
                       "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
    }


def _alpha_of(cfg: Config, c: CellSpec) -> float:
    """The cell's cilium angle: 0 for the baselines; a network cell's from its genome."""
    if c.kind != "network":
        return 0.0
    from protocell.cell import decode

    return float(decode(cfg, c.spec["mode"], c.spec["genomes"]).alpha[0])


def write_page(replay: Mapping[str, Any], path: Path, *, fragment: bool = False) -> Path:
    return pages.write(path, "replay.html", replay, fragment=fragment)


def main(argv: Optional[Sequence[str]] = None) -> Path:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0], epilog=__doc__.split("\n\n", 2)[2],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="burn", choices=[*CONFIGURATIONS, TRANSLUCENT])
    parser.add_argument("--start", type=int, default=51, help="the start's number (1-based), from the world's check starts")
    parser.add_argument("--cells", nargs="+", default=["b0", "b2r", "b2rr"])
    parser.add_argument("--stride", type=int, default=DEFAULT_STRIDE, help="keep every n-th tick (1 s each)")
    parser.add_argument("--ticks", type=int, default=None, help="stop after this many ticks (default: the whole lifetime)")
    parser.add_argument("--quick", action="store_true", help="the smoke test's 2,000-tick day")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--fragment", action="store_true", help="write the page without its document skeleton (for publishing)")
    args = parser.parse_args(argv)
    cfg, seed = world(args.config, args.quick)
    starts = sample_starts(cfg, "cave", args.start, seed).numbered([args.start])
    cells = [parse_cell(text, cfg, args.config, seed=seed) for text in args.cells]
    replay = record(cfg, args.config, starts, cells, seed=seed, stride=args.stride, ticks=args.ticks)
    out = args.out or OUT_DIR / f"{args.config}-start{args.start}-{'-'.join(c.short for c in cells)}.html"
    write_page(replay, out, fragment=args.fragment)
    for c in replay["cells"]:
        s = c["summary"]
        fate = "survived" if s["survived"] else f"{s['death_cause']} at tick {s['death_tick']}"
        print(f"{c['label']}: {fate}, fitness {s['fitness']:.3f}")
    print(f"{replay['frames']} frames, written to {out} ({out.stat().st_size / 1e6:.1f} MB)")
    return out


if __name__ == "__main__":
    main(sys.argv[1:])
