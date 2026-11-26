"""The compiled life in single precision (docs/prereg/fast32.md): the network cell's life in the cave, as
``protocell.fast`` runs it, with most of its arithmetic in single precision, for an Nvidia GPU.

Why: the double-precision engine runs on a GPU and gains nothing there. Consumer GPUs do double precision at a small
fraction of their single-precision rate, and on the owner's laptop 75 whole lives took 36 to 40 s on the GPU and 6 to
15 s on one CPU core (D54).

What is single and what is double:

- **Double:** the cell's place (up to 5,000 R from the pool's centre), its heading (it grows without bound as the cell
  turns), the reserve, the damage, the light's source, and the sums the outcome is made of: about 25 operations a tick.
  The place relative to the source and the heading reduced to one turn are worked out in double and then rounded.
- **Single:** everything else: the light at each node, the senses, the network's step, the cilia's pull, the light
  soaked.
- **The same model, in other words:** the same formulas as the reference, with two rewritten for speed where the
  arithmetic is the same: the falloff takes the squared distance (no square root then a square), and a division by a
  time constant is a multiplication by its reciprocal.

It is specialised to the cell's size (16 wall nodes, 8 core neurons, which every stage uses), so that a compiler can
keep a life's state in registers. The luck is the reference's, rounded to single precision: a start's track is
``protocell.fast``'s.

Its outcomes are not the double engine's: single precision moves a last digit at every step, and a life is chaotic.
The claim, as for the double engine, is agreement with the reference in distribution and in ranking; it is checked
apart (``experiments/fastcheck.py --precision single``). A batch equals its singles, and a life run in pieces is the
life run whole, on any one machine (tested).
"""

from __future__ import annotations

import math
from typing import Any, Dict, Mapping, Optional, Sequence

import numpy as np
from numba import njit

from protocell import evolve
from protocell.cell import Params
from protocell.config import Config
from protocell import fast
from protocell.fast import (K_ENERGY, K_ETA, K_HEADING, K_SHADE, K_X, K_Y, N_OUT, O_ALIVE, O_BEAT, O_CAUSE, O_DAMAGE, O_DEATH_TICK,
                            O_ENERGY, O_FITNESS, O_HEADING, O_LEVEL, O_SOAKED, O_X, O_Y, S_COVER, S_SCALE, S_X, S_Y, Lives, Track)
from protocell.world import node_angles

N, K = 16, 8  # wall nodes and core neurons: the cell every stage uses
M = N + K
# the constants a life reads, in ``consts`` (double; the single-precision ones are rounded once, at a life's start)
(C_VMAX, C_OMEGA, C_CLAMP2, C_CLAMP, C_INV_FALLOFF2, C_C0, C_C1, C_DAMAGE_AT, C_DAMAGE_RATE, C_REPAIR, C_INV_ADAPT, C_SENSE_FLOOR,
 C_LEVEL_FLOOR, C_RELATIVE, N_CONSTS) = range(15)
# a cell's single-precision numbers, in ``cellf``
F_GAIN, F_SIN_ALPHA, N_CELLF = range(3)
ZERO, ONE, CLIP, NF = np.float32(0.0), np.float32(1.0), np.float32(500.0), np.float32(N)
TWO_PI = 2.0 * math.pi


