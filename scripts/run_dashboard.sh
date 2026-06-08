#!/bin/bash
# =========================================================================
# TikTok Trend Analytics Dashboard Launcher
# =========================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo "========================================================================"
echo "Starting TikTok Trend Streamlit Dashboard..."
echo "========================================================================"

if [ -d ".venv" ]; then
    echo "[INFO] Activating virtual environment"
    source .venv/bin/activate
fi

export PYTHONPATH=.

# Run Streamlit dashboard
streamlit run src/dashboard.py --server.port 8501
