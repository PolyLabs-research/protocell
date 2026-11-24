"""Set this checkout up on another machine for the searches, and measure it there (docs/prereg/fast.md).
Windows, Linux or macOS; it needs only Python 3.11 or later, and uses nothing outside Python's own library.

    python laptop.py                 # set up .venv, test the compiled life, time the CPU, and the GPU if there is one
    python laptop.py --workers 6     # the processes to time a generation on (default: the physical cores)
    python laptop.py --no-gpu        # leave the GPU out

It installs into .venv beside this file and writes its timings under docs/data/fast/ (speed-<name>/, and gpu-<name>/
and speed-<name>-gpu/ when there is a GPU). It starts no search. An all-core run heats a laptop: mains power, and room
under it for air.
"""

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NEED = (3, 11)
TESTS = ("tests/test_fast.py", "tests/test_fastcheck.py")
SHOWN = ("gpu", "one_core_ratio", "compiled_us_a_cell_tick", "workers", "device", "generation_seconds", "largest_early_position_difference",
         "pooled_difference", "largest_pair_difference")


def too_old(version=None):
    """What to tell a Python older than the project needs, or None when it will do."""
    version = sys.version_info if version is None else version
    if tuple(version[:2]) >= NEED:
        return None
    lines = ["!! this needs Python %d.%d or later, and this one is %d.%d." % (NEED + tuple(version[:2]))]
    if shutil.which("conda"):
        lines += ["   With conda:", "       conda create -n protocell python=3.11 -y", "       conda activate protocell", "       python laptop.py"]
    elif shutil.which("uv"):
        lines += ["   With uv:", "       uv run --no-project --python 3.11 laptop.py"]
    else:
        lines += ["   Install Python 3.11 or later (python.org, or uv: https://docs.astral.sh/uv/) and run this again with it."]
    return "\n".join(lines)


def venv_python(root=ROOT, windows=None):
    """The environment's own Python: Windows keeps it in Scripts, the others in bin."""
    windows = (os.name == "nt") if windows is None else windows
    return root / ".venv" / ("Scripts" if windows else "bin") / ("python.exe" if windows else "python")


def _count(cmd):
    """The number a command prints (the sum, if it prints one a processor)."""
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.TimeoutExpired):
        return 0
    found = re.findall(r"\d+", out)
    return sum(int(x) for x in found) if found else 0


def physical_cores():
    """The machine's physical cores: what a generation is best spread over. Half the logical ones if nothing says."""
    system = platform.system()
    n = 0
    if system == "Linux":
        try:
            pairs = set()
            block = {}
            for line in Path("/proc/cpuinfo").read_text().splitlines() + [""]:
                if ":" in line:
                    k, v = line.split(":", 1)
                    block[k.strip()] = v.strip()
                elif block:
                    pairs.add((block.get("physical id", "0"), block.get("core id", block.get("processor", "0"))))
                    block = {}
            n = len(pairs)
        except OSError:
            n = 0
    elif system == "Windows":
        n = _count(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor | Measure-Object -Property NumberOfCores -Sum).Sum"])
    elif system == "Darwin":
        n = _count(["sysctl", "-n", "hw.physicalcpu"])
    return n if n >= 1 else max(1, (os.cpu_count() or 2) // 2)


def nvidia_gpu():
    """The Nvidia GPU's name, memory and driver as nvidia-smi gives them, or None."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        done = subprocess.run([exe, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    line = done.stdout.strip().splitlines()[0] if done.returncode == 0 and done.stdout.strip() else None
    return line


def run(cmd, check=True):
    """One step, shown as it would be typed, its output passed straight through."""
    print("   > " + " ".join(str(c) for c in cmd), flush=True)
    done = subprocess.run([str(c) for c in cmd], cwd=str(ROOT))
    if check and done.returncode != 0:
        raise SystemExit("!! that step failed (exit %d): what it printed above says why" % done.returncode)
    return done.returncode == 0


def make_environment(py):
    if py.exists():
        return
    uv = shutil.which("uv")
    if uv:
        run([uv, "venv", "--python", sys.executable, ".venv"])
    else:
        run([sys.executable, "-m", "venv", ".venv"])


def install(py, extras, check=True):
    uv = shutil.which("uv")
    if uv:
        return run([uv, "pip", "install", "--python", py, "-e", ".[%s]" % extras], check=check)
    return run([py, "-m", "pip", "install", "-e", ".[%s]" % extras], check=check)


def machine_name():
    name = re.sub(r"[^A-Za-z0-9_-]+", "-", platform.node().split(".")[0]).strip("-")
    return name or "machine"


def show(name):
    print("== done. The numbers, from docs/data/fast/*-%s*/summary.json:" % name, flush=True)
    for path in sorted((ROOT / "docs" / "data" / "fast").glob("*-%s*/summary.json" % name)):
        summary = json.loads(path.read_text())
        print("   " + path.parent.name, flush=True)
        for key in SHOWN:
            if key in summary:
                print("      %s: %s" % (key, summary[key]), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--workers", type=int, default=None, help="the processes to time a generation on (default: the physical cores)")
    parser.add_argument("--no-gpu", action="store_true", help="leave the GPU out")
    parser.add_argument("--name", default=None, help="a name for this machine in the output's directories (default: its host name)")
    args = parser.parse_args(argv)
    message = too_old()
    if message:
        print(message, flush=True)
        return 1
    name = args.name or machine_name()
    cores = physical_cores()
    workers = args.workers or cores
    gpu = None if args.no_gpu else nvidia_gpu()
    print("== %s: %s, %s; %d physical cores; timing on %d processes; Nvidia GPU: %s" % (
        name, platform.system(), platform.processor() or platform.machine(), cores, workers, gpu or "none found"), flush=True)

    py = venv_python()
    make_environment(py)
    if gpu and not install(py, "dev,gpu", check=False):
        print("!! the GPU's packages did not install: going on with the CPU alone", flush=True)
        gpu = None
    if not gpu:
        install(py, "dev,fast")
    run([py, "-c", "import sys, numpy, numba; print('python', sys.version.split()[0], 'numpy', numpy.__version__, 'numba', numba.__version__)"])

    print("== the compiled life's tests (about a minute)", flush=True)
    run([py, "-m", "pytest", "-q", *TESTS])

    print("== the CPU: one core, then a generation on %d processes" % workers, flush=True)
    run([py, "-m", "experiments.fastcheck", "--part", "speed", "--workers", workers, "--tag", name])

    if gpu:
        print("== the GPU's kernel beside the CPU's (a few minutes), then a generation on the GPU", flush=True)
        if run([py, "-m", "experiments.fastcheck", "--part", "gpu", "--tag", name], check=False):
            run([py, "-m", "experiments.fastcheck", "--part", "speed", "--device", "cuda", "--tag", name + "-gpu"], check=False)
        else:
            print("!! the GPU part did not run: the CPU's numbers above still stand", flush=True)
    show(name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
