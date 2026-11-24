"""A compiled life (docs/prereg/fast.md): the network cell's life in the cave, tick for tick as
``protocell.sim.simulate`` runs it, written as scalar code for one cell and compiled with Numba, for the CPU or for
an Nvidia GPU. It is a second engine for the same model, for the searches, where the time goes. The reference stays
``simulate``: every test and every reported number is still made there.

What is the same, and what is not:

- **The arithmetic is the reference's, operation for operation, in the reference's order.** Sums over the wall's
  nodes are added in numpy's order for a row (pairwise, eight lanes), the network's sum over neurons in
  ``batched_matvec``'s order. With ``strict=True`` and numpy's ``exp``, ``log``, ``sin`` and ``cos`` replaced by the C
  library's, the two engines give the same bits (tested).
- **The luck is the reference's.** A life's sensor and rotation noise, its sky and its light's source are drawn or
  computed beforehand, per start, by the reference's own streams and functions (a start's ``Track``).
- **The library functions are not.** numpy's ``exp``, ``log``, ``sin`` and ``cos`` are its own vectorised ones and
  differ from the C library's in the last bit now and then; the GPU's differ again, and it fuses multiplies and adds.
  By default (``strict=False``) the kernel also takes each node's direction from the heading's sine and cosine by the
  angle-sum rule (two calls a tick, where the reference makes 64). A life is chaotic, so a last bit grows: single
  lives part from the reference's after a while. The two engines agree in distribution, not life by life
  (``experiments/fastcheck.py`` measures it).

Only what a search needs is here: the cave, the network cell (absolute or relative sensing), the senses as they are
(``sense_contrast`` 1). Anything else raises.

A life is independent of every other, so a batch equals its singles on any one machine, whatever the batch.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
from numba import njit

from protocell import evolve
from protocell.cell import Params, decode
from protocell.config import Config
from protocell.energy import start_energy
from protocell.rng import stream
from protocell.sim import STREAM_MOTION, STREAM_SENSORS
from protocell.world import Sky, Starts, daylight, lifetimes, mouth_position, node_angles

# the constants a life reads, in ``consts``
(C_VMAX, C_OMEGA, C_CLAMP, C_FALLOFF, C_C0, C_C1, C_DAMAGE_AT, C_DAMAGE_RATE, C_REPAIR, C_ADAPT, C_SENSE_FLOOR,
 C_LEVEL_FLOOR, C_RELATIVE, C_STRICT, N_CONSTS) = range(15)
# a cell's numbers, in ``cellf``
F_GAIN, F_ALPHA, F_SIN_ALPHA, N_CELLF = range(4)
# a start's numbers, in ``trackf``
K_X, K_Y, K_HEADING, K_ENERGY, K_SHADE, K_ETA, N_TRACKF = range(7)
# a start's tick-by-tick numbers, in ``sched``
S_X, S_Y, S_SCALE, S_COVER, N_SCHED = range(5)
# a life's outcome, in ``out``
(O_FITNESS, O_SOAKED, O_BEAT, O_ALIVE, O_DEATH_TICK, O_CAUSE, O_ENERGY, O_DAMAGE, O_X, O_Y, O_HEADING, N_OUT) = range(12)
MAX_WALL, MAX_NEURONS = 32, 64  # the GPU's per-thread scratch is a fixed size


def _life(l, cell, track, n, m, consts, Wt, bias, tau, cellf, cta, sta, theta, ct, st, tracki, trackf, sched, sens, mot, out,
          nx, ny, lt, xs, tmp, acc, y, o):
    """One life, start to death or to its lifetime's end: life ``l`` is cell ``cell`` on start ``track``. Scalar code
    in the subset both of Numba's targets compile; the eight last arguments are scratch."""

    def add(v, k):
        # numpy's order for a row of k numbers: in turn below eight, else eight lanes added pairwise and the rest in turn
        if k < 8:
            res = 0.0
            for i in range(k):
                res += v[i]
            return res
        r0, r1, r2, r3, r4, r5, r6, r7 = v[0], v[1], v[2], v[3], v[4], v[5], v[6], v[7]
        i = 8
        stop = k - (k % 8)
        while i < stop:
            r0 += v[i]
            r1 += v[i + 1]
            r2 += v[i + 2]
            r3 += v[i + 3]
            r4 += v[i + 4]
            r5 += v[i + 5]
            r6 += v[i + 6]
            r7 += v[i + 7]
            i += 8
        res = ((r0 + r1) + (r2 + r3)) + ((r4 + r5) + (r6 + r7))
        while i < k:
            res += v[i]
            i += 1
        return res

    v_max = consts[C_VMAX]
    omega_max = consts[C_OMEGA]
    clamp_radius = consts[C_CLAMP]
    falloff = consts[C_FALLOFF]
    c0 = consts[C_C0]
    c1 = consts[C_C1]
    damage_at = consts[C_DAMAGE_AT]
    damage_rate = consts[C_DAMAGE_RATE]
    repair = consts[C_REPAIR]
    adapt_tau = consts[C_ADAPT]
    sense_floor = consts[C_SENSE_FLOOR]
    level_floor = consts[C_LEVEL_FLOOR]
    relative = consts[C_RELATIVE] != 0.0
    strict = consts[C_STRICT] != 0.0
    ticks = tracki[track]
    px = trackf[track, K_X]
    py = trackf[track, K_Y]
    heading = trackf[track, K_HEADING]
    energy = trackf[track, K_ENERGY]
    shade = trackf[track, K_SHADE]
    eta = trackf[track, K_ETA]
    shaded = shade != 1.0
    gain = cellf[cell, F_GAIN]
    alpha = cellf[cell, F_ALPHA]
    sin_alpha = cellf[cell, F_SIN_ALPHA]
    nf = float(n)
    damage = 0.0
    level = 0.0
    fitness = 0.0
    soaked_sum = 0.0
    beat_sum = 0.0
    alive = 1.0
    death_tick = -1.0
    cause = 0.0
    ch = 1.0
    sh = 0.0
    tx = 0.0
    ty = 0.0
    tn = 1.0
    for i in range(m):
        y[i] = 0.0
        o[i] = 1.0 / (1.0 + math.exp(-min(max(0.0 + bias[cell, i], -500.0), 500.0)))
    for t in range(ticks):
        source_x = sched[track, t, S_X]
        source_y = sched[track, t, S_Y]
        scale = sched[track, t, S_SCALE]
        cover = sched[track, t, S_COVER]
        # the light at each node (world.node_light), at the pose the tick begins with
        if strict:
            for i in range(n):
                a = heading + theta[i]
                nx[i] = math.cos(a)
                ny[i] = math.sin(a)
        else:
            ch = math.cos(heading)
            sh = math.sin(heading)
            for i in range(n):
                nx[i] = ch * ct[i] - sh * st[i]
                ny[i] = sh * ct[i] + ch * st[i]
        if shaded:
            tx = source_x - px
            ty = source_y - py
            tn = max(math.sqrt(tx * tx + ty * ty), 1.0)
        for i in range(n):
            dx = (px + nx[i]) - source_x
            dy = (py + ny[i]) - source_y
            q = math.sqrt(dx * dx + dy * dy) / falloff
            light = scale * (1.0 / (1.0 + q * q))
            if shaded:
                cos_beta = (nx[i] * tx + ny[i] * ty) / tn
                light = light * (shade + (1.0 - shade) * max(0.0, cos_beta))
            lt[i] = light * cover
        # the senses (sim.Network.relative_input) and the network's step (cell.ctrnn_step)
        if relative:
            for i in range(n):
                xs[i] = max(lt[i] + sens[track, t, i], 0.0)
            mean = add(xs, n) / nf
            if t == 0:
                level = mean
            below = level + level_floor
            for i in range(n):
                xs[i] = gain * math.log((xs[i] + sense_floor) / below)
            level = level + (mean - level) / adapt_tau
        else:
            for i in range(n):
                xs[i] = gain * (lt[i] + sens[track, t, i])
        for i in range(m):
            acc[i] = Wt[cell, 0, i] * o[0]
        for j in range(1, m):
            oj = o[j]
            for i in range(m):
                acc[i] = acc[i] + Wt[cell, j, i] * oj
        for i in range(n):
            y[i] = y[i] + (-y[i] + acc[i] + xs[i]) / tau[cell, i]
        for i in range(n, m):
            y[i] = y[i] + (-y[i] + acc[i] + 0.0) / tau[cell, i]
        for i in range(m):
            o[i] = 1.0 / (1.0 + math.exp(-min(max(y[i] + bias[cell, i], -500.0), 500.0)))
        # the cilia and the move (motion.cilia_motion, motion.move)
        if strict:
            for i in range(n):
                tmp[i] = o[i] * math.cos(heading + theta[i] + alpha)
            vx = v_max * add(tmp, n)
            for i in range(n):
                tmp[i] = o[i] * math.sin(heading + theta[i] + alpha)
            vy = v_max * add(tmp, n)
        else:
            for i in range(n):
                tmp[i] = o[i] * (ch * cta[cell, i] - sh * sta[cell, i])
            vx = v_max * add(tmp, n)
            for i in range(n):
                tmp[i] = o[i] * (sh * cta[cell, i] + ch * sta[cell, i])
            vy = v_max * add(tmp, n)
        beats = add(o, n)
        omega = omega_max * beats * sin_alpha
        px = px + vx
        py = py + vy
        r = math.sqrt(px * px + py * py)
        if r > clamp_radius:
            pull = clamp_radius / max(r, 1e-300)
            px = px * pull
            py = py * pull
        heading = (heading + omega) + mot[track, t]
        # energy and damage (energy.energy_step, energy.damage_step), then the death check
        for i in range(n):
            tmp[i] = lt[i] / (1.0 + lt[i])
        soaked = add(tmp, n) / nf
        effort = beats / nf
        new_energy = min(max(energy + eta * soaked - (c0 + c1 * effort), 0.0), 1.0)
        for i in range(n):
            tmp[i] = max(0.0, lt[i] - damage_at)
        above = add(tmp, n) / nf
        damage = max(0.0, damage + damage_rate * above - repair * damage)
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


