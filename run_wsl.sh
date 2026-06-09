#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt
if [ "${SKIP_TRANSCRIBE_DEPS:-0}" != "1" ]; then
  pip install -r requirements-transcribe.txt
fi
pip install -e .
export PLAYWRIGHT_BROWSERS_PATH="$PWD/runtime/ms-playwright"
export MODELSCOPE_CACHE="${MODELSCOPE_CACHE:-$PWD/models/modelscope}"
python -m playwright install chromium
python -m douyin_style_profiler "$@"
