# kwif-gpu-worker-runpod

RunPod GPU worker for KWIF livestream infrastructure.

## Video sample template: DISABLED

The demo video recorder (`record-gpu-live-sample.py`) and startup script have been **disabled** to prevent:
- Repeated identical Telegram video uploads
- Continuous GPU billing when not in use

`scripts/runpod-pod-startup.sh` exits immediately — no install, no recording.

## To run a sample (explicit opt-in only)

From the main workspace repo:

```bash
RUNPOD_POD_CREATE_ENABLED=1 VIDEO_GENERATION_ENABLED=1 python3 scripts/runpod-real-live-sample.py
```

Pods always terminate after the job — never left running.

## Emergency: kill all pods

```bash
bash scripts/kill-all-runpod-pods.sh
```
