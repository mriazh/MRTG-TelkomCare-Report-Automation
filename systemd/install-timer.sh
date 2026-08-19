#!/usr/bin/env bash
# ==============================================================================
# Helper script to install and enable MRTG TelkomCare systemd timer on Debian
# ==============================================================================
set -euo pipefail

SYSTEMD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "📦 Installing systemd service and timer units."
sudo cp "$SYSTEMD_DIR/mrtg-telkomcare-daily.service" /etc/systemd/system/
sudo cp "$SYSTEMD_DIR/mrtg-telkomcare-daily.timer" /etc/systemd/system/

echo "🔄 Reloading systemd daemon."
sudo systemctl daemon-reload

echo "🚀 Enabling and starting mrtg-telkomcare-daily.timer."
sudo systemctl enable --now mrtg-telkomcare-daily.timer

echo "=========================================================="
echo "✅ Timer successfully enabled! Current timer status:"
echo "=========================================================="
sudo systemctl list-timers --all | grep mrtg-telkomcare || true