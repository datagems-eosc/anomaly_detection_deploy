# Deployment

## Overview

This guide covers deploying the Real-Time Anomaly Detection system in production environments.

## Deployment Options

### Option 1: Systemd Service (Recommended for Linux)
### Option 2: Docker Container
### Option 3: Cron Jobs
### Option 4: Kubernetes (Enterprise)

---

## Option 1: Systemd Service

### Step 1: Create Service User

```bash
# Create dedicated user
sudo useradd -r -s /bin/false -m -d /var/lib/weather weather

# Create directories
sudo mkdir -p /var/lib/weather/data
sudo mkdir -p /var/log/weather
sudo chown -R weather:weather /var/lib/weather /var/log/weather
```

### Step 2: Install Application

```bash
# Clone repository
sudo -u weather git clone https://github.com/datagems-eosc/real-time-anomaly-detection.git /var/lib/weather/app
cd /var/lib/weather/app/stream_detection

# Install dependencies in virtual environment
sudo -u weather python3 -m venv /var/lib/weather/venv
sudo -u weather /var/lib/weather/venv/bin/pip install -r requirements.txt
```

### Step 3: Create Systemd Service Files

#### Collector Service

```bash
sudo nano /etc/systemd/system/weather-collector.service
```

```ini
[Unit]
Description=Weather Data Collector
After=network.target

[Service]
Type=simple
User=weather
Group=weather
WorkingDirectory=/var/lib/weather/app/stream_detection
Environment="PATH=/var/lib/weather/venv/bin"
Environment="WEATHER_DB=/var/lib/weather/data/weather_stream.db"
ExecStart=/var/lib/weather/venv/bin/python streaming_collector_sqlite.py
Restart=always
RestartSec=30

# Logging
StandardOutput=append:/var/log/weather/collector.log
StandardError=append:/var/log/weather/collector.error.log

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/var/lib/weather /var/log/weather

[Install]
WantedBy=multi-user.target
```

#### Detection Service (Periodic)

```bash
sudo nano /etc/systemd/system/weather-detector.service
```

```ini
[Unit]
Description=Weather Anomaly Detection
After=network.target weather-collector.service

[Service]
Type=oneshot
User=weather
Group=weather
WorkingDirectory=/var/lib/weather/app/stream_detection
Environment="PATH=/var/lib/weather/venv/bin"
Environment="WEATHER_DB=/var/lib/weather/data/weather_stream.db"
ExecStart=/var/lib/weather/venv/bin/python anomaly_detector.py --end "NOW" --spatial-verify --save /var/log/weather/reports/report_%Y%m%d_%H%M%S.json

# Logging
StandardOutput=append:/var/log/weather/detector.log
StandardError=append:/var/log/weather/detector.error.log
```

#### Detection Timer

```bash
sudo nano /etc/systemd/system/weather-detector.timer
```

```ini
[Unit]
Description=Run Weather Anomaly Detection Hourly

[Timer]
OnBootSec=15min
OnUnitActiveSec=1h
Persistent=true

[Install]
WantedBy=timers.target
```

### Step 4: Enable and Start Services

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable services
sudo systemctl enable weather-collector.service
sudo systemctl enable weather-detector.timer

# Start services
sudo systemctl start weather-collector.service
sudo systemctl start weather-detector.timer

# Check status
sudo systemctl status weather-collector.service
sudo systemctl status weather-detector.timer
```

### Step 5: Verify Deployment

```bash
# Check collector logs
sudo tail -f /var/log/weather/collector.log

# Check database
sudo -u weather sqlite3 /var/lib/weather/data/weather_stream.db "SELECT COUNT(*) FROM observations;"

# Manual detection test
sudo -u weather /var/lib/weather/venv/bin/python /var/lib/weather/app/stream_detection/anomaly_detector.py --end "NOW"
```

---

## Option 2: Docker Container

### Dockerfile

```dockerfile
# Dockerfile
FROM python:3.10-slim

# Install dependencies
RUN apt-update && apt-get install -y \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create data directory
RUN mkdir -p /data
VOLUME ["/data"]

# Expose ports (if REST API is added)
# EXPOSE 8000

# Default command
CMD ["python", "streaming_collector_sqlite.py"]
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  collector:
    build: .
    container_name: weather-collector
    restart: always
    volumes:
      - weather-data:/data
    environment:
      - WEATHER_DB=/data/weather_stream.db
    command: python streaming_collector_sqlite.py

  detector:
    build: .
    container_name: weather-detector
    restart: "no"
    volumes:
      - weather-data:/data
      - ./reports:/reports
    environment:
      - WEATHER_DB=/data/weather_stream.db
    command: python anomaly_detector.py --end "NOW" --spatial-verify --save /reports/report.json
    depends_on:
      - collector

volumes:
  weather-data:
```

### Deploy with Docker

```bash
# Build image
docker-compose build

# Start collector
docker-compose up -d collector

# Run detection manually
docker-compose run --rm detector

# Or schedule with cron
echo "0 * * * * cd /path/to/app && docker-compose run --rm detector" | crontab -
```

---

## Option 3: Cron Jobs

### Setup

```bash
# Edit crontab
crontab -e

# Add these lines:

# Data collection (continuous background process)
@reboot cd /path/to/stream_detection && ./manage_collector.sh start

# Anomaly detection (every hour)
0 * * * * cd /path/to/stream_detection && /path/to/venv/bin/python anomaly_detector.py --end "NOW" --spatial-verify >> /var/log/weather/detector.log 2>&1

# Report cleanup (daily at 2 AM)
0 2 * * * find /var/log/weather/reports -name "*.json" -mtime +30 -delete

