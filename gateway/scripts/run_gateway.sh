#!/bin/bash
# Sugarcane Field Gateway — Launcher Script
#
# Usage:
#   ./run_gateway.sh              # Normal mode (uses config receiver type)
#   ./run_gateway.sh --mock       # Mock receiver mode
#
# For systemd service:
#   Copy this to /etc/systemd/system/sugarcane-gateway.service
#   [Service]
#   Type=simple
#   WorkingDirectory=/opt/sugarcane-gateway
#   ExecStart=/opt/sugarcane-gateway/scripts/run_gateway.sh
#   Restart=always
#   RestartSec=10

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Activate virtual environment if available
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Run the gateway
exec python -m gateway.main "$@"
