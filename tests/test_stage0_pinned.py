"""Stage 0's recorded trajectory hashes (docs/data/stage0/summary.json, W6, run 2 at 78c4c38) still come out of the
code: the stage 0 path is bit for bit what produced the data, whatever is built beside it."""

from __future__ import annotations

import protocell  # noqa: F401

from protocell.cell import random_genomes
from protocell.config import STAGE0
from protocell.rng import stream
from protocell.sim import simulate
from protocell.world import sample_starts

RECORDED = {"spot": "8297cc6ac46d0b72941ce5d9ae18e88586e70cf4f3474833bfae0735ceba3ee0",
            "lamp": "95f316c711fd28e759690990998b9a8a706546074f01a84e35aa953e4cd4250a"}


def test_stage0_w6_network_hashes_are_reproduced() -> None:
    genomes = random_genomes(STAGE0, "fourier1", 5, stream(0, "genomes"))
    for kind, recorded in RECORDED.items():
        few = sample_starts(STAGE0, kind, 100, 0).numbered(range(51, 56))
        run = simulate(STAGE0, few, {"controller": "network", "mode": "fourier1", "genomes": genomes}, seed=0, cell_ids=[1, 2, 3, 4, 5], record=True)
        assert run.run_hash() == recorded, kind
