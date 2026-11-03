"""Named random streams (docs/determinism.md): each source of randomness draws from its own stream, derived from the
run's seed and the stream's name, so switching one source off or adding a new one never shifts another's draws.

Streams in use (docs/prereg/stage0.md §3 and §11 C4–C5): ``sensors`` (sensor noise), ``motion`` (rotational noise),
``beats`` (B1's random beating), ``starts`` (layouts and starting positions), ``genomes`` (random genomes). Later
stages add ``train`` (stage 1's training starts), ``bootstrap`` (resampling for intervals), ``walk`` (B7's run
directions, stage 3c), ``tether`` and ``tether_angles`` (the sensor noise and the brighter side's direction of a cell
held in place, stage 3c).

A stream may be keyed, ``stream(seed, "sensors", (cell, start))``: a cell's draws are then its own, the same whether it
runs alone or in a batch (rule 3, stage 0's W6), and the same for every controller that shares its key.
"""

from __future__ import annotations

import zlib
from typing import Sequence

import numpy as np


def stream(seed: int, name: str, key: Sequence[int] = ()) -> np.random.Generator:
    """The generator for stream ``name`` of run ``seed``: PCG64 over a SeedSequence keyed by the seed, a stable hash of
    the name (CRC-32, the same on every platform and Python version, unlike ``hash``) and the optional key's integers."""
    if seed < 0:
        raise ValueError("a seed must be non-negative")
    if any(int(k) < 0 for k in key):
        raise ValueError("a stream key's integers must be non-negative")
    spawn_key = (zlib.crc32(name.encode("utf-8")), *(int(k) for k in key))
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence(entropy=seed, spawn_key=spawn_key)))
