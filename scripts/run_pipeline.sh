#!/bin/bash
# =========================================================================
# TikTok Trend Data Engineering Pipeline Orchestrator
# =========================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo "========================================================================"
echo "TikTok Trend Data Engineering Pipeline Orchestrator: $(date)"
echo "========================================================================"

if [ -d ".venv" ]; then
    echo "[INFO] Setting up Python virtual environment"
    source .venv/bin/activate
fi

export PYTHONPATH=.

echo ""
echo "------------------------------------------------------------------------"
echo "Step 1: Crawl Top Ads Vietnam data..."
echo "------------------------------------------------------------------------"
python3 src/crawl_creative_center.py --period 30 --country VN

echo ""
echo "------------------------------------------------------------------------"
echo "Step 2: Load raw JSON data into PostgreSQL Staging..."
echo "------------------------------------------------------------------------"
python3 src/load.py

echo ""
echo "------------------------------------------------------------------------"
echo "Step 3: Transform data with dbt to update Data Warehouse..."
echo "------------------------------------------------------------------------"
dbt run --project-dir dbt_project --profiles-dir dbt_project

echo ""
echo "========================================================================"
echo "PIPELINE HAS BEEN COMPLETED SUCCESSFULLY! : $(date)"
echo "========================================================================"
