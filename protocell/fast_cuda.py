"""The compiled life on an Nvidia GPU (protocell/fast.py): one thread a life, the same ``_life``.

Its own module, imported only when a GPU is asked for, with ``cuda`` a module-level name so that Numba's CUDA
simulator (``NUMBA_ENABLE_CUDASIM=1``, which runs a kernel as plain Python) can stand in for it in the tests.

What differs from the CPU's engine is the GPU's library (its ``exp``, ``log``, ``sin``, ``cos``) and that its
compiler fuses a multiply and an add into one rounded operation; both move last bits. Double precision throughout.
"""

from __future__ import annotations

from typing import Mapping

import numpy as np
from numba import cuda, float64

from protocell.fast import MAX_NEURONS, MAX_WALL, N_OUT, _life

THREADS = 64  # a block's threads
_life_gpu = cuda.jit(device=True)(_life)


@cuda.jit
def kernel(cells, tracks, n, m, consts, Wt, bias, tau, cellf, cta, sta, theta, ct, st, tracki, trackf, sched, sens, mot, out):
    l = cuda.grid(1)
    if l < cells.shape[0]:
        nx = cuda.local.array(MAX_WALL, float64)
        ny = cuda.local.array(MAX_WALL, float64)
        lt = cuda.local.array(MAX_WALL, float64)
        xs = cuda.local.array(MAX_WALL, float64)
        tmp = cuda.local.array(MAX_WALL, float64)
        acc = cuda.local.array(MAX_NEURONS, float64)
        y = cuda.local.array(MAX_NEURONS, float64)
        o = cuda.local.array(MAX_NEURONS, float64)
        _life_gpu(l, cells[l], tracks[l], n, m, consts, Wt, bias, tau, cellf, cta, sta, theta, ct, st, tracki, trackf, sched, sens, mot,
                  out, nx, ny, lt, xs, tmp, acc, y, o)


def run(cells: np.ndarray, on: np.ndarray, n: int, m: int, consts: np.ndarray, arrays: Mapping[str, np.ndarray],
        stacked: Mapping[str, np.ndarray]) -> np.ndarray:
    """Every life of the call in one launch; the outcome array back on the host."""
    lives = int(cells.shape[0])
    out = cuda.to_device(np.zeros((lives, N_OUT)))
    held = [cuda.to_device(np.ascontiguousarray(a)) for a in (
        cells, on, consts, arrays["Wt"], arrays["bias"], arrays["tau"], arrays["cellf"], arrays["cta"], arrays["sta"], arrays["theta"],
        arrays["ct"], arrays["st"], stacked["tracki"], stacked["trackf"], stacked["sched"], stacked["sens"], stacked["mot"])]
    kernel[(lives + THREADS - 1) // THREADS, THREADS](held[0], held[1], n, m, *held[2:], out)
    cuda.synchronize()
    return out.copy_to_host()
