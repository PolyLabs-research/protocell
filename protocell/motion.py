"""The cilia and motion (docs/prereg/stage0.md §3): no momentum. Velocity is the summed pull of the cilia, rotation
their summed torque, and the heading diffuses (stream ``motion``)."""

from __future__ import annotations

import math
from typing import Optional, Tuple

import numpy as np

from protocell.config import Config
from protocell.world import clamp, node_angles


def cilia_motion(cfg: Config, beats: np.ndarray, heading: np.ndarray, alpha: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """From the beats ``g_i`` ``(P, N)``, the heading ``(P,)`` and the cilium angle ``alpha`` ``(P,)``:
    v = v_max (pi / N) sum g_i u_i, u_i the direction from the centre to node i turned by alpha (alpha = 0: a node
    pulls the cell toward its own side), and omega = omega_max (1 / N) sum g_i sin alpha. Returns v ``(P, 2)`` and
    omega ``(P,)``."""
    n = cfg.n_wall
    angle = heading[:, None] + node_angles(cfg)[None, :] + alpha[:, None]
    vx = cfg.v_max * (math.pi / n) * (beats * np.cos(angle)).sum(axis=1)
    vy = cfg.v_max * (math.pi / n) * (beats * np.sin(angle)).sum(axis=1)
    omega = cfg.omega_max * (1.0 / n) * beats.sum(axis=1) * np.sin(alpha)
    return np.stack([vx, vy], axis=1), omega


def move(cfg: Config, pos: np.ndarray, heading: np.ndarray, v: np.ndarray, omega: np.ndarray,
         rotation_noise: Optional[np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
    """One tick: the centre moves by v (a tick is the unit of time), the heading turns by omega plus the rotational
    noise (already scaled, ``(P,)``; None when off), and the centre is kept within the dish."""
    new_pos = clamp(cfg, pos + v)
    new_heading = heading + omega
    if rotation_noise is not None:
        new_heading = new_heading + rotation_noise
    return new_pos, new_heading
