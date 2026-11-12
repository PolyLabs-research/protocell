"""Stage 4e (docs/prereg/stage4e.md): a cell written by hand, weight by weight, to do B8's job in stage 4a's world.

    .venv/bin/python -m experiments.stage4e genome DESIGN.json                       # the design's genome, its ranges checked
    .venv/bin/python -m experiments.stage4e probe DESIGN.json step --level 1 --rise 0.02   # open loop, unlimited, logged
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage4e check DESIGN.json      # a world check: at most 50 a mode
    .venv/bin/python -m experiments.stage4e note --mode fourier1 "what the check taught"
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage4e judge DESIGN.json      # once a mode: 100 fresh starts

A design is a JSON file naming every part of the cell (§3): the wall's bias, time constant, sensory gain and ring
weights; the cilium angle; each of the 8 core neurons' bias, time constant and spokes in and out (a number in the
uniform mode, (a, b, c) for a + b cos theta + c sin theta in fourier1); and the core's links, as (from, to, weight).
Core neurons a design leaves out sit at bias -8 with no links: off. Every design carries ``why``: what it should do and
why, which the notebook takes down before its check runs (§4).

A world check runs one design closed loop in stage 4a's world on stage 4b's validation starts (seed 20, some or all of
24) with shared noise, as stage 4d validated; the tool counts the checks and refuses the 51st (§4). A probe runs the
network alone on light the probe makes up, with the sensors' noise from stream ``probe``: a calculator for one design,
unlimited but logged. The judge (§5): the submitted design, B8 and B0 on fresh starts 1-100 at seed 27; the share of the
gap from B0 to B8 closed, with a bootstrap interval (seed 28). Everything runs as one process (§8). Writes
docs/data/stage4e/<mode>/.
"""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from experiments import stage4_probe as probe_rules
from experiments import stage4_thrift as thrift
from experiments import stage4a
from experiments.stage4d import verdict
from protocell.cell import MODES, decode, genome_ranges, layout
from protocell.config import Config
from protocell.evolve import NOISE_CELL_ID
from protocell.manifest import build_manifest, finish_manifest, git_state, write_manifest
from protocell.rng import stream
from protocell.sim import Network, simulate
from protocell.tables import write_csv
from protocell.world import node_angles, sample_starts

VALIDATION_SEED = 20  # stage 4b's validation starts, as stage 4d validated on
JUDGE_SEED, BOOTSTRAP_SEED = 27, 28  # fresh
BUDGET = 50  # world checks a mode (§9, the owner's answer)
VALIDATION_STARTS, JUDGE_STARTS, CHUNK = 24, 100, 50
RESAMPLES = 10_000
STREAM_PROBE = "probe"
DEFAULT_OUT = Path("docs/data/stage4e")
CHECK_COLUMNS = ("check", "design", "sha", "starts", "fitness", "survival", "day_light", "day_beat", "night_beat", "reached",
                 "b8_fitness", "b8_survival", "b0_fitness", "tctl_before", "tctl_after", "seconds", "git", "dirty")
JUDGE_COLUMNS = ("cell", "start", "survived", "fitness", "day_light", "day_beat", "night_beat")


def world(quick: bool = False) -> Config:
    return stage4a.world(quick)


@dataclass(frozen=True)
class Stage:
    """Which test this is: stage 4e's, or a later stage running the same test on a changed cell (stage 5b)."""

    name: str
    world: Callable[[bool], Config]
    judge_seed: int
    bootstrap_seed: int
    out: Path


STAGE4E = Stage("stage4e", world, JUDGE_SEED, BOOTSTRAP_SEED, DEFAULT_OUT)


# --- designs ------------------------------------------------------------------------------------------------------------

class DesignError(ValueError):
    pass


def load(path: Path) -> Dict[str, Any]:
    d = json.loads(Path(path).read_text())
    if d.get("mode") not in MODES:
        raise DesignError(f"the design's mode is one of {MODES}")
    if not str(d.get("why", "")).strip():
        raise DesignError("a design says what it should do and why, before it runs (stage4e.md §4)")
    return d


def sha(design: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(design, sort_keys=True).encode()).hexdigest()[:12]


