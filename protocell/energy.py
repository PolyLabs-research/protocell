"""Energy and damage (docs/prereg/stage0.md §4): saturating photosynthesis, a resting and a beating cost, death at
E = 0; damage above a threshold, repaired slowly, death at D = 1 (inert in stages 0 and 1: the threshold is above
every field's peak)."""

from __future__ import annotations

from typing import Tuple

import numpy as np

from protocell.config import Config


def photosynthesis(light: np.ndarray) -> np.ndarray:
    """P(I) = I / (1 + I): the saturating rate, half its maximum at I = 1."""
    return light / (1.0 + light)


def energy_step(cfg: Config, energy: np.ndarray, light: np.ndarray, beats: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """One tick for ``(P,)`` reserves from this tick's noiseless light at the nodes ``(P, N)`` (after shading) and
    this tick's beats ``(P, N)``: gain eta (1/N) sum P(I_i), cost c0 + c1 (1/N) sum g_i, the reserve kept in [0, 1].
    Returns the new reserve, the light soaked (1/N) sum P(I_i) and the mean beat (the measures of §5)."""
    soaked = photosynthesis(light).mean(axis=1)
    effort = beats.mean(axis=1)
    new = np.clip(energy + cfg.eta * soaked - (cfg.c0 + cfg.c1 * effort), 0.0, 1.0)
    return new, soaked, effort


def damage_step(cfg: Config, damage: np.ndarray, light: np.ndarray) -> np.ndarray:
    """D <- D + (1/N) sum max(0, I_i - I_d) - r_D D, kept at or above 0."""
    above = np.maximum(0.0, light - cfg.damage_threshold).mean(axis=1)
    return np.maximum(0.0, damage + above - cfg.damage_repair * damage)
