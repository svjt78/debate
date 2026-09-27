#!/bin/zsh
set -euo pipefail
cd "$(dirname "$0")/.."
export DEBATE_DATA_DIR="$PWD/.data/live-verification"
export DEBATE_PORT=8788
exec ./scripts/launch.sh
