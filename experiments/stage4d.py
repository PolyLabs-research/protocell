"""Stage 4d (docs/prereg/stage4d.md): can the cell carry B8? A cell is fitted to B8's beats on B8's own record, then
judged closed loop in stage 4a's world.

    EXPERIMENT=stage4d bash cloud/launch_phase.sh TAG HOURS MAX_RATE fit uniform:1 fourier1:1   # both modes, on a pod
    .venv/bin/python -W error::RuntimeWarning -m experiments.stage4d --score   # after both: §6's predictions
    .venv/bin/python -m experiments.stage4d --mode uniform --quick --out /tmp/s4d --workers 2   # the smoke test: not a result

The record (§2): B8 in stage 4a's world on starts 1-40 at seed 24, kept in windows of 500 ticks, six from the daylight
and two from anywhere per start (stream ``windows`` keyed by the start); a window counts only if B8 lived through it.
Starts 1-32 train, 33-40 are held out. The fit (§3): stage 4c's CMA-ES on the mean squared difference between the cell's
beats and B8's over each window's last 300 ticks, the cell run open loop on what B8 sensed, its cilium angle fixed at 0.
Every 250 generations the best sample and the mean run closed loop on stage 4b's 24 validation starts; the fitted cell
is the best there. The judge (§4): the fitted cell, B8 and B0 on fresh starts 1-100 at seed 25, the share of the gap
from B0 to B8 the cell closes, with a bootstrap interval (seed 26). A fit checkpoints every 50 generations and resumes
from the checkpoint, the same bits for any number of workers (tested). Writes docs/data/stage4d/fit/<mode>-<seed>/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import protocell  # noqa: F401  # pins the BLAS thread counts before numpy loads

import numpy as np

from experiments import stage4_probe as probe
from experiments import stage4_thrift as thrift
from experiments import stage4a
from protocell.cell import MODES, decode, layout, sigmoid
from protocell.cmaes import STREAM_CMAES, Strategy, to_genomes
from protocell.config import Config
from protocell.evolve import NOISE_CELL_ID, validation_job
from protocell.manifest import build_manifest, finish_manifest, write_manifest
from protocell.rng import stream
from protocell.sim import simulate
from protocell.tables import write_csv
from protocell.world import Starts, daylight, lifetimes, sample_starts

SEED, JUDGE_SEED, BOOTSTRAP_SEED = 24, 25, 26  # fresh: the record's starts and noise, the judge's, the bootstrap
VALIDATION_SEED = 20  # stage 4b's validation starts
PHASE = "fit"  # the pod scripts name a stage's runs by phase, mode and replicate; this stage has one of each
FIT_SEEDS = {"uniform": 2701, "fourier1": 2702}
STREAM_WINDOWS = "windows"
CARRIES, PARTLY = 0.9, 0.5  # §5: the share of the gap from B0 to B8 closed
RESAMPLES = 10_000
GENERATION_COLUMNS = ("generation", "sigma", "best_error", "median_error", "best_match", "seconds")
VALIDATION_COLUMNS = ("generation", "candidate", "train_match", "validation_fitness", "validation_survival", "validation_mean_beat", "fitted")
JUDGE_COLUMNS = ("cell", "start", "survived", "fitness", "day_light", "day_beat", "night_beat")
DEFAULT_OUT = Path("docs/data/stage4d")


@dataclass(frozen=True)
class Sizes:
    """§2-§4's numbers; ``generations`` set by §8's timing note."""

    record_starts: int = 40
    train_starts: int = 32  # starts 1-32 train; the rest are held out
    day_windows: int = 6
    any_windows: int = 2
    warmup: int = 200
    scored: int = 300
    population: int = 96
    sigma0: float = 0.1
    generations: int = 8000  # §8's timing note
    validate_every: int = 250
    checkpoint_every: int = 50
    validation_starts: int = 24
    judge_starts: int = 100
    chunk: int = 50
    resamples: int = RESAMPLES

    @property
    def window(self) -> int:
        return self.warmup + self.scored

    @staticmethod
    def quick() -> "Sizes":
        """The smoke test's sizes: not a result."""
        return Sizes(record_starts=4, train_starts=3, day_windows=2, any_windows=1, warmup=20, scored=30, population=8, generations=4,
                     validate_every=2, checkpoint_every=1, validation_starts=2, judge_starts=4, chunk=2, resamples=200)