_life_cpu = njit(nogil=True, cache=True)(_life)


@njit(nogil=True, cache=True)
def _run_cpu(cells, tracks, n, m, consts, Wt, bias, tau, cellf, cta, sta, theta, ct, st, tracki, trackf, sched, sens, mot, out):
    nx, ny, lt, xs, tmp = np.empty(n), np.empty(n), np.empty(n), np.empty(n), np.empty(n)
    acc, y, o = np.empty(m), np.empty(m), np.empty(m)
    for l in range(cells.shape[0]):
        _life_cpu(l, cells[l], tracks[l], n, m, consts, Wt, bias, tau, cellf, cta, sta, theta, ct, st, tracki, trackf, sched, sens, mot,
                  out, nx, ny, lt, xs, tmp, acc, y, o)


# --- what a life is given -----------------------------------------------------------------------------------------------

def check(cfg: Config, starts: Optional[Starts] = None) -> None:
    """Raise unless this engine runs the world as the reference does."""
    if starts is not None and starts.kind != "cave":
        raise ValueError(f"the compiled life runs in the cave, not the {starts.kind}")
    if cfg.sense_contrast != 1.0:
        raise ValueError("the compiled life senses the light itself (sense_contrast 1)")
    if cfg.sensing not in ("absolute", "relative"):
        raise ValueError(f"sensing is 'absolute' or 'relative', not {cfg.sensing!r}")
    if cfg.sensing == "relative" and not (cfg.adapt_tau >= 1.0 and cfg.sense_floor > 0.0 and cfg.level_floor > 0.0):
        raise ValueError("relative sensing needs adapt_tau >= 1 tick and positive sense_floor and level_floor")
    if not (0 < cfg.n_wall <= MAX_WALL and 0 < cfg.n_wall + cfg.n_core <= MAX_NEURONS):
        raise ValueError(f"at most {MAX_WALL} wall nodes and {MAX_NEURONS} neurons")


