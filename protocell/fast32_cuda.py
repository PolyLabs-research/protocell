"""The single-precision life on an Nvidia GPU (protocell/fast32.py): one thread a life, the same ``_life32``, in short
launches steered toward a fifth of a second each, as ``protocell.fast_cuda`` runs the double-precision life.

Its own module, imported only when a GPU is asked for, with ``cuda`` a module-level name so that Numba's CUDA
simulator can stand in for it in the tests. The simulator runs the kernel as plain Python, where ``math.exp`` of a
single-precision number returns a double: there it shows the plumbing, not single-precision arithmetic.
"""

from __future__ import annotations

import time
from typing import Mapping

import numpy as np
from numba import cuda, float32

from protocell.fast import N_OUT
from protocell.fast32 import ARGS, M, N, TRACK_ARGS, _life32
from protocell.fast_cuda import FIRST_TICKS, THREADS, next_ticks

_life32_gpu = cuda.jit(device=True)(_life32)


@cuda.jit
def kernel(cells, tracks, t0, t1, consts, Wt, bias, itau, cellf, cta, sta, ct, st, tracki, trackf, src, scale, cover, sens, mot, out, ys, os_):
    l = cuda.grid(1)
    if l < cells.shape[0]:
        lt = cuda.local.array(N, float32)
        xs = cuda.local.array(N, float32)
        acc = cuda.local.array(M, float32)
        y = cuda.local.array(M, float32)
        o = cuda.local.array(M, float32)
        _life32_gpu(l, cells[l], tracks[l], t0, t1, consts, Wt, bias, itau, cellf, cta, sta, ct, st, tracki, trackf, src, scale, cover, sens, mot,
                    out, ys, os_, lt, xs, acc, y, o)


def run(cells: np.ndarray, on: np.ndarray, consts: np.ndarray, arrays: Mapping[str, np.ndarray], stacked: Mapping[str, np.ndarray]) -> np.ndarray:
    """Every life of the call, carried forward launch by launch to the longest lifetime; the outcome back on the host."""
    lives = int(cells.shape[0])
    out = cuda.to_device(np.zeros((lives, N_OUT)))
    ys, os_ = cuda.to_device(np.zeros((lives, M), np.float32)), cuda.to_device(np.zeros((lives, M), np.float32))
    held = [cuda.to_device(np.ascontiguousarray(a)) for a in (cells, on)]
    rest = [cuda.to_device(np.ascontiguousarray(a)) for a in (consts, *(arrays[k] for k in ARGS), *(stacked[k] for k in TRACK_ARGS))]
    blocks = (lives + THREADS - 1) // THREADS
    longest = int(np.asarray(stacked["tracki"]).max()) if lives else 0
    t0, ticks, first = 0, FIRST_TICKS, True
    while t0 < longest:
        t1 = min(t0 + ticks, longest)
        began = time.perf_counter()
        kernel[blocks, THREADS](held[0], held[1], t0, t1, *rest, out, ys, os_)
        cuda.synchronize()
        if not first:  # the first launch's time has the compiling in it
            ticks = next_ticks(t1 - t0, time.perf_counter() - began)
        t0, first = t1, False
    return out.copy_to_host()
