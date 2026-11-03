"""Stage 3c's design probe (docs/decisions.md D12): how uniform champion 2203, a cell with no front, finds the light.

    .venv/bin/python -W error::RuntimeWarning -m experiments.stage3c_probe --workers 16
    .venv/bin/python -m experiments.stage3c_probe --quick --out /tmp/s3cp --workers 2   # the smoke test: not a result

Three parts, in stage 3's translucent world (docs/prereg/stage3.md), on fresh starts (seed 13):

A. **Movement.** The champion, the other working champion (fourier1 3202), B5 and B2r on starts 1-100, with shared
   noise. Each tick of each cell is *parked* (its mean beat above 0.9), *running* (otherwise, when the first Fourier
   mode of its beats, m1 = sum g_i e^(i theta_i), has modulus above 1: more than one node's worth of beating on one
   side) or *idle*. The cell's thrust points along heading + alpha + arg m1 (``protocell/motion.py``). For each cell:
   the time budget by the light it is in; every run of at least 3 ticks, with the light where it began, its duration
   and the angle between its direction at its third tick and the direction to the mouth; and over consecutive running
   ticks, how fast the body spins and the beating creeps around the wall.
B. **The tethered cell.** A network held in place with its heading fixed, fed light that is the same at every node
   (each level for 3 hours, the first 2 to settle; with and without the sensor noise, stream ``tether``), or the
   champion's network fed light brighter by a fraction eps toward one side (a direction per replicate, stream
   ``tether_angles``; 1 hour to settle, 3 measured). Read: the beating, the runs and their creep at each level, and how
   far runs start toward the brighter side at each eps.
C. **Readability recomputed.** Stage 3a's T2 called the direction readable at once where the light's spread over the
   wall (the brightest node less the dimmest) is at least 3 times one node's noise sigma. A cell can read every node
   at once: the light's first Fourier mode over the wall, z = (2/N) sum I_i e^(i theta_i), carries noise of SD
   sigma sqrt(2/N) in each component, and holding still for k ticks divides that by sqrt(k). At noon at the 100 starts'
   places: the share readable by T2's criterion, by |z| at least 3 times its noise in one tick, and over 10 ticks.

Nothing here is a test: the probe's findings become stage 3c's preregistered predictions. Writes
``docs/data/stage3c/probe/``.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from experiments.cave import RUN_COLUMNS, run_summary
from experiments.stage3 import configure, reflex, runwait
from protocell.cell import RING_NAMES, decode, layout
from protocell.config import Config
from protocell.evolve import NOISE_CELL_ID
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.rng import stream
from protocell.sim import CellNoise, Network, simulate
from protocell.tables import write_csv
from protocell.world import Starts, mouth_position, node_angles, node_light, sample_starts

SEED = 13  # fresh: no start, noise or genome has been drawn at this seed
STREAM_TETHER = "tether"  # the tethered cell's sensor noise
STREAM_TETHER_ANGLES = "tether_angles"  # the brighter side's direction for each replicate
CHAMPIONS = {"U2203": ("uniform", Path("docs/data/stage3b/confirm/uniform-2203/champion.npy")),
             "F3202": ("fourier1", Path("docs/data/stage3b/confirm/fourier1-3202/champion.npy"))}
SUBJECT = "U2203"
B5_TAU = 30.0  # stage 3a's choice (docs/data/stage3/summary.json)
B2R_K = 100.0  # stage 3a's choice
PARKED_ABOVE = 0.9  # the mean beat above which a cell is parked
RUN_ABOVE = 1.0  # |m1| above which it is running: one node beating fully gives 1, three neighbours 2.85, a front half 5.03
MIN_RUN = 3  # ticks: shorter runs are flickers; a run's direction is read at its third tick
BANDS = (0.0, 0.01, 0.1, 0.3, 1.0, 3.0, 5.0, math.inf)  # the wall's mean noiseless light
STATES = ("parked", "running", "idle")
TETHER_LEVELS = (0.0, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 2.0, 3.0, 4.0, 5.0, 7.0, 10.0)
ONSET_LEVELS = (0.3, 1.0, 2.0)
ONSET_EPS = (0.0, 0.0005, 0.001, 0.002, 0.005, 0.01)
ONSET_REPLICATES = 8
READ_TICKS = 10
CHUNK = 25  # starts per job (a batch equals its singles, so chunking changes nothing)
DEFAULT_OUT = Path("docs/data/stage3c/probe")


def band_label(b: int) -> str:
    lo, hi = BANDS[b], BANDS[b + 1]
    return f"[{lo:g}, {hi:g})" if math.isfinite(hi) else f">= {lo:g}"


def wrap(a: np.ndarray) -> np.ndarray:
    """Angles to [-pi, pi)."""
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def first_mode(x: np.ndarray, theta: np.ndarray) -> np.ndarray:
    """sum_i x_i e^(i theta_i) over the wall for each row, ``(P,)`` complex, summed node by node."""
    c, s = np.cos(theta), np.sin(theta)
    re, im = x[:, 0] * c[0], x[:, 0] * s[0]
    for i in range(1, x.shape[1]):
        re = re + x[:, i] * c[i]
        im = im + x[:, i] * s[i]
    return re + 1j * im


def classify(beats: np.ndarray, m1: np.ndarray) -> np.ndarray:
    """Each row's state: 0 parked, 1 running, 2 idle."""
    parked = beats.mean(axis=1) > PARKED_ABOVE
    running = ~parked & (np.abs(m1) > RUN_ABOVE)
    return np.where(parked, 0, np.where(running, 1, 2))