def world(quick: bool = False) -> Config:
    return stage4a.world(quick)


def seed_for(phase: str, mode: str, replicate: int) -> int:
    if phase != PHASE or replicate != 1:
        raise SystemExit(f"stage 4d has one phase, {PHASE!r}, and one run per mode")
    return FIT_SEEDS[mode]


def run_dir(out_root: Path, mode: str) -> Path:
    return out_root / PHASE / f"{mode}-{FIT_SEEDS[mode]}"


# --- the record (§2) ----------------------------------------------------------------------------------------------------

def draw_windows(cfg: Config, starts: Starts, sizes: Sizes) -> List[Tuple[int, int]]:
    """Each start's windows, as (row, first tick): ``day_windows`` whose first tick is in daylight and ``any_windows``
    from anywhere, each wholly within the start's life, from stream ``windows`` keyed by the start's number."""
    ends = lifetimes(cfg, starts)
    out = []
    for row in range(len(starts)):
        last = int(ends[row]) - sizes.window  # the latest first tick
        rng = stream(SEED, STREAM_WINDOWS, (int(starts.index[row]),))
        ticks = np.arange(last + 1)
        lit = ticks[daylight(cfg, starts.phase[row] + ticks) > 0.0]
        day = rng.choice(lit, size=sizes.day_windows, replace=False)
        anywhere = rng.integers(0, last + 1, size=sizes.any_windows)
        out += [(row, int(t)) for t in sorted(np.concatenate([day, anywhere]).tolist())]
    return out


class Recorder:
    """An observer for ``simulate`` that keeps, within each window, what the nodes sensed and how the cell beat, and
    whether the cell was alive at each tick."""

    def __init__(self, windows: Sequence[Tuple[int, int]], length: int, n_wall: int) -> None:
        self.rows = np.array([w[0] for w in windows], dtype=np.intp)
        self.first = np.array([w[1] for w in windows], dtype=np.int64)
        self.length = length
        self.sensed = np.zeros((len(windows), length, n_wall))
        self.beats = np.zeros((len(windows), length, n_wall))
        self.lived = np.zeros((len(windows), length), dtype=bool)

    def __call__(self, t: int, state: Mapping[str, Any]) -> None:
        now = np.flatnonzero((self.first <= t) & (t < self.first + self.length))
        if now.size:
            at, rows = t - self.first[now], self.rows[now]
            self.sensed[now, at] = state["sensed"][rows]
            self.beats[now, at] = state["beats"][rows]
            self.lived[now, at] = state["active"][rows]


def record_job(job: Mapping[str, Any]) -> Dict[str, Any]:
    cfg: Config = job["cfg"]
    starts: Starts = job["starts"]
    rec = Recorder(job["windows"], job["length"], cfg.n_wall)
    simulate(cfg, starts, thrift.cell_spec(cfg, "B8", len(starts)), seed=SEED, cell_ids=[NOISE_CELL_ID] * len(starts), observe=rec)
    return {"first_row": job["first_row"], "starts": [int(starts.index[r]) for r, _ in job["windows"]], "ticks": [t for _, t in job["windows"]],
            "sensed": rec.sensed, "beats": rec.beats, "whole": rec.lived.all(axis=1)}


