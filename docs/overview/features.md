# Key Features

## Two Detection Modes

This system provides two complementary detection capabilities:

1. **Short-Term Detection**: Real-time anomaly detection (hours) using dual-verification
2. **Long-Term Health Monitoring**: Sensor health tracking (days/weeks) for chronic issues 🆕

## Dual-Verification Strategy (Short-Term)

The core innovation of the short-term detection system is its ability to distinguish between device failures and extreme weather events through a two-step verification process.

### Why This Matters

Traditional anomaly detection systems generate numerous false alarms when extreme weather events occur, because they cannot distinguish between:

- **Genuine Equipment Failure**: Only one station is malfunctioning
- **Extreme Weather Event**: Multiple stations show similar anomalous patterns

Our dual-verification approach solves this by combining:

1. **Temporal Analysis** (Self-Check): "Is this station behaving differently than usual?"
2. **Spatial Verification** (Neighbor-Check): "Are nearby stations behaving similarly?"

## Multi-Method Detection

The system supports seven different temporal detection algorithms:

| Method | Best For | Computational Cost |
|--------|----------|-------------------|
| ARIMA | Complex trends, seasonal patterns | High |
| 3-Sigma | Quick outlier detection | Low |
| MAD | Robust to outliers | Medium |
| IQR | Exploratory analysis | Low |
| Isolation Forest | Multidimensional patterns | High |
| STL | Strong seasonality | High |
| LOF | Density-based outliers | Medium |

!!! tip "Recommended Method"
    For weather data, **ARIMA** provides the best balance between accuracy and false alarm reduction.

## Real-Time Processing

### Streaming Architecture

- **Ingestion Frequency**: Data collected every 10 minutes
- **Detection Window**: Configurable (default: 6 hours)
- **Sliding Stride**: Moves forward with each new data point
- **Latency**: Near real-time detection (< 1 minute processing time)

### Memory Efficiency

The sliding window mechanism ensures:

- **Constant Memory Usage**: O(1) regardless of database size
- **Fast Query Performance**: Only queries relevant time ranges
- **Scalable Storage**: Old data remains accessible but not loaded into memory

## Spatial Intelligence

### Neighbor Detection

The system automatically:

1. Calculates distances between all station pairs
2. Identifies neighbors within 100km radius
3. Computes correlation coefficients during anomalies
4. Interpolates missing data to ensure robust comparison

### Correlation Thresholds

| Correlation | Interpretation | Action |
|-------------|----------------|--------|
| > 0.6 | High correlation - Weather event | Ignore |
| 0.3 - 0.6 | Uncertain - Requires manual review | Flag as "Suspected" |
| < 0.3 | Low correlation - Device failure | Alert |

!!! note "Missing Data Handling"
    When neighbor data has gaps, the system uses **linear interpolation** to fill missing values before computing correlations.

## Scalable Database Backend

### SQLite Mode (Default)

Perfect for:

- Standalone deployment
- Development and testing
- Single-server installations
- < 100 stations

### TimescaleDB Mode (Enterprise)

Recommended for:

- Multi-server deployment
- > 100 stations
- Years of historical data
- Advanced analytics queries

Migration between backends requires minimal code changes - only the connection string needs updating.

## Interactive Visualization

The system generates:

- **Station Network Maps**: Interactive HTML maps showing station locations and neighbor connections
- **Anomaly Reports**: JSON format for integration with monitoring dashboards
- **Console Output**: Human-readable summaries for manual inspection

View an example: [Station Network Map](../system/station-network.md)

## API-First Design

While currently used as a command-line tool, the detection engine is designed with clear interfaces:

- Input: Time window + detection parameters
- Output: Structured anomaly reports
- Future-ready: Can be easily wrapped in a REST API

## Long-Term Health Monitoring 🆕

### Overview

In addition to real-time anomaly detection, the system now provides long-term health monitoring to detect chronic sensor problems that develop over days or weeks.

### What It Detects

#### Stalled Sensors

Detects sensors that are physically stuck or malfunctioning:

- **Metric**: Zero Ratio - percentage of zero readings
- **Threshold**: > 30% zero values over analysis period
- **Common Cause**: Wind speed sensors stuck at zero due to mechanical failure
- **Example**: Station "grevena" showed 71.6% zero readings over 7 days

#### Data Loss

Identifies communication failures or sensor outages:

- **Metric**: Null Ratio - percentage of missing observations
- **Threshold**: > 50% missing data
- **Common Cause**: Network issues, power failures, sensor disconnection
- **Impact**: Unreliable data for analysis and forecasting

#### Sensor Degradation

Flags sensors that are stuck or not responding to environmental changes:

- **Metric**: Variance - statistical measure of data variability
- **Threshold**: < 0.1 for variables that should naturally fluctuate
- **Common Cause**: Sensor aging, calibration drift, physical obstruction
- **Example**: Wind sensor showing constant low values despite changing conditions

#### Data Completeness

Tracks overall data availability per station:

- **Metric**: Percentage of expected observations received
- **Expected**: ~144 observations per day (10-minute intervals)
- **Analysis**: Shows trends in data reliability over time
- **Use Case**: Identify stations requiring maintenance

### Usage

```bash
# Check all stations for the last 7 days
python anomaly_detector.py --health-check --days 7

# Check specific station over 30 days
python anomaly_detector.py --health-check --days 30 --station grevena

# Generate JSON report for monitoring integration
python anomaly_detector.py --health-check --days 7 --save health_report.json
```

### Output Format

#### Console Summary

```text
Station              Status       Completeness    Issues
--------------------------------------------------------------------------------
grevena              🔴 CRITICAL  58.0%           1 problems
  └─ wind_speed: High zero ratio (71.6%) - sensor may be stalled
dodoni               ✅ HEALTHY   57.6%           0 problems
volos                ✅ HEALTHY   57.9%           0 problems
```

#### JSON Report

```json
{
  "station_id": "grevena",
  "analysis_period_days": 7,
  "data_completeness": 0.58,
  "total_data_points": 585,
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
```

### Severity Levels

| Level | Criteria | Action |
|-------|----------|--------|
| **Healthy** | All metrics within normal ranges | Routine monitoring |
| **Warning** | Minor issues detected | Schedule inspection |
| **Critical** | Severe problems detected | Immediate maintenance required |

### Integration

The JSON reports are designed for easy integration with:

- **Monitoring Dashboards**: Grafana, Kibana, custom dashboards
- **Alerting Systems**: Email, Slack, PagerDuty notifications
- **Maintenance Scheduling**: Automated ticket creation
- **Quality Assurance**: Long-term performance tracking

### Complementary to Short-Term Detection

Long-term health monitoring complements real-time detection:

- **Short-Term**: Catches sudden failures (sensor crash, extreme events)
- **Long-Term**: Identifies gradual degradation (sensor drift, increasing data loss)
- **Together**: Comprehensive coverage of all failure modes

## Extensibility

Adding new features is straightforward:

- **New Detection Methods**: Implement the `TemporalDetector` interface
- **New Variables**: Add to the database schema and detector configuration
- **New Spatial Methods**: Extend the `SpatialVerifier` class
- **New Data Sources**: Replace the collector module
- **New Health Metrics**: Extend the `HealthChecker` class with custom thresholds

