#!/bin/bash
# Make a booted pod ready to run protocell at this checkout's commit:
#
#   bash cloud/stage_pod.sh POD_ID
#   POD_TESTS="tests/test_fast.py tests/test_stage8b.py" bash cloud/stage_pod.sh POD_ID     # only these tests there
#
# Pushes a git bundle of the current branch (the pod never holds GitHub credentials) and the pod scripts, then runs
# cloud/setup_pod.sh there. Refuses a dirty tree: a run's manifest must name a commit that holds its code.
set -euo pipefail
POD=$1
REPO=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    echo "refusing: the tree has uncommitted changes" >&2
    exit 1
fi
BRANCH=$(git rev-parse --abbrev-ref HEAD)
CHESS=$HOME/Documents/dev/chess
RP=("$CHESS/.venv/bin/python" "$CHESS/scripts/runpod_pod.py")
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
git bundle create "$STAGE/protocell.bundle" "$BRANCH" 2> /dev/null
"${RP[@]}" ssh "$POD" -- mkdir -p /root/pc
"${RP[@]}" push "$POD" "$STAGE/protocell.bundle" /root/pc/protocell.bundle
for f in setup_pod.sh pod_job.sh; do "${RP[@]}" push "$POD" "cloud/$f" "/root/pc/$f"; done
# shellcheck disable=SC2086  # POD_TESTS is a list of files
"${RP[@]}" ssh "$POD" -- bash /root/pc/setup_pod.sh /root/pc/protocell.bundle "$BRANCH" ${POD_TESTS:-} 2>&1 | grep -E '^(code|stack|cpu|tests|cost):'
echo "staged $(git rev-parse --short HEAD) on $POD"
