#!/bin/bash
# Short-term anomaly detection tests

cd "$(dirname "$0")/.."

echo "🧪 Short-Term Detection Tests"
echo ""

# Test 1: Basic detection
echo "1. Basic detection (3-sigma)..."
python anomaly_detector.py --end "NOW" --window 6 --temporal-method 3sigma

# Test 2: With spatial verification
echo -e "\n2. With spatial verification..."
python anomaly_detector.py --end "NOW" --window 6 --spatial-verify

# Test 3: ARIMA method
echo -e "\n3. ARIMA method..."
python anomaly_detector.py --end "NOW" --window 6 --temporal-method arima --spatial-verify

echo -e "\n✅ Tests completed"

