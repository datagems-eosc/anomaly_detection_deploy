# Parameters Reference

Complete reference for all command-line parameters and configuration options.

## Command-Line Parameters

### Detection Window

#### `--end`

Specifies the target timestamp for anomaly detection.

| Property | Value |
|----------|-------|
| Type | String |
| Default | "NOW" |
| Required | No |
| Example | `--end "2025-11-22 17:00:00"` |

**Accepted Formats**:

```bash
# Current time
--end "NOW"

# ISO 8601 format
--end "2025-11-22T17:00:00"
--end "2025-11-22 17:00:00"

# Unix timestamp
--end "1732294800"
```

**Use Cases**:

- Real-time monitoring: `--end "NOW"`
- Historical analysis: `--end "2025-11-01 12:00:00"`
- Batch processing: Loop through timestamps

---

#### `--window`

Length of historical data to analyze (in hours).

| Property | Value |
|----------|-------|
| Type | Integer |
| Default | 6 |
| Unit | Hours |
| Range | 1-48 |
| Example | `--window 6` |

**Guidelines**:

| Window Size | Data Points (10min) | Use Case |
|-------------|---------------------|----------|
| 1 hour | 6 | Quick checks, testing |
| 6 hours | 36 | **Recommended** for ARIMA |
| 12 hours | 72 | Capturing half-day cycles |
| 24 hours | 144 | Full daily cycle (for STL) |
| 48 hours | 288 | Multi-day analysis |

!!! warning "Performance Impact"
    Larger windows increase computation time, especially for ARIMA and STL methods.

---

### Temporal Detection

#### `--temporal-method`

Algorithm for temporal anomaly detection.

| Property | Value |
|----------|-------|
| Type | String (enum) |
| Default | "arima" |
| Options | `arima`, `3sigma`, `mad`, `iqr`, `isolation_forest`, `stl`, `lof` |
| Example | `--temporal-method arima` |

**Method Selection Guide**:

=== "For Accuracy"

    1. **arima** - Best overall
    2. **stl** - If strong daily seasonality
    3. **isolation_forest** - For multivariate patterns

=== "For Speed"

    1. **3sigma** - Fastest
    2. **iqr** - Very fast
    3. **mad** - Fast and robust

=== "For Robustness"

    1. **mad** - Most robust to outliers
    2. **iqr** - Robust, simple
    3. **arima** - Adapts to trends

**Detailed Comparison**: See [Detection Methods](../system/detection-methods.md)

---

#### `--temporal-threshold`

Threshold for temporal anomaly detection (method-specific).

| Property | Value |
|----------|-------|
| Type | Float |
| Default | Method-dependent |
| Example | `--temporal-threshold 3.0` |

**Default Thresholds by Method**:

| Method | Default | Interpretation | Adjustable Range |
|--------|---------|----------------|------------------|
| arima | 0.95 | Confidence level | 0.90 - 0.99 |
| 3sigma | 3.0 | Standard deviations | 2.0 - 4.0 |
| mad | 3.5 | MAD units | 2.5 - 5.0 |
| iqr | 1.5 | IQR multiplier | 1.0 - 3.0 |
| isolation_forest | 0.1 | Contamination rate | 0.05 - 0.2 |
| stl | 3.0 | Residual sigma | 2.0 - 4.0 |
| lof | 0.1 | Contamination rate | 0.05 - 0.2 |

**Tuning**:

- **Lower threshold** → More sensitive → More detections (higher recall)
- **Higher threshold** → Less sensitive → Fewer detections (higher precision)

---

### Spatial Verification

#### `--spatial-verify`

Enable spatial verification to distinguish weather events from device failures.

| Property | Value |
|----------|-------|
| Type | Boolean flag |
| Default | False |
| Example | `--spatial-verify` |

**Impact**:

| Metric | Without | With |
|--------|---------|------|
| False Positives | ~40% | ~5% |
| True Positives | 100% | 100% |
| Processing Time | 100% | 120% |

!!! tip "Production Recommendation"
    **Always enable** spatial verification in production environments to reduce false alarms.

