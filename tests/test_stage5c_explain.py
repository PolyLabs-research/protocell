"""Stage 5c's explaining probe: the hybrids are what they say, the gaps are counted, and the probe runs end to end."""

import numpy as np

from experiments import stage5b, stage5c, stage5c_explain as ex
from protocell.cell import layout


def test_the_hybrids_swap_one_group_and_the_line_passes_through_both_cells():
    cfg = stage5b.world(True)
    c = ex.cells(cfg, True)
    g0, g1 = c["design16"], c[f"champion{ex.SUBJECT}"]
    lay = layout(cfg, ex.MODE)
    for group in stage5c.GENE_GROUPS:
        sl = getattr(lay, group)
        give, take = c[f"give {group}"], c[f"take {group}"]
        assert np.array_equal(give[sl], g1[sl]) and np.array_equal(take[sl], g0[sl])
        rest = np.ones(g0.size, dtype=bool)
        rest[sl] = False
        assert np.array_equal(give[rest], g0[rest]) and np.array_equal(take[rest], g1[rest])
    assert np.allclose(c["line 0.5"], 0.5 * (g0 + g1), atol=1e-9)
    assert np.allclose(ex.displacement(cfg, g0, g0), 0.0)


def test_an_onset_keeps_the_idle_ticks_before_its_run():
    t = ex.GapTracker(1)
    z, one = np.zeros(1), np.ones(1, dtype=np.int64)
    pattern = [1, 1, 1, 0, 0, 1, 1, 1, 1] + [0] * 12 + [1, 1, 1]
    for r in pattern:
        t.step(np.array([bool(r)]), one, z, z)
    t.finish()
    assert len(t.onsets) == 3 and t.onset_gaps[1:] == [2, 12] and t.onset_gaps[0] >= ex.RESUME_GAP


def test_quick_probe_end_to_end(tmp_path):
    result = ex.main(["--quick", "--out", str(tmp_path)])
    assert [p["number"] for p in result["predictions"]] == [1, 2, 3, 4, 5]
    assert len(result["cosines"]) == 3 and "give core_w" in result["cells"]
    for name in ("cells.csv", "per_start.csv", "budget.csv", "runs.csv", "open_loop.csv", "summary.json", "manifest.json"):
        assert (tmp_path / name).exists()
