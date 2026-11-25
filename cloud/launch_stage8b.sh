#!/bin/bash
# Launch a CPU pod and make stage 8b runs on it, one after another, on the compiled life (docs/prereg/stage8b.md):
# launch at the owner's confirmed ceiling, wait for SSH, ask the host its speed, stage this commit, start the runs under
# the job guard, start the pull campaign. Started detached, so it does not depend on the session that started it:
#
#   setsid nohup bash cloud/launch_stage8b.sh TAG HOURS MAX_RATE PHASE:REPLICATE [PHASE:REPLICATE ...] \
#       > ~/protocell-runs/launch-TAG.log 2>&1 < /dev/null &
#   e.g. TAG protocell-s8b-1, HOURS 3.6, MAX_RATE 0.56, runs extend:1 fresh:1 fresh:6
#
# The pod's deadline (HOURS from the launch) and the sweeper cap everything if any step fails; a failed step after the
# launch terminates the pod. The owner confirms the flavour, MAX_RATE, HOURS and the worst cost first. Steps that ask
# RunPod's API are tried again when refused: its rate limit is shared with every other pod's polling.
set -u
TAG=$1
HOURS=$2
MAX_RATE=$3
shift 3
RUNS=("$@")
PULL_WAIT=${PULL_WAIT:-3600}
WORKERS=${WORKERS:-16}
VCPU=${VCPU:-16}
FLAVOR=${FLAVOR:-cpu5c}
SLOWEST=${SLOWEST:-0.6}  # the speed gate's seconds: this box takes about 0.24
POD_TESTS=${POD_TESTS:-tests/test_fast.py tests/test_fastcheck.py tests/test_stage8b.py}
REPO=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO" || exit 1
CHESS=$HOME/Documents/dev/chess
RP=("$CHESS/.venv/bin/python" "$CHESS/scripts/runpod_pod.py")
PY=$REPO/.venv/bin/python
say() { echo "$(date -Is) $*"; }
try() {
    for i in 1 2 3 4 5; do
        "$@" && return 0
        say "retry $i: $*"
        sleep $((40 + RANDOM % 30))
    done
    return 1
}

names=()
for run in "${RUNS[@]}"; do
    name=$("$PY" -c "from experiments.stage8b import MODE, seed_for; p, r = '$run'.split(':'); print(f'{p}/{MODE}-{seed_for(p, int(r))}')") || exit 1
    names+=("$name")
done
say "launch $TAG: stage8b ${RUNS[*]} -> ${names[*]}; ${HOURS} h cap at most \$${MAX_RATE}/h"
out=$("$PY" cloud/cpu_pod.py launch --tag "$TAG" --flavor "$FLAVOR" --vcpu "$VCPU" --hours "$HOURS" --max-rate "$MAX_RATE" --yes 2>&1)
echo "$out"
POD=$(echo "$out" | sed -n 's/^launched \([a-z0-9]*\) .*/\1/p')
if [ -z "$POD" ]; then
    say "no pod launched; stopping"
    exit 1
fi
fail() {
    say "FAILED: $*; terminating $POD"
    try "${RP[@]}" terminate "$POD" || say "TERMINATE FAILED for $POD: its deadline and the sweeper remain; terminate it by hand"
    notify-send -u critical "protocell $TAG" "launch failed: $*" 2> /dev/null || true
    exit 1
}
try "${RP[@]}" wait-ssh "$POD" --timeout 900 || fail "no SSH"
try "${RP[@]}" ssh "$POD" -- mkdir -p /root/pc || fail "no folder for the scripts"
try "${RP[@]}" push "$POD" cloud/speed_gate.py /root/pc/speed_gate.py || fail "pushing the speed gate"
speed=$("${RP[@]}" ssh "$POD" -- python3 /root/pc/speed_gate.py 2> /dev/null | tail -1)
say "the host's speed gate: ${speed:-none} s (this box about 0.24; at most $SLOWEST)"
awk -v t="${speed:-99}" -v most="$SLOWEST" 'BEGIN { exit !(t + 0 > 0 && t + 0 <= most) }' || fail "a slow host (${speed:-no answer} s)"
stage() {
    staged=$(POD_TESTS="$POD_TESTS" bash cloud/stage_pod.sh "$POD" 2>&1)
    local status=$?
    echo "$staged"
    return $status
}
try stage || fail "staging"
# Staging prints the pod's tests' last line and does not fail on it: read it here, and run nothing on a pod whose tests did not pass.
echo "$staged" | grep -E '^tests: ' | grep -q ' passed' || fail "the pod's tests did not pass"
if echo "$staged" | grep -E '^tests: ' | grep -q -E 'failed|error'; then fail "the pod's tests failed"; fi
# Start the job detached on the pod; the local ssh is cut after 30 s (the job is setsid and nohup there, so it lives on).
timeout 30 "${RP[@]}" ssh "$POD" -- "cd /root/protocell && ${CHUNK:+CHUNK=$CHUNK }nohup setsid bash /root/pc/pod_job.sh /root/protocell/pc-job $PULL_WAIT -- bash /root/protocell/cloud/run_stage8b.sh $WORKERS ${RUNS[*]} > /dev/null 2>&1 < /dev/null &" > /dev/null 2>&1
sleep 25
try "${RP[@]}" ssh "$POD" -- "grep -q 'job start' /root/protocell/pc-job/lifecycle.log" || fail "the job did not start"
say "job started on $POD"
# The campaign pulls docs/data/stage8b/ whole (its phase is "."), and looks for each run under its own phase's folder.
EXPERIMENT=stage8b PULL_EVERY=${PULL_EVERY:-180} setsid nohup bash cloud/campaign.sh "$POD" . "${names[@]}" > /dev/null 2>&1 < /dev/null &
say "campaign started for $POD (log ~/protocell-runs/campaign-stage8b-.-$POD.log)"
