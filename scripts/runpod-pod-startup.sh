#!/bin/bash
# RunPod pod startup — VIDEO SAMPLE TEMPLATE DISABLED.
# This script exits immediately. No recording, no Telegram, no billing waste.
# To re-enable (explicit user request only): set VIDEO_GENERATION_ENABLED=1 on the pod.

set -euo pipefail

log() { echo "[runpod-startup] $(date -u +%H:%M:%S) $*"; }

POD_ID="${RUNPOD_POD_ID:-unknown}"
log "Pod ${POD_ID}: video sample template DISABLED — exiting immediately"
log "No install, no recording, no Telegram. Pod should terminate via orchestrator."

echo STOPPED > /tmp/runpod_job_status
echo "video template disabled" > /tmp/runpod_job_complete
exit 0
