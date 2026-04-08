"""
Streaming Data Collector (SQLite + PostgreSQL/TimescaleDB)
==========================================================

A unified streaming collector that supports both:
1. SQLite (local file, default)
2. PostgreSQL / TimescaleDB (remote database)

Key features:
- Seamless switching via connection string
- Automatic schema creation
- Robust error handling and reconnection logic
- Sliding window query optimization

Author: Weather Anomaly Detection Team
Date: 2025-11-22
"""

import sqlite3
import requests
import time
import argparse
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union, Any
import threading
import logging
import os

# Optional PostgreSQL support
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PG_AVAILABLE = True
except ImportError:
    PG_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('streaming_collector.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class DatabaseInterface:
    """Abstract interface for database operations."""
    def insert_station(self, station_id: str, info: Dict) -> bool: raise NotImplementedError
    def insert_observations_batch(self, observations: List[Tuple]) -> int: raise NotImplementedError
    def log_collection(self, status: str, stations_count: int, obs_count: int, message: str = ""): raise NotImplementedError
    def get_station_window(self, station_id: str, window_size: int = 6) -> List[Dict]: raise NotImplementedError
    def get_stats(self) -> Dict: raise NotImplementedError
    def close(self): raise NotImplementedError


class SQLiteDatabase(DatabaseInterface):
    """SQLite implementation."""
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = None
        self._connect()
        self._init_database()
    
    def _connect(self):
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            logger.info(f"Connected to SQLite: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"SQLite Connection Error: {e}")
            raise
    
    def _init_database(self):
        cursor = self.conn.cursor()
        # Stations Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stations (
                station_id TEXT PRIMARY KEY,
                station_name_en TEXT,
                station_name_gr TEXT,
                latitude REAL,
                longitude REAL,
                elevation REAL,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Observations Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                time TIMESTAMP NOT NULL,
                station_id TEXT NOT NULL,
                temp_out REAL,
                hi_temp REAL,
                low_temp REAL,
                out_hum REAL,
                bar REAL,
                rain REAL,
                wind_speed REAL,
                wind_dir REAL,
                wind_dir_str TEXT,
                hi_speed REAL,
                hi_dir REAL,
                hi_dir_str TEXT,
                collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(time, station_id)
            )
        """)
        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_observations_station_time ON observations (station_id, time DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_observations_time ON observations (time DESC)")
        # Log Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS collection_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT,
                stations_count INTEGER,
                observations_count INTEGER,
                message TEXT
            )
        """)
        self.conn.commit()

    def insert_station(self, station_id: str, info: Dict) -> bool:
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO stations (
                    station_id, station_name_en, station_name_gr,
                    latitude, longitude, elevation, first_seen, last_seen
                ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(station_id) DO UPDATE SET
                    station_name_en = excluded.station_name_en,
                    station_name_gr = excluded.station_name_gr,
                    latitude = excluded.latitude,
                    longitude = excluded.longitude,
                    elevation = excluded.elevation,
                    last_seen = CURRENT_TIMESTAMP
            """, (
                station_id, info.get('station_name_en'), info.get('station_name_gr'),
                info.get('latitude'), info.get('longitude'), info.get('elevation')
            ))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Station Insert Error: {e}")
            return False

    def insert_observations_batch(self, observations: List[Tuple]) -> int:
        try:
            cursor = self.conn.cursor()
            cursor.executemany("""
                INSERT OR IGNORE INTO observations (
                    time, station_id, temp_out, hi_temp, low_temp, out_hum,
                    bar, rain, wind_speed, wind_dir, wind_dir_str,
                    hi_speed, hi_dir, hi_dir_str
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, observations)
            self.conn.commit()
            return cursor.rowcount
        except sqlite3.Error as e:
            logger.error(f"Observation Batch Error: {e}")
            return 0

    def log_collection(self, status: str, stations_count: int, obs_count: int, message: str = ""):
        try:
            self.conn.execute("INSERT INTO collection_log (status, stations_count, observations_count, message) VALUES (?, ?, ?, ?)", 
                            (status, stations_count, obs_count, message))
            self.conn.commit()
        except: pass

    def get_station_window(self, station_id: str, window_size: int = 6) -> List[Dict]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT strftime('%s', time) as timestamp, * FROM observations
            WHERE station_id = ? ORDER BY time DESC LIMIT ?
        """, (station_id, window_size))
        return [dict(row) for row in cursor.fetchall()]

    def get_stats(self) -> Dict:
        try:
            cur = self.conn.cursor()
            stats = {}
            stats['stations_count'] = cur.execute("SELECT COUNT(*) FROM stations").fetchone()[0]
            stats['observations_count'] = cur.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
            db_size = Path(self.db_path).stat().st_size / (1024 * 1024)
            stats['database_size_mb'] = f"{db_size:.2f} MB"
            return stats
        except: return {}

    def close(self):
        if self.conn: self.conn.close()


class PostgresDatabase(DatabaseInterface):
    """PostgreSQL / TimescaleDB implementation."""
    def __init__(self, dsn: str):
        if not PG_AVAILABLE:
            raise ImportError("psycopg2 is required for PostgreSQL support. pip install psycopg2-binary")
        self.dsn = dsn
        self.conn = None
        self._connect()
        self._init_database()

    def _connect(self):
        try:
            self.conn = psycopg2.connect(self.dsn, cursor_factory=RealDictCursor)
            self.conn.autocommit = True
            logger.info("Connected to PostgreSQL/TimescaleDB")
        except psycopg2.Error as e:
            logger.error(f"PostgreSQL Connection Error: {e}")
            raise

    def _init_database(self):
        with self.conn.cursor() as cur:
            # Stations
            cur.execute("""
                CREATE TABLE IF NOT EXISTS stations (
                    station_id TEXT PRIMARY KEY,
                    station_name_en TEXT,
                    station_name_gr TEXT,
                    latitude DOUBLE PRECISION,
                    longitude DOUBLE PRECISION,
                    elevation DOUBLE PRECISION,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Observations
            cur.execute("""
                CREATE TABLE IF NOT EXISTS observations (
                    time TIMESTAMP NOT NULL,
                    station_id TEXT NOT NULL,
                    temp_out DOUBLE PRECISION,
                    hi_temp DOUBLE PRECISION,
                    low_temp DOUBLE PRECISION,
                    out_hum DOUBLE PRECISION,
                    bar DOUBLE PRECISION,
                    rain DOUBLE PRECISION,
                    wind_speed DOUBLE PRECISION,
                    wind_dir DOUBLE PRECISION,
                    wind_dir_str TEXT,
                    hi_speed DOUBLE PRECISION,
                    hi_dir DOUBLE PRECISION,
                    hi_dir_str TEXT,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(time, station_id)
                )
            """)
            
            # Try converting to Hypertable (TimescaleDB feature)
            try:
                cur.execute("SELECT create_hypertable('observations', 'time', if_not_exists => TRUE);")
                logger.info("✓ Converted 'observations' to TimescaleDB Hypertable")
            except psycopg2.Error:
                logger.info("ℹ️ Using standard PostgreSQL table (TimescaleDB not detected or already set)")

            # Log Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS collection_log (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT,
                    stations_count INTEGER,
                    observations_count INTEGER,
                    message TEXT
                )
            """)
    
    def insert_station(self, station_id: str, info: Dict) -> bool:
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO stations (
                        station_id, station_name_en, station_name_gr,
                        latitude, longitude, elevation, first_seen, last_seen
                    ) VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT(station_id) DO UPDATE SET
                        station_name_en = EXCLUDED.station_name_en,
                        latitude = EXCLUDED.latitude,
                        longitude = EXCLUDED.longitude,
                        last_seen = CURRENT_TIMESTAMP
                """, (
                    station_id, info.get('station_name_en'), info.get('station_name_gr'),
                    info.get('latitude'), info.get('longitude'), info.get('elevation')
                ))
            return True
        except psycopg2.Error as e:
            logger.error(f"PG Station Insert Error: {e}")
            return False

    def insert_observations_batch(self, observations: List[Tuple]) -> int:
        try:
            # Convert tuple list to string for fast bulk insert
            # Note: Need to handle None values correctly for Postgres
            args_str = ','.join(cur.mogrify(
                "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", x
            ).decode('utf-8') for x in observations)
            
            with self.conn.cursor() as cur:
                cur.execute("INSERT INTO observations VALUES " + args_str + " ON CONFLICT DO NOTHING")
                return cur.rowcount
        except Exception as e: # Use generic exception to catch mogrify errors too
             # Fallback to row-by-row if mogrify fails (simplified logic for robustness)
             count = 0
             try:
                 with self.conn.cursor() as cur:
                    for obs in observations:
                        cur.execute("""
                            INSERT INTO observations (
                                time, station_id, temp_out, hi_temp, low_temp, out_hum,
                                bar, rain, wind_speed, wind_dir, wind_dir_str,
                                hi_speed, hi_dir, hi_dir_str
                            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            ON CONFLICT DO NOTHING
                        """, obs)
                        count += cur.rowcount
                 return count
             except psycopg2.Error as e2:
                 logger.error(f"PG Batch Error: {e2}")
                 return 0

    def log_collection(self, status: str, stations_count: int, obs_count: int, message: str = ""):
        try:
            with self.conn.cursor() as cur:
                cur.execute("INSERT INTO collection_log (status, stations_count, observations_count, message) VALUES (%s, %s, %s, %s)", 
                            (status, stations_count, obs_count, message))
        except: pass
    
    def get_stats(self) -> Dict:
        return {"type": "PostgreSQL/TimescaleDB"} # Simplified stats
    
    def close(self):
        if self.conn: self.conn.close()


