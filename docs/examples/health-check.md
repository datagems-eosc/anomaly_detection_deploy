# Long-Term Health Check Examples

This page provides practical examples of using the long-term health check feature to detect chronic sensor problems.

## Overview

Long-term health checks analyze sensor data over days or weeks to detect:

- 🔴 **Stalled sensors**: Stuck at zero or constant values
- 🔴 **Data loss**: Missing observations due to communication failures
- 🔴 **Sensor degradation**: Abnormally low variance indicating malfunction

Unlike short-term detection (which catches sudden failures), health checks identify gradual degradation before it becomes critical.

---

## Basic Examples

### Example 1: Weekly Health Check (All Stations)

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
amfissa              ✅ HEALTHY   57.4%           0 problems
dodoni               ✅ HEALTHY   57.6%           0 problems
embonas              ✅ HEALTHY   58.0%           0 problems
grevena              🔴 CRITICAL  58.0%           1 problems
  └─ wind_speed: High zero ratio (71.6%) - sensor may be stalled
heraclion            ✅ HEALTHY   57.9%           0 problems
...
```

**When to Use**: Routine weekly monitoring to identify new problems

---

### Example 2: Monthly Health Review

Check all stations over the last 30 days:

```bash
python anomaly_detector.py --health-check --days 30
```

**When to Use**: Monthly maintenance planning and trend analysis

---

### Example 3: Single Station Investigation

Investigate a specific problematic station:

```bash
python anomaly_detector.py --health-check --days 7 --station grevena
```

**Output**:

```text
Station: grevena
Status: 🔴 CRITICAL
Data Completeness: 58.0%
Total Data Points: 585

Variable Reports:
  wind_speed:
    ✗ High zero ratio (71.6%) - sensor may be stalled
    • Zero Ratio: 0.716 (71.6%)
    • Null Ratio: 0.000 (0.0%)
    • Variance: 1.37
```

**When to Use**: Focused investigation of known problem stations

---

### Example 4: Generate JSON Report

Export detailed report for integration:

```bash
python anomaly_detector.py --health-check --days 7 --save health_report.json
```

**Output File** (`health_report.json`):

```json
[
  {
    "station_id": "grevena",
    "analysis_period_days": 7,
    "data_completeness": 0.5803571428571429,
    "total_data_points": 585,
    "overall_status": "critical",
    "variable_reports": [
      {
        "variable": "wind_speed",
        "zero_ratio": 0.7162393162393162,
        "null_ratio": 0.0,
        "variance": 1.3745650392225732,
        "issues": [
          "High zero ratio (71.6%) - sensor may be stalled"
        ],
        "severity": "critical"
      }
    ]
  }
]
```

**When to Use**: Integration with monitoring dashboards, alerting systems, or quality tracking

---

## Advanced Examples

### Example 5: Custom Time Period

Check a specific historical period:

```bash
# Check last 14 days
python anomaly_detector.py --health-check --days 14

# Check last quarter (90 days)
python anomaly_detector.py --health-check --days 90
```

**When to Use**: 
- Investigate historical problems
- Quarterly reporting
- Trend analysis over extended periods

---

### Example 6: Multiple Variables

Check all meteorological variables for health:

```bash
python anomaly_detector.py --health-check --days 7 \
  --variables wind_speed,temp_out,out_hum,bar,rain
```

**Output**:

```text
Station: grevena
  wind_speed:
    ✗ High zero ratio (71.6%) - sensor may be stalled
  temp_out:
    ✓ Healthy
  out_hum:
    ✓ Healthy
  bar:
    ✓ Healthy
  rain:
    ⚠ High null ratio (45.2%) - intermittent data loss
```

**When to Use**: Comprehensive station diagnostics

---

### Example 7: Automated Daily Reports

Create a cron job for daily health monitoring:

```bash
# Edit crontab
crontab -e

# Add this line (runs at 6 AM daily)
0 6 * * * cd /path/to/stream_detection && python anomaly_detector.py --health-check --days 7 --save /var/log/health/report_$(date +\%Y\%m\%d).json >> /var/log/health/health_check.log 2>&1
```

**When to Use**: Continuous monitoring with daily snapshots

---

## Real-World Use Cases

### Use Case 1: Detecting Stalled Wind Sensors

**Problem**: Wind speed sensor at station "grevena" showing mostly zero readings

**Investigation**:

```bash
python anomaly_detector.py --health-check --days 7 --station grevena --variables wind_speed
```

**Result**:

```text
grevena - wind_speed:
  Zero Ratio: 71.6%  ← 🔴 CRITICAL
  Variance: 1.37     ← Abnormally low (normal: 10-80)
  
