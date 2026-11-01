"""The world (docs/prereg/stage0.md §1–§2): the circular dish, the two light fields, the cell's wall nodes' places in
them, and the sampling of starts.

Everything is vectorised over a population: positions are ``(P, 2)`` arrays, headings ``(P,)``, and a wall node's
light ``(P, N)``. Arithmetic is written out by component (no reductions over tiny axes), so that a cell's numbers are
the same bits alone or in a batch (docs/determinism.md rule 3).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from protocell.config import Config
from protocell.rng import stream

KINDS = ("spot", "lamp")
STREAM_STARTS = "starts"
_MAX_REJECTIONS = 100_000


@dataclass(frozen=True)
class Starts:
    """A batch of starts: each row a layout (the spot's centre or the lamp's position), a position and a heading, with
    the start's number (1-based) for the noise keys and the tables."""

    kind: str
    source: np.ndarray  # (P, 2)
    pos: np.ndarray  # (P, 2)
    heading: np.ndarray  # (P,)
    index: np.ndarray  # (P,) int, 1-based

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"unknown light kind {self.kind!r}")
        if not (self.source.shape == self.pos.shape == (len(self.heading), 2) and self.index.shape == self.heading.shape):
            raise ValueError("starts' arrays disagree in shape")

    def __len__(self) -> int:
        return int(self.heading.shape[0])

    def take(self, which: Sequence[int]) -> "Starts":
        """The starts at these row positions (0-based), as their own batch."""
        idx = np.asarray(list(which), dtype=np.intp)
        return Starts(self.kind, self.source[idx].copy(), self.pos[idx].copy(), self.heading[idx].copy(), self.index[idx].copy())

    def numbered(self, numbers: Sequence[int]) -> "Starts":
        """The starts with these numbers (1-based), in the order given."""
        lookup = {int(n): i for i, n in enumerate(self.index.tolist())}
        return self.take([lookup[int(n)] for n in numbers])

    def with_pos(self, pos: np.ndarray) -> "Starts":
        return Starts(self.kind, self.source.copy(), np.array(pos, dtype=np.float64), self.heading.copy(), self.index.copy())


def _uniform_disc(rng: np.random.Generator, radius: float) -> np.ndarray:
    """A point uniform over the disc of this radius: r = radius sqrt(u), angle 2 pi u' (two draws, in that order)."""
    r = radius * math.sqrt(rng.random())
    a = 2.0 * math.pi * rng.random()
    return np.array([r * math.cos(a), r * math.sin(a)], dtype=np.float64)


def sample_starts(cfg: Config, kind: str, n: int, seed: int) -> Starts:
    """Starts 1..n of this light kind from stream ``starts`` (§2 Starts; §11 C3): for each start, in this order, the
    layout (spot: its centre uniform within ``spot_centre_within`` of the dish's centre; lamp: its angle uniform, the
    lamp on the dish's edge), the heading (uniform), then positions uniform over the disc of radius ``clamp_radius``
    (where the cell's centre may be) until one is at least ``spot_start_min`` from the spot's centre or
    ``lamp_start_min`` from the lamp. Start k is the k-th drawn, so starts 1..m are the same for every n >= m."""
    if kind not in KINDS:
        raise ValueError(f"unknown light kind {kind!r}")
    rng = stream(seed, STREAM_STARTS)
    source, pos, heading = np.empty((n, 2)), np.empty((n, 2)), np.empty(n)
    for s in range(n):
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
    return Starts(kind, source, pos, heading, np.arange(1, n + 1))


def node_angles(cfg: Config) -> np.ndarray:
    """theta_i = 2 pi i / N: node i's angle from the cell's heading; node i + 1 is anticlockwise of node i."""
    return 2.0 * math.pi * np.arange(cfg.n_wall, dtype=np.float64) / cfg.n_wall


def node_normals(cfg: Config, heading: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
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


def centre_light(cfg: Config, kind: str, source: np.ndarray, pos: np.ndarray) -> np.ndarray:
    """The unshaded intensity at the cell's centre, ``(P,)``: what the soak region and the brightest point are
    measured by (§11 C2)."""
    f = spot_intensity if kind == "spot" else lamp_intensity
    return f(cfg, pos[:, 0], pos[:, 1], source[:, 0], source[:, 1])


def node_light(cfg: Config, kind: str, source: np.ndarray, pos: np.ndarray, heading: np.ndarray) -> np.ndarray:
    """The noiseless light each wall node receives, ``(P, N)``: the field at the node's own place on the membrane,
    and for the lamp shaded by the cell itself, I (shade_floor + (1 - shade_floor) max(0, cos beta)), beta the angle
    between the node's outward normal and the direction from the cell's centre to the lamp (§2; §11 C2)."""
    nx, ny = node_normals(cfg, heading)
    x = pos[:, 0:1] + nx  # R = 1: the node sits one radius out along its normal
    y = pos[:, 1:2] + ny
    sx, sy = source[:, 0:1], source[:, 1:2]
    if kind == "spot":
        return spot_intensity(cfg, x, y, sx, sy)
    raw = lamp_intensity(cfg, x, y, sx, sy)
    tx, ty = sx - pos[:, 0:1], sy - pos[:, 1:2]  # from the centre to the lamp (never shorter than 1 R: the lamp is on the edge)
    t = np.sqrt(tx * tx + ty * ty)
    cos_beta = (nx * tx + ny * ty) / t
    return raw * (cfg.shade_floor + (1.0 - cfg.shade_floor) * np.maximum(0.0, cos_beta))


def soak_radius(cfg: Config, kind: str) -> float:
    """How far from the source the unshaded intensity stays at least ``soak_threshold``."""
    peak_over = (cfg.soak_threshold - cfg.background)
    if kind == "spot":
        return math.sqrt(2.0 * cfg.spot_sigma ** 2 * math.log(cfg.spot_peak / peak_over))
    return cfg.lamp_scale * math.sqrt(cfg.lamp_peak / peak_over - 1.0)


def source_distance(source: np.ndarray, pos: np.ndarray) -> np.ndarray:
    dx, dy = pos[:, 0] - source[:, 0], pos[:, 1] - source[:, 1]
    return np.sqrt(dx * dx + dy * dy)


def soak_distance(cfg: Config, kind: str, source: np.ndarray, pos: np.ndarray) -> np.ndarray:
    """The straight distance from each position to the soak region's edge (0 inside it); the dish is convex, so the
    straight line stays inside it (§11 C9)."""
    return np.maximum(0.0, source_distance(source, pos) - soak_radius(cfg, kind))


def brightest_point(cfg: Config, kind: str, source: np.ndarray) -> np.ndarray:
    """Where a cell's centre gets the most unshaded light: the spot's centre; for the lamp, ``clamp_radius`` toward it
    (one radius from the lamp, the nearest the centre may be) (§11 C2)."""
    if kind == "spot":
        return source.copy()
    return source * (cfg.clamp_radius / cfg.dish_radius)


def clamp(cfg: Config, pos: np.ndarray) -> np.ndarray:
    """Keep the cell's centre within ``clamp_radius`` of the dish's centre: a cell beyond it is put on the circle (it
    slides along the edge)."""
    r = np.sqrt(pos[:, 0] * pos[:, 0] + pos[:, 1] * pos[:, 1])
    scale = np.where(r > cfg.clamp_radius, cfg.clamp_radius / np.maximum(r, 1e-300), 1.0)
    return pos * scale[:, None]
