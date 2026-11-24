"""The compiled life (protocell/fast.py): it is the reference's model, its luck is the reference's, a batch equals its
singles, the searches run on it unchanged, and its GPU form compiles."""

import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("numba")

from experiments import stage4b, stage8  # noqa: E402
from protocell import evolve, fast  # noqa: E402
from protocell.cell import apply_removal, decode, random_genomes  # noqa: E402
from protocell.cmaes import CMA, run  # noqa: E402
from protocell.config import CAVE  # noqa: E402
from protocell.rng import stream  # noqa: E402
from protocell.sim import STREAM_MOTION, STREAM_SENSORS, CellNoise, simulate  # noqa: E402
from protocell.world import Sky, daylight, lifetimes, mouth_position, sample_starts  # noqa: E402

MODES = ("fourier1", "uniform")
SAME = ("fitness", "light_soaked", "mean_beat", "survived", "death_tick", "death_cause", "final_energy", "final_damage", "pos", "heading")


def worlds():
    """The four worlds stage 8 trains in (the smoke test's 2,000-tick day), a world on stage 4b's path (part shaded,
    the cave's gain), the cave as stage 1 met it (absolute sensing, shaded, damage live), and two that kill quickly."""
    home = stage8.world("home", quick=True)
    out = {name: stage8.world(name, quick=True) for name in stage8.TRAINED}
    out["path"] = stage4b.training_world(home, 1, 2, 2).but(shade_floor=0.65)
    out["cave"] = CAVE.but(day_ticks=2000, lifetime=4000, cave_sweep=True)
    out["starving"] = home.but(c0=1.0 / 300.0)
    out["burning"] = out["cave"].but(damage_threshold=0.05, damage_rate=0.5)
    return out


def genomes_for(cfg, mode, n, seed=5):
    return random_genomes(cfg, mode, n, stream(seed, "genomes"))


def reference(cfg, starts, mode, genomes, seed, ticks=None):
    return simulate(cfg, starts, {"controller": "network", "mode": mode, "genomes": genomes}, seed=seed, cell_ids=[evolve.NOISE_CELL_ID] * len(starts),
                    ticks=ticks)


@pytest.fixture(scope="module")
def compiled():
    """The kernel compiled before any test replaces numpy's functions (Numba reads numpy's while it compiles)."""
    cfg = stage8.world("home", quick=True)
    fast.simulate_network(cfg, sample_starts(cfg, "cave", 1, 1), "fourier1", genomes_for(cfg, "fourier1", 1), seed=1, ticks=2)


@pytest.fixture
def c_library_maths(compiled, monkeypatch):
    """numpy's exp, log, sin and cos replaced by the C library's, element by element: the functions the compiled life
    calls. Under it the two engines share every operation."""
    def each(f):
        def g(x, *args, **kwargs):
            x = np.asarray(x, dtype=np.float64)
            return np.array([f(float(v)) for v in x.ravel()], dtype=np.float64).reshape(x.shape)
        return g
    for name in ("exp", "log", "sin", "cos"):
        monkeypatch.setattr(np, name, each(getattr(math, name)))


def test_a_track_is_the_references_luck(compiled):
    cfg = stage8.world("flicker", quick=True)
    starts = sample_starts(cfg, "cave", 3, 11)
    row, seed, ticks = 2, 11, 1200
    track = fast.build_track(cfg, starts, row, seed, ticks=ticks)
    key = [(evolve.NOISE_CELL_ID, int(starts.index[row]))]
    sensors = CellNoise(seed, STREAM_SENSORS, key, (cfg.n_wall,), "normal", cfg.sensor_noise_sd)
    motion = CellNoise(seed, STREAM_MOTION, key, (), "normal", cfg.rotation_noise_sd)
    sky = Sky(cfg, seed, [int(starts.index[row])])
    for t in range(ticks):  # across the reference's chunks of 250 draws and many spells of cloud
        assert np.array_equal(track.sens[t], sensors.at(t)[0])
        assert track.mot[t] == motion.at(t)[0]
        assert track.sched[t, fast.S_COVER] == sky.at(t)[0]
    assert set(np.unique(track.sched[:, fast.S_COVER])) == {cfg.cloud_shade, 1.0}
    time = int(starts.phase[row]) + np.arange(ticks)
    assert np.array_equal(track.sched[:, fast.S_X:fast.S_Y + 1], mouth_position(cfg, time))
    assert np.array_equal(track.sched[:, fast.S_SCALE], cfg.mouth_light * daylight(cfg, time))
    assert fast.build_track(cfg, starts, row, seed).ticks == int(lifetimes(cfg, starts)[row])