class RunTracker:
    """The runs of P cells, a run being at least MIN_RUN consecutive running ticks: each run's label where it began (a
    light band, or 0), its duration, and the angle between its direction at its MIN_RUN-th tick and a target."""

    def __init__(self, population: int) -> None:
        self.length = np.zeros(population, dtype=np.int64)
        self.label = np.zeros(population, dtype=np.int64)
        self.onsets: List[Tuple[int, int, float]] = []  # (cell, label, angle to the target)
        self.durations: List[Tuple[int, int, int]] = []  # (cell, label, ticks)

    def step(self, running: np.ndarray, label: np.ndarray, direction: np.ndarray, target: np.ndarray) -> None:
        self._close((self.length > 0) & ~running)
        begin = running & (self.length == 0)
        self.label[begin] = label[begin]
        self.length[running] += 1
        for p in np.flatnonzero(running & (self.length == MIN_RUN)).tolist():
            self.onsets.append((p, int(self.label[p]), float(wrap(direction[p] - target[p]))))

    def _close(self, which: np.ndarray) -> None:
        for p in np.flatnonzero(which).tolist():
            if self.length[p] >= MIN_RUN:
                self.durations.append((p, int(self.label[p]), int(self.length[p])))
        self.length[which] = 0

    def finish(self) -> None:
        self._close(self.length > 0)


