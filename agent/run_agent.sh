#!/bin/bash
# run_agent.sh — wrapper for cron to run the LangGraph agent.
# Activates the venv, sets working directory, runs agent, captures all output.

set -e

AGENT_DIR="/home/pi/sugarcane-iot-system-main/agent"
VENV_PYTHON="$AGENT_DIR/.venv/bin/python"
LOG_FILE="$AGENT_DIR/logs/cron.log"

mkdir -p "$AGENT_DIR/logs"

{
  echo ""
  echo "=========================================="
  echo "Agent cycle started at: $(date)"
  echo "=========================================="
  cd "$AGENT_DIR"
  "$VENV_PYTHON" agent_graph.py
  echo "Agent cycle ended at: $(date)"
} >> "$LOG_FILE" 2>&1