def _terms(value: Any, mode: str, what: str) -> List[float]:
    if mode == "uniform":
        if isinstance(value, (list, tuple)):
            raise DesignError(f"{what}: a uniform spoke is one number")
        return [float(value)]
    v = [float(x) for x in (value if isinstance(value, (list, tuple)) else [value, 0.0, 0.0])]
    if len(v) != 3:
        raise DesignError(f"{what}: a fourier1 spoke is (a, b, c)")
    return v


def genome(cfg: Config, design: Mapping[str, Any]) -> np.ndarray:
    """The design's genome, ``(G,)``, every gene checked against its range; raises DesignError naming each one out."""
    mode = design["mode"]
    lay = layout(cfg, mode)
    k = cfg.n_core
    g = np.zeros(lay.length)
    wall = design.get("wall", {})
    tau = float(wall.get("tau", 1.0))
    g[lay.ring] = [float(wall.get("self", 0.0)), float(wall.get("from_cw", 0.0)), float(wall.get("from_ccw", 0.0)),
                   float(wall.get("bias", -8.0)), math.log(tau) if tau > 0 else -math.inf, float(wall.get("gain", 0.0))]
    g[lay.alpha] = float(design.get("alpha", 0.0))
    core = list(design.get("core", []))
    if len(core) > k:
        raise DesignError(f"the core has {k} neurons")
    names = [c.get("name", f"c{j}") for j, c in enumerate(core)] + [f"off{j}" for j in range(len(core), k)]
    if len(set(names)) != k:
        raise DesignError("core neurons have distinct names")
    terms = lay.spoke_terms
    bias, log_tau = np.full(k, -8.0), np.zeros(k)
    s_in, s_out = np.zeros((k, terms)), np.zeros((k, terms))
    for j, c in enumerate(core):
        bias[j] = float(c.get("bias", -8.0))
        t = float(c.get("tau", 1.0))
        log_tau[j] = math.log(t) if t > 0 else -math.inf
        s_in[j] = _terms(c.get("in", 0.0), mode, f"{names[j]} in")
        s_out[j] = _terms(c.get("out", 0.0), mode, f"{names[j]} out")
    w = np.zeros((k, k))  # to j from l
    for link in design.get("links", []):
        src, dst, weight = link
        if src not in names or dst not in names:
            raise DesignError(f"link {link}: no core neuron by that name")
        w[names.index(dst), names.index(src)] += float(weight)
    g[lay.core_w] = w.reshape(-1)
    g[lay.core_bias] = bias
    g[lay.core_log_tau] = log_tau
    g[lay.spokes_in] = s_in.reshape(-1)
    g[lay.spokes_out] = s_out.reshape(-1)
    lo, hi = genome_ranges(cfg, mode)
    bad = np.flatnonzero((g < lo - 1e-12) | (g > hi + 1e-12) | ~np.isfinite(g))
    if bad.size:
        labels = gene_labels(cfg, mode, names)
        raise DesignError("out of range: " + "; ".join(f"{labels[i]} = {g[i]:.4g} (range {lo[i]:.4g} to {hi[i]:.4g})" for i in bad))
    return g


def gene_labels(cfg: Config, mode: str, names: Sequence[str]) -> List[str]:
    lay = layout(cfg, mode)
    labels = [""] * lay.length
    for j in range(cfg.n_core):
        for l in range(cfg.n_core):
            labels[lay.core_w.start + j * cfg.n_core + l] = f"link {names[l]}->{names[j]}"
        labels[lay.core_bias.start + j] = f"{names[j]} bias"
        labels[lay.core_log_tau.start + j] = f"{names[j]} log tau"
        for t in range(lay.spoke_terms):
            labels[lay.spokes_in.start + j * lay.spoke_terms + t] = f"{names[j]} in[{t}]"
            labels[lay.spokes_out.start + j * lay.spoke_terms + t] = f"{names[j]} out[{t}]"
    for i, n in enumerate(("wall self", "wall from_cw", "wall from_ccw", "wall bias", "wall log tau", "wall gain")):
        labels[lay.ring.start + i] = n
    labels[lay.alpha.start] = "alpha"
    return labels


def spec(cfg: Config, design: Mapping[str, Any], n: int) -> Dict[str, Any]:
    return {"controller": "network", "mode": design["mode"], "genomes": np.repeat(genome(cfg, design)[None], n, axis=0)}


# --- probes: the network alone on made-up light ---------------------------------------------------------------------------