def constants(cfg: Config, strict: bool = False) -> np.ndarray:
    """The world's and the cell's numbers a life reads, each the product the reference forms before it meets an array."""
    check(cfg)
    c = np.zeros(N_CONSTS)
    c[C_VMAX] = cfg.v_max * (math.pi / cfg.n_wall)
    c[C_OMEGA] = cfg.omega_max * (1.0 / cfg.n_wall)
    c[C_CLAMP], c[C_FALLOFF] = cfg.clamp_radius, cfg.cave_falloff
    c[C_C0], c[C_C1] = cfg.c0, cfg.c1
    c[C_DAMAGE_AT], c[C_DAMAGE_RATE], c[C_REPAIR] = cfg.damage_threshold, cfg.damage_rate, cfg.damage_repair
    c[C_ADAPT], c[C_SENSE_FLOOR], c[C_LEVEL_FLOOR] = cfg.adapt_tau, cfg.sense_floor, cfg.level_floor
    c[C_RELATIVE] = 1.0 if cfg.sensing == "relative" else 0.0
    c[C_STRICT] = 1.0 if strict else 0.0
    return c


def sky_cover(cfg: Config, seed: int, number: int, ticks: int) -> np.ndarray:
    """The clouds' factor at every tick of one start's life: the reference's own ``Sky``, asked spell by spell, so the
    draws are its draws."""
    if cfg.cloud_shade == 1.0:
        return np.ones(ticks)
    sky = Sky(cfg, seed, [int(number)])
    out = np.empty(ticks)
    t = 0
    while t < ticks:
        end = min(int(sky.ends[0]), ticks)
        out[t:end] = 1.0 if sky.sun[0] else sky.shade
        t = end
        if t < ticks:
            sky.tick = t - 1  # the spell ends at tick t: the reference flips it there and draws the next
            sky.at(t)
    return out


