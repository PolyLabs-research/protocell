"""Stage 5c's design probe: the neighbours are drawn as the searches draw, and the probe runs end to end."""

import numpy as np

from experiments import stage4e, stage5b, stage5c_probe
from protocell.cell import genome_ranges


def _seed():
    cfg = stage5b.world(True)
    design = stage4e.load(stage5c_probe.SEED_DESIGN)
    return cfg, design["mode"], stage4e.genome(cfg, design)


def test_neighbours_stay_in_range_and_scale_with_sigma():
    cfg, mode, g0 = _seed()
    lo, hi = genome_ranges(cfg, mode)
    near = stage5c_probe.neighbours(cfg, mode, g0, 0.002, 16, 0)
    far = stage5c_probe.neighbours(cfg, mode, g0, 0.05, 16, 4)
    for g in (near, far):
        assert g.shape == (16, g0.shape[0])
        assert np.all(g >= lo - 1e-12) and np.all(g <= hi + 1e-12)
    step = lambda g: np.abs((g - g0) / (hi - lo)).mean()  # noqa: E731
    assert step(near) < 0.004 < step(far)


def test_neighbours_are_the_same_bits_twice():
    cfg, mode, g0 = _seed()
    a = stage5c_probe.neighbours(cfg, mode, g0, 0.01, 8, 2)
    b = stage5c_probe.neighbours(cfg, mode, g0, 0.01, 8, 2)
    assert np.array_equal(a, b)


def test_quick_probe_end_to_end(tmp_path):
    result = stage5c_probe.main(["--quick", "--out", str(tmp_path)])
    assert set(result["references"]) == {"design 16", "B8", "B0"}
    assert len(result["ladder"]) == 2
    for name in ("neighbours.csv", "summary.csv", "summary.json", "manifest.json"):
        assert (tmp_path / name).exists()
