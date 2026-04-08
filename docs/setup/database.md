# Database Options

## Overview

The system supports two database backends:

1. **SQLite** (default) - For standalone deployments
2. **TimescaleDB** - For enterprise scale

---

## SQLite (Default)

### Advantages

- ✅ No external dependencies
- ✅ Zero configuration
- ✅ Single-file storage
- ✅ Perfect for < 100 stations
- ✅ Embedded in Python

### Limitations

- ⚠️ Single writer (sufficient for this use case)
- ⚠️ Local storage only
- ⚠️ Limited scalability

### Configuration

```python
# Default - no configuration needed
DATABASE_PATH = "weather_stream.db"
```

### Performance Optimization

```python
import sqlite3

conn = sqlite3.connect('weather_stream.db')

# Enable WAL mode for better concurrent reads
conn.execute('PRAGMA journal_mode=WAL;')

# Increase cache size (10MB)
conn.execute('PRAGMA cache_size=-10000;')

# Optimize synchronization
conn.execute('PRAGMA synchronous=NORMAL;')

# Enable memory-mapped I/O (64MB)
conn.execute('PRAGMA mmap_size=67108864;')
```

### Maintenance

```bash
# Vacuum database (reclaim space)
sqlite3 weather_stream.db 'VACUUM;'

# Analyze for query optimization
sqlite3 weather_stream.db 'ANALYZE;'

# Check integrity
sqlite3 weather_stream.db 'PRAGMA integrity_check;'
```

---

## TimescaleDB (Enterprise)

### When to Use

Consider TimescaleDB when:

- ✅ Monitoring > 100 stations
- ✅ Need distributed deployment
- ✅ Require advanced analytics
- ✅ Want automatic data compression
- ✅ Need high availability

### Installation

#### Docker (Recommended)

```bash
# Run TimescaleDB container
docker run -d \
    --name timescaledb \
    -p 5432:5432 \
    -e POSTGRES_PASSWORD=password \
    -v timescale-data:/var/lib/postgresql/data \
    timescale/timescaledb:latest-pg15
```

#### Ubuntu/Debian

```bash
# Add repository
sudo sh -c "echo 'deb https://packagecloud.io/timescale/timescaledb/ubuntu/ $(lsb_release -c -s) main' > /etc/apt/sources.list.d/timescaledb.list"

# Import GPG key
wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | sudo apt-key add -

# Install
sudo apt update
sudo apt install timescaledb-2-postgresql-15

# Configure
sudo timescaledb-tune --quiet --yes

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### Database Setup

```sql
-- Create database
CREATE DATABASE weather_monitoring;

-- Connect
\c weather_monitoring

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create table
CREATE TABLE observations (
    time TIMESTAMPTZ NOT NULL,
    station_id TEXT NOT NULL,
    temp_out REAL,
    out_hum REAL,
    wind_speed REAL,
    bar REAL,
    rain REAL
);

-- Convert to hypertable (enables time-series optimizations)
SELECT create_hypertable('observations', 'time');

-- Create indexes
CREATE INDEX idx_station_time ON observations (station_id, time DESC);
CREATE INDEX idx_time ON observations (time DESC);

-- Add compression policy (compress data > 7 days old)
ALTER TABLE observations SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'station_id'
);

SELECT add_compression_policy('observations', INTERVAL '7 days');

-- Add retention policy (drop data > 1 year old)
SELECT add_retention_policy('observations', INTERVAL '1 year');
```

### Application Configuration

Update connection string in collector and detector:

```python
# streaming_collector_timescale.py
import psycopg2

# PostgreSQL/TimescaleDB connection
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="weather_monitoring",
    user="postgres",
    password="password"
)

# Use same SQL as SQLite (mostly compatible)
cursor = conn.cursor()
cursor.execute("""
    INSERT INTO observations (time, station_id, temp_out, out_hum, wind_speed, bar, rain)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (time, station_id) DO UPDATE SET
        temp_out = EXCLUDED.temp_out,
        out_hum = EXCLUDED.out_hum,
        wind_speed = EXCLUDED.wind_speed,
        bar = EXCLUDED.bar,
        rain = EXCLUDED.rain
""", (time, station_id, temp, hum, wind, bar, rain))
conn.commit()
```

### Performance Tuning

```sql
-- Optimize query performance
SET max_parallel_workers_per_gather = 4;
SET work_mem = '256MB';

-- Enable Just-In-Time compilation
SET jit = on;