def record(cfg: Config, sizes: Sizes, pool: ProcessPoolExecutor) -> Dict[str, Any]:
    """B8's record on starts 1..record_starts, in windows: the training and held-out windows B8 lived through."""
    starts = sample_starts(cfg, "cave", sizes.record_starts, SEED)
    windows = draw_windows(cfg, starts, sizes)
    jobs = []
    for lo in range(0, len(starts), 5):
        rows = range(lo, min(lo + 5, len(starts)))
        jobs.append({"cfg": cfg, "starts": starts.take(rows), "first_row": lo, "length": sizes.window,
                     "windows": [(r - lo, t) for r, t in windows if r in rows]})
    parts = sorted(pool.map(record_job, jobs), key=lambda p: p["first_row"])
    start_no = np.array([s for p in parts for s in p["starts"]])
    first = np.array([t for p in parts for t in p["ticks"]])
    sensed, beats = np.concatenate([p["sensed"] for p in parts]), np.concatenate([p["beats"] for p in parts])
    whole = np.concatenate([p["whole"] for p in parts])
    train = whole & (start_no <= sizes.train_starts)
    held = whole & (start_no > sizes.train_starts)
    digest = hashlib.sha256()
    for a in (start_no, first, sensed, beats, whole):
        digest.update(np.ascontiguousarray(a).tobytes())
    return {"train": (sensed[train], beats[train]), "held": (sensed[held], beats[held]), "windows": len(windows), "whole": int(whole.sum()),
            "train_windows": int(train.sum()), "held_windows": int(held.sum()), "digest": digest.hexdigest(),
            "rows": [{"start": int(s), "first_tick": int(t), "whole": int(w), "set": "train" if s <= sizes.train_starts else "held"}
                     for s, t, w in zip(start_no, first, whole)]}


# --- the fit (§3) -------------------------------------------------------------------------------------------------------

def open_loop(cfg: Config, mode: str, genome: np.ndarray, sensed: np.ndarray) -> np.ndarray:
    """The cell's beats ``(S, T, N)`` when its nodes sense ``sensed`` ``(S, T, N)``: each window from rest, stepped as
    ``protocell.sim.Network`` steps it (the sums in another order, so equal to rounding)."""
    p = decode(cfg, mode, np.asarray(genome, dtype=np.float64)[None])
    n = cfg.n_wall
    Wt, bias, tau, gain = p.W[0].T.copy(), p.bias[0], p.tau[0], float(p.gain[0])
    s, steps = sensed.shape[0], sensed.shape[1]
    y = np.zeros((s, bias.shape[0]))
    out = np.repeat(sigmoid(bias)[None], s, axis=0)
    drive = np.zeros_like(y)
    beats = np.empty((s, steps, n))
    for t in range(steps):
        drive[:, :n] = gain * sensed[:, t]
        y = y + (-y + out @ Wt + drive) / tau
        out = sigmoid(y + bias)
        beats[:, t] = out[:, :n]
    return beats


def error(cfg: Config, mode: str, genome: np.ndarray, sensed: np.ndarray, target: np.ndarray, warmup: int) -> float:
    """The mean squared difference between the cell's beats and the target's over the scored ticks and the nodes."""
    return float(np.mean((open_loop(cfg, mode, genome, sensed)[:, warmup:] - target[:, warmup:]) ** 2))


def match(err: float, target: np.ndarray, warmup: int) -> float:
    """1 less the error as a share of a never-beating cell's."""
    zero = float(np.mean(target[:, warmup:] ** 2))
    return 1.0 - err / zero if zero > 0.0 else math.nan


_DATA: Dict[str, Any] = {}


def _load_data(cfg: Config, mode: str, sensed: np.ndarray, target: np.ndarray, warmup: int) -> None:
    _DATA.update(cfg=cfg, mode=mode, sensed=sensed, target=target, warmup=warmup)


def errors_job(genomes: np.ndarray) -> np.ndarray:
    d = _DATA
    return np.array([error(d["cfg"], d["mode"], g, d["sensed"], d["target"], d["warmup"]) for g in genomes])


def with_alpha_zero(cfg: Config, mode: str, samples: np.ndarray) -> np.ndarray:
    """Normalised genomes from the fit's samples, which leave out the cilium angle: it is put at the middle of its
    range, 0."""
    a = layout(cfg, mode).alpha.start
    return np.insert(samples, a, 0.5, axis=1)


