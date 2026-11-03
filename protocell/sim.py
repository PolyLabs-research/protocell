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
retreats above the damage threshold), B5 run and wait, B6 read and run and B7 run anywhere, and the network cell, built
from a plain spec so a job can cross a process boundary.

The senses (docs/prereg/stage3c.md §3.1): with ``sense_contrast`` other than 1, the nodes sense a transform of the
light that keeps the wall's mean; the energy and damage use the light itself.
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
from protocell.world import Sky, Starts, centre_light, daylight, lifetimes, node_light, source_distance

NOISE_CHUNK = 250  # ticks of draws made at once; chunking does not change a generator's sequence (tested)
STREAM_SENSORS = "sensors"
STREAM_MOTION = "motion"
STREAM_BEATS = "beats"
STREAM_WALK = "walk"  # B7's run directions (docs/prereg/stage3c.md §5)
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


class RunAndWait(Controller):
    """B5 (docs/prereg/stage3.md §3): the simplest cell that compares over time. Its memory is one number per cell, an
    exponential average m of the wall's mean sensed light, m <- m + (mean - m) / tau, starting at the first reading.
    Each tick: in the dark (mean < ``rest_below``) it rests; if the light is rising (mean > m, the reading compared with
    the average of the readings before it) it runs, the nodes on its front half (cos theta_i > 0) beating fully, the
    rest not at all, so with alpha = 0 it swims straight ahead; otherwise it waits and its rotational noise turns it."""

    FRONT_TOLERANCE = 1e-9  # the node at 90 degrees has cos = 6e-17 in floating point: it is not on the front half

    def __init__(self, cfg: Config, population: int, tau: float, rest_below: float) -> None:
        if tau < 1.0:
            raise ValueError("the memory's time constant is at least one tick")
        self.alpha = np.zeros(population)
        self.tau = float(tau)
        self.rest_below = float(rest_below)
        theta = 2.0 * math.pi * np.arange(cfg.n_wall) / cfg.n_wall
        self.front = (np.cos(theta) > self.FRONT_TOLERANCE).astype(np.float64)[None, :]
        self.memory: Optional[np.ndarray] = None

    def beats(self, sensed: np.ndarray, tick: int) -> np.ndarray:
        mean = sensed.mean(axis=1, keepdims=True)
        if self.memory is None:
            self.memory = mean.copy()
        rising = mean > self.memory
        self.memory = self.memory + (mean - self.memory) / self.tau
        g = np.where(rising, self.front, 0.0)
        return np.where(mean < self.rest_below, 0.0, g)


class ReadAndRun(Controller):
    """B6 and B7 (docs/prereg/stage3c.md §5): the stage 3c champion's timing with one rule each; alpha = 0.

    It cycles every ``cycle`` ticks from its first: idle, then a run of ``run`` ticks in which the half of the wall
    facing a direction psi in the body's frame (the nodes with cos(theta_i - psi) > 0) beats fully and the rest not at
    all. B6 (``aim="read"``) takes psi at each run's first tick from its sensed light: the direction of the wall's
    first Fourier mode, sum_i s_i e^(i theta_i), summed over the idle phase just ended. B7 (``aim="random"``) draws psi
    uniformly from stream ``walk`` instead. In the dark (the wall's mean sensed light below ``rest_below``) it rests,
    as B2r and B5 do, and in bright light (at least ``still_above``) it keeps still; the cycle runs on regardless."""

    HALF_TOLERANCE = 1e-9  # a node exactly at right angles to psi is not on the half that beats

    def __init__(self, cfg: Config, population: int, aim: str, cycle: int, run: int, rest_below: float, still_above: float,
                 noise: Optional[CellNoise] = None) -> None:
        if aim not in ("read", "random"):
            raise ValueError(f"aim is 'read' or 'random', not {aim!r}")
        if not 0 < run < cycle:
            raise ValueError("a run is at least one tick and shorter than the cycle")
        if (aim == "random") != (noise is not None):
            raise ValueError("B7 draws its directions from stream walk, and only B7 does")
        self.alpha = np.zeros(population)
        self.aim, self.cycle, self.run = aim, int(cycle), int(run)
        self.rest_below, self.still_above = float(rest_below), float(still_above)
        self.noise = noise
        theta = 2.0 * math.pi * np.arange(cfg.n_wall) / cfg.n_wall
        self.theta, self.cos, self.sin = theta, np.cos(theta), np.sin(theta)
        self.re, self.im = np.zeros(population), np.zeros(population)
        self.psi = np.zeros(population)

    def beats(self, sensed: np.ndarray, tick: int) -> np.ndarray:
        phase = tick % self.cycle
        idle_ticks = self.cycle - self.run
        if phase == 0:
            self.re[:], self.im[:] = 0.0, 0.0
        if phase < idle_ticks:
            for i in range(sensed.shape[1]):  # node by node, in a fixed order
                self.re = self.re + sensed[:, i] * self.cos[i]
                self.im = self.im + sensed[:, i] * self.sin[i]
            g = np.zeros_like(sensed)
        else:
            if phase == idle_ticks:
                if self.aim == "read":
                    self.psi = np.arctan2(self.im, self.re)
                else:
                    assert self.noise is not None
                    self.psi = 2.0 * math.pi * self.noise.at(tick) - math.pi
            g = (np.cos(self.theta[None, :] - self.psi[:, None]) > self.HALF_TOLERANCE).astype(np.float64)
        mean = sensed.mean(axis=1, keepdims=True)
        return np.where((mean < self.rest_below) | (mean >= self.still_above), 0.0, g)

    def noise_digests(self) -> Dict[str, str]:
        return {} if self.noise is None else {STREAM_WALK: self.noise.digest}


