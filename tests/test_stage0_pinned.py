"""Stage 0's recorded trajectory hashes (docs/data/stage0/summary.json, W6, run 2 at 78c4c38) still come out of the
code: the stage 0 path is bit for bit what produced the data, whatever is built beside it.

The claim is the same bits on the same platform (docs/determinism.md), and numpy's vectorised exp, sin and cos
depend on the CPU's instruction set. So the test runs only on the platform that recorded the hashes, and says why it
skips elsewhere (CI's runners, for one).
"""

from __future__ import annotations

import platform

import protocell  # noqa: F401

import numpy as np
import pytest

from protocell.cell import random_genomes
from protocell.config import STAGE0
from protocell.rng import stream
from protocell.sim import simulate
from protocell.world import sample_starts

RECORDED = {"spot": "8297cc6ac46d0b72941ce5d9ae18e88586e70cf4f3474833bfae0735ceba3ee0",
            "lamp": "95f316c711fd28e759690990998b9a8a706546074f01a84e35aa953e4cd4250a"}
SIMD = ("SSE42", "AVX", "F16C", "FMA3", "AVX2", "AVX512F", "AVX512CD", "AVX512_SKX", "AVX512_CLX", "AVX512_CNL", "AVX512_ICL", "AVX512_SPR")
RECORDED_ON = {"machine": "x86_64", "numpy": "2.4.6",
               "simd": ["SSE42", "AVX", "F16C", "FMA3", "AVX2", "AVX512F", "AVX512CD", "AVX512_SKX", "AVX512_CLX", "AVX512_CNL", "AVX512_ICL"]}


def platform_fingerprint() -> dict:
    """The machine, numpy's version and the SIMD extensions numpy dispatches to: what the bits depend on."""
    try:
        from numpy._core._multiarray_umath import __cpu_features__ as features
    except ImportError:  # pragma: no cover - numpy's private module moved
        features = {}
    return {"machine": platform.machine(), "numpy": np.__version__, "simd": [k for k in SIMD if features.get(k)]}


@pytest.mark.skipif(platform_fingerprint() != RECORDED_ON,
                    reason="the recorded hashes are bits of the platform that recorded them (docs/determinism.md)")
def test_stage0_w6_network_hashes_are_reproduced() -> None:
    genomes = random_genomes(STAGE0, "fourier1", 5, stream(0, "genomes"))
    for kind, recorded in RECORDED.items():
        few = sample_starts(STAGE0, kind, 100, 0).numbered(range(51, 56))
        run = simulate(STAGE0, few, {"controller": "network", "mode": "fourier1", "genomes": genomes}, seed=0, cell_ids=[1, 2, 3, 4, 5], record=True)
        assert run.run_hash() == recorded, kind


def test_the_fingerprint_names_the_machine_numpy_and_its_simd() -> None:
    fp = platform_fingerprint()
    assert set(fp) == {"machine", "numpy", "simd"} and fp["numpy"] == np.__version__ and set(fp["simd"]) <= set(SIMD)
