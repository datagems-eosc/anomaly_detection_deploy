# Test Scripts

This directory contains test scripts for validating the anomaly detection system.

## Available Tests

### 1. Short-Term Detection Tests
Test real-time anomaly detection over short time windows (hours).

```bash
bash tests/test_short_term_detection.sh
```

**What it tests:**
- Basic detection with 3-sigma method
- Spatial verification
- ARIMA method
- Single station detection

---

### 2. Long-Term Health Check Tests
Test sensor health monitoring over extended periods (days/weeks).

```bash
bash tests/test_long_term_health.sh
```

**What it tests:**
- 7-day health check for all stations
- 30-day health check for all stations
- Problem stations (dodoni, kolympari, volos)
- Baseline healthy station (grevena)

**Expected issues to detect:**
- 🔴 **dodoni**: High zero ratio in wind_speed (stalled sensor)
- 🔴 **kolympari**: High missing rate (data loss)
- 🔴 **volos**: Low variance (stuck sensor)
- ✅ **grevena**: Should be healthy (baseline)

---

### 3. Data Collection Tests
Test database health and data collection pipeline.

```bash
bash tests/test_data_collection.sh
```

**What it tests:**
- Database existence and size
- Data freshness (< 15 minutes)
- Station coverage
- Collector process status
- Recent data completeness

---

## Quick Test All

Run all tests in sequence:

```bash
bash tests/test_data_collection.sh
bash tests/test_short_term_detection.sh
bash tests/test_long_term_health.sh
```

---

## Prerequisites

Before running tests, ensure:

1. **Database exists**: `weather_stream.db` should be present
2. **Collector is running**: Start with `./manage_collector.sh start`
3. **Data is available**: Wait at least 1 hour for sufficient data
4. **Dependencies installed**: `pip install -r requirements.txt`

---

## Making Scripts Executable

```bash
chmod +x tests/*.sh
```

Then you can run them directly:

```bash
./tests/test_short_term_detection.sh
./tests/test_long_term_health.sh
./tests/test_data_collection.sh
```

---

## Troubleshooting

### No data in database
```bash
# Start the collector
./manage_collector.sh start

# Wait 10-15 minutes for first data collection
sleep 600

# Check database
sqlite3 weather_stream.db "SELECT COUNT(*) FROM observations;"
```

### Collector not running
```bash
# Check status
./manage_collector.sh status

# View logs
tail -f streaming_collector.log

# Restart collector
./manage_collector.sh restart
```

### Tests fail with import errors
```bash
# Ensure you're in the correct conda environment
conda activate datagem

# Reinstall dependencies
pip install -r requirements.txt
```