def _save_fit(path: Path, strategy: Strategy, state: Mapping[str, Any]) -> None:
    """The fit's state, on disk whole or not at all: the host has stopped dead under long runs."""
    tmp = path.with_suffix(".tmp.npz")
    with open(tmp, "wb") as f:
        np.savez(f, genome=state["genome"], **strategy.state(),
                 meta=np.array(json.dumps({k: state[k] for k in ("next_generation", "digest", "history", "validation", "fitted")})))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _load_fit(path: Path, n: int, population: int) -> Tuple[Strategy, Dict[str, Any]]:
    with np.load(path, allow_pickle=False) as z:
        meta = json.loads(str(z["meta"]))
        strategy = Strategy.restore(n, population, {k: z[k] for k in ("mean", "sigma", "C", "ps", "pc", "updates")})
        return strategy, {"genome": z["genome"].copy(), **meta}


def fit(cfg: Config, mode: str, sizes: Sizes, data: Mapping[str, Any], pool: ProcessPoolExecutor, workers: int,
        log, ckpt: Path, stop_after: Optional[int] = None) -> Dict[str, Any]:
    """§3's fit: CMA-ES on the training windows' error; every ``validate_every`` generations, and at the last, the best
    sample and the mean closed loop on the validation starts. The fitted cell is the best there (ties: the earlier).
    Checkpoints to ``ckpt`` every ``checkpoint_every`` generations and resumes from it."""
    seed = FIT_SEEDS[mode]
    n = layout(cfg, mode).length - 1
    sensed, target = data["train"]
    if ckpt.exists():
        strategy, state = _load_fit(ckpt, n, sizes.population)
        if state["digest"] != data["digest"]:
            raise ValueError("the checkpoint was fitted to another record")
        log(f"[{mode}] resumed at generation {state['next_generation']}")
    else:
        strategy = Strategy(n, sizes.population, stream(seed, STREAM_CMAES).random(n), sizes.sigma0)
        state = {"genome": np.full(n + 1, math.nan), "next_generation": 0, "digest": data["digest"], "history": [], "validation": [], "fitted": None}
    vstarts = sample_starts(cfg, "cave", sizes.validation_starts, VALIDATION_SEED)
    per = max(1, math.ceil(sizes.population / workers))
    done = 0
    while state["next_generation"] < sizes.generations and (stop_after is None or done < stop_after):
        g = state["next_generation"]
        t0 = time.time()
        samples = strategy.ask(stream(seed, STREAM_CMAES, (g + 1,)))
        genomes = to_genomes(cfg, mode, with_alpha_zero(cfg, mode, samples))
        errs = np.concatenate(list(pool.map(errors_job, [genomes[i:i + per] for i in range(0, sizes.population, per)])))
        order = np.argsort(errs, kind="stable")
        best = int(order[0])
        row = {"generation": g + 1, "sigma": strategy.sigma, "best_error": float(errs[best]), "median_error": float(np.median(errs)),
               "best_match": match(float(errs[best]), target, sizes.warmup)}
        if (g + 1) % sizes.validate_every == 0 or g + 1 == sizes.generations:
            mean_genome = to_genomes(cfg, mode, with_alpha_zero(cfg, mode, strategy.mean[None]))[0]
            mean_err = error(cfg, mode, mean_genome, sensed, target, sizes.warmup)
            candidates = [("best sample", genomes[best], row["best_match"]), ("mean", mean_genome, match(mean_err, target, sizes.warmup))]
            jobs = [{"cfg": cfg, "mode": mode, "seed": VALIDATION_SEED, "starts": vstarts, "genome": c[1]} for c in candidates]
            for (name, genome, m), v in zip(candidates, pool.map(validation_job, jobs)):
                better = state["fitted"] is None or v["fitness"] > state["fitted"]["validation_fitness"]
                if better:
                    state["genome"] = np.asarray(genome).copy()
                    state["fitted"] = {"generation": g + 1, "candidate": name, "train_match": m, "validation_fitness": v["fitness"],
                                       "validation_survival": v["survival"]}
                state["validation"].append({"generation": g + 1, "candidate": name, "train_match": m, "validation_fitness": v["fitness"],
                                            "validation_survival": v["survival"], "validation_mean_beat": v["mean_beat"], "fitted": int(better)})
                log(f"[{mode}] validation at {g + 1}: {name} match {m:.3f}, fitness {v['fitness']:.3f}, survival {v['survival']:.0%}")
        strategy.tell(samples, -errs)
        row["seconds"] = round(time.time() - t0, 3)
        state["history"].append(row)
        state["next_generation"] = g + 1
        done += 1
        if (g + 1) % sizes.checkpoint_every == 0 or g + 1 == sizes.generations:
            _save_fit(ckpt, strategy, state)
        if (g + 1) % 50 == 0 or g == 0:
            log(f"[{mode}] generation {g + 1}: best match {row['best_match']:.3f}, sigma {strategy.sigma:.4f} [{row['seconds']:.2f} s]")
    fitted = None if state["fitted"] is None else {**state["fitted"], "genome": state["genome"]}
    return {"history": state["history"], "validation": state["validation"], "fitted": fitted, "final_sigma": strategy.sigma, "strategy": strategy}