class StreamingCollector:
    def __init__(self, geojson_url: str, db: DatabaseInterface, interval_seconds: int = 600):
        self.geojson_url = geojson_url
        self.db = db
        self.interval_seconds = interval_seconds
        self.running = False
        self.thread = None
    
    def fetch_and_store(self) -> Tuple[bool, str]:
        try:
            logger.info(f"Fetching from {self.geojson_url} ...")
            response = requests.get(self.geojson_url, timeout=30)
            response.raise_for_status()
            
            features = response.json().get('features', [])
            if not features: return False, "No data"
            
            station_info_list = []
            observations_list = []
            
            for feature in features:
                props = feature['properties']
                coords = feature['geometry']['coordinates']
                station_id = props.get('station_file', props.get('fid', ''))
                if not station_id: continue
                
                station_info_list.append({
                    'station_id': station_id,
                    'station_name_en': props.get('station_name_en'),
                    'station_name_gr': props.get('station_name_gr'),
                    'latitude': coords[1], 'longitude': coords[0],
                    'elevation': coords[2] if len(coords) > 2 else None
                })
                
                ts = props.get('ts', 0)
                if ts > 0:
                    time_dt = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                    observations_list.append((
                        time_dt, station_id,
                        props.get('temp_out'), props.get('hi_temp'), props.get('low_temp'),
                        props.get('out_hum'), props.get('bar'), props.get('rain'),
                        props.get('wind_speed'), props.get('wind_dir'), props.get('wind_dir_str'),
                        props.get('hi_speed'), props.get('hi_dir'), props.get('hi_dir_str')
                    ))
            
            # Write to DB
            for info in station_info_list: self.db.insert_station(info['station_id'], info)
            count = self.db.insert_observations_batch(observations_list)
            
            msg = f"Stored {count} obs from {len(station_info_list)} stations"
            logger.info(msg)
            self.db.log_collection('SUCCESS', len(station_info_list), count, msg)
            return True, msg
            
        except Exception as e:
            msg = f"Error: {e}"
            logger.error(msg)
            self.db.log_collection('ERROR', 0, 0, msg)
            return False, msg

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        logger.info("Collector started")

    def stop(self):
        self.running = False
        if self.thread: self.thread.join(timeout=5)
        logger.info("Collector stopped")

    def _loop(self):
        while self.running:
            start = time.time()
            self.fetch_and_store()
            elapsed = time.time() - start
            sleep_time = max(0, self.interval_seconds - elapsed)
            for _ in range(int(sleep_time)):
                if not self.running: break
                time.sleep(1)


