"""The simulation and the baselines (docs/prereg/stage0.md §3–§6), and W6: same seed, same hash; a batch equals its
singles bit for bit; the named streams are independent."""

from __future__ import annotations

import protocell  # noqa: F401
import numpy as np
import pytest

from protocell.cell import MODES, random_genomes, sigmoid
from protocell.config import STAGE0
from protocell.rng import stream
from protocell.sim import NOISE_CHUNK, STREAM_BEATS, STREAM_MOTION, STREAM_SENSORS, CellNoise, Reflex, simulate
from protocell.world import brightest_point, sample_starts, soak_radius

cfg = STAGE0
N = cfg.n_wall
STILL, RANDOM, REFLEX = {"controller": "still"}, {"controller": "random"}, {"controller": "reflex", "k": 10}


def network(mode: str, n: int, seed: int = 0):
    return {"controller": "network", "mode": mode, "genomes": random_genomes(cfg, mode, n, stream(seed, "genomes"))}


def test_b0_never_beats_and_only_its_heading_diffuses() -> None:
    starts = sample_starts(cfg, "spot", 3, seed=0)
    r = simulate(cfg, starts, STILL, seed=0, ticks=20, record=True)
    assert (r.trajectory["beat"] == 0).all() and r.mean_beat.tolist() == [0, 0, 0]
    assert np.array_equal(r.pos, starts.pos) and not np.array_equal(r.heading, starts.heading)
    quiet = simulate(cfg.but(rotation_noise_sd=0.0), starts, STILL, seed=0, ticks=20)
    assert np.array_equal(quiet.heading, starts.heading)


def test_b1_beats_at_random_without_sensing() -> None:
    starts = sample_starts(cfg, "spot", 2, seed=0)
    r = simulate(cfg, starts, RANDOM, seed=0, ticks=30, record=True)
    beat = r.trajectory["beat"]
    assert (beat > 0).all() and (beat < 1).all() and 0.3 < beat.mean() < 0.7 and len(set(beat[0].tolist())) == 30
    assert not np.array_equal(r.pos, starts.pos)
    assert STREAM_BEATS in r.noise_digests


def test_the_reflex_beats_harder_on_the_brighter_side() -> None:
    reflex = Reflex(cfg, 1, k=10.0)
    flat = reflex.beats(np.full((1, N), 0.5), 0)
    assert np.allclose(flat, 0.5)
    sensed = np.full((1, N), 0.5)
    sensed[0, 0] = 0.6
    g = reflex.beats(sensed, 0)
    mean = sensed.mean()
    assert g[0, 0] == pytest.approx(sigmoid(np.array([10 * (0.6 - mean) / (mean + 0.01)]))[0]) and g[0, 0] > 0.5 > g[0, 1]


def test_the_reflex_reaches_the_light_and_a_dead_cell_stops_counting() -> None:
    starts = sample_starts(cfg, "spot", 1, seed=0)
    just_outside = starts.with_pos(starts.source + np.array([[soak_radius(cfg, "spot") + 3.0, 0.0]]))
    r = simulate(cfg, just_outside, REFLEX, seed=0, ticks=100)
    assert 0 < r.reach_tick[0] < 40 and r.survived[0] and r.death_tick[0] == -1
    dark = cfg.but(background=0.0, spot_peak=0.0, rotation_noise_sd=0.0)
    d = simulate(dark, starts, STILL, seed=0, ticks=800, record=True)
    assert not d.survived[0] and 749 <= d.death_tick[0] <= 751 and d.final_energy[0] == 0.0
    t = d.death_tick[0]
    assert (d.trajectory["energy"][0, t:] == 0).all() and d.trajectory["energy"][0, t - 2] > 0
    assert d.fitness[0] == pytest.approx(d.trajectory["energy"][0].mean()) and d.light_soaked[0] == 0.0
    assert np.isnan(d.effort_per_light[0])


def test_b0_at_the_brightest_point_gains() -> None:
    for kind in ("spot", "lamp"):
        starts = sample_starts(cfg, kind, 2, seed=0)
        r = simulate(cfg, starts.with_pos(brightest_point(cfg, kind, starts.source)), STILL, seed=0, ticks=50)
        assert (r.final_energy > cfg.energy_start).all() and r.survived.all() and (r.reach_tick == 1).all()


# --- W6 ---------------------------------------------------------------------------------------------------------------

def test_w6_same_seed_same_trajectory_hash() -> None:
    starts = sample_starts(cfg, "lamp", 3, seed=0)
    for spec in (REFLEX, network("fourier1", 3)):
        a = simulate(cfg, starts, spec, seed=0, cell_ids=[1, 2, 3], ticks=60, record=True)
        b = simulate(cfg, starts, spec, seed=0, cell_ids=[1, 2, 3], ticks=60, record=True)
        assert a.run_hash() == b.run_hash() and [a.cell_hash(i) for i in range(3)] == [b.cell_hash(i) for i in range(3)]
        c = simulate(cfg, starts, spec, seed=1, cell_ids=[1, 2, 3], ticks=60, record=True)
        assert c.run_hash() != a.run_hash()