# --- the judge (§4) -----------------------------------------------------------------------------------------------------

def judge_job(job: Mapping[str, Any]) -> Dict[str, Any]:
    cfg: Config = job["cfg"]
    starts: Starts = job["starts"]
    ledger = thrift.Ledger(cfg, len(starts))
    r = simulate(cfg, starts, job["spec"], seed=JUDGE_SEED, cell_ids=[NOISE_CELL_ID] * len(starts), observe=ledger)
    day_light, day_beat = thrift._per(ledger.day_soak, ledger.day_ticks), thrift._per(ledger.day_beat, ledger.day_ticks)
    night_beat = thrift._per(ledger.night_beat, ledger.night_ticks)
    return {"cell": job["cell"], "first": job["first"], "rows": [
        {"cell": job["cell"], "start": int(starts.index[i]), "survived": int(r.survived[i]), "fitness": float(r.fitness[i]),
         "day_light": float(day_light[i]), "day_beat": float(day_beat[i]), "night_beat": float(night_beat[i])} for i in range(len(starts))]}


def gap_share(cell: np.ndarray, b8: np.ndarray, b0: np.ndarray, resamples: int, key: int) -> Tuple[float, float, float]:
    """The share of the gap from B0 to B8 that the cell closes, on mean fitness over the starts, with a 95% bootstrap
    interval from resampling the starts together (seed 26)."""
    def share(idx: np.ndarray) -> np.ndarray:
        lo, hi = b0[idx].mean(axis=-1), b8[idx].mean(axis=-1)
        return (cell[idx].mean(axis=-1) - lo) / (hi - lo)
    point = float(share(np.arange(cell.shape[0])))
    idx = stream(BOOTSTRAP_SEED, "bootstrap", (key,)).integers(0, cell.shape[0], size=(resamples, cell.shape[0]))
    boot = share(idx)
    return point, float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))


def verdict(share: float) -> str:
    return "carries B8" if share >= CARRIES else "partly" if share >= PARTLY else "does not"