def _life32(l, cell, track, t0, t1, consts, Wt, bias, itau, cellf, cta, sta, ct, st, tracki, trackf, src, scale, cover, sens, mot, out, ys, os_,
            lt, xs, acc, y, o):
    """Ticks ``t0`` to ``t1`` (or to its death, or its lifetime's end) of life ``l``: cell ``cell`` on start ``track``.
    From tick 0 the life begins; from a later tick it goes on from what the call before left in ``out``, ``ys`` and
    ``os_``. Scalar code in the subset both of Numba's targets compile; the last five arguments are scratch. Every
    constant here is single precision unless it is meant to be double: in Numba a bare ``1.0`` is double, and a double
    anywhere turns the arithmetic around it into double."""
    v_max = np.float32(consts[C_VMAX])
    omega_max = np.float32(consts[C_OMEGA])
    clamp2 = consts[C_CLAMP2]
    clamp_radius = consts[C_CLAMP]
    inv_falloff2 = np.float32(consts[C_INV_FALLOFF2])
    c0 = consts[C_C0]
    c1 = consts[C_C1]
    damage_at = np.float32(consts[C_DAMAGE_AT])
    damage_rate = consts[C_DAMAGE_RATE]
    repair = consts[C_REPAIR]
    inv_adapt = np.float32(consts[C_INV_ADAPT])
    sense_floor = np.float32(consts[C_SENSE_FLOOR])
    level_floor = np.float32(consts[C_LEVEL_FLOOR])
    relative = consts[C_RELATIVE] != 0.0
    ticks = tracki[track]
    shade = np.float32(trackf[track, K_SHADE])
    eta = trackf[track, K_ETA]
    shaded = shade != ONE
    gain = cellf[cell, F_GAIN]
    sin_alpha = cellf[cell, F_SIN_ALPHA]
    if t0 == 0:  # the life begins
        px = trackf[track, K_X]
        py = trackf[track, K_Y]
        heading = trackf[track, K_HEADING]
        energy = trackf[track, K_ENERGY]
        damage = 0.0
        level = ZERO
        fitness = 0.0
        soaked_sum = 0.0
        beat_sum = 0.0
        alive = 1.0
        death_tick = -1.0
        cause = 0.0
        for i in range(M):
            y[i] = ZERO
            o[i] = ONE / (ONE + math.exp(-min(max(bias[cell, i], -CLIP), CLIP)))
    else:  # it goes on from where the call before left it
        px = out[l, O_X]
        py = out[l, O_Y]
        heading = out[l, O_HEADING]
        energy = out[l, O_ENERGY]
        damage = out[l, O_DAMAGE]
        level = np.float32(out[l, O_LEVEL])
        fitness = out[l, O_FITNESS]
        soaked_sum = out[l, O_SOAKED]
        beat_sum = out[l, O_BEAT]
        alive = out[l, O_ALIVE]
        death_tick = out[l, O_DEATH_TICK]
        cause = out[l, O_CAUSE]
        for i in range(M):
            y[i] = ys[l, i]
            o[i] = os_[l, i]
    stop = min(t1, ticks)
    if alive == 0.0:  # a cell that has died does not go on
        stop = t0
    for t in range(t0, stop):
        # where the cell is relative to the source, and its heading within one turn: worked out in double, then rounded
        rx = np.float32(px - src[track, t, 0])
        ry = np.float32(py - src[track, t, 1])
        turn = np.float32(heading % TWO_PI)
        ch = math.cos(turn)
        sh = math.sin(turn)
        light_scale = scale[track, t]
        clouds = cover[track, t]
        tn = ONE
        if shaded:
            tn = max(math.sqrt(rx * rx + ry * ry), ONE)
        # the light at each node (world.node_light): the field one radius out along the node's normal, shaded
        for i in range(N):
            nx = ch * ct[i] - sh * st[i]
            ny = sh * ct[i] + ch * st[i]
            dx = rx + nx
            dy = ry + ny
            light = light_scale / (ONE + (dx * dx + dy * dy) * inv_falloff2)
            if shaded:
                cos_beta = (-(nx * rx) - ny * ry) / tn  # the normal against the direction to the source
                light = light * (shade + (ONE - shade) * max(ZERO, cos_beta))
            lt[i] = light * clouds
        # the senses (sim.Network.relative_input) and the network's step (cell.ctrnn_step)
        if relative:
            mean = ZERO
            for i in range(N):
                x = max(lt[i] + sens[track, t, i], ZERO)
                xs[i] = x
                mean += x
            mean = mean / NF
            if t == 0:
                level = mean
            inv_below = ONE / (level + level_floor)
            for i in range(N):
                xs[i] = gain * math.log((xs[i] + sense_floor) * inv_below)
            level = level + (mean - level) * inv_adapt
        else:
            for i in range(N):
                xs[i] = gain * (lt[i] + sens[track, t, i])
        for i in range(M):
            acc[i] = Wt[cell, 0, i] * o[0]
        for j in range(1, M):
            oj = o[j]
            for i in range(M):
                acc[i] += Wt[cell, j, i] * oj
        for i in range(N):
            y[i] += (acc[i] + xs[i] - y[i]) * itau[cell, i]
        for i in range(N, M):
            y[i] += (acc[i] - y[i]) * itau[cell, i]
        for i in range(M):
            o[i] = ONE / (ONE + math.exp(-min(max(y[i] + bias[cell, i], -CLIP), CLIP)))
        # the cilia and the move (motion.cilia_motion, motion.move)
        vx = ZERO
        vy = ZERO
        beats = ZERO
        for i in range(N):
            vx += o[i] * (ch * cta[cell, i] - sh * sta[cell, i])
            vy += o[i] * (sh * cta[cell, i] + ch * sta[cell, i])
            beats += o[i]
        px += v_max * vx
        py += v_max * vy
        r2 = px * px + py * py
        if r2 > clamp2:
            pull = clamp_radius / math.sqrt(r2)
            px *= pull
            py *= pull
        heading += omega_max * beats * sin_alpha + mot[track, t]
        # energy and damage (energy.energy_step, energy.damage_step), then the death check
        soaked = ZERO
        above = ZERO
        for i in range(N):
            soaked += lt[i] / (ONE + lt[i])
            above += max(ZERO, lt[i] - damage_at)
        soaked = soaked / NF
        effort = beats / NF
        new_energy = min(max(energy + eta * soaked - (c0 + c1 * effort), 0.0), 1.0)
        damage = max(0.0, damage + damage_rate * (above / NF) - repair * damage)
        if new_energy <= 0.0:
            energy = 0.0
            alive = 0.0
            death_tick = float(t + 1)
            cause = 1.0
            break
        if damage >= 1.0:
            energy = 0.0
            alive = 0.0
            death_tick = float(t + 1)
            cause = 2.0
            break
        energy = new_energy
        fitness += energy
        soaked_sum += soaked
        beat_sum += effort
    out[l, O_FITNESS] = fitness
    out[l, O_SOAKED] = soaked_sum
    out[l, O_BEAT] = beat_sum
    out[l, O_ALIVE] = alive
    out[l, O_DEATH_TICK] = death_tick
    out[l, O_CAUSE] = cause
    out[l, O_ENERGY] = energy
    out[l, O_DAMAGE] = damage
    out[l, O_X] = px
    out[l, O_Y] = py
    out[l, O_HEADING] = heading
    out[l, O_LEVEL] = level
    for i in range(M):
        ys[l, i] = y[i]
        os_[l, i] = o[i]


