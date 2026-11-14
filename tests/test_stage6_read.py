"""Stage 6's reading probe: an onset keeps what came before it, and the probe runs end to end."""

import math

import numpy as np

from experiments import stage6_read as read


def test_an_onset_keeps_the_previous_runs_direction_and_length():
    t = read.History(1)
    one = np.ones(1, dtype=np.int64)
    target = np.zeros(1)
    pattern = [(1, 0.0)] * 5 + [(0, 0.0)] * 20 + [(1, math.pi)] * 4 + [(0, 0.0)] * 3 + [(1, 0.0)] * 3
    for running, direction in pattern:
        t.step(np.array([bool(running)]), one, np.array([direction]), target)
    t.finish()
    assert len(t.onsets) == 3
    assert math.isnan(t.onset_prev_cos[0])  # the first run has none before it
    assert t.onset_prev_cos[1] == 1.0 and t.onset_prev_ticks[1] == 5  # after a run toward the target, five ticks long
    assert t.onset_prev_cos[2] == -1.0 and t.onset_prev_ticks[2] == 4 and t.onset_gaps[1:] == [20, 3]


def test_quick_probe_end_to_end(tmp_path):
    result = read.main(["--quick", "--out", str(tmp_path)])
    assert set(result["cells"]) == {"design16", "champion3603", "champion6301", "champion6301 ring cut"}
    assert [p["number"] for p in result["predictions"]] == [1, 2, 3, 4, 5]
    assert set(result["cells"]["design16"]["ring"]) == set(read.RING_GENES)
    for name in ("budget.csv", "onsets_by_rest.csv", "open_loop.csv", "summary.json", "manifest.json"):
        assert (tmp_path / name).exists()