class Movement:
    """Part A's observer: per cell, the ticks by light band and state, the distance moved and moved toward the mouth by
    band, the runs (labelled by band), and the body's spin and the beating's creep over consecutive running ticks."""

    def __init__(self, cfg: Config, starts: Starts, alpha: np.ndarray) -> None:
        p, nb = len(starts), len(BANDS) - 1
        self.cfg, self.alpha, self.theta = cfg, np.asarray(alpha, dtype=np.float64), node_angles(cfg)
        self.ticks = np.zeros((p, nb, len(STATES)), dtype=np.int64)
        self.moved = np.zeros((p, nb))
        self.toward = np.zeros((p, nb))
        self.spin, self.creep, self.pairs = np.zeros(p), np.zeros(p), np.zeros(p, dtype=np.int64)
        self.runs = RunTracker(p)
        self.pos, self.heading = starts.pos.copy(), starts.heading.copy()
        self.prev_running, self.prev_arg, self.prev_spin = np.zeros(p, dtype=bool), np.zeros(p), np.zeros(p)

    def __call__(self, t: int, s: Mapping[str, Any]) -> None:
        counting = s["active"] & s["alive"]
        beats = s["beats"]
        m1 = first_mode(beats, self.theta)
        state = classify(beats, m1)
        band = np.clip(np.searchsorted(BANDS, s["light"].mean(axis=1), side="right") - 1, 0, len(BANDS) - 2)
        mouth = mouth_position(self.cfg, s["time"])
        tx, ty = mouth[:, 0] - self.pos[:, 0], mouth[:, 1] - self.pos[:, 1]
        dist = np.sqrt(tx * tx + ty * ty)
        dx, dy = s["pos"][:, 0] - self.pos[:, 0], s["pos"][:, 1] - self.pos[:, 1]
        idx = np.flatnonzero(counting)
        np.add.at(self.ticks, (idx, band[idx], state[idx]), 1)
        np.add.at(self.moved, (idx, band[idx]), np.sqrt(dx * dx + dy * dy)[idx])
        np.add.at(self.toward, (idx, band[idx]), ((dx * tx + dy * ty) / np.maximum(dist, 1e-9))[idx])
        running = counting & (state == 1)
        arg = np.angle(m1)
        self.runs.step(running, band, self.heading + self.alpha + arg, np.arctan2(ty, tx))
        both = running & self.prev_running
        self.spin[both] += self.prev_spin[both]
        self.creep[both] += wrap(arg - self.prev_arg)[both]
        self.pairs[both] += 1
        self.prev_spin = s["heading"] - self.heading
        self.prev_arg, self.prev_running = arg, running
        self.pos, self.heading = s["pos"].copy(), s["heading"].copy()


def cell_spec(cfg: Config, name: str, n: int) -> Tuple[Dict[str, Any], np.ndarray]:
    """A cell's controller spec for n starts and its cilium angle per start."""
    if name == "B5":
        return runwait(cfg, B5_TAU), np.zeros(n)
    if name == "B2r":
        return reflex(cfg, B2R_K), np.zeros(n)
    mode, path = CHAMPIONS[name]
    genomes = np.repeat(np.load(path).reshape(1, -1), n, axis=0)
    return {"controller": "network", "mode": mode, "genomes": genomes}, decode(cfg, mode, genomes[:1]).alpha.repeat(n)


def movement_job(job: Mapping[str, Any]) -> Dict[str, Any]:
    cfg: Config = job["cfg"]
    starts: Starts = job["starts"]
    spec, alpha = cell_spec(cfg, job["cell"], len(starts))
    obs = Movement(cfg, starts, alpha)
    result = simulate(cfg, starts, spec, seed=SEED, cell_ids=[NOISE_CELL_ID] * len(starts), observe=obs)
    obs.runs.finish()
    first = job["first"]
    return {"cell": job["cell"], "first": first, "rows": result.rows(starts, cell_name=job["cell"]), "result": result,
            "ticks": obs.ticks, "moved": obs.moved, "toward": obs.toward, "spin": obs.spin, "creep": obs.creep, "pairs": obs.pairs,
            "onsets": [(c + first, b, a) for c, b, a in obs.runs.onsets], "durations": [(c + first, b, d) for c, b, d in obs.runs.durations]}


