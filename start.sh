#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8000}"

echo "Serving Cini English dashboard at http://localhost:${PORT}"
echo "Press Ctrl+C to stop."
python3 -m http.server "${PORT}"