def judge(cfg: Config, mode: str, genome: np.ndarray, sizes: Sizes, pool: ProcessPoolExecutor) -> Dict[str, Any]:
    starts = sample_starts(cfg, "cave", sizes.judge_starts, JUDGE_SEED)
    chunks = [(lo, starts.take(range(lo, min(lo + sizes.chunk, len(starts))))) for lo in range(0, len(starts), sizes.chunk)]
    specs = {"fitted": lambda n: {"controller": "network", "mode": mode, "genomes": np.repeat(np.asarray(genome)[None], n, axis=0)},
             "B8": lambda n: thrift.cell_spec(cfg, "B8", n), "B0": lambda n: thrift.cell_spec(cfg, "B0", n)}
    jobs = [{"cfg": cfg, "starts": part, "spec": make(len(part)), "cell": cell, "first": lo} for cell, make in specs.items() for lo, part in chunks]
    parts = list(pool.map(judge_job, jobs))
    rows = [row for cell in specs for p in sorted((p for p in parts if p["cell"] == cell), key=lambda p: p["first"]) for row in p["rows"]]
    col = {cell: {k: np.array([r[k] for r in rows if r["cell"] == cell]) for k in ("fitness", "survived", "day_light", "day_beat")} for cell in specs}
    share, lo, hi = gap_share(col["fitted"]["fitness"], col["B8"]["fitness"], col["B0"]["fitness"], sizes.resamples, MODES.index(mode) + 1)
    cells = {cell: {"fitness": float(c["fitness"].mean()), "survival": float(c["survived"].mean()),
                    "day_light": float(np.nanmean(c["day_light"])) if np.isfinite(c["day_light"]).any() else None,
                    "day_beat": float(np.nanmean(c["day_beat"])) if np.isfinite(c["day_beat"]).any() else None} for cell, c in col.items()}
    return {"rows": rows, "cells": cells, "gap_share": share, "gap_low": lo, "gap_high": hi, "verdict": verdict(share)}


# --- a mode's run, and the predictions ----------------------------------------------------------------------------------

def run_mode(mode: str, out_root: Path, workers: int, quick: bool) -> Dict[str, Any]:
    cfg = world(quick)
    sizes = Sizes.quick() if quick else Sizes()
    out = run_dir(out_root, mode)
    out.mkdir(parents=True, exist_ok=True)
    settings = {"world": cfg.as_dict(), "mode": mode, "sizes": asdict(sizes), "seed": SEED, "judge_seed": JUDGE_SEED, "bootstrap_seed": BOOTSTRAP_SEED,
                "validation_seed": VALIDATION_SEED, "fit_seed": FIT_SEEDS[mode], "b8": {"tau": thrift.B8_TAU, "aim_tau": probe.B8_AIM_TAU},
                "verdict": {"carries_at_least": CARRIES, "partly_at_least": PARTLY}, "quick": quick}
    manifest = build_manifest(protocol="stage4d", settings=settings, seeds=[SEED, JUDGE_SEED, BOOTSTRAP_SEED, FIT_SEEDS[mode]], extra={"out": str(out)})
    t0 = time.time()

    def log(msg: str) -> None:
        print(f"{time.time() - t0:8.1f}s {msg}", flush=True)

    with ProcessPoolExecutor(max_workers=max(1, workers)) as pool:
        data = record(cfg, sizes, pool)
    log(f"[{mode}] the record: {data['whole']} of {data['windows']} windows whole; {data['train_windows']} train, {data['held_windows']} held out; "
        f"sha256 {data['digest'][:12]}")
    sensed, target = data["train"]
    with ProcessPoolExecutor(max_workers=max(1, workers), initializer=_load_data, initargs=(cfg, mode, sensed, target, sizes.warmup)) as pool:
        result = fit(cfg, mode, sizes, data, pool, workers, log, out / "checkpoint.npz")
        fitted = result["fitted"]
        held_sensed, held_target = data["held"]
        held = match(error(cfg, mode, fitted["genome"], held_sensed, held_target, sizes.warmup), held_target, sizes.warmup)
        log(f"[{mode}] fitted: {fitted['candidate']} at generation {fitted['generation']}, train match {fitted['train_match']:.3f}, held-out {held:.3f}, "
            f"validation fitness {fitted['validation_fitness']:.3f}")
        judged = judge(cfg, mode, fitted["genome"], sizes, pool)
    c = judged["cells"]
    log(f"[{mode}] judge: fitted {c['fitted']['fitness']:.3f} ({c['fitted']['survival']:.0%}), B8 {c['B8']['fitness']:.3f} ({c['B8']['survival']:.0%}), "
        f"B0 {c['B0']['fitness']:.3f}; closes {judged['gap_share']:.2f} [{judged['gap_low']:.2f}, {judged['gap_high']:.2f}] of the gap: {judged['verdict']}")
    write_csv(out / "generations.csv", GENERATION_COLUMNS, result["history"])
    write_csv(out / "validation.csv", VALIDATION_COLUMNS, result["validation"])
    write_csv(out / "windows.csv", ("start", "first_tick", "whole", "set"), data["rows"])
    write_csv(out / "judge.csv", JUDGE_COLUMNS, judged["rows"])
    np.save(out / "champion.npy", np.asarray(fitted["genome"])[None])
    info = {k: v for k, v in fitted.items() if k != "genome"}
    summary = {"mode": mode, "fitted": {**info, "held_out_match": held}, "record": {k: data[k] for k in ("windows", "whole", "train_windows", "held_windows", "digest")},
               "final_sigma": result["final_sigma"], "judge": {k: v for k, v in judged.items() if k != "rows"}, "quick": quick}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=probe._json) + "\n")
    (out / "champion.json").write_text(json.dumps({"mode": mode, **info, "held_out_match": held, "genome": np.asarray(fitted["genome"]).tolist()}, indent=1) + "\n")
    finish_manifest(manifest, wall_seconds=time.time() - t0, workers=workers, generations=sizes.generations)
    write_manifest(out / "manifest.json", manifest)
    log(f"[{mode}] done, written to {out}")
    return summary