def tether(cfg: Config, mode: str, genome: np.ndarray, light: np.ndarray, settle: int, measure: int, *, keys: Optional[Sequence[Tuple[int, int]]],
           target: Optional[np.ndarray] = None) -> Dict[str, np.ndarray]:
    """The network held in place, its heading fixed at 0, fed the same light ``(P, N)`` every tick plus the sensor noise
    (stream ``tether``, keyed per row) unless ``keys`` is None; ``settle`` ticks, then ``measure`` ticks read. Each
    row's mean beat, share of ticks parked, running and idle, mean speed it would swim at, the creep of its beating
    over consecutive running ticks (rad/s), its runs (counted, their median duration) and their direction at their
    third tick (alpha + arg m1) against ``target`` (default 0)."""
    p = light.shape[0]
    net = Network(cfg, decode(cfg, mode, np.repeat(genome.reshape(1, -1), p, axis=0)))
    alpha = net.alpha
    noise = None if keys is None else CellNoise(SEED, STREAM_TETHER, keys, (cfg.n_wall,), "normal", cfg.sensor_noise_sd)
    theta = node_angles(cfg)
    goal = np.zeros(p) if target is None else target
    beat, speed, creep = np.zeros(p), np.zeros(p), np.zeros(p)
    count = np.zeros((p, len(STATES)), dtype=np.int64)
    pairs = np.zeros(p, dtype=np.int64)
    runs = RunTracker(p)
    prev_running, prev_arg = np.zeros(p, dtype=bool), np.zeros(p)
    rows = np.arange(p)
    for t in range(settle + measure):
        beats = net.beats(light if noise is None else light + noise.at(t), t)
        if t < settle:
            continue
        m1 = first_mode(beats, theta)
        state = classify(beats, m1)
        arg = np.angle(m1)
        beat += beats.mean(axis=1)
        speed += cfg.v_max * (math.pi / cfg.n_wall) * np.abs(m1)
        count[rows, state] += 1
        running = state == 1
        both = running & prev_running
        creep[both] += wrap(arg - prev_arg)[both]
        pairs[both] += 1
        runs.step(running, np.zeros(p, dtype=np.int64), alpha + arg, goal)
        prev_running, prev_arg = running, arg
    runs.finish()
    durations = [[] for _ in range(p)]
    for c, _, d in runs.durations:
        durations[c].append(d)
    cosines = [[] for _ in range(p)]
    for c, _, a in runs.onsets:
        cosines[c].append(math.cos(a))
    return {"mean_beat": beat / measure, "shares": count / measure, "speed": speed / measure,
            "creep": np.divide(creep, pairs, out=np.full(p, math.nan), where=pairs > 0),
            "runs": np.array([len(d) for d in durations]), "median_run": np.array([float(np.median(d)) if d else math.nan for d in durations]),
            "cosines": cosines}


def tether_levels_job(job: Mapping[str, Any]) -> List[Dict[str, Any]]:
    cfg: Config = job["cfg"]
    mode, path = CHAMPIONS[job["cell"]]
    levels = np.asarray(job["levels"], dtype=np.float64)
    light = np.repeat(levels[:, None], cfg.n_wall, axis=1)
    keys = [(i, 0) for i in range(len(levels))] if job["noisy"] else None
    r = tether(cfg, mode, np.load(path), light, job["settle"], job["measure"], keys=keys)
    hours = job["measure"] / 3600.0
    return [{"cell": job["cell"], "noise": "on" if job["noisy"] else "off", "level": float(lv), "mean_beat": r["mean_beat"][i],
             "parked": r["shares"][i, 0], "running": r["shares"][i, 1], "idle": r["shares"][i, 2], "speed": r["speed"][i],
             "creep": r["creep"][i], "runs_per_hour": r["runs"][i] / hours, "median_run": r["median_run"][i]}
            for i, lv in enumerate(levels.tolist())]


