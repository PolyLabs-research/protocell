"""The simulation (docs/prereg/stage0.md §3–§6): a whole population at once, each cell a row of the arrays.

The tick (§11 C1): sense at the current pose -> update the network -> beats -> move (velocity, rotation, noise, the
dish's edge) -> energy (this tick's noiseless light, this tick's beats) -> damage -> the death check. A cell dead at a
tick's end counts 0 for that tick in every per-tick measure, and dead cells do not move.

Noise (§11 C4): each cell draws from its own keyed streams, ``(cell, start)``, in chunks of ``NOISE_CHUNK`` ticks, so a
cell's draws are the same bits whether it runs alone or in a batch (W6). A stream's standard deviation of 0 switches
it off (no generator is made), which leaves every other stream's draws as they were.

Controllers: the four of §6 (B0 still, B1 random beating, B2 the reflex) and the network cell (§3), built from a plain
spec so a job can cross a process boundary.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from protocell.cell import Params, ctrnn_step, decode, sigmoid
from protocell.config import Config
from protocell.energy import damage_step, energy_step
from protocell.motion import cilia_motion, move
from protocell.rng import stream
from protocell.world import Starts, centre_light, node_light, source_distance

NOISE_CHUNK = 250  # ticks of draws made at once; chunking does not change a generator's sequence (tested)
STREAM_SENSORS = "sensors"
STREAM_MOTION = "motion"
STREAM_BEATS = "beats"
BASELINE_CELL_ID = 0  # B0–B2 share this id, so every baseline (and every reflex gain) sees the same noise on a start


class CellNoise:
    """One named stream's draws for P cells, each from its own keyed generator, ``distribution`` "normal" (scaled by
    ``scale``) or "uniform" (in [0, 1)). ``at(tick)`` is the draw for that tick, ``(P, *per_tick)``. ``digest`` is a
    SHA-256 over every draw made so far (the independence check of W6 reads it)."""

    def __init__(self, seed: int, name: str, keys: Sequence[Tuple[int, int]], per_tick: Tuple[int, ...],
                 distribution: str, scale: float = 1.0) -> None:
        if distribution not in ("normal", "uniform"):
            raise ValueError(distribution)
        self.name = name
        self.generators = [stream(seed, name, key) for key in keys]
        self.per_tick = tuple(per_tick)
        self.distribution = distribution
        self.scale = scale
        self._chunk: Optional[np.ndarray] = None
        self._chunk_start = -1
        self._digest = hashlib.sha256()

    def _refill(self, start: int) -> None:
        size = (NOISE_CHUNK, *self.per_tick)
        if self.distribution == "normal":
            draws = np.stack([g.standard_normal(size) for g in self.generators])
            if self.scale != 1.0:
                draws = draws * self.scale
        else:
            draws = np.stack([g.random(size) for g in self.generators])
        self._chunk, self._chunk_start = draws, start
        self._digest.update(draws.tobytes())

    def at(self, tick: int) -> np.ndarray:
        start = (tick // NOISE_CHUNK) * NOISE_CHUNK
        if self._chunk is None or start != self._chunk_start:
            if self._chunk is not None and start != self._chunk_start + NOISE_CHUNK:
                raise ValueError("ticks must be asked for in order")
            self._refill(start)
        assert self._chunk is not None
        return self._chunk[:, tick - start]

    @property
    def digest(self) -> str:
        return self._digest.hexdigest()


class Controller:
    """Turns the sensed light ``(P, N)`` into the beats ``(P, N)`` each tick; ``alpha`` ``(P,)`` is its cilium angle."""

    alpha: np.ndarray

    def beats(self, sensed: np.ndarray, tick: int) -> np.ndarray:
        raise NotImplementedError

    def noise_digests(self) -> Dict[str, str]:
        return {}


class Still(Controller):
    """B0: no cilium ever beats."""

    def __init__(self, cfg: Config, population: int) -> None:
        self.alpha = np.zeros(population)
        self._zeros = np.zeros((population, cfg.n_wall))

    def beats(self, sensed: np.ndarray, tick: int) -> np.ndarray:
        return self._zeros


class RandomBeating(Controller):
    """B1: each g_i uniform in (0, 1) each tick, from stream ``beats`` (§11 C5); alpha = 0."""

    def __init__(self, cfg: Config, population: int, noise: CellNoise) -> None:
        self.alpha = np.zeros(population)
        self.noise = noise

    def beats(self, sensed: np.ndarray, tick: int) -> np.ndarray:
        return self.noise.at(tick)

    def noise_digests(self) -> Dict[str, str]:
        return {STREAM_BEATS: self.noise.digest}


class Reflex(Controller):
    """B2: g_i = sigma(k (I_i - mean) / (mean + 0.01)), the mean over the wall of this tick's sensed light (§11 C6);
    alpha = 0: the brighter side beats harder and pulls the cell toward the light."""

    def __init__(self, cfg: Config, population: int, k: float) -> None:
        self.alpha = np.zeros(population)
        self.k = float(k)

    def beats(self, sensed: np.ndarray, tick: int) -> np.ndarray:
        mean = sensed.mean(axis=1, keepdims=True)
        return sigmoid(self.k * (sensed - mean) / (mean + 0.01))


class Network(Controller):
    """The cell of §3: the CTRNN's wall outputs are the beats. The state starts at y = 0; the output sigma(y + bias)
    is computed after each update and serves both as this tick's beats and as the next update's input (§11 C1)."""

    def __init__(self, cfg: Config, params: Params) -> None:
        self.n_wall = cfg.n_wall
        self.params = params
        self.alpha = params.alpha
        self.Wt = np.ascontiguousarray(np.transpose(params.W, (0, 2, 1)))
        self.y = np.zeros_like(params.bias)
        self.output = sigmoid(self.y + params.bias)
        self.sensory = np.zeros_like(params.bias)

    def beats(self, sensed: np.ndarray, tick: int) -> np.ndarray:
        self.sensory[:, :self.n_wall] = self.params.gain[:, None] * sensed
        self.y = ctrnn_step(self.y, self.output, self.Wt, self.params.tau, self.sensory)
        self.output = sigmoid(self.y + self.params.bias)
        return self.output[:, :self.n_wall]


def build_controller(cfg: Config, spec: Mapping[str, Any], population: int, seed: int,
                     keys: Sequence[Tuple[int, int]]) -> Controller:
    """A controller from a plain spec: ``{"controller": "still"}``, ``{"controller": "random"}``,
    ``{"controller": "reflex", "k": 10}`` or ``{"controller": "network", "mode": ..., "genomes": (P, G)}``."""
    kind = spec["controller"]
    if kind == "still":
        return Still(cfg, population)
    if kind == "random":
        return RandomBeating(cfg, population, CellNoise(seed, STREAM_BEATS, keys, (cfg.n_wall,), "uniform"))
    if kind == "reflex":
        return Reflex(cfg, population, spec["k"])
    if kind == "network":
        genomes = np.asarray(spec["genomes"], dtype=np.float64)
        if genomes.shape[0] != population:
            raise ValueError(f"{genomes.shape[0]} genomes for {population} cells")
        return Network(cfg, decode(cfg, spec["mode"], genomes))
    raise ValueError(f"unknown controller {kind!r}")


@dataclass
class RunResult:
    """One batch's outcome, a row per cell (§5): survival, fitness (the mean of E over the lifetime, dead ticks 0),
    light soaked, the mean beat, effort per unit light, the tick the soak region was reached and the tick of death
    (-1: never), the final reserve and damage, the final pose; the trajectory when recorded (``pos`` (P, T, 2),
    ``heading``, ``energy``, ``beat`` (P, T)); and each noise stream's digest."""

    ticks: int
    start_index: np.ndarray
    cell_id: np.ndarray
    survived: np.ndarray
    fitness: np.ndarray
    light_soaked: np.ndarray
    mean_beat: np.ndarray
    effort_per_light: np.ndarray
    reach_tick: np.ndarray
    death_tick: np.ndarray
    final_energy: np.ndarray
    final_damage: np.ndarray
    pos: np.ndarray
    heading: np.ndarray
    noise_digests: Dict[str, str]
    trajectory: Optional[Dict[str, np.ndarray]] = None

    def __len__(self) -> int:
        return int(self.survived.shape[0])

    def _trajectory(self) -> Dict[str, np.ndarray]:
        if self.trajectory is None:
            raise ValueError("the run was not recorded")
        return self.trajectory

    def cell_hash(self, i: int) -> str:
        """SHA-256 over cell i's positions, headings and reserves, tick by tick."""
        t = self._trajectory()
        h = hashlib.sha256()
        for name in ("pos", "heading", "energy"):
            h.update(np.ascontiguousarray(t[name][i]).tobytes())
        return h.hexdigest()

    def run_hash(self) -> str:
        """SHA-256 over the batch's positions, headings and reserves."""
        t = self._trajectory()
        h = hashlib.sha256()
        for name in ("pos", "heading", "energy"):
            h.update(np.ascontiguousarray(t[name]).tobytes())
        return h.hexdigest()

    def rows(self, starts: Starts, **extra: Any) -> List[Dict[str, Any]]:
        """A table row per cell, with the start's number and distance to the source."""
        dist = source_distance(starts.source, starts.pos)
        out = []
        for i in range(len(self)):
            out.append({**extra, "start": int(self.start_index[i]), "cell": int(self.cell_id[i]),
                        "start_distance": float(dist[i]), "survived": int(self.survived[i]),
                        "fitness": float(self.fitness[i]), "light_soaked": float(self.light_soaked[i]),
                        "mean_beat": float(self.mean_beat[i]), "effort_per_light": float(self.effort_per_light[i]),
                        "reach_tick": int(self.reach_tick[i]), "death_tick": int(self.death_tick[i]),
                        "final_energy": float(self.final_energy[i])})
        return out