---

#### `--spatial-method`

Method for spatial verification.

| Property | Value |
|----------|-------|
| Type | String (enum) |
| Default | "pearson" |
| Options | `pearson`, `distance` |
| Example | `--spatial-method pearson` |

**Method Comparison**:

| Method | Measures | Advantages | Disadvantages |
|--------|----------|------------|---------------|
| pearson | Trend correlation | Robust to different baselines | Requires sufficient data |
| distance | Value deviation | Simple, fast | Sensitive to baseline differences |

---

#### `--neighbor-radius`

Maximum distance (in kilometers) for neighbor selection.

| Property | Value |
|----------|-------|
| Type | Float |
| Default | 100.0 |
| Unit | Kilometers |
| Range | 10 - 500 |
| Example | `--neighbor-radius 100` |

**Tuning Guidelines**:

| Scenario | Recommended Radius | Rationale |
|----------|-------------------|-----------|
| Dense urban | 50 km | High station density |
| Rural plains | 100 km | **Default** |
| Mountainous | 50 km | Microclimates |
| Sparse network | 150-200 km | Find enough neighbors |
| Continental scale | 200-500 km | Large-scale phenomena |

---

#### `--correlation-threshold-high`

Minimum correlation to classify as "weather event".

| Property | Value |
|----------|-------|
| Type | Float |
| Default | 0.6 |
| Range | 0.5 - 0.9 |
| Example | `--correlation-threshold-high 0.6` |

**Impact**:

- **Lower** (e.g., 0.5): More anomalies classified as weather events
- **Higher** (e.g., 0.8): Stricter criteria, fewer weather events

---

#### `--correlation-threshold-low`

Maximum correlation to classify as "device failure".

| Property | Value |
|----------|-------|
| Type | Float |
| Default | 0.3 |
| Range | 0.1 - 0.4 |
| Example | `--correlation-threshold-low 0.3` |

**Impact**:

- **Lower** (e.g., 0.2): Stricter criteria for device failures
- **Higher** (e.g., 0.4): More anomalies classified as device failures

---

### Variables

#### `--variables`

Comma-separated list of variables to analyze.

| Property | Value |
|----------|-------|
| Type | String (comma-separated) |
| Default | "temp_out,out_hum,wind_speed,bar,rain" |
| Example | `--variables "temp_out,bar"` |

**Available Variables**:

| Variable | Description | Unit | Typical Range |
|----------|-------------|------|---------------|
| temp_out | Outdoor temperature | °C | -10 to 40 |
| out_hum | Outdoor humidity | % | 0 to 100 |
| wind_speed | Wind speed | km/h | 0 to 100 |
| bar | Barometric pressure | hPa | 950 to 1050 |
| rain | Rainfall rate | mm | 0 to 50 |

**Use Cases**:

```bash
# Only temperature (fastest)
--variables "temp_out"

# Temperature and pressure (common failure indicators)
--variables "temp_out,bar"

# All variables except wind (wind is noisy)
--variables "temp_out,out_hum,bar,rain"
```

---

### Output

#### `--save`

Save detection report to JSON file.

| Property | Value |
|----------|-------|
| Type | String (file path) |
| Default | None (console only) |
| Example | `--save report.json` |

**Examples**:

```bash
# Simple filename
--save report.json

# With timestamp
--save "report_$(date +%Y%m%d_%H%M%S).json"

# Full path
--save "/var/log/anomaly_reports/report.json"

# Method-specific
--save "report_${METHOD}_$(date +%Y%m%d).json"
```

---

#### `--output-format`

Output format for saved reports.

| Property | Value |
|----------|-------|
| Type | String (enum) |
| Default | "json" |
| Options | `json`, `csv`, `html` |
| Example | `--output-format json` |

**Format Comparison**:

| Format | Use Case | Parseable | Human-Readable |
|--------|----------|-----------|----------------|
| json | API integration, storage | ✅ | ⚠️ |
| csv | Spreadsheet analysis | ✅ | ✅ |
| html | Email reports, dashboards | ❌ | ✅✅ |

