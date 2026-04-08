#!/usr/bin/env python3
"""
Interactive Anomaly Visualization System
=========================================
Generates an interactive map with time series visualization for detected anomalies.

Features:
1. Map showing all stations (normal=blue, anomaly=red)
2. Click on station to view time series with anomaly markers
3. Support for both point anomalies and subsequence anomalies
4. Neighbor connections visualization

Usage:
    python visualize_anomalies.py --end "NOW" --window 168 --comprehensive
    python visualize_anomalies.py --end "NOW" --window 24 --station dodoni
"""

import sqlite3
import pandas as pd
import numpy as np
import folium
from folium import IFrame
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import argparse
import base64
from io import BytesIO
import json
import math
import warnings
warnings.filterwarnings('ignore')

# Import from anomaly_detector
from anomaly_detector import (
    AnomalyDetector, SQLiteLoader, PostgresLoader,
    SubsequenceDetector, SpatialDetector, ReportGenerator
)

# Check for optional dependencies
try:
    import stumpy
    STUMPY_AVAILABLE = True
except ImportError:
    STUMPY_AVAILABLE = False


class AnomalyVisualizer:
    """
    Interactive visualization combining map and time series plots.
    """
    
    # Color scheme
    COLORS = {
        'normal': '#3388ff',      # Blue
        'anomaly': '#dc3545',     # Red
        'warning': '#ffc107',     # Yellow
        'weather_event': '#28a745',  # Green
        'point_anomaly': '#dc3545',  # Red dot
        'subsequence_anomaly': 'rgba(255, 0, 0, 0.2)',  # Red region
        'neighbor_line': '#6c757d',  # Gray
    }
    
    DETECTION_VARS = {
        'temp_out': {'name': 'Temperature', 'unit': '°C', 'color': '#e74c3c'},
        'out_hum': {'name': 'Humidity', 'unit': '%', 'color': '#3498db'},
        'wind_speed': {'name': 'Wind Speed', 'unit': 'km/h', 'color': '#2ecc71'},
        'bar': {'name': 'Pressure', 'unit': 'hPa', 'color': '#9b59b6'},
        'rain': {'name': 'Rain', 'unit': 'mm', 'color': '#1abc9c'},
    }
    
    def __init__(self, db_path: str = None, pg_url: str = None):
        """Initialize with database connection."""
        if pg_url:
            self.loader = PostgresLoader(pg_url)
            self.db_type = 'postgres'
        else:
            self.loader = SQLiteLoader(db_path or 'weather_stream.db')
            self.db_type = 'sqlite'
        
        self.stations_df = self.loader.get_all_stations()
        print(f"📍 Loaded {len(self.stations_df)} stations")
    
    def get_haversine_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two coordinates in km."""
        R = 6371
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        a = math.sin((lat2-lat1)/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2-lon1)/2)**2
        return R * 2 * math.asin(math.sqrt(a))
    
    def find_neighbors(self, station_id: str, max_distance: float = 100, max_elev_diff: float = 500):
        """Find neighboring stations."""
        target = self.stations_df[self.stations_df['station_id'] == station_id].iloc[0]
        neighbors = []
        
        for _, row in self.stations_df.iterrows():
            if row['station_id'] == station_id:
                continue
            dist = self.get_haversine_distance(
                target['latitude'], target['longitude'],
                row['latitude'], row['longitude']
            )
            elev_diff = abs(target['elevation'] - row['elevation'])
            
            if dist <= max_distance and elev_diff <= max_elev_diff:
                neighbors.append({
                    'station_id': row['station_id'],
                    'name': row['station_name_en'],
                    'distance': dist,
                    'elev_diff': elev_diff
                })
        
        return neighbors
    
    def create_time_series_plot(self, station_id: str, start_time: str, end_time: str,
                                 point_anomalies: dict = None, 
                                 subsequence_anomalies: dict = None,
                                 variables: list = None) -> str:
        """
        Create time series plot with anomaly markers.
        Returns base64 encoded PNG image.
        """
        # Get data
        df = self.loader.get_window_data(station_id, start_time, end_time)
        if df.empty:
            return None
        
        df['time'] = pd.to_datetime(df['time'])
        variables = variables or list(self.DETECTION_VARS.keys())
        
        # Filter to available variables
        available_vars = [v for v in variables if v in df.columns and not df[v].isna().all()]
        if not available_vars:
            return None
        
        # Create figure
        n_vars = len(available_vars)
        fig, axes = plt.subplots(n_vars, 1, figsize=(12, 3 * n_vars), sharex=True)
        if n_vars == 1:
            axes = [axes]
        
        fig.suptitle(f'Station: {station_id}\n{start_time} to {end_time}', fontsize=14, fontweight='bold')
        
        for idx, var in enumerate(available_vars):
            ax = axes[idx]
            var_config = self.DETECTION_VARS.get(var, {'name': var, 'unit': '', 'color': '#333'})
            
            # Plot time series
            ax.plot(df['time'], df[var], color=var_config['color'], linewidth=1.5, 
                   label=f"{var_config['name']} ({var_config['unit']})")
            
            # Mark point anomalies
            if point_anomalies and var in point_anomalies:
                anomaly_info = point_anomalies[var]
                for rec in anomaly_info.get('anomaly_records', []):
                    anom_time = pd.to_datetime(rec['time'])
                    anom_val = rec['value']
                    
                    # Get label/type for coloring
                    anom_type = rec.get('type', 'anomaly')
                    if anom_type == 'critical_failure':
                        color = self.COLORS['anomaly']
                        marker = 'X'
                        label = '🔴 Device Failure'
                    elif anom_type == 'weather_event':
                        color = self.COLORS['weather_event']
                        marker = 'D'
                        label = '🌧️ Weather Event'
                    else:
                        color = self.COLORS['warning']
                        marker = 'o'
                        label = '⚠️ Anomaly'
                    
                    ax.scatter([anom_time], [anom_val], color=color, s=100, 
                              marker=marker, zorder=5, edgecolors='black', linewidths=1)
                    ax.annotate(label, (anom_time, anom_val), 
                               textcoords="offset points", xytext=(5, 10),
                               fontsize=8, color=color)
            
            # Mark subsequence anomalies (highlight regions)
            if subsequence_anomalies and var in subsequence_anomalies:
                subseq_info = subsequence_anomalies[var]
                for event in subseq_info.get('events', []):
                    start_idx = event.get('start_idx', 0)
                    end_idx = event.get('end_idx', len(df)-1)
                    
                    # Get corresponding times
                    if start_idx < len(df) and end_idx <= len(df):
                        event_start = df['time'].iloc[start_idx]
                        event_end = df['time'].iloc[min(end_idx, len(df)-1)]
                        
                        # Draw shaded region
                        ax.axvspan(event_start, event_end, 
                                  alpha=0.3, color='red', 
                                  label='Subsequence Anomaly')
                        
                        # Add label
                        severity = event.get('severity', 'medium')
                        severity_icon = '🔴' if severity == 'high' else '🟡'
                        mid_time = event_start + (event_end - event_start) / 2
                        y_pos = ax.get_ylim()[1] * 0.95
                        ax.annotate(f'{severity_icon} Pattern Anomaly', 
                                   (mid_time, y_pos), fontsize=8, 
                                   ha='center', color='red')
            
            # Formatting
            ax.set_ylabel(f"{var_config['name']}\n({var_config['unit']})")
            ax.grid(True, alpha=0.3)
            ax.legend(loc='upper left', fontsize=8)
            
            # Statistics annotation
            stats_text = f"Mean: {df[var].mean():.2f} | Std: {df[var].std():.2f}"
            ax.text(0.99, 0.02, stats_text, transform=ax.transAxes, 
                   fontsize=8, ha='right', va='bottom', 
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        # Format x-axis
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        axes[-1].xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.xticks(rotation=45)
        
        plt.tight_layout()
        
        # Convert to base64
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close(fig)
        
        return img_base64
    
    def create_comparison_plot(self, station_id: str, variable: str,
                                start_time: str, end_time: str,
                                neighbor_ids: list = None) -> str:
        """
        Create comparison plot with neighboring stations.
        Useful for spatial verification visualization.
        """
        df_main = self.loader.get_window_data(station_id, start_time, end_time)
        if df_main.empty or variable not in df_main.columns:
            return None
        
        df_main['time'] = pd.to_datetime(df_main['time'])
        
        fig, ax = plt.subplots(figsize=(12, 5))
        
        # Plot main station (thicker line)
        ax.plot(df_main['time'], df_main[variable], 
               linewidth=2.5, label=f'{station_id} (Target)', 
               color=self.COLORS['anomaly'])
        
        # Plot neighbors
        if neighbor_ids:
            colors = plt.cm.Blues(np.linspace(0.4, 0.8, len(neighbor_ids)))
            for i, nid in enumerate(neighbor_ids[:5]):  # Limit to 5 neighbors
                df_neighbor = self.loader.get_window_data(nid, start_time, end_time)
                if not df_neighbor.empty and variable in df_neighbor.columns:
                    df_neighbor['time'] = pd.to_datetime(df_neighbor['time'])
                    ax.plot(df_neighbor['time'], df_neighbor[variable],
                           linewidth=1, alpha=0.7, label=nid, color=colors[i])
        
        var_config = self.DETECTION_VARS.get(variable, {'name': variable, 'unit': ''})
        ax.set_ylabel(f"{var_config['name']} ({var_config['unit']})")
        ax.set_xlabel('Time')
        ax.set_title(f'Spatial Comparison: {station_id} vs Neighbors\nVariable: {var_config["name"]}')
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, alpha=0.3)
        
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        buffer = BytesIO()
        plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        plt.close(fig)
        
        return img_base64
    
    def generate_interactive_map(self, detection_results: list, 
                                  start_time: str, end_time: str,
                                  output_file: str = 'anomaly_map.html',
                                  show_neighbors: bool = True,
                                  max_neighbor_dist: float = 100):
        """
        Generate interactive map with anomaly visualization.
        
        Parameters:
        -----------
        detection_results: List of detection results from AnomalyDetector
        start_time, end_time: Time window for visualization
        output_file: Output HTML file path
        show_neighbors: Whether to show neighbor connections
        max_neighbor_dist: Maximum distance for neighbor connections (km)
        """
        
        # Create base map centered on Greece
        center_lat = self.stations_df['latitude'].mean()
        center_lon = self.stations_df['longitude'].mean()
        
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=7,
            tiles='CartoDB positron'
        )
        
        # Add title
        title_html = f'''
        <div style="position: fixed; top: 10px; left: 60px; z-index: 1000; 
                    background: white; padding: 10px 20px; border-radius: 8px;
                    box-shadow: 0 2px 6px rgba(0,0,0,0.3); font-family: Arial;">
            <h3 style="margin: 0;">🌦️ Weather Anomaly Detection</h3>
            <p style="margin: 5px 0 0 0; font-size: 12px; color: #666;">
                Window: {start_time} to {end_time}<br>
                Click on a station to view time series
            </p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(title_html))
        
        # Build results lookup
        results_map = {r['station_id']: r for r in detection_results if 'station_id' in r}
        
        # Track anomalous stations for legend
        anomaly_stations = []
        normal_stations = []
        
        # Draw neighbor connections first (so they appear behind markers)
        if show_neighbors:
            processed_pairs = set()
            for _, s1 in self.stations_df.iterrows():
                for _, s2 in self.stations_df.iterrows():
                    if s1['station_id'] >= s2['station_id']:
                        continue
                    
                    pair_key = tuple(sorted([s1['station_id'], s2['station_id']]))
                    if pair_key in processed_pairs:
                        continue
                    
                    dist = self.get_haversine_distance(
                        s1['latitude'], s1['longitude'],
                        s2['latitude'], s2['longitude']
                    )
                    elev_diff = abs(s1['elevation'] - s2['elevation'])
                    
                    if dist <= max_neighbor_dist and elev_diff <= 500:
                        folium.PolyLine(
                            locations=[
                                [s1['latitude'], s1['longitude']],
                                [s2['latitude'], s2['longitude']]
                            ],
                            color=self.COLORS['neighbor_line'],
                            weight=1.5,
                            opacity=0.4,
                            tooltip=f"Distance: {dist:.1f}km"
                        ).add_to(m)
                        processed_pairs.add(pair_key)
        
        # Add station markers
        for _, station in self.stations_df.iterrows():
            station_id = station['station_id']
            result = results_map.get(station_id, {})
            
            # Determine station status
            has_point_anomaly = result.get('has_point_anomaly', False) or result.get('has_anomaly', False)
            has_subseq_anomaly = result.get('has_subsequence_anomaly', False)
            
            if has_point_anomaly or has_subseq_anomaly:
                color = self.COLORS['anomaly']
                icon_name = 'exclamation-triangle'
                anomaly_stations.append(station_id)
            else:
                color = self.COLORS['normal']
                icon_name = 'cloud'
                normal_stations.append(station_id)
            
            # Get anomaly details for popup
            point_anomalies = result.get('point_anomalies', result.get('anomalies', {}))
            subseq_anomalies = result.get('subsequence_anomalies', {})
            
            # Create time series plot
            img_base64 = self.create_time_series_plot(
                station_id, start_time, end_time,
                point_anomalies=point_anomalies,
                subsequence_anomalies=subseq_anomalies
            )
            
            # Build popup content
            popup_html = self._build_popup_html(
                station, result, img_base64, 
                point_anomalies, subseq_anomalies
            )
            
            # Create marker
            iframe = IFrame(popup_html, width=850, height=700)
            popup = folium.Popup(iframe, max_width=900)
            
            folium.CircleMarker(
                location=[station['latitude'], station['longitude']],
                radius=12 if (has_point_anomaly or has_subseq_anomaly) else 8,
                popup=popup,
                tooltip=f"<b>{station['station_name_en']}</b><br>{'🔴 Anomaly Detected!' if (has_point_anomaly or has_subseq_anomaly) else '✅ Normal'}",
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.8,
                weight=2
            ).add_to(m)
        
        # Add legend
        legend_html = self._build_legend_html(len(anomaly_stations), len(normal_stations))
        m.get_root().html.add_child(folium.Element(legend_html))
        
        # Save map
        m.save(output_file)
        print(f"✅ Interactive map saved to: {output_file}")
        print(f"   🔴 Anomaly stations: {len(anomaly_stations)}")
        print(f"   🔵 Normal stations: {len(normal_stations)}")
        
        return output_file
    
    def _build_popup_html(self, station, result, img_base64, 
                          point_anomalies, subseq_anomalies):
        """Build HTML content for station popup."""
        
        station_id = station['station_id']
        station_name = station['station_name_en']
        
        # Status determination
        has_point = bool(point_anomalies)
        has_subseq = any(v.get('has_anomaly', False) for v in subseq_anomalies.values()) if subseq_anomalies else False
        
        if has_point or has_subseq:
            status_badge = '<span style="background:#dc3545;color:white;padding:3px 8px;border-radius:4px;">⚠️ Anomaly Detected</span>'
        else:
            status_badge = '<span style="background:#28a745;color:white;padding:3px 8px;border-radius:4px;">✅ Normal</span>'
        
        # Build anomaly summary
        anomaly_summary = ''
        
        if point_anomalies:
            anomaly_summary += '<h4 style="color:#dc3545;margin:10px 0 5px 0;">📍 Point Anomalies</h4><ul style="margin:0;padding-left:20px;">'
            for var, info in point_anomalies.items():
                var_name = self.DETECTION_VARS.get(var, {}).get('name', var)
                count = info.get('count', len(info.get('anomaly_records', [])))
                anomaly_summary += f'<li><b>{var_name}</b>: {count} anomalies detected</li>'
                
                # Show first few records
                for rec in info.get('anomaly_records', [])[:3]:
                    label = rec.get('label', 'Anomaly')
                    time = rec.get('time', 'N/A')
                    value = rec.get('value', 'N/A')
                    anomaly_summary += f'<ul><li style="font-size:11px;">{time}: {value:.2f} → {label}</li></ul>'
            anomaly_summary += '</ul>'
        
        if has_subseq:
            anomaly_summary += '<h4 style="color:#9b59b6;margin:10px 0 5px 0;">📐 Subsequence Anomalies</h4><ul style="margin:0;padding-left:20px;">'
            for var, info in subseq_anomalies.items():
                if info.get('has_anomaly', False):
                    var_name = self.DETECTION_VARS.get(var, {}).get('name', var)
                    events = info.get('events', [])
                    anomaly_summary += f'<li><b>{var_name}</b>: {len(events)} pattern anomalies</li>'
                    for e in events[:2]:
                        start = e.get('start_time', 'N/A')
                        end = e.get('end_time', 'N/A')
                        duration = e.get('duration_hours', 'N/A')
                        severity = e.get('severity', 'medium')
                        icon = '🔴' if severity == 'high' else '🟡'
                        anomaly_summary += f'<ul><li style="font-size:11px;">{icon} {start} to {end} ({duration}h)</li></ul>'
            anomaly_summary += '</ul>'
        
        if not anomaly_summary:
            anomaly_summary = '<p style="color:#28a745;">No anomalies detected in this time window.</p>'
        
        # Image section
        img_section = ''
        if img_base64:
            img_section = f'<img src="data:image/png;base64,{img_base64}" style="width:100%;border:1px solid #ddd;border-radius:4px;margin-top:10px;">'
        else:
            img_section = '<p style="color:#999;">No data available for visualization.</p>'
        
        # Complete HTML
        html = f'''
        <div style="font-family: Arial, sans-serif; max-width: 800px;">
            <div style="border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 10px;">
                <h2 style="margin: 0 0 5px 0;">🌡️ {station_name}</h2>
                <p style="margin: 0; color: #666; font-size: 12px;">
                    ID: {station_id} | 
                    Lat: {station['latitude']:.4f} | 
                    Lon: {station['longitude']:.4f} | 
                    Elev: {station['elevation']}m
                </p>
                <p style="margin: 5px 0 0 0;">{status_badge}</p>
            </div>
            
            <div style="background: #f8f9fa; padding: 10px; border-radius: 4px; margin-bottom: 10px;">
                <h3 style="margin: 0 0 10px 0;">📊 Detection Summary</h3>
                {anomaly_summary}
            </div>
            
            <div>
                <h3 style="margin: 10px 0;">📈 Time Series Visualization</h3>
                {img_section}
            </div>
        </div>
        '''
        
        return html
    
    def _build_legend_html(self, anomaly_count, normal_count):
        """Build legend HTML."""
        return f'''
        <div style="position: fixed; bottom: 30px; right: 30px; z-index: 1000;
                    background: white; padding: 15px; border-radius: 8px;
                    box-shadow: 0 2px 6px rgba(0,0,0,0.3); font-family: Arial;">
            <h4 style="margin: 0 0 10px 0;">Legend</h4>
            <div style="display: flex; align-items: center; margin-bottom: 5px;">
                <div style="width: 16px; height: 16px; background: {self.COLORS['anomaly']}; 
                            border-radius: 50%; margin-right: 8px;"></div>
                <span>Anomaly ({anomaly_count})</span>
            </div>
            <div style="display: flex; align-items: center; margin-bottom: 5px;">
                <div style="width: 16px; height: 16px; background: {self.COLORS['normal']}; 
                            border-radius: 50%; margin-right: 8px;"></div>
                <span>Normal ({normal_count})</span>
            </div>
            <div style="display: flex; align-items: center;">
                <div style="width: 20px; height: 2px; background: {self.COLORS['neighbor_line']}; 
                            margin-right: 8px;"></div>
                <span>Neighbor Link</span>
            </div>
        </div>
        '''
    
    def close(self):
        """Close database connection."""
        self.loader.close()


def main():
    parser = argparse.ArgumentParser(
        description='Interactive Anomaly Visualization',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Comprehensive visualization (recommended)
  python visualize_anomalies.py --end "NOW" --window 168 --comprehensive
  
  # Point anomaly only
  python visualize_anomalies.py --end "NOW" --window 24 --spatial-verify
  
  # Specific station
  python visualize_anomalies.py --end "NOW" --window 168 --station dodoni
  
  # With TimescaleDB
  python visualize_anomalies.py --pg-url "postgresql://user:pass@host/db" --end "NOW" --window 168
        """
    )
    
    parser.add_argument('--db', default='weather_stream.db', help='SQLite DB path')
    parser.add_argument('--pg-url', help='PostgreSQL Connection String')
    parser.add_argument('--end', required=True, help='End Time ("NOW" or timestamp)')
    parser.add_argument('--window', type=int, required=True, help='Window Hours')
    parser.add_argument('--temporal-method', default='3sigma', 
                       choices=['3sigma', 'zscore', 'arima', 'isolation_forest'])
    parser.add_argument('--spatial-verify', action='store_true')
    parser.add_argument('--comprehensive', action='store_true',
                       help='Run comprehensive analysis (point + subsequence)')
    parser.add_argument('--station', help='Specific station to analyze')
    parser.add_argument('--output', default='anomaly_map.html', help='Output HTML file')
    parser.add_argument('--no-neighbors', action='store_true', help='Hide neighbor connections')
    parser.add_argument('--neighbor-dist', type=float, default=100, 
                       help='Max neighbor distance in km (default: 100)')
    
    args = parser.parse_args()
    
    # Try to get pg_url from environment if not provided via CLI
    if not args.pg_url:
        import os
        host = os.environ.get("POSTGRES_TIMESCALE_HOST")
        port = os.environ.get("POSTGRES_TIMESCALE_PORT", "5432")
        user = os.environ.get("POSTGRES_USER")
        pwd = os.environ.get("POSTGRES_PASSWORD")
        db_name = os.environ.get("POSTGRES_DB", "ds_weather_stream")
        
        if host and user and pwd:
            args.pg_url = f"postgresql://{user}:{pwd}@{host}:{port}/{db_name}"
            print("📦 Using PostgreSQL URL from environment variables")
    
    print(f"\n{'#'*60}")
    print(f"🗺️  INTERACTIVE ANOMALY VISUALIZATION")
    print(f"{'#'*60}")
    
    # Calculate time window
    if args.end.upper() == 'NOW':
        end_time = datetime.now()
    else:
        end_time = pd.to_datetime(args.end)
    start_time = end_time - timedelta(hours=args.window)
    
    start_str = start_time.strftime('%Y-%m-%d %H:%M:%S')
    end_str = end_time.strftime('%Y-%m-%d %H:%M:%S')
    
    print(f"📅 Time Window: {start_str} to {end_str}")
    print(f"📊 Detection Mode: {'Comprehensive' if args.comprehensive else 'Point Anomaly'}")
    print(f"{'#'*60}\n")
    
    # Run anomaly detection
    detector = AnomalyDetector(
        db_path=args.db, pg_url=args.pg_url,
        start_time=start_str, end_time=end_str,
        temporal_method=args.temporal_method,
        spatial_verify=args.spatial_verify
    )
    
    print("🔍 Running anomaly detection...")
    
    if args.comprehensive:
        if args.station:
            results = [detector.comprehensive_analysis(args.station)]
        else:
            results = detector.analyze_all_stations(include_subsequence=True)
    else:
        if args.station:
            results = [detector.detect_station(args.station)]
        else:
            results = detector.detect_all_stations()
    
    # Count anomalies
    anomaly_count = sum(1 for r in results if r.get('has_anomaly') or r.get('has_point_anomaly') or r.get('has_subsequence_anomaly'))
    print(f"✅ Detection complete: {anomaly_count}/{len(results)} stations with anomalies\n")
    
    # Generate visualization
    print("🎨 Generating interactive map...")
    
    visualizer = AnomalyVisualizer(db_path=args.db, pg_url=args.pg_url)
    
    output_file = visualizer.generate_interactive_map(
        detection_results=results,
        start_time=start_str,
        end_time=end_str,
        output_file=args.output,
        show_neighbors=not args.no_neighbors,
        max_neighbor_dist=args.neighbor_dist
    )
    
    # Cleanup
    detector.close()
    visualizer.close()
    
    print(f"\n🌐 Open {output_file} in your browser to view the interactive map!")
    print(f"   💡 Click on any station marker to see detailed time series")


if __name__ == '__main__':
    main()
