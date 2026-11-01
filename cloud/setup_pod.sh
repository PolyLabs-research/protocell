#!/bin/bash
# Prepare a fresh CPU pod (runpod/base:1.4.1-ubuntu2404) to run protocell:
#
#   bash setup_pod.sh /root/pc/protocell.bundle BRANCH
#
# Clones the code from a git bundle pushed from this box (the pod never holds GitHub credentials), installs the
# pinned numerical stack, runs the test suite (the platform-pinned hash test skips here, saying why), and prints the
# stack and the CPU quota it ended up on.
set -euo pipefail
# An SSH session does not inherit the container's environment, so adopt pid 1's (RunPod's RUNPOD_* among it).
while IFS= read -r -d '' kv; do export "$kv"; done < /proc/1/environ
BUNDLE=${1:?bundle}
BRANCH=${2:?branch}
cd /root
rm -rf protocell
git clone -q -b "$BRANCH" "$BUNDLE" protocell
cd protocell
if ! python3 -m pip --version > /dev/null 2>&1; then
    DEBIAN_FRONTEND=noninteractive apt-get -qq update
    DEBIAN_FRONTEND=noninteractive apt-get -qq install -y python3-pip > /dev/null
fi
command -v rsync > /dev/null || { DEBIAN_FRONTEND=noninteractive apt-get -qq update; DEBIAN_FRONTEND=noninteractive apt-get -qq install -y rsync > /dev/null; }
# The same numpy as this box's runs (2.4.6); Ubuntu 24.04 marks its Python as externally managed.
python3 -m pip install -q --break-system-packages "numpy==2.4.6" "threadpoolctl==3.7.0" "pytest==8.4.2"
python3 -m pip install -q --break-system-packages --no-deps -e .
quota=$(cat /sys/fs/cgroup/cpu.max 2> /dev/null || echo "$(cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us) $(cat /sys/fs/cgroup/cpu/cpu.cfs_period_us)")
echo "code:  $(git rev-parse --short HEAD) $(git status --porcelain --untracked-files=no | wc -l) dirty"
echo "stack: $(python3 -c 'import protocell, sys, numpy; print(sys.version.split()[0], "numpy", numpy.__version__)')"
echo "cpu:   $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | xargs)  quota '$quota'  RUNPOD_CPU_COUNT=${RUNPOD_CPU_COUNT:-?}"
echo "tests: $(python3 -W error::RuntimeWarning -m pytest -q 2>&1 | tail -1)"
echo "cost:  $(python3 -W error::RuntimeWarning -c 'import protocell; from experiments.stage1_budget import cost; r = cost(48); print(f"{r[\"us_per_tick\"]:.0f} us a tick for 48 cells")')"
