"""Stage 4's design probe (experiments/stage4_probe.py): the circling spot, the clouds, B8, the ceiling, the runner."""

from __future__ import annotations

import json
import math

import protocell  # noqa: F401
import numpy as np
import pytest

from experiments import stage4_probe as probe
from experiments.stage3 import configure
from protocell.sim import AimAndRun, simulate
from protocell.world import Sky, clamp, mouth_position, node_angles, node_light, sample_starts

CFG = configure(quick=True)
N = CFG.n_wall
THETA = node_angles(CFG)


def test_the_spot_circles_the_pools_centre_anticlockwise() -> None:
    spot = CFG.but(cave_path="circle", path_radius=2500.0, path_period=400)
    p = mouth_position(spot, np.array([0, 100, 200, 400]))
    assert np.allclose(p, [[2500.0, 0.0], [0.0, 2500.0], [-2500.0, 0.0], [2500.0, 0.0]], atol=1e-9)
    assert np.allclose(mouth_position(CFG, np.array([0, 100])), [[0.0, -CFG.dish_radius]] * 2, atol=1e-9)  # the mouth as it was
    with pytest.raises(ValueError):
        mouth_position(CFG.but(cave_path="zigzag"), np.array([0]))


def test_the_spots_starts_are_the_caves_with_the_source_where_the_spot_is() -> None:
    spot = CFG.but(cave_path="circle", path_period=400)
    a, b = sample_starts(CFG, "cave", 5, 16), sample_starts(spot, "cave", 5, 16)
    assert np.array_equal(a.pos, b.pos) and np.array_equal(a.heading, b.heading) and np.array_equal(a.phase, b.phase)
    assert np.allclose(b.source, mouth_position(spot, b.phase))


def test_a_translucent_cell_on_the_spot_gets_its_light_without_a_direction() -> None:
    spot = CFG.but(cave_path="circle", path_period=400)
    at = mouth_position(spot, np.array([30]))
    light = node_light(spot, "cave", at, at, np.array([0.3]), np.array([30]))  # the centre exactly on the source
    assert np.isfinite(light).all() and light.min() > 0.0


def test_the_sky_is_each_starts_own_and_alternates_sun_and_shade() -> None:
    cloudy = CFG.but(cloud_shade=0.3, cloud_sun_mean=60.0, cloud_shade_mean=30.0)
    both, alone = Sky(cloudy, 16, [3, 5]), Sky(cloudy, 16, [5])
    seen_both = np.array([both.at(t) for t in range(3000)])
    seen_alone = np.array([alone.at(t) for t in range(3000)])
    assert np.array_equal(seen_both[:, 1], seen_alone[:, 0])  # start 5's sky is the same in any batch
    assert set(np.unique(seen_both)) <= {0.3, 1.0} and not np.array_equal(seen_both[:, 0], seen_both[:, 1])
    assert 0.5 < (seen_both == 1.0).mean() < 0.8  # sun about two thirds of the time
    with pytest.raises(ValueError):
        both.at(5)  # in order only
    with pytest.raises(ValueError):
        Sky(CFG.but(cloud_shade=1.0), 16, [1])


def test_the_cells_see_and_eat_the_clouded_light() -> None:
    cloudy = CFG.but(cloud_shade=0.3, cloud_sun_mean=60.0, cloud_shade_mean=30.0)
    starts = sample_starts(cloudy, "cave", 2, 16)
    seen = []
    simulate(cloudy, starts, {"controller": "still"}, seed=16, ticks=300, observe=lambda t, s: seen.append(s["light"].copy()))
    sky = Sky(cloudy, 16, starts.index.tolist())
    clear = node_light(CFG, "cave", starts.source, starts.pos, starts.heading, starts.phase + 0)
    assert np.allclose(seen[0], clear * sky.at(0)[:, None], rtol=0.0, atol=0.0)
    sunny = simulate(CFG, starts, {"controller": "still"}, seed=16, ticks=300)
    shaded = simulate(cloudy, starts, {"controller": "still"}, seed=16, ticks=300)
    assert np.all(shaded.final_energy <= sunny.final_energy)


def test_b8_runs_toward_the_brighter_side_while_the_light_rises() -> None:
    b8 = AimAndRun(CFG, 1, tau=3.0, aim_tau=1.0, rest_below=0.01)
    pattern = 1.0 + 0.01 * np.cos(THETA - 1.0)
    assert (b8.beats(0.5 * pattern[None, :], 0) == 0.0).all()  # the first reading only sets the memory
    g = b8.beats(0.6 * pattern[None, :], 1)  # rising
    assert g.sum() == 8 and abs(probe_wrap(np.angle((g[0] * np.exp(1j * THETA)).sum()) - 1.0)) < math.pi / 16
    assert (b8.beats(0.4 * pattern[None, :], 2) == 0.0).all()  # falling: it waits
    assert (b8.beats(np.full((1, N), 0.005), 3) == 0.0).all()  # in the dark it rests


def probe_wrap(a: float) -> float:
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def test_the_ceiling_is_a_still_cell_at_the_brightest_point() -> None:
    starts = sample_starts(CFG, "cave", 3, 16)
    fitness, alive = probe.always_brightest(CFG, starts)
    at_mouth = starts.with_pos(clamp(CFG, mouth_position(CFG, starts.phase)))  # the fixed mouth: the brightest point never moves
    still = simulate(CFG, at_mouth, {"controller": "still"}, seed=16)
    assert np.array_equal(fitness, still.fitness) and np.array_equal(alive, still.survived)
    anywhere = simulate(CFG, starts, {"controller": "still"}, seed=16)
    assert np.all(fitness >= anywhere.fitness)


def test_the_quick_run_writes_its_tables(tmp_path) -> None:
    summary = probe.main(["--quick", "--workers", "2", "--out", str(tmp_path), "--worlds", "clouds", "spot_2h"])
    names = {p.name for p in tmp_path.iterdir()}
    assert {"grid.csv", "per_start.csv", "headroom.csv", "random_genomes.csv", "summary.json", "manifest.json"} <= names
    assert set(summary["worlds"]) == {"clouds", "spot_2h"}
    for w in summary["worlds"].values():
        assert w["best_simple_rule"] in probe.SIMPLE and w["ceiling"] >= w["rules"]["B0"]["report_fitness"]
    assert json.loads((tmp_path / "manifest.json").read_text())["settings"]["seed"] == 16


def test_the_economy_probe_scales_the_gain_and_writes_its_tables(tmp_path) -> None:
    from experiments import stage4_economy as economy
    from protocell.config import CAVE

    assert economy.variant_cfg("spot_2h", 0.4, True).eta == pytest.approx(0.4 * CAVE.eta)
    assert economy.variant_cfg("spot_2h", 0.4, True).path_period == 7_200
    summary = economy.main(["--quick", "--workers", "2", "--out", str(tmp_path), "--worlds", "flicker"])
    assert set(summary["variants"]) == {f"flicker eta x{s:g}" for s in economy.SCALES}
    assert {"grid.csv", "per_start.csv", "headroom.csv", "summary.json", "manifest.json"} <= {p.name for p in tmp_path.iterdir()}
