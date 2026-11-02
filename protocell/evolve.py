"""Evolution (docs/prereg/stage1.md §4): a generational genetic algorithm with elitism, truncation selection and
mutation only. Each generation every genome is scored on training starts drawn fresh for that generation, all
genomes on a start sharing the same noise; at set generations the best few are scored on fixed validation starts,
and the run's champion is the best on validation.

Every source of randomness is keyed by the run's seed and the generation (streams ``evolution`` and ``train``), so a
run resumed from its checkpoint is the same bits as one run straight through (tested). Evaluation goes through a
``mapper`` (the builtin ``map``, or a process pool's), and a batch equals its singles, so the number of workers never
changes a result.
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

import numpy as np

from protocell.cell import genome_ranges, layout, random_genomes
from protocell.config import Config
from protocell.rng import stream
from protocell.sim import simulate
from protocell.tables import write_csv
from protocell.world import Starts, sample_starts

STREAM_EVOLUTION = "evolution"
STREAM_TRAIN = "train"
NOISE_CELL_ID = 0  # every genome on a start draws the same noise: genomes are ranked on the same luck
Mapper = Callable[[Callable[[Any], Any], Iterable[Any]], Iterable[Any]]


@dataclass(frozen=True)
class GA:
    """The algorithm's numbers (stage1.md §4), each with its reason there."""

    population: int = 96
    elites: int = 4
    parents: int = 24  # children's parents are drawn uniformly from the best this many
    sigma: float = 0.02  # a mutation's sd, as a share of each number's range
    generations: int = 100
    train_starts: int = 8
    chunk: int = 48  # genomes in one job: two jobs a start fill 16 workers
    validate_every: int = 10
    validate_top: int = 3
    validation_starts: int = 24
    validation_seed: int = 4

    def __post_init__(self) -> None:
        if not (0 < self.elites < self.population and 0 < self.parents <= self.population):
            raise ValueError("elites and parents must fit in the population")
        if self.population % self.chunk:
            raise ValueError("the population must split into whole jobs")

    @staticmethod
    def quick() -> "GA":
        """The smoke test's sizes: not a result."""
        return GA(population=8, elites=2, parents=4, generations=3, train_starts=2, chunk=4, validate_every=1,
                  validate_top=2, validation_starts=2)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def but(self, **changes: Any) -> "GA":
        return replace(self, **changes)


# --- the operators ------------------------------------------------------------------------------------------------------

