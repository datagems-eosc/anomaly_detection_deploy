# Streaming Column Statistics Profiler

A lightweight profiler that computes real-time column statistics over a sliding time window, designed to integrate with the [MoMa](https://github.com/datagems-eosc/moma-management) metadata management system.

## What It Does

Connects to the weather observation database (TimescaleDB or SQLite), computes **10 standard statistics** for each variable (`temp_out`, `out_hum`, `wind_speed`, `bar`, `rain`, `wind_dir`), and outputs results matching the MoMa `ColumnStatistics` schema.

### MoMa ColumnStatistics Fields

| Field | Description | SQL Equivalent |
|:------|:------------|:---------------|
| `rowCount` | Total number of rows | `count(*)` |
| `mean` | Arithmetic mean | `avg(column)` |
| `median` | 50th percentile | `percentile_cont(0.5)` |
| `standardDeviation` | Standard deviation | `stddev(column)` |
| `min` | Minimum value | `min(column)` |
| `max` | Maximum value | `max(column)` |
| `missingCount` | Number of NULL values | `count(*) FILTER (WHERE column IS NULL)` |
| `missingPercentage` | Percentage of NULLs | `missingCount / rowCount * 100` |
| `histogram` | Distribution (10 bins) | `width_bucket()` or numpy |
| `uniqueCount` | Distinct value count | `count(DISTINCT column)` |

These fields are defined in the MoMa mapping specification: [`moma-management/moma_management/domain/mapping.yml`](https://github.com/datagems-eosc/moma-management/blob/main/moma_management/domain/mapping.yml) under `ColumnStatistics`.

---

## Quick Start

### Prerequisites

```bash
pip install pandas numpy psycopg2-binary requests
```

### Run with SQLite (local testing)

```bash
python streaming_profiler.py --db weather_stream.db --window 999999
```

> `--window 999999` covers all historical data. Use smaller windows (e.g. `--window 6`) when connected to a live database with recent data.

### Run with TimescaleDB (production)

```bash
python streaming_profiler.py \
  --pg-url "postgresql://user:pass@host:5432/ds_weather_stream" \
  --window 6
```

Or via environment variables (used in K8s deployment):

```bash
export POSTGRES_TIMESCALE_HOST=<host>
export POSTGRES_TIMESCALE_PORT=5432
export POSTGRES_USER=<user>
export POSTGRES_PASSWORD=<password>
export POSTGRES_DB=ds_weather_stream

python streaming_profiler.py --window 6
```

### Export to JSON

```bash
python streaming_profiler.py --db weather_stream.db --window 999999 --output-json profiler_output.json
```

### Profile a specific station

```bash
python streaming_profiler.py --db weather_stream.db --window 999999 --station dodoni
```

### TimescaleDB time_bucket demo

Shows native TimescaleDB hourly aggregation (requires PostgreSQL, not SQLite):

```bash
python streaming_profiler.py \
  --pg-url "postgresql://user:pass@host:5432/ds_weather_stream" \
  --window 6 --timescale-demo
```

---

## Command Reference

| Argument | Description | Default |
|:---------|:------------|:--------|
| `--db PATH` | SQLite database file path (fallback) | `weather_stream.db` |
| `--pg-url URL` | PostgreSQL/TimescaleDB connection string | env vars fallback |
| `--window HOURS` | Sliding window size in hours | `6` |
| `--station ID` | Profile a specific station only | all stations |
| `--output-json FILE` | Export results to JSON file | console only |
| `--timescale-demo` | Show TimescaleDB time_bucket aggregation | off |
| `--moma-url URL` | MoMa API base URL (for pushing results) | off |
| `--moma-token TOKEN` | MoMa API Bearer token | `MOMA_TOKEN` env var |

---

## Output Format

### Console Output

```
================================================================================
  STREAMING COLUMN STATISTICS PROFILER
  Window: 2025-11-14T23:10:00 to 2026-01-15T01:50:00
================================================================================

--- Global Statistics (all stations combined) ---

  Column                Rows       Mean     Median     StdDev     Min        Max   Missing%   Unique
  ----------------------------------------------------------------------------------------------------
  temp_out             93244       9.98      10.40       5.41   -13.60      25.10       0.2%     383
  out_hum              93244      75.72      78.00      14.29    19.00      99.00       0.2%      81
  ...

--- Per-Station Statistics (14 stations) ---

  Station: dodoni
    Column           Rows       Mean     StdDev        Min        Max   Miss%
    ---------------------------------------------------------------------------
    temp_out         7407       7.03       4.15      -5.90      16.30    0.0%
    ...
```

### JSON Output

```json
{
  "window": {
    "start": "2025-11-14T23:10:00",
    "end": "2026-01-15T01:50:00",
    "hours": 999999
  },
  "generated_at": "2026-04-08T11:09:50.823096",
  "global": {
    "temp_out": {
      "rowCount": 93244,
      "mean": 9.9769,
      "median": 10.4,
      "standardDeviation": 5.4128,
      "min": -13.6,
      "max": 25.1,
      "missingCount": 172,
      "missingPercentage": 0.18,
      "histogram": { "bins": [...], "counts": [...] },
      "uniqueCount": 383,
      "columnName": "temp_out",
      "columnLabel": "Air Temperature (°C)"
    }
  },
  "stations": {
    "dodoni": {
      "temp_out": { ... },
      "out_hum": { ... }
    }
  }
}
```

---

## Architecture: How It Fits in the System

```
┌─────────────────────────────────────────────────────────────┐
│                   Kubernetes (namespace: upcite)            │
│                                                             │
│  Airflow DAG (Giorgos)      CronJob: anomaly-detector      │
│  ┌─────────────────┐        ┌─────────────────────┐        │
│  │ Data Ingestion   │        │ Anomaly Detection   │        │
│  │ (every 10 min)   │        │ (every 6 hours)     │        │
│  └────────┬────────┘        └──────────┬──────────┘        │
│           │                            │                   │
│           ▼                            ▼                   │
│  ┌──────────────────────────────────────────────┐          │
│  │       TimescaleDB (ds_weather_stream)        │          │
│  │  ┌──────────┐  ┌────────────────────────┐    │          │
│  │  │ stations │  │ observations (hypertable)│    │          │
│  │  │ (14 rows)│  │ (streaming, every 10min)│    │          │
│  │  └──────────┘  └────────────────────────┘    │          │
│  └──────────────────────┬───────────────────────┘          │
│                         │                                  │
│                         ▼                                  │
│  ┌──────────────────────────────────┐                      │
│  │  CronJob: streaming-profiler     │                      │
│  │  (proposed, every 6 hours)       │                      │
│  │                                  │                      │
│  │  Computes ColumnStatistics:      │                      │
│  │  mean, median, std, min, max,    │                      │
│  │  missingCount, histogram, etc.   │                      │
│  └───────────────┬──────────────────┘                      │
│                  │                                         │
└──────────────────┼─────────────────────────────────────────┘
                   │ PATCH /api/v1/nodes/{id}
                   ▼
          ┌─────────────────┐         ┌──────────────┐
          │   MoMa API      │────────▶│  Platform UI │
          │   (Neo4j)       │         │  (read-only) │
          └─────────────────┘         └──────────────┘
```

---

## MoMa Integration (Pending)

The profiler is ready to push statistics to MoMa via `PATCH /api/v1/nodes/{id}`. Before this can work, the following are needed from the CNRS/MoMa team (Lucas, Silviu):

1. **MoMa API base URL** — where the MoMa service is hosted
2. **Authentication credentials** — Bearer token or API key
3. **Node ID mapping** — UUIDs for each Column's ColumnStatistics node in the MoMa graph

Once available, create a `moma_node_mapping.json` file:

```json
{
  "dodoni/temp_out": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "dodoni/out_hum": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "volos/temp_out": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

Then run:

```bash
python streaming_profiler.py \
  --window 6 \
  --moma-url https://moma.example.com/api/v1 \
  --moma-token "your-bearer-token"
```

---

## Related Components

| Component | File | Schedule | Purpose |
|:----------|:-----|:---------|:--------|
| Data Ingestion | Airflow DAG (managed by Giorgos) | Every 10 min | Fetch NOA API → TimescaleDB |
| Anomaly Detection | `anomaly_detector.py` | Every 6 hours | Point + subsequence anomaly detection |
| Health Check | `anomaly_detector.py --health-check` | Daily | Sensor health monitoring |
| **Profiler** | **`streaming_profiler.py`** | **Every 6 hours (proposed)** | **Column statistics → MoMa** |
