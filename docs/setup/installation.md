# Installation

## Prerequisites

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Linux/macOS | Linux (Ubuntu 20.04+) |
| Python | 3.8+ | 3.10+ |
| RAM | 512MB | 2GB |
| Disk | 1GB | 10GB |
| CPU | 1 core | 2+ cores |

### Software Dependencies

- Python 3.8 or higher
- pip (Python package manager)
- SQLite 3 (included with Python)
- Git (for cloning repository)

---

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/datagems-eosc/real-time-anomaly-detection.git
cd real-time-anomaly-detection/stream_detection
```

### 2. Create Virtual Environment

```bash
# Using venv
python3 -m venv venv
source venv/bin/activate

# Or using conda
conda create -n datagem python=3.10
conda activate datagem
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Verify Installation

```bash
python anomaly_detector.py --help
```

Expected output:

```
usage: anomaly_detector.py [-h] [--end END] [--window WINDOW] ...

Real-Time Weather Anomaly Detection System
...
```

### 5. Test Data Collection

```bash
# Start data collector (background)
./manage_collector.sh start

# Wait 30 seconds for first data fetch
sleep 30

# Check database
sqlite3 weather_stream.db "SELECT COUNT(*) FROM observations;"
```

Expected: Number > 0 (should have data from ~14 stations)

### 6. Run First Detection

```bash
python anomaly_detector.py --end "NOW" --spatial-verify
```

If no data yet:

```bash
# Wait for more data collection
sleep 600  # 10 minutes

# Try again
python anomaly_detector.py --end "NOW" --spatial-verify
```

---

## Detailed Installation

### Python Environment Setup

#### Conda (Recommended)

```bash
# Create environment with specific Python version
conda create -n datagem python=3.10

# Activate
conda activate datagem

# Install pip dependencies
pip install -r requirements.txt
```

---

### Installing Dependencies

#### From requirements.txt

```bash
pip install -r requirements.txt
```

#### Manual Installation

```bash
# Core dependencies
pip install pandas numpy

# Time series analysis
pip install statsmodels

# Machine learning
pip install scikit-learn

# Visualization
pip install folium

# Database (optional, for TimescaleDB)
pip install psycopg2-binary
```

#### Verify Installation

```python
python3 << EOF
import pandas
import numpy
import statsmodels
import sklearn
import folium
print("All dependencies installed successfully!")
EOF
```

---

## Verifying Installation

### Manual Verification

```bash
# 1. Check Python version
python --version
# Should be 3.8 or higher

# 2. Check dependencies
pip list | grep -E '(pandas|statsmodels|scikit-learn)'

# 3. Test database access
python << EOF
import sqlite3
conn = sqlite3.connect('weather_stream.db')
print("Database access OK")
conn.close()
EOF

# 4. Test data collection
python streaming_collector_sqlite.py --test

# 5. Test detection (requires data)
python anomaly_detector.py --end "NOW" --temporal-method 3sigma
```

---

## Directory Structure

After installation:

```
stream_detection/
├── anomaly_detector.py           # Main detection script
├── streaming_collector_sqlite.py # Data collector
├── manage_collector.sh            # Service management
├── requirements.txt               # Python dependencies
├── weather_stream.db              # SQLite database (created on first run)
├── spatial_network_map.html       # Station map (optional)
├── docs/                          # Documentation (if using MkDocs)
└── README.md                      # Original README
```

---

## Next Steps

After successful installation:

1. **Configure the system**: See [Configuration](configuration.md)
2. **Deploy the collector**: See [Deployment](deployment.md)
3. **Set up monitoring**: See monitoring documentation (coming soon)
4. **Read API documentation**: See [API Overview](../api/overview.md)


