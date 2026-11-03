"""The world: stage 0's circular dish with the spot and the lamp (docs/prereg/stage0.md §1–§2), and the cave pool
with its mouth, its day and its sweep (docs/prereg/cave.md §2–§3, §6); the cell's wall nodes' places in the light;
the sampling of starts.

Everything is vectorised over a population: positions are ``(P, 2)`` arrays, headings ``(P,)``, a wall node's light
``(P, N)``. Arithmetic is written out by component (no reductions over tiny axes), so that a cell's numbers are the
same bits alone or in a batch (docs/determinism.md rule 3). The cave's light depends on each cell's own time, its
phase plus the tick, ``(P,)``; the spot's and the lamp's do not.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import numpy as np

from protocell.config import Config
from protocell.rng import stream

KINDS = ("spot", "lamp", "cave")
PATHS = ("mouth", "circle")
STREAM_STARTS = "starts"
STREAM_SKY = "sky"
_MAX_REJECTIONS = 100_000


@dataclass(frozen=True)
class Starts:
    """A batch of starts: each row a layout (the spot's centre, the lamp's position, or the cave's mouth due south), a
    position, a heading, the start's number (1-based) for the noise keys and the tables, and its phase (ticks after
    sunrise; 0 for the spot and the lamp)."""

    kind: str
    source: np.ndarray  # (P, 2)
    pos: np.ndarray  # (P, 2)
    heading: np.ndarray  # (P,)
    index: np.ndarray  # (P,) int, 1-based
    phase: Optional[np.ndarray] = None  # (P,) int

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown light kind {self.kind!r}")
        if self.phase is None:
            object.__setattr__(self, "phase", np.zeros(self.heading.shape[0], dtype=np.int64))
        if not (self.source.shape == self.pos.shape == (len(self.heading), 2) and self.index.shape == self.heading.shape == self.phase.shape):
            raise ValueError("starts' arrays disagree in shape")

    def __len__(self) -> int:
        return int(self.heading.shape[0])

    def take(self, which: Sequence[int]) -> "Starts":
        """The starts at these row positions (0-based), as their own batch."""
        idx = np.asarray(list(which), dtype=np.intp)
        return Starts(self.kind, self.source[idx].copy(), self.pos[idx].copy(), self.heading[idx].copy(), self.index[idx].copy(),
                      self.phase[idx].copy())

    def numbered(self, numbers: Sequence[int]) -> "Starts":
        """The starts with these numbers (1-based), in the order given."""
        lookup = {int(n): i for i, n in enumerate(self.index.tolist())}
        return self.take([lookup[int(n)] for n in numbers])

    def renumbered(self, index: Sequence[int]) -> "Starts":
        """The same starts under other numbers (the numbers key the noise: stage 1 numbers its training starts
        uniquely within a run)."""
        idx = np.asarray(list(index), dtype=np.int64)
        if idx.shape != self.index.shape:
            raise ValueError("one number per start")
        return Starts(self.kind, self.source.copy(), self.pos.copy(), self.heading.copy(), idx, self.phase.copy())

    def with_pos(self, pos: np.ndarray) -> "Starts":
        return Starts(self.kind, self.source.copy(), np.array(pos, dtype=np.float64), self.heading.copy(), self.index.copy(),
                      self.phase.copy())


def _uniform_disc(rng: np.random.Generator, radius: float) -> np.ndarray:
    """A point uniform over the disc of this radius: r = radius sqrt(u), angle 2 pi u' (two draws, in that order)."""
    r = radius * math.sqrt(rng.random())
    a = 2.0 * math.pi * rng.random()
    return np.array([r * math.cos(a), r * math.sin(a)], dtype=np.float64)


