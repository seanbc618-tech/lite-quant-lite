#!/usr/bin/env bash
# Daily maintenance: refresh modern provider data and run local health checks.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${ROOT}/.venv/bin/python"
MODERN_PROVIDER="${HOME}/.qlib/qlib_data/us_modern_liquid100"
CSV_SOURCE="${HOME}/.qlib/stock_data/source/us_data"
LOG_DIR="${ROOT}/logs"
mkdir -p "$LOG_DIR"

if [[ ! -x "$PY" ]]; then
  echo "Missing virtualenv at ${ROOT}/.venv" >&2
  exit 1
fi

CALENDAR_FILE="${MODERN_PROVIDER}/calendars/day.txt"
if [[ -f "$CALENDAR_FILE" ]]; then
  LAST_SESSION="$(tail -n 1 "$CALENDAR_FILE")"
  START_DATE="$(
    "$PY" - <<'PY' "$LAST_SESSION"
import sys
from datetime import date, timedelta

last = date.fromisoformat(sys.argv[1])
print((last - timedelta(days=7)).isoformat())
PY
  )"
else
  START_DATE="2025-03-27"
fi

END_DATE="$("$PY" - <<'PY'
from datetime import date

print(date.today().isoformat())
PY
)"

echo "[daily_pipeline] refresh CSV ${START_DATE} -> ${END_DATE}"
PYTHONPATH=src "$PY" scripts/update_nasdaq_csv.py \
  --csv-dir "$CSV_SOURCE" \
  --symbols-from-provider "${MODERN_PROVIDER}/build_summary.json" \
  --symbols SPY QQQ \
  --start "$START_DATE" \
  --end "$END_DATE"

echo "[daily_pipeline] rebuild modern provider"
PYTHONPATH=src "$PY" scripts/build_modern_qlib_provider.py \
  --provider-uri "$MODERN_PROVIDER" \
  --market liquid100 \
  --csv-dir "$CSV_SOURCE" \
  --symbols-from-csv \
  --overwrite

echo "[daily_pipeline] health check"
PYTHONPATH=src "$PY" scripts/health_check.py \
  --modern-provider-uri "$MODERN_PROVIDER"

echo "[daily_pipeline] done"