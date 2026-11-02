"""The simulation (docs/prereg/stage0.md §3–§6; docs/prereg/cave.md §4–§8): a whole population at once, each cell a
row of the arrays.

The tick (stage0.md §11 C1): sense at the current pose -> update the network -> beats -> move (velocity, rotation,
noise, the dish's edge) -> energy (this tick's noiseless light, this tick's beats) -> damage -> the death check. A
cell dead at a tick's end counts 0 for that tick in every per-tick measure, and dead cells do not move. In the cave
each cell has its own lifetime (to its second sunrise) and its own time (its phase plus the tick); a batch runs to the
longest lifetime in it and a cell past its own is frozen and no longer counted.

Noise (stage0.md §11 C4): each cell draws from its own keyed streams, ``(cell, start)``, in chunks of ``NOISE_CHUNK``
ticks, so a cell's draws are the same bits whether it runs alone or in a batch (W6). A stream's standard deviation of
0 switches it off (no generator is made), which leaves every other stream's draws as they were.

Controllers: B0 still, B1 random beating, B2 the reflex (and B2r, which rests in the dark, and B2rr, which also
retreats above the damage threshold), and the network cell, built from a plain spec so a job can cross a process
boundary.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np

from protocell.cell import Params, apply_removal, ctrnn_step, decode, hold_at_average, sigmoid
from protocell.config import Config
from protocell.energy import damage_step, energy_step, start_energy
from protocell.motion import cilia_motion, move
from protocell.rng import stream
from protocell.world import Starts, centre_light, daylight, lifetimes, node_light, source_distance

NOISE_CHUNK = 250  # ticks of draws made at once; chunking does not change a generator's sequence (tested)
STREAM_SENSORS = "sensors"
STREAM_MOTION = "motion"
STREAM_BEATS = "beats"
BASELINE_CELL_ID = 0  # B0–B2 share this id, so every baseline (and every reflex gain) sees the same noise on a start
STARVED, BURNT = 1, 2  # a death's cause
Observer = Callable[[int, Mapping[str, Any]], None]


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
    """B1: each g_i uniform in (0, 1) each tick, from stream ``beats`` (stage0.md §11 C5); alpha = 0."""

    def __init__(self, cfg: Config, population: int, noise: CellNoise) -> None:
        self.alpha = np.zeros(population)
        self.noise = noise

    def beats(self, sensed: np.ndarray, tick: int) -> np.ndarray:
        return self.noise.at(tick)

    def noise_digests(self) -> Dict[str, str]:
        return {STREAM_BEATS: self.noise.digest}


class Reflex(Controller):
    """B2: g_i = sigma(k (I_i - mean) / (mean + 0.01)), the mean over the wall of this tick's sensed light (stage0.md
    §11 C6); alpha = 0: the brighter side beats harder and pulls the cell toward the light. With ``rest_below`` (B2r,
    cave.md §8) it does not beat while the mean is below it; with ``retreat_above`` (B2rr) the sign of k reverses
    while the light is above it, so the darker side beats harder and the cell backs out of the burn. ``retreat_on``
    says which light: the wall's ``mean`` (as cave.md §8 preregistered) or its brightest node, ``max`` (amendment A1:
    damage counts each node's light above the threshold, and the lit side gets nearly twice the mean)."""

    def __init__(self, cfg: Config, population: int, k: float, rest_below: Optional[float] = None,
                 retreat_above: Optional[float] = None, retreat_on: str = "mean") -> None:
        if retreat_on not in ("mean", "max"):
            raise ValueError(f"retreat_on is 'mean' or 'max', not {retreat_on!r}")
        self.alpha = np.zeros(population)
        self.k = float(k)
        self.rest_below = rest_below
        self.retreat_above = retreat_above
        self.retreat_on = retreat_on

    def beats(self, sensed: np.ndarray, tick: int) -> np.ndarray:
        mean = sensed.mean(axis=1, keepdims=True)
        contrast = (sensed - mean) / (mean + 0.01)
        g = sigmoid(self.k * contrast)
        if self.retreat_above is not None:
            trigger = mean if self.retreat_on == "mean" else sensed.max(axis=1, keepdims=True)
            g = np.where(trigger > self.retreat_above, sigmoid(-self.k * contrast), g)
        if self.rest_below is not None:
            g = np.where(mean < self.rest_below, 0.0, g)
        return g


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
        self.extra = params.extra  # a constant input, when a pathway is held at its average (stage 1b)

    def beats(self, sensed: np.ndarray, tick: int) -> np.ndarray:
        self.sensory[:, :self.n_wall] = self.params.gain[:, None] * sensed
        inputs = self.sensory if self.extra is None else self.sensory + self.extra
        self.y = ctrnn_step(self.y, self.output, self.Wt, self.params.tau, inputs)
        self.output = sigmoid(self.y + self.params.bias)
        return self.output[:, :self.n_wall]