def sample_starts(cfg: Config, kind: str, n: int, seed: int, *, stream_name: str = STREAM_STARTS, key: Sequence[int] = ()) -> Starts:
    """Starts 1..n of this light kind from stream ``starts``. Spot and lamp (stage0.md §2, §11 C3): for each start,
    in this order, the layout (spot: its centre uniform within ``spot_centre_within`` of the dish's centre; lamp: its
    angle uniform, the lamp on the dish's edge), the heading (uniform), then positions uniform over the disc of
    radius ``clamp_radius`` until one is at least ``spot_start_min`` from the spot's centre or ``lamp_start_min``
    from the lamp. Cave (cave.md §6): the phase (an integer tick uniform over the day), the heading, the position
    uniform over the disc; the mouth is due south for every start. Start k is the k-th drawn, so starts 1..m are the
    same for every n >= m. ``stream_name`` and ``key`` choose another stream (stage 1 draws its training starts from
    stream ``train`` keyed by the run and the generation); by default the starts are stage 0's and the cave's."""
    if kind not in KINDS:
        raise ValueError(f"unknown light kind {kind!r}")
    rng = stream(seed, stream_name, key)
    source, pos, heading = np.empty((n, 2)), np.empty((n, 2)), np.empty(n)
    phase = np.zeros(n, dtype=np.int64)
    for s in range(n):
        if kind == "cave":
            phase[s] = int(rng.integers(0, cfg.day_ticks))
            source[s] = (0.0, -cfg.dish_radius)
            heading[s] = rng.uniform(-math.pi, math.pi)
            pos[s] = _uniform_disc(rng, cfg.clamp_radius)
            continue
        if kind == "spot":
            source[s] = _uniform_disc(rng, cfg.spot_centre_within)
            at_least = cfg.spot_start_min
        else:
            a = rng.uniform(-math.pi, math.pi)
            source[s] = (cfg.dish_radius * math.cos(a), cfg.dish_radius * math.sin(a))
            at_least = cfg.lamp_start_min
        heading[s] = rng.uniform(-math.pi, math.pi)
        for _ in range(_MAX_REJECTIONS):
            p = _uniform_disc(rng, cfg.clamp_radius)
            if math.hypot(p[0] - source[s, 0], p[1] - source[s, 1]) >= at_least:
                pos[s] = p
                break
        else:  # pragma: no cover - the stated geometry always has room
            raise RuntimeError(f"no start found at least {at_least} R from the {kind}")
    if kind == "cave" and cfg.cave_path != "mouth":  # the light's source where it is at each start's first tick (no draws)
        source = mouth_position(cfg, phase)
    return Starts(kind, source, pos, heading, np.arange(1, n + 1), phase)


def lifetimes(cfg: Config, starts: Starts) -> np.ndarray:
    """Each start's lifetime in ticks: the preregistered lifetime, or for the cave to the second sunrise after the
    start (cave.md §6): two days less the phase."""
    if starts.kind == "cave":
        return 2 * cfg.day_ticks - starts.phase
    return np.full(len(starts), cfg.lifetime, dtype=np.int64)


# --- the cave's day ----------------------------------------------------------------------------------------------------

def daylight(cfg: Config, time: np.ndarray) -> np.ndarray:
    """A half sine from sunrise to sunset, zero at night (cave.md §3); 1 at every hour without the cycle."""
    t = np.asarray(time, dtype=np.float64)
    if not cfg.cave_cycle:
        return np.ones_like(t)
    half = cfg.day_ticks / 2.0
    phase = t % cfg.day_ticks
    return np.where(phase < half, np.sin(math.pi * phase / half), 0.0)


def mouth_angle(cfg: Config, time: np.ndarray) -> np.ndarray:
    """Where on the edge the light comes from (x east, y north): due south, or with the sweep from ``cave_sweep_deg``
    east of south at sunrise to as far west of south at sunset, linearly in time."""
    t = np.asarray(time, dtype=np.float64)
    if not (cfg.cave_sweep and cfg.cave_cycle):
        return np.full_like(t, -math.pi / 2)
    half = cfg.day_ticks / 2.0
    frac = np.clip((t % cfg.day_ticks) / half, 0.0, 1.0)
    return -math.pi / 2 + math.radians(cfg.cave_sweep_deg) * (1.0 - 2.0 * frac)


def mouth_position(cfg: Config, time: np.ndarray) -> np.ndarray:
    """The light's source at each cell's time, ``(P, 2)``: the mouth on the pool's edge (``cave_path`` "mouth"), or
    the spot circling the pool's centre (``cave_path`` "circle"; stage 4's probe), at angle 2 pi t / path_period from
    east, anticlockwise."""
    if cfg.cave_path == "circle":
        t = np.asarray(time, dtype=np.float64)
        a = 2.0 * math.pi * (t % cfg.path_period) / cfg.path_period
        return np.stack([cfg.path_radius * np.cos(a), cfg.path_radius * np.sin(a)], axis=-1)
    if cfg.cave_path != "mouth":
        raise ValueError(f"unknown cave_path {cfg.cave_path!r}; one of {PATHS}")
    a = mouth_angle(cfg, time)
    return np.stack([cfg.dish_radius * np.cos(a), cfg.dish_radius * np.sin(a)], axis=-1)


