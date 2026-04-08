# Configuration

## Overview

The Real-Time Anomaly Detection system can be configured through:

1. **Command-line arguments** (highest priority)
2. **Environment variables**
3. **Default values** (lowest priority)

---

## Collector Configuration

### Data Source

The collector fetches data from the NOA API:

**Default URL**: `https://stratus.meteo.noa.gr/data/stations/latestValues_Datagems.geojson`

To use a different data source, edit `streaming_collector_sqlite.py`:

```python
# Change this line
API_URL = "https://your-custom-api.example.com/data.geojson"
```

### Collection Interval

**Default**: 10 minutes

To change the interval, edit `streaming_collector_sqlite.py`:

```python
# Change this value (in seconds)
COLLECTION_INTERVAL = 600  # 10 minutes
```

**Recommendations**:

| Interval | Use Case | Disk Usage |
|----------|----------|------------|
| 5 min | High-resolution monitoring | 20MB/month |
| 10 min | **Default** (balanced) | 10MB/month |
| 30 min | Low-frequency monitoring | 3MB/month |
| 60 min | Historical trends only | 1.5MB/month |

!!! warning "API Rate Limits"
    The NOA API updates every 10 minutes. Setting intervals < 10 minutes will fetch duplicate data.

### Database Path

**Default**: `weather_stream.db` (current directory)

To change:

```bash
# Option 1: Edit streaming_collector_sqlite.py
DATABASE_PATH = "/var/lib/weather/stream.db"

# Option 2: Use environment variable
export WEATHER_DB="/var/lib/weather/stream.db"
python streaming_collector_sqlite.py
```

---

## Detector Configuration

### Default Parameters

Create a configuration file for convenience:

```bash
# config.env
export DETECTION_METHOD="arima"
export DETECTION_WINDOW=6
export SPATIAL_VERIFY=1
export NEIGHBOR_RADIUS=100
export DATABASE_PATH="weather_stream.db"
```

Load before running:

```bash
source config.env
python anomaly_detector.py --end "NOW"
```

### Detection Method

**Default**: ARIMA

To change default, edit `anomaly_detector.py`:

```python
parser.add_argument('--temporal-method', default='arima', ...)
```

**Method Selection Matrix**:

| Scenario | Recommended Method |
|----------|-------------------|
| Production (accuracy) | arima |
| Testing (speed) | 3sigma |
| Noisy data | mad |
| Exploratory | iqr |
| Multidimensional | isolation_forest |

### Window Size

**Default**: 6 hours

Adjust based on data patterns:

```bash
# Short-term anomalies (sensor glitches)
--window 1

# Standard weather patterns (recommended)
--window 6

# Daily cycles (temperature, humidity)
--window 24

# Multi-day trends
--window 48
```

### Spatial Verification

**Default**: Disabled (for backward compatibility)

**Recommendation**: Always enable in production

```bash
# Enable (recommended)
python anomaly_detector.py --spatial-verify

# Disable (testing only)
python anomaly_detector.py
```

### Correlation Thresholds

**Defaults**:

- High threshold: 0.6 (weather event)
- Low threshold: 0.3 (device failure)

Tune based on your environment:

```bash
# More strict (fewer weather events)
--correlation-threshold-high 0.7 \
--correlation-threshold-low 0.2

# More lenient (more weather events)
--correlation-threshold-high 0.5 \
--correlation-threshold-low 0.4
```

**Effect**:

```
High = 0.7, Low = 0.3:
  [0.0 - 0.3): Device Failure
  [0.3 - 0.7): Suspected
  [0.7 - 1.0]: Weather Event

High = 0.6, Low = 0.3 (default):
  [0.0 - 0.3): Device Failure
  [0.3 - 0.6): Suspected
  [0.6 - 1.0]: Weather Event
```

### Neighbor Radius

**Default**: 100 km

Adjust based on terrain:

| Terrain Type | Recommended Radius | Reason |
|--------------|-------------------|--------|
| Flat plains | 100-150 km | Weather systems move uniformly |
| Mountains | 50-75 km | Microclimates |
| Coastal | 75-100 km | Land-sea interaction |
| Urban | 50 km | Heat islands |
| Sparse network | 150-200 km | Need enough neighbors |

```bash
# Mountain region
--neighbor-radius 50

# Flat plains
--neighbor-radius 150
```

---

## Station Configuration

### Station Metadata

Station information is automatically fetched from the NOA API. To manually override, create `stations.json`:

```json
{
  "uth_volos": {
    "name": "University of Thessaly - Volos",
    "lat": 39.3636,
    "lon": 22.9530,
    "elevation": 15,
    "enabled": true
  },
  "volos": {
    "name": "Volos City Center",
    "lat": 39.3620,
    "lon": 22.9467,
    "elevation": 5,
    "enabled": true
  }
}
```

### Disabling Stations

To exclude specific stations from analysis:

```bash
# Edit anomaly_detector.py
EXCLUDED_STATIONS = ['metsovo', 'preveza']  # Isolated stations
```

Or use command-line filter (future feature):

```bash
python anomaly_detector.py --exclude-stations "metsovo,preveza"
```

---

## Variable Configuration

### Enabled Variables

**Default**: All variables (temp_out, out_hum, wind_speed, bar, rain)

To analyze specific variables only:

```bash
# Temperature only
python anomaly_detector.py --variables "temp_out"

# Temperature and pressure
python anomaly_detector.py --variables "temp_out,bar"
```

### Variable-Specific Thresholds

For advanced tuning, edit the detector configuration:

```python
# In anomaly_detector.py
VARIABLE_THRESHOLDS = {
    'temp_out': {'method': 'arima', 'threshold': 0.95},
    'out_hum': {'method': 'arima', 'threshold': 0.90},
    'wind_speed': {'method': 'mad', 'threshold': 4.0},
    'bar': {'method': '3sigma', 'threshold': 3.0},
    'rain': {'method': 'iqr', 'threshold': 1.5}
}
```

**Rationale**:

- **Temperature**: Smooth trends → ARIMA
- **Humidity**: Similar to temperature → ARIMA
- **Wind Speed**: Very volatile → MAD (robust)
- **Pressure**: Stable baseline → 3-Sigma (fast)
- **Rainfall**: Sparse, many zeros → IQR

---

## Logging Configuration

### Log Levels

**Default**: INFO

```python
# In streaming_collector_sqlite.py or anomaly_detector.py
import logging

# Change log level
logging.basicConfig(level=logging.DEBUG)  # Verbose
logging.basicConfig(level=logging.INFO)   # Default
logging.basicConfig(level=logging.WARNING) # Quiet
```

### Log Files

**Default**: Console output + `streaming_collector.log`

To customize:

```python
# In streaming_collector_sqlite.py
LOG_FILE = "/var/log/weather/collector.log"

# Add file handler
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setLevel(logging.INFO)
logger.addHandler(file_handler)
```

### Log Rotation

For production, use `logrotate`:

```bash
# Create /etc/logrotate.d/weather-collector
cat > /etc/logrotate.d/weather-collector << 'EOF'
/var/log/weather/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
    create 0640 weather weather
}
EOF
```

---

## Performance Tuning

### Database Optimization

#### SQLite Configuration

```python
# In streaming_collector_sqlite.py
conn = sqlite3.connect('weather_stream.db')

# Enable WAL mode for better concurrency
conn.execute('PRAGMA journal_mode=WAL')

# Increase cache size (10MB)
conn.execute('PRAGMA cache_size=-10000')

# Synchronous mode (balance safety vs speed)
conn.execute('PRAGMA synchronous=NORMAL')
```

#### Vacuum Database Periodically

```bash
# Add to cron (weekly)
0 2 * * 0 sqlite3 /path/to/weather_stream.db 'VACUUM;'
```

### Memory Usage

Limit memory for large windows:

```python
# In anomaly_detector.py
import resource

# Limit to 1GB
resource.setrlimit(resource.RLIMIT_AS, (1024*1024*1024, 1024*1024*1024))
```

### Parallel Processing (Future)

Enable multi-station parallel detection:

```python
# Future feature
python anomaly_detector.py --end "NOW" --spatial-verify --parallel --workers 4
```

---

## Security Configuration

### Database Permissions

```bash
# Restrict database access
chmod 600 weather_stream.db
chown weather:weather weather_stream.db
```

### Network Security

The collector uses HTTPS by default. To add authentication:

```python
# In streaming_collector_sqlite.py
import requests

# Add authentication
response = requests.get(API_URL, auth=('username', 'password'))
```

### Sandboxing

Run collector as limited user:

```bash
# Create dedicated user
sudo useradd -r -s /bin/false weather

# Run as this user
sudo -u weather python streaming_collector_sqlite.py
```

---

## Environment-Specific Configuration

### Development

```bash
# config_dev.env
export WEATHER_DB="dev_weather.db"
export DETECTION_METHOD="3sigma"  # Faster
export COLLECTION_INTERVAL=300    # 5 min for testing
export LOG_LEVEL="DEBUG"
```

### Production

```bash
# config_prod.env
export WEATHER_DB="/var/lib/weather/stream.db"
export DETECTION_METHOD="arima"
export COLLECTION_INTERVAL=600    # 10 min
export LOG_LEVEL="INFO"
export ENABLE_ALERTS=1
```

### Testing

```bash
# config_test.env
export WEATHER_DB=":memory:"      # In-memory DB
export DETECTION_METHOD="3sigma"
export LOG_LEVEL="WARNING"
```

---

## Configuration Validation

### Validate Settings

```python
#!/usr/bin/env python3
# validate_config.py

import sys

def validate_config():
    errors = []
    
    # Check database path
    import os
    if not os.access(os.path.dirname(DATABASE_PATH) or '.', os.W_OK):
        errors.append(f"Database path not writable: {DATABASE_PATH}")
    
    # Check collection interval
    if COLLECTION_INTERVAL < 60:
        errors.append(f"Collection interval too short: {COLLECTION_INTERVAL}s")
    
    # Check neighbor radius
    if NEIGHBOR_RADIUS < 10 or NEIGHBOR_RADIUS > 500:
        errors.append(f"Neighbor radius out of range: {NEIGHBOR_RADIUS}km")
    
    if errors:
        print("Configuration Errors:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("✅ Configuration valid")

if __name__ == "__main__":
    validate_config()
```

Run before deployment:

```bash
python validate_config.py
```

---

## Configuration Examples

### Example 1: High-Accuracy Production

```bash
python anomaly_detector.py \
  --end "NOW" \
  --window 6 \
  --temporal-method arima \
  --spatial-verify \
  --neighbor-radius 100 \
  --correlation-threshold-high 0.6 \
  --correlation-threshold-low 0.3 \
  --save "/var/log/anomaly_reports/report_$(date +%Y%m%d_%H%M%S).json"
```

### Example 2: Fast Testing

```bash
python anomaly_detector.py \
  --end "NOW" \
  --window 1 \
  --temporal-method 3sigma \
  --variables "temp_out"
```

### Example 3: Conservative (Few False Alarms)

```bash
python anomaly_detector.py \
  --end "NOW" \
  --temporal-method arima \
  --temporal-threshold 0.99 \
  --spatial-verify \
  --correlation-threshold-high 0.7 \
  --correlation-threshold-low 0.2
```

---

For deployment-specific configurations, see [Deployment Guide](deployment.md).

