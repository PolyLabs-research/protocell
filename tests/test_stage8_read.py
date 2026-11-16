"""Stage 8's reading probe: the cloud's two events are what they say, and the probe runs end to end."""

from experiments import stage8, stage8_read as read


def test_a_cloud_is_a_fall_to_its_shade_and_a_return():
    cfg = stage8.world("home", True)
    rows = read.cloud_rows(cfg, read.genomes(cfg, True), True)
    assert {r["event"] for r in rows} == {"shadow", "sun returns"} and len(rows) == len(read.CELLS) * len(read.CLOUD_LEVELS) * 2
    assert all(0.0 <= r["moving_before"] <= 1.0 and 0.0 <= r["moving_after"] <= 1.0 for r in rows)


def test_quick_probe_end_to_end(tmp_path):
    s = read.main(["--quick", "--out", str(tmp_path)])
    assert set(s["worlds"]) == set(stage8.TRAINED) and [p["number"] for p in s["predictions"]] == [1, 2, 3, 4, 5]
    for w in s["worlds"].values():
        assert set(w["cells"]) == set(read.MOVERS) and "ring_links" in w["removals"] and "direction_removed" in w
    for name in ("budget.csv", "movement.csv", "parts.csv", "clouds.csv", "summary.json", "manifest.json"):
        assert (tmp_path / name).exists()