def light_scenario(cfg: Config, kind: str, level: float, rise: float, contrast: float, angle: float, ticks: int, before: int) -> np.ndarray:
    """``(ticks, N)`` light: ``step`` holds ``level`` for ``before`` ticks, then ``level`` (1 + rise); ``ramp`` holds it,
    then grows by the factor (1 + rise) a tick, as a cell running toward the light sees; ``fall`` shrinks by it. Every
    tick the wall sees a gradient across the body: node i gets the mean times 1 + contrast cos(theta_i - angle), the
    brighter side at ``angle`` from the heading."""
    theta = node_angles(cfg)
    t = np.arange(ticks)
    if kind == "step":
        mean = np.where(t < before, level, level * (1.0 + rise))
    elif kind in ("ramp", "fall"):
        sign = 1.0 if kind == "ramp" else -1.0
        mean = level * np.where(t < before, 1.0, (1.0 + sign * rise) ** np.maximum(0, t - before + 1))
    elif kind == "hold":
        mean = np.full(ticks, level)
    else:
        raise ValueError(f"unknown scenario {kind!r}")
    return mean[:, None] * (1.0 + contrast * np.cos(theta[None, :] - angle))


def run_probe(cfg: Config, design: Mapping[str, Any], light: np.ndarray, noise: bool, seed: int = 0) -> Dict[str, np.ndarray]:
    """The network on ``light`` ``(T, N)``, one cell, from rest, stepped as the simulation steps it, with the sensors'
    noise (stream ``probe``) or without. Returns per tick: the mean beat, the forward and leftward pull (the cell's own
    frame, in units of v_max), the beats and the core's outputs."""
    return run_probe_genome(cfg, design["mode"], genome(cfg, design), light, noise, seed)


def run_probe_genome(cfg: Config, mode: str, g: np.ndarray, light: np.ndarray, noise: bool, seed: int = 0) -> Dict[str, np.ndarray]:
    """``run_probe`` for a genome that is not a design (an evolved cell)."""
    n = cfg.n_wall
    p = decode(cfg, mode, np.asarray(g)[None])
    net = Network(cfg, p)
    rng = stream(seed, STREAM_PROBE)
    angle = node_angles(cfg) + float(p.alpha[0])
    T = light.shape[0]
    beats, core = np.zeros((T, n)), np.zeros((T, cfg.n_core))
    for t in range(T):
        sensed = light[t][None] + (rng.normal(0.0, cfg.sensor_noise_sd, size=(1, n)) if noise else 0.0)
        beats[t] = net.beats(sensed, t)[0]
        core[t] = net.output[0, n:]
    pull = (math.pi / n) * beats
    return {"mean_beat": beats.mean(axis=1), "forward": (pull * np.cos(angle)).sum(axis=1), "left": (pull * np.sin(angle)).sum(axis=1),
            "beats": beats, "core": core}


def probe_table(result: Mapping[str, np.ndarray], light: np.ndarray, names: Sequence[str], every: int) -> List[str]:
    rows = [f"{'tick':>6} {'light':>8} {'beat':>7} {'fwd':>7} {'left':>7}  " + " ".join(f"{x[:6]:>6}" for x in names)]
    T = light.shape[0]
    for t in sorted(set(list(range(0, T, every)) + [T - 1])):
        rows.append(f"{t:6d} {light[t].mean():8.4f} {result['mean_beat'][t]:7.4f} {result['forward'][t]:7.4f} {result['left'][t]:7.4f}  "
                    + " ".join(f"{x:6.3f}" for x in result["core"][t][:len(names)]))
    return rows


# --- world checks and the notebook ----------------------------------------------------------------------------------------

def tctl() -> Optional[float]:
    for h in Path("/sys/class/hwmon").glob("hwmon*"):
        try:
            if (h / "name").read_text().strip() == "k10temp":
                return int((h / "temp1_input").read_text()) / 1000.0
        except OSError:
            continue
    return None


def _append(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())


def _rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    import csv
    with path.open() as f:
        return list(csv.DictReader(f))


