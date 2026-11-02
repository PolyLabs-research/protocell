"""The cell (docs/prereg/stage0.md §3): N wall neurons on a ring and K core neurons as one CTRNN with a topology
mask; the genome that encodes it, in either spoke mode; and the network's step.

Neuron indices: wall nodes 0..N-1 (node i at angle theta_i = 2 pi i / N from the heading), core N..N+K-1. ``W[i, j]``
is the weight to i from j. Node i's clockwise neighbour is i - 1 (the smaller angle), its anticlockwise neighbour
i + 1 (§11 C10).

The genome, in this order (§11 C10):
  core weights (K x K, row-major, to j from l) | core biases (K) | core log tau (K) |
  ring: self weight, from the clockwise neighbour, from the anticlockwise neighbour, bias, log tau, sensory gain g |
  the cilium angle alpha | spokes in (wall -> core) | spokes out (core -> wall)
with the spokes K numbers each way in the ``uniform`` mode (every wall node sends/receives the same weight) and 3K each
way in ``fourier1`` (a_j + b_j cos theta_i + c_j sin theta_i). 103 numbers (uniform) or 135 (fourier1).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np

from protocell.config import Config
from protocell.world import node_angles

MODES = ("uniform", "fourier1")
STREAM_GENOMES = "genomes"
RING_NAMES = ("ring_self", "ring_from_cw", "ring_from_ccw", "ring_bias", "ring_log_tau", "gain")


@dataclass(frozen=True)
class Layout:
    """Where each block of the genome sits."""

    mode: str
    n_wall: int
    n_core: int
    core_w: slice
    core_bias: slice
    core_log_tau: slice
    ring: slice
    alpha: slice
    spokes_in: slice
    spokes_out: slice
    length: int

    @property
    def spoke_terms(self) -> int:
        return 1 if self.mode == "uniform" else 3


def layout(cfg: Config, mode: str) -> Layout:
    if mode not in MODES:
        raise ValueError(f"unknown spoke mode {mode!r}")
    n, k = cfg.n_wall, cfg.n_core
    terms = 1 if mode == "uniform" else 3
    at = 0

    def block(size: int) -> slice:
        nonlocal at
        s = slice(at, at + size)
        at += size
        return s

    return Layout(mode, n, k, core_w=block(k * k), core_bias=block(k), core_log_tau=block(k), ring=block(len(RING_NAMES)),
                  alpha=block(1), spokes_in=block(terms * k), spokes_out=block(terms * k), length=at)


def genome_length(cfg: Config, mode: str) -> int:
    return layout(cfg, mode).length


def genome_ranges(cfg: Config, mode: str) -> Tuple[np.ndarray, np.ndarray]:
    """The lower and upper bound of every gene (§3): weights and biases in ``weight_range`` (the fourier1 coefficients
    each, §11 C7), log tau in ``log_tau_range``, g in ``gain_range``, alpha in ``alpha_range``."""
    lay = layout(cfg, mode)
    lo, hi = np.empty(lay.length), np.empty(lay.length)
    lo[:], hi[:] = cfg.weight_range
    lo[lay.core_log_tau], hi[lay.core_log_tau] = cfg.log_tau_range
    ring_lo = np.array([cfg.weight_range[0]] * 4 + [cfg.log_tau_range[0], cfg.gain_range[0]])
    ring_hi = np.array([cfg.weight_range[1]] * 4 + [cfg.log_tau_range[1], cfg.gain_range[1]])
    lo[lay.ring], hi[lay.ring] = ring_lo, ring_hi
    lo[lay.alpha], hi[lay.alpha] = cfg.alpha_range
    return lo, hi


def random_genomes(cfg: Config, mode: str, n: int, rng: np.random.Generator) -> np.ndarray:
    """``n`` genomes uniform over the ranges, ``(n, G)``. Drawn row by row from one call, so genome g is the g-th
    whatever n: genomes 1..m are the same for every n >= m."""
    lo, hi = genome_ranges(cfg, mode)
    return rng.uniform(lo, hi, size=(n, lo.shape[0]))


@dataclass
class Params:
    """A population's decoded networks: ``W`` (P, M, M) masked to the topology, ``bias`` and ``tau`` (P, M), the
    sensory gain and the cilium angle (P,)."""

    W: np.ndarray
    bias: np.ndarray
    tau: np.ndarray
    gain: np.ndarray
    alpha: np.ndarray
    extra: Optional[np.ndarray] = None  # a constant input to each neuron, (P, M): stage 1b's pathways held at their average

    def __len__(self) -> int:
        return int(self.gain.shape[0])

    def take(self, which) -> "Params":
        idx = np.asarray(list(which), dtype=np.intp)
        return Params(self.W[idx].copy(), self.bias[idx].copy(), self.tau[idx].copy(), self.gain[idx].copy(), self.alpha[idx].copy(),
                      None if self.extra is None else self.extra[idx].copy())


def topology_mask(cfg: Config) -> np.ndarray:
    """Which weights the organism has (``(M, M)`` bool): the ring (each wall neuron: itself and its two neighbours),
    the spokes both ways, and the core's own links (fully recurrent, self links included)."""
    n, k = cfg.n_wall, cfg.n_core
    m = np.zeros((n + k, n + k), dtype=bool)
    for i in range(n):
        m[i, i] = m[i, (i - 1) % n] = m[i, (i + 1) % n] = True
    m[n:, :n] = True
    m[:n, n:] = True
    m[n:, n:] = True
    return m


