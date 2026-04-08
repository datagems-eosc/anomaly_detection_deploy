# Code Examples

## Detection Modes

This system provides two detection modes:

1. **Short-Term Detection**: Real-time anomaly detection (Examples 1-17)
2. **Long-Term Health Check**: Sensor health monitoring (Examples 18-23) 🆕

---

## Short-Term Detection Examples

### Example 1: Real-Time Detection

Detect anomalies at the current time with default settings:

```bash
python anomaly_detector.py --end "NOW" --spatial-verify
```

**Output**:

```
Total Stations: 14
Anomalous Stations: 0
Normal Stations: 14

Anomaly Breakdown:
  🔴 Device Failures: 0
  🌧️ Weather Events: 0
  ⚠️ Suspected: 0
```

---

### Example 2: Historical Analysis

Analyze a specific historical timestamp:

```bash
python anomaly_detector.py \
  --end "2025-11-22 17:00:00" \
  --window 6 \
  --temporal-method arima \
  --spatial-verify
```

**Use Case**: Investigate why an alert was missed or validate detection performance.

---

### Example 3: Method Comparison

Compare different detection methods on the same data:

```bash
# ARIMA (best accuracy)
python anomaly_detector.py --end "2025-11-22 17:00:00" --temporal-method arima --spatial-verify --save report_arima.json

# 3-Sigma (fastest)
python anomaly_detector.py --end "2025-11-22 17:00:00" --temporal-method 3sigma --spatial-verify --save report_3sigma.json

# MAD (most robust)
python anomaly_detector.py --end "2025-11-22 17:00:00" --temporal-method mad --spatial-verify --save report_mad.json
```

Then compare results:

```bash
echo "ARIMA:"
jq '.summary' report_arima.json

echo "3-Sigma:"
jq '.summary' report_3sigma.json

echo "MAD:"
jq '.summary' report_mad.json
```

---

### Example 4: Single Variable Analysis

Only analyze temperature:

```bash
python anomaly_detector.py \
  --end "NOW" \
  --variables "temp_out" \
  --temporal-method arima \
  --spatial-verify
```

**Use Case**: Faster execution when you only care about specific variables.

---

### Example 5: Without Spatial Verification

Quick temporal check without neighbor comparison:

```bash
python anomaly_detector.py --end "NOW" --temporal-method 3sigma
```

**Warning**: Higher false positive rate. Only use for testing.

---

## Advanced Examples

### Example 6: Custom Thresholds

Fine-tune detection sensitivity:

```bash
python anomaly_detector.py \
  --end "NOW" \
  --temporal-method 3sigma \
  --temporal-threshold 2.5 \
  --spatial-verify \
  --correlation-threshold-high 0.7 \
  --correlation-threshold-low 0.2
```

**Effect**:

- Lower temporal threshold (2.5 vs 3.0): More sensitive → more detections
- Higher correlation threshold (0.7 vs 0.6): Stricter weather event criteria

---

### Example 7: Wider Neighbor Radius

Expand spatial verification to 150km:

```bash
python anomaly_detector.py \
  --end "NOW" \
  --spatial-verify \
  --neighbor-radius 150
```

**Use Case**: Sparse station networks or large-scale weather phenomena.

---

### Example 8: Verbose Debugging

Get detailed execution logs:

```bash
python anomaly_detector.py \
  --end "NOW" \
  --spatial-verify \
  --verbose
```

**Output includes**:

- Database queries
- Model fitting details
- Correlation calculations
- Classification logic

---

## Automation Examples

### Example 9: Cron Job (Hourly Monitoring)

Add to crontab:

```bash
# Edit crontab
crontab -e

# Add this line (runs every hour)
0 * * * * cd /path/to/stream_detection && /path/to/python anomaly_detector.py --end "NOW" --spatial-verify --save /var/log/anomaly_reports/report_$(date +\%Y\%m\%d_\%H\%M).json >> /var/log/anomaly_detector.log 2>&1
```

---

### Example 10: Alert on Device Failures

Bash script that sends alerts:

```bash
#!/bin/bash
# detect_and_alert.sh

REPORT_FILE="/tmp/anomaly_report.json"

# Run detection
python anomaly_detector.py \
  --end "NOW" \
  --spatial-verify \
  --save "$REPORT_FILE"

# Check for device failures
FAILURES=$(jq '.summary.device_failures' "$REPORT_FILE")

if [ "$FAILURES" -gt 0 ]; then
    # Extract failure details
    STATIONS=$(jq -r '.anomalies[] | select(.classification == "device_failure") | .station_id' "$REPORT_FILE" | tr '\n' ', ')
    
    # Send alert (example with email)
    echo "Device failures detected at: $STATIONS" | \
        mail -s "ALERT: Weather Station Failure" admin@example.com
    
    # Send alert (example with Slack)
    curl -X POST -H 'Content-type: application/json' \
        --data "{\"text\":\"🔴 Device failures detected: $STATIONS\"}" \
        YOUR_SLACK_WEBHOOK_URL
fi
```

Make executable and add to cron:

```bash
chmod +x detect_and_alert.sh

# Run every 30 minutes
*/30 * * * * /path/to/detect_and_alert.sh
```

---

### Example 11: Batch Historical Analysis

Analyze multiple historical timestamps:

```bash
#!/bin/bash
# batch_analysis.sh

START_DATE="2025-11-01 00:00:00"
END_DATE="2025-11-22 23:00:00"
INTERVAL_HOURS=6

current=$(date -d "$START_DATE" +%s)
end=$(date -d "$END_DATE" +%s)

while [ $current -le $end ]; do
    timestamp=$(date -d "@$current" "+%Y-%m-%d %H:%M:%S")
    echo "Analyzing $timestamp..."
    
    python anomaly_detector.py \
        --end "$timestamp" \
        --window 6 \
        --spatial-verify \
        --save "reports/report_${current}.json"
    
    current=$((current + INTERVAL_HOURS * 3600))
done

# Aggregate results
echo "Aggregating results..."
jq -s '[.[] | .anomalies[]] | group_by(.classification) | map({classification: .[0].classification, count: length})' reports/*.json > summary.json
```

---

### Example 12: Python Integration

Use the detector in a Python application:

```python
import subprocess
import json
import sys

def detect_anomalies(end_time="NOW", method="arima"):
    """
    Run anomaly detection and return structured results.
    """
    cmd = [
        "python", "anomaly_detector.py",
        "--end", end_time,
        "--temporal-method", method,
        "--spatial-verify",
        "--save", "/tmp/report.json"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Load JSON report
        with open('/tmp/report.json', 'r') as f:
            report = json.load(f)
        
        return report
    
    except subprocess.CalledProcessError as e:
        print(f"Detection failed: {e.stderr}", file=sys.stderr)
        return None

# Usage
if __name__ == "__main__":
    report = detect_anomalies()
    
    if report:
        # Check for device failures
        if report['summary']['device_failures'] > 0:
            print("⚠️ Device failures detected:")
            for anomaly in report['anomalies']:
                if anomaly['classification'] == 'device_failure':
                    print(f"  - {anomaly['station_id']}: {anomaly['variable']} = {anomaly['actual_value']}")
        else:
            print("✅ All stations operating normally")
```

---

### Example 13: Dashboard Integration

Export data for real-time dashboard:

```python
import json
import time
from datetime import datetime

def export_for_dashboard():
    """
    Run detection and export to dashboard-friendly format.
    """
    # Run detection
    import subprocess
    subprocess.run([
        "python", "anomaly_detector.py",
        "--end", "NOW",
        "--spatial-verify",
        "--save", "/tmp/report.json"
    ])
    
    # Load report
    with open('/tmp/report.json', 'r') as f:
        report = json.load(f)
    
    # Transform for dashboard
    dashboard_data = {
        "timestamp": datetime.now().isoformat(),
        "status": "critical" if report['summary']['device_failures'] > 0 else "normal",
        "stats": {
            "total": report['summary']['total_stations'],
            "normal": report['summary']['normal_stations'],
            "anomalous": report['summary']['anomalous_stations'],
            "failures": report['summary']['device_failures']
        },
        "alerts": [
            {
                "station": a['station_id'],
                "type": a['classification'],
                "value": a['actual_value'],
                "expected": a['expected_value'],
                "severity": "high" if a['classification'] == "device_failure" else "low"
            }
            for a in report['anomalies']
        ]
    }
    
    # Save for dashboard
    with open('/var/www/dashboard/data/latest.json', 'w') as f:
        json.dump(dashboard_data, f)

# Run every minute
while True:
    export_for_dashboard()
    time.sleep(60)
```