@pytest.mark.parametrize("kind", ["spot", "lamp"])
@pytest.mark.parametrize("mode", MODES)
def test_w6_a_batch_reproduces_its_single_cell_runs_bit_for_bit(kind: str, mode: str) -> None:
    starts = sample_starts(cfg, kind, 4, seed=0)
    spec = network(mode, 4)
    ids = [11, 12, 13, 14]
    batch = simulate(cfg, starts, spec, seed=0, cell_ids=ids, ticks=NOISE_CHUNK + 20, record=True)
    for i in range(4):
        single = simulate(cfg, starts.take([i]), {**spec, "genomes": spec["genomes"][i:i + 1]}, seed=0, cell_ids=ids[i:i + 1],
                          ticks=NOISE_CHUNK + 20, record=True)
        for name in ("pos", "heading", "energy", "beat"):
            assert np.array_equal(single.trajectory[name][0], batch.trajectory[name][i]), name
        assert single.cell_hash(0) == batch.cell_hash(i)
        assert single.fitness[0] == batch.fitness[i] and single.light_soaked[0] == batch.light_soaked[i]
        assert single.reach_tick[0] == batch.reach_tick[i] and single.survived[0] == batch.survived[i]
    for spec in (STILL, RANDOM, REFLEX):  # the baselines too
        whole = simulate(cfg, starts, spec, seed=0, ticks=30, record=True)
        for i in range(4):
            one = simulate(cfg, starts.take([i]), spec, seed=0, ticks=30, record=True)
            assert one.cell_hash(0) == whole.cell_hash(i)


def test_w6_the_named_streams_are_independent() -> None:
    starts = sample_starts(cfg, "spot", 3, seed=0)
    spec = network("uniform", 3)
    both = simulate(cfg, starts, spec, seed=0, cell_ids=[1, 2, 3], ticks=40)
    no_sensors = simulate(cfg.but(sensor_noise_sd=0.0), starts, spec, seed=0, cell_ids=[1, 2, 3], ticks=40)
    no_motion = simulate(cfg.but(rotation_noise_sd=0.0), starts, spec, seed=0, cell_ids=[1, 2, 3], ticks=40)
    assert set(both.noise_digests) == {STREAM_SENSORS, STREAM_MOTION}
    assert no_sensors.noise_digests == {STREAM_MOTION: both.noise_digests[STREAM_MOTION]}
    assert no_motion.noise_digests == {STREAM_SENSORS: both.noise_digests[STREAM_SENSORS]}
    random_both = simulate(cfg, starts, RANDOM, seed=0, ticks=40)
    random_quiet = simulate(cfg.but(rotation_noise_sd=0.0, sensor_noise_sd=0.0), starts, RANDOM, seed=0, ticks=40)
    assert random_quiet.noise_digests == {STREAM_BEATS: random_both.noise_digests[STREAM_BEATS]}
    still_on = simulate(cfg, starts, STILL, seed=0, ticks=40, record=True)
    still_off = simulate(cfg.but(sensor_noise_sd=0.0), starts, STILL, seed=0, ticks=40, record=True)
    assert still_on.run_hash() == still_off.run_hash()  # B0 ignores its sensors; the motion noise is untouched


def test_a_keyed_stream_is_its_own_and_chunking_does_not_change_it() -> None:
    a = stream(0, "sensors", (1, 2)).standard_normal(4)
    assert not np.array_equal(a, stream(0, "sensors", (2, 1)).standard_normal(4))
    assert not np.array_equal(a, stream(0, "sensors").standard_normal(4))
    assert np.array_equal(a, stream(0, "sensors", (1, 2)).standard_normal(4))
    with pytest.raises(ValueError):
        stream(0, "sensors", (-1,))
    whole = stream(0, "motion", (3, 4)).standard_normal((2 * NOISE_CHUNK, N))
    g = stream(0, "motion", (3, 4))
    chunked = np.concatenate([g.standard_normal((NOISE_CHUNK, N)), g.standard_normal((NOISE_CHUNK, N))])
    assert np.array_equal(whole, chunked)
    noise = CellNoise(0, "motion", [(3, 4)], (N,), "normal", 0.05)
    assert np.array_equal(noise.at(0)[0], whole[0] * 0.05) and np.array_equal(noise.at(NOISE_CHUNK + 1)[0], whole[NOISE_CHUNK + 1] * 0.05)