def tether_onsets_job(job: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """The champion's network fed I_i = L (1 + eps cos(theta_i - phi)) for each (L, eps) and replicate; the replicates'
    directions phi from stream ``tether_angles`` and their noise keyed (1000 + replicate, 0), the same for every
    condition (paired)."""
    cfg: Config = job["cfg"]
    mode, path = CHAMPIONS[SUBJECT]
    reps = job["replicates"]
    phi = stream(SEED, STREAM_TETHER_ANGLES).uniform(-math.pi, math.pi, reps)
    conditions = [(lv, eps) for lv in job["levels"] for eps in job["eps"]]
    theta = node_angles(cfg)
    light = np.array([[lv * (1.0 + eps * math.cos(th - phi[r])) for th in theta.tolist()] for lv, eps in conditions for r in range(reps)])
    target = np.tile(phi, len(conditions))
    keys = [(1000 + r, 0) for _ in conditions for r in range(reps)]
    res = tether(cfg, mode, np.load(path), light, job["settle"], job["measure"], keys=keys, target=target)
    rows = []
    noise_mode = cfg.sensor_noise_sd * math.sqrt(2.0 / cfg.n_wall)
    for k, (lv, eps) in enumerate(conditions):
        cos = [c for r in range(reps) for c in res["cosines"][k * reps + r]]
        n = len(cos)
        rows.append({"level": lv, "eps": eps, "amplitude": lv * eps, "amplitude_over_node_noise": lv * eps / cfg.sensor_noise_sd,
                     "first_mode_snr_per_tick": lv * eps / noise_mode, "replicates": reps, "runs": n,
                     "cos_mean": float(np.mean(cos)) if n else math.nan,
                     "cos_se": float(np.std(cos, ddof=1) / math.sqrt(n)) if n > 1 else math.nan,
                     "toward_share": float(np.mean(np.array(cos) > 0.0)) if n else math.nan})
    return rows


def readability(cfg: Config, starts: Starts) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Part C at noon at each start's place and heading."""
    n = len(starts)
    noon = np.full(n, cfg.day_ticks // 4)
    light = node_light(cfg, "cave", starts.source, starts.pos, starts.heading, noon)
    spread = light.max(axis=1) - light.min(axis=1)
    z = (2.0 / cfg.n_wall) * first_mode(light, node_angles(cfg))
    noise = cfg.sensor_noise_sd * math.sqrt(2.0 / cfg.n_wall)
    snr = np.abs(z) / noise
    mouth = mouth_position(cfg, noon)
    dist = np.hypot(starts.pos[:, 0] - mouth[:, 0], starts.pos[:, 1] - mouth[:, 1])
    rows = [{"start": int(starts.index[i]), "mouth_distance": dist[i], "noon_wall_mean": float(light[i].mean()), "spread": spread[i],
             "t2_readable": bool(spread[i] >= 3.0 * cfg.sensor_noise_sd), "first_mode": float(np.abs(z[i])), "snr_one_tick": snr[i],
             "readable_one_tick": bool(snr[i] >= 3.0), f"readable_{READ_TICKS}_ticks": bool(snr[i] * math.sqrt(READ_TICKS) >= 3.0)}
            for i in range(n)]
    summary = {"t2_share": float(np.mean(spread >= 3.0 * cfg.sensor_noise_sd)), "one_tick_share": float(np.mean(snr >= 3.0)),
               f"{READ_TICKS}_ticks_share": float(np.mean(snr * math.sqrt(READ_TICKS) >= 3.0)), "median_snr_one_tick": float(np.median(snr)),
               "first_mode_noise": noise, "t2_threshold": 3.0 * cfg.sensor_noise_sd}
    return rows, summary


def champion_parts(cfg: Config) -> Dict[str, Any]:
    mode, path = CHAMPIONS[SUBJECT]
    g = np.load(path).reshape(-1)
    lay = layout(cfg, mode)
    ring = dict(zip(RING_NAMES, g[lay.ring].tolist()))
    ring["ring_tau"] = math.exp(ring.pop("ring_log_tau"))
    p = decode(cfg, mode, g[None])
    return {"run": SUBJECT, "mode": mode, **ring, "alpha": float(p.alpha[0]), "core_tau": p.tau[0, cfg.n_wall:].tolist(),
            "spokes_in": g[lay.spokes_in].tolist(), "spokes_out": g[lay.spokes_out].tolist()}


def movement_tables(cell: str, parts: Sequence[Mapping[str, Any]], alpha: float) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    """One cell's budget and runs by band, and its rates during runs, from its jobs."""
    ticks = np.concatenate([p["ticks"] for p in parts])
    moved = np.concatenate([p["moved"] for p in parts])
    toward = np.concatenate([p["toward"] for p in parts])
    spin, creep = sum(float(p["spin"].sum()) for p in parts), sum(float(p["creep"].sum()) for p in parts)
    pairs = sum(int(p["pairs"].sum()) for p in parts)
    onsets = [o for p in parts for o in p["onsets"]]
    durations = [d for p in parts for d in p["durations"]]
    living = int(ticks.sum())
    budget, runs = [], []
    for b in range(len(BANDS) - 1):
        n_b = int(ticks[:, b].sum())
        row: Dict[str, Any] = {"cell": cell, "band": band_label(b), "share_of_life": n_b / living if living else math.nan}
        for k, name in enumerate(STATES):
            row[name] = ticks[:, b, k].sum() / n_b if n_b else math.nan
        row["speed"] = moved[:, b].sum() / n_b if n_b else math.nan
        row["toward_mouth"] = toward[:, b].sum() / n_b if n_b else math.nan
        budget.append(row)
        cos = np.array([math.cos(a) for _, lab, a in onsets if lab == b])
        dur = np.array([d for _, lab, d in durations if lab == b], dtype=np.float64)
        runs.append({"cell": cell, "band": band_label(b), "runs": int(cos.size),
                     "onset_cos_mean": float(cos.mean()) if cos.size else math.nan,
                     "onset_cos_se": float(cos.std(ddof=1) / math.sqrt(cos.size)) if cos.size > 1 else math.nan,
                     "toward_share": float((cos > 0).mean()) if cos.size else math.nan,
                     "median_duration": float(np.median(dur)) if dur.size else math.nan,
                     "mean_duration": float(dur.mean()) if dur.size else math.nan})
    overall = {"living_ticks": living, **{name: float(ticks[:, :, k].sum() / living) if living else math.nan for k, name in enumerate(STATES)},
               "runs": len(onsets), "alpha": alpha,
               "spin_during_runs": spin / pairs if pairs else math.nan, "creep_during_runs": creep / pairs if pairs else math.nan,
               "turning_during_runs": (spin + creep) / pairs if pairs else math.nan, "running_pairs": pairs}
    return budget, runs, overall


def run(out: Path, workers: int, quick: bool) -> Dict[str, Any]:
    cfg = configure(quick)
    n_starts = 6 if quick else 100
    settle, measure = (200, 400) if quick else (7200, 3600)
    onset_settle, onset_measure = (200, 600) if quick else (3600, 10_800)
    reps = 2 if quick else ONSET_REPLICATES
    out.mkdir(parents=True, exist_ok=True)
    cells = ("U2203", "F3202", "B5", "B2r")
    settings = {**cfg.as_dict(), "seed": SEED, "n_starts": n_starts, "cells": cells, "b5_tau": B5_TAU, "b2r_k": B2R_K,
                "parked_above": PARKED_ABOVE, "run_above": RUN_ABOVE, "min_run": MIN_RUN, "bands": [b if math.isfinite(b) else "inf" for b in BANDS],
                "tether_levels": TETHER_LEVELS, "tether_settle": settle, "tether_measure": measure, "onset_levels": ONSET_LEVELS,
                "onset_eps": ONSET_EPS, "onset_replicates": reps, "onset_settle": onset_settle, "onset_measure": onset_measure,
                "read_ticks": READ_TICKS, "quick": quick}
    manifest = build_manifest(protocol="stage3c_probe", settings=settings, seeds=[SEED], extra={"out": str(out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:7.1f}s {msg}", flush=True)

    starts = sample_starts(cfg, "cave", n_starts, SEED)
    chunks = [(lo, starts.take(range(lo, min(lo + CHUNK, n_starts)))) for lo in range(0, n_starts, CHUNK)]
    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        moves = [pool.submit(movement_job, {"cfg": cfg, "cell": c, "starts": st, "first": lo}) for c in cells for lo, st in chunks]
        levels = [pool.submit(tether_levels_job, {"cfg": cfg, "cell": c, "levels": TETHER_LEVELS, "noisy": noisy, "settle": settle, "measure": measure})
                  for c in CHAMPIONS for noisy in (False, True)]
        onsets = [pool.submit(tether_onsets_job, {"cfg": cfg, "levels": (lv,), "eps": ONSET_EPS, "replicates": reps, "settle": onset_settle,
                                                  "measure": onset_measure}) for lv in ONSET_LEVELS]
        move_parts = [f.result() for f in moves]
        log("part A: movement done")
        level_rows = [row for f in levels for row in f.result()]
        onset_rows = [row for f in onsets for row in f.result()]
        log("part B: the tethered cell done")

    per_start, budget, runs, overall, results = [], [], [], {}, {}
    for c in cells:
        parts = sorted((p for p in move_parts if p["cell"] == c), key=lambda p: p["first"])
        per_start += [row for p in parts for row in p["rows"]]
        alpha = float(cell_spec(cfg, c, 1)[1][0])
        b, r, o = movement_tables(c, parts, alpha)
        budget += b
        runs += r
        fitness = np.concatenate([p["result"].fitness for p in parts])
        survived = np.concatenate([p["result"].survived for p in parts])
        mean_beat = np.concatenate([p["result"].mean_beat for p in parts])
        overall[c] = {**o, "mean_fitness": float(fitness.mean()), "survival": float(survived.mean()), "mean_beat": float(mean_beat.mean())}
        results[c] = parts
        log(f"{c}: fitness {overall[c]['mean_fitness']:.3f}, survival {overall[c]['survival']:.0%}; parked {o['parked']:.0%}, running "
            f"{o['running']:.0%}; {o['runs']} runs; during runs spin {o['spin_during_runs']:+.4f}, creep {o['creep_during_runs']:+.4f} rad/s")
    write_csv(out / "per_start.csv", ("cell_name", *RUN_COLUMNS), per_start)
    write_csv(out / "budget.csv", ("cell", "band", "share_of_life", *STATES, "speed", "toward_mouth"), budget)
    write_csv(out / "runs.csv", ("cell", "band", "runs", "onset_cos_mean", "onset_cos_se", "toward_share", "median_duration", "mean_duration"), runs)
    write_csv(out / "tether_levels.csv", ("cell", "noise", "level", "mean_beat", "parked", "running", "idle", "speed", "creep", "runs_per_hour",
                                          "median_run"), level_rows)
    write_csv(out / "tether_onsets.csv", ("level", "eps", "amplitude", "amplitude_over_node_noise", "first_mode_snr_per_tick", "replicates",
                                          "runs", "cos_mean", "cos_se", "toward_share"), onset_rows)
    read_rows, read_summary = readability(cfg, starts)
    write_csv(out / "readability.csv", tuple(read_rows[0]), read_rows)
    log(f"part C: readable by T2's criterion on {read_summary['t2_share']:.0%}; by the first mode in one tick on {read_summary['one_tick_share']:.0%}, "
        f"over {READ_TICKS} ticks on {read_summary[f'{READ_TICKS}_ticks_share']:.0%}")
    for row in runs:
        if row["cell"] == SUBJECT and row["runs"]:
            log(f"{SUBJECT} runs from light {row['band']}: {row['runs']}, onset cos to the mouth {row['onset_cos_mean']:+.3f} "
                f"(se {row['onset_cos_se']:.3f}), median {row['median_duration']:.0f} s")
    for row in onset_rows:
        log(f"tethered, light {row['level']:g}, eps {row['eps']:g} (first-mode SNR a tick {row['first_mode_snr_per_tick']:.2f}): "
            f"{row['runs']} runs, cos to the brighter side {row['cos_mean']:+.3f}")
    summary = {"champion": champion_parts(cfg), "movement": overall, "readability": read_summary,
               "run_summaries": {c: run_summary(_merge(results[c])) for c in cells}, "quick": quick}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=_json) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0, workers=workers)
    write_manifest(out / "manifest.json", manifest)
    log(f"done, written to {out}")
    return summary


def _merge(parts: Sequence[Mapping[str, Any]]) -> Any:
    """The jobs' results for one cell as one RunResult-like object for ``run_summary``."""
    from dataclasses import fields, replace

    first = parts[0]["result"]
    merged = {}
    for f in fields(first):
        if f.name in ("ticks", "noise_digests", "trajectory"):
            continue
        merged[f.name] = np.concatenate([np.atleast_1d(getattr(p["result"], f.name)) for p in parts])
    return replace(first, ticks=max(p["result"].ticks for p in parts), trajectory=None, **merged)


def _json(x: Any) -> Any:
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating,)):
        return None if not math.isfinite(float(x)) else float(x)
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, float) and not math.isfinite(x):
        return None
    raise TypeError(type(x))


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    args = parser.parse_args(argv)
    return run(args.out, args.workers, args.quick)


if __name__ == "__main__":
    main(sys.argv[1:])
