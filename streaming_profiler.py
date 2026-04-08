#!/usr/bin/env python3
"""
Streaming Column Statistics Profiler
=====================================

Computes real-time column statistics over a sliding time window from
TimescaleDB, matching the MoMa ColumnStatistics schema:

    rowCount, mean, median, standardDeviation, min, max,
    missingCount, missingPercentage, histogram, uniqueCount

Output modes:
    1. Print to console (default) — for testing
    2. Export to JSON file (--output-json) — for review / archival
    3. Push to MoMa API (--moma-url) — for platform integration

Usage:
    # Local test against TimescaleDB
    python streaming_profiler.py --pg-url "postgresql://user:pass@host:5432/db" --window 6

    # Export to JSON
    python streaming_profiler.py --window 6 --output-json profiler_output.json

    # Push to MoMa (once MoMa API URL and credentials are available)
    python streaming_profiler.py --window 6 --moma-url "https://moma.example.com/api/v1"

Author: Weather Stream Detection Team
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

try:
    import psycopg2
    PG_AVAILABLE = True
except ImportError:
    PG_AVAILABLE = False

try:
    import requests as http_requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("streaming_profiler")

PROFILE_COLUMNS = ["temp_out", "out_hum", "wind_speed", "bar", "rain", "wind_dir"]

COLUMN_LABELS = {
    "temp_out":    "Air Temperature (°C)",
    "out_hum":     "Relative Humidity (%)",
    "wind_speed":  "Wind Speed (km/h)",
    "bar":         "Barometric Pressure (hPa)",
    "rain":        "Rainfall (mm)",
    "wind_dir":    "Wind Direction (°)",
}


def build_pg_url_from_env():
    """Build PostgreSQL URL from environment variables (K8s secret injection)."""
    host = os.environ.get("POSTGRES_TIMESCALE_HOST")
    port = os.environ.get("POSTGRES_TIMESCALE_PORT", "5432")
    user = os.environ.get("POSTGRES_USER")
    pwd = os.environ.get("POSTGRES_PASSWORD")
    db = os.environ.get("POSTGRES_DB", "ds_weather_stream")
    if host and user and pwd:
        return f"postgresql://{user}:{pwd}@{host}:{port}/{db}"
    return None


def compute_histogram(series: pd.Series, bins: int = 10) -> dict:
    """Compute a histogram with bin edges and counts."""
    clean = series.dropna()
    if clean.empty:
        return {"bins": [], "counts": []}
    counts, edges = np.histogram(clean, bins=bins)
    return {
        "bins": [round(float(e), 4) for e in edges],
        "counts": [int(c) for c in counts],
    }


def compute_column_statistics(df: pd.DataFrame, column: str) -> dict:
    """
    Compute the 10 MoMa ColumnStatistics fields for one column.

    These fields are defined in moma-management mapping.yml:
        rowCount, mean, median, standardDeviation,
        min, max, missingCount, missingPercentage,
        histogram, uniqueCount
    """
    series = df[column]
    total = len(series)
    missing = int(series.isna().sum())

    if total == 0:
        return {
            "rowCount": 0, "mean": None, "median": None,
            "standardDeviation": None, "min": None, "max": None,
            "missingCount": 0, "missingPercentage": 0.0,
            "histogram": {"bins": [], "counts": []},
            "uniqueCount": 0,
        }

    clean = series.dropna()

    return {
        "rowCount":          total,
        "mean":              round(float(clean.mean()), 4) if not clean.empty else None,
        "median":            round(float(clean.median()), 4) if not clean.empty else None,
        "standardDeviation": round(float(clean.std()), 4) if len(clean) > 1 else None,
        "min":               round(float(clean.min()), 4) if not clean.empty else None,
        "max":               round(float(clean.max()), 4) if not clean.empty else None,
        "missingCount":      missing,
        "missingPercentage": round(missing / total * 100, 2),
        "histogram":         compute_histogram(series),
        "uniqueCount":       int(clean.nunique()),
    }


def _is_sqlite(conn) -> bool:
    return type(conn).__module__.startswith("sqlite3")


def profile_with_timescaledb(conn, window_hours: int, station_id: str = None) -> dict:
    """
    Query TimescaleDB (or SQLite) and compute ColumnStatistics for each variable
    across all (or one specific) station(s).
    """
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=window_hours)

    logger.info(
        "Profiling window: %s to %s (%d hours)",
        start_time.strftime("%Y-%m-%d %H:%M"),
        end_time.strftime("%Y-%m-%d %H:%M"),
        window_hours,
    )

    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")

    if _is_sqlite(conn):
        params_list = [start_str, end_str]
        station_filter = ""
        if station_id:
            station_filter = "AND station_id = ?"
            params_list.append(station_id)
        query = f"""
            SELECT time, station_id, temp_out, out_hum, wind_speed, bar, rain, wind_dir
            FROM observations
            WHERE time >= ? AND time < ?
            {station_filter}
            ORDER BY time ASC
        """
        df = pd.read_sql_query(query, conn, params=params_list)
    else:
        params_dict: dict = {"start": start_time, "end": end_time}
        station_filter = ""
        if station_id:
            station_filter = "AND station_id = %(station_id)s"
            params_dict["station_id"] = station_id
        query = f"""
            SELECT time, station_id, temp_out, out_hum, wind_speed, bar, rain, wind_dir
            FROM observations
            WHERE time >= %(start)s AND time < %(end)s
            {station_filter}
            ORDER BY time ASC
        """
        df = pd.read_sql_query(query, conn, params=params_dict)
    df["time"] = pd.to_datetime(df["time"])

    if df.empty:
        logger.warning("No data found in the specified window!")
        return {"window": {"start": str(start_time), "end": str(end_time)}, "stations": {}}

    stations = df["station_id"].unique()
    logger.info("Found %d stations, %d total rows", len(stations), len(df))

    result = {
        "window": {
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "hours": window_hours,
        },
        "generated_at": datetime.utcnow().isoformat(),
        "stations": {},
    }

    for sid in sorted(stations):
        station_df = df[df["station_id"] == sid]
        station_stats = {}
        for col in PROFILE_COLUMNS:
            if col not in station_df.columns:
                continue
            stats = compute_column_statistics(station_df, col)
            stats["columnName"] = col
            stats["columnLabel"] = COLUMN_LABELS.get(col, col)
            station_stats[col] = stats
        result["stations"][sid] = station_stats

    all_stations_stats = {}
    for col in PROFILE_COLUMNS:
        if col not in df.columns:
            continue
        stats = compute_column_statistics(df, col)
        stats["columnName"] = col
        stats["columnLabel"] = COLUMN_LABELS.get(col, col)
        all_stations_stats[col] = stats
    result["global"] = all_stations_stats

    return result


def timescaledb_aggregation_demo(conn, window_hours: int):
    """
    Demonstrate TimescaleDB-native time_bucket aggregation.

    This shows how TimescaleDB can compute rolling statistics efficiently
    at the database level, useful for very large datasets where pulling
    all raw data into Python would be too slow.
    """
    query = """
        SELECT
            time_bucket('1 hour', time) AS bucket,
            station_id,
            count(*)                                        AS row_count,
            round(avg(temp_out)::numeric, 2)                AS mean_temp,
            round(stddev(temp_out)::numeric, 2)             AS std_temp,
            min(temp_out)                                   AS min_temp,
            max(temp_out)                                   AS max_temp,
            count(*) FILTER (WHERE temp_out IS NULL)        AS missing_temp,
            round(avg(out_hum)::numeric, 2)                 AS mean_hum,
            round(avg(wind_speed)::numeric, 2)              AS mean_wind,
            round(avg(bar)::numeric, 2)                     AS mean_bar
        FROM observations
        WHERE time >= NOW() - INTERVAL '%s hours'
        GROUP BY bucket, station_id
        ORDER BY bucket DESC, station_id
        LIMIT 50;
    """
    df = pd.read_sql_query(query, conn, params=(window_hours,))
    if df.empty:
        logger.warning("No data for time_bucket demo")
        return

    print("\n" + "=" * 90)
    print("  TimescaleDB time_bucket Aggregation Demo (1-hour buckets)")
    print("=" * 90)
    print(df.to_string(index=False))
    print("=" * 90 + "\n")


def push_to_moma(moma_url: str, moma_token: str, profile_data: dict):
    """
    Push computed statistics to MoMa via PATCH /api/v1/nodes/{id}.

    NOTE: This requires the MoMa node IDs to be pre-registered.
    The node_id_mapping should be provided via a config file or
    environment variables once the MoMa team sets up the nodes.

    For now this is a placeholder that shows the expected HTTP calls.
    """
    if not REQUESTS_AVAILABLE:
        logger.error("'requests' library required for MoMa push. pip install requests")
        return

    # TODO: Replace with actual node ID mapping from MoMa registration
    # Format: { "station_id/column_name": "moma-node-uuid" }
    node_id_mapping_file = os.environ.get("MOMA_NODE_MAPPING", "moma_node_mapping.json")
    if not os.path.exists(node_id_mapping_file):
        logger.warning(
            "MoMa node mapping file not found: %s. "
            "This file should map 'station_id/column_name' to MoMa node UUIDs. "
            "Ask the CNRS team (Lucas, Silviu) to register the nodes first.",
            node_id_mapping_file,
        )
        logger.info("Printing what WOULD be sent to MoMa instead:\n")
        for sid, columns in profile_data.get("stations", {}).items():
            for col_name, stats in columns.items():
                moma_payload = {
                    "mean": stats.get("mean"),
                    "median": stats.get("median"),
                    "standardDeviation": stats.get("standardDeviation"),
                    "min": stats.get("min"),
                    "max": stats.get("max"),
                    "rowCount": stats.get("rowCount"),
                    "missingCount": stats.get("missingCount"),
                    "missingPercentage": stats.get("missingPercentage"),
                    "histogram": stats.get("histogram"),
                    "uniqueCount": stats.get("uniqueCount"),
                }
                print(f"  PATCH {moma_url}/nodes/<node-id-for-{sid}/{col_name}>")
                print(f"  Body: {json.dumps(moma_payload, indent=2)[:200]}...\n")
        return

    with open(node_id_mapping_file) as f:
        node_mapping = json.load(f)

    headers = {"Authorization": f"Bearer {moma_token}", "Content-Type": "application/json"}

    success_count = 0
    error_count = 0

    for sid, columns in profile_data.get("stations", {}).items():
        for col_name, stats in columns.items():
            mapping_key = f"{sid}/{col_name}"
            node_id = node_mapping.get(mapping_key)
            if not node_id:
                logger.warning("No MoMa node ID for %s, skipping", mapping_key)
                continue

            payload = {
                "mean": stats.get("mean"),
                "median": stats.get("median"),
                "standardDeviation": stats.get("standardDeviation"),
                "min": stats.get("min"),
                "max": stats.get("max"),
                "rowCount": stats.get("rowCount"),
                "missingCount": stats.get("missingCount"),
                "missingPercentage": stats.get("missingPercentage"),
                "histogram": stats.get("histogram"),
                "uniqueCount": stats.get("uniqueCount"),
            }

            url = f"{moma_url}/nodes/{node_id}"
            try:
                resp = http_requests.patch(url, json=payload, headers=headers, timeout=10)
                if resp.status_code == 200:
                    logger.info("Updated MoMa node %s (%s)", node_id, mapping_key)
                    success_count += 1
                else:
                    logger.error(
                        "MoMa PATCH failed for %s: %s %s",
                        mapping_key, resp.status_code, resp.text[:200],
                    )
                    error_count += 1
            except Exception as e:
                logger.error("MoMa request error for %s: %s", mapping_key, e)
                error_count += 1

    logger.info("MoMa push complete: %d success, %d errors", success_count, error_count)


def print_profile_summary(profile_data: dict):
    """Pretty-print the profiling results to console."""
    window = profile_data.get("window", {})
    print("\n" + "=" * 80)
    print("  STREAMING COLUMN STATISTICS PROFILER")
    print(f"  Window: {window.get('start', '?')} to {window.get('end', '?')}")
    print(f"  Generated: {profile_data.get('generated_at', '?')}")
    print("=" * 80)

    global_stats = profile_data.get("global", {})
    if global_stats:
        print("\n--- Global Statistics (all stations combined) ---\n")
        print(f"  {'Column':<20} {'Rows':>8} {'Mean':>10} {'Median':>10} "
              f"{'StdDev':>10} {'Min':>10} {'Max':>10} {'Missing%':>10} {'Unique':>8}")
        print("  " + "-" * 106)
        for col, stats in global_stats.items():
            def fmt(v):
                return f"{v:>10.2f}" if v is not None else f"{'N/A':>10}"
            print(
                f"  {col:<20} {stats['rowCount']:>8} "
                f"{fmt(stats['mean'])} {fmt(stats['median'])} "
                f"{fmt(stats['standardDeviation'])} {fmt(stats['min'])} "
                f"{fmt(stats['max'])} {stats['missingPercentage']:>9.1f}% "
                f"{stats['uniqueCount']:>8}"
            )

    stations = profile_data.get("stations", {})
    print(f"\n--- Per-Station Statistics ({len(stations)} stations) ---\n")
    for sid in sorted(stations):
        print(f"  Station: {sid}")
        cols = stations[sid]
        print(f"    {'Column':<16} {'Rows':>6} {'Mean':>10} {'StdDev':>10} "
              f"{'Min':>10} {'Max':>10} {'Miss%':>7}")
        print("    " + "-" * 79)
        for col, stats in cols.items():
            def fmt(v):
                return f"{v:>10.2f}" if v is not None else f"{'N/A':>10}"
            print(
                f"    {col:<16} {stats['rowCount']:>6} "
                f"{fmt(stats['mean'])} {fmt(stats['standardDeviation'])} "
                f"{fmt(stats['min'])} {fmt(stats['max'])} "
                f"{stats['missingPercentage']:>6.1f}%"
            )
        print()

    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Streaming Column Statistics Profiler for MoMa Integration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Profile last 6 hours, print to console
  python streaming_profiler.py --pg-url "postgresql://user:pass@host:5432/db" --window 6

  # Profile and export to JSON
  python streaming_profiler.py --window 6 --output-json profile.json

  # Profile a specific station
  python streaming_profiler.py --window 24 --station dodoni

  # Show TimescaleDB time_bucket aggregation demo
  python streaming_profiler.py --window 6 --timescale-demo

  # Push to MoMa API (future use)
  python streaming_profiler.py --window 6 --moma-url https://moma.example.com/api/v1
        """,
    )
    parser.add_argument("--db", default="weather_stream.db", help="SQLite DB path (fallback)")
    parser.add_argument("--pg-url", help="PostgreSQL/TimescaleDB connection string")
    parser.add_argument("--window", type=int, default=6, help="Sliding window in hours (default: 6)")
    parser.add_argument("--station", help="Profile a specific station only")
    parser.add_argument("--output-json", help="Export results to JSON file")
    parser.add_argument("--timescale-demo", action="store_true",
                        help="Show TimescaleDB time_bucket aggregation demo")
    parser.add_argument("--moma-url", help="MoMa API base URL (e.g. https://moma.example.com/api/v1)")
    parser.add_argument("--moma-token", help="MoMa API Bearer token")

    args = parser.parse_args()

    pg_url = args.pg_url or build_pg_url_from_env()
    use_sqlite = False

    if pg_url:
        if not PG_AVAILABLE:
            print("Error: psycopg2 is required. Install with: pip install psycopg2-binary")
            sys.exit(1)
        logger.info("Connecting to PostgreSQL...")
        conn = psycopg2.connect(pg_url)
        logger.info("Connected to PostgreSQL successfully")
    elif os.path.exists(args.db):
        import sqlite3
        logger.info("No PostgreSQL URL found. Using SQLite: %s", args.db)
        conn = sqlite3.connect(args.db)
        use_sqlite = True
    else:
        print("Error: No database connection available.")
        print("  Provide --pg-url, set POSTGRES_* env vars, or ensure SQLite DB exists.")
        sys.exit(1)

    try:
        if args.timescale_demo:
            if use_sqlite:
                logger.warning("time_bucket demo requires TimescaleDB, skipping for SQLite")
            else:
                timescaledb_aggregation_demo(conn, args.window)

        profile_data = profile_with_timescaledb(conn, args.window, station_id=args.station)

        print_profile_summary(profile_data)

        if args.output_json:
            with open(args.output_json, "w") as f:
                json.dump(profile_data, f, indent=2, default=str)
            logger.info("Profile exported to %s", args.output_json)

        if args.moma_url:
            token = args.moma_token or os.environ.get("MOMA_TOKEN", "")
            push_to_moma(args.moma_url, token, profile_data)

    finally:
        conn.close()
        logger.info("Done")


if __name__ == "__main__":
    main()