@dataclass
class Track:
    """What every cell on one start meets, for the start's whole life: its lifetime, its pose and reserve at the start,
    the world's shading floor and gain, and tick by tick the light's source, the mouth's light at that hour, the
    clouds' factor, and the sensor and rotation noise (already scaled)."""

    ticks: int
    numbers: np.ndarray  # (N_TRACKF,)
    sched: np.ndarray  # (ticks, N_SCHED)
    sens: np.ndarray  # (ticks, n_wall)
    mot: np.ndarray  # (ticks,)


def build_track(cfg: Config, starts: Starts, row: int, seed: int, *, cell_id: int = evolve.NOISE_CELL_ID,
                ticks: Optional[int] = None) -> Track:
    """The track of start ``row`` of ``starts`` under seed ``seed``: the noise from the streams ``simulate`` keys by
    (``cell_id``, the start's number), the sky from stream ``sky`` keyed by the number, the source and the hour by the
    world's own functions. ``ticks`` overrides the lifetime, as it does in ``simulate``."""
    check(cfg, starts)
    one = starts.take([row])
    number, phase = int(one.index[0]), int(one.phase[0])
    T = int(lifetimes(cfg, one)[0]) if ticks is None else int(ticks)
    time = phase + np.arange(T, dtype=np.int64)
    sched = np.empty((T, N_SCHED))
    source = mouth_position(cfg, time)
    sched[:, S_X], sched[:, S_Y] = source[:, 0], source[:, 1]
    sched[:, S_SCALE] = cfg.mouth_light * daylight(cfg, time)
    sched[:, S_COVER] = sky_cover(cfg, seed, number, T)
    key = (int(cell_id), number)
    if cfg.sensor_noise_sd > 0:
        sens = stream(seed, STREAM_SENSORS, key).standard_normal((T, cfg.n_wall))
        if cfg.sensor_noise_sd != 1.0:
            sens = sens * cfg.sensor_noise_sd
    else:
        sens = np.zeros((T, cfg.n_wall))
    if cfg.rotation_noise_sd > 0:
        mot = stream(seed, STREAM_MOTION, key).standard_normal(T)
        if cfg.rotation_noise_sd != 1.0:
            mot = mot * cfg.rotation_noise_sd
    else:
        mot = np.zeros(T)
    numbers = np.empty(N_TRACKF)
    numbers[K_X], numbers[K_Y], numbers[K_HEADING] = one.pos[0, 0], one.pos[0, 1], one.heading[0]
    numbers[K_ENERGY] = start_energy(cfg, one.kind, one.phase)[0]
    numbers[K_SHADE], numbers[K_ETA] = cfg.shade_floor, cfg.eta
    return Track(T, numbers, sched, np.ascontiguousarray(sens), mot)


def stack_tracks(tracks: Sequence[Track]) -> Dict[str, np.ndarray]:
    """Several tracks as the kernel's arrays, each padded to the longest lifetime."""
    k, longest, n = len(tracks), max(tr.ticks for tr in tracks), tracks[0].sens.shape[1]
    tracki = np.array([tr.ticks for tr in tracks], dtype=np.int64)
    trackf = np.stack([tr.numbers for tr in tracks])
    if k == 1:  # the usual case on the CPU: no copy
        return {"tracki": tracki, "trackf": trackf, "sched": tracks[0].sched[None], "sens": tracks[0].sens[None], "mot": tracks[0].mot[None]}
    sched, sens, mot = np.zeros((k, longest, N_SCHED)), np.zeros((k, longest, n)), np.zeros((k, longest))
    for i, tr in enumerate(tracks):
        sched[i, :tr.ticks], sens[i, :tr.ticks], mot[i, :tr.ticks] = tr.sched, tr.sens, tr.mot
    return {"tracki": tracki, "trackf": trackf, "sched": sched, "sens": sens, "mot": mot}