@pytest.mark.parametrize("mode", MODES)
def test_strict_it_is_the_reference_bit_for_bit(c_library_maths, mode):
    seed, ticks = 7, 500
    died, moved = set(), {}
    for name, cfg in worlds().items():
        starts = sample_starts(cfg, "cave", 4, seed)
        genomes = genomes_for(cfg, mode, len(starts))
        ref = reference(cfg, starts, mode, genomes, seed, ticks)
        got = fast.simulate_network(cfg, starts, mode, genomes, seed=seed, ticks=ticks, strict=True)
        for k in SAME:
            assert np.array_equal(getattr(got, k), getattr(ref, k)), (name, k)
        moved[name] = float(np.abs(ref.pos - starts.pos).max())
        died |= set(ref.death_cause.tolist())
    assert died == {0, 1, 2}  # a life that ran its course, one that starved and one that burnt
    assert sum(d > 1.0 for d in moved.values()) >= len(moved) // 2, moved  # and the cells moved: not a check of still cells


def test_strict_whole_lives_and_removed_parts(c_library_maths):
    cfg = stage8.world("shaded", quick=True)
    seed = 9
    starts = sample_starts(cfg, "cave", 3, seed)
    genomes = genomes_for(cfg, "fourier1", len(starts))
    ref = reference(cfg, starts, "fourier1", genomes, seed)
    got = fast.simulate_network(cfg, starts, "fourier1", genomes, seed=seed, strict=True)
    assert np.array_equal(got.lifetime, lifetimes(cfg, starts)) and len(set(got.lifetime.tolist())) == 3  # each to its own second sunrise
    for k in SAME:
        assert np.array_equal(getattr(got, k), getattr(ref, k)), k
    params = apply_removal(cfg, decode(cfg, "fourier1", genomes), "ring_links")  # the kernel takes any decoded network
    cut = simulate(cfg, starts, {"controller": "network", "mode": "fourier1", "genomes": genomes, "removal": "ring_links"}, seed=seed,
                   cell_ids=[0] * len(starts), ticks=300)
    tracks = [fast.build_track(cfg, starts, i, seed, ticks=300) for i in range(len(starts))]
    lives = fast.run_lives(cfg, params, tracks, range(len(starts)), range(len(starts)), strict=True)
    assert np.array_equal(lives.pos, cut.pos) and np.array_equal(lives.fitness, cut.fitness)


def test_the_default_differs_from_strict_only_in_the_last_bits(compiled):
    cfg = stage8.world("shaded", quick=True)
    starts = sample_starts(cfg, "cave", 4, 3)
    genomes = genomes_for(cfg, "fourier1", len(starts))
    a = fast.simulate_network(cfg, starts, "fourier1", genomes, seed=3, ticks=40, strict=True)
    b = fast.simulate_network(cfg, starts, "fourier1", genomes, seed=3, ticks=40)
    assert float(np.abs(a.pos - b.pos).max()) < 1e-6 and float(np.abs(a.fitness - b.fitness).max()) < 1e-9
    assert float(np.abs(a.pos - starts.pos).max()) > 1.0