class Tracer:
    """An observer that keeps, every ``every`` ticks, each cell's place, the mean light on its wall, its mean beat, its
    core's outputs and whether it lives: the trace a check may record (stage4e.md §4)."""

    def __init__(self, every: int) -> None:
        self.every = every
        self.rows: Dict[str, List[np.ndarray]] = {k: [] for k in ("tick", "pos", "light", "beat", "core", "alive")}

    def __call__(self, t: int, state: Mapping[str, Any]) -> None:
        if t % self.every:
            return
        n = state["beats"].shape[1]
        self.rows["tick"].append(np.array(t))
        self.rows["pos"].append(state["pos"].copy())
        self.rows["light"].append(state["light"].mean(axis=1))
        self.rows["beat"].append(state["beats"].mean(axis=1))
        self.rows["core"].append(state["controller"].output[:, n:].copy())
        self.rows["alive"].append(state["alive"].copy())

    def arrays(self) -> Dict[str, np.ndarray]:
        return {k: np.stack(v) for k, v in self.rows.items()}


def run_cells(cfg: Config, starts, specs: Mapping[str, Mapping[str, Any]], seed: int, trace_every: int = 0) -> Dict[str, Dict[str, np.ndarray]]:
    """Each named controller on the starts, as one batch each, with shared noise and the thrift probe's ledger (and, with
    ``trace_every``, the trace)."""
    out = {}
    for name, s in specs.items():
        ledger = thrift.Ledger(cfg, len(starts))
        tracer = Tracer(trace_every) if trace_every else None

        def observe(t: int, state: Mapping[str, Any], ledger=ledger, tracer=tracer) -> None:
            ledger(t, state)
            if tracer is not None:
                tracer(t, state)
        r = simulate(cfg, starts, s, seed=seed, cell_ids=[NOISE_CELL_ID] * len(starts), observe=observe)
        out[name] = {"fitness": r.fitness, "survived": r.survived.astype(float), "day_light": thrift._per(ledger.day_soak, ledger.day_ticks),
                     "day_beat": thrift._per(ledger.day_beat, ledger.day_ticks), "night_beat": thrift._per(ledger.night_beat, ledger.night_ticks),
                     "reached": (r.reach_tick >= 0).astype(float), "start": starts.index.copy()}
        if tracer is not None:
            out[name]["trace"] = tracer.arrays()
    return out


def _mean(x: np.ndarray) -> float:
    return float(np.nanmean(x)) if np.isfinite(x).any() else math.nan


def reference(cfg: Config, out: Path, quick: bool) -> Dict[str, Any]:
    """B8 and B0 on the validation starts, once a mode (not a check): what every check is read against."""
    path = out / "reference.json"
    if path.exists():
        return json.loads(path.read_text())
    starts = sample_starts(cfg, "cave", 4 if quick else VALIDATION_STARTS, VALIDATION_SEED)
    r = run_cells(cfg, starts, {"B8": thrift.cell_spec(cfg, "B8", len(starts)), "B0": thrift.cell_spec(cfg, "B0", len(starts))}, VALIDATION_SEED)
    ref = {name: {"per_start": {k: v.tolist() for k, v in cells.items()}} for name, cells in r.items()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ref, indent=1, default=probe_rules._json) + "\n")
    return ref


