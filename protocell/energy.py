"""Energy and damage (docs/prereg/stage0.md §4; docs/prereg/cave.md §5–§6): saturating photosynthesis, a resting
and a beating cost, death at E = 0; damage above a threshold at a rate, repaired slowly, death at D = 1; and the
cave's reserve at a start, matched to its phase."""

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
    """D <- D + k_D (1/N) sum max(0, I_i - I_d) - r_D D, kept at or above 0 (stage 0's law had k_D = 1)."""
    above = np.maximum(0.0, light - cfg.damage_threshold).mean(axis=1)
    return np.maximum(0.0, damage + cfg.damage_rate * above - cfg.damage_repair * damage)


def start_reserve(cfg: Config, phase: np.ndarray) -> np.ndarray:
    """The cave's reserve at a start (cave.md §6): what a cell that fills at the light ``fill_light`` by day and rests
    by night holds at that phase. From 1 less a night's resting cost at sunrise it rises at that cell's net rate until
    full, holds 1 to sunset, then falls at the resting cost through the night."""
    p = np.asarray(phase, dtype=np.float64)
    half = cfg.day_ticks / 2.0
    at_sunrise = 1.0 - cfg.c0 * half
    rate = cfg.eta * cfg.fill_light / (1.0 + cfg.fill_light) - cfg.c0
    by_day = np.minimum(1.0, at_sunrise + rate * p)
    by_night = 1.0 - cfg.c0 * (p - half)
    return np.where(p < half, by_day, by_night)


def start_energy(cfg: Config, kind: str, phase: np.ndarray) -> np.ndarray:
    """Each cell's reserve at its start: the preregistered constant, or the cave's matched reserve."""
    if kind == "cave":
        return start_reserve(cfg, phase)
    return np.full(phase.shape[0], cfg.energy_start)
