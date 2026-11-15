#!/bin/bash
# Pull a pod's stage 1 phase back to this box while it runs, and close the pod's job when it is done. Started detached,
# so it outlives the session that started it (the chess project's remote_campaign.sh pattern):
#
#   setsid nohup bash cloud/campaign.sh POD_ID PHASE RUN [RUN ...] > /dev/null 2>&1 < /dev/null &
#   setsid nohup bash cloud/campaign.sh y5zj5soqt71qpg pilot uniform-1001 fourier1-1002 > /dev/null 2>&1 < /dev/null &
#
# Every PULL_EVERY seconds (default 600): pull docs/data/stage1/PHASE/ into this repo, and the pod's logs and job
# record into ~/protocell-runs/. When the pod's job marks DONE: pull again, check that every RUN has its champion.json
# and manifest.json, then write PULLED on the pod (its job then deletes it). If a run's outputs are missing, PULLED is
# not written, so the pod waits out its pull wait (or its deadline) for them to be fetched by hand. The pod's deadline
# and the sweeper cap everything if this box is down. Log: ~/protocell-runs/campaign-PHASE-POD.log.
set -u
POD=$1
PHASE=$2
shift 2
RUNS=("$@")
PULL_EVERY=${PULL_EVERY:-600}
EXPERIMENT=${EXPERIMENT:-stage1}  # the data's folder under docs/data/
REPO=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO" || exit 1
CHESS=$HOME/Documents/dev/chess
RP=("$CHESS/.venv/bin/python" "$CHESS/scripts/runpod_pod.py")
OUT=$HOME/protocell-runs
LOG=$OUT/campaign-$EXPERIMENT-$PHASE-$POD.log
mkdir -p "$OUT" "docs/data/$EXPERIMENT/$PHASE"

log() { echo "$(date -Is) $*" >> "$LOG"; }

pull_all() {
    "${RP[@]}" pull "$POD" "/root/protocell/docs/data/$EXPERIMENT/$PHASE/" "docs/data/$EXPERIMENT/$PHASE/" >> "$LOG" 2>&1
    "${RP[@]}" pull "$POD" /root/protocell/logs/ "$OUT/$EXPERIMENT-$PHASE-logs/" >> "$LOG" 2>&1
    "${RP[@]}" pull "$POD" /root/protocell/pc-job/ "$OUT/$EXPERIMENT-$PHASE-$POD-job/" >> "$LOG" 2>&1
}

# One failed status call is not a missing pod: the API can fail for a moment (it ended stage 4b's pilot campaign while the
# pod ran on). Three misses in a row, 30 s apart, are.
pod_alive() {
    for _ in 1 2 3; do
        "${RP[@]}" status 2> /dev/null | grep -q "^$POD " && return 0
        log "the pod was not listed; asking again"
        sleep 30
    done
    return 1
}

log "campaign start: pod $POD phase $PHASE runs ${RUNS[*]}, pulling every ${PULL_EVERY}s"
while pod_alive; do
    if "${RP[@]}" ssh "$POD" -- test -e /root/protocell/pc-job/DONE 2> /dev/null; then
        log "the pod's job is DONE; final pull"
        pull_all
        missing=0
        for run in "${RUNS[@]}"; do
            for f in champion.json manifest.json; do
                [ -s "docs/data/$EXPERIMENT/$PHASE/$run/$f" ] || { log "MISSING docs/data/$EXPERIMENT/$PHASE/$run/$f"; missing=1; }
            done
        done
        if [ "$missing" = 0 ]; then
            marked=0  # a refused call (the API's rate limit) must not pass for a written mark: the pod would wait out its hour
            for _ in 1 2 3 4 5 6; do
                if "${RP[@]}" ssh "$POD" -- touch /root/protocell/pc-job/PULLED >> "$LOG" 2>&1; then marked=1; break; fi
                sleep 40
            done
            if [ "$marked" = 1 ]; then
                log "every run pulled; PULLED written; the pod deletes itself"
            else
                log "every run pulled; PULLED COULD NOT BE WRITTEN: terminating the pod from here"
                "${RP[@]}" terminate "$POD" >> "$LOG" 2>&1 || log "TERMINATE FAILED for $POD: terminate it by hand"
            fi
            notify-send "protocell $EXPERIMENT $PHASE" "pulled; the pod deletes itself" 2> /dev/null || true
        else
            log "outputs missing: PULLED NOT written; fetch by hand before the pod's pull wait or deadline"
            notify-send -u critical "protocell $EXPERIMENT $PHASE" "outputs missing on $POD" 2> /dev/null || true
        fi
        exit "$missing"
    fi
    pull_all
    log "pulled ($(du -sh "docs/data/$EXPERIMENT/$PHASE" | cut -f1))"
    sleep "$PULL_EVERY"
done
log "the pod is gone"