def _spoke_weights(lay: Layout, block: np.ndarray, theta: np.ndarray) -> np.ndarray:
    """``(P, K, N)``: the weight between core neuron j and wall node i, from the block's K (uniform) or 3K (fourier1)
    numbers per genome."""
    p, k = block.shape[0], lay.n_core
    if lay.mode == "uniform":
        return np.repeat(block[:, :, None], lay.n_wall, axis=2)
    abc = block.reshape(p, k, 3)
    return abc[:, :, 0:1] + abc[:, :, 1:2] * np.cos(theta)[None, None, :] + abc[:, :, 2:3] * np.sin(theta)[None, None, :]


def decode(cfg: Config, mode: str, genomes: np.ndarray) -> Params:
    """Genomes ``(P, G)`` to the networks they encode."""
    lay = layout(cfg, mode)
    genomes = np.asarray(genomes, dtype=np.float64)
    if genomes.ndim != 2 or genomes.shape[1] != lay.length:
        raise ValueError(f"a {mode} genome has {lay.length} numbers; got shape {genomes.shape}")
    p, n, k = genomes.shape[0], lay.n_wall, lay.n_core
    theta = node_angles(cfg)
    W = np.zeros((p, n + k, n + k))
    ring = genomes[:, lay.ring]
    idx = np.arange(n)
    W[:, idx, idx] = ring[:, 0:1]
    W[:, idx, (idx - 1) % n] = ring[:, 1:2]
    W[:, idx, (idx + 1) % n] = ring[:, 2:3]
    W[:, n:, :n] = _spoke_weights(lay, genomes[:, lay.spokes_in], theta)
    W[:, :n, n:] = np.transpose(_spoke_weights(lay, genomes[:, lay.spokes_out], theta), (0, 2, 1))
    W[:, n:, n:] = genomes[:, lay.core_w].reshape(p, k, k)
    bias = np.empty((p, n + k))
    bias[:, :n] = ring[:, 3:4]
    bias[:, n:] = genomes[:, lay.core_bias]
    tau = np.empty((p, n + k))
    tau[:, :n] = np.exp(ring[:, 4:5])
    tau[:, n:] = np.exp(genomes[:, lay.core_log_tau])
    return Params(W, bias, tau, ring[:, 5].copy(), genomes[:, lay.alpha.start].copy())


def encode(cfg: Config, mode: str, params: Params) -> np.ndarray:
    """The inverse of ``decode`` (the fourier1 coefficients recovered by the discrete Fourier sums over the N equally
    spaced nodes, exact up to rounding)."""
    lay = layout(cfg, mode)
    n, k, p = lay.n_wall, lay.n_core, len(params)
    theta = node_angles(cfg)
    g = np.empty((p, lay.length))
    g[:, lay.core_w] = params.W[:, n:, n:].reshape(p, k * k)
    g[:, lay.core_bias] = params.bias[:, n:]
    g[:, lay.core_log_tau] = np.log(params.tau[:, n:])
    g[:, lay.ring] = np.stack([params.W[:, 0, 0], params.W[:, 0, n - 1], params.W[:, 0, 1], params.bias[:, 0],
                               np.log(params.tau[:, 0]), params.gain], axis=1)
    g[:, lay.alpha] = params.alpha[:, None]
    for sl, spokes in ((lay.spokes_in, params.W[:, n:, :n]), (lay.spokes_out, np.transpose(params.W[:, :n, n:], (0, 2, 1)))):
        if lay.mode == "uniform":
            g[:, sl] = spokes[:, :, 0]
        else:
            a = spokes.mean(axis=2)
            b = 2.0 * (spokes * np.cos(theta)[None, None, :]).sum(axis=2) / n
            c = 2.0 * (spokes * np.sin(theta)[None, None, :]).sum(axis=2) / n
            g[:, sl] = np.stack([a, b, c], axis=2).reshape(p, 3 * k)
    return g


def gene_names(cfg: Config, mode: str) -> Dict[str, slice]:
    lay = layout(cfg, mode)
    return {"core_w": lay.core_w, "core_bias": lay.core_bias, "core_log_tau": lay.core_log_tau, "ring": lay.ring,
            "alpha": lay.alpha, "spokes_in": lay.spokes_in, "spokes_out": lay.spokes_out}


REMOVALS = ("blind", "ring_links", "loop", "core", "core_recurrence")  # stage 1's (stage1.md §7)
TIME_REMOVALS = ("wall_fast", "core_fast")  # stage 3b's (stage3b.md §6): memory in slow decay, not loops