def test_a_batch_equals_its_singles_and_the_order_does_not_matter(compiled):
    cfg = stage8.world("spot", quick=True)
    starts = sample_starts(cfg, "cave", 3, 21)
    genomes = genomes_for(cfg, "fourier1", 5)
    specs = [fast.LifeSpec(cfg, "fourier1", genomes[g], starts, row, 21) for g in range(5) for row in range(3)]
    together = fast.run_specs(specs)
    one_call = fast.run_specs(specs, max_tracks=3)  # every start's track held at once, as on the GPU
    order = list(reversed(range(len(specs))))
    backwards = fast.run_specs([specs[i] for i in order])
    for k in SAME:
        assert np.array_equal(getattr(one_call, k), getattr(together, k)), k
        assert np.array_equal(getattr(backwards, k), getattr(together, k)[order]), k
    for i in (0, 7, 14):
        alone = fast.run_specs([specs[i]])
        assert alone.fitness[0] == together.fitness[i] and np.array_equal(alone.pos[0], together.pos[i])
    assert len(set(together.fitness.tolist())) == len(specs)  # the lives differ


def test_a_life_run_in_pieces_is_the_life_run_whole(compiled):
    """What the GPU does (short launches, a life's state carried between them), done on the CPU: whole lives to their
    ends and to their deaths, in pieces of a few sizes, in the default form and the strict one."""
    died = set()
    for name, cfg in worlds().items():
        starts = sample_starts(cfg, "cave", 3, 13)
        params = decode(cfg, "fourier1", genomes_for(cfg, "fourier1", 3))
        tracks = [fast.build_track(cfg, starts, i, 13) for i in range(3)]
        cells, on = [0, 1, 2, 0, 1, 2, 0, 1, 2], [0, 0, 0, 1, 1, 1, 2, 2, 2]
        for strict in (False, True):
            whole = fast.run_lives(cfg, params, tracks, cells, on, strict=strict)
            for pieces in (1000, 251, 7) if name in ("home", "starving", "burning") else (251,):
                parted = fast.run_lives(cfg, params, tracks, cells, on, strict=strict, pieces=pieces)
                for k in SAME:
                    assert np.array_equal(getattr(parted, k), getattr(whole, k)), (name, strict, pieces, k)
        assert len(set(whole.lifetime.tolist())) == 3  # three lifetimes: the pieces end at different places in each
        died |= set(whole.death_cause.tolist())
    assert died == {0, 1, 2}  # lives that ran their course, starved, and burnt: a dead cell stays dead in the pieces after
    with pytest.raises(ValueError, match="piece"):
        fast.run_lives(cfg, params, tracks, cells, on, pieces=0)


def test_the_gpus_launches_are_steered_toward_a_fifth_of_a_second():
    fast_cuda = pytest.importorskip("protocell.fast_cuda")
    assert fast_cuda.TARGET_SECONDS == 0.2 and fast_cuda.LEAST_TICKS <= fast_cuda.FIRST_TICKS <= fast_cuda.MOST_TICKS
    assert fast_cuda.next_ticks(256, 0.2) == 256  # on target: as it was
    assert fast_cuda.next_ticks(256, 0.001) == 512  # far too short: at most doubled
    assert fast_cuda.next_ticks(4096, 1.6) == 512  # too long: cut at once, to what the target allows
    assert fast_cuda.next_ticks(16, 100.0) == fast_cuda.LEAST_TICKS and fast_cuda.next_ticks(60_000, 0.01) == fast_cuda.MOST_TICKS