class AimAndRun(Controller):
    """B8 (stage 4's probe): B5's trigger with B6's aim. Its memory is B5's, an exponential average m of the wall's mean
    sensed light with time constant ``tau``, starting at the first reading. While the light is rising (the mean above
    m) it runs toward the brighter side: the half of the wall facing psi beats fully and the rest not at all, psi the
    direction of an exponential average (time constant ``aim_tau``) of the wall's first Fourier mode, sum_i s_i
    e^(i theta_i). Otherwise it waits; in the dark it rests. alpha = 0."""

    HALF_TOLERANCE = 1e-9

    def __init__(self, cfg: Config, population: int, tau: float, aim_tau: float, rest_below: float) -> None:
        if tau < 1.0 or aim_tau < 1.0:
            raise ValueError("the memories' time constants are at least one tick")
        self.alpha = np.zeros(population)
        self.tau, self.aim_tau, self.rest_below = float(tau), float(aim_tau), float(rest_below)
        theta = 2.0 * math.pi * np.arange(cfg.n_wall) / cfg.n_wall
        self.theta, self.cos, self.sin = theta, np.cos(theta), np.sin(theta)
        self.memory: Optional[np.ndarray] = None
        self.re, self.im = np.zeros(population), np.zeros(population)

    def beats(self, sensed: np.ndarray, tick: int) -> np.ndarray:
        mean = sensed.mean(axis=1, keepdims=True)
        re, im = sensed[:, 0] * self.cos[0], sensed[:, 0] * self.sin[0]
        for i in range(1, sensed.shape[1]):  # node by node, in a fixed order
            re = re + sensed[:, i] * self.cos[i]
            im = im + sensed[:, i] * self.sin[i]
        if self.memory is None:
            self.memory, self.re, self.im = mean.copy(), re, im
        else:
            self.re = self.re + (re - self.re) / self.aim_tau
            self.im = self.im + (im - self.im) / self.aim_tau
        rising = mean > self.memory
        self.memory = self.memory + (mean - self.memory) / self.tau
        psi = np.arctan2(self.im, self.re)
        half = (np.cos(self.theta[None, :] - psi[:, None]) > self.HALF_TOLERANCE).astype(np.float64)
        g = np.where(rising, half, 0.0)
        return np.where(mean < self.rest_below, 0.0, g)


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
    ``{"controller": "reflex", "k": 10}`` (with optional ``rest_below``, ``retreat_above`` and ``retreat_on``),
    ``{"controller": "runwait", "tau": 30, "rest_below": 0.01}`` (B5),
    ``{"controller": "readrun", "aim": "read" or "random", "cycle": 100, "run": 36, "rest_below": 0.01,
    "still_above": 4.5}`` (B6 and B7, stage 3c's §5), ``{"controller": "aimrun", "tau": 30, "aim_tau": 10,
    "rest_below": 0.01}`` (B8, stage 4's probe) or
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
    if kind == "runwait":
        return RunAndWait(cfg, population, spec["tau"], spec["rest_below"])
    if kind == "aimrun":
        return AimAndRun(cfg, population, spec["tau"], spec["aim_tau"], spec["rest_below"])
    if kind == "readrun":
        noise = CellNoise(seed, STREAM_WALK, keys, (), "uniform") if spec["aim"] == "random" else None
        return ReadAndRun(cfg, population, spec["aim"], spec["cycle"], spec["run"], spec["rest_below"], spec["still_above"], noise)
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


def sense(cfg: Config, light: np.ndarray) -> np.ndarray:
    """What the wall's nodes sense before their noise, ``(P, N)`` (docs/prereg/stage3c.md §3.1): the wall's mean light
    plus ``sense_contrast`` (k) times each node's departure from it. The mean is kept, so a cell that reads only the
    level or its change over time senses the same at any k; k = 0 removes the direction across the body, -1 reverses
    it, 10 magnifies it. ``simulate`` never calls it at k = 1, so the light itself is passed on, the same bits."""
    mean = light.mean(axis=1, keepdims=True)
    return mean + cfg.sense_contrast * (light - mean)


def simulate(cfg: Config, starts: Starts, controller_spec: Mapping[str, Any], *, seed: int,
             cell_ids: Optional[Sequence[int]] = None, ticks: Optional[int] = None, record: bool = False,
             observe: Optional[Observer] = None) -> RunResult:
    """Run every start of the batch under one controller spec, each for its own lifetime (``ticks`` overrides it for
    every cell). ``cell_ids`` (default: the baselines' 0) key the noise with the start's number.

    ``observe(t, state)``, when given, is called at the end of every tick t with the batch's state: ``time`` (each
    cell's time at the tick's start), ``light`` (the true light) and ``sensed`` (what the nodes sensed, transformed by
    the senses and with their noise), both at the pose the tick began with, ``beats``, then
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
    sky = Sky(cfg, seed, starts.index.tolist()) if cfg.cloud_shade != 1.0 else None  # stage 4's clouds; off by default
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
        cover = sky.at(t) if sky is not None else None
        if cover is not None:
            light = light * cover[:, None]
        seen = light if cfg.sense_contrast == 1.0 else sense(cfg, light)
        sensed = seen + sensors.at(t) if sensors is not None else seen
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
        if cover is not None:
            at_centre = at_centre * cover
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