Diagnosis: Sensor physically stuck or malfunctioning
Action: Schedule on-site inspection
```

**Real Data Comparison**:
- Healthy station (dodoni): 21.5% zero ratio, variance: 18.0
- Problem station (grevena): 71.6% zero ratio, variance: 1.37

---

### Use Case 2: Identifying Communication Failures

**Problem**: Station "kolympari" shows intermittent data loss

**Investigation**:

```bash
python anomaly_detector.py --health-check --days 30 --station kolympari
```

**Expected Output**:

```text
kolympari:
  Null Ratio: 52.3%  ← 🔴 CRITICAL
  Data Completeness: 47.7%
  
Diagnosis: Network/communication issue
Action: Check network connection, power supply
```

---

### Use Case 3: Pre-Maintenance Screening

**Scenario**: Before winter season, check all stations for potential problems

**Command**:

```bash
# Check all stations over last 30 days
python anomaly_detector.py --health-check --days 30 --save pre_winter_check.json

# Extract only critical stations
jq '.[] | select(.overall_status == "critical") | {station_id, issues: [.variable_reports[].issues[]]}' pre_winter_check.json
```

**Output**:

```json
{
  "station_id": "grevena",
  "issues": [
    "High zero ratio (71.6%) - sensor may be stalled"
  ]
}
```

**Action**: Schedule maintenance for identified stations before critical season

---

## Automation Examples

### Example 8: Alert on Critical Status

Script that sends alerts when critical issues are detected:

```bash
#!/bin/bash
# health_check_alert.sh

REPORT_FILE="/tmp/health_check.json"

# Run health check
python anomaly_detector.py --health-check --days 7 --save "$REPORT_FILE"

# Count critical stations
CRITICAL_COUNT=$(jq '[.[] | select(.overall_status == "critical")] | length' "$REPORT_FILE")

if [ "$CRITICAL_COUNT" -gt 0 ]; then
    # Extract critical station names
    CRITICAL_STATIONS=$(jq -r '.[] | select(.overall_status == "critical") | .station_id' "$REPORT_FILE" | tr '\n' ', ')
    
    # Extract issues
    ISSUES=$(jq -r '.[] | select(.overall_status == "critical") | .variable_reports[].issues[]' "$REPORT_FILE")
    
    # Send email alert
    echo -e "Critical sensor health issues detected:\n\nStations: $CRITICAL_STATIONS\n\nIssues:\n$ISSUES" | \
        mail -s "⚠️ ALERT: Critical Sensor Health Issues" admin@example.com
    
    # Send Slack notification
    curl -X POST -H 'Content-type: application/json' \
        --data "{\"text\":\"🔴 Critical sensor health issues at: $CRITICAL_STATIONS\"}" \
        YOUR_SLACK_WEBHOOK_URL
fi
```

Make executable and schedule:

```bash
chmod +x health_check_alert.sh

# Run daily at 8 AM
0 8 * * * /path/to/health_check_alert.sh
```

---

### Example 9: Trend Analysis Dashboard

Python script to track health trends over time:

```python
import json
import pandas as pd
from datetime import datetime, timedelta

def collect_health_metrics(days=30):
    """
    Collect daily health metrics for trend analysis.
    """
    results = []
    
    for day in range(days):
        date = datetime.now() - timedelta(days=day)
        report_file = f"health_reports/report_{date.strftime('%Y%m%d')}.json"
        
        try:
            with open(report_file, 'r') as f:
                data = json.load(f)
            
            for station in data:
                results.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'station_id': station['station_id'],
                    'completeness': station['data_completeness'],
                    'status': station['overall_status'],
                    'zero_ratio': station['variable_reports'][0].get('zero_ratio', 0)
                })
        except FileNotFoundError:
            continue
    
    return pd.DataFrame(results)

# Analyze trends
df = collect_health_metrics(30)

# Find degrading stations
degrading = df.groupby('station_id')['completeness'].apply(
    lambda x: x.iloc[0] - x.iloc[-1] > 0.1  # Completeness dropped > 10%
)

