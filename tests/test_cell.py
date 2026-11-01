"""The cell (docs/prereg/stage0.md §3): the genome, the topology, the two spoke modes, the CTRNN's step."""

from __future__ import annotations

import math
import warnings

import protocell  # noqa: F401
import numpy as np
import pytest

from protocell.cell import (MODES, batched_matvec, ctrnn_step, decode, encode, genome_length, genome_ranges, layout, random_genomes,
                            sigmoid, topology_mask)
from protocell.config import STAGE0 as cfg
from protocell.rng import stream
from protocell.world import node_angles

N, K, M = cfg.n_wall, cfg.n_core, cfg.n_wall + cfg.n_core


def test_the_genome_has_103_or_135_numbers() -> None:
    assert genome_length(cfg, "uniform") == 103 and genome_length(cfg, "fourier1") == 135
    with pytest.raises(ValueError):
        layout(cfg, "fourier2")


@pytest.mark.parametrize("mode", MODES)
def test_the_ranges_are_as_stated(mode: str) -> None:
    lo, hi = genome_ranges(cfg, mode)
    lay = layout(cfg, mode)
    assert lo.shape == hi.shape == (lay.length,)
    assert (lo[lay.core_w] == -8).all() and (hi[lay.core_w] == 8).all()
    assert (lo[lay.core_bias] == -8).all() and (hi[lay.spokes_in] == 8).all() and (lo[lay.spokes_out] == -8).all()
    assert (lo[lay.core_log_tau] == 0).all() and np.allclose(hi[lay.core_log_tau], math.log(20))
    ring_lo, ring_hi = lo[lay.ring], hi[lay.ring]
    assert ring_lo.tolist() == [-8, -8, -8, -8, 0, 0] and ring_hi.tolist() == pytest.approx([8, 8, 8, 8, math.log(20), 20])
    assert lo[lay.alpha] == pytest.approx(-math.pi) and hi[lay.alpha] == pytest.approx(math.pi)


@pytest.mark.parametrize("mode", MODES)
def test_random_genomes_lie_in_the_ranges_and_form_a_fixed_sequence(mode: str) -> None:
    lo, hi = genome_ranges(cfg, mode)
    g = random_genomes(cfg, mode, 50, stream(0, "genomes"))
    assert g.shape == (50, lo.shape[0]) and (g >= lo).all() and (g <= hi).all()
    assert np.array_equal(random_genomes(cfg, mode, 5, stream(0, "genomes")), g[:5])  # genome g is the g-th drawn
    params = decode(cfg, mode, g)
    assert (params.tau >= 1).all() and (params.tau <= 20 + 1e-9).all()
    assert (params.gain >= 0).all() and (np.abs(params.alpha) <= math.pi).all()


def test_the_mask_is_the_organisms_topology() -> None:
    m = topology_mask(cfg)
    assert m.shape == (M, M)
    for i in range(N):
        assert set(np.flatnonzero(m[i, :N]).tolist()) == {(i - 1) % N, i, (i + 1) % N}
    assert m[:N, N:].all() and m[N:, :N].all() and m[N:, N:].all()
    assert m.sum() == 3 * N + 2 * N * K + K * K


@pytest.mark.parametrize("mode", MODES)
def test_decoded_weights_respect_the_mask_and_the_ring_is_repeated_units(mode: str) -> None:
    g = random_genomes(cfg, mode, 3, stream(2, "genomes"))
    p = decode(cfg, mode, g)
    assert p.W.shape == (3, M, M) and (p.W[:, ~topology_mask(cfg)] == 0).all()
    lay = layout(cfg, mode)
    for c in range(3):
        ring = g[c, lay.ring]
        for i in range(N):
            assert p.W[c, i, i] == ring[0] and p.W[c, i, (i - 1) % N] == ring[1] and p.W[c, i, (i + 1) % N] == ring[2]
            assert p.bias[c, i] == ring[3] and p.tau[c, i] == pytest.approx(math.exp(ring[4]), rel=1e-14)
        assert p.gain[c] == ring[5] and p.alpha[c] == g[c, lay.alpha.start]
        assert np.array_equal(p.W[c, N:, N:].reshape(-1), g[c, lay.core_w])
        assert np.array_equal(p.bias[c, N:], g[c, lay.core_bias]) and np.allclose(p.tau[c, N:], np.exp(g[c, lay.core_log_tau]))


