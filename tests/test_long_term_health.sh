#!/bin/bash
# Long-term sensor health check tests

cd "$(dirname "$0")/.."

echo "🏥 Long-Term Health Check Tests"
echo ""

# Test 1: All stations (7 days)
echo "1. All stations (last 7 days)..."
python anomaly_detector.py --health-check --days 7


# Test 2: Problem stations
echo -e "\n3. Problem stations..."
python anomaly_detector.py --health-check --days 7 --station dodoni




