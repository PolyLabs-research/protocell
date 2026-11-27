"""Stage 8e's reading: its cells are the runs that did not follow the spot, as they stood at 400 generations, and the
probe runs end to end."""

import json

from experiments import stage8c, stage8d, stage8e_read as read


def test_the_cells_are_the_runs_that_did_not_follow_the_spot():
    s = json.loads((stage8c.DEFAULT_OUT / "test" / "summary.json").read_text())
    fresh = {int(c): r for c, r in s["reading"].items() if r["kind"] == "fresh"}
    followers = {x for x, r in fresh.items() if "spot" in r["trained"]}
    assert set(read.CONTROL + read.SHADED + read.STILL) == set(fresh) - followers  # every run of stage 8c that did not
    assert read.CONTROL == stage8d.CONTROL and all(not fresh[x]["trained"] for x in read.STILL)
    cells = read.genomes()
    assert len(cells) == 17 and len({g.tobytes() for g in cells.values()}) == 17
    assert read.SEED not in (48, 54, 55, 65, 66, 67, 70, 71, 72)


def test_quick_probe_end_to_end(tmp_path):
    s = read.main(["--quick", "--out", str(tmp_path)])
    assert set(s["movement"]) == set(read.WORLDS) and all(len(s["movement"][w]) == 17 for w in read.WORLDS)
    assert [p["number"] for p in s["predictions"]] == [1, 2, 3, 4, 5]
    assert (tmp_path / "movement.csv").read_text().count("\n") == 1 + 2 * 17
