"""The cave pool as built (docs/prereg/cave.md): its light equals the probe's formulas; its starts, lifetimes and
matched reserves; the reflexes that rest and retreat; a batch with cells of different lifetimes; the runner at the
smoke test's sizes."""

from __future__ import annotations

import json
import math

import protocell  # noqa: F401
import numpy as np
import pytest

from experiments import cave_geometry as probe_mod
from experiments.cave import CONFIGURATIONS, best_fixed_point, configure, main
from protocell.config import CAVE, cave_damage_rate
from protocell.energy import start_reserve
from protocell.sim import BURNT, STARVED, Reflex, simulate
from protocell.world import centre_light, daylight, lifetimes, mouth_angle, node_light, sample_starts, soak_radius

DAY, HALF = CAVE.day_ticks, CAVE.day_ticks // 2


@pytest.mark.parametrize("cycle,sweep", [(True, False), (False, False), (True, True)])
def test_the_built_light_equals_the_probes_formulas(cycle: bool, sweep: bool) -> None:
    cfg = CAVE.but(cave_cycle=cycle, cave_sweep=sweep)
    cave = probe_mod.Cave(cycle=cycle, sweep=sweep)
    rng = np.random.default_rng(3)
    pos = rng.uniform(-3500, 3500, size=(12, 2))
    heading = rng.uniform(-math.pi, math.pi, size=12)
    source = np.repeat(np.array([[0.0, -5000.0]]), 12, axis=0)
    for t in (0, 3600, HALF // 2, HALF - 1, HALF + 5000, DAY + 20000):
        built = node_light(cfg, "cave", source, pos, heading, np.full(12, t))
        assert np.allclose(built, probe_mod.node_light(cave, pos, heading, t), rtol=1e-12, atol=1e-15)
        assert np.allclose(centre_light(cfg, "cave", source, pos, np.full(12, t)), probe_mod.centre_light(cave, pos, t), rtol=1e-12)
        assert np.allclose(daylight(cfg, np.array([t])), probe_mod.daylight(cave, np.array([t])))
        assert mouth_angle(cfg, np.array([t]))[0] == pytest.approx(float(probe_mod.source_angle(cave, np.array(t))))


def test_the_damage_rate_and_the_economy_match_the_probe() -> None:
    cave = probe_mod.Cave()
    assert CAVE.damage_rate == pytest.approx(probe_mod.damage_rate_rule(cave), rel=1e-9)
    assert cave_damage_rate() == pytest.approx(1.58e-4, rel=0.01)
    assert (CAVE.c0, CAVE.c1, CAVE.eta, CAVE.damage_repair, CAVE.sensor_noise_sd) == (cave.c0, cave.c1, cave.eta, cave.damage_repair, cave.sensor_sd)
    assert (CAVE.cave_falloff, CAVE.mouth_light, CAVE.dish_radius) == (cave.falloff, cave.mouth_light, cave.pool_radius)
    assert soak_radius(CAVE, "cave") == pytest.approx(2250.0)


def test_cave_starts_have_phases_and_lifetimes_to_the_second_sunrise() -> None:
    starts = sample_starts(CAVE, "cave", 30, seed=2)
    assert (starts.phase >= 0).all() and (starts.phase < DAY).all() and len(set(starts.phase.tolist())) > 20
    assert (starts.source == np.array([0.0, -5000.0])).all()
    assert (np.hypot(starts.pos[:, 0], starts.pos[:, 1]) <= CAVE.clamp_radius).all()
    ends = lifetimes(CAVE, starts)
    assert np.array_equal(ends, 2 * DAY - starts.phase) and (ends > DAY).all() and (ends <= 2 * DAY).all()
    assert np.array_equal(sample_starts(CAVE, "cave", 5, seed=2).phase, starts.phase[:5])
    assert (lifetimes(CAVE, sample_starts(CAVE, "lamp", 3, seed=0)) == CAVE.lifetime).all()


def test_the_matched_reserve_follows_the_rule() -> None:
    phases = np.array([0, 3 * 3600, 6 * 3600, HALF, HALF + 6 * 3600, DAY - 1])
    e0 = start_reserve(CAVE, phases)
    assert e0[0] == pytest.approx(0.28) and e0[1] == pytest.approx(0.96, abs=0.005) and e0[2] == 1.0 and e0[3] == 1.0
    assert e0[4] == pytest.approx(0.64) and e0[5] == pytest.approx(0.28, abs=1e-4)
    assert e0[:3].tolist() == [pytest.approx(probe_mod.start_reserve(probe_mod.Cave(), float(p))) for p in phases[:3]]


def test_the_reflex_rests_in_the_dark_and_retreats_above_the_threshold() -> None:
    dark = np.full((1, 16), 0.001)
    bright = np.full((1, 16), 6.0)
    bright[0, 0] = 7.0
    plain = Reflex(CAVE, 1, 10.0)
    resting = Reflex(CAVE, 1, 10.0, rest_below=0.01)
    retreating = Reflex(CAVE, 1, 10.0, rest_below=0.01, retreat_above=4.0)
    assert (plain.beats(dark, 0) > 0).all() and (resting.beats(dark, 0) == 0).all()
    assert plain.beats(bright, 0)[0, 0] > 0.5 and retreating.beats(bright, 0)[0, 0] < 0.5  # the lit node now beats less
    dim = np.full((1, 16), 0.5)
    dim[0, 0] = 0.6
    assert np.array_equal(retreating.beats(dim, 0), plain.beats(dim, 0))


def test_the_retreat_can_be_triggered_by_the_mean_or_the_brightest_node() -> None:
    sensed = np.full((1, 16), 2.0)
    sensed[0, 0] = 6.0  # the lit node above the threshold, the wall's mean (2.25) well below it
    by_mean = Reflex(CAVE, 1, 10.0, rest_below=0.01, retreat_above=4.0, retreat_on="mean").beats(sensed, 0)
    by_max = Reflex(CAVE, 1, 10.0, rest_below=0.01, retreat_above=4.0, retreat_on="max").beats(sensed, 0)
    assert by_mean[0, 0] > 0.5 and by_max[0, 0] < 0.5  # only the brightest-node rule backs away from the lit side
    assert CAVE.retreat_on == "max"  # amendment A1
    with pytest.raises(ValueError):
        Reflex(CAVE, 1, 10.0, retreat_above=4.0, retreat_on="median")


def test_the_retreat_probe_runs_its_twelve_jobs() -> None:
    from experiments.cave_retreat_probe import jobs, run_job

    todo = jobs(2, quick=True)
    assert len(todo) == 12 and {j["trigger"] for j in todo} == {"mean", "max"}
    row = run_job(todo[3])
    assert row["trigger"] == "max" and 0 <= row["survival"] <= 1 and row["n"] == 2


def test_a_batch_runs_each_cell_to_its_own_end_and_equals_its_singles() -> None:
    cfg = configure("burn", quick=True)  # a 2,000-tick day
    starts = sample_starts(cfg, "cave", 4, seed=2)
    assert len(set(lifetimes(cfg, starts).tolist())) > 1
    batch = simulate(cfg, starts, {"controller": "reflex", "k": 10, "rest_below": 0.01}, seed=2, record=True)
    for i in range(4):
        own = int(batch.lifetime[i])
        single = simulate(cfg, starts.take([i]), {"controller": "reflex", "k": 10, "rest_below": 0.01}, seed=2, record=True)
        assert single.ticks == own
        for name in ("pos", "heading", "energy", "beat"):
            assert np.array_equal(single.trajectory[name][0], batch.trajectory[name][i, :own]), name
        assert single.fitness[0] == batch.fitness[i] and single.survived[0] == batch.survived[i]
        if own < batch.ticks:  # frozen past its own end: no movement, no energy change, no beat counted
            assert (batch.trajectory["beat"][i, own:] == 0).all()
            assert np.array_equal(batch.trajectory["pos"][i, own:], np.repeat(batch.trajectory["pos"][i, own - 1:own], batch.ticks - own, axis=0))
    assert batch.fitness.tolist() == pytest.approx([batch.trajectory["energy"][i, :int(batch.lifetime[i])].mean() for i in range(4)])


def test_deaths_record_their_cause() -> None:
    cfg = configure("burn", quick=False)  # the real day: the damage rule is "an hour at the noon mouth kills"
    drawn = sample_starts(cfg, "cave", 2, seed=2).with_pos(np.array([[0.0, -4999.0], [0.0, 4500.0]]))
    from protocell.world import Starts
    starts = Starts("cave", drawn.source, drawn.pos, drawn.heading, drawn.index, np.zeros(2, dtype=np.int64))  # both at sunrise
    r = simulate(cfg, starts, {"controller": "still"}, seed=2, ticks=25_000)  # to mid-afternoon of the first day
    assert r.death_cause[0] == BURNT and r.death_cause[1] == STARVED and not r.survived.any()
    assert r.burn_share[0] > 0 and r.burn_share[1] == 0
    assert 0.28 * 60_000 <= r.death_tick[1] < 25_000  # after the pure-resting bound: the back gets a little morning light
    assert (r.night_beat == 0).all()  # daylight is 0 at the sunrise tick itself, the only "night" tick before mid-afternoon; B0 never beats


def test_the_best_fixed_point_comes_from_the_probe_at_the_real_day() -> None:
    point, probed = best_fixed_point(configure("day", quick=False), 40, (0, HALF))
    assert math.hypot(point[0], point[1]) <= CAVE.dish_radius and 0 <= probed["sitter_share"] <= 1
    assert math.hypot(point[0], point[1] + CAVE.dish_radius) == pytest.approx(probed["best_distance_to_mouth"])
    quick_point, quick_probed = best_fixed_point(configure("day", quick=True), 40, (0, 1000))
    assert quick_point.tolist() == [0.0, -CAVE.clamp_radius] and quick_probed["sitter_share"] is None


def test_the_quick_run_writes_a_configuration(tmp_path) -> None:
    summaries = main(["--config", "burn", "--quick", "--workers", "2", "--out", str(tmp_path)])
    assert set(summaries) == {"burn"}
    names = {p.name for p in (tmp_path / "burn").iterdir()}
    assert {"starts.csv", "b0.csv", "b0_best.csv", "b1.csv", "b2r_select.csv", "b2r_report.csv", "b2rr_select.csv", "b2rr_report.csv",
            "b3_uniform.csv", "b3_fourier1.csv", "summary.json", "manifest.json"} <= names
    back = json.loads((tmp_path / "burn" / "summary.json").read_text())
    assert set(back["checks"]) == {"K1", "K2", "K3", "K4", "K5", "K6", "K7"} and back["checks"]["K6"]["pass"] is True
    assert back["checks"]["K7"]["judged"] is True and "b2rr" in back["checks"]["K7"]
    assert back["checks"]["K5"]["bar"] == "b2rr" and back["bar"]["controller"] == "b2rr"  # with damage on, the bar is B2rr (A1)
    manifest = json.loads((tmp_path / "burn" / "manifest.json").read_text())
    assert manifest["settings"]["configuration"] == "burn" and manifest["settings"]["day_ticks"] == 2000
    assert set(CONFIGURATIONS) == {"noon", "day", "burn", "sweep"}
