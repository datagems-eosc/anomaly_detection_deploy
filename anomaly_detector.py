#!/usr/bin/env python3
"""
Weather Data Anomaly Detection System (SQLite + PostgreSQL/TimescaleDB)
-------------------------------------
A comprehensive system for detecting anomalies in weather station data using:
1. Temporal Analysis (ARIMA, STL, Statistical methods)
2. Spatial Verification (Neighbor trend correlation)
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Union
import argparse
import json
import warnings
import sys
import math
import os
warnings.filterwarnings('ignore')

# Optional: TSB-UAD dependencies for advanced subsequence detection
try:
    import stumpy
    STUMPY_AVAILABLE = True
except ImportError:
    STUMPY_AVAILABLE = False

try:
    from statsmodels.tsa.stattools import acf
    from scipy.signal import argrelextrema
    STATSMODELS_AVAILABLE = True
except ImportError:
    STATSMODELS_AVAILABLE = False

# Check for PostgreSQL support
try:
    import psycopg2
    PG_AVAILABLE = True
except ImportError:
    PG_AVAILABLE = False


class DataLoader:
    """Abstract Data Loader"""
    def get_window_data(self, station_id: str, start_time: str = None, end_time: str = None, window_hours: int = None) -> pd.DataFrame: raise NotImplementedError
    def get_all_stations(self) -> pd.DataFrame: raise NotImplementedError
    def get_spatial_data(self, timestamp: str, station_ids: List[str] = None, variable: str = None) -> pd.DataFrame: raise NotImplementedError
    def close(self): raise NotImplementedError


def parse_time(time_str: str) -> datetime:
    """Parse time string, supporting 'NOW' as current time."""
    if time_str is None:
        return None
    if isinstance(time_str, str) and time_str.upper() == 'NOW':
        return datetime.now()
    return pd.to_datetime(time_str)


class SQLiteLoader(DataLoader):
    """Loads data from SQLite."""
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
    
    def get_window_data(self, station_id: str, start_time: str = None, end_time: str = None, window_hours: int = None) -> pd.DataFrame:
        if start_time and end_time:
            start_dt, end_dt = parse_time(start_time), parse_time(end_time)
        elif end_time and window_hours:
            end_dt = parse_time(end_time)
            start_dt = end_dt - timedelta(hours=window_hours)
        else: raise ValueError("Must specify time range")
        
        query = """
            SELECT time, temp_out, out_hum, wind_speed, bar, rain
            FROM observations
            WHERE station_id = ? AND time BETWEEN ? AND ?
            ORDER BY time ASC
        """
        df = pd.read_sql_query(query, self.conn, params=(station_id, start_dt.strftime('%Y-%m-%d %H:%M:%S'), end_dt.strftime('%Y-%m-%d %H:%M:%S')))
        df['time'] = pd.to_datetime(df['time'])
        return df

    def get_all_stations(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT station_id, station_name_en, latitude, longitude, elevation FROM stations", self.conn)

    def get_spatial_data(self, timestamp: str, station_ids: List[str] = None, variable: str = None) -> pd.DataFrame:
        # General spatial query logic used by detect_spatial_anomalies
        # If station_ids is None, fetch all for snapshot. If provided, fetch specific history for trend.
        pass # Implemented directly in anomaly methods via raw query for flexibility, or can refactor.
             # For now, let's keep the existing query style but adapted for DB type.
    
    def get_conn(self):
        return self.conn

    def close(self):
        if self.conn: self.conn.close()


class PostgresLoader(DataLoader):
    """Loads data from PostgreSQL/TimescaleDB."""
    def __init__(self, dsn: str):
        if not PG_AVAILABLE: raise ImportError("psycopg2 required")
        self.conn = psycopg2.connect(dsn)
    
    def get_window_data(self, station_id: str, start_time: str = None, end_time: str = None, window_hours: int = None) -> pd.DataFrame:
        if start_time and end_time:
            start_dt, end_dt = parse_time(start_time), parse_time(end_time)
        elif end_time and window_hours:
            end_dt = parse_time(end_time)
            start_dt = end_dt - timedelta(hours=window_hours)
        else: raise ValueError("Must specify time range")
        
        query = """
            SELECT time, temp_out, out_hum, wind_speed, bar, rain
            FROM observations
            WHERE station_id = %s AND time BETWEEN %s AND %s
            ORDER BY time ASC
        """
        df = pd.read_sql_query(query, self.conn, params=(station_id, start_dt, end_dt))
        df['time'] = pd.to_datetime(df['time'])
        return df

    def get_all_stations(self) -> pd.DataFrame:
        return pd.read_sql_query("SELECT station_id, station_name_en, latitude, longitude, elevation FROM stations", self.conn)

    def get_conn(self):
        return self.conn

    def close(self):
        if self.conn: self.conn.close()


# ... [StatisticalDetector, TimeSeriesDetector, MLDetector, SpatialDetector classes remain unchanged] ...
# Copying them back to ensure file integrity.

class StatisticalDetector:
    """Statistical methods for point anomaly detection."""
    
    @staticmethod
    def detect_3sigma(values: np.ndarray, threshold: float = 3.0) -> Tuple[np.ndarray, Dict]:
        """3-Sigma rule: anomaly = |x - μ| > 3σ. Best for normally distributed data."""
        if len(values) < 3: return np.zeros(len(values), dtype=bool), {}
        mean, std = np.mean(values), np.std(values)
        if std == 0: return np.zeros(len(values), dtype=bool), {'mean': mean, 'std': 0, 'is_constant': True}
        upper, lower = mean + threshold * std, mean - threshold * std
        return (values > upper) | (values < lower), {'mean': mean, 'std': std, 'upper_bound': upper, 'lower_bound': lower}

    @staticmethod
    def detect_zscore(values: np.ndarray, threshold: float = 3.0) -> Tuple[np.ndarray, Dict]:
        """Modified Z-Score using MAD. More robust to outliers than 3-sigma."""
        if len(values) < 3: return np.zeros(len(values), dtype=bool), {}
        median = np.median(values)
        mad = np.median(np.abs(values - median))
        if mad == 0: return np.zeros(len(values), dtype=bool), {'median': median, 'mad': 0, 'is_constant': True}
        scores = 0.6745 * (values - median) / mad
        return np.abs(scores) > threshold, {'median': median, 'mad': mad, 'threshold': threshold, 'std': mad * 1.4826}


class TimeSeriesDetector:
    """Time series methods for point anomaly detection."""
    
    @staticmethod
    def detect_arima_residuals(values: np.ndarray, threshold: float = 3.0) -> Tuple[np.ndarray, Dict]:
        """ARIMA residual analysis. Best for data with temporal trends."""
        try:
            from statsmodels.tsa.arima.model import ARIMA
            if len(values) < 20: return np.zeros(len(values), dtype=bool), {'error': 'insufficient data'}
            model = ARIMA(values, order=(1, 0, 1)).fit()
            resid = model.resid
            std = np.std(resid)
            if std == 0: return np.zeros(len(values), dtype=bool), {}
            return np.abs(resid) > threshold * std, {'mean_residual': float(np.mean(resid)), 'std_residual': float(std)}
        except Exception as e: return np.zeros(len(values), dtype=bool), {'error': str(e)}


class MLDetector:
    """Machine learning methods for point anomaly detection."""
    
    @staticmethod
    def detect_isolation_forest(values: np.ndarray, contamination: float = 0.1) -> Tuple[np.ndarray, Dict]:
        """Isolation Forest. Best for multivariate data and large datasets."""
        try:
            from sklearn.ensemble import IsolationForest
            if len(values) < 10: return np.zeros(len(values), dtype=bool), {}
            return IsolationForest(contamination=contamination, random_state=42).fit_predict(values.reshape(-1, 1)) == -1, {'contamination': contamination}
        except ImportError: return np.zeros(len(values), dtype=bool), {'error': 'sklearn missing'}
        except ImportError: return np.zeros(len(values), dtype=bool), {'error': 'sklearn missing'}





class SubsequenceDetector:
    """
    Subsequence Anomaly Detection using Matrix Profile and related methods.
    Detects anomalous patterns/segments in time series, not just individual points.
    Useful for detecting:
    - Unusual weather patterns (e.g., sudden temperature drops lasting hours)
    - Sensor drift/degradation over time windows
    - Recurring anomalous events
    """

    @staticmethod
    def find_optimal_window(data: np.ndarray, max_lag: int = 400) -> int:
        """
        Determine optimal subsequence length based on autocorrelation.
        Similar to TSB-UAD's find_length function.
        """
        if not STATSMODELS_AVAILABLE:
            return min(100, len(data) // 4)  # Default fallback
        if len(data.shape) > 1 or len(data) < 20:
            return min(100, len(data) // 4)
        data_sample = data[:min(20000, len(data))]
        base = 3
        
        try:
            auto_corr = acf(data_sample, nlags=min(max_lag, len(data_sample) // 2), fft=True)[base:]
            local_max = argrelextrema(auto_corr, np.greater)[0]
            
            if len(local_max) == 0:
                return min(100, len(data) // 4)
            max_local_max = np.argmax([auto_corr[lcm] for lcm in local_max])
            window = local_max[max_local_max] + base
            
            # Bounds check
            if window < 3 or window > 300:
                return min(100, len(data) // 4)
            return window
        except Exception:
            return min(100, len(data) // 4)

    @staticmethod
    def detect_matrix_profile(values: np.ndarray, window: int = None, 
                              threshold_percentile: float = 95) -> Tuple[np.ndarray, Dict]:
        """
        Detect subsequence anomalies using Matrix Profile.
        Matrix Profile finds the nearest neighbor distance for each subsequence,
        high values indicate anomalous (dissimilar) subsequences.
        Parameters:
        -----------
        values: Time series data
        window: Subsequence window length (auto-detected if None)
        threshold_percentile: Percentile above which subsequences are anomalous
        Returns:
        --------
        scores: Anomaly scores for each time point
        info: Detection metadata
        """
        if not STUMPY_AVAILABLE:
            return np.zeros(len(values)), {'error': 'stumpy not installed. Run: pip install stumpy'}
        if len(values) < 20:
            return np.zeros(len(values)), {'error': 'insufficient data for subsequence detection'}
        
        # Auto-detect window if not specified
        if window is None:
            window = SubsequenceDetector.find_optimal_window(values)
        # Ensure window is valid
        window = max(4, min(window, len(values) // 3))
        try:
            # Compute Matrix Profile
            profile = stumpy.stump(values.astype(np.float64), m=window)
            mp_scores = profile[:, 0].astype(np.float64)  # Matrix Profile distances
            # Handle NaN/Inf
            mp_scores = np.nan_to_num(mp_scores, nan=0, posinf=0, neginf=0)
            # Normalize to [0, 1]
            if mp_scores.max() > mp_scores.min():
                mp_scores_norm = (mp_scores - mp_scores.min()) / (mp_scores.max() - mp_scores.min())
            else:
                mp_scores_norm = np.zeros_like(mp_scores)
            # Pad scores to match original length
            # Matrix Profile is shorter by (window-1) at the end
            pad_front = (window - 1) // 2
            pad_back = window - 1 - pad_front
            scores_padded = np.concatenate([
                np.full(pad_front, mp_scores_norm[0]),
                mp_scores_norm,
                np.full(pad_back, mp_scores_norm[-1])
            ])
            # Identify anomalous subsequences
            threshold = np.percentile(mp_scores_norm, threshold_percentile)
            anomaly_indices = np.where(mp_scores_norm > threshold)[0] + pad_front
            # Find anomalous events (contiguous regions)
            events = SubsequenceDetector._find_events(anomaly_indices, window)
            return scores_padded, {
                'method': 'matrix_profile',
                'window': window,
                'threshold': float(threshold),
                'threshold_percentile': threshold_percentile,
                'num_events': len(events),
                'events': events,
                'mean_score': float(np.mean(mp_scores_norm)),
                'max_score': float(np.max(mp_scores_norm))
            }
        except Exception as e:
            return np.zeros(len(values)), {'error': str(e)}
    
    
    
    @staticmethod
    def detect_discord(values: np.ndarray, window: int = None, 
                       top_k: int = 3) -> Tuple[List[Dict], Dict]:
        """
        Find top-k discords (most unusual subsequences) using Matrix Profile.
        Discords are subsequences that are maximally different from all other
        subsequences in the time series.
        Returns:
        --------
        discords: List of discord events with start/end indices and scores
        info: Detection metadata
        """
        if not STUMPY_AVAILABLE:
            return [], {'error': 'stumpy not installed'}
        
        if len(values) < 20:
            return [], {'error': 'insufficient data'}
        
        if window is None:
            window = SubsequenceDetector.find_optimal_window(values)
        window = max(4, min(window, len(values) // 3))
        
        try:
            profile = stumpy.stump(values.astype(np.float64), m=window)
            mp_scores = profile[:, 0].astype(np.float64)
            mp_scores = np.nan_to_num(mp_scores, nan=0)
            
            # Find top-k discords (highest MP values)
            # Exclude trivial matches by ensuring minimum distance between discords
            discords = []
            used_indices = set()
            
            sorted_indices = np.argsort(mp_scores)[::-1]  # Descending
            
            for idx in sorted_indices:
                if len(discords) >= top_k:
                    break
                
                # Check if too close to existing discord
                too_close = False
                for used_idx in used_indices:
                    if abs(idx - used_idx) < window:
                        too_close = True
                        break
                
                if not too_close:
                    discords.append({
                        'start_idx': int(idx),
                        'end_idx': int(idx + window),
                        'score': float(mp_scores[idx]),
                        'rank': len(discords) + 1
                    })
                    used_indices.add(idx)
            
            return discords, {
                'method': 'discord_detection',
                'window': window,
                'top_k': top_k,
                'found': len(discords)
            }
        except Exception as e:
            return [], {'error': str(e)}
    
    
    
    @staticmethod
    def _find_events(anomaly_indices: np.ndarray, min_gap: int = 1) -> List[Dict]:
        """Convert anomaly indices to contiguous event ranges."""
        if len(anomaly_indices) == 0:
            return []
        
        events = []
        start = anomaly_indices[0]
        end = anomaly_indices[0]
        for idx in anomaly_indices[1:]:
            if idx - end <= min_gap:
                end = idx
            else:
                events.append({'start_idx': int(start), 'end_idx': int(end), 'length': int(end - start + 1)})
                start = idx
                end = idx
        events.append({'start_idx': int(start), 'end_idx': int(end), 'length': int(end - start + 1)})
        return events
    
    
    
    @staticmethod
    def sliding_window_features(values: np.ndarray, window: int) -> np.ndarray:
        """
        Convert 1D time series to 2D feature matrix using sliding windows.
        Useful for ML-based subsequence anomaly detection.
        """
        if len(values) < window:
            return np.array([])
        n_windows = len(values) - window + 1
        features = np.zeros((n_windows, window))
        for i in range(n_windows):
            features[i] = values[i:i + window]
        return features


class SpatialDetector:
    @staticmethod
    def haversine_distance(lat1, lon1, lat2, lon2):
        R = 6371
        lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
        a = np.sin((lat2-lat1)/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2-lon1)/2)**2
        return R * 2 * np.arcsin(np.sqrt(a))

    @staticmethod
    def find_neighbors(station_idx, locations, max_distance=100, max_elev_diff=500):
        neighbors = []
        t_lat, t_lon, t_elev = locations[station_idx]
        for i, loc in enumerate(locations):
            if i == station_idx: continue
            if abs(t_elev - loc[2]) > max_elev_diff: continue
            if SpatialDetector.haversine_distance(t_lat, t_lon, loc[0], loc[1]) <= max_distance:
                neighbors.append(i)
        return neighbors

    @staticmethod
    def elevation_adjusted_value(value, elev_diff, var_type='temp'):
        if var_type == 'temp': return value + (elev_diff / 100) * 0.65
        elif var_type == 'bar': return value + (elev_diff / 10) * 1.2
        return value

    @staticmethod
    def detect_spatial_anomalies(station_data, variable, threshold=3.0, max_distance=100, min_neighbors=2, max_elev_diff=500):
        ids = list(station_data.keys())
        if len(ids) < min_neighbors + 1: return [], {}
        locs = np.array([[station_data[sid]['latitude'], station_data[sid]['longitude'], station_data[sid]['elevation']] for sid in ids])
        vals = np.array([station_data[sid].get(variable, np.nan) for sid in ids])
        
        anomalies = []
        details = {}
        
        for i, sid in enumerate(ids):
            if np.isnan(vals[i]): continue
            nb_idxs = SpatialDetector.find_neighbors(i, locs, max_distance, max_elev_diff)
            if len(nb_idxs) < min_neighbors: continue
            
            nb_vals = []
            for j in nb_idxs:
                if not np.isnan(vals[j]):
                    diff = locs[j, 2] - locs[i, 2]
                    nb_vals.append(SpatialDetector.elevation_adjusted_value(vals[j], diff, variable))
            
            if len(nb_vals) < min_neighbors: continue
            
            med = np.median(nb_vals)
            mad = np.median(np.abs(np.array(nb_vals) - med))
            if mad == 0: mad = np.std(nb_vals) or 1e-6
            
            dev = abs(vals[i] - med) / (1.4826 * mad)
            if dev > threshold:
                anomalies.append(sid)
                details[sid] = {'value': float(vals[i]), 'neighbor_median': float(med), 'deviation': float(dev)}
        
        return anomalies, details


class AnomalyDetector:
    AVAILABLE_METHODS = {
        '3sigma': '3-Sigma Rule', 'mad': 'Median Absolute Deviation', 'zscore': 'Modified Z-Score',
        'percentile': 'Percentile', 'arima': 'ARIMA Residuals', 'stl': 'STL Decomposition',
        'isolation_forest': 'Isolation Forest', 'lof': 'Local Outlier Factor', 'ocsvm': 'One-Class SVM',
        'spatial': 'Spatial Correlation'
    }
    
    DETECTION_VARS = {
        'temp_out': {'name': 'Temp', 'unit': '°C', 'threshold': 3, 'sudden_change': 5.0},
        'out_hum': {'name': 'Humidity', 'unit': '%', 'threshold': 3},
        'wind_speed': {'name': 'Wind', 'unit': 'km/h', 'threshold': 3},
        'bar': {'name': 'Pressure', 'unit': 'hPa', 'threshold': 3, 'sudden_change': 10.0}
    }
    
    def __init__(self, db_path: str = None, pg_url: str = None,
                 start_time: str = None, end_time: str = None, window_hours: int = None,
                 temporal_method: str = '3sigma', spatial_method: str = 'mad', spatial_verify: bool = False):
        
        self.start_time = start_time
        self.end_time = end_time
        self.window_hours = window_hours
        self.temporal_method = temporal_method
        self.spatial_method = spatial_method
        self.spatial_verify = spatial_verify
        
        if not ((start_time and end_time) or (end_time and window_hours)):
            raise ValueError("Must specify time range")
        
        # Initialize Loader based on connection type
        if pg_url:
            if not PG_AVAILABLE: raise ImportError("psycopg2 required for PG")
            self.loader = PostgresLoader(pg_url)
            print(f"🔌 Connected to PostgreSQL: {pg_url}")
        else:
            self.loader = SQLiteLoader(db_path or 'weather_stream.db')
            print(f"🔌 Connected to SQLite: {db_path or 'weather_stream.db'}")

        self.stat_detector = StatisticalDetector()
        self.ts_detector = TimeSeriesDetector()
        self.ml_detector = MLDetector()

    def verify_spatial_trend(self, station_id: str, timestamp: str, variable: str, window_minutes: int = 30) -> Dict:
        dt = pd.to_datetime(timestamp)
        start_dt, end_dt = dt - timedelta(minutes=window_minutes), dt + timedelta(minutes=window_minutes)
        
        stations_df = self.loader.get_all_stations()
        locs = stations_df[['latitude', 'longitude', 'elevation']].values
        ids = stations_df['station_id'].tolist()
        
        try: target_idx = ids.index(station_id)
        except ValueError: return {'error': 'station not found'}
        
        nb_idxs = SpatialDetector.find_neighbors(target_idx, locs, 100, 500)
        if not nb_idxs: return {'status': 'no_neighbors', 'correlation': 0}
        
        nb_ids = [ids[i] for i in nb_idxs]
        all_ids = [station_id] + nb_ids
        
        # Flexible query for both DB types
        placeholders = ','.join(['%s' if isinstance(self.loader, PostgresLoader) else '?'] * len(all_ids))
        time_ph = '%s' if isinstance(self.loader, PostgresLoader) else '?'
        
        query = f"""
            SELECT time, station_id, {variable} FROM observations
            WHERE station_id IN ({placeholders}) AND time BETWEEN {time_ph} AND {time_ph}
            ORDER BY time
        """
        
        params = all_ids + [start_dt, end_dt]
        # Ensure params are correct types for driver
        if isinstance(self.loader, SQLiteLoader):
            params = all_ids + [start_dt.strftime('%Y-%m-%d %H:%M:%S'), end_dt.strftime('%Y-%m-%d %H:%M:%S')]

        df = pd.read_sql_query(query, self.loader.get_conn(), params=params)
        
        if df.empty: return {'status': 'no_data', 'correlation': 0}
        
        df['time'] = pd.to_datetime(df['time'])
        pivot = df.pivot(index='time', columns='station_id', values=variable)
        if station_id not in pivot.columns: return {'status': 'no_data', 'correlation': 0}
        
        pivot = pivot.interpolate(method='time', limit_direction='both', limit=2).dropna()
        if len(pivot) < 5: return {'status': 'insufficient_points', 'correlation': 0}
        
        corrs = []
        for nid in nb_ids:
            if nid in pivot.columns:
                c = pivot[station_id].corr(pivot[nid])
                if not np.isnan(c): corrs.append(c)
        
        if not corrs: return {'status': 'no_valid_correlations', 'correlation': 0}
        
        med_corr = np.median(corrs)
        return {
            'status': 'success', 'median_corr': med_corr, 'n_neighbors': len(corrs),
            'is_trend_consistent': med_corr > 0.6 or np.max(corrs) > 0.8,
            'neighbor_ids': nb_ids, 'pivot_data': pivot  # Add detailed data for reporting
        }

    def detect_station(self, station_id: str) -> Dict:
        df = self.loader.get_window_data(station_id, self.start_time, self.end_time, self.window_hours)
        if df.empty or len(df) < 3: return {'station_id': station_id, 'status': 'insufficient_data', 'has_anomaly': False}
        
        res = {'station_id': station_id, 'window_start': str(df['time'].min()), 'window_end': str(df['time'].max()), 
               'data_count': len(df), 'anomalies': {}, 'has_anomaly': False}
        
        for var, cfg in self.DETECTION_VARS.items():
            info = self._detect_variable(df, var, cfg)
            if info:
                if self.spatial_verify:
                    for rec in info['anomaly_records']:
                        trend = self.verify_spatial_trend(station_id, rec['time'], var, self.window_hours * 60)
                        if trend.get('status') == 'success':
                            corr = trend['median_corr']
                            if trend['is_trend_consistent']:
                                rec.update({'type': 'weather_event', 'label': '🌧️ Weather Event', 'desc': f"Trend Consistent (Corr: {corr:.2f})"})
                            elif corr < 0.3:
                                rec.update({
                                    'type': 'critical_failure', 
                                    'label': '🔴 Device Failure', 
                                    'desc': f"Trend Inconsistent (Corr: {corr:.2f})",
                                    'correlation': corr,
                                    'neighbor_ids': trend.get('neighbor_ids', []),
                                    'detail_data': trend.get('pivot_data')  # Store detailed time series
                                })
                            else:
                                rec.update({'type': 'warning', 'label': '⚠️ Suspected', 'desc': f"Weak Correlation (Corr: {corr:.2f})"})
                        else:
                             rec.update({'label': '⚠️ Unverified Anomaly', 'desc': f"Spatial Skip: {trend.get('status')}"})
                
                res['anomalies'][var] = info
                res['has_anomaly'] = True
        
        return res

    def _detect_variable(self, df, var, config):
        if var not in df.columns: return None
        vals = df[var].values
        if np.all(np.isnan(vals)): return None
        
        if self.temporal_method == 'arima': mask, stats = self.ts_detector.detect_arima_residuals(vals, 3.0)
        elif self.temporal_method == 'zscore': mask, stats = self.stat_detector.detect_zscore(vals, 3.0)
        elif self.temporal_method == 'isolation_forest': mask, stats = self.ml_detector.detect_isolation_forest(vals)
        else: mask, stats = self.stat_detector.detect_3sigma(vals, config['threshold'])
        
        if not np.any(mask) or 'error' in stats: return None
        
        recs = []
        for idx in np.where(mask)[0]:
            recs.append({'time': str(df.iloc[idx]['time']), 'value': float(vals[idx]), 'deviation': 0.0}) # Simplified deviation
            
        return {'name': config['name'], 'unit': config['unit'], 'count': int(np.sum(mask)), 
                'method': self.temporal_method, 'statistics': stats, 'anomaly_records': recs}

    def detect_all_stations(self):
        return [self.detect_station(row['station_id']) for _, row in self.loader.get_all_stations().iterrows()]

    def detect_subsequence_anomalies(self, station_id: str, 
                                      variables: List[str] = None,
                                      window: int = None) -> Dict:
        """
        Detect subsequence (pattern) anomalies for a station.
        
        Unlike point anomaly detection which identifies individual outliers,
        subsequence detection finds unusual patterns/segments in the time series.
        Uses Matrix Profile to identify events where scores exceed the 95th percentile.
        
        Parameters:
        -----------
        station_id: Station to analyze
        variables: List of variables to check (default: all)
        window: Subsequence window length (auto-detected if None)
        
        Returns:
        --------
        Dict with subsequence anomaly events for each variable
        """
        df = self.loader.get_window_data(station_id, self.start_time, self.end_time, self.window_hours)
        
        if df.empty or len(df) < 20:
            return {
                'station_id': station_id,
                'status': 'insufficient_data',
                'message': 'Need at least 20 data points for subsequence detection',
                'subsequence_anomalies': {}
            }
        
        variables = variables or list(self.DETECTION_VARS.keys())
        results = {
            'station_id': station_id,
            'window_start': str(df['time'].min()),
            'window_end': str(df['time'].max()),
            'data_count': len(df),
            'subsequence_anomalies': {},
            'has_subsequence_anomaly': False
        }
        
        for var in variables:
            if var not in df.columns:
                continue
            
            vals = df[var].dropna().values
            if len(vals) < 20:
                continue
            
            # Get Matrix Profile scores and events
            scores, mp_info = SubsequenceDetector.detect_matrix_profile(
                vals, window=window, threshold_percentile=95
            )
            
            if 'error' in mp_info:
                continue
            
            times = df['time']
            events = mp_info.get('events', [])
            
            # Add timestamps and duration to events
            for event in events:
                if event['start_idx'] < len(times):
                    event['start_time'] = times.iloc[event['start_idx']].strftime('%Y-%m-%d %H:%M:%S')
                if event['end_idx'] < len(times):
                    event['end_time'] = times.iloc[min(event['end_idx'], len(times)-1)].strftime('%Y-%m-%d %H:%M:%S')
                # Calculate duration in hours
                if 'start_time' in event and 'end_time' in event:
                    start = pd.to_datetime(event['start_time'])
                    end = pd.to_datetime(event['end_time'])
                    event['duration_hours'] = round((end - start).total_seconds() / 3600, 1)
                event['severity'] = 'high' if event.get('length', 0) > 20 else 'medium'
            
            has_anomaly = len(events) > 0
            
            var_result = {
                'variable': var,
                'name': self.DETECTION_VARS.get(var, {}).get('name', var),
                'window_length': mp_info.get('window'),
                'threshold_percentile': 95,
                'has_anomaly': has_anomaly,
                'num_events': len(events),
                'events': events
            }
            
            results['subsequence_anomalies'][var] = var_result
            
            if has_anomaly:
                results['has_subsequence_anomaly'] = True
        
        return results

    def comprehensive_analysis(self, station_id: str, 
                                include_subsequence: bool = True,
                                subsequence_window: int = None) -> Dict:
        """
        Comprehensive anomaly analysis combining:
        1. Point anomaly detection (individual outliers)
        2. Subsequence anomaly detection (unusual patterns)
        3. Spatial verification (if enabled)
        
        This is the main analysis entry point for the weather pilot.
        
        Parameters:
        -----------
        station_id: Station to analyze
        include_subsequence: Whether to run subsequence detection
        subsequence_window: Window for subsequence detection (auto if None)
        
        Returns:
        --------
        Dict with comprehensive analysis results
        """
        df = self.loader.get_window_data(station_id, self.start_time, self.end_time, self.window_hours)
        
        if df.empty:
            return {
                'station_id': station_id,
                'status': 'no_data',
                'analysis_type': 'comprehensive',
                'point_anomalies': {},
                'subsequence_anomalies': {},
                'summary': {'total_point_anomalies': 0, 'total_subsequence_events': 0}
            }
        
        result = {
            'station_id': station_id,
            'analysis_type': 'comprehensive',
            'window_start': str(df['time'].min()),
            'window_end': str(df['time'].max()),
            'data_count': len(df),
            'timestamp': datetime.now().isoformat(),
            'point_anomalies': {},
            'subsequence_anomalies': {},
            'summary': {}
        }
        
        # 1. Point Anomaly Detection
        point_result = self.detect_station(station_id)
        result['point_anomalies'] = point_result.get('anomalies', {})
        result['has_point_anomaly'] = point_result.get('has_anomaly', False)
        
        total_point = sum(
            info.get('count', 0) 
            for info in result['point_anomalies'].values()
        )
        
        # 2. Subsequence Anomaly Detection
        if include_subsequence and len(df) >= 20:
            subseq_result = self.detect_subsequence_anomalies(
                station_id, 
                window=subsequence_window
            )
            result['subsequence_anomalies'] = subseq_result.get('subsequence_anomalies', {})
            result['has_subsequence_anomaly'] = subseq_result.get('has_subsequence_anomaly', False)
        else:
            result['has_subsequence_anomaly'] = False
        
        total_subseq = sum(
            info.get('num_events', 0) 
            for info in result['subsequence_anomalies'].values()
        )
        
        # 3. Summary
        result['summary'] = {
            'total_point_anomalies': total_point,
            'total_subsequence_events': total_subseq,
            'variables_with_point_anomalies': list(result['point_anomalies'].keys()),
            'variables_with_subsequence_anomalies': [
                k for k, v in result['subsequence_anomalies'].items() 
                if v.get('has_anomaly', False)
            ],
            'overall_status': self._determine_status(total_point, total_subseq)
        }
        
        return result
    
    def _determine_status(self, point_count: int, subseq_count: int) -> str:
        """Determine overall status based on anomaly counts."""
        if point_count == 0 and subseq_count == 0:
            return 'normal'
        elif point_count > 5 or subseq_count > 3:
            return 'critical'
        elif point_count > 2 or subseq_count > 1:
            return 'warning'
        else:
            return 'attention'
    
    def analyze_all_stations(self, include_subsequence: bool = True) -> List[Dict]:
        """Run comprehensive analysis on all stations."""
        stations = self.loader.get_all_stations()
        results = []
        
        for _, row in stations.iterrows():
            result = self.comprehensive_analysis(
                row['station_id'], 
                include_subsequence=include_subsequence
            )
            results.append(result)
        
        return results

    def close(self):
        self.loader.close()

class ReportGenerator:
    @staticmethod
    def generate_comprehensive_report(results: List[Dict], window_info: str) -> str:
        """
        Generate comprehensive report including both point and subsequence anomalies.
        """
        lines = [
            "=" * 80,
            "📊 COMPREHENSIVE ANOMALY ANALYSIS REPORT",
            "=" * 80,
            f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Analysis Window: {window_info}",
            "-" * 80
        ]
        
        # Summary statistics
        total_stations = len(results)
        stations_with_point = sum(1 for r in results if r.get('has_point_anomaly'))
        stations_with_subseq = sum(1 for r in results if r.get('has_subsequence_anomaly'))
        
        lines.append(f"\n📈 SUMMARY")
        lines.append(f"   Total Stations Analyzed: {total_stations}")
        lines.append(f"   Stations with Point Anomalies: {stations_with_point}")
        lines.append(f"   Stations with Subsequence Anomalies: {stations_with_subseq}")
        lines.append("-" * 80)
        
        # Detailed results for each station
        for r in results:
            if not r.get('has_point_anomaly') and not r.get('has_subsequence_anomaly'):
                continue
            
            summary = r.get('summary', {})
            status_icon = {'normal': '✅', 'attention': '⚠️', 'warning': '🟡', 'critical': '🔴'}.get(
                summary.get('overall_status', 'normal'), '❓'
            )
            
            lines.append(f"\n{status_icon} Station: {r['station_id']}")
            lines.append(f"   Status: {summary.get('overall_status', 'unknown').upper()}")
            lines.append(f"   Data Points: {r.get('data_count', 0)}")
            lines.append(f"   Window: {r.get('window_start', 'N/A')} to {r.get('window_end', 'N/A')}")
            
            # Point anomalies
            if r.get('has_point_anomaly'):
                lines.append(f"\n   📍 POINT ANOMALIES ({summary.get('total_point_anomalies', 0)} total)")
                for var, info in r.get('point_anomalies', {}).items():
                    lines.append(f"      • {info['name']}: {info['count']} anomalies")
                    for rec in info.get('anomaly_records', [])[:3]:  # Limit to 3
                        label = rec.get('label', 'Anomaly')
                        lines.append(f"        - {rec['time']}: {rec['value']:.2f} {info['unit']} → {label}")
                    if len(info.get('anomaly_records', [])) > 3:
                        lines.append(f"        ... and {len(info['anomaly_records']) - 3} more")
            
            # Subsequence anomalies
            if r.get('has_subsequence_anomaly'):
                lines.append(f"\n   📐 SUBSEQUENCE ANOMALIES (Unusual Patterns)")
                for var, info in r.get('subsequence_anomalies', {}).items():
                    if not info.get('has_anomaly', False):
                        continue
                    
                    events = info.get('events', [])
                    lines.append(f"      • {info.get('name', var)}:")
                    lines.append(f"        Method: Matrix Profile | Window: {info.get('window_length', 'N/A')}")
                    lines.append(f"        Anomalous Events: {len(events)}")
                    for e in events[:3]:
                        severity = e.get('severity', 'medium')
                        severity_icon = '🔴' if severity == 'high' else '🟡'
                        lines.append(f"          {severity_icon} {e.get('start_time', 'N/A')} to {e.get('end_time', 'N/A')} ({e.get('duration_hours', 'N/A')}h)")
            
            lines.append("")
        lines.append("=" * 80)
        lines.append("📝 Legend:")
        lines.append("   Point Anomaly: Individual data point that deviates from expected values")
        lines.append("   Subsequence Anomaly: A segment/pattern that is unusual compared to others")
        lines.append("=" * 80)
        return "\n".join(lines)




    @staticmethod
    def generate_text_report(results, window_info, method):
        lines = ["ANOMALY DETECTION REPORT", f"Date: {datetime.now()}", f"Window: {window_info}", "-"*50]
        anom = [r for r in results if r.get('has_anomaly')]
        lines.append(f"Total: {len(results)} | Anomalous: {len(anom)}")
        lines.append("-" * 50)
        for r in anom:
            lines.append(f"[Station: {r['station_id']}]")
            for v, info in r['anomalies'].items():
                lines.append(f"  ⚠️  {v}: {info['count']} anomalies")
                for rec in info['anomaly_records']:
                    lines.append(f"    • {rec['time']}: {rec['value']} -> {rec.get('label', 'Anomaly')} ({rec.get('desc', '')})")
                    
                    # If Device Failure, print detailed time series data
                    if rec.get('type') == 'critical_failure' and 'detail_data' in rec:
                        lines.append(f"\n    📊 DETAILED DIAGNOSIS - Device Failure at {r['station_id']}")
                        lines.append(f"    Variable: {v} | Window: {window_info}")
                        lines.append(f"    " + "="*70)
                        
                        pivot = rec['detail_data']
                        station_id = r['station_id']
                        neighbor_ids = rec.get('neighbor_ids', [])
                        
                        # Print header
                        header = f"    {'Time':<20} | {station_id:>12} |"
                        for nid in neighbor_ids[:5]:  # Limit to 5 neighbors for readability
                            header += f" {nid:>12} |"
                        lines.append(header)
                        lines.append(f"    " + "-"*70)
                        
                        # Print data rows
                        for idx, row in pivot.iterrows():
                            time_str = idx.strftime('%Y-%m-%d %H:%M')
                            row_str = f"    {time_str:<20} | {row[station_id]:>12.2f} |"
                            for nid in neighbor_ids[:5]:
                                if nid in row.index:
                                    row_str += f" {row[nid]:>12.2f} |"
                                else:
                                    row_str += f" {'---':>12} |"
                            lines.append(row_str)
                        
                        lines.append(f"    " + "="*70)
                        lines.append(f"    💡 Analysis: Station {station_id} shows trend inconsistent with {len(neighbor_ids)} neighbors")
                        lines.append(f"    Correlation: {rec.get('correlation', 0):.2f} (< 0.3 indicates likely sensor failure)\n")
                        
            lines.append("")
        return "\n".join(lines)

class LongTermHealthChecker:
    """
    Long-Term Sensor Health Checker
    
    Detects chronic sensor problems over extended periods (days/weeks):
    - Stalled wind speed sensors (excessive zero values)
    - Failed wind direction sensors (excessive NULL values)  
    - Degraded sensor quality (low variance, poor correlation)
    """
    
    def __init__(self, loader: DataLoader):
        self.loader = loader
        self.ZERO_RATIO_THRESHOLD = 0.3   # > 30% zeros
        self.NULL_RATIO_THRESHOLD = 0.5   # > 50% missing
        self.LOW_VARIANCE_THRESHOLD = 0.1  # Variance too low
    
    def get_long_term_data(self, station_id: str, days: int) -> pd.DataFrame:
        """Get data for specified number of days."""
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        return self.loader.get_window_data(
            station_id, 
            start_time=start_time.strftime('%Y-%m-%d %H:%M:%S'),
            end_time=end_time.strftime('%Y-%m-%d %H:%M:%S')
        )
    
    def check_wind_speed_health(self, df: pd.DataFrame) -> Dict:
        """Check wind speed sensor for stalling/stuck issues."""
        wind_speed = df['wind_speed']
        zero_ratio = (wind_speed == 0).sum() / len(wind_speed) if len(wind_speed) > 0 else 0
        null_ratio = wind_speed.isna().sum() / len(wind_speed) if len(wind_speed) > 0 else 1
        variance = wind_speed.dropna().var() if len(wind_speed.dropna()) > 1 else 0
        
        issues = []
        if zero_ratio > self.ZERO_RATIO_THRESHOLD:
            issues.append(f"High zero ratio ({zero_ratio:.1%}) - sensor may be stalled")
        if null_ratio > self.NULL_RATIO_THRESHOLD:
            issues.append(f"High missing rate ({null_ratio:.1%})")
        if variance < self.LOW_VARIANCE_THRESHOLD and null_ratio < 0.9:
            issues.append(f"Low variance ({variance:.3f}) - sensor may be stuck")
        
        return {
            'variable': 'wind_speed',
            'zero_ratio': zero_ratio,
            'null_ratio': null_ratio,
            'variance': variance,
            'issues': issues,
            'severity': 'critical' if issues else 'healthy'
        }
    
    def check_wind_dir_health(self, df: pd.DataFrame) -> Dict:
        """Check wind direction sensor for failure/stuck issues."""
        # Note: wind_dir not in current schema, would need to add if available
        # For now, return placeholder
        return {
            'variable': 'wind_dir',
            'null_ratio': 1.0,
            'issues': ['wind_dir not available in current schema'],
            'severity': 'unknown'
        }
    
    def check_station_health(self, station_id: str, days: int = 30) -> Dict:
        """Comprehensive health check for a station over N days."""
        df = self.get_long_term_data(station_id, days)
        
        if df.empty:
            return {
                'station_id': station_id,
                'status': 'no_data',
                'data_points': 0,
                'message': f'No data for last {days} days'
            }
        
        # Data completeness
        total_expected = days * 24 * 6  # 6 obs/hour
        completeness = len(df) / total_expected
        
        # Check variables
        reports = []
        reports.append(self.check_wind_speed_health(df))
        
        # Overall status
        critical = any(r['severity'] == 'critical' for r in reports)
        
        return {
            'station_id': station_id,
            'analysis_period_days': days,
            'data_completeness': completeness,
            'total_data_points': len(df),
            'overall_status': 'critical' if critical else 'healthy',
            'variable_reports': reports
        }
    
    def check_all_stations(self, days: int = 30) -> List[Dict]:
        """Check all stations for long-term health issues."""
        stations_df = self.loader.get_all_stations()
        reports = []
        
        for _, station_row in stations_df.iterrows():
            station_id = station_row['station_id']
            report = self.check_station_health(station_id, days)
            reports.append(report)
        
        return reports


def main():
    parser = argparse.ArgumentParser(
        description='Weather Anomaly Detection System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Point anomaly detection only
  python anomaly_detector.py --end "NOW" --window 6 --spatial-verify
  
  # Comprehensive analysis (point + subsequence anomalies) - RECOMMENDED
  python anomaly_detector.py --end "NOW" --window 168 --comprehensive
  python anomaly_detector.py --end "NOW" --window 168 --comprehensive --station dodoni
  
  # Subsequence-only detection
  python anomaly_detector.py --end "NOW" --window 168 --subsequence-only
  
  # Long-term sensor health check
  python anomaly_detector.py --health-check --days 30
  python anomaly_detector.py --health-check --days 7 --station dodoni
        """
    )
    parser.add_argument('--db', default='weather_stream.db', help='SQLite DB path')
    parser.add_argument('--pg-url', help='PostgreSQL Connection String')
    
    # Mode selection
    parser.add_argument('--health-check', action='store_true', 
                       help='Run long-term health check instead of anomaly detection')
    parser.add_argument('--comprehensive', action='store_true',
                       help='Run comprehensive analysis (point + subsequence anomalies)')
    parser.add_argument('--subsequence-only', action='store_true',
                       help='Run only subsequence anomaly detection')
    parser.add_argument('--days', type=int, default=30,
                       help='Days to analyze for health check (default: 30)')
    
    # Anomaly detection args
    parser.add_argument('--end', help='End Time (required for anomaly detection)')
    parser.add_argument('--window', type=int, help='Window Hours (required for anomaly detection)')
    parser.add_argument('--temporal-method', default='3sigma', 
                       choices=['3sigma', 'zscore', 'arima', 'isolation_forest'],
                       help='Point anomaly detection method (default: 3sigma)')
    parser.add_argument('--spatial-verify', action='store_true')
    parser.add_argument('--station', help='Specific station to check')
    parser.add_argument('--subseq-window', type=int, default=None,
                       help='Subsequence window length (auto-detect if not specified)')
    parser.add_argument('--output-json', type=str, default=None,
                       help='Export results to JSON file')
    
    args = parser.parse_args()
    
    # Try to get pg_url from environment if not provided via CLI
    if not args.pg_url:
        host = os.environ.get("POSTGRES_TIMESCALE_HOST")
        port = os.environ.get("POSTGRES_TIMESCALE_PORT", "5432")
        user = os.environ.get("POSTGRES_USER")
        pwd = os.environ.get("POSTGRES_PASSWORD")
        db_name = os.environ.get("POSTGRES_DB", "ds_weather_stream")
        
        if host and user and pwd:
            args.pg_url = f"postgresql://{user}:{pwd}@{host}:{port}/{db_name}"
            print("📦 Using PostgreSQL URL from environment variables")
    
    # Create data loader
    if args.pg_url:
        loader = PostgresLoader(args.pg_url)
    else:
        loader = SQLiteLoader(args.db)
    
    try:
        if args.health_check:
            # Long-term health check mode
            print(f"\n{'#'*80}")
            print(f"🏥 LONG-TERM SENSOR HEALTH CHECK")
            print(f"   Period: Last {args.days} days")
            print(f"{'#'*80}\n")
            
            checker = LongTermHealthChecker(loader)
            
            if args.station:
                reports = [checker.check_station_health(args.station, args.days)]
            else:
                reports = checker.check_all_stations(args.days)
            
            # Print summary
            print(f"\n{'='*80}")
            print(f"📋 SUMMARY")
            print(f"{'='*80}\n")
            print(f"{'Station':<20} {'Status':<12} {'Completeness':<15} {'Issues'}")
            print(f"{'-'*80}")
            
            for report in reports:
                if report.get('status') == 'no_data':
                    print(f"{report['station_id']:<20} {'NO DATA':<12} {'0%':<15} N/A")
                    continue
                
                status = report['overall_status'].upper()
                completeness = f"{report['data_completeness']:.1%}"
                issue_count = sum(len(r['issues']) for r in report['variable_reports'])
                
                icon = '✅' if status == 'HEALTHY' else '🔴'
                print(f"{report['station_id']:<20} {icon} {status:<10} {completeness:<15} {issue_count} problems")
                
                # Print detailed issues
                for var_report in report['variable_reports']:
                    if var_report['issues']:
                        for issue in var_report['issues']:
                            print(f"  └─ {var_report['variable']}: {issue}")
            
            print(f"{'-'*80}\n")
            
            # Export to JSON
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = args.output_json or f"health_report_{timestamp}.json"
            with open(output_file, 'w') as f:
                json.dump(reports, f, indent=2, default=str)
            print(f"✅ Report exported to: {output_file}\n")
            
        elif args.comprehensive or args.subsequence_only:
            # Comprehensive analysis mode (point + subsequence)
            if not args.end or not args.window:
                parser.error("--end and --window are required for anomaly detection mode")
            
            print(f"\n{'#'*80}")
            if args.comprehensive:
                print(f"📊 COMPREHENSIVE ANOMALY ANALYSIS")
                print(f"   Mode: Point Anomalies + Subsequence Anomalies")
            else:
                print(f"📐 SUBSEQUENCE ANOMALY DETECTION")
                print(f"   Mode: Pattern-based detection only")
            print(f"   Window: Last {args.window} hours")
            print(f"   Subsequence Window: {'Auto-detect' if not args.subseq_window else args.subseq_window}")
            print(f"{'#'*80}\n")
            
            detector = AnomalyDetector(
                db_path=args.db, pg_url=args.pg_url,
                end_time=args.end, window_hours=args.window,
                temporal_method=args.temporal_method, spatial_verify=args.spatial_verify
            )
            
            if args.subsequence_only:
                # Subsequence-only mode
                if args.station:
                    results = [detector.detect_subsequence_anomalies(
                        args.station, window=args.subseq_window
                    )]
                else:
                    stations = detector.loader.get_all_stations()
                    results = [
                        detector.detect_subsequence_anomalies(
                            row['station_id'], window=args.subseq_window
                        ) 
                        for _, row in stations.iterrows()
                    ]
                
                # Simple output for subsequence-only
                for r in results:
                    if r.get('has_subsequence_anomaly'):
                        print(f"\n🔍 {r['station_id']}: Subsequence anomalies detected")
                        for var, info in r.get('subsequence_anomalies', {}).items():
                            if info.get('has_anomaly', False):
                                events = info.get('events', [])
                                print(f"   {info.get('name', var)}: {len(events)} event(s)")
                                for e in events:
                                    print(f"     - {e.get('start_time', 'N/A')} to {e.get('end_time', 'N/A')} ({e.get('severity', 'medium')})")
            else:
                # Full comprehensive analysis
                if args.station:
                    results = [detector.comprehensive_analysis(
                        args.station, 
                        include_subsequence=True,
                        subsequence_window=args.subseq_window
                    )]
                else:
                    results = detector.analyze_all_stations(include_subsequence=True)
                
                # Print comprehensive report
                print(ReportGenerator.generate_comprehensive_report(
                    results, f"Last {args.window}h from {args.end}"
                ))
            
            # Export to JSON if requested
            if args.output_json:
                with open(args.output_json, 'w') as f:
                    json.dump(results, f, indent=2, default=str)
                print(f"\n✅ Results exported to: {args.output_json}")
            
            detector.close()
            
        else:
            # Original point anomaly detection mode
            if not args.end or not args.window:
                parser.error("--end and --window are required for anomaly detection mode")
            
            detector = AnomalyDetector(
                db_path=args.db, pg_url=args.pg_url,
                end_time=args.end, window_hours=args.window,
                temporal_method=args.temporal_method, spatial_verify=args.spatial_verify
            )
            
            results = [detector.detect_station(args.station)] if args.station else detector.detect_all_stations()
            print(ReportGenerator.generate_text_report(results, f"Last {args.window}h from {args.end}", args.temporal_method))
            
            # Export to JSON if requested
            if args.output_json:
                with open(args.output_json, 'w') as f:
                    json.dump(results, f, indent=2, default=str)
                print(f"\n✅ Results exported to: {args.output_json}")
            
            detector.close()
    
    finally:
        loader.close()

