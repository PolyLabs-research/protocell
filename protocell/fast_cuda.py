"""The compiled life on an Nvidia GPU (protocell/fast.py): one thread a life, the same ``_life``.

Its own module, imported only when a GPU is asked for, with ``cuda`` a module-level name so that Numba's CUDA
simulator (``NUMBA_ENABLE_CUDASIM=1``, which runs a kernel as plain Python) can stand in for it in the tests.

**Lives run in short launches.** A launch carries every life forward some ticks and returns; the next goes on from
there (``_life`` keeps a life's state between calls). A whole life in one launch could hold the GPU for seconds, and
Windows resets a GPU that does not answer for about two. The launches are steered toward ``TARGET_SECONDS`` each. How
a life is cut into launches changes nothing in it (tested on the CPU and in the simulator).

What differs from the CPU's engine is the GPU's library (its ``exp``, ``log``, ``sin``, ``cos``) and that its
compiler fuses a multiply and an add into one rounded operation; both move last bits. Double precision throughout.
"""

from __future__ import annotations

import time
from typing import Mapping

import numpy as np
from numba import cuda, float64

from protocell.fast import MAX_NEURONS, MAX_WALL, N_OUT, _life

THREADS = 64  # a block's threads
FIRST_TICKS, LEAST_TICKS, MOST_TICKS = 256, 16, 65_536  # a launch's ticks: the first, and the bounds it is steered within
TARGET_SECONDS = 0.2  # what a launch is steered toward: a tenth of Windows' two seconds
_life_gpu = cuda.jit(device=True)(_life)


@cuda.jit
def kernel(cells, tracks, n, m, t0, t1, consts, Wt, bias, tau, cellf, cta, sta, theta, ct, st, tracki, trackf, sched, sens, mot, out, ys, os_):
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
        _life_gpu(l, cells[l], tracks[l], n, m, t0, t1, consts, Wt, bias, tau, cellf, cta, sta, theta, ct, st, tracki, trackf, sched, sens,
                  mot, out, ys, os_, nx, ny, lt, xs, tmp, acc, y, o)


def next_ticks(ticks: int, seconds: float) -> int:
    """A launch's ticks, from what the last launch of ``ticks`` took: toward ``TARGET_SECONDS``, at most doubling,
    within the bounds."""
    wanted = ticks * TARGET_SECONDS / max(seconds, 1e-6)
    return int(min(MOST_TICKS, max(LEAST_TICKS, min(wanted, 2.0 * ticks))))


def run(cells: np.ndarray, on: np.ndarray, n: int, m: int, consts: np.ndarray, arrays: Mapping[str, np.ndarray],
        stacked: Mapping[str, np.ndarray]) -> np.ndarray:
    """Every life of the call, carried forward launch by launch to the longest lifetime; the outcome back on the host."""
    lives = int(cells.shape[0])
    out = cuda.to_device(np.zeros((lives, N_OUT)))
    ys, os_ = cuda.to_device(np.zeros((lives, m))), cuda.to_device(np.zeros((lives, m)))
    held = [cuda.to_device(np.ascontiguousarray(a)) for a in (
        cells, on, consts, arrays["Wt"], arrays["bias"], arrays["tau"], arrays["cellf"], arrays["cta"], arrays["sta"], arrays["theta"],
        arrays["ct"], arrays["st"], stacked["tracki"], stacked["trackf"], stacked["sched"], stacked["sens"], stacked["mot"])]
    blocks = (lives + THREADS - 1) // THREADS
    longest = int(np.asarray(stacked["tracki"]).max()) if lives else 0
    t0, ticks, first = 0, FIRST_TICKS, True
    while t0 < longest:
        t1 = min(t0 + ticks, longest)
        began = time.perf_counter()
        kernel[blocks, THREADS](held[0], held[1], n, m, t0, t1, *held[2:], out, ys, os_)
        cuda.synchronize()
        if not first:  # the first launch's time has the compiling in it
            ticks = next_ticks(t1 - t0, time.perf_counter() - began)
        t0, first = t1, False
    return out.copy_to_host()
