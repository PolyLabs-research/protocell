#!/bin/bash
# Launch a CPU pod and start stage 1 runs on it with no idle gap: launch at the owner's confirmed ceiling, wait for
# SSH, stage this commit, start the runs under the job guard, start the pull campaign. Started detached, so it does
# not depend on the session that started it:
#
#   setsid nohup bash cloud/launch_phase.sh TAG HOURS MAX_RATE PHASE MODE:REPLICATE [MODE:REPLICATE ...] \
#       > ~/protocell-runs/launch-TAG.log 2>&1 < /dev/null &
#   e.g. TAG protocell-confirm-a, HOURS 3, MAX_RATE 1.12, PHASE confirm, runs uniform:1 fourier1:1
#
# The pod's deadline (HOURS from the launch) and the sweeper cap everything if any step fails; a failed step after
# the launch terminates the pod at once. The owner confirms the flavour, MAX_RATE, HOURS and the worst cost first.
set -u
TAG=$1
HOURS=$2
MAX_RATE=$3
PHASE=$4
shift 4
RUNS=("$@")
PULL_WAIT=${PULL_WAIT:-3600}
EXPERIMENT=${EXPERIMENT:-stage1}  # the stage's module: stage1, stage3b
WORKERS=${WORKERS:-16}
VCPU=${VCPU:-32}  # 16 for one run alone on a smaller pod, at half the rate
FLAVOR=${FLAVOR:-cpu5c}  # cpu3c when no cpu5c is free (older, slower CPUs, cheaper)
REPO=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO" || exit 1
CHESS=$HOME/Documents/dev/chess
RP=("$CHESS/.venv/bin/python" "$CHESS/scripts/runpod_pod.py")
PY=$REPO/.venv/bin/python
say() { echo "$(date -Is) $*"; }

names=()
for run in "${RUNS[@]}"; do
    names+=("$("$PY" -c "from experiments.$EXPERIMENT import seed_for; m, r = '$run'.split(':'); print(f'{m}-{seed_for(\"$PHASE\", m, int(r))}')")")
done
say "launch $TAG: $EXPERIMENT $PHASE ${RUNS[*]} -> ${names[*]}; ${HOURS} h cap at most \$${MAX_RATE}/h"
out=$("$PY" cloud/cpu_pod.py launch --tag "$TAG" --flavor "$FLAVOR" --vcpu "$VCPU" --hours "$HOURS" --max-rate "$MAX_RATE" --yes 2>&1)
echo "$out"
POD=$(echo "$out" | sed -n 's/^launched \([a-z0-9]*\) .*/\1/p')
if [ -z "$POD" ]; then
    say "no pod launched; stopping"
    exit 1
fi
fail() {
    say "FAILED: $*; terminating $POD"
    "${RP[@]}" terminate "$POD"
    notify-send -u critical "protocell $TAG" "launch failed: $*" 2> /dev/null || true
    exit 1
}
"${RP[@]}" wait-ssh "$POD" --timeout 900 || fail "no SSH"
bash cloud/stage_pod.sh "$POD" || fail "staging"
# RESUME=1: carry each run's checkpoint from this box, so its runs go on from where an earlier pod stopped.
if [ "${RESUME:-0}" = 1 ]; then
    for name in "${names[@]}"; do
        ckpt=docs/data/$EXPERIMENT/$PHASE/$name/checkpoint.npz
        [ -s "$ckpt" ] || fail "no checkpoint at $ckpt"
        "${RP[@]}" ssh "$POD" -- mkdir -p "/root/protocell/$(dirname "$ckpt")" || fail "making the folder for $ckpt"
        "${RP[@]}" push "$POD" "$ckpt" "/root/protocell/$ckpt" || fail "pushing $ckpt"
    done
fi
# Start the job detached on the pod; the local ssh is cut after 30 s (the job is setsid and nohup there, so it lives on).
timeout 30 "${RP[@]}" ssh "$POD" -- "cd /root/protocell && EXPERIMENT=$EXPERIMENT nohup setsid bash /root/pc/pod_job.sh /root/protocell/pc-job $PULL_WAIT -- bash /root/protocell/cloud/run_phase.sh $PHASE $WORKERS ${RUNS[*]} > /dev/null 2>&1 < /dev/null &" > /dev/null 2>&1
sleep 20
"${RP[@]}" ssh "$POD" -- "grep -q 'job start' /root/protocell/pc-job/lifecycle.log" || fail "the job did not start"
say "job started on $POD"
EXPERIMENT=$EXPERIMENT setsid nohup bash cloud/campaign.sh "$POD" "$PHASE" "${names[@]}" > /dev/null 2>&1 < /dev/null &
say "campaign started for $POD (log ~/protocell-runs/campaign-$EXPERIMENT-$PHASE-$POD.log)"