class Sky:
    """The clouds over each start of a batch (stage 4's probe): spells of sun (factor 1) and shade (factor
    ``cloud_shade``), each spell's length in ticks exponential with its mean (``cloud_sun_mean``, ``cloud_shade_mean``)
    and at least one tick; the first spell's kind drawn from the two kinds' shares of the time. Each start draws from
    stream ``sky`` keyed by its number alone, so every cell on a start, under any controller, has the same sky.
    ``at(t)`` is the factor at tick t of each start's life, ``(P,)``; ticks are asked for in order."""

    def __init__(self, cfg: Config, seed: int, numbers: Sequence[int]) -> None:
        if not 0.0 <= cfg.cloud_shade < 1.0:
            raise ValueError("a sky with clouds has a shade factor in [0, 1)")
        self.shade = float(cfg.cloud_shade)
        self.means = (float(cfg.cloud_shade_mean), float(cfg.cloud_sun_mean))  # by kind: 0 shade, 1 sun
        self.generators = [stream(seed, STREAM_SKY, (int(k),)) for k in numbers]
        share_sun = self.means[1] / (self.means[0] + self.means[1])
        self.sun = np.array([g.random() < share_sun for g in self.generators])
        self.ends = np.array([self._spell(g, bool(s)) for g, s in zip(self.generators, self.sun)], dtype=np.int64)
        self.tick = -1

    def _spell(self, generator: np.random.Generator, sun: bool) -> int:
        return max(1, int(round(generator.exponential(self.means[1 if sun else 0]))))

    def at(self, t: int) -> np.ndarray:
        if t != self.tick + 1:
            raise ValueError("ticks must be asked for in order")
        self.tick = t
        for p in np.flatnonzero(self.ends <= t).tolist():
            self.sun[p] = not self.sun[p]
            self.ends[p] = t + self._spell(self.generators[p], bool(self.sun[p]))
        return np.where(self.sun, 1.0, self.shade)


def cave_falloff(cfg: Config, d: np.ndarray) -> np.ndarray:
    q = d / cfg.cave_falloff
    return 1.0 / (1.0 + q * q)


# --- the fields --------------------------------------------------------------------------------------------------------

def node_angles(cfg: Config) -> np.ndarray:
    """theta_i = 2 pi i / N: node i's angle from the cell's heading; node i + 1 is anticlockwise of node i."""
    return 2.0 * math.pi * np.arange(cfg.n_wall, dtype=np.float64) / cfg.n_wall