def reflect(x: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """Fold values back into [lo, hi] as a mirror would, however far they overshoot."""
    width = hi - lo
    y = np.mod(x - lo, 2.0 * width)
    return lo + np.where(y > width, 2.0 * width - y, y)


def wrap_angle(x: np.ndarray) -> np.ndarray:
    """An angle in [-pi, pi)."""
    return np.mod(x + math.pi, 2.0 * math.pi) - math.pi


def mutate(cfg: Config, mode: str, parents: np.ndarray, sigma: float, rng: np.random.Generator) -> np.ndarray:
    """Every number of every parent moves by a normal step of sd ``sigma`` times its range's width; a step past a
    bound is reflected back inside, and the cilium angle alpha wraps around the circle."""
    lo, hi = genome_ranges(cfg, mode)
    child = parents + rng.standard_normal(parents.shape) * (sigma * (hi - lo))
    out = reflect(child, lo, hi)
    a = layout(cfg, mode).alpha.start
    out[:, a] = wrap_angle(child[:, a])
    return out


def initial_population(cfg: Config, mode: str, ga: GA, seed: int) -> np.ndarray:
    """Generation 0: uniform over the ranges, from stream ``evolution`` keyed by (0,)."""
    return random_genomes(cfg, mode, ga.population, stream(seed, STREAM_EVOLUTION, (0,)))


def next_population(cfg: Config, mode: str, ga: GA, population: np.ndarray, fitness: np.ndarray, seed: int,
                    generation: int) -> np.ndarray:
    """Generation ``generation``'s genomes (>= 1) from the previous generation's and their fitness: the best
    ``elites`` unchanged, then children of parents drawn uniformly from the best ``parents`` (ties keep the earlier
    genome), from stream ``evolution`` keyed by (generation,)."""
    if generation < 1:
        raise ValueError("generation 0 is the initial population")
    rng = stream(seed, STREAM_EVOLUTION, (generation,))
    order = np.argsort(-np.asarray(fitness), kind="stable")
    picks = rng.integers(0, ga.parents, size=ga.population - ga.elites)
    children = mutate(cfg, mode, population[order[picks]], ga.sigma, rng)
    return np.concatenate([population[order[:ga.elites]], children])


def training_starts(cfg: Config, ga: GA, seed: int, generation: int) -> Starts:
    """The generation's training starts: drawn by the cave's rule from stream ``train`` keyed by (generation,), and
    numbered uniquely within the run (the numbers key the noise)."""
    starts = sample_starts(cfg, "cave", ga.train_starts, seed, stream_name=STREAM_TRAIN, key=(generation,))
    return starts.renumbered(generation * ga.train_starts + np.arange(1, ga.train_starts + 1))


def validation_starts(cfg: Config, ga: GA) -> Starts:
    return sample_starts(cfg, "cave", ga.validation_starts, ga.validation_seed)


# --- jobs (module level, so a process pool can run them) ----------------------------------------------------------------

def train_job(job: Mapping[str, Any]) -> Dict[str, np.ndarray]:
    """Some genomes on one training start, as one batch."""
    genomes = np.asarray(job["genomes"])
    n = genomes.shape[0]
    r = simulate(job["cfg"], job["starts"].take([job["start"]] * n), {"controller": "network", "mode": job["mode"], "genomes": genomes},
                 seed=job["seed"], cell_ids=[NOISE_CELL_ID] * n)
    return {"fitness": r.fitness, "survived": r.survived, "mean_beat": r.mean_beat, "light_soaked": r.light_soaked}


def validation_job(job: Mapping[str, Any]) -> Dict[str, float]:
    """One genome on every validation start, as one batch."""
    starts: Starts = job["starts"]
    n = len(starts)
    r = simulate(job["cfg"], starts, {"controller": "network", "mode": job["mode"], "genomes": np.repeat(np.asarray(job["genome"])[None], n, axis=0)},
                 seed=job["seed"], cell_ids=[NOISE_CELL_ID] * n)
    return {"fitness": float(r.fitness.mean()), "survival": float(r.survived.mean()), "mean_beat": float(r.mean_beat.mean())}


def evaluate(cfg: Config, mode: str, ga: GA, population: np.ndarray, seed: int, generation: int, mapper: Mapper) -> Dict[str, np.ndarray]:
    """Every genome on the generation's training starts: its fitness (the mean over the starts), and the per-start
    matrices ``(population, starts)``."""
    starts = training_starts(cfg, ga, seed, generation)
    jobs = [{"cfg": cfg, "mode": mode, "seed": seed, "starts": starts, "start": s, "genomes": population[c:c + ga.chunk]}
            for s in range(ga.train_starts) for c in range(0, ga.population, ga.chunk)]
    parts = list(mapper(train_job, jobs))
    n_chunks = ga.population // ga.chunk
    out = {}
    for key in ("fitness", "survived", "mean_beat", "light_soaked"):
        out[key] = np.stack([np.concatenate([parts[s * n_chunks + c][key] for c in range(n_chunks)]) for s in range(ga.train_starts)], axis=1)
    out["mean_fitness"] = out["fitness"].mean(axis=1)
    return out


# --- a run --------------------------------------------------------------------------------------------------------------

GENERATION_COLUMNS = ("generation", "shade_floor", "best_fitness", "median_fitness", "mean_fitness", "best_survival", "share_surviving_all",
                      "best_mean_beat", "seconds")
VALIDATION_COLUMNS = ("generation", "rank", "train_fitness", "validation_fitness", "validation_survival", "validation_mean_beat", "champion")


def _save_checkpoint(path: Path, state: Mapping[str, Any]) -> None:
    tmp = path.with_suffix(".tmp.npz")
    np.savez(tmp, population=state["population"], champion=state["champion"],
             meta=np.array(json.dumps({k: state[k] for k in ("next_generation", "history", "validation", "champion_info")})))
    os.replace(tmp, path)


def _load_checkpoint(path: Path) -> Dict[str, Any]:
    with np.load(path, allow_pickle=False) as z:
        meta = json.loads(str(z["meta"]))
        return {"population": z["population"].copy(), "champion": z["champion"].copy(), **meta}


def run(cfg: Config, mode: str, ga: GA, seed: int, out: Path, mapper: Mapper, *, log: Callable[[str], None] = print,
        stop_after: Optional[int] = None, world_for: Optional[Callable[[int], Config]] = None, champion_from: int = 1) -> Dict[str, Any]:
    """Evolve one run, checkpointing after every generation to ``out/checkpoint.npz`` and resuming from it if it is
    there. ``stop_after`` ends this call after that many generations (a resumed call goes on from there). Returns the
    run's state; when the run is complete it also writes ``generations.csv``, ``validation.csv``, ``champion.npy``,
    ``champion.json`` and ``population.npy``.

    ``world_for(generation)`` (1-based), when given, is the world the generation's training starts run in (stage 3b's
    amendment A1 fades the cell's shading this way); validation always runs in ``cfg``. Only checkpoints at or after
    generation ``champion_from`` can supply the champion; earlier ones are recorded. With neither given, a run is the
    same bits as before they existed."""
    out.mkdir(parents=True, exist_ok=True)
    ckpt = out / "checkpoint.npz"
    vstarts = validation_starts(cfg, ga)
    if ckpt.exists():
        state = _load_checkpoint(ckpt)
        log(f"resumed at generation {state['next_generation']}")
    else:
        state = {"population": initial_population(cfg, mode, ga, seed), "champion": np.full(layout(cfg, mode).length, np.nan),
                 "next_generation": 0, "history": [], "validation": [], "champion_info": None}
    done = 0
    while state["next_generation"] < ga.generations and (stop_after is None or done < stop_after):
        g = state["next_generation"]
        t0 = time.time()
        pop = state["population"]
        train_cfg = cfg if world_for is None else world_for(g + 1)
        ev = evaluate(train_cfg, mode, ga, pop, seed, g, mapper)
        fit = ev["mean_fitness"]
        order = np.argsort(-fit, kind="stable")
        best = int(order[0])
        if (g + 1) % ga.validate_every == 0:
            top = order[:ga.validate_top]
            jobs = [{"cfg": cfg, "mode": mode, "seed": ga.validation_seed, "starts": vstarts, "genome": pop[i]} for i in top]
            for rank, (i, v) in enumerate(zip(top, mapper(validation_job, jobs)), start=1):
                info = state["champion_info"]
                better = (g + 1) >= champion_from and (info is None or v["fitness"] > info["validation_fitness"])
                if better:
                    state["champion"] = pop[i].copy()
                    state["champion_info"] = {"generation": g + 1, "rank": rank, "train_fitness": float(fit[i]),
                                              "validation_fitness": v["fitness"], "validation_survival": v["survival"]}
                state["validation"].append({"generation": g + 1, "rank": rank, "train_fitness": float(fit[i]), "validation_fitness": v["fitness"],
                                            "validation_survival": v["survival"], "validation_mean_beat": v["mean_beat"], "champion": int(better)})
        row = {"generation": g + 1, "shade_floor": train_cfg.shade_floor, "best_fitness": float(fit[best]), "median_fitness": float(np.median(fit)), "mean_fitness": float(fit.mean()),
               "best_survival": float(ev["survived"][best].mean()), "share_surviving_all": float(ev["survived"].all(axis=1).mean()),
               "best_mean_beat": float(ev["mean_beat"][best].mean()), "seconds": round(time.time() - t0, 3)}
        state["history"].append(row)
        log(f"generation {g + 1:3d}: best {row['best_fitness']:.3f}, median {row['median_fitness']:.3f}, best survives {row['best_survival']:.0%}, "
            f"all-surviving {row['share_surviving_all']:.0%}" + (f"; champion {state['champion_info']['validation_fitness']:.3f} (gen {state['champion_info']['generation']})"
                                                                    if state["champion_info"] else "") + f" [{row['seconds']:.0f} s]")
        if g + 1 < ga.generations:
            state["population"] = next_population(cfg, mode, ga, pop, fit, seed, g + 1)
        state["next_generation"] = g + 1
        _save_checkpoint(ckpt, state)
        done += 1
    if state["next_generation"] >= ga.generations:
        _write_outputs(out, mode, seed, state)
    return state


def _write_outputs(out: Path, mode: str, seed: int, state: Mapping[str, Any]) -> None:
    write_csv(out / "generations.csv", GENERATION_COLUMNS, state["history"])
    write_csv(out / "validation.csv", VALIDATION_COLUMNS, state["validation"])
    np.save(out / "champion.npy", np.asarray(state["champion"])[None])
    np.save(out / "population.npy", np.asarray(state["population"]))
    (out / "champion.json").write_text(json.dumps({"mode": mode, "seed": seed, **(state["champion_info"] or {}),
                                                   "genome": np.asarray(state["champion"]).tolist()}, indent=1) + "\n")
