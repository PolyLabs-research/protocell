"""Stage 8d's reading probe: its fifteen cells are stage 8c's that follow the spot, and the probe runs end to end."""

import json

from experiments import stage8, stage8c, stage8d, stage8d_read as read


def test_the_fifteen_are_stage_8cs_generalists_and_near_misses():
    s = json.loads((stage8c.DEFAULT_OUT / "test" / "summary.json").read_text())
    assert sorted(int(c) for c in s["generalists"]) == sorted(read.GENERALISTS)
    assert read.NEAR == stage8d.NEAR and not set(read.NEAR) & set(read.GENERALISTS)
    cells = read.genomes()
    assert len(cells) == 15 and len({g.tobytes() for g in cells.values()}) == 15
    assert read.SEED not in (48, 54, 55, 65, 66, 67, stage8d.TEST_SEED, stage8d.BOOTSTRAP_SEED)


def test_quick_probe_end_to_end(tmp_path):
    s = read.main(["--quick", "--out", str(tmp_path)])
    assert set(s["movement"]) == set(stage8.TRAINED) and [p["number"] for p in s["predictions"]] == [1, 2, 3, 4, 5]
    assert all(len(s["movement"][w]) == 15 for w in stage8.TRAINED)
    assert set(s["medians"]["flicker"]) == {"generalists", "near"}
    assert (tmp_path / "movement.csv").read_text().count("\n") == 1 + 4 * 15
    assert (tmp_path / "manifest.json").exists() and (tmp_path / "summary.json").exists()
