"""Stage 7 (docs/prereg/stage7.md): the worlds are what they say, and a quick run reads every cell in every world."""

from experiments import stage4a, stage5b, stage7


def test_home_is_stage_4as_world_with_stage_5s_cell_and_the_others_differ_as_named():
    home = stage7.world_cfg("home", False)
    assert home == stage5b.world(False)
    assert not stage7.world_cfg("fixed mouth", False).cave_sweep and stage7.world_cfg("fixed mouth", False).eta == home.eta
    assert stage7.world_cfg("tighter", False).eta < home.eta and stage7.world_cfg("tighter", False).cave_sweep
    assert stage7.world_cfg("flicker", False).cloud_shade == 0.3 and stage7.world_cfg("sweep and flicker", False).cave_sweep
    assert stage7.world_cfg("spot", False).cave_path == "circle" and stage7.world_cfg("shaded", False).shade_floor == 0.3
    assert stage4a.world(False).but(sensing="relative", adapt_tau=home.adapt_tau, sense_floor=home.sense_floor, level_floor=home.level_floor) == home
    assert len(stage7.UNSEEN) == 6


def test_quick_run_end_to_end(tmp_path):
    s = stage7.main(["--quick", "--out", str(tmp_path), "--worlds", "home", "flicker", "spot", "shaded", "fixed mouth", "tighter", "sweep and flicker"])
    assert set(s["worlds"]) == set(stage7.WORLDS) and [p["number"] for p in s["predictions"]] == [1, 2, 3, 4, 5, 6]
    for w in s["worlds"].values():
        assert set(w["cells"]) == set(stage7.CELLS) and set(w["rules"]) == {"B2r", "B5", "B6", "B8"}
    for name in ("cells.csv", "summary.json", "manifest.json"):
        assert (tmp_path / name).exists()
