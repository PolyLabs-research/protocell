"""Stage 8b's reading probe: its cells are where the stage left them, a circler is what D44 called one, and the probe
runs end to end."""

from experiments import stage8, stage8b_read as read


def test_the_cells_are_the_stages_champions():
    cells = read.genomes()
    assert set(cells) == set(read.CELLS) and len({g.tobytes() for g in cells.values()}) == len(cells)  # nine different cells
    assert set(read.GENERALISTS) | set(read.EARLIER.values()) | set(read.LOST) == set(read.CELLS)
    assert read.SEED not in (48, 54, 55, 65, 66)  # stage 8's reading, stage 8b's test, stage 8c's test


def test_a_circler_runs_most_of_the_day_and_turns():
    assert read.circles({"running_by_day": 0.95, "turning_during_runs": -0.075})  # champion 8102 at home (D45)
    assert not read.circles({"running_by_day": 0.84, "turning_during_runs": -0.002})  # champion 6402: a straight swimmer
    assert not read.circles({"running_by_day": 0.24, "turning_during_runs": -0.2})  # a rester


def test_quick_probe_end_to_end(tmp_path):
    s = read.main(["--quick", "--out", str(tmp_path)])
    assert set(s["movement"]) == set(stage8.TRAINED) and [p["number"] for p in s["predictions"]] == [1, 2, 3, 4, 5, 6]
    for w in stage8.TRAINED:
        assert set(s["movement"][w]) == set(read.CELLS) and set(s["parts"][w]) == set(read.GENERALISTS)
        assert all(set(v) == {"ring_links", "direction_removed"} for v in s["parts"][w].values())
    for name in ("movement.csv", "parts.csv", "summary.json", "manifest.json"):
        assert (tmp_path / name).exists()
    assert (tmp_path / "movement.csv").read_text().count("\n") == 1 + 4 * len(read.CELLS)
    assert (tmp_path / "parts.csv").read_text().count("\n") == 1 + 4 * len(read.GENERALISTS) * 2