-- Create materialized view for faster aggregations
CREATE MATERIALIZED VIEW hourly_stats
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS hour,
    station_id,
    AVG(temp_out) as avg_temp,
    MIN(temp_out) as min_temp,
    MAX(temp_out) as max_temp,
    STDDEV(temp_out) as stddev_temp
FROM observations
GROUP BY hour, station_id;

-- Refresh policy
SELECT add_continuous_aggregate_policy('hourly_stats',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');
```

---

## Migration from SQLite to TimescaleDB

### Step 1: Export Data

```bash
# Export SQLite to CSV
sqlite3 weather_stream.db <<EOF
.headers on
.mode csv
.output observations.csv
SELECT * FROM observations ORDER BY time;
EOF
```

### Step 2: Import to TimescaleDB

```bash
# Import CSV
psql -d weather_monitoring -c "\
COPY observations (time, station_id, temp_out, out_hum, wind_speed, bar, rain)
FROM '/path/to/observations.csv'
WITH (FORMAT csv, HEADER true);"
```

### Step 3: Update Configuration

```python
# Update connection string
DATABASE_URL = "postgresql://postgres:password@localhost:5432/weather_monitoring"
```

### Step 4: Verify

```sql
-- Check row count
SELECT COUNT(*) FROM observations;

-- Check time range
SELECT MIN(time), MAX(time) FROM observations;

-- Check stations
SELECT station_id, COUNT(*) as obs_count
FROM observations
GROUP BY station_id
ORDER BY obs_count DESC;
```

---

## Performance Comparison

| Metric | SQLite | TimescaleDB |
|--------|--------|-------------|
| Insert Rate | ~1000/sec | ~50,000/sec |
| Query Time (6h window) | 50-100ms | 10-30ms |
| Storage (1 year, 14 stations) | ~500MB | ~150MB (compressed) |
| Concurrent Reads | Limited | Unlimited |
| Scalability | 100 stations | 10,000+ stations |
| Setup Complexity | None | Medium |

---

## Backup Strategies

### SQLite Backup

```bash
# Online backup
sqlite3 weather_stream.db ".backup backup.db"

# Point-in-time backup with WAL
cp weather_stream.db weather_stream.db.backup
cp weather_stream.db-wal weather_stream.db-wal.backup
```

### TimescaleDB Backup

```bash
# Logical backup
pg_dump weather_monitoring > backup.sql

# Physical backup (faster)
pg_basebackup -D /backups/weather -Ft -z -Xs -P

# Point-in-time recovery setup
# Edit postgresql.conf:
# wal_level = replica
# archive_mode = on
# archive_command = 'cp %p /archive/%f'
```

---

## High Availability

### TimescaleDB Replication

```sql
-- Primary server
-- Edit postgresql.conf
wal_level = replica
max_wal_senders = 3

-- Create replication user
CREATE USER replicator WITH REPLICATION ENCRYPTED PASSWORD 'password';

-- Standby server
pg_basebackup -h primary -D /var/lib/postgresql/data -U replicator -P -Xs -R
```

### Load Balancing

```
┌─────────────┐
│   HAProxy   │  (Port 5432)
└─────────────┘
       │
   ┌───┴───┐
   │       │
 ┌─▼──┐ ┌──▼─┐
 │ M  │ │ R1 │  (M = Master, R = Replica)
 └────┘ └────┘
          │
        ┌─▼──┐
        │ R2 │
        └────┘
```

---

## Monitoring Queries

### SQLite

```sql
-- Database size
SELECT page_count * page_size / 1024.0 / 1024.0 as size_mb
FROM pragma_page_count(), pragma_page_size();

-- Recent activity
SELECT
    COUNT(*) as total_rows,
    MIN(time) as oldest,
    MAX(time) as newest,
    COUNT(DISTINCT station_id) as stations
FROM observations;
```

### TimescaleDB

```sql
-- Hypertable stats
SELECT * FROM timescaledb_information.hypertables;

-- Chunk statistics
SELECT
    chunk_name,
    range_start,
    range_end,
    pg_size_pretty(total_bytes) as size
FROM timescaledb_information.chunks
WHERE hypertable_name = 'observations'
ORDER BY range_start DESC
LIMIT 10;

-- Compression stats
SELECT
    pg_size_pretty(before_compression_total_bytes) as uncompressed,
    pg_size_pretty(after_compression_total_bytes) as compressed,
    ROUND(100 - (after_compression_total_bytes::NUMERIC / before_compression_total_bytes * 100), 2) as compression_ratio
FROM timescaledb_information.compression_settings
WHERE hypertable_name = 'observations';
```

---

For production deployment recommendations, see [Deployment Guide](deployment.md).

