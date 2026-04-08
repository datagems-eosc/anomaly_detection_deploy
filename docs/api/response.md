# Response Format

## Console Output

### Structure

Console output follows this structure:

1. **Header**: Report metadata
2. **Summary**: High-level statistics
3. **Detailed Reports**: Per-station anomaly details
4. **Data Tables**: Supporting evidence (when anomalies found)

### Example Output

```
═══════════════════════════════════════════════
 ANOMALY DETECTION REPORT
═══════════════════════════════════════════════
End Time: 2025-11-22 17:00:00
Window: 6 hours
Method: arima
Spatial Verification: Enabled

Total Stations: 14
Anomalous Stations: 2
Normal Stations: 12

Anomaly Breakdown:
  🔴 Device Failures: 1      <-- CHECK THIS (Real Hardware Issues)
  🌧️ Weather Events: 1       <-- IGNORE THIS (Just Weather)
  ⚠️ Suspected: 0            <-- MANUAL CHECK (Uncertain Cases)

═══════════════════════════════════════════════
 DETAILED REPORTS
═══════════════════════════════════════════════

[ STATION: uth_volos (Volos - University) ]
  ⚠️  Temperature Anomaly:
      Method: arima
      Expected: 12.5°C | Actual: 10.1°C
      • 2025-11-22 17:00:00: 10.10°C -> 🌧️ Extreme Weather / Env Change
        └─ Diag: Trend Consistent (Corr: 0.85, 3 neighbors)

[ STATION: pelion (Pelion Mountain) ]
  🔴 Temperature Anomaly:
      Method: arima
      Expected: 5.2°C | Actual: 99.0°C
      • 2025-11-22 17:00:00: 99.00°C -> 🔴 Device Failure
        └─ Diag: Trend Inconsistent (Corr: 0.05, 2 neighbors)

═══════════════════════════════════════════════
 NEIGHBOR COMPARISON
═══════════════════════════════════════════════

Station: pelion (Anomalous)
Neighbors: zagora (28.5km), volos (32.1km)

Time                 | pelion (°C) | zagora (°C) | volos (°C)
---------------------|-------------|-------------|-------------
2025-11-22 11:00:00  | 5.2         | 8.1         | 10.2
2025-11-22 11:10:00  | 5.3         | 8.0         | 10.3
...
2025-11-22 16:50:00  | 5.1         | 7.9         | 10.1
2025-11-22 17:00:00  | 99.0 ⚠️     | 7.8         | 10.0

Observation: pelion suddenly jumps to 99°C while neighbors remain stable
→ Classification: Device Failure
```

### Summary Section

#### Field Descriptions

| Field | Description | Values |
|-------|-------------|--------|
| End Time | Target timestamp for detection | ISO 8601 format |
| Window | Historical window size | Hours |
| Method | Temporal detection algorithm | arima, 3sigma, etc. |
| Spatial Verification | Whether spatial verify is enabled | Enabled/Disabled |
| Total Stations | Number of monitored stations | Integer |
| Anomalous Stations | Stations with detected anomalies | Integer |
| Normal Stations | Stations with no anomalies | Integer |
| Device Failures | Confirmed hardware issues | **Action required** |
| Weather Events | Extreme weather patterns | No action |
| Suspected | Uncertain cases | Manual review |

#### Interpretation Guide

```
Device Failures: N    → Check N station(s) for hardware issues
Weather Events: M     → Ignore (M station(s) experiencing weather)
Suspected: K          → Review K station(s) manually
```

### Detailed Reports Section

#### Anomaly Entry Format

```
[ STATION: {station_id} ({station_name}) ]
  {icon} {variable} Anomaly:
      Method: {detection_method}
      Expected: {predicted_value} | Actual: {actual_value}
      • {timestamp}: {value} -> {classification_icon} {classification_text}
        └─ Diag: {spatial_diagnosis}
```

#### Icons

| Icon | Meaning |
|------|---------|
| 🔴 | Device Failure |
| 🌧️ | Weather Event |
| ⚠️ | Suspected / Under Review |
| ✅ | Normal (verbose mode) |

#### Spatial Diagnosis

| Text | Interpretation | Correlation Range |
|------|----------------|-------------------|
| Trend Consistent | Neighbors show same pattern | > 0.6 |
| Trend Inconsistent | Only this station anomalous | < 0.3 |
| Trend Unclear | Uncertain correlation | 0.3 - 0.6 |
| Trend Skipped: no_neighbors | No neighbors within radius | N/A |

