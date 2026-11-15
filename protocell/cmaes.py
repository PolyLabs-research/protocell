"""CMA-ES, the covariance matrix adaptation evolution strategy (docs/prereg/stage4c.md §3), as a second search beside
stage 1's genetic algorithm (protocell/evolve.py).

The strategy keeps a normal distribution over genomes: a mean, a step size and a covariance. Each generation it
samples ``population`` genomes, ranks them by fitness, moves the mean toward the best half (weighted), and adapts the
step size and the covariance from the steps that worked (Hansen 2016, "The CMA Evolution Strategy: A Tutorial",
with its default constants). The GA mutates every gene by the same fixed share of its range; CMA-ES learns how far to
step and in which directions.

Genes live in normalised coordinates, 0 to 1 across each gene's range. The distribution is unbounded; a genome is read
from a sample by mirroring each coordinate back into [0, 1] (the cilium angle wraps around its circle instead), so the
updates never see a repaired point and stay unbiased.

Every source of randomness is keyed by the run's seed: stream ``cmaes`` keyed by () for the starting mean and by
(generation,) for a generation's samples. A run resumed from its checkpoint is the same bits as one run straight
through (tested). Evaluation, validation and the champion's choice are the GA's (``protocell.evolve``).
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional

import numpy as np

from protocell.cell import genome_ranges, layout
from protocell.config import Config
from protocell.evolve import GA, Mapper, VALIDATION_COLUMNS, evaluate, validation_job, validation_starts
from protocell.rng import stream
from protocell.tables import write_csv

STREAM_CMAES = "cmaes"
GENERATION_COLUMNS = ("generation", "shade_floor", "eta", "sigma", "best_fitness", "median_fitness", "mean_fitness", "best_survival",
                      "share_surviving_all", "best_mean_beat", "seconds")


@dataclass(frozen=True)
class CMA:
    """The strategy's numbers (stage4c.md §3), each with its reason there."""

    population: int = 96  # lambda: the GA's population, so a generation costs the same
    sigma0: float = 0.3  # the first step, in normalised units: about the spread of the GA's uniform first population (0.29)
    generations: int = 200
    train_starts: int = 8
    chunk: int = 48
    validate_every: int = 10
    validate_top: int = 3  # the best three samples, and the distribution's mean beside them
    validation_starts: int = 24
    validation_seed: int = 20

    @staticmethod
    def quick() -> "CMA":
        """The smoke test's sizes: not a result."""
        return CMA(population=8, generations=3, train_starts=2, chunk=4, validate_every=1, validate_top=2, validation_starts=2)

    def as_ga(self) -> GA:
        """The GA's settings that evaluation and validation read (its selection numbers go unused)."""
        return GA(population=self.population, elites=1, parents=self.population, generations=self.generations, train_starts=self.train_starts,
                  chunk=self.chunk, validate_every=self.validate_every, validate_top=self.validate_top,
                  validation_starts=self.validation_starts, validation_seed=self.validation_seed)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def but(self, **changes: Any) -> "CMA":
        return replace(self, **changes)


