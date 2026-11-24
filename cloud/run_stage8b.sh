#!/bin/bash
# Stage 8b's runs on a pod, one after another, each with every worker and its own log; exits non-zero if any failed:
#
#   bash cloud/run_stage8b.sh WORKERS PHASE:REPLICATE [PHASE:REPLICATE ...]
#   bash cloud/run_stage8b.sh 16 extend:1 fresh:1 fresh:6
#
# One after another, so a pod that reaches its deadline leaves one run unfinished and not three (a run checkpoints
# every generation and the same command carries it on). CHUNK, when set, is the genomes in a job. Started under
# cloud/pod_job.sh, which marks DONE when this returns, waits for this box to pull, then deletes the pod.
set -u
cd "${PROTOCELL_ROOT:-/root/protocell}" || exit 1
WORKERS=$1
shift
mkdir -p logs
status=0
for run in "$@"; do
    phase=${run%%:*}
    rep=${run##*:}
    # shellcheck disable=SC2086  # the chunk and any extra arguments are separate words when set
    "${PYTHON:-python3}" -W error::RuntimeWarning -m experiments.stage8b --phase "$phase" --replicate "$rep" --workers "$WORKERS" \
        ${CHUNK:+--chunk $CHUNK} ${STAGE8B_EXTRA:-} > "logs/stage8b-$phase-$rep.log" 2>&1 || status=1
done
exit $status