def cell_arrays(cfg: Config, params: Params) -> Dict[str, np.ndarray]:
    """A population's networks as the kernel's arrays. ``sin(alpha)`` and each node's angle are numpy's, as the
    reference's are."""
    if params.extra is not None:
        raise ValueError("the compiled life has no pathway held at its average")
    theta = node_angles(cfg)
    with_alpha = theta[None, :] + params.alpha[:, None]
    cellf = np.empty((len(params), N_CELLF))
    cellf[:, F_GAIN], cellf[:, F_ALPHA], cellf[:, F_SIN_ALPHA] = params.gain, params.alpha, np.sin(params.alpha)
    return {"Wt": np.ascontiguousarray(np.transpose(params.W, (0, 2, 1))), "bias": np.ascontiguousarray(params.bias),
            "tau": np.ascontiguousarray(params.tau), "cellf": cellf, "cta": np.cos(with_alpha), "sta": np.sin(with_alpha),
            "theta": theta, "ct": np.cos(theta), "st": np.sin(theta)}


# --- running lives ------------------------------------------------------------------------------------------------------

@dataclass
class Lives:
    """A batch's outcome, a row per life, as ``protocell.sim.RunResult`` names them."""

    lifetime: np.ndarray
    survived: np.ndarray
    fitness: np.ndarray
    light_soaked: np.ndarray
    mean_beat: np.ndarray
    death_tick: np.ndarray
    death_cause: np.ndarray
    final_energy: np.ndarray
    final_damage: np.ndarray
    pos: np.ndarray
    heading: np.ndarray

    def __len__(self) -> int:
        return int(self.fitness.shape[0])

    def take(self, which: Sequence[int]) -> "Lives":
        idx = np.asarray(list(which), dtype=np.intp)
        return Lives(**{k: getattr(self, k)[idx] for k in self.__dataclass_fields__})


def _blank(n: int) -> Lives:
    return Lives(lifetime=np.zeros(n, dtype=np.int64), survived=np.zeros(n, dtype=bool), fitness=np.zeros(n), light_soaked=np.zeros(n),
                 mean_beat=np.zeros(n), death_tick=np.zeros(n, dtype=np.int64), death_cause=np.zeros(n, dtype=np.int64), final_energy=np.zeros(n),
                 final_damage=np.zeros(n), pos=np.zeros((n, 2)), heading=np.zeros(n))


def _outcome(out: np.ndarray, ends: np.ndarray) -> Lives:
    return Lives(lifetime=ends.copy(), survived=out[:, O_ALIVE] > 0.0, fitness=out[:, O_FITNESS] / ends, light_soaked=out[:, O_SOAKED] / ends,
                 mean_beat=out[:, O_BEAT] / ends, death_tick=out[:, O_DEATH_TICK].astype(np.int64), death_cause=out[:, O_CAUSE].astype(np.int64),
                 final_energy=out[:, O_ENERGY].copy(), final_damage=out[:, O_DAMAGE].copy(), pos=out[:, O_X:O_Y + 1].copy(),
                 heading=out[:, O_HEADING].copy())