def simulate(cfg: Config, starts: Starts, controller_spec: Mapping[str, Any], *, seed: int,
             cell_ids: Optional[Sequence[int]] = None, ticks: Optional[int] = None, record: bool = False) -> RunResult:
    """Run every start of the batch for ``ticks`` (the lifetime by default) under one controller spec. ``cell_ids``
    (default: the baselines' 0) key the noise with the start's number."""
    population = len(starts)
    T = cfg.lifetime if ticks is None else int(ticks)
    ids = np.full(population, BASELINE_CELL_ID) if cell_ids is None else np.asarray(list(cell_ids), dtype=np.int64)
    if ids.shape != (population,):
        raise ValueError("one cell id per start")
    keys = [(int(c), int(s)) for c, s in zip(ids.tolist(), starts.index.tolist())]
    controller = build_controller(cfg, controller_spec, population, seed, keys)
    sensors = CellNoise(seed, STREAM_SENSORS, keys, (cfg.n_wall,), "normal", cfg.sensor_noise_sd) if cfg.sensor_noise_sd > 0 else None
    motion = CellNoise(seed, STREAM_MOTION, keys, (), "normal", cfg.rotation_noise_sd) if cfg.rotation_noise_sd > 0 else None

    kind, source = starts.kind, starts.source
    pos, heading = starts.pos.copy(), starts.heading.copy()
    energy = np.full(population, cfg.energy_start)
    damage = np.zeros(population)
    alive = np.ones(population, dtype=bool)
    fitness_sum, soaked_sum, beat_sum = np.zeros(population), np.zeros(population), np.zeros(population)
    reach_tick, death_tick = np.full(population, -1, dtype=np.int64), np.full(population, -1, dtype=np.int64)
    traj_pos: List[np.ndarray] = []
    traj_heading: List[np.ndarray] = []
    traj_energy: List[np.ndarray] = []
    traj_beat: List[np.ndarray] = []

    for t in range(T):
        light = node_light(cfg, kind, source, pos, heading)
        sensed = light + sensors.at(t) if sensors is not None else light
        beats = controller.beats(sensed, t)
        v, omega = cilia_motion(cfg, beats, heading, controller.alpha)
        new_pos, new_heading = move(cfg, pos, heading, v, omega, motion.at(t) if motion is not None else None)
        pos = np.where(alive[:, None], new_pos, pos)
        heading = np.where(alive, new_heading, heading)
        new_energy, soaked, effort = energy_step(cfg, energy, light, beats)
        new_damage = damage_step(cfg, damage, light)
        still_alive = alive & (new_energy > 0.0) & (new_damage < 1.0)
        death_tick = np.where(alive & ~still_alive, t + 1, death_tick)
        energy = np.where(still_alive, new_energy, 0.0)
        damage = np.where(alive, new_damage, damage)
        alive = still_alive
        fitness_sum += energy
        soaked_sum += np.where(alive, soaked, 0.0)
        beat_sum += np.where(alive, effort, 0.0)
        at_centre = centre_light(cfg, kind, source, pos)
        reach_tick = np.where(alive & (reach_tick < 0) & (at_centre >= cfg.soak_threshold), t + 1, reach_tick)
        if record:
            traj_pos.append(pos.copy())
            traj_heading.append(heading.copy())
            traj_energy.append(energy.copy())
            traj_beat.append(np.where(alive, effort, 0.0))

    light_soaked = soaked_sum / T
    mean_beat = beat_sum / T
    effort_per_light = np.full(population, math.nan)
    np.divide(mean_beat, light_soaked, out=effort_per_light, where=light_soaked > 0.0)
    digests = {}
    if sensors is not None:
        digests[STREAM_SENSORS] = sensors.digest
    if motion is not None:
        digests[STREAM_MOTION] = motion.digest
    digests.update(controller.noise_digests())
    trajectory = None
    if record:
        trajectory = {"pos": np.ascontiguousarray(np.transpose(np.stack(traj_pos), (1, 0, 2))),
                      "heading": np.ascontiguousarray(np.stack(traj_heading).T),
                      "energy": np.ascontiguousarray(np.stack(traj_energy).T),
                      "beat": np.ascontiguousarray(np.stack(traj_beat).T)}
    return RunResult(T, starts.index.copy(), ids, alive.copy(), fitness_sum / T, light_soaked, mean_beat,
                     effort_per_light, reach_tick, death_tick, energy.copy(), damage.copy(), pos, heading, digests, trajectory)
