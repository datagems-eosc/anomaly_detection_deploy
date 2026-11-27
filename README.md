# Real-Time Weather Stream Anomaly Detection

Real-time streaming data collection, anomaly detection, and profiling for 14 meteorological stations from the [National Observatory of Athens (NOA)](https://www.noa.gr/), deployed on Kubernetes as part of the [DataGEMS](https://datagems-eosc.github.io/) platform.

## Key Features

| Feature | Description |
|:--------|:------------|
| **Streaming Data Collection** | Continuous ingestion from the NOA GeoJSON API every 10 minutes |
| **Point Anomaly Detection** | Statistical (3-Sigma, Z-Score/MAD), Time Series (ARIMA), and ML (Isolation Forest) methods |
| **Subsequence Anomaly Detection** | Matrix Profile algorithm (STUMPY) for unusual temporal patterns |
| **Spatial Verification** | Pearson correlation with neighbor stations to distinguish device failures from weather events |
| **Sensor Health Monitoring** | Long-term detection of stalled sensors, data loss, and sensor degradation |
| **Column Statistics Profiler** | MoMa-compatible profiling (mean, median, std, histogram, etc.) over sliding time windows |
| **Interactive Visualization** | Folium-based HTML maps with embedded time-series plots and anomaly markers |

## Architecture

```
┌───────────────────────────────────────────────────────────────────┐
│                   Kubernetes (namespace: upcite)                  │
│                                                                   │
│  ┌──────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │ Airflow DAG       │  │ CronJob:        │  │ CronJob:        │  │
│  │ Data Ingestion    │  │ anomaly-detector│  │ health-check    │  │
│  │ (every 10 min)    │  │ (every 6 hours) │  │ (daily)         │  │
│  └────────┬──────────┘  └───────┬─────────┘  └───────┬─────────┘  │
│           │                     │                     │           │
│           ▼                     ▼                     ▼           │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │              TimescaleDB (ds_weather_stream)               │   │
│  │    stations (14 rows)  |  observations (hypertable)        │   │
│  └────────────────────────────┬───────────────────────────────┘   │
│                               │                                   │
│                               ▼                                   │
│  ┌─────────────────────────────────────────┐                      │
│  │  CronJob: streaming-profiler (proposed) │                      │
│  │  Column statistics → MoMa API           │                      │
│  └─────────────────────────────────────────┘                      │
└───────────────────────────────────────────────────────────────────┘
```

## Detection Methods

### Point Anomaly Detection

Detects individual data points that deviate significantly from expected values.

| Method | Description | Best For |
|:-------|:------------|:---------|
| `3sigma` | 3-Sigma Rule (mean +/- 3 sigma) | Normally distributed data |
| `zscore` | Modified Z-Score using MAD | Robust to existing outliers |
| `arima` | ARIMA(1,0,1) residual analysis | Data with temporal trends |
| `isolation_forest` | Isolation Forest (scikit-learn) | Multivariate data |

### Subsequence Anomaly Detection

Detects unusual temporal patterns using the Matrix Profile algorithm (STUMPY). Identifies sensor drift, sudden weather shifts, and recurring anomalous patterns over sliding windows.

### Spatial Verification

After a temporal anomaly is detected, the system checks neighbor stations (within 100 km, similar elevation):

- **Correlation > 0.6** -> Weather event (ignore)
- **Correlation < 0.3** -> Device failure (alert)
- **0.3 - 0.6** -> Suspected (needs review)

### Sensor Health Check

Monitors sensor quality over days/weeks: stalled wind sensors (>30% zeros), missing data (>50% NULL), stuck sensors (near-zero variance).

## Database Schema

```sql
CREATE TABLE stations (
    station_id TEXT PRIMARY KEY,
    station_name_en TEXT,
    latitude REAL, longitude REAL, elevation REAL,
    first_seen TIMESTAMP, last_seen TIMESTAMP
);

CREATE TABLE observations (
    time TIMESTAMP NOT NULL,
    station_id TEXT NOT NULL,
    temp_out REAL,    -- Temperature (C)
    out_hum REAL,     -- Humidity (%)
    wind_speed REAL,  -- Wind Speed (km/h)
    bar REAL,         -- Pressure (hPa)
    rain REAL,        -- Rain (mm)
    wind_dir REAL,    -- Wind Direction (deg)
    UNIQUE(time, station_id)
);

-- TimescaleDB hypertable in production
SELECT create_hypertable('observations', 'time', if_not_exists => TRUE);
```

## Quick Start

### Install Dependencies

```bash
pip install -r requirements.txt
pip install psycopg2-binary  # for PostgreSQL/TimescaleDB
```

### Local Development (SQLite)

```bash
# Collect data
python streaming_collector_sqlite.py --continuous --interval 600

# Run anomaly detection (last 6 hours)
python anomaly_detector.py --end "NOW" --window 6 --spatial-verify

# Comprehensive analysis (last 7 days)
python anomaly_detector.py --end "NOW" --window 168 --comprehensive

# Sensor health check (last 30 days)
python anomaly_detector.py --health-check --days 30

# Generate interactive map
python visualize_anomalies.py --end "NOW" --window 168 --comprehensive

# Column statistics profiler
python streaming_profiler.py --db weather_stream.db --window 168
```

### Production (TimescaleDB)

```bash
# Via connection string
python anomaly_detector.py \
  --pg-url "postgresql://user:pass@host:5432/ds_weather_stream" \
  --end "NOW" --window 168 --comprehensive

# Via environment variables (K8s)
export POSTGRES_TIMESCALE_HOST=<host>
export POSTGRES_USER=<user>
export POSTGRES_PASSWORD=<password>
export POSTGRES_DB=ds_weather_stream
python anomaly_detector.py --end "NOW" --window 6
```

### Docker Compose

```bash
docker-compose up -d                          # Start TimescaleDB + collector
docker-compose logs -f datagem                # View logs
docker exec datagem-app python anomaly_detector.py \
  --pg-url "postgresql://datagems:datagems2024@postgres:5432/datagems" \
  --end "NOW" --window 168 --comprehensive
```

## Kubernetes Deployment

Manifests are in `k8s/`, managed via Kustomize, and deployed to namespace `upcite`.

```
k8s/
├── base/                 # shared manifests
│   └── runner/           # run_anomaly.py + moma_connection.py, mounted into the pods
└── overlays/
    ├── dev/              # SCAYLE development cluster
    └── prod/             # SCAYLE production cluster
```

| Resource | File (`k8s/base/`) | Schedule |
|:---------|:-----|:---------|
| Anomaly Detection CronJob | `cronjob-anomaly-detector.yaml` | Every 6 hours |
| Health Check CronJob | `cronjob-health-check.yaml` | Daily at 08:00 |
| Manual Job | `job-anomaly-manual.yaml` | On-demand (not part of the kustomization) |
| Vault Secret | `vault-secret.yaml` | Credentials from Vault |

```bash
kubectl --kubeconfig /path/to/dev.kubeconfig apply -k k8s/overlays/dev
kubectl --kubeconfig /path/to/prod.kubeconfig apply -k k8s/overlays/prod
kubectl --kubeconfig /path/to/prod.kubeconfig get cronjobs -n upcite
```

Select the intended cluster's kubeconfig explicitly: dev and prod can both have
a context named `upcite`. The production API endpoint is `172.16.68.4:6443`.

### Database connection

Vault only holds credentials. Database host, port and name are read at start-up
from the dataset profile in MoMa (Data Model Management), by the runner wrapper
in `k8s/base/runner/`:

1. Get a token from the DataGEMS AAI with the client-credentials grant
   (client `anomaly-detector`, scope `datagems`).
2. `GET {MOMA_API_URL}/api/v1/dataset/get/{MOMA_DATASET_ID}`.
3. Read `postgresql://host:port/db` from the `dg:DatabaseConnection` node.

| Setting | Source |
|:--------|:-------|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `AAI_CLIENT_SECRET` | Vault `kvv2/upcite/anomaly-detector` → Secret `anomaly-detector-secrets` |
| `MOMA_API_URL`, `MOMA_DATASET_ID`, `AAI_TOKEN_URL`, `AAI_CLIENT_ID` | ConfigMap `anomaly-detector-config` (per overlay) |
| `REQUIRE_POSTGRES=true` | Fail instead of falling back to a local SQLite file |

The runner is mounted from a ConfigMap, so this works with the existing image.

#### Production MoMa connection

Use `k8s/overlays/prod` for production. It enables both CronJobs and resolves the
database connection from MoMa dataset `36853ff2-4942-4019-9bf3-9d517b16a26c` at
each job's start. Database host and port are not set in the deployment ConfigMap.

On 2026-11-27, a production validation job confirmed that the corrected profile
resolves to `172.16.68.5:30433/ds_weather_stream`. Full seven-day anomaly detection
and 30-day sensor health checks through MoMa each produced nonempty reports for
all 14 NOA stations. Database credentials and the AAI client secret continue to
come from Vault.

The temporary `prod-direct-db` overlay, introduced on 2026-11-21 while the profile
contained a development database address, has been removed. Deployments that used
that path must switch to `k8s/overlays/prod`; applying it removes the old host/port
override and keeps both schedules enabled.

Reports are still written to `/tmp/anomaly_report.json` and
`/tmp/health_report.json` in the respective containers. Persistent report storage,
report retrieval authorization, and UI integration remain separate work items.

### Differences between dev and prod

| | dev | prod |
|:--|:--|:--|
| Node pinning | `srv-prj-dg-k8s-worker01/02` | none |
| Image pull secret | not set | `ghcr-pull-secret` |
| Collector Deployment | present (0 replicas) | not deployed; data is ingested by the platform |
| CronJob schedule | active | active (`suspend: false`) |

Run once by hand:

```bash
kubectl --kubeconfig /path/to/prod.kubeconfig -n upcite create job anomaly-run-$(date +%Y%m%d%H%M) --from=cronjob/anomaly-detector
kubectl --kubeconfig /path/to/prod.kubeconfig -n upcite create job health-run-$(date +%Y%m%d%H%M) --from=cronjob/sensor-health-check
```

Cluster access (VPN profile and kubeconfig) is personal and is requested through
`datagems-eosc/project-sms`. Never commit those files to this repository.

## Streaming Profiler (MoMa Integration)

The `streaming_profiler.py` computes column statistics matching the [MoMa](https://github.com/datagems-eosc/moma-management) `ColumnStatistics` schema:

| Statistic | Field |
|:----------|:------|
| Row count | `rowCount` |
| Mean | `mean` |
| Median | `median` |
| Standard deviation | `standardDeviation` |
| Min / Max | `min`, `max` |
| Missing count / percentage | `missingCount`, `missingPercentage` |
| Histogram | `histogram` |
| Unique values | `uniqueCount` |

```bash
# Compute and export
python streaming_profiler.py --window 6 --output-json profile.json

# Push to MoMa (once API credentials are available)
python streaming_profiler.py --window 6 --moma-url https://moma.example.com/api/v1
```

See [PROFILER_README.md](PROFILER_README.md) for full documentation.

## Project Structure

```
stream_anomaly_detection/
├── anomaly_detector.py            # Core detection engine (point, subsequence, spatial, health)
├── streaming_collector_sqlite.py  # Data collector (NOA API -> SQLite/TimescaleDB)
├── streaming_profiler.py          # Column statistics profiler (MoMa integration)
├── visualize_anomalies.py         # Interactive map visualization (Folium)
├── generate_map.py                # Static station network map
├── view_data.py                   # Database query utility
├── requirements.txt               # Python dependencies
├── Dockerfile                     # Container image (Python 3.11-slim)
├── docker-compose.yml             # Local dev (TimescaleDB + app)
├── mkdocs.yml                     # Documentation config
├── k8s/
│   ├── cronjob-anomaly-detector.yaml
│   ├── cronjob-health-check.yaml
│   ├── job-anomaly-manual.yaml
│   ├── vault-secret.yaml
│   └── kustomization.yaml
├── tests/
│   ├── test_data_collection.sh
│   ├── test_short_term_detection.sh
│   ├── test_long_term_health.sh
│   └── run_best_detection.sh
└── docs/                          # MkDocs documentation source
```

## Command Reference

| Script | Key Arguments | Description |
|:-------|:-------------|:------------|
| `anomaly_detector.py` | `--end`, `--window`, `--comprehensive`, `--health-check` | Anomaly detection and health monitoring |
| `streaming_collector_sqlite.py` | `--continuous`, `--interval`, `--pg-url` | Data ingestion from NOA API |
| `streaming_profiler.py` | `--window`, `--output-json`, `--moma-url` | Column statistics for MoMa |
| `visualize_anomalies.py` | `--end`, `--window`, `--comprehensive`, `--output` | Interactive HTML map generation |
| `view_data.py` | `--latest`, `--station`, `--summary`, `--export` | Database query and export |

## Data Source

[NOA DataGEMS GeoJSON Feed](https://stratus.meteo.noa.gr/data/stations/latestValues_Datagems.geojson) — updates every 10 minutes from 14 stations across Greece.

| Variable | Unit | Description |
|:---------|:-----|:------------|
| `temp_out` | C | Air Temperature |
| `out_hum` | % | Relative Humidity |
| `wind_speed` | km/h | Wind Speed |
| `bar` | hPa | Barometric Pressure |
| `rain` | mm | Rainfall |
| `wind_dir` | deg | Wind Direction |

## License

This project is part of the [DataGEMS](https://datagems-eosc.github.io/) initiative under EOSC.
