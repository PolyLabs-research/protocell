"""The CPU pod launcher (cloud/cpu_pod.py): what it asks RunPod for. Skipped where the chess repo's lifecycle library
is absent (CI)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

CHESS_SRC = Path("~/Documents/dev/chess/src/tinyalphazero/cloud.py").expanduser()
pytestmark = pytest.mark.skipif(not CHESS_SRC.exists(), reason="the RunPod lifecycle library lives in the chess repo, absent here")


def _load():
    spec = importlib.util.spec_from_file_location("cpu_pod", Path(__file__).resolve().parent.parent / "cloud" / "cpu_pod.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_cpu_pod_is_asked_for_as_the_lifecycle_requires() -> None:
    m = _load()
    b = m.body("protocell-pilot", 1_900_000_000, "cpu5c", 32, 20)
    # RunPod's REST v2 request (v1 was retired): the fields its schema names, and no others
    assert set(b) == {"name", "image", "cloud", "cpu", "disk", "ports", "startSsh", "cmd", "env"}
    assert b["name"] == "taz-protocell-pilot-dl1900000000" and b["cpu"] == {"id": "cpu5c", "vcpuCount": 32} and b["cloud"] == "SECURE"
    assert b["image"] == m.CPU_IMAGE and b["disk"] == 20 and b["startSsh"] is True and b["env"]["TAZ_DEADLINE"] == "1900000000"
    assert "TAZ_DEADLINE" in " ".join(b["cmd"]) and b["cmd"][-1].endswith("exec /start.sh") and "api.runpod.io/v2" in " ".join(b["cmd"])
    job = (Path(__file__).resolve().parent.parent / "cloud" / "pod_job.sh").read_text()
    assert "api.runpod.io/v2/pods/$POD_ID" in job and "rest.runpod.io" not in job  # the pod's own delete call
    with pytest.raises(m.cloud.CloudError):  # v2 takes a power of two
        m.body("protocell-pilot", 1_900_000_000, "cpu5c", 24, 20)
    assert m.listed_rate(0.07, 32) == pytest.approx(1.12)  # the pilot's pod billed $1.12/h
    with pytest.raises(m.cloud.CloudError):
        m.body("protocell-pilot", 1_900_000_000, "cpu9x", 32, 20)


def test_only_protocell_tags_launch() -> None:
    m = _load()
    with pytest.raises(SystemExit):
        m.main(["launch", "--tag", "p2n", "--hours", "1", "--max-rate", "1"])