def apply_removal(cfg: Config, params: Params, removal: str) -> Params:
    """A copy of the networks with one part removed (docs/prereg/stage1.md §7), without re-evolving:
    ``blind`` the sensory gain g set to 0; ``ring_links`` the weights between ring neighbours, both directions (the
    self weights kept); ``loop`` the two weights between nodes N-1 and 0, so the ring becomes a chain; ``core`` every
    spoke, both directions, so the wall is alone; ``core_recurrence`` every core-to-core weight, self links included;
    ``wall_fast`` the wall's time constant set to 1 tick and ``core_fast`` every core neuron's (stage3b.md §6), so a
    neuron keeps nothing of its past input but what its links feed back."""
    if removal not in REMOVALS + TIME_REMOVALS:
        raise ValueError(f"unknown removal {removal!r}; one of {REMOVALS + TIME_REMOVALS}")
    n = cfg.n_wall
    out = Params(params.W.copy(), params.bias.copy(), params.tau.copy(), params.gain.copy(), params.alpha.copy(),
                 None if params.extra is None else params.extra.copy())
    if removal == "blind":
        out.gain[:] = 0.0
    elif removal == "ring_links":
        idx = np.arange(n)
        out.W[:, idx, (idx - 1) % n] = 0.0
        out.W[:, idx, (idx + 1) % n] = 0.0
    elif removal == "loop":
        out.W[:, 0, n - 1] = 0.0
        out.W[:, n - 1, 0] = 0.0
    elif removal == "core":
        out.W[:, n:, :n] = 0.0
        out.W[:, :n, n:] = 0.0
    elif removal == "core_recurrence":
        out.W[:, n:, n:] = 0.0
    elif removal == "wall_fast":
        out.tau[:, :n] = 1.0
    else:
        out.tau[:, n:] = 1.0
    return out


PATHWAYS = ("core_drive", "core_recurrence", "ring_links")


def pathway_mask(cfg: Config, pathway: str) -> np.ndarray:
    """Which weights carry a pathway (docs/prereg/stage1b.md §1), ``(M, M)`` bool, to row from column:
    ``core_drive`` core -> wall; ``core_recurrence`` core -> core, self links included; ``ring_links`` each wall
    neuron's two neighbours."""
    n, k = cfg.n_wall, cfg.n_core
    m = np.zeros((n + k, n + k), dtype=bool)
    if pathway == "core_drive":
        m[:n, n:] = True
    elif pathway == "core_recurrence":
        m[n:, n:] = True
    elif pathway == "ring_links":
        idx = np.arange(n)
        m[idx, (idx - 1) % n] = True
        m[idx, (idx + 1) % n] = True
    else:
        raise ValueError(f"unknown pathway {pathway!r}; one of {PATHWAYS}")
    return m


def hold_at_average(cfg: Config, params: Params, pathway: str, means: np.ndarray) -> Params:
    """A copy of the networks with one pathway held at its average (stage1b.md §1): its weights set to zero, and each
    neuron given instead the constant ``means`` (``(M,)`` or ``(P, M)``), the pathway's mean input to it in the intact
    network. ``means`` is zero for the neurons the pathway does not feed."""
    mask = pathway_mask(cfg, pathway)
    receives = mask.any(axis=1)
    means = np.broadcast_to(np.asarray(means, dtype=np.float64), params.bias.shape)
    if np.any(means[:, ~receives] != 0.0):
        raise ValueError(f"{pathway} feeds only {np.flatnonzero(receives).tolist()}")
    W = params.W.copy()
    W[:, mask] = 0.0
    extra = means.copy() if params.extra is None else params.extra + means
    return Params(W, params.bias.copy(), params.tau.copy(), params.gain.copy(), params.alpha.copy(), extra)


def sigmoid(x: np.ndarray) -> np.ndarray:
    """The logistic function, its argument clipped to +-500 so the exponent cannot overflow (§11 C12)."""
    return 1.0 / (1.0 + np.exp(-np.clip(x, -500.0, 500.0)))


def batched_matvec(Wt: np.ndarray, v: np.ndarray) -> np.ndarray:
    """``sum_j W[:, :, j] v[:, j]`` for a stack of matrices, given ``Wt = W`` transposed to ``(P, j, i)`` so each
    slice is contiguous. The sum runs over j in a fixed order, so a cell's result is the same bits in any batch."""
    acc = Wt[:, 0, :] * v[:, 0:1]
    for j in range(1, v.shape[1]):
        acc = acc + Wt[:, j, :] * v[:, j:j + 1]
    return acc


def ctrnn_step(y: np.ndarray, output: np.ndarray, Wt: np.ndarray, tau: np.ndarray, sensory: np.ndarray) -> np.ndarray:
    """One tick of y <- y + (1 / tau)(-y + W sigma(y + bias) + S), with ``output = sigma(y + bias)`` for the y given
    and ``S`` the sensory input (nonzero on wall neurons only)."""
    return y + (-y + batched_matvec(Wt, output) + sensory) / tau
