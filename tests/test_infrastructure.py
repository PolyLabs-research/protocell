"""The determinism infrastructure (docs/determinism.md): the thread pin, the named streams, the manifest."""

from __future__ import annotations

import json
import os

import protocell  # noqa: F401  # pins the threads
from protocell.manifest import build_manifest, finish_manifest, git_state, write_manifest
from protocell.rng import stream


def test_importing_the_package_pins_one_blas_thread() -> None:
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        assert os.environ.get(name) is not None


def test_streams_are_reproducible_and_independent_by_name() -> None:
    a1, a2 = stream(7, "sensors").normal(size=5), stream(7, "sensors").normal(size=5)
    assert (a1 == a2).all()
    assert not (stream(7, "motion").normal(size=5) == a1).any()
    assert not (stream(8, "sensors").normal(size=5) == a1).any()
    # the draws of one stream do not depend on whether another was drawn from first
    s = stream(7, "motion")
    s.normal(size=100)
    assert (stream(7, "sensors").normal(size=5) == a1).all()


def test_streams_are_pinned_across_versions() -> None:
    # recorded with numpy 2.4.6: if numpy or the derivation changes these bits, every recorded run changes with them
    assert stream(1, "starts").integers(0, 2**31, size=3).tolist() == [645250620, 888581300, 1248278705]
    assert stream(1, "sensors").normal() == 1.0552741608403278


def test_the_manifest_records_code_platform_and_timing(tmp_path) -> None:
    m = build_manifest(protocol="test", settings={"a": 1}, seeds=[1, 2])
    finish_manifest(m, wall_seconds=1.5, ticks=10)
    write_manifest(tmp_path / "manifest.json", m)
    back = json.loads((tmp_path / "manifest.json").read_text())
    assert back["seeds"] == [1, 2] and back["timing"] == {"wall_seconds": 1.5, "ticks": 10}
    assert back["platform"]["numpy"] and set(git_state()) == {"sha", "branch", "dirty"}