def build_controller(cfg: Config, spec: Mapping[str, Any], population: int, seed: int,
                     keys: Sequence[Tuple[int, int]]) -> Controller:
    """A controller from a plain spec: ``{"controller": "still"}``, ``{"controller": "random"}``,
    ``{"controller": "reflex", "k": 10}`` (with optional ``rest_below``, ``retreat_above`` and ``retreat_on``) or
    ``{"controller": "network", "mode": ..., "genomes": (P, G)}`` (with an optional ``removal``, stage 1's §7, or
    ``hold``: ``{"pathway": ..., "means": (M,)}``, stage 1b's §1).
    """
    kind = spec["controller"]
    if kind == "still":
        return Still(cfg, population)
    if kind == "random":
        return RandomBeating(cfg, population, CellNoise(seed, STREAM_BEATS, keys, (cfg.n_wall,), "uniform"))
    if kind == "reflex":
        return Reflex(cfg, population, spec["k"], spec.get("rest_below"), spec.get("retreat_above"), spec.get("retreat_on", "mean"))
    if kind == "network":
        genomes = np.asarray(spec["genomes"], dtype=np.float64)
        if genomes.shape[0] != population:
            raise ValueError(f"{genomes.shape[0]} genomes for {population} cells")
        params = decode(cfg, spec["mode"], genomes)
        if spec.get("removal"):
            params = apply_removal(cfg, params, spec["removal"])
        if spec.get("hold"):
            params = hold_at_average(cfg, params, spec["hold"]["pathway"], spec["hold"]["means"])
        return Network(cfg, params)
    raise ValueError(f"unknown controller {kind!r}")


@dataclass
class RunResult:
    """One batch's outcome, a row per cell (stage0.md §5; cave.md §7): survival, fitness (the mean of E over the
    cell's lifetime, dead ticks 0), light soaked, the mean beat, effort per unit light, the tick the soak region was
    reached and the tick of death (-1: never) with its cause (0 none, 1 starved, 2 burnt), the final reserve and
    damage, the least reserve, the least reserve at a sunset (cave only; NaN otherwise), the mean beat at night and
    the shares of the lifetime in the burn zone and the soak zone (cave only), each cell's lifetime, the final pose;
    the trajectory when recorded (``pos`` (P, T, 2), ``heading``, ``energy``, ``beat`` (P, T)); and each noise
    stream's digest."""

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
    death_cause: np.ndarray
    final_energy: np.ndarray
    final_damage: np.ndarray
    min_energy: np.ndarray
    min_sunset_energy: np.ndarray
    night_beat: np.ndarray
    burn_share: np.ndarray
    soak_share: np.ndarray
    lifetime: np.ndarray
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
        """A table row per cell, with the start's number, phase and distance to the source."""
        dist = source_distance(starts.source, starts.pos)
        out = []
        for i in range(len(self)):
            out.append({**extra, "start": int(self.start_index[i]), "cell": int(self.cell_id[i]), "phase": int(starts.phase[i]),
                        "lifetime": int(self.lifetime[i]), "start_distance": float(dist[i]), "survived": int(self.survived[i]),
                        "fitness": float(self.fitness[i]), "light_soaked": float(self.light_soaked[i]),
                        "mean_beat": float(self.mean_beat[i]), "effort_per_light": float(self.effort_per_light[i]),
                        "reach_tick": int(self.reach_tick[i]), "death_tick": int(self.death_tick[i]), "death_cause": int(self.death_cause[i]),
                        "final_energy": float(self.final_energy[i]), "final_damage": float(self.final_damage[i]),
                        "min_energy": float(self.min_energy[i]), "min_sunset_energy": float(self.min_sunset_energy[i]),
                        "night_beat": float(self.night_beat[i]), "burn_share": float(self.burn_share[i]), "soak_share": float(self.soak_share[i])})
        return out