_life32_cpu = njit(nogil=True, cache=True)(_life32)


@njit(nogil=True, cache=True)
def _run_cpu32(cells, tracks, t0, t1, consts, Wt, bias, itau, cellf, cta, sta, ct, st, tracki, trackf, src, scale, cover, sens, mot, out, ys, os_):
    lt, xs = np.empty(N, np.float32), np.empty(N, np.float32)
    acc, y, o = np.empty(M, np.float32), np.empty(M, np.float32), np.empty(M, np.float32)
    for l in range(cells.shape[0]):
        _life32_cpu(l, cells[l], tracks[l], t0, t1, consts, Wt, bias, itau, cellf, cta, sta, ct, st, tracki, trackf, src, scale, cover, sens, mot,
                    out, ys, os_, lt, xs, acc, y, o)


# --- what a life is given ------------------------------------------------------------------------------------------------

def check(cfg: Config) -> None:
    """Raise unless this engine runs the world as the reference does, for the cell it is made for."""
    fast.check(cfg)
    if (cfg.n_wall, cfg.n_core) != (N, K):
        raise ValueError(f"the single-precision life is made for {N} wall nodes and {K} core neurons")


def constants(cfg: Config) -> np.ndarray:
    check(cfg)
    c = np.zeros(N_CONSTS)
    c[C_VMAX] = cfg.v_max * (math.pi / cfg.n_wall)
    c[C_OMEGA] = cfg.omega_max * (1.0 / cfg.n_wall)
    c[C_CLAMP2], c[C_CLAMP] = cfg.clamp_radius ** 2, cfg.clamp_radius
    c[C_INV_FALLOFF2] = 1.0 / cfg.cave_falloff ** 2
    c[C_C0], c[C_C1] = cfg.c0, cfg.c1
    c[C_DAMAGE_AT], c[C_DAMAGE_RATE], c[C_REPAIR] = cfg.damage_threshold, cfg.damage_rate, cfg.damage_repair
    c[C_INV_ADAPT], c[C_SENSE_FLOOR], c[C_LEVEL_FLOOR] = 1.0 / cfg.adapt_tau, cfg.sense_floor, cfg.level_floor
    c[C_RELATIVE] = 1.0 if cfg.sensing == "relative" else 0.0
    return c


def cell_arrays(cfg: Config, params: Params) -> Dict[str, np.ndarray]:
    """A population's networks in single precision: the weights transposed for the step, the biases, the reciprocals of
    the time constants, the gain and sin(alpha), and each node's angle with the cilium's turned in."""
    if params.extra is not None:
        raise ValueError("the compiled life has no pathway held at its average")
    theta = node_angles(cfg)
    with_alpha = theta[None, :] + params.alpha[:, None]
    cellf = np.empty((len(params), N_CELLF), dtype=np.float32)
    cellf[:, F_GAIN], cellf[:, F_SIN_ALPHA] = params.gain, np.sin(params.alpha)
    f32 = np.float32
    return {"Wt": np.ascontiguousarray(np.transpose(params.W, (0, 2, 1)), dtype=f32), "bias": np.ascontiguousarray(params.bias, dtype=f32),
            "itau": np.ascontiguousarray(1.0 / params.tau, dtype=f32), "cellf": cellf, "cta": np.cos(with_alpha).astype(f32),
            "sta": np.sin(with_alpha).astype(f32), "ct": np.cos(theta).astype(f32), "st": np.sin(theta).astype(f32)}