def test_uniform_spokes_show_the_core_only_the_rings_total() -> None:
    one = random_genomes(cfg, "uniform", 1, stream(3, "genomes"))
    p = decode(cfg, "uniform", np.repeat(one, 2, axis=0))  # the same genome twice
    spokes_in, spokes_out = p.W[:, N:, :N], p.W[:, :N, N:]
    assert (spokes_in == spokes_in[:, :, :1]).all()  # every wall node sends core neuron j the same weight
    assert (spokes_out == spokes_out[:, :1, :]).all()  # and receives the same from it
    light = np.zeros((2, N))
    light[0, 3], light[1, 3], light[1, 11] = 1.0, 0.5, 0.5  # the same total, a different direction
    seen = np.einsum("pji,pi->pj", spokes_in, light)
    assert np.allclose(seen[0], seen[1])


def test_fourier1_spokes_vary_with_the_angle_so_the_cell_has_a_front() -> None:
    g = random_genomes(cfg, "fourier1", 2, stream(4, "genomes"))
    p = decode(cfg, "fourier1", g)
    lay = layout(cfg, "fourier1")
    theta = node_angles(cfg)
    abc = g[:, lay.spokes_in].reshape(2, K, 3)
    expected = abc[:, :, 0:1] + abc[:, :, 1:2] * np.cos(theta) + abc[:, :, 2:3] * np.sin(theta)
    assert np.allclose(p.W[:, N:, :N], expected)
    abc_out = g[:, lay.spokes_out].reshape(2, K, 3)
    expected_out = abc_out[:, :, 0:1] + abc_out[:, :, 1:2] * np.cos(theta) + abc_out[:, :, 2:3] * np.sin(theta)
    assert np.allclose(p.W[:, :N, N:], np.transpose(expected_out, (0, 2, 1)))
    assert not np.allclose(p.W[0, N, :N], p.W[0, N, 0])  # not the same weight from every node


@pytest.mark.parametrize("mode", MODES)
def test_encode_inverts_decode(mode: str) -> None:
    g = random_genomes(cfg, mode, 4, stream(5, "genomes"))
    assert np.allclose(encode(cfg, mode, decode(cfg, mode, g)), g, atol=1e-12)
    with pytest.raises(ValueError):
        decode(cfg, mode, g[:, :-1])


def test_the_ctrnn_step_is_beers_equation() -> None:
    # two neurons: y <- y + (1/tau)(-y + W sigma(y + b) + S)
    W = np.array([[[0.5, -1.0], [2.0, 0.0]]])
    bias, tau, S = np.array([[0.1, -0.2]]), np.array([[1.0, 4.0]]), np.array([[3.0, 0.0]])
    y = np.array([[0.3, -0.7]])
    out = sigmoid(y + bias)
    new = ctrnn_step(y, out, np.ascontiguousarray(np.transpose(W, (0, 2, 1))), tau, S)
    expected = y + (-y + (W[0] @ out[0])[None, :] + S) / tau
    assert np.allclose(new, expected)
    assert np.allclose(batched_matvec(np.ascontiguousarray(np.transpose(W, (0, 2, 1))), out), np.einsum("pij,pj->pi", W, out))


def test_the_sigmoid_cannot_overflow() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        s = sigmoid(np.array([-1e9, -40.0, 0.0, 20.0, 1e9]))
    assert 0 <= s[0] < 1e-200 and s[2] == 0.5 and s[4] == 1.0 and 0 < s[1] < 1e-15 and 1 - 1e-8 < s[3] < 1
