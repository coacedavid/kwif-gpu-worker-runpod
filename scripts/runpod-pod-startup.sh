#!/bin/bash
# RunPod GPU pod startup — installs deps, records sample, sends Telegram status.
# Invoked as: curl -fsSL "$RUNPOD_STARTUP_SCRIPT_URL" | bash
# Required env (set by orchestrator on the pod):
#   RUNPOD_WORKER_BUNDLE_URL, TELEGRAM_BOT_TOKEN, TELEGRAM_GROUP_CHAT_ID
# Optional: RECORD_DURATION_SEC (default 30), WIDTH, HEIGHT, FPS

set -euo pipefail

log() { echo "[runpod-startup] $(date -u +%H:%M:%S) $*"; }

tg() {
  local text="$1"
  local token="${TELEGRAM_BOT_TOKEN:-${TELEGRAM_OPS_BOT_TOKEN:-}}"
  local chat="${TELEGRAM_GROUP_CHAT_ID:-${TELEGRAM_OPS_ADMIN_CHAT_ID:-}}"
  [[ -n "$token" && -n "$chat" ]] || return 0
  curl -fsS -X POST "https://api.telegram.org/bot${token}/sendMessage" \
    -d "chat_id=${chat}" \
    --data-urlencode "text=${text}" >/dev/null 2>&1 || true
}

on_err() {
  local line="$1"
  log "FAILED at line ${line}"
  tg "❌ RunPod sample FAILED (line ${line})
Host: $(hostname)
Tail log:
$(tail -n 40 /tmp/record.log 2>/dev/null || echo 'no record.log')"
  echo FAILED > /tmp/runpod_job_status
  exit 1
}
trap 'on_err $LINENO' ERR

export DEBIAN_FRONTEND=noninteractive
POD_ID="${RUNPOD_POD_ID:-unknown}"
DURATION="${RECORD_DURATION_SEC:-30}"

tg "🚀 RunPod GPU sample STARTED
Pod: ${POD_ID}
Duration: ${DURATION}s
Bundle: ${RUNPOD_WORKER_BUNDLE_URL:-missing}"

log "Installing system packages..."
apt-get update -qq
apt-get install -y -qq curl ffmpeg libgl1 libglib2.0-0 > /dev/null

log "Installing Python deps..."
pip install -q numpy opencv-python-headless websockets httpx edge-tts pydantic pydantic-settings python-dotenv aiofiles

REPO_URL="${RUNPOD_WORKER_GIT_URL:-https://github.com/coacedavid/kwif-gpu-worker-runpod.git}"

log "Fetching worker code..."
rm -rf /app
if [[ -n "${RUNPOD_WORKER_BUNDLE_URL:-}" ]]; then
  mkdir -p /app
  curl -fsSL "${RUNPOD_WORKER_BUNDLE_URL}" -o /tmp/bundle.tar.gz
  tar xzf /tmp/bundle.tar.gz -C /app
elif command -v git >/dev/null 2>&1; then
  git clone --depth 1 "${REPO_URL}" /app
else
  apt-get install -y -qq git > /dev/null
  git clone --depth 1 "${REPO_URL}" /app
fi

log "Installing worker requirements..."
cd /app/workers/gpu-stream-worker
pip install -q -r requirements.txt

mkdir -p assets/audio/cinema_stems assets/cinema_stock/images
curl -fsSL 'https://incompetech.com/music/royalty-free/mp3-royaltyfree/Carefree.mp3' \
  -o assets/audio/cinema_stems/bg_lofi.mp3 || true

cd /app
export TOKEN_SYMBOL="${TOKEN_SYMBOL:-KWIF}"
export TOKEN_MINT="${TOKEN_MINT:-demo-kwif-runpod-live}"
export RECORD_DURATION_SEC="${DURATION}"
export WIDTH="${WIDTH:-1280}"
export HEIGHT="${HEIGHT:-720}"
export FPS="${FPS:-30}"
export OUTPUT_MP4=/tmp/runpod-live-sample.mp4
export TELEGRAM_OPS_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
export TELEGRAM_OPS_ADMIN_CHAT_ID="${TELEGRAM_GROUP_CHAT_ID:-}"

log "Recording ${RECORD_DURATION_SEC}s sample..."
python3 scripts/record-gpu-live-sample.py 2>&1 | tee /tmp/record.log

if [[ ! -f /tmp/runpod-live-sample.mp4 ]]; then
  log "ERROR: output MP4 missing"
  exit 1
fi

MB=$(du -m /tmp/runpod-live-sample.mp4 | cut -f1)
tg "✅ RunPod GPU sample SUCCESS
Pod: ${POD_ID}
File: /tmp/runpod-live-sample.mp4 (${MB} MB)
Video was uploaded above (or saved on pod if Telegram upload failed)."

echo SUCCESS > /tmp/runpod_job_status
echo DONE > /tmp/runpod_job_complete
log "Job complete."