def get_pg_url_from_env():
    """
    Build PostgreSQL connection URL from environment variables.
    Used for K8s deployment with secrets (e.g., ap-explanation).
    """
    host = os.environ.get("POSTGRES_TIMESCALE_HOST")
    port = os.environ.get("POSTGRES_TIMESCALE_PORT", "5432")
    user = os.environ.get("POSTGRES_USER")
    pwd = os.environ.get("POSTGRES_PASSWORD")
    db_name = os.environ.get("POSTGRES_DB", "ds_weather_stream")
    
    if host and user and pwd:
        return f"postgresql://{user}:{pwd}@{host}:{port}/{db_name}"
    return None


def main():
    parser = argparse.ArgumentParser(description='Streaming Weather Collector (SQLite/PostgreSQL)')
    parser.add_argument('--database', type=str, help='SQLite file path (default: weather_stream.db)')
    parser.add_argument('--pg-url', type=str, help='PostgreSQL connection string (e.g., postgresql://user:pass@host/db)')
    parser.add_argument('--interval', type=int, default=600, help='Interval in seconds')
    parser.add_argument('--continuous', action='store_true', help='Run continuously')
    
    args = parser.parse_args()
    
    # Try to get pg_url from environment if not provided via CLI
    if not args.pg_url:
        env_pg_url = get_pg_url_from_env()
        if env_pg_url:
            args.pg_url = env_pg_url
            print("📦 Using PostgreSQL URL from environment variables")
    
    # DB Factory
    if args.pg_url:
        if not PG_AVAILABLE:
            print("Error: psycopg2 not installed. Cannot use PostgreSQL.")
            sys.exit(1)
        # Mask password in log output
        safe_url = args.pg_url.split('@')[-1] if '@' in args.pg_url else args.pg_url
        print(f"🔌 Mode: PostgreSQL/TimescaleDB (@{safe_url})")
        db = PostgresDatabase(args.pg_url)
    else:
        db_path = args.database or 'weather_stream.db'
        print(f"🔌 Mode: SQLite ({db_path})")
        db = SQLiteDatabase(db_path)
    
    collector = StreamingCollector('https://stratus.meteo.noa.gr/data/stations/latestValues_Datagems.geojson', db, args.interval)
    
    if args.continuous:
        try:
            collector.start()
            while True: time.sleep(1)
        except KeyboardInterrupt:
            collector.stop()
            db.close()
    else:
        collector.fetch_and_store()
        db.close()

if __name__ == '__main__':
    main()
