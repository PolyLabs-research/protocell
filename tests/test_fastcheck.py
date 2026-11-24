"""The compiled life's check (experiments/fastcheck.py): its parts run at the smoke test's size and say what they found."""

import json

import numpy as np
import pytest

pytest.importorskip("numba")

from experiments import fastcheck  # noqa: E402


def test_the_worlds_are_what_a_stage_8_run_meets():
    w = fastcheck.worlds(True)
    assert list(w) == ["home", "flicker", "spot", "shaded", "path 25", "path 75"]
    assert 0.3 < w["path 25"].shade_floor < 1.0 and w["path 25"].eta > w["home"].eta  # part shaded, the cave's gain
    assert w["path 75"].shade_floor == 1.0 and w["home"].eta < w["path 75"].eta < w["path 25"].eta  # translucent, the gain falling
    assert all(c.sensing == "relative" for c in w.values())


def test_under_the_c_librarys_maths_numpy_is_put_back():
    before = np.exp
    with fastcheck.c_library_maths():
        assert np.exp is not before and float(np.exp(np.array([1.0]))[0]) == pytest.approx(2.718281828459045)
    assert np.exp is before


def test_the_same_model_part(tmp_path):
    s = fastcheck.main(["--part", "same", "--quick", "--out", str(tmp_path)])
    assert s["A"] and s["identical"] == s["lives"] == 24
    assert json.loads((tmp_path / "same" / "summary.json").read_text())["A"] is True
    assert (tmp_path / "same" / "manifest.json").exists() and (tmp_path / "same" / "lives.csv").read_text().count("\n") == 25


def test_the_agreement_part(tmp_path):
    s = fastcheck.main(["--part", "agree", "--quick", "--out", str(tmp_path)])
    assert s["pairs"] == 12 and s["lives"] == 72 and len(s["ranking"]) == 4 and len(s["predictions"]) == 4
    assert s["B1"] and s["B3"]  # short lives barely part
    assert all(abs(r["spearman"]) <= 1.0 + 1e-9 and abs(r["step_cosine"]) <= 1.0 + 1e-9 for r in s["ranking"])
    scores = np.load(tmp_path / "agree" / "ranking_scores.npz")
    assert scores["reference_52"].shape == scores["compiled_53"].shape == (8, 4)


def test_the_ranking_measures():
    a = np.array([0.1, 0.5, 0.3, 0.9])
    assert fastcheck.spearman(a, a * 2 + 1) == pytest.approx(1.0) and fastcheck.spearman(a, -a) == pytest.approx(-1.0)
    genomes = np.arange(8.0).reshape(4, 2)
    assert fastcheck.cosine(fastcheck.step(genomes, a), fastcheck.step(genomes, a + 1.0)) == pytest.approx(1.0)
    assert fastcheck.cosine(fastcheck.step(genomes, a), fastcheck.step(genomes, -a)) == pytest.approx(-1.0)


def test_the_speed_part(tmp_path):
    s = fastcheck.main(["--part", "speed", "--quick", "--workers", "1", "--tag", "here", "--out", str(tmp_path)])
    assert s["one_core_ratio"] > 1.0 and s["generation_lives"] == 32 and s["generation_seconds"] > 0.0
    assert (tmp_path / "speed-here" / "summary.json").exists()


def test_the_gpu_part_needs_a_gpu(tmp_path):
    from protocell import fast

    if fast.cuda_ready()[0]:
        pytest.skip("this machine has a GPU")
    with pytest.raises(SystemExit, match="no GPU"):
        fastcheck.main(["--part", "gpu", "--quick", "--out", str(tmp_path)])