def check(design_path: Path, out_root: Path, starts_wanted: Optional[Sequence[int]], quick: bool, budget: int = BUDGET,
          require_clean: bool = True, trace_every: int = 0, stage: Stage = STAGE4E) -> Dict[str, Any]:
    design = load(design_path)
    mode = design["mode"]
    cfg = stage.world(quick)
    genome(cfg, design)  # refuses a design out of range before it costs a check
    out = out_root / mode
    git = git_state()
    if require_clean and git["dirty"]:
        raise SystemExit("refusing: the tree has tracked changes (a check's record names the code it ran)")
    done = _rows(out / "checks.csv")
    if len(done) >= budget:
        raise SystemExit(f"refusing: {mode} has used all {budget} world checks")
    number = len(done) + 1
    n_all = 4 if quick else VALIDATION_STARTS
    wanted = list(range(1, n_all + 1)) if not starts_wanted else sorted(set(int(s) for s in starts_wanted))
    if any(not 1 <= s <= n_all for s in wanted):
        raise SystemExit(f"the validation starts are 1-{n_all}")
    ref = reference(cfg, out, quick)
    h = sha(design)
    (out / "checks").mkdir(parents=True, exist_ok=True)
    (out / "checks" / f"{number:02d}-{design_path.stem}-{h}.json").write_text(json.dumps(design, indent=1) + "\n")
    _append(out / "notebook.md", f"\n### Check {number}: `{design_path.name}` ({h}), starts {_span(wanted)}\n\n"
            f"**Why, written before it ran:** {design['why'].strip()}\n\n")
    t0, before = time.time(), tctl()
    starts = sample_starts(cfg, "cave", n_all, VALIDATION_SEED).numbered(wanted)
    r = run_cells(cfg, starts, {"cell": spec(cfg, design, len(starts))}, VALIDATION_SEED, trace_every)["cell"]
    if "trace" in r:
        np.savez_compressed(out / "checks" / f"{number:02d}-trace.npz", start=np.array(wanted), every=trace_every, **r.pop("trace"))
    idx = [s - 1 for s in wanted]
    b8 = {k: np.array(v)[idx] for k, v in ref["B8"]["per_start"].items()}
    b0 = {k: np.array(v)[idx] for k, v in ref["B0"]["per_start"].items()}
    row = {"check": number, "design": design_path.name, "sha": h, "starts": _span(wanted), "fitness": float(r["fitness"].mean()),
           "survival": float(r["survived"].mean()), "day_light": _mean(r["day_light"]), "day_beat": _mean(r["day_beat"]),
           "night_beat": _mean(r["night_beat"]), "reached": float(r["reached"].mean()), "b8_fitness": float(b8["fitness"].mean()),
           "b8_survival": float(b8["survived"].mean()), "b0_fitness": float(b0["fitness"].mean()), "tctl_before": before,
           "tctl_after": tctl(), "seconds": round(time.time() - t0, 1), "git": git["sha"][:7], "dirty": git["dirty"]}
    write_csv(out / "checks.csv", CHECK_COLUMNS, done + [row])
    per = _rows(out / "checks_per_start.csv")
    per += [{"check": number, "start": int(s), **{k: float(r[k][i]) for k in ("fitness", "survived", "day_light", "day_beat", "night_beat", "reached")}}
            for i, s in enumerate(wanted)]
    write_csv(out / "checks_per_start.csv", ("check", "start", "fitness", "survived", "day_light", "day_beat", "night_beat", "reached"), per)
    gap = (row["fitness"] - row["b0_fitness"]) / (row["b8_fitness"] - row["b0_fitness"]) if row["b8_fitness"] != row["b0_fitness"] else math.nan
    _append(out / "notebook.md", "| | this design | B8 | B0 |\n|---|---|---|---|\n"
            f"| fitness | {row['fitness']:.3f} | {row['b8_fitness']:.3f} | {row['b0_fitness']:.3f} |\n"
            f"| survival | {row['survival']:.0%} | {row['b8_survival']:.0%} | 0% |\n"
            f"| light per daylight tick | {row['day_light']:.3f} | {_mean(b8['day_light']):.3f} | {_mean(b0['day_light']):.3f} |\n"
            f"| beat by day / night | {row['day_beat']:.3f} / {row['night_beat']:.3f} | {_mean(b8['day_beat']):.3f} / 0 | 0 / 0 |\n"
            f"| reached the soak region | {row['reached']:.0%} | {_mean(b8['reached']):.0%} | {_mean(b0['reached']):.0%} |\n\n"
            f"Share of the gap from B0 to B8 on these starts: {gap:.2f}. Check {number} of {budget}; {row['seconds']:.0f} s; "
            f"code {row['git']}.\n")
    return {**row, "gap": gap, "remaining": budget - number}


def _span(starts: Sequence[int]) -> str:
    s = list(starts)
    return f"{s[0]}-{s[-1]}" if s == list(range(s[0], s[-1] + 1)) else ",".join(map(str, s))


def note(out_root: Path, mode: str, text: str) -> None:
    _append(out_root / mode / "notebook.md", f"\n**Learnt ({time.strftime('%Y-%m-%d %H:%M', time.gmtime())} UTC):** {text.strip()}\n")


# --- the judge (§5) -------------------------------------------------------------------------------------------------------

