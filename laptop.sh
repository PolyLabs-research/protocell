#!/usr/bin/env bash
# Set this checkout up on another machine for the searches, and measure it there (docs/prereg/fast.md).
#
#   bash laptop.sh                 # set up, test the compiled life, time the CPU, and the GPU if there is one
#   WORKERS=6 bash laptop.sh       # the processes to time a generation on (default: the physical cores)
#   GPU=0 bash laptop.sh           # leave the GPU out
#
# It installs into .venv beside this file and writes its timings under docs/data/fast/ (speed-<name>/, and gpu-<name>/
# and speed-<name>-gpu/ when there is a GPU). It starts no search. An all-core run heats a laptop: mains power, and
# room under it for air.
set -euo pipefail
cd "$(dirname "$0")"

NAME="${NAME:-$(hostname -s 2>/dev/null || echo machine)}"
CORES="$(lscpu -p=core,socket 2>/dev/null | grep -v '^#' | sort -u | wc -l || true)"
[ "${CORES:-0}" -ge 1 ] || CORES="$(getconf _NPROCESSORS_ONLN)"
WORKERS="${WORKERS:-$CORES}"

HAS_GPU=0
if [ "${GPU:-1}" != "0" ] && command -v nvidia-smi >/dev/null 2>&1; then
    if nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null; then HAS_GPU=1; fi
fi
echo "== $NAME: $(lscpu 2>/dev/null | sed -n 's/^Model name: *//p' | head -1); $CORES physical cores; timing on $WORKERS processes; GPU: $HAS_GPU"

if [ ! -x .venv/bin/python ]; then
    if command -v uv >/dev/null 2>&1; then
        uv venv --python 3.11 .venv
    elif python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
        python3 -m venv .venv
    else
        echo "!! this needs Python 3.11 or later, and this machine's python3 is older. Install uv (https://docs.astral.sh/uv/), which fetches one, and run this again."
        exit 1
    fi
fi
install() {
    if command -v uv >/dev/null 2>&1; then
        uv pip install --python .venv/bin/python -e ".[$1]"
    else
        .venv/bin/python -m pip install --upgrade pip && .venv/bin/python -m pip install -e ".[$1]"
    fi
}
if [ "$HAS_GPU" = 1 ]; then
    install "dev,gpu" || { echo "!! the GPU's packages did not install: going on with the CPU alone"; HAS_GPU=0; install "dev,fast"; }
else
    install "dev,fast"
fi
PY=.venv/bin/python
$PY -c "import sys, numpy, numba; print('python', sys.version.split()[0], 'numpy', numpy.__version__, 'numba', numba.__version__)"

echo "== the compiled life's tests (about a minute)"
$PY -m pytest -q tests/test_fast.py tests/test_fastcheck.py

echo "== the CPU: one core, then a generation on $WORKERS processes"
$PY -m experiments.fastcheck --part speed --workers "$WORKERS" --tag "$NAME"

if [ "$HAS_GPU" = 1 ]; then
    echo "== the GPU's kernel beside the CPU's (a few minutes), then a generation on the GPU"
    if $PY -m experiments.fastcheck --part gpu --tag "$NAME"; then
        $PY -m experiments.fastcheck --part speed --device cuda --tag "$NAME-gpu"
    else
        echo "!! the GPU part did not run: the CPU's numbers above still stand"
    fi
fi

echo "== done. The numbers are in docs/data/fast/*-$NAME*/summary.json:"
for f in docs/data/fast/*-"$NAME"*/summary.json; do
    [ -f "$f" ] && echo "$f" && $PY - "$f" <<'EOF'
import json, sys
s = json.load(open(sys.argv[1]))
for k in ("gpu", "one_core_ratio", "compiled_us_a_cell_tick", "workers", "device", "generation_seconds", "largest_early_position_difference",
          "pooled_difference", "largest_pair_difference"):
    if k in s:
        print(f"   {k}: {s[k]}")
EOF
done
