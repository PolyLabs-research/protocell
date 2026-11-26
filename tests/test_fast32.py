"""The single-precision life (protocell/fast32.py): it stays with the double engine over a life's first ticks, a life in
pieces is the life whole, a batch equals its singles, the searches run on it unchanged, and its GPU form compiles mostly
to single-precision instructions."""

import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("numba")

from experiments import stage4b, stage8  # noqa: E402
from protocell import evolve, fast, fast32  # noqa: E402
from protocell.cell import decode, random_genomes  # noqa: E402
from protocell.cmaes import run  # noqa: E402
from protocell.config import CAVE  # noqa: E402
from protocell.rng import stream  # noqa: E402
from protocell.world import sample_starts  # noqa: E402

SAME = ("fitness", "light_soaked", "mean_beat", "survived", "death_tick", "death_cause", "final_energy", "final_damage", "pos", "heading")
ROOT = Path(__file__).resolve().parents[1]


def worlds():
    """Stage 8's four worlds (the smoke test's day), a world on stage 4b's path, the cave of stage 1 (absolute sensing,
    shaded, damage live), and two that kill quickly."""
    home = stage8.world("home", quick=True)
    out = {name: stage8.world(name, quick=True) for name in stage8.TRAINED}
    out["path"] = stage4b.training_world(home, 1, 2, 2).but(shade_floor=0.65)
    out["cave"] = CAVE.but(day_ticks=2000, lifetime=4000, cave_sweep=True)
    out["starving"] = home.but(c0=1.0 / 300.0)
    out["burning"] = out["cave"].but(damage_threshold=0.05, damage_rate=0.5)
    return out


def genomes_for(cfg, n, seed=5):
    return random_genomes(cfg, "fourier1", n, stream(seed, "genomes"))


def test_it_stays_with_the_double_engine_over_the_first_ticks():
    for name, cfg in worlds().items():
        starts = sample_starts(cfg, "cave", 4, 7)
        g = genomes_for(cfg, 4)
        a = fast.simulate_network(cfg, starts, "fourier1", g, seed=7, ticks=100)
        b = fast.simulate_network(cfg, starts, "fourier1", g, seed=7, ticks=100, precision="single")
        assert float(np.abs(a.pos - b.pos).max()) < 1e-3, name  # single precision moves a cell by thousandths of a radius at most
        assert float(np.abs(a.fitness - b.fitness).max()) < 1e-8, name
        assert np.array_equal(a.survived, b.survived) and np.array_equal(a.death_tick, b.death_tick), name


def test_a_life_run_in_pieces_is_the_life_run_whole():
    died = set()
    for name, cfg in worlds().items():
        starts = sample_starts(cfg, "cave", 3, 13)
        params = decode(cfg, "fourier1", genomes_for(cfg, 3))
        tracks = [fast.build_track(cfg, starts, i, 13) for i in range(3)]
        cells, on = [0, 1, 2, 0, 1, 2, 0, 1, 2], [0, 0, 0, 1, 1, 1, 2, 2, 2]
        whole = fast32.run_lives32(cfg, params, tracks, cells, on)
        for pieces in (1000, 251, 7) if name in ("home", "starving", "burning") else (251,):
            parted = fast32.run_lives32(cfg, params, tracks, cells, on, pieces=pieces)
            for k in SAME:
                assert np.array_equal(getattr(parted, k), getattr(whole, k)), (name, pieces, k)
        died |= set(whole.death_cause.tolist())
    assert died == {0, 1, 2}
    with pytest.raises(ValueError, match="piece"):
        fast32.run_lives32(cfg, params, tracks, cells, on, pieces=0)


def test_a_batch_equals_its_singles_and_the_order_does_not_matter():
    cfg = stage8.world("spot", quick=True)
    starts = sample_starts(cfg, "cave", 3, 21)
    g = genomes_for(cfg, 5)
    specs = [fast.LifeSpec(cfg, "fourier1", g[k], starts, row, 21) for k in range(5) for row in range(3)]
    together = fast.run_specs(specs, precision="single")
    one_call = fast.run_specs(specs, max_tracks=3, precision="single")
    order = list(reversed(range(len(specs))))
    backwards = fast.run_specs([specs[i] for i in order], precision="single")
    for k in SAME:
        assert np.array_equal(getattr(one_call, k), getattr(together, k)), k
        assert np.array_equal(getattr(backwards, k), getattr(together, k)[order]), k
    alone = fast.run_specs([specs[7]], precision="single")
    assert alone.fitness[0] == together.fitness[7] and np.array_equal(alone.pos[0], together.pos[7])


def test_what_it_is_not_made_for_is_refused():
    cfg = stage8.world("home", quick=True)
    starts = sample_starts(cfg, "cave", 1, 1)
    g = genomes_for(cfg, 1)
    small = cfg.but(n_wall=12)
    with pytest.raises(ValueError, match="16 wall nodes"):
        fast.simulate_network(small, starts, "fourier1", genomes_for(small, 1), seed=1, ticks=2, precision="single")
    with pytest.raises(ValueError, match="strict"):
        fast.simulate_network(cfg, starts, "fourier1", g, seed=1, ticks=2, strict=True, precision="single")
    with pytest.raises(ValueError, match="precision"):
        fast.simulate_network(cfg, starts, "fourier1", g, seed=1, ticks=2, precision="half")
    with pytest.raises(ValueError, match="sense_contrast"):
        fast.simulate_network(cfg.but(sense_contrast=0.0), starts, "fourier1", g, seed=1, ticks=2, precision="single")