def judge(design_path: Path, out_root: Path, quick: bool, require_clean: bool = True, stage: Stage = STAGE4E) -> Dict[str, Any]:
    design = load(design_path)
    mode = design["mode"]
    cfg = stage.world(quick)
    out = out_root / mode
    if (out / "summary.json").exists():
        raise SystemExit(f"refusing: {mode} has been judged; one submission a mode")
    git = git_state()
    if require_clean and git["dirty"]:
        raise SystemExit("refusing: the tree has tracked changes")
    n = 8 if quick else JUDGE_STARTS
    chunk = 4 if quick else CHUNK
    settings = {"world": cfg.as_dict(), "mode": mode, "design": design, "design_sha": sha(design), "genome": genome(cfg, design).tolist(),
                "judge_seed": stage.judge_seed, "bootstrap_seed": stage.bootstrap_seed, "n_starts": n, "b8": {"tau": thrift.B8_TAU, "aim_tau": probe_rules.B8_AIM_TAU},
                "checks_used": len(_rows(out / "checks.csv")), "quick": quick}
    manifest = build_manifest(protocol=stage.name, settings=settings, seeds=[stage.judge_seed, stage.bootstrap_seed], extra={"out": str(out)})
    t0 = time.time()
    starts = sample_starts(cfg, "cave", n, stage.judge_seed)
    rows: List[Dict[str, Any]] = []
    cols: Dict[str, Dict[str, List[np.ndarray]]] = {}
    for lo in range(0, n, chunk):
        part = starts.take(range(lo, min(lo + chunk, n)))
        specs = {"written": spec(cfg, design, len(part)), "B8": thrift.cell_spec(cfg, "B8", len(part)), "B0": thrift.cell_spec(cfg, "B0", len(part))}
        for name, r in run_cells(cfg, part, specs, stage.judge_seed).items():
            for k, v in r.items():
                cols.setdefault(name, {}).setdefault(k, []).append(v)
    col = {name: {k: np.concatenate(v) for k, v in c.items()} for name, c in cols.items()}
    for name, c in col.items():
        rows += [{"cell": name, "start": int(c["start"][i]), "survived": int(c["survived"][i]), "fitness": float(c["fitness"][i]),
                  "day_light": float(c["day_light"][i]), "day_beat": float(c["day_beat"][i]), "night_beat": float(c["night_beat"][i])}
                 for i in range(n)]
    share, lo_, hi_ = _gap_share(col["written"]["fitness"], col["B8"]["fitness"], col["B0"]["fitness"], 200 if quick else RESAMPLES, MODES.index(mode) + 1,
                                 stage.bootstrap_seed)
    cells = {name: {"fitness": float(c["fitness"].mean()), "survival": float(c["survived"].mean()), "day_light": _mean(c["day_light"]),
                    "day_beat": _mean(c["day_beat"]), "night_beat": _mean(c["night_beat"])} for name, c in col.items()}
    beats_b8 = share > 1.0 and lo_ > 1.0
    summary = {"mode": mode, "design": design_path.name, "design_sha": sha(design), "checks_used": settings["checks_used"], "cells": cells,
               "gap_share": share, "gap_low": lo_, "gap_high": hi_, "verdict": verdict(share), "beats_b8": beats_b8, "quick": quick}
    write_csv(out / "judge.csv", JUDGE_COLUMNS, rows)
    (out / "submitted.json").write_text(json.dumps(design, indent=1) + "\n")
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=probe_rules._json) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0)
    write_manifest(out / "manifest.json", manifest)
    return summary


def _gap_share(cell: np.ndarray, b8: np.ndarray, b0: np.ndarray, resamples: int, key: int,
               seed: int = BOOTSTRAP_SEED) -> Tuple[float, float, float]:
    """Stage 4d's measure (``experiments.stage4d.gap_share``) with the stage's own bootstrap seed."""
    def share(idx: np.ndarray) -> np.ndarray:
        return (cell[idx].mean(axis=-1) - b0[idx].mean(axis=-1)) / (b8[idx].mean(axis=-1) - b0[idx].mean(axis=-1))
    point = float(share(np.arange(cell.shape[0])))
    idx = stream(seed, "bootstrap", (key,)).integers(0, cell.shape[0], size=(resamples, cell.shape[0]))
    boot = share(idx)
    return point, float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))