def run_lives(cfg: Config, params: Params, tracks: Sequence[Track], cells: Sequence[int], on: Sequence[int], *, strict: bool = False,
              device: str = "cpu") -> Lives:
    """Life i is cell ``cells[i]`` of ``params`` on track ``on[i]``, all in one call. ``device`` is "cpu" or "cuda"."""
    arrays = cell_arrays(cfg, params)
    stacked = stack_tracks(tracks)
    cells_, on_ = np.asarray(list(cells), dtype=np.int64), np.asarray(list(on), dtype=np.int64)
    if cells_.shape != on_.shape or (len(cells_) and (cells_.min() < 0 or on_.min() < 0 or cells_.max() >= len(params) or on_.max() >= len(tracks))):
        raise ValueError("each life names a cell and a track")
    consts = constants(cfg, strict)
    n, m = cfg.n_wall, cfg.n_wall + cfg.n_core
    if device == "cpu":
        out = np.zeros((len(cells_), N_OUT))
        _run_cpu(cells_, on_, n, m, consts, arrays["Wt"], arrays["bias"], arrays["tau"], arrays["cellf"], arrays["cta"], arrays["sta"],
                 arrays["theta"], arrays["ct"], arrays["st"], stacked["tracki"], stacked["trackf"], stacked["sched"], stacked["sens"],
                 stacked["mot"], out)
    elif device == "cuda":
        out = _run_cuda(cells_, on_, n, m, consts, arrays, stacked)
    else:
        raise ValueError(f"device is 'cpu' or 'cuda', not {device!r}")
    return _outcome(out, stacked["tracki"][on_])


@dataclass
class LifeSpec:
    """One life to run: a genome in a world, on one start of a batch, under a seed."""

    cfg: Config
    mode: str
    genome: np.ndarray
    starts: Starts
    row: int
    seed: int


def run_specs(specs: Sequence[LifeSpec], *, device: str = "cpu", max_tracks: Optional[int] = None, strict: bool = False,
              cell_id: int = evolve.NOISE_CELL_ID, ticks: Optional[int] = None) -> Lives:
    """Any lives, returned in the order given. Lives whose worlds share the kernel's constants run together; a start's
    track is built once however many lives share it; at most ``max_tracks`` tracks are held at a time (one on the CPU,
    where the lives run in turn anyway, sixteen on the GPU: a start's noise is about 30 MB)."""
    if max_tracks is None:
        max_tracks = 1 if device == "cpu" else 16
    result = _blank(len(specs))
    groups: Dict[Tuple[Any, ...], List[int]] = {}
    for i, spec in enumerate(specs):
        groups.setdefault((spec.mode, spec.cfg.n_wall, spec.cfg.n_core, *constants(spec.cfg, strict).tolist()), []).append(i)
    for members in groups.values():
        first = specs[members[0]]
        params = decode(first.cfg, first.mode, np.stack([np.asarray(specs[i].genome, dtype=np.float64) for i in members]))
        where: Dict[Tuple[Any, ...], int] = {}
        builders: List[LifeSpec] = []
        on = []
        for i in members:
            s = specs[i]
            key = (s.cfg, s.seed, int(s.starts.index[s.row]), int(s.starts.phase[s.row]), float(s.starts.pos[s.row, 0]), float(s.starts.pos[s.row, 1]),
                   float(s.starts.heading[s.row]))
            if key not in where:
                where[key] = len(builders)
                builders.append(s)
            on.append(where[key])
        on_ = np.asarray(on, dtype=np.int64)
        for lo in range(0, len(builders), max_tracks):
            hi = min(lo + max_tracks, len(builders))
            mine = np.flatnonzero((on_ >= lo) & (on_ < hi))
            tracks = [build_track(b.cfg, b.starts, b.row, b.seed, cell_id=cell_id, ticks=ticks) for b in builders[lo:hi]]
            r = run_lives(first.cfg, params, tracks, mine, on_[mine] - lo, strict=strict, device=device)
            to = np.asarray(members, dtype=np.intp)[mine]
            for k in Lives.__dataclass_fields__:
                getattr(result, k)[to] = getattr(r, k)
    return result


def simulate_network(cfg: Config, starts: Starts, mode: str, genomes: np.ndarray, *, seed: int, cell_id: int = evolve.NOISE_CELL_ID,
                     ticks: Optional[int] = None, strict: bool = False, device: str = "cpu") -> Lives:
    """``simulate`` for the network cell, one genome a start, on the compiled engine. Every cell draws the noise of
    cell ``cell_id`` on its start, as the searches and the tests have it."""
    genomes = np.asarray(genomes, dtype=np.float64)
    if genomes.shape[0] != len(starts):
        raise ValueError(f"{genomes.shape[0]} genomes for {len(starts)} starts")
    return run_specs([LifeSpec(cfg, mode, genomes[i], starts, i, seed) for i in range(len(starts))], device=device, strict=strict,
                     cell_id=cell_id, ticks=ticks)


# --- the searches' jobs (protocell.evolve's, on this engine) -----------------------------------------------------------