def test_the_mapper_sends_the_searches_jobs_to_single_precision():
    seen = []

    def inner(fn, jobs):
        seen.append(fn)
        return [None for _ in jobs]

    m = fast.Mapper(inner, precision="single")
    m(evolve.train_job, [1])
    m(evolve.validation_job, [1])
    m(len, [1])
    assert seen == [fast32.train_job, fast32.validation_job, len]
    with pytest.raises(ValueError):
        fast.Mapper(inner, precision="half")


def test_a_search_in_single_precision_resumes_bit_for_bit(tmp_path):
    home = stage8.world("home", quick=True)
    cma = stage8.cma_for(True)
    mix = [stage8.world(w, True) for w in stage8.TRAINED]
    kwargs = dict(world_for=lambda g: mix, validation_worlds=stage8.validation_worlds(True), log=lambda _: None)
    mapper = fast.Mapper(precision="single")
    straight = run(home, "fourier1", cma, 8001, tmp_path / "a", mapper, **kwargs)
    run(home, "fourier1", cma, 8001, tmp_path / "b", mapper, stop_after=1, **kwargs)
    resumed = run(home, "fourier1", cma, 8001, tmp_path / "b", mapper, **kwargs)
    assert np.array_equal(straight["champion"], resumed["champion"]) and np.array_equal(straight["samples"], resumed["samples"])
    assert json.dumps(straight["validation"]) == json.dumps(resumed["validation"])


CUDA_SIM = """
import os
os.environ["NUMBA_ENABLE_CUDASIM"] = "1"
import protocell
import numpy as np
from experiments import stage8
from protocell import fast, fast_cuda
from protocell.cell import random_genomes
from protocell.rng import stream
from protocell.world import sample_starts

fast_cuda.FIRST_TICKS, fast_cuda.LEAST_TICKS, fast_cuda.MOST_TICKS = 5, 3, 5
from protocell import fast32_cuda
fast32_cuda.FIRST_TICKS = 5
cfg = stage8.world("shaded", quick=True)
starts = sample_starts(cfg, "cave", 2, 5)
genomes = random_genomes(cfg, "fourier1", 3, stream(5, "genomes"))
specs = [fast.LifeSpec(cfg, "fourier1", genomes[g], starts, row, 5) for g in range(3) for row in range(2)]
cpu = fast.run_specs(specs, ticks=12, precision="single")
gpu = fast.run_specs(specs, ticks=12, device="cuda", precision="single")
close = float(np.abs(cpu.pos - gpu.pos).max()) < 1e-4 and float(np.abs(cpu.fitness - gpu.fitness).max()) < 1e-9
print("CLOSE" if close and np.array_equal(cpu.survived, gpu.survived) else f"FAR {np.abs(cpu.pos - gpu.pos).max()}")
"""


def test_the_gpu_path_runs_in_numbas_simulator():
    """The simulator runs the kernel as plain Python (its ``math.exp`` of a single-precision number is a double): it
    proves the plumbing, the launches and the state carried between them, not single-precision arithmetic."""
    env = {**os.environ, "NUMBA_ENABLE_CUDASIM": "1", "PYTHONPATH": str(ROOT)}
    done = subprocess.run([sys.executable, "-c", CUDA_SIM], capture_output=True, text=True, env=env, cwd=ROOT)
    assert done.stdout.strip().endswith("CLOSE"), done.stdout[-400:] + done.stderr[-1500:]


def test_the_life_compiles_for_cuda_mostly_in_single_precision():
    """Where NVIDIA's compiler is installed (the ``gpu`` extra), the life compiles to GPU code whose arithmetic is
    single precision but for the few double-precision steps the design keeps (place, heading, reserve, sums)."""
    import importlib.util

    if importlib.util.find_spec("numba_cuda") is None:
        pytest.skip("no CUDA compiler without the gpu extra")
    from numba import cuda, float32, float64, int64

    f1, f2, f3 = float64[::1], float64[:, ::1], float64[:, :, ::1]
    s1, s2, s3 = float32[::1], float32[:, ::1], float32[:, :, ::1]
    signature = (int64, int64, int64, int64, int64, f1, s3, s2, s2, s2, s2, s2, s1, s1, int64[::1], f2, f3, s2, s2, s3, s2, f2, s2, s2,
                 s1, s1, s1, s1, s1)
    ptx, _ = cuda.compile_ptx(fast32._life32, signature, device=True, cc=(8, 9))
    ops = Counter(line.split()[0] for line in (x.strip() for x in ptx.splitlines()) if line and not line.startswith(("//", ".", "{", "}", "$")))
    arithmetic = re.compile(r"^(add|sub|mul|div|fma|sqrt|neg|abs|min|max)\.")
    f64 = sum(v for k, v in ops.items() if k.endswith(".f64") and arithmetic.match(k))
    f32 = sum(v for k, v in ops.items() if ".f32" in k and arithmetic.match(k))
    assert f64 <= 40 and f32 >= 20 * f64, (f64, f32)