class Strategy:
    """CMA-ES's state and its two steps, ``ask`` (sample) and ``tell`` (update from the ranking), for maximising.
    Constants as Hansen's tutorial (2016) sets them for dimension n and population lambda, with mu = lambda / 2 and
    positive weights only."""

    def __init__(self, n: int, population: int, mean: np.ndarray, sigma: float) -> None:
        self.n, self.lam = int(n), int(population)
        self.mu = self.lam // 2
        w = math.log((self.lam + 1) / 2.0) - np.log(np.arange(1, self.mu + 1))
        self.weights = w / w.sum()
        self.mueff = 1.0 / float(np.sum(self.weights ** 2))
        n_, mueff = float(self.n), self.mueff
        self.cs = (mueff + 2.0) / (n_ + mueff + 5.0)
        self.ds = 1.0 + 2.0 * max(0.0, math.sqrt((mueff - 1.0) / (n_ + 1.0)) - 1.0) + self.cs
        self.cc = (4.0 + mueff / n_) / (n_ + 4.0 + 2.0 * mueff / n_)
        self.c1 = 2.0 / ((n_ + 1.3) ** 2 + mueff)
        self.cmu = min(1.0 - self.c1, 2.0 * (mueff - 2.0 + 1.0 / mueff) / ((n_ + 2.0) ** 2 + mueff))
        self.chi = math.sqrt(n_) * (1.0 - 1.0 / (4.0 * n_) + 1.0 / (21.0 * n_ * n_))
        self.mean = np.asarray(mean, dtype=np.float64).copy()
        self.sigma = float(sigma)
        self.C = np.eye(self.n)
        self.ps = np.zeros(self.n)
        self.pc = np.zeros(self.n)
        self.updates = 0
        self._decompose()

    def _decompose(self) -> None:
        self.C = 0.5 * (self.C + self.C.T)
        d2, self.B = np.linalg.eigh(self.C)
        self.D = np.sqrt(np.maximum(d2, 1e-30))
        self.invsqrtC = (self.B / self.D) @ self.B.T

    def ask(self, rng: np.random.Generator) -> np.ndarray:
        """``population`` samples, ``(lambda, n)``: mean + sigma B (D z), z standard normal."""
        z = rng.standard_normal((self.lam, self.n))
        return self.mean[None, :] + self.sigma * (z * self.D[None, :]) @ self.B.T

    def tell(self, samples: np.ndarray, fitness: np.ndarray) -> None:
        """One update from the samples ``ask`` gave and their fitness (higher is better; ties keep the earlier)."""
        order = np.argsort(-np.asarray(fitness, dtype=np.float64), kind="stable")[: self.mu]
        y = (samples[order] - self.mean[None, :]) / self.sigma
        yw = self.weights @ y
        self.mean = self.mean + self.sigma * yw
        self.updates += 1
        self.ps = (1.0 - self.cs) * self.ps + math.sqrt(self.cs * (2.0 - self.cs) * self.mueff) * (self.invsqrtC @ yw)
        norm = float(np.linalg.norm(self.ps))
        hsig = 1.0 if norm / math.sqrt(1.0 - (1.0 - self.cs) ** (2 * self.updates)) < (1.4 + 2.0 / (self.n + 1.0)) * self.chi else 0.0
        self.pc = (1.0 - self.cc) * self.pc + hsig * math.sqrt(self.cc * (2.0 - self.cc) * self.mueff) * yw
        rank_mu = (y * self.weights[:, None]).T @ y
        self.C = ((1.0 + self.c1 * (1.0 - hsig) * self.cc * (2.0 - self.cc) - self.c1 - self.cmu) * self.C
                  + self.c1 * np.outer(self.pc, self.pc) + self.cmu * rank_mu)
        self.sigma = self.sigma * math.exp((self.cs / self.ds) * (norm / self.chi - 1.0))
        self._decompose()

    def state(self) -> Dict[str, np.ndarray]:
        return {"mean": self.mean, "sigma": np.array(self.sigma), "C": self.C, "ps": self.ps, "pc": self.pc, "updates": np.array(self.updates)}

    @classmethod
    def restore(cls, n: int, population: int, saved: Mapping[str, np.ndarray]) -> "Strategy":
        s = cls(n, population, saved["mean"], float(saved["sigma"]))
        s.C, s.ps, s.pc, s.updates = saved["C"].copy(), saved["ps"].copy(), saved["pc"].copy(), int(saved["updates"])
        s._decompose()
        return s


def to_genomes(cfg: Config, mode: str, samples: np.ndarray) -> np.ndarray:
    """Genomes from normalised samples: each coordinate mirrored back into [0, 1] and scaled to its gene's range; the
    cilium angle wraps around its circle."""
    lo, hi = genome_ranges(cfg, mode)
    y = np.mod(samples, 2.0)
    mirrored = np.where(y > 1.0, 2.0 - y, y)
    a = layout(cfg, mode).alpha.start
    mirrored[:, a] = np.mod(samples[:, a], 1.0)
    return lo + mirrored * (hi - lo)


def normalised(cfg: Config, mode: str, genome: np.ndarray) -> np.ndarray:
    """A genome in the strategy's coordinates, 0 to 1 across each gene's range: ``to_genomes``'s inverse inside the
    ranges."""
    lo, hi = genome_ranges(cfg, mode)
    g = np.asarray(genome, dtype=np.float64)
    if g.shape != lo.shape or np.any(g < lo - 1e-12) or np.any(g > hi + 1e-12):
        raise ValueError("the starting genome must lie within the genes' ranges")
    return (g - lo) / (hi - lo)


def _save(path: Path, strategy: Strategy, state: Mapping[str, Any]) -> None:
    tmp = path.with_suffix(".tmp.npz")
    np.savez(tmp, champion=state["champion"], samples=state["samples"], **strategy.state(),
             meta=np.array(json.dumps({k: state[k] for k in ("next_generation", "history", "validation", "champion_info", "validation_by_world")
                                       if k in state})))
    os.replace(tmp, path)


