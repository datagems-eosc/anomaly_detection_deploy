#!/bin/bash
# Best practice: Complete anomaly detection with spatial verification
# Usage: 
#   bash run_best_detection.sh              # Use current time (NOW)
#   bash run_best_detection.sh "2025-11-23 02:00:00"  # Use specific time

cd "$(dirname "$0")/.."

# Get timestamp (default to NOW)
TIMESTAMP=${1:-"NOW"}

echo "🔍 Running Complete Anomaly Detection"
echo "   Time: $TIMESTAMP"
echo "   Method: 3-sigma (fast and reliable)"
echo "   Window: 6 hours"
echo "   Spatial verification: ENABLED"
echo ""

python anomaly_detector.py \
    --end "$TIMESTAMP" \
    --window 6 \
    --temporal-method 3sigma \
    --spatial-verify