def test_the_searches_jobs_have_the_references_shape(compiled):
    cfg = stage8.world("home", quick=True)
    starts = sample_starts(cfg, "cave", 2, 4)
    genomes = genomes_for(cfg, "fourier1", 6)
    job = {"cfg": cfg, "mode": "fourier1", "seed": 4, "starts": starts, "start": 1, "genomes": genomes}
    ref, got = evolve.train_job(job), fast.train_job(job)
    assert set(got) == set(ref)
    for k in ref:
        assert got[k].shape == ref[k].shape and got[k].dtype == ref[k].dtype, k
    assert np.array_equal(got["fitness"][:2], fast.train_job({**job, "genomes": genomes[:2]})["fitness"])
    vjob = {"cfg": cfg, "mode": "fourier1", "seed": 4, "starts": starts, "genome": genomes[0]}
    vref, vgot = evolve.validation_job(vjob), fast.validation_job(vjob)
    assert set(vgot) == set(vref) and all(isinstance(v, float) for v in vgot.values())
    assert 0.0 <= vgot["survival"] <= 1.0 and 0.0 < vgot["fitness"] < 1.0


def test_the_mapper_sends_only_the_searches_jobs():
    seen = []

    def inner(fn, jobs):
        seen.append(fn)
        return [None for _ in jobs]

    m = fast.Mapper(inner)
    m(evolve.train_job, [1])
    m(evolve.validation_job, [1])
    m(len, [1])
    assert seen == [fast.train_job, fast.validation_job, len]


def test_a_search_on_this_engine_resumes_bit_for_bit(compiled, tmp_path):
    home = stage8.world("home", quick=True)
    cma = stage8.cma_for(True)
    mix = [stage8.world(w, True) for w in stage8.TRAINED]
    kwargs = dict(world_for=lambda g: mix, validation_worlds=stage8.validation_worlds(True), log=lambda _: None)
    straight = run(home, "fourier1", cma, 8001, tmp_path / "a", fast.Mapper(), **kwargs)
    run(home, "fourier1", cma, 8001, tmp_path / "b", fast.Mapper(), stop_after=1, **kwargs)
    resumed = run(home, "fourier1", cma, 8001, tmp_path / "b", fast.Mapper(), **kwargs)
    assert straight["next_generation"] == cma.generations and straight["champion_info"] is not None
    assert np.array_equal(straight["champion"], resumed["champion"]) and np.array_equal(straight["samples"], resumed["samples"])
    assert [h["best_fitness"] for h in straight["history"]] == [h["best_fitness"] for h in resumed["history"]]
    assert json.dumps(straight["validation"]) == json.dumps(resumed["validation"])  # as text: a mean has no training fitness (NaN)
    # and it is a search on this engine, not the reference: one generation's fitness is the compiled life's
    one = CMA.quick().but(generations=1, validate_every=5)
    out = run(home, "fourier1", one, 8001, tmp_path / "c", fast.Mapper(), log=lambda _: None)
    ref = run(home, "fourier1", one, 8001, tmp_path / "d", map, log=lambda _: None)
    assert np.array_equal(out["samples"], ref["samples"])  # the same genomes were asked for


def test_worlds_it_does_not_run_are_refused(compiled):
    cfg = stage8.world("home", quick=True)
    starts = sample_starts(cfg, "cave", 1, 1)
    g = genomes_for(cfg, "fourier1", 1)
    with pytest.raises(ValueError, match="sense_contrast"):
        fast.simulate_network(cfg.but(sense_contrast=0.0), starts, "fourier1", g, seed=1, ticks=2)
    with pytest.raises(ValueError, match="cave"):
        fast.simulate_network(cfg, sample_starts(cfg, "lamp", 1, 1), "fourier1", g, seed=1, ticks=2)
    with pytest.raises(ValueError, match="genomes"):
        fast.simulate_network(cfg, starts, "fourier1", np.repeat(g, 2, axis=0), seed=1, ticks=2)
    held = decode(cfg, "fourier1", g)
    held.extra = np.zeros_like(held.bias)
    with pytest.raises(ValueError, match="held"):
        fast.cell_arrays(cfg, held)
    with pytest.raises(ValueError, match="device"):
        fast.simulate_network(cfg, starts, "fourier1", g, seed=1, ticks=2, device="tpu")


