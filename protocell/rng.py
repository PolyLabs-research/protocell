"""Named random streams (docs/determinism.md): each source of randomness draws from its own stream, derived from the
run's seed and the stream's name, so switching one source off or adding a new one never shifts another's draws.

Streams in use (docs/prereg/stage0.md §3): ``sensors`` (sensor noise), ``motion`` (rotational noise, random beating),
``starts`` (layouts and starting positions), ``genomes`` (random genomes).
"""

from __future__ import annotations

import zlib

import numpy as np


def stream(seed: int, name: str) -> np.random.Generator:
    """The generator for stream ``name`` of run ``seed``: PCG64 over a SeedSequence keyed by the seed and a stable hash
    of the name (CRC-32, the same on every platform and Python version, unlike ``hash``)."""
    if seed < 0:
        raise ValueError("a seed must be non-negative")
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence(entropy=seed, spawn_key=(zlib.crc32(name.encode("utf-8")),))))
