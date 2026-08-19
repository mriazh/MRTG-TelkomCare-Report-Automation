#!/usr/bin/env bash
# ==============================================================================
# MRTG TelkomCare Automated Daily Scraping & Reporting Runner
# Target: Debian / Linux
# Runs full pipeline for yesterday's date (H-1) at 01:00 AM
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$APP_DIR"

PYTHON="$APP_DIR/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  echo "❌ Python virtual environment not found at $PYTHON" >&2
  exit 1
fi

# Calculate yesterday's date in YYYYMMDD format
YESTERDAY="$("$PYTHON" -c 'from datetime import date, timedelta; print((date.today() - timedelta(days=1)).strftime("%Y%m%d"))')"
echo "=========================================================="
echo "🚀 [MRTG TelkomCare] Starting daily pipeline for date: $YESTERDAY"
echo "=========================================================="

# Check if xvfb-run is available for virtual display
if command -v xvfb-run >/dev/null 2>&1; then
  EXEC_CMD=(xvfb-run -a "$PYTHON" -m mrtg_automation full --date "$YESTERDAY" --targets ocr --report-mode ocr)
else
  echo "⚠️ xvfb-run not found. Running with existing DISPLAY=${DISPLAY:-:0}."
  EXEC_CMD=("$PYTHON" -m mrtg_automation full --date "$YESTERDAY" --targets ocr --report-mode ocr)
fi

"${EXEC_CMD[@]}"

echo "=========================================================="
echo "✅ [MRTG TelkomCare] Daily pipeline completed for: $YESTERDAY"
echo "=========================================================="