CUDA_SIM = """
import os, sys
os.environ["NUMBA_ENABLE_CUDASIM"] = "1"
import protocell
import numpy as np
from experiments import stage8
from protocell import evolve, fast
from protocell.cell import random_genomes
from protocell.rng import stream
from protocell.world import sample_starts

from protocell import fast_cuda
fast_cuda.FIRST_TICKS, fast_cuda.LEAST_TICKS, fast_cuda.MOST_TICKS = 5, 3, 5  # launches of a few ticks: a life is carried across several

cfg = stage8.world("shaded", quick=True)
starts = sample_starts(cfg, "cave", 2, 5)
genomes = random_genomes(cfg, "fourier1", 3, stream(5, "genomes"))
specs = [fast.LifeSpec(cfg, "fourier1", genomes[g], starts, row, 5) for g in range(3) for row in range(2)]
cpu = fast.run_specs(specs, ticks=12, strict=True)
gpu = fast.run_specs(specs, ticks=12, strict=True, device="cuda")
same = all(np.array_equal(getattr(cpu, k), getattr(gpu, k)) for k in fast.Lives.__dataclass_fields__)
jobs = [{"cfg": cfg.but(lifetime=20, day_ticks=10), "mode": "fourier1", "seed": 5, "starts": sample_starts(cfg.but(lifetime=20, day_ticks=10), "cave", 2, 5),
         "start": s, "genomes": genomes[c:c + 2]} for s in range(2) for c in (0, 1)]
a = list(fast.CudaMapper()(evolve.train_job, jobs))
b = list(fast.Mapper()(evolve.train_job, jobs))
same_jobs = all(np.array_equal(x[k], y[k]) for x, y in zip(a, b) for k in x)
print("SAME" if same and same_jobs and len(a) == 4 else f"DIFFERENT {same} {same_jobs}")
"""


def test_the_gpu_path_gives_the_cpus_bits_in_numbas_simulator():
    """Numba's CUDA simulator runs the kernel as plain Python on the CPU: it proves the GPU path's plumbing (the
    kernel's launch, the device arrays, the batching), not a GPU."""
    env = {**os.environ, "NUMBA_ENABLE_CUDASIM": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[1])}
    done = subprocess.run([sys.executable, "-c", CUDA_SIM], capture_output=True, text=True, env=env, cwd=Path(__file__).resolve().parents[1])
    assert done.stdout.strip().endswith("SAME"), done.stdout[-400:] + done.stderr[-1200:]


def test_the_life_compiles_for_cuda():
    """The life compiles to GPU code wherever NVIDIA's compiler is installed (the ``gpu`` extra), device or no device.
    Without that extra there is no compiler and the test is skipped; with it, a failure here is a failure: a GPU run
    would stop at the same place. (The kernel around the life, a dozen lines, needs a device to compile; the
    simulator's test runs it.)"""
    import importlib.util

    cuda = pytest.importorskip("numba.cuda")
    from numba import float64, int64

    f1, f2, f3, i1 = float64[::1], float64[:, ::1], float64[:, :, ::1], int64[::1]
    signature = (int64, int64, int64, int64, int64, int64, int64, f1, f3, f2, f2, f2, f2, f2, f1, f1, f1, i1, f2, f3, f3, f2, f2, f2, f2, f1, f1, f1, f1, f1, f1, f1, f1)
    if importlib.util.find_spec("numba_cuda") is None:  # Numba's own, older CUDA target: here only if a compiler happens to be about
        try:
            ptx, _ = cuda.compile_ptx(fast._life, signature, device=True, cc=(7, 5))
        except Exception as e:
            pytest.skip(f"no CUDA compiler without the gpu extra: {type(e).__name__}")
    else:
        ptx, _ = cuda.compile_ptx(fast._life, signature, device=True, cc=(7, 5))
    assert ".func" in ptx and len(ptx) > 20_000  # a device function with a life's worth of code