---

#### `--verbose`

Enable detailed debug output.

| Property | Value |
|----------|-------|
| Type | Boolean flag |
| Default | False |
| Example | `--verbose` |

**Output Difference**:

=== "Standard"

    ```
    Total Stations: 14
    Anomalous Stations: 1
    Device Failures: 0
    ```

=== "Verbose"

    ```
    [DEBUG] Connecting to database: weather_stream.db
    [DEBUG] Loading station metadata...
    [DEBUG] Found 14 stations
    [DEBUG] Querying data window: 2025-11-22 11:00:00 to 17:00:00
    [DEBUG] Retrieved 504 observations (14 stations × 36 timestamps)
    [DEBUG] Starting temporal detection (method: arima)
    [DEBUG] Station uth_volos: Analyzing temp_out...
    [DEBUG] ARIMA model fit: AIC=125.4, BIC=130.2
    [DEBUG] Forecast: 12.5°C ± 1.8°C (95% CI)
    [DEBUG] Actual: 10.1°C
    [DEBUG] Anomaly detected: Outside confidence interval
    [DEBUG] Starting spatial verification...
    [DEBUG] Found 3 neighbors within 100km
    [DEBUG] Pearson correlation: 0.85 (high)
    [DEBUG] Classification: Weather Event
    Total Stations: 14
    Anomalous Stations: 1
    Device Failures: 0
    ```

---

### Database

#### `--database`

Path to SQLite database or PostgreSQL connection string.

| Property | Value |
|----------|-------|
| Type | String (path or URL) |
| Default | "weather_stream.db" |
| Example | `--database /path/to/db.sqlite` |

**Examples**:

```bash
# SQLite (relative path)
--database weather_stream.db

# SQLite (absolute path)
--database /var/lib/weather/stream.db

# PostgreSQL / TimescaleDB
--database "postgresql://user:pass@localhost:5432/weather"
```

---

## Configuration File (Future)

For convenience, parameters can be saved in a configuration file:

```yaml
# anomaly_detection_config.yaml

detection:
  window_hours: 6
  temporal_method: arima
  temporal_threshold: 0.95

spatial:
  enabled: true
  method: pearson
  neighbor_radius: 100
  correlation_threshold_high: 0.6
  correlation_threshold_low: 0.3

variables:
  - temp_out
  - out_hum
  - wind_speed
  - bar
  - rain

output:
  save_path: /var/log/anomaly_reports
  format: json
  verbose: false

database:
  path: weather_stream.db
```

Usage:

```bash
python anomaly_detector.py --config anomaly_detection_config.yaml
```

!!! note "Roadmap Feature"
    Configuration file support is planned for a future release.

## Environment Variables

Some parameters can be set via environment variables:

| Variable | Equivalent Parameter | Example |
|----------|---------------------|---------|
| `WEATHER_DB` | `--database` | `export WEATHER_DB=/path/to/db` |
| `DETECTION_METHOD` | `--temporal-method` | `export DETECTION_METHOD=arima` |
| `SPATIAL_VERIFY` | `--spatial-verify` | `export SPATIAL_VERIFY=1` |

Priority order (highest to lowest):

1. Command-line arguments
2. Configuration file (future)
3. Environment variables
4. Default values

## Validation

The system validates all parameters before execution:

### Invalid Parameter Example

```bash
$ python anomaly_detector.py --window 0
Error: --window must be >= 1

$ python anomaly_detector.py --temporal-method invalid
Error: --temporal-method must be one of: arima, 3sigma, mad, iqr, isolation_forest, stl, lof

$ python anomaly_detector.py --neighbor-radius -10
Error: --neighbor-radius must be positive
```

### Warnings

Some combinations trigger warnings but don't fail:

```bash
$ python anomaly_detector.py --window 1 --temporal-method arima
Warning: ARIMA works best with window >= 6 hours. Results may be inaccurate.

$ python anomaly_detector.py --temporal-method 3sigma --window 24
Warning: Window size of 24 hours is excessive for 3-sigma. Consider reducing to 6 hours.
```