---

## Testing Examples

### Example 14: Test Individual Methods

Compare all methods quickly:

```bash
#!/bin/bash
# test_all_methods.sh

TIMESTAMP="2025-11-22 17:00:00"
METHODS=("arima" "3sigma" "mad" "iqr" "isolation_forest" "stl" "lof")

echo "Method,TotalAnomalies,DeviceFailures,WeatherEvents,ExecutionTime"

for method in "${METHODS[@]}"; do
    start=$(date +%s.%N)
    
    python anomaly_detector.py \
        --end "$TIMESTAMP" \
        --temporal-method "$method" \
        --spatial-verify \
        --save "/tmp/test_${method}.json" > /dev/null 2>&1
    
    end=$(date +%s.%N)
    runtime=$(echo "$end - $start" | bc)
    
    total=$(jq '.summary.anomalous_stations' "/tmp/test_${method}.json")
    failures=$(jq '.summary.device_failures' "/tmp/test_${method}.json")
    weather=$(jq '.summary.weather_events' "/tmp/test_${method}.json")
    
    echo "$method,$total,$failures,$weather,$runtime"
done
```

---

### Example 15: Validate Detection Accuracy

Test with known anomalies:

```python
import json
from datetime import datetime, timedelta

# Known anomalies (from manual inspection)
KNOWN_ANOMALIES = {
    "2025-11-15 14:00:00": {
        "station": "pelion",
        "type": "device_failure",
        "variable": "temp_out"
    },
    "2025-11-20 08:00:00": {
        "station": "uth_volos",
        "type": "weather_event",
        "variable": "temp_out"
    }
}

def validate_detection():
    """
    Test detection against known anomalies.
    """
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    
    for timestamp, expected in KNOWN_ANOMALIES.items():
        # Run detection
        subprocess.run([
            "python", "anomaly_detector.py",
            "--end", timestamp,
            "--spatial-verify",
            "--save", "/tmp/validation.json"
        ], capture_output=True)
        
        # Load results
        with open('/tmp/validation.json', 'r') as f:
            report = json.load(f)
        
        # Check if detected
        detected = False
        for anomaly in report['anomalies']:
            if (anomaly['station_id'] == expected['station'] and
                anomaly['variable'] == expected['variable']):
                detected = True
                
                # Check classification
                if anomaly['classification'] == expected['type']:
                    true_positives += 1
                else:
                    false_positives += 1
                break
        
        if not detected:
            false_negatives += 1
    
    # Calculate metrics
    precision = true_positives / (true_positives + false_positives)
    recall = true_positives / (true_positives + false_negatives)
    f1 = 2 * (precision * recall) / (precision + recall)
    
    print(f"Precision: {precision:.2%}")
    print(f"Recall: {recall:.2%}")
    print(f"F1 Score: {f1:.2%}")

if __name__ == "__main__":
    validate_detection()
```

---

## Performance Examples

### Example 16: Benchmark Methods

Compare execution times:

```bash
#!/bin/bash
# benchmark.sh

echo "Benchmarking detection methods..."

for method in arima 3sigma mad iqr; do
    echo "Testing $method..."
    time python anomaly_detector.py \
        --end "NOW" \
        --temporal-method "$method" \
        --spatial-verify \
        > /dev/null 2>&1
done
```

Typical results:

```
Testing arima...
real    0m2.345s

Testing 3sigma...
real    0m0.123s

Testing mad...
real    0m0.156s

Testing iqr...
real    0m0.134s
```

---

### Example 17: Database Performance

Test query performance with different window sizes:

```python
import subprocess
import time

window_sizes = [1, 6, 12, 24, 48]

print("Window (hours) | Query Time (s)")
print("---------------|---------------")

for window in window_sizes:
    start = time.time()
    
    subprocess.run([
        "python", "anomaly_detector.py",
        "--end", "NOW",
        "--window", str(window),
        "--temporal-method", "3sigma"  # Fast method to isolate DB time
    ], capture_output=True)
    
    elapsed = time.time() - start
    print(f"{window:14d} | {elapsed:.3f}")
```

---

## Integration Examples

### Example 18: Prometheus Exporter

Export metrics for Prometheus:

```python
from prometheus_client import Gauge, start_http_server
import json
import subprocess
import time

# Define metrics
device_failures = Gauge('weather_device_failures', 'Number of device failures')
weather_events = Gauge('weather_extreme_events', 'Number of weather events')
anomalous_stations = Gauge('weather_anomalous_stations', 'Number of stations with anomalies')

def collect_metrics():
    """
    Run detection and update Prometheus metrics.
    """
    subprocess.run([
        "python", "anomaly_detector.py",
        "--end", "NOW",
        "--spatial-verify",
        "--save", "/tmp/report.json"
    ], capture_output=True)
    
    with open('/tmp/report.json', 'r') as f:
        report = json.load(f)
    
    device_failures.set(report['summary']['device_failures'])
    weather_events.set(report['summary']['weather_events'])
    anomalous_stations.set(report['summary']['anomalous_stations'])

if __name__ == "__main__":
    # Start Prometheus HTTP server
    start_http_server(8000)
    
    # Update metrics every 5 minutes
    while True:
        collect_metrics()
        time.sleep(300)
```

---

## Long-Term Health Check Examples 🆕

### Example 18: Weekly Health Check

Check all stations for the last 7 days:

```bash
python anomaly_detector.py --health-check --days 7
```

**Output**:

```text
═══════════════════════════════════════════════════════════════════════════════
📊 LONG-TERM SENSOR HEALTH CHECK
Period: Last 7 days
═══════════════════════════════════════════════════════════════════════════════

Station              Status       Completeness    Issues
--------------------------------------------------------------------------------
grevena              🔴 CRITICAL  58.0%           1 problems
  └─ wind_speed: High zero ratio (71.6%) - sensor may be stalled
dodoni               ✅ HEALTHY   57.6%           0 problems
volos                ✅ HEALTHY   57.9%           0 problems
...
```

**Use Case**: Routine weekly monitoring to identify chronic sensor problems

---

### Example 19: Monthly Health Review with JSON Export

Check all stations over 30 days and save detailed report:

```bash
python anomaly_detector.py --health-check --days 30 --save health_monthly.json
```

**JSON Output**:

```json
[
  {
    "station_id": "grevena",
    "analysis_period_days": 30,
    "data_completeness": 0.58,
    "total_data_points": 2340,
    "overall_status": "critical",
    "variable_reports": [
      {
        "variable": "wind_speed",
        "zero_ratio": 0.716,
        "null_ratio": 0.0,
        "variance": 1.37,
        "issues": ["High zero ratio (71.6%) - sensor may be stalled"],
        "severity": "critical"
      }
    ]
  }
]
```

**Use Case**: Monthly maintenance planning and trend analysis

---

### Example 20: Investigate Specific Station

Focus on a problematic station:

```bash
python anomaly_detector.py --health-check --days 7 --station grevena
```

**Use Case**: Detailed diagnosis of known problem stations

---

### Example 21: Check Multiple Variables

Analyze all meteorological variables:

```bash
python anomaly_detector.py --health-check --days 7 \
  --variables wind_speed,temp_out,out_hum,bar,rain \
  --save comprehensive_health.json
```

**Use Case**: Comprehensive station diagnostics before critical weather season

---

### Example 22: Automated Daily Health Monitoring

Create a cron job for daily health checks with alerting:

```bash
#!/bin/bash
# daily_health_check.sh

REPORT_FILE="/tmp/health_$(date +%Y%m%d).json"

# Run health check
python anomaly_detector.py --health-check --days 7 --save "$REPORT_FILE"

# Count critical stations
CRITICAL_COUNT=$(jq '[.[] | select(.overall_status == "critical")] | length' "$REPORT_FILE")

if [ "$CRITICAL_COUNT" -gt 0 ]; then
    # Extract critical stations and issues
    CRITICAL_STATIONS=$(jq -r '.[] | select(.overall_status == "critical") | .station_id' "$REPORT_FILE" | tr '\n' ', ')
    ISSUES=$(jq -r '.[] | select(.overall_status == "critical") | .variable_reports[].issues[]' "$REPORT_FILE")
    
    # Send alert
    echo -e "Critical sensor health issues:\n\nStations: $CRITICAL_STATIONS\n\nIssues:\n$ISSUES" | \
        mail -s "🔴 ALERT: Critical Sensor Health Issues" admin@example.com
fi
```

Add to crontab:

```bash
# Run daily at 6 AM
0 6 * * * /path/to/daily_health_check.sh
```

**Use Case**: Continuous monitoring with automatic alerts

---

### Example 23: Health Metrics Dashboard Integration

Export health metrics for Grafana/Prometheus:

```python
from prometheus_client import Gauge, CollectorRegistry, write_to_textfile
import json
import subprocess

# Create metrics
registry = CollectorRegistry()
completeness = Gauge('station_data_completeness', 
                     'Data completeness percentage',
                     ['station_id'], registry=registry)
zero_ratio = Gauge('station_zero_ratio',
                   'Zero readings percentage',
                   ['station_id', 'variable'], registry=registry)
status = Gauge('station_health_status',
               'Health status (0=healthy, 1=warning, 2=critical)',
               ['station_id'], registry=registry)

def export_health_metrics():
    # Run health check
    subprocess.run([
        "python", "anomaly_detector.py",
        "--health-check", "--days", "7",
        "--save", "/tmp/health.json"
    ])
    
    # Load report
    with open('/tmp/health.json', 'r') as f:
        report = json.load(f)
    
    # Export metrics
    status_map = {'healthy': 0, 'warning': 1, 'critical': 2}
    
    for station in report:
        sid = station['station_id']
        
        completeness.labels(station_id=sid).set(station['data_completeness'])
        status.labels(station_id=sid).set(status_map[station['overall_status']])
        
        for var in station['variable_reports']:
            zero_ratio.labels(
                station_id=sid,
                variable=var['variable']
            ).set(var['zero_ratio'])
    
    # Write for Prometheus
    write_to_textfile('/var/lib/prometheus/health.prom', registry)

if __name__ == "__main__":
    export_health_metrics()
```

Schedule with cron:

```bash
*/10 * * * * /path/to/export_health_metrics.py
```

**Use Case**: Real-time dashboard visualization and alerting

---

### Health Check vs Short-Term Detection

| Feature | Short-Term Detection | Long-Term Health Check |
|---------|---------------------|------------------------|
| **Time Scale** | Hours (1-24) | Days/Weeks (7-90) |
| **Purpose** | Catch sudden failures | Identify gradual degradation |
| **Metrics** | Temporal + Spatial anomalies | Zero ratio, data loss, variance |
| **Output** | Anomaly classification | Health status + metrics |
| **Frequency** | Every 10 min - hourly | Daily - weekly |
| **Use Case** | Real-time alerting | Maintenance planning |

### When to Use Each Mode

**Use Short-Term Detection when**:
- Monitoring for sudden device failures
- Distinguishing weather events from equipment issues
- Real-time alerting is needed
- Analyzing specific timestamps

**Use Long-Term Health Check when**:
- Planning maintenance schedules
- Identifying chronic sensor problems
- Tracking data quality trends
- Preparing seasonal reports

**Use Both for**:
- Comprehensive monitoring strategy
- Complete failure coverage
- Quality assurance programs

---

These examples cover most common use cases. For more specific scenarios, refer to:

- [API Reference](overview.md) - Complete parameter documentation
- [Long-Term Health Check Guide](../examples/health-check.md) - Detailed health check examples
- [FAQ](../faq.md) - Common questions and troubleshooting