def simulate(cfg: Config, starts: Starts, controller_spec: Mapping[str, Any], *, seed: int,
             cell_ids: Optional[Sequence[int]] = None, ticks: Optional[int] = None, record: bool = False,
             observe: Optional[Observer] = None) -> RunResult:
    """Run every start of the batch under one controller spec, each for its own lifetime (``ticks`` overrides it for
    every cell). ``cell_ids`` (default: the baselines' 0) key the noise with the start's number.

    ``observe(t, state)``, when given, is called at the end of every tick t with the batch's state: ``time`` (each
    cell's time at the tick's start), ``light`` and ``sensed`` (at the pose the tick began with), ``beats``, then
    ``pos``, ``heading``, ``energy``, ``damage``, ``alive`` and ``active`` after the tick, and the ``controller``. It
    only reads: the arrays may be reused, so it copies what it keeps, and a run's results are the same bits with or
    without it (tested). The replays use it (``tools/replay.py``)."""
    population = len(starts)
    ends = lifetimes(cfg, starts) if ticks is None else np.full(population, int(ticks), dtype=np.int64)
    T = int(ends.max())
    ids = np.full(population, BASELINE_CELL_ID) if cell_ids is None else np.asarray(list(cell_ids), dtype=np.int64)
    if ids.shape != (population,):
        raise ValueError("one cell id per start")
    keys = [(int(c), int(s)) for c, s in zip(ids.tolist(), starts.index.tolist())]
    controller = build_controller(cfg, controller_spec, population, seed, keys)
    sensors = CellNoise(seed, STREAM_SENSORS, keys, (cfg.n_wall,), "normal", cfg.sensor_noise_sd) if cfg.sensor_noise_sd > 0 else None
    motion = CellNoise(seed, STREAM_MOTION, keys, (), "normal", cfg.rotation_noise_sd) if cfg.rotation_noise_sd > 0 else None

    kind, source, cave = starts.kind, starts.source, starts.kind == "cave"
    half = cfg.day_ticks // 2
    pos, heading = starts.pos.copy(), starts.heading.copy()
    energy = start_energy(cfg, kind, starts.phase)
    damage = np.zeros(population)
    alive = np.ones(population, dtype=bool)
    fitness_sum, soaked_sum, beat_sum = np.zeros(population), np.zeros(population), np.zeros(population)
    reach_tick, death_tick = np.full(population, -1, dtype=np.int64), np.full(population, -1, dtype=np.int64)
    death_cause = np.zeros(population, dtype=np.int64)
    min_energy = energy.copy()
    min_sunset_energy = np.full(population, math.nan)
    night_beat_sum, night_ticks = np.zeros(population), np.zeros(population, dtype=np.int64)
    burn_ticks, soak_ticks = np.zeros(population, dtype=np.int64), np.zeros(population, dtype=np.int64)
    traj_pos: List[np.ndarray] = []
    traj_heading: List[np.ndarray] = []
    traj_energy: List[np.ndarray] = []
    traj_beat: List[np.ndarray] = []

    for t in range(T):
        time = starts.phase + t
        active = alive & (t < ends)
        light = node_light(cfg, kind, source, pos, heading, time)
        sensed = light + sensors.at(t) if sensors is not None else light
        beats = controller.beats(sensed, t)
        v, omega = cilia_motion(cfg, beats, heading, controller.alpha)
        new_pos, new_heading = move(cfg, pos, heading, v, omega, motion.at(t) if motion is not None else None)
        pos = np.where(active[:, None], new_pos, pos)
        heading = np.where(active, new_heading, heading)
        new_energy, soaked, effort = energy_step(cfg, energy, light, beats)
        new_damage = damage_step(cfg, damage, light)
        starved = active & (new_energy <= 0.0)
        burnt = active & ~starved & (new_damage >= 1.0)
        dead_now = starved | burnt
        death_tick = np.where(dead_now, t + 1, death_tick)
        death_cause = np.where(starved, STARVED, np.where(burnt, BURNT, death_cause))
        energy = np.where(active, np.where(dead_now, 0.0, new_energy), energy)
        damage = np.where(active, new_damage, damage)
        alive = alive & ~dead_now
        counting = active & alive
        fitness_sum += np.where(active, energy, 0.0)
        soaked_sum += np.where(counting, soaked, 0.0)
        beat_sum += np.where(counting, effort, 0.0)
        at_centre = centre_light(cfg, kind, source, pos, time)
        reach_tick = np.where(counting & (reach_tick < 0) & (at_centre >= cfg.soak_threshold), t + 1, reach_tick)
        if cave:
            night = active & (daylight(cfg, time) == 0.0)
            night_ticks += night
            night_beat_sum += np.where(night & alive, effort, 0.0)
            burn_ticks += counting & (at_centre >= cfg.damage_threshold)
            soak_ticks += counting & (at_centre >= cfg.soak_threshold)
            min_energy = np.where(counting, np.minimum(min_energy, energy), min_energy)
            sunset = counting & ((time % cfg.day_ticks) == half)
            min_sunset_energy = np.where(sunset, np.fmin(min_sunset_energy, energy), min_sunset_energy)
        if record:
            traj_pos.append(pos.copy())
            traj_heading.append(heading.copy())
            traj_energy.append(energy.copy())
            traj_beat.append(np.where(counting, effort, 0.0))
        if observe is not None:
            observe(t, {"time": time, "light": light, "sensed": sensed, "beats": beats, "pos": pos, "heading": heading,
                        "energy": energy, "damage": damage, "alive": alive, "active": active, "controller": controller})

    light_soaked = soaked_sum / ends
    mean_beat = beat_sum / ends
    effort_per_light = np.full(population, math.nan)
    np.divide(mean_beat, light_soaked, out=effort_per_light, where=light_soaked > 0.0)
    night_beat = np.full(population, math.nan)
    np.divide(night_beat_sum, night_ticks, out=night_beat, where=night_ticks > 0)
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
    return RunResult(T, starts.index.copy(), ids, alive.copy(), fitness_sum / ends, light_soaked, mean_beat,
                     effort_per_light, reach_tick, death_tick, death_cause, energy.copy(), damage.copy(), min_energy,
                     min_sunset_energy, night_beat, burn_ticks / ends, soak_ticks / ends, ends.copy(), pos, heading, digests, trajectory)