def stack_tracks(tracks: Sequence[Track]) -> Dict[str, np.ndarray]:
    """Several of ``protocell.fast``'s tracks as this engine's arrays, padded to the longest lifetime: the source in
    double, the rest rounded to single."""
    k, longest = len(tracks), max(tr.ticks for tr in tracks)
    tracki = np.array([tr.ticks for tr in tracks], dtype=np.int64)
    trackf = np.stack([tr.numbers for tr in tracks])
    src = np.zeros((k, longest, 2))
    scale, cover = np.zeros((k, longest), np.float32), np.ones((k, longest), np.float32)
    sens, mot = np.zeros((k, longest, N), np.float32), np.zeros((k, longest), np.float32)
    for i, tr in enumerate(tracks):
        T = tr.ticks
        src[i, :T, 0], src[i, :T, 1] = tr.sched[:, S_X], tr.sched[:, S_Y]
        scale[i, :T], cover[i, :T] = tr.sched[:, S_SCALE], tr.sched[:, S_COVER]
        sens[i, :T], mot[i, :T] = tr.sens, tr.mot
    return {"tracki": tracki, "trackf": trackf, "src": src, "scale": scale, "cover": cover, "sens": sens, "mot": mot}


ARGS = ("Wt", "bias", "itau", "cellf", "cta", "sta", "ct", "st")
TRACK_ARGS = ("tracki", "trackf", "src", "scale", "cover", "sens", "mot")


def run_lives32(cfg: Config, params: Params, tracks: Sequence[Track], cells: Sequence[int], on: Sequence[int], *, device: str = "cpu",
                pieces: Optional[int] = None) -> Lives:
    """Life i is cell ``cells[i]`` of ``params`` on track ``on[i]``. ``device`` is "cpu" or "cuda". On the CPU each life
    runs in one call, or with ``pieces`` in calls of that many ticks, as the GPU runs it: the same life either way."""
    check(cfg)
    arrays = cell_arrays(cfg, params)
    stacked = stack_tracks(tracks)
    cells_, on_ = np.asarray(list(cells), dtype=np.int64), np.asarray(list(on), dtype=np.int64)
    if cells_.shape != on_.shape or (len(cells_) and (cells_.min() < 0 or on_.min() < 0 or cells_.max() >= len(params) or on_.max() >= len(tracks))):
        raise ValueError("each life names a cell and a track")
    consts = constants(cfg)
    if device == "cpu":
        out = np.zeros((len(cells_), N_OUT))
        ys, os_ = np.zeros((len(cells_), M), np.float32), np.zeros((len(cells_), M), np.float32)
        longest = int(stacked["tracki"].max()) if len(tracks) else 0
        step = longest if pieces is None else int(pieces)
        if step < 1 and longest:
            raise ValueError("a piece is at least one tick")
        for t0 in range(0, longest, max(step, 1)):
            _run_cpu32(cells_, on_, t0, t0 + step, consts, *(arrays[a] for a in ARGS), *(stacked[a] for a in TRACK_ARGS), out, ys, os_)
    elif device == "cuda":
        from protocell import fast32_cuda  # imported only here: the CPU needs none of it

        out = fast32_cuda.run(cells_, on_, consts, arrays, stacked)
    else:
        raise ValueError(f"device is 'cpu' or 'cuda', not {device!r}")
    return fast._outcome(out, stacked["tracki"][on_])  # noqa: SLF001 - the same outcome as the double engine's


# --- the searches' jobs, on this engine ----------------------------------------------------------------------------------

def train_job(job: Mapping[str, Any]) -> Dict[str, np.ndarray]:
    """``protocell.evolve.train_job``, in single precision."""
    return fast._train_result(fast.run_specs(fast._train_specs(job), precision="single"))  # noqa: SLF001


def validation_job(job: Mapping[str, Any]) -> Dict[str, float]:
    """``protocell.evolve.validation_job``, in single precision."""
    return fast._validation_result(fast.run_specs(fast._validation_specs(job), precision="single"))  # noqa: SLF001


JOBS = {evolve.train_job: train_job, evolve.validation_job: validation_job}
