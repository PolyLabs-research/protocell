#!/usr/bin/env bash
# Linux or macOS: laptop.py (set this checkout up on another machine, test the compiled life, time the CPU and the GPU),
# run by a Python new enough for it, fetched by uv when this machine's is older. On Windows: python laptop.py
set -euo pipefail
cd "$(dirname "$0")"
if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    exec python3 laptop.py "$@"
fi
if command -v uv >/dev/null 2>&1; then
    exec uv run --no-project --python 3.11 laptop.py "$@"
fi
echo "!! this needs Python 3.11 or later, and this machine's python3 is older. Install uv (https://docs.astral.sh/uv/), which fetches one, and run this again."
exit 1
