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


def test_the_follow_up_part(tmp_path):
    s = fastcheck.main(["--part", "follow", "--quick", "--out", str(tmp_path)])
    assert s["starts"] == 8 and s["world"] == "spot" and s["cell"] == "champion6402" and s["F1"] and s["F2"]
    assert set(s["compiled"]) == set(s["strict"]) and [p["number"] for p in s["predictions"]] == [1, 2]
    assert (tmp_path / "follow" / "lives.csv").read_text().count("\n") == 9
    assert fastcheck.FOLLOW_SEED not in (fastcheck.SEED, fastcheck.BOOTSTRAP_SEED, *fastcheck.LUCK_SEEDS)


def test_the_sign_test():
    assert fastcheck.sign_test(0, 0) == 1.0 and fastcheck.sign_test(5, 5) == 1.0
    assert fastcheck.sign_test(9, 17) == pytest.approx(0.1686, abs=1e-3)  # B's one pair
    assert fastcheck.sign_test(0, 10) == pytest.approx(2 / 1024) and fastcheck.sign_test(10, 0) == fastcheck.sign_test(0, 10)


def test_the_gpu_part_runs_in_numbas_simulator(tmp_path):
    """The part meant for a machine with a GPU, on Numba's simulator (the kernel as plain Python): its plumbing."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    env = {**os.environ, "NUMBA_ENABLE_CUDASIM": "1", "PYTHONPATH": str(root)}
    done = subprocess.run([sys.executable, "-m", "experiments.fastcheck", "--part", "gpu", "--quick", "--starts", "1", "--out", str(tmp_path)],
                          capture_output=True, text=True, env=env, cwd=root)
    assert done.returncode == 0, done.stdout[-400:] + done.stderr[-1200:]
    s = json.loads((tmp_path / "gpu" / "summary.json").read_text())
    assert s["lives"] == 12 and s["largest_early_position_difference"] == 0.0 and s["pooled_difference"] == 0.0  # the simulator is the CPU


def test_the_gpu_part_needs_a_gpu(tmp_path):
    from protocell import fast

    if fast.cuda_ready()[0]:
        pytest.skip("this machine has a GPU")
    with pytest.raises(SystemExit, match="no GPU"):
        fastcheck.main(["--part", "gpu", "--quick", "--out", str(tmp_path)])


def test_the_agreement_part_in_single_precision(tmp_path):
    s = fastcheck.main(["--part", "agree", "--precision", "single", "--quick", "--out", str(tmp_path)])
    assert s["precision"] == "single" and s["pairs"] == 12 and s["lives"] == 72 and len(s["predictions"]) == 4
    assert {"S1", "S2", "S3", "S4", "S5"} <= set(s) and s["S1"] and s["S3"]
    assert (tmp_path / "agree-single" / "summary.json").exists() and not (tmp_path / "agree").exists()
    with pytest.raises(SystemExit):
        fastcheck.main(["--part", "same", "--precision", "single", "--quick", "--out", str(tmp_path)])
