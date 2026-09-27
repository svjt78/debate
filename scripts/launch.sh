#!/bin/zsh
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/backend"
export HF_HUB_OFFLINE=1
export HF_HUB_DISABLE_TELEMETRY=1
if [[ -z "${DEBATE_WHISPER_MODEL:-}" && -f "$PWD/.data/auxiliary-models/whisper-small-mlx/weights.npz" ]]; then
  export DEBATE_WHISPER_MODEL="$PWD/.data/auxiliary-models/whisper-small-mlx"
fi
export HF_HOME="$PWD/.data/auxiliary-cache"
export XDG_CACHE_HOME="$PWD/.data/cache"
exec .venv/bin/python -m uvicorn debate_lab.app:factory --factory --host 127.0.0.1 --port "${DEBATE_PORT:-8787}" --workers 1 --timeout-graceful-shutdown 5
