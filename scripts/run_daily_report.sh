#!/usr/bin/env bash
# ==============================================================================
# MRTG TelkomCare Automated Daily Scraping & Reporting Runner
# Target: Debian / Linux
# Runs full pipeline for yesterday's date (H-1) at 01:00 AM
#
# WhatsApp lifecycle notifications (REQ-18) are sent through the locally running
# GOWA REST gateway. Every notification is best-effort: failures, HTTP errors and
# timeouts only add a journal warning and never change the pipeline exit status.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$APP_DIR"

PYTHON="$APP_DIR/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  echo "Python virtual environment not found at $PYTHON" >&2
  exit 1
fi

WA_MAX_TIME_SECONDS=5
WA_CONNECT_TIMEOUT_SECONDS=2

trim() {
  local value="$1"
  case "$value" in
    '"'*'"') value="${value:1:${#value}-2}" ;;
    "'"*"'") value="${value:1:${#value}-2}" ;;
  esac
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

alerts_enabled() {
  case "${WA_ALERT_ENABLED,,}" in
    true | 1 | yes) [ -n "$WA_TARGET_JID" ] ;;
    *) return 1 ;;
  esac
}

notify() {
  local status="$1" message payload url
  local -a headers=(--header "Content-Type: application/json")

  alerts_enabled || return 0

  if ! command -v curl >/dev/null 2>&1; then
    echo "[WARNING] WhatsApp notification ($status) skipped: curl is not installed" >&2
    return 0
  fi

  case "$status" in
    start) message="MRTG TelkomCare daily report: STARTED (date ${YESTERDAY})." ;;
    success) message="MRTG TelkomCare daily report: SUCCESS (date ${YESTERDAY})." ;;
    failure) message="MRTG TelkomCare daily report: FAILED (date ${YESTERDAY}, exit code ${PIPELINE_EXIT_CODE})." ;;
    *)
      echo "[WARNING] WhatsApp notification skipped: unknown status '${status}'" >&2
      return 0
      ;;
  esac

  if [ -n "$WA_DEVICE_ID" ]; then
    headers+=(--header "X-Device-Id: ${WA_DEVICE_ID}")
  fi

  payload="$("$PYTHON" -c 'import json,sys; print(json.dumps({"phone": sys.argv[1], "message": sys.argv[2]}))' "$WA_TARGET_JID" "$message")" || {
    echo "[WARNING] WhatsApp notification ($status) skipped: payload encoding failed" >&2
    return 0
  }

  url="${WA_GATEWAY_URL%/}/send/message"
  if curl --silent --fail \
    --max-time "$WA_MAX_TIME_SECONDS" \
    --connect-timeout "$WA_CONNECT_TIMEOUT_SECONDS" \
    --request POST "$url" "${headers[@]}" \
    --data "$payload" >/dev/null 2>&1; then
    return 0
  fi

  echo "[WARNING] WhatsApp notification ($status) not delivered by GOWA gateway" >&2
  return 0
}

YESTERDAY="$("$PYTHON" -c 'from datetime import date, timedelta; print((date.today() - timedelta(days=1)).strftime("%Y%m%d"))')"
echo "[MRTG TelkomCare] Starting daily pipeline for date: $YESTERDAY"

WA_ALERT_ENABLED=""
WA_GATEWAY_URL="http://localhost:3000"
WA_DEVICE_ID=""
WA_TARGET_JID=""
if [ -r "$APP_DIR/config/.env" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    case "$line" in
      "export "*) line="${line#export }" ;;
    esac
    case "$line" in
      WA_ALERT_ENABLED=*) WA_ALERT_ENABLED="$(trim "${line#*=}")" ;;
      WA_GATEWAY_URL=*) WA_GATEWAY_URL="$(trim "${line#*=}")" ;;
      WA_DEVICE_ID=*) WA_DEVICE_ID="$(trim "${line#*=}")" ;;
      WA_TARGET_JID=*) WA_TARGET_JID="$(trim "${line#*=}")" ;;
    esac
  done < "$APP_DIR/config/.env"
fi

if [ -z "$WA_GATEWAY_URL" ]; then
  WA_GATEWAY_URL="http://localhost:3000"
fi

PIPELINE_EXIT_CODE=0
if command -v xvfb-run >/dev/null 2>&1; then
  EXEC_CMD=(xvfb-run -a "$PYTHON" -m mrtg_automation full --date "$YESTERDAY" --targets ocr --report-mode ocr)
else
  echo "xvfb-run not found. Running with existing DISPLAY=${DISPLAY:-:0}."
  EXEC_CMD=("$PYTHON" -m mrtg_automation full --date "$YESTERDAY" --targets ocr --report-mode ocr)
fi

notify start
"${EXEC_CMD[@]}" || PIPELINE_EXIT_CODE=$?

if [ "$PIPELINE_EXIT_CODE" -eq 0 ]; then
  notify success
  echo "[MRTG TelkomCare] Daily pipeline completed for: $YESTERDAY"
else
  notify failure
  echo "[MRTG TelkomCare] Daily pipeline failed for: $YESTERDAY (exit code $PIPELINE_EXIT_CODE)" >&2
fi

exit "$PIPELINE_EXIT_CODE"