# Database vacuum (weekly on Sunday at 3 AM)
0 3 * * 0 sqlite3 /var/lib/weather/weather_stream.db 'VACUUM;'
```

---

## Option 4: Kubernetes

### ConfigMap

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: weather-config
data:
  WEATHER_DB: "/data/weather_stream.db"
  DETECTION_METHOD: "arima"
  SPATIAL_VERIFY: "1"
```

### PersistentVolume

```yaml
# pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: weather-data-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

### Collector Deployment

```yaml
# collector-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: weather-collector
spec:
  replicas: 1
  selector:
    matchLabels:
      app: weather-collector
  template:
    metadata:
      labels:
        app: weather-collector
    spec:
      containers:
      - name: collector
        image: datagem/weather-collector:latest
        envFrom:
        - configMapRef:
            name: weather-config
        volumeMounts:
        - name: data
          mountPath: /data
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: weather-data-pvc
```

### Detector CronJob

```yaml
# detector-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: weather-detector
spec:
  schedule: "0 * * * *"  # Every hour
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: detector
            image: datagem/weather-detector:latest
            args: ["--end", "NOW", "--spatial-verify"]
            envFrom:
            - configMapRef:
                name: weather-config
            volumeMounts:
            - name: data
              mountPath: /data
          restartPolicy: OnFailure
          volumes:
          - name: data
            persistentVolumeClaim:
              claimName: weather-data-pvc
```

### Deploy to Kubernetes

```bash
kubectl apply -f configmap.yaml
kubectl apply -f pvc.yaml
kubectl apply -f collector-deployment.yaml
kubectl apply -f detector-cronjob.yaml

# Check status
kubectl get pods
kubectl logs -f deployment/weather-collector
```

---

## Monitoring & Alerting

### Health Checks

```bash
# /usr/local/bin/weather-healthcheck.sh
#!/bin/bash

# Check if collector is running
if ! systemctl is-active --quiet weather-collector; then
    echo "ERROR: Collector not running"
    exit 1
fi

# Check data freshness
LAST_DATA=$(sqlite3 /var/lib/weather/data/weather_stream.db \
    "SELECT MAX(time) FROM observations;")
CURRENT_TIME=$(date +%s)
LAST_DATA_TIME=$(date -d "$LAST_DATA" +%s 2>/dev/null || echo 0)
AGE=$((CURRENT_TIME - LAST_DATA_TIME))

if [ $AGE -gt 900 ]; then  # 15 minutes
    echo "ERROR: Data is stale (last: $LAST_DATA)"
    exit 1
fi

echo "OK: System healthy"
exit 0
```

### Prometheus Metrics (Future)

```python
# metrics_exporter.py
from prometheus_client import start_http_server, Gauge
import time

# Define metrics
data_age = Gauge('weather_data_age_seconds', 'Age of last observation')
db_size = Gauge('weather_db_size_bytes', 'Database size')
collection_errors = Gauge('weather_collection_errors_total', 'Collection errors')

# Start server
start_http_server(9090)

# Update loop
while True:
    update_metrics()
    time.sleep(60)
```

### Grafana Dashboard

Import `grafana-dashboard.json` for visualization:

- Data collection rate
- Detection frequency
- Anomaly trends
- System health

---

## Backup & Recovery

### Automated Backup

```bash
#!/bin/bash
# /usr/local/bin/weather-backup.sh

BACKUP_DIR="/var/backups/weather"
DB_PATH="/var/lib/weather/data/weather_stream.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create backup
mkdir -p "$BACKUP_DIR"
sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/weather_$TIMESTAMP.db'"

# Compress
gzip "$BACKUP_DIR/weather_$TIMESTAMP.db"

# Delete old backups (keep 7 days)
find "$BACKUP_DIR" -name "weather_*.db.gz" -mtime +7 -delete
```

Add to cron:

```bash
0 4 * * * /usr/local/bin/weather-backup.sh
```

### Recovery

```bash
# Restore from backup
gunzip /var/backups/weather/weather_20251122_040000.db.gz
cp /var/backups/weather/weather_20251122_040000.db /var/lib/weather/data/weather_stream.db
sudo systemctl restart weather-collector
```

---

## Troubleshooting Deployment

### Issue: Collector Not Starting

```bash
# Check logs
sudo journalctl -u weather-collector -n 50

# Check permissions
sudo -u weather ls -l /var/lib/weather/data

# Test manually
sudo -u weather /var/lib/weather/venv/bin/python /var/lib/weather/app/stream_detection/streaming_collector_sqlite.py
```

### Issue: Detection Fails

```bash
# Check if enough data
sqlite3 /var/lib/weather/data/weather_stream.db \
    "SELECT COUNT(DISTINCT time) FROM observations WHERE time > datetime('now', '-6 hours');"

# Should be >= 36 for 6-hour window

# Run with verbose output
sudo -u weather /var/lib/weather/venv/bin/python /var/lib/weather/app/stream_detection/anomaly_detector.py --end "NOW" --verbose
```

### Issue: High Memory Usage

```bash
# Check process memory
ps aux | grep python

# Reduce window size or use faster method
python anomaly_detector.py --window 3 --temporal-method 3sigma
```

---

## Security Hardening

1. **Run as non-root user** ✓
2. **Use virtual environment** ✓
3. **Restrict file permissions**: `chmod 600 weather_stream.db`
4. **Enable firewall**: No inbound ports needed
5. **Regular updates**: `pip install --upgrade -r requirements.txt`
6. **Audit logs**: Monitor `/var/log/weather/`

---

For database migration to TimescaleDB, see [Database Options](database.md).