def score_predictions(summaries: Mapping[str, Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """§6's predictions, from both modes' summaries."""
    share = {m: summaries[m]["judge"]["gap_share"] for m in MODES}
    fitness = {m: summaries[m]["judge"]["cells"]["fitted"]["fitness"] for m in MODES}
    b8 = {m: summaries[m]["judge"]["cells"]["B8"]["fitness"] for m in MODES}
    held = summaries["fourier1"]["fitted"]["held_out_match"]
    out = [
        (1, "the fourier1 cell closes at least half the gap", share["fourier1"] >= PARTLY, share),
        (2, "the uniform cell closes less of the gap than the fourier1 cell", share["uniform"] < share["fourier1"], share),
        (3, "neither fitted cell beats B8 on mean fitness", all(fitness[m] <= b8[m] for m in MODES), {"fitted": fitness, "B8": b8}),
        (4, "the held-out match is at least 0.5 in the fourier1 mode", held >= 0.5, {"fourier1": held}),
    ]
    return [{"number": n, "text": text, "holds": bool(holds), "values": values} for n, text, holds, values in out]


def score(out_root: Path) -> Dict[str, Any]:
    summaries = {m: json.loads((run_dir(out_root, m) / "summary.json").read_text()) for m in MODES}
    predictions = score_predictions(summaries)
    for p in predictions:
        print(f"prediction {p['number']}: {'✓' if p['holds'] else '✗'} {p['text']}", flush=True)
    summary = {"verdicts": {m: summaries[m]["judge"]["verdict"] for m in MODES}, "gap_share": {m: summaries[m]["judge"]["gap_share"] for m in MODES},
               "predictions": predictions}
    (out_root / PHASE / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True, default=probe._json) + "\n")
    return summary


def main(argv: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--phase", choices=[PHASE], default=PHASE)
    parser.add_argument("--mode", choices=MODES)
    parser.add_argument("--replicate", type=int, choices=[1], default=1)
    parser.add_argument("--score", action="store_true", help="read both modes' results and score §6's predictions")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--quick", action="store_true", help="the smoke test's sizes and a 2,000-tick day: not a result")
    args = parser.parse_args(argv)
    if args.score:
        return score(args.out)
    if args.mode is None:
        parser.error("--mode or --score")
    return run_mode(args.mode, args.out, args.workers, args.quick)


if __name__ == "__main__":
    main(sys.argv[1:])