### Data Tables

When anomalies are detected with spatial verification, the system prints comparison tables:

```
Time                 | suspect | neighbor1 | neighbor2 | neighbor3
---------------------|---------|-----------|-----------|----------
2025-11-22 16:00:00  | 12.5    | 12.8      | 12.3      | 12.6
2025-11-22 16:10:00  | 12.3    | 12.5      | 12.1      | 12.4
2025-11-22 16:20:00  | 12.0    | 12.2      | 11.9      | 12.1
2025-11-22 16:30:00  | 11.8    | 11.9      | 11.6      | 11.8
2025-11-22 16:40:00  | 11.5    | 11.7      | 11.4      | 11.6
2025-11-22 16:50:00  | 11.2    | 11.4      | 11.1      | 11.3
2025-11-22 17:00:00  | 10.1 ⚠️  | 11.2      | 10.9      | 11.1
```

**Purpose**: Allows manual inspection to verify the classification.

---

## JSON Output

### Schema

```json
{
  "metadata": {
    "timestamp": "string (ISO 8601)",
    "window_hours": "integer",
    "temporal_method": "string",
    "temporal_threshold": "float",
    "spatial_verify": "boolean",
    "spatial_method": "string",
    "neighbor_radius": "float",
    "variables": ["string"],
    "database": "string"
  },
  "summary": {
    "total_stations": "integer",
    "anomalous_stations": "integer",
    "normal_stations": "integer",
    "device_failures": "integer",
    "weather_events": "integer",
    "suspected": "integer"
  },
  "anomalies": [
    {
      "station_id": "string",
      "station_name": "string",
      "variable": "string",
      "timestamp": "string (ISO 8601)",
      "actual_value": "float",
      "expected_value": "float",
      "deviation": "float",
      "temporal_method": "string",
      "classification": "string",
      "spatial_verification": {
        "enabled": "boolean",
        "method": "string",
        "correlation": "float",
        "neighbors_checked": "integer",
        "neighbors": ["string"]
      }
    }
  ],
  "normal_stations": ["string"]
}
```

### Full Example

```json
{
  "metadata": {
    "timestamp": "2025-11-22T17:00:00Z",
    "window_hours": 6,
    "temporal_method": "arima",
    "temporal_threshold": 0.95,
    "spatial_verify": true,
    "spatial_method": "pearson",
    "neighbor_radius": 100.0,
    "variables": ["temp_out", "out_hum", "wind_speed", "bar", "rain"],
    "database": "weather_stream.db"
  },
  "summary": {
    "total_stations": 14,
    "anomalous_stations": 2,
    "normal_stations": 12,
    "device_failures": 1,
    "weather_events": 1,
    "suspected": 0
  },
  "anomalies": [
    {
      "station_id": "uth_volos",
      "station_name": "Volos - University",
      "variable": "temp_out",
      "timestamp": "2025-11-22T17:00:00Z",
      "actual_value": 10.1,
      "expected_value": 12.5,
      "deviation": -2.4,
      "temporal_method": "arima",
      "classification": "weather_event",
      "spatial_verification": {
        "enabled": true,
        "method": "pearson",
        "correlation": 0.85,
        "neighbors_checked": 3,
        "neighbors": ["volos", "zagora", "larissa"]
      }
    },
    {
      "station_id": "pelion",
      "station_name": "Pelion Mountain",
      "variable": "temp_out",
      "timestamp": "2025-11-22T17:00:00Z",
      "actual_value": 99.0,
      "expected_value": 5.2,
      "deviation": 93.8,
      "temporal_method": "arima",
      "classification": "device_failure",
      "spatial_verification": {
        "enabled": true,
        "method": "pearson",
        "correlation": 0.05,
        "neighbors_checked": 2,
        "neighbors": ["zagora", "volos"]
      }
    }
  ],
  "normal_stations": [
    "volos",
    "zagora",
    "anavra",
    "domokos",
    "karditsa",
    "larissa",
    "trikala",
    "pyli",
    "metsovo",
    "ioannina",
    "agrinio",
    "preveza"
  ]
}
```

### Field Descriptions

#### Metadata Object

