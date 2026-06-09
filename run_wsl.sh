#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
export PLAYWRIGHT_BROWSERS_PATH="$PWD/runtime/ms-playwright"
python -m playwright install chromium
python -m douyin_style_profiler "$@"