def _load(path: Path, n: int, population: int) -> "tuple[Strategy, Dict[str, Any]]":
    with np.load(path, allow_pickle=False) as z:
        meta = json.loads(str(z["meta"]))
        strategy = Strategy.restore(n, population, {k: z[k] for k in ("mean", "sigma", "C", "ps", "pc", "updates")})
        return strategy, {"champion": z["champion"].copy(), "samples": z["samples"].copy(), **meta}


def run(cfg: Config, mode: str, cma: CMA, seed: int, out: Path, mapper: Mapper, *, log: Callable[[str], None] = print,
        stop_after: Optional[int] = None, world_for: Optional[Callable[[int], Config]] = None, champion_from: int = 1,
        start: Optional[np.ndarray] = None, keep_at: "tuple[int, ...]" = (),
        validation_worlds: "Optional[list[tuple[str, Config, Any]]]" = None) -> Dict[str, Any]:
    """One CMA-ES run, as ``protocell.evolve.run`` runs the GA: training starts drawn fresh each generation with shared
    noise; every ``validate_every`` generations the best samples and the distribution's mean are scored on the fixed
    validation starts, in ``cfg``; the champion is the best on validation from generation ``champion_from`` on;
    ``world_for(generation)`` is a generation's training world. Checkpoints after every generation to
    ``out/checkpoint.npz`` and resumes from it. When complete, writes ``generations.csv``, ``validation.csv``,
    ``mean.npy`` (the final mean's genome) and ``population.npy`` (the last samples' genomes), and, when the run has a
    champion, ``champion.npy`` and ``champion.json``.

    ``start`` (stage 5c), a genome, is where the distribution's mean begins instead of a random draw; it is validated
    before generation 1 and recorded as generation 0, rank 0, the run's reference, never its champion. Without it a run
    is the same bits as before it existed.

    ``keep_at`` (stage 6b) names generations at whose end the run's champion, as it then stands, is also written to
    ``champion-at-<generation>.json``. It changes nothing else about the run.

    ``world_for`` may return several worlds for a generation, which then share its training starts equally (stage 8).
    ``validation_worlds``, (name, world, starts) for each, replaces the single validation: a candidate's validation
    fitness and survival are the means over every world's starts, each world's own numbers are kept, and the finished
    run also writes ``validation_worlds.csv``. Without them a run is the same bits as before."""
    out.mkdir(parents=True, exist_ok=True)
    ckpt = out / "checkpoint.npz"
    ga = cma.as_ga()
    n = layout(cfg, mode).length
    vstarts = validation_starts(cfg, ga)
    if ckpt.exists():
        strategy, state = _load(ckpt, n, cma.population)
        log(f"resumed at generation {state['next_generation']}")
    else:
        mean0 = stream(seed, STREAM_CMAES).random(n) if start is None else normalised(cfg, mode, start)
        strategy = Strategy(n, cma.population, mean0, cma.sigma0)
        state = {"champion": np.full(n, np.nan), "samples": np.zeros((cma.population, n)), "next_generation": 0, "history": [],
                 "validation": [], "champion_info": None}
        if start is not None:
            v = next(iter(mapper(validation_job, [{"cfg": cfg, "mode": mode, "seed": cma.validation_seed, "starts": vstarts, "genome": np.asarray(start)}])))
            state["validation"].append({"generation": 0, "rank": 0, "train_fitness": math.nan, "validation_fitness": v["fitness"],
                                        "validation_survival": v["survival"], "validation_mean_beat": v["mean_beat"], "champion": 0})
            log(f"the start validates at {v['fitness']:.3f}, survival {v['survival']:.0%}")
            _save(ckpt, strategy, state)
    done = 0
    while state["next_generation"] < cma.generations and (stop_after is None or done < stop_after):
        g = state["next_generation"]
        t0 = time.time()
        samples = strategy.ask(stream(seed, STREAM_CMAES, (g + 1,)))
        genomes = to_genomes(cfg, mode, samples)
        train_cfg = cfg if world_for is None else world_for(g + 1)
        ev = evaluate(train_cfg, mode, ga, genomes, seed, g, mapper)
        fit = ev["mean_fitness"]
        order = np.argsort(-fit, kind="stable")
        best = int(order[0])
        if (g + 1) % cma.validate_every == 0:
            candidates = [(f"sample {rank}", genomes[i], float(fit[i])) for rank, i in enumerate(order[: cma.validate_top], start=1)]
            candidates.append(("mean", to_genomes(cfg, mode, strategy.mean[None, :])[0], math.nan))
            if validation_worlds is None:
                jobs = [{"cfg": cfg, "mode": mode, "seed": cma.validation_seed, "starts": vstarts, "genome": genome} for _, genome, _ in candidates]
                results = list(mapper(validation_job, jobs))
            else:
                jobs = [{"cfg": wcfg, "mode": mode, "seed": cma.validation_seed, "starts": wstarts, "genome": genome}
                        for _, genome, _ in candidates for _, wcfg, wstarts in validation_worlds]
                parts = list(mapper(validation_job, jobs))
                sizes = np.array([len(wstarts) for _, _, wstarts in validation_worlds], dtype=np.float64)
                results = []
                for c in range(len(candidates)):
                    mine = parts[c * len(validation_worlds):(c + 1) * len(validation_worlds)]
                    results.append({k: float(np.dot([m[k] for m in mine], sizes) / sizes.sum()) for k in ("fitness", "survival", "mean_beat")})
                    state.setdefault("validation_by_world", []).extend(
                        {"generation": g + 1, "rank": c + 1, "world": wname, "validation_fitness": m["fitness"], "validation_survival": m["survival"]}
                        for (wname, _, _), m in zip(validation_worlds, mine))
            for rank, ((name, genome, train_fit), v) in enumerate(zip(candidates, results), start=1):
                info = state["champion_info"]
                better = (g + 1) >= champion_from and (info is None or v["fitness"] > info["validation_fitness"])
                if better:
                    state["champion"] = np.asarray(genome).copy()
                    state["champion_info"] = {"generation": g + 1, "rank": rank, "candidate": name, "train_fitness": train_fit,
                                              "validation_fitness": v["fitness"], "validation_survival": v["survival"]}
                state["validation"].append({"generation": g + 1, "rank": rank, "train_fitness": train_fit, "validation_fitness": v["fitness"],
                                            "validation_survival": v["survival"], "validation_mean_beat": v["mean_beat"], "champion": int(better)})
        several = isinstance(train_cfg, (list, tuple))
        row = {"generation": g + 1, "shade_floor": math.nan if several else train_cfg.shade_floor, "eta": math.nan if several else train_cfg.eta,
               "sigma": strategy.sigma, "best_fitness": float(fit[best]),
               "median_fitness": float(np.median(fit)), "mean_fitness": float(fit.mean()), "best_survival": float(ev["survived"][best].mean()),
               "share_surviving_all": float(ev["survived"].all(axis=1).mean()), "best_mean_beat": float(ev["mean_beat"][best].mean()),
               "seconds": round(time.time() - t0, 3)}
        state["history"].append(row)
        strategy.tell(samples, fit)
        state["samples"] = samples
        log(f"generation {g + 1:3d}: best {row['best_fitness']:.3f}, median {row['median_fitness']:.3f}, best survives {row['best_survival']:.0%}, "
            f"sigma {row['sigma']:.3f}" + (f"; champion {state['champion_info']['validation_fitness']:.3f} (gen {state['champion_info']['generation']}, "
                                         f"{state['champion_info']['candidate']})" if state["champion_info"] else "") + f" [{row['seconds']:.0f} s]")
        state["next_generation"] = g + 1
        _save(ckpt, strategy, state)
        if (g + 1) in keep_at and state["champion_info"] is not None:
            (out / f"champion-at-{g + 1}.json").write_text(json.dumps({"mode": mode, "seed": seed, **state["champion_info"],
                                                                       "genome": np.asarray(state["champion"]).tolist()}, indent=1) + "\n")
        done += 1
    if state["next_generation"] >= cma.generations:
        write_csv(out / "generations.csv", GENERATION_COLUMNS, state["history"])
        write_csv(out / "validation.csv", VALIDATION_COLUMNS, state["validation"])
        if state.get("validation_by_world"):
            write_csv(out / "validation_worlds.csv", ("generation", "rank", "world", "validation_fitness", "validation_survival"), state["validation_by_world"])
        np.save(out / "mean.npy", to_genomes(cfg, mode, strategy.mean[None, :]))
        np.save(out / "population.npy", to_genomes(cfg, mode, state["samples"]))
        if state["champion_info"] is not None:  # a run that ends before champion_from (stage 4c's check) has none
            np.save(out / "champion.npy", np.asarray(state["champion"])[None])
            (out / "champion.json").write_text(json.dumps({"mode": mode, "seed": seed, **state["champion_info"],
                                                           "genome": np.asarray(state["champion"]).tolist()}, indent=1) + "\n")
    return {**state, "strategy": strategy}