def _train_specs(job: Mapping[str, Any]) -> List[LifeSpec]:
    return [LifeSpec(job["cfg"], job["mode"], g, job["starts"], job["start"], job["seed"]) for g in np.asarray(job["genomes"], dtype=np.float64)]


def _validation_specs(job: Mapping[str, Any]) -> List[LifeSpec]:
    return [LifeSpec(job["cfg"], job["mode"], job["genome"], job["starts"], row, job["seed"]) for row in range(len(job["starts"]))]


def _train_result(r: Lives) -> Dict[str, np.ndarray]:
    return {"fitness": r.fitness, "survived": r.survived, "mean_beat": r.mean_beat, "light_soaked": r.light_soaked}


def _validation_result(r: Lives) -> Dict[str, float]:
    return {"fitness": float(r.fitness.mean()), "survival": float(r.survived.mean()), "mean_beat": float(r.mean_beat.mean())}


def train_job(job: Mapping[str, Any]) -> Dict[str, np.ndarray]:
    """``protocell.evolve.train_job``: some genomes on one training start, all on the start's one track."""
    return _train_result(run_specs(_train_specs(job)))


def validation_job(job: Mapping[str, Any]) -> Dict[str, float]:
    """``protocell.evolve.validation_job``: one genome on every validation start."""
    return _validation_result(run_specs(_validation_specs(job)))


JOBS: Dict[Callable[..., Any], Callable[..., Any]] = {evolve.train_job: train_job, evolve.validation_job: validation_job}


class Mapper:
    """A mapper for ``protocell.evolve.run`` and ``protocell.cmaes.run`` that sends the searches' two jobs to this
    engine and passes every other job on unchanged: ``Mapper(pool.map)`` runs them in the pool's processes. The
    searches themselves are untouched."""

    def __init__(self, inner: Callable[[Callable[[Any], Any], Iterable[Any]], Iterable[Any]] = map) -> None:
        self.inner = inner

    def __call__(self, fn: Callable[[Any], Any], jobs: Iterable[Any]) -> Iterable[Any]:
        return self.inner(JOBS.get(fn, fn), jobs)


# --- the GPU ------------------------------------------------------------------------------------------------------------

def cuda_ready() -> Tuple[bool, str]:
    """Whether a GPU can be used; its name, or why not."""
    try:
        from numba import cuda

        if not cuda.is_available():
            return False, "no CUDA device or driver found"
        if not hasattr(cuda, "get_current_device"):
            return True, "Numba's CUDA simulator"
        name = cuda.get_current_device().name
        return True, name.decode() if isinstance(name, bytes) else str(name)
    except Exception as e:  # pragma: no cover - depends on the machine
        return False, f"numba's CUDA target does not start: {e}"


def _run_cuda(cells: np.ndarray, on: np.ndarray, n: int, m: int, consts: np.ndarray, arrays: Mapping[str, np.ndarray],
              stacked: Mapping[str, np.ndarray]) -> np.ndarray:
    from protocell import fast_cuda  # imported only here: the CPU needs none of it

    return fast_cuda.run(cells, on, n, m, consts, arrays, stacked)


class CudaMapper:
    """A mapper that runs the searches' two jobs on the GPU, a whole call's jobs as one batch (a generation's training
    jobs are one launch: every genome on every start at once), and passes every other job to ``inner``.
    ``max_tracks`` bounds the starts held on the device at once."""

    def __init__(self, inner: Callable[[Callable[[Any], Any], Iterable[Any]], Iterable[Any]] = map, max_tracks: int = 16) -> None:
        self.inner, self.max_tracks = inner, int(max_tracks)

    def _run(self, per_job: List[List[LifeSpec]]) -> List[Lives]:
        r = run_specs([s for specs in per_job for s in specs], device="cuda", max_tracks=self.max_tracks)
        bounds = np.cumsum([0] + [len(specs) for specs in per_job])
        return [r.take(range(int(bounds[i]), int(bounds[i + 1]))) for i in range(len(per_job))]

    def __call__(self, fn: Callable[[Any], Any], jobs: Iterable[Any]) -> Iterable[Any]:
        if fn is evolve.train_job:
            return [_train_result(r) for r in self._run([_train_specs(job) for job in jobs])]
        if fn is evolve.validation_job:
            return [_validation_result(r) for r in self._run([_validation_specs(job) for job in jobs])]
        return self.inner(fn, jobs)