def node_normals(cfg: Config, heading: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """The outward normal of each node, (cos, sin) of heading + theta_i: two ``(P, N)`` arrays."""
    angle = heading[:, None] + node_angles(cfg)[None, :]
    return np.cos(angle), np.sin(angle)


def spot_intensity(cfg: Config, x: np.ndarray, y: np.ndarray, cx: np.ndarray, cy: np.ndarray) -> np.ndarray:
    """The spot's field at (x, y) with its centre at (cx, cy); arrays broadcast."""
    dx, dy = x - cx, y - cy
    return cfg.spot_peak * np.exp(-(dx * dx + dy * dy) / (2.0 * cfg.spot_sigma * cfg.spot_sigma)) + cfg.background


def lamp_intensity(cfg: Config, x: np.ndarray, y: np.ndarray, lx: np.ndarray, ly: np.ndarray) -> np.ndarray:
    """The lamp's field at (x, y), the lamp at (lx, ly), before any shading; arrays broadcast."""
    dx, dy = x - lx, y - ly
    d = np.sqrt(dx * dx + dy * dy)
    q = d / cfg.lamp_scale
    return cfg.lamp_peak / (1.0 + q * q) + cfg.background


def cave_intensity(cfg: Config, x: np.ndarray, y: np.ndarray, sx: np.ndarray, sy: np.ndarray, scale: np.ndarray) -> np.ndarray:
    """The cave's field at (x, y) before shading, the source at (sx, sy) and ``scale`` the mouth's light at this
    hour (mouth_light times daylight); arrays broadcast."""
    dx, dy = x - sx, y - sy
    return scale * cave_falloff(cfg, np.sqrt(dx * dx + dy * dy))


def _shaded(cfg: Config, raw: np.ndarray, nx: np.ndarray, ny: np.ndarray, pos: np.ndarray, source: np.ndarray) -> np.ndarray:
    """Self-shading (stage0.md §2, §11 C2): I (shade_floor + (1 - shade_floor) max(0, cos beta)), beta between the
    node's outward normal and the direction from the cell's centre to the source (never shorter than one radius). A
    translucent cell (floor 1) is not shaded at all: it gets the light itself, the same bits the formula gives, with no
    direction needed when its centre sits on a source inside the pool (stage 4's spot)."""
    if cfg.shade_floor == 1.0:
        return raw
    tx, ty = source[:, 0:1] - pos[:, 0:1], source[:, 1:2] - pos[:, 1:2]
    t = np.maximum(np.sqrt(tx * tx + ty * ty), 1.0)
    cos_beta = (nx * tx + ny * ty) / t
    return raw * (cfg.shade_floor + (1.0 - cfg.shade_floor) * np.maximum(0.0, cos_beta))


def centre_light(cfg: Config, kind: str, source: np.ndarray, pos: np.ndarray, time: Optional[np.ndarray] = None) -> np.ndarray:
    """The unshaded intensity at the cell's centre, ``(P,)``: what the soak region, the burn zone and the brightest
    point are measured by. The cave needs each cell's time."""
    if kind == "spot":
        return spot_intensity(cfg, pos[:, 0], pos[:, 1], source[:, 0], source[:, 1])
    if kind == "lamp":
        return lamp_intensity(cfg, pos[:, 0], pos[:, 1], source[:, 0], source[:, 1])
    s = mouth_position(cfg, _time(time, pos))
    scale = cfg.mouth_light * daylight(cfg, _time(time, pos))
    return cave_intensity(cfg, pos[:, 0], pos[:, 1], s[:, 0], s[:, 1], scale)


def node_light(cfg: Config, kind: str, source: np.ndarray, pos: np.ndarray, heading: np.ndarray,
               time: Optional[np.ndarray] = None) -> np.ndarray:
    """The noiseless light each wall node receives, ``(P, N)``: the field at the node's own place on the membrane
    (one radius out along its normal), shaded by the cell itself for the lamp and the cave."""
    nx, ny = node_normals(cfg, heading)
    x = pos[:, 0:1] + nx
    y = pos[:, 1:2] + ny
    if kind == "spot":
        return spot_intensity(cfg, x, y, source[:, 0:1], source[:, 1:2])
    if kind == "lamp":
        return _shaded(cfg, lamp_intensity(cfg, x, y, source[:, 0:1], source[:, 1:2]), nx, ny, pos, source)
    t = _time(time, pos)
    s = mouth_position(cfg, t)
    scale = (cfg.mouth_light * daylight(cfg, t))[:, None]
    return _shaded(cfg, cave_intensity(cfg, x, y, s[:, 0:1], s[:, 1:2], scale), nx, ny, pos, s)


def _time(time: Optional[np.ndarray], pos: np.ndarray) -> np.ndarray:
    if time is None:
        raise ValueError("the cave's light needs each cell's time")
    t = np.asarray(time)
    return np.broadcast_to(t, (pos.shape[0],)) if t.ndim == 0 else t


def soak_radius(cfg: Config, kind: str) -> float:
    """How far from the source the unshaded intensity stays at least ``soak_threshold`` (the cave: at noon)."""
    peak_over = cfg.soak_threshold - cfg.background
    if kind == "spot":
        return math.sqrt(2.0 * cfg.spot_sigma ** 2 * math.log(cfg.spot_peak / peak_over))
    if kind == "lamp":
        return cfg.lamp_scale * math.sqrt(cfg.lamp_peak / peak_over - 1.0)
    return cfg.cave_falloff * math.sqrt(cfg.mouth_light / cfg.soak_threshold - 1.0)


def source_distance(source: np.ndarray, pos: np.ndarray) -> np.ndarray:
    dx, dy = pos[:, 0] - source[:, 0], pos[:, 1] - source[:, 1]
    return np.sqrt(dx * dx + dy * dy)


def soak_distance(cfg: Config, kind: str, source: np.ndarray, pos: np.ndarray) -> np.ndarray:
    """The straight distance from each position to the soak region's edge (0 inside it; the cave's at noon, the
    source due south); the dish is convex, so the straight line stays inside it."""
    return np.maximum(0.0, source_distance(source, pos) - soak_radius(cfg, kind))


def brightest_point(cfg: Config, kind: str, source: np.ndarray) -> np.ndarray:
    """Where a cell's centre gets the most unshaded light: the spot's centre; for the lamp and the cave's mouth at
    noon, ``clamp_radius`` toward it (one radius from the source, the nearest the centre may be)."""
    if kind == "spot":
        return source.copy()
    return source * (cfg.clamp_radius / cfg.dish_radius)


def clamp(cfg: Config, pos: np.ndarray) -> np.ndarray:
    """Keep the cell's centre within ``clamp_radius`` of the dish's centre: a cell beyond it is put on the circle (it
    slides along the edge)."""
    r = np.sqrt(pos[:, 0] * pos[:, 0] + pos[:, 1] * pos[:, 1])
    scale = np.where(r > cfg.clamp_radius, cfg.clamp_radius / np.maximum(r, 1e-300), 1.0)
    return pos * scale[:, None]
