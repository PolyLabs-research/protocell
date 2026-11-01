#!/bin/bash
# Run stage 1's runs side by side on a pod, each with its own log, and exit non-zero if any failed:
#
#   bash cloud/run_phase.sh PHASE WORKERS MODE:REPLICATE [MODE:REPLICATE ...]
#   bash cloud/run_phase.sh pilot 16 uniform:1 fourier1:1
#
# Started under cloud/pod_job.sh, which marks DONE when this returns, waits for this box to pull, then deletes the pod.
set -u
cd /root/protocell
PHASE=$1
WORKERS=$2
shift 2
mkdir -p logs
pids=()
for run in "$@"; do
    mode=${run%%:*}
    rep=${run##*:}
    python3 -W error::RuntimeWarning -m experiments.stage1 --phase "$PHASE" --mode "$mode" --replicate "$rep" --workers "$WORKERS" \
        > "logs/$PHASE-$mode-$rep.log" 2>&1 &
    pids+=($!)
done
status=0
for pid in "${pids[@]}"; do wait "$pid" || status=1; done
exit $status