| Field | Type | Description |
|-------|------|-------------|
| timestamp | string | Detection timestamp (ISO 8601) |
| window_hours | integer | Historical window size |
| temporal_method | string | Detection algorithm used |
| temporal_threshold | float | Threshold for temporal detection |
| spatial_verify | boolean | Whether spatial verification was enabled |
| spatial_method | string | Spatial verification method (if enabled) |
| neighbor_radius | float | Neighbor selection radius (km) |
| variables | array | Variables analyzed |
| database | string | Database path/URL |

#### Summary Object

| Field | Type | Description |
|-------|------|-------------|
| total_stations | integer | Total monitored stations |
| anomalous_stations | integer | Stations with anomalies |
| normal_stations | integer | Stations without anomalies |
| device_failures | integer | Confirmed device failures |
| weather_events | integer | Confirmed weather events |
| suspected | integer | Uncertain cases |

#### Anomaly Object

| Field | Type | Description |
|-------|------|-------------|
| station_id | string | Unique station identifier |
| station_name | string | Human-readable station name |
| variable | string | Affected variable (temp_out, etc.) |
| timestamp | string | Anomaly timestamp (ISO 8601) |
| actual_value | float | Measured value |
| expected_value | float | Predicted/expected value |
| deviation | float | Difference (actual - expected) |
| temporal_method | string | Detection method used |
| classification | string | Final classification |
| spatial_verification | object | Spatial verification details |

#### Spatial Verification Object

| Field | Type | Description |
|-------|------|-------------|
| enabled | boolean | Whether spatial verify was used |
| method | string | Verification method (pearson/distance) |
| correlation | float | Average correlation with neighbors |
| neighbors_checked | integer | Number of neighbors compared |
| neighbors | array | List of neighbor station IDs |

#### Classification Values

| Value | Meaning | Action Required |
|-------|---------|----------------|
| "device_failure" | Hardware malfunction | ✅ Yes - Check equipment |
| "weather_event" | Extreme weather | ❌ No - Normal |
| "suspected" | Uncertain | ⚠️ Maybe - Manual review |

---

## CSV Output (Future)

Flattened format for spreadsheet analysis:

```csv
timestamp,station_id,station_name,variable,actual,expected,deviation,method,classification,correlation,neighbors
2025-11-22T17:00:00Z,uth_volos,Volos - University,temp_out,10.1,12.5,-2.4,arima,weather_event,0.85,3
2025-11-22T17:00:00Z,pelion,Pelion Mountain,temp_out,99.0,5.2,93.8,arima,device_failure,0.05,2
```

## HTML Output (Future)

Rich formatted report with charts and tables:

- Summary dashboard
- Station-by-station cards
- Time series plots
- Correlation heatmaps
- Interactive maps

---

## Exit Codes

Programs can check the exit code for automation:

```bash
python anomaly_detector.py --end "NOW" --spatial-verify
EXITCODE=$?

if [ $EXITCODE -eq 0 ]; then
    echo "Detection completed successfully"
elif [ $EXITCODE -eq 1 ]; then
    echo "Error occurred"
    exit 1
elif [ $EXITCODE -eq 2 ]; then
    echo "Database error"
    exit 2
fi
```

| Exit Code | Meaning | stdout | stderr |
|-----------|---------|--------|--------|
| 0 | Success | Report | Empty |
| 1 | General error | Partial report | Error message |
| 2 | Database error | Empty | Error message |
| 3 | Invalid parameters | Empty | Usage help |
| 4 | Insufficient data | Empty | Error message |

---

## Programmatic Parsing

### Parsing JSON with Python

```python
import json

with open('report.json', 'r') as f:
    report = json.load(f)

# Check for device failures
if report['summary']['device_failures'] > 0:
    for anomaly in report['anomalies']:
        if anomaly['classification'] == 'device_failure':
            print(f"ALERT: {anomaly['station_id']} - {anomaly['variable']}")
            send_alert(anomaly)
```

### Parsing JSON with jq

```bash
# Extract device failures only
cat report.json | jq '.anomalies[] | select(.classification == "device_failure")'

# Count anomalies by type
cat report.json | jq '.summary'

# Get affected station IDs
cat report.json | jq -r '.anomalies[].station_id'
```

### Parsing Console Output

For scripts that cannot use JSON:

```bash
# Extract device failure count
python anomaly_detector.py | grep "Device Failures" | awk '{print $3}'

# Check if any device failures exist
if python anomaly_detector.py | grep -q "Device Failures: [1-9]"; then
    echo "Device failures detected!"
fi
```