if __name__ == '__main__':
    main()

# Usage Examples:
# 
# 1. Point anomaly detection (individual outliers):
#    python anomaly_detector.py --end "NOW" --window 6 --spatial-verify
#    python anomaly_detector.py --end "2025-11-21 02:00:00" --window 6 --temporal-method arima
#
# 2. Comprehensive analysis (point + subsequence anomalies) - RECOMMENDED for 7-day context:
#    python anomaly_detector.py --end "NOW" --window 168 --comprehensive
#    python anomaly_detector.py --end "NOW" --window 168 --comprehensive --station dodoni
#    python anomaly_detector.py --end "NOW" --window 168 --comprehensive --output-json results.json
#
# 3. Subsequence-only detection (pattern anomalies):
#    python anomaly_detector.py --end "NOW" --window 168 --subsequence-only
#    python anomaly_detector.py --end "NOW" --window 168 --subsequence-only --subseq-window 24
#
# 4. Long-term sensor health check (days/weeks):
#    python anomaly_detector.py --health-check --days 30
#    python anomaly_detector.py --health-check --days 7 --station dodoni
#
# 5. Data collection:
#    python streaming_collector_sqlite.py --continuous
#
# 6. With TimescaleDB:
#    python anomaly_detector.py --pg-url "postgresql://user:pass@localhost:5432/weather" --end "NOW" --window 168 --comprehensive
#
# Notes:
# - For subsequence detection, use larger windows (e.g., 168 hours = 7 days) for better context
# - Subsequence detection uses Matrix Profile algorithm (requires: pip install stumpy)
# - Auto window detection uses autocorrelation to find optimal pattern length