# --- the command line -----------------------------------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None, stage: Stage = STAGE4E) -> Any:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=stage.out)
    parser.add_argument("--quick", action="store_true", help="the smoke test's 2,000-tick day: not a result")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("genome")
    p.add_argument("design", type=Path)
    p = sub.add_parser("probe")
    p.add_argument("design", type=Path)
    p.add_argument("scenario", choices=("step", "ramp", "fall", "hold"))
    p.add_argument("--level", type=float, default=1.0)
    p.add_argument("--rise", type=float, default=0.01)
    p.add_argument("--contrast", type=float, default=0.0)
    p.add_argument("--angle", type=float, default=0.0, help="degrees from the heading, anticlockwise")
    p.add_argument("--ticks", type=int, default=300)
    p.add_argument("--before", type=int, default=150)
    p.add_argument("--every", type=int, default=25)
    p.add_argument("--noise", action="store_true")
    p = sub.add_parser("check")
    p.add_argument("design", type=Path)
    p.add_argument("--starts", type=int, nargs="+")
    p.add_argument("--trace", type=int, default=0, help="record the trace every this many ticks (the same check)")
    p = sub.add_parser("note")
    p.add_argument("--mode", choices=MODES, required=True)
    p.add_argument("text")
    p = sub.add_parser("judge")
    p.add_argument("design", type=Path)
    args = parser.parse_args(argv)
    cfg = stage.world(args.quick)
    if args.command == "genome":
        design = load(args.design)
        g = genome(cfg, design)
        names = [c.get("name", f"c{j}") for j, c in enumerate(design.get("core", []))]
        names += [f"off{j}" for j in range(len(names), cfg.n_core)]
        for label, x in zip(gene_labels(cfg, design["mode"], names), g):
            if x != 0.0:
                print(f"{label:24s} {x: .4f}")
        return g
    if args.command == "probe":
        design = load(args.design)
        light = light_scenario(cfg, args.scenario, args.level, args.rise, args.contrast, math.radians(args.angle), args.ticks, args.before)
        result = run_probe(cfg, design, light, args.noise)
        names = [c.get("name", f"c{j}") for j, c in enumerate(design.get("core", []))]
        lines = probe_table(result, light, names, args.every) if args.every > 0 else []
        cut = min(args.before, args.ticks)
        spans = []  # the log keeps each part's means, not only the last tick, which can catch a pause in a run
        for label, sl in (("before", slice(0, cut)), ("after", slice(cut, args.ticks))):
            if sl.stop > sl.start:
                lines.append(f"{label:6s}: mean beat {result['mean_beat'][sl].mean():.4f}, forward {result['forward'][sl].mean():+.4f}, "
                             f"running (forward > 0.25) {np.mean(result['forward'][sl] > 0.25):.0%}, core " +
                             " ".join(f"{n}={v:.3f}" for n, v in zip(names, result["core"][sl].mean(axis=0))))
                spans.append(f"; {label} mean beat {result['mean_beat'][sl].mean():.4f} forward {result['forward'][sl].mean():+.4f} "
                             f"running {np.mean(result['forward'][sl] > 0.25):.0%}")
        print("\n".join(lines))
        _append(args.out / design["mode"] / "probes.log", f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {args.design.name} ({sha(design)}) "
                f"{args.scenario} level {args.level} rise {args.rise} contrast {args.contrast} angle {args.angle} ticks {args.ticks} before {args.before} "
                f"noise {args.noise}: final beat {result['mean_beat'][-1]:.4f} forward {result['forward'][-1]:.4f} left {result['left'][-1]:.4f}"
                + "".join(spans) + "\n")
        return result
    if args.command == "check":
        r = check(args.design, args.out, args.starts, args.quick, trace_every=args.trace, stage=stage)
        print(f"check {r['check']} ({r['remaining']} left): fitness {r['fitness']:.3f} (B8 {r['b8_fitness']:.3f}, B0 {r['b0_fitness']:.3f}), "
              f"survival {r['survival']:.0%}, gap share {r['gap']:.2f}, day light {r['day_light']:.3f}, day beat {r['day_beat']:.3f}, "
              f"night beat {r['night_beat']:.3f}, reached {r['reached']:.0%} [{r['seconds']:.0f} s]")
        return r
    if args.command == "note":
        note(args.out, args.mode, args.text)
        return None
    s = judge(args.design, args.out, args.quick, stage=stage)
    c = s["cells"]
    print(f"judge {s['mode']}: written {c['written']['fitness']:.3f} ({c['written']['survival']:.0%}), B8 {c['B8']['fitness']:.3f}, "
          f"B0 {c['B0']['fitness']:.3f}; closes {s['gap_share']:.3f} [{s['gap_low']:.3f}, {s['gap_high']:.3f}]: {s['verdict']}"
          + (" and beats B8" if s["beats_b8"] else ""))
    return s


if __name__ == "__main__":
    main(sys.argv[1:])