print("Stations with declining health:")
print(degrading[degrading].index.tolist())
```

---

### Example 10: Integration with Grafana

Export metrics for Grafana visualization:

```python
from prometheus_client import Gauge, CollectorRegistry, write_to_textfile
import json
import subprocess

# Create metrics
registry = CollectorRegistry()
data_completeness = Gauge('station_data_completeness', 
                          'Percentage of expected data received',
                          ['station_id'], registry=registry)
zero_ratio = Gauge('station_zero_ratio',
                   'Percentage of zero readings',
                   ['station_id', 'variable'], registry=registry)
health_status = Gauge('station_health_status',
                      'Health status (0=healthy, 1=warning, 2=critical)',
                      ['station_id'], registry=registry)

def export_metrics():
    # Run health check
    subprocess.run([
        "python", "anomaly_detector.py",
        "--health-check", "--days", "7",
        "--save", "/tmp/health_report.json"
    ])
    
    # Load report
    with open('/tmp/health_report.json', 'r') as f:
        report = json.load(f)
    
    # Export metrics
    for station in report:
        station_id = station['station_id']
        
        # Completeness
        data_completeness.labels(station_id=station_id).set(
            station['data_completeness']
        )
        
        # Status
        status_map = {'healthy': 0, 'warning': 1, 'critical': 2}
        health_status.labels(station_id=station_id).set(
            status_map.get(station['overall_status'], 0)
        )
        
        # Variable metrics
        for var_report in station['variable_reports']:
            zero_ratio.labels(
                station_id=station_id,
                variable=var_report['variable']
            ).set(var_report['zero_ratio'])
    
    # Write to file for Prometheus
    write_to_textfile('/var/lib/prometheus/node_exporter/health_metrics.prom', registry)

if __name__ == "__main__":
    export_metrics()
```

Schedule with cron:

```bash
*/5 * * * * /path/to/export_metrics.py
```

---

## Interpretation Guide

### Understanding Zero Ratio

**What it means**: Percentage of sensor readings that are exactly zero

| Zero Ratio | Wind Speed | Temperature | Interpretation |
|------------|------------|-------------|----------------|
| 0-20% | Normal | Abnormal | Calm periods expected for wind |
| 20-30% | Monitor | Critical | Extended calm or minor issue |
| 30-50% | Warning | Critical | Likely sensor problem |
| >50% | Critical | Critical | Sensor definitely stalled |

### Understanding Data Completeness

**What it means**: Percentage of expected observations received

| Completeness | Status | Action |
|--------------|--------|--------|
| 90-100% | Excellent | Continue monitoring |
| 70-89% | Good | Minor issues, monitor |
| 50-69% | Warning | Investigate connection |
| <50% | Critical | Immediate action required |

### Understanding Variance

**What it means**: How much the sensor readings vary over time

**Low variance indicates**: Sensor stuck or not responding to environmental changes

| Variable | Normal Variance | Concerning Variance |
|----------|----------------|---------------------|
| wind_speed | 10-80 | <1.0 |
| temp_out | 5-50 | <0.5 |
| out_hum | 50-200 | <5.0 |
| bar | 1-20 | <0.1 |

---

## Best Practices

### Frequency Recommendations

| Check Type | Frequency | Purpose |
|------------|-----------|---------|
| **Quick Check** | Daily | Catch new issues early |
| **Standard Check** | Weekly (7 days) | Routine monitoring |
| **Detailed Check** | Monthly (30 days) | Trend analysis |
| **Comprehensive Review** | Quarterly (90 days) | Long-term planning |

### Thresholds for Alerts

Configure alerts based on severity:

- **Critical**: Immediate notification (email, SMS, Slack)
  - Zero ratio > 50%
  - Data loss > 50%
  - Variance < 0.1

- **Warning**: Daily digest email
  - Zero ratio 30-50%
  - Data loss 30-50%
  - Completeness < 70%

- **Info**: Weekly report
  - Completeness 70-90%
  - Minor fluctuations

### Maintenance Workflow

1. **Daily**: Automated health check with critical alerts
2. **Weekly**: Review summary report, identify trends
3. **Monthly**: Comprehensive analysis, schedule maintenance
4. **Quarterly**: Performance review, update thresholds

---

For more examples, see:
- [API Overview](../api/overview.md) - Complete parameter reference
- [Device Failure Examples](device-failure.md) - Short-term detection examples
- [FAQ](../faq.md) - Common questions and troubleshooting

