#!/usr/bin/env python3
"""
数据查看工具
快速查看数据库中的气象数据
"""

import sqlite3
import pandas as pd
import argparse
from datetime import datetime, timedelta

def view_latest(limit=20):
    """查看最新数据"""
    conn = sqlite3.connect('weather_stream.db')
    
    query = f"""
        SELECT 
            time, 
            station_id, 
            temp_out as '温度(°C)', 
            out_hum as '湿度(%)', 
            wind_speed as '风速(km/h)', 
            bar as '气压(hPa)', 
            rain as '降雨(mm)'
        FROM observations 
        ORDER BY time DESC 
        LIMIT {limit}
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print(f"\n{'='*100}")
    print(f"最新 {limit} 条观测数据")
    print(f"{'='*100}")
    print(df.to_string(index=False))
    print(f"{'='*100}\n")

def view_station(station_id, limit=10):
    """查看特定站点数据"""
    conn = sqlite3.connect('weather_stream.db')
    
    query = f"""
        SELECT 
            time, 
            temp_out as '温度(°C)', 
            out_hum as '湿度(%)', 
            wind_speed as '风速(km/h)', 
            wind_dir_str as '风向',
            bar as '气压(hPa)', 
            rain as '降雨(mm)'
        FROM observations 
        WHERE station_id = '{station_id}'
        ORDER BY time DESC 
        LIMIT {limit}
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        print(f"\n❌ 未找到站点: {station_id}")
        return
    
    print(f"\n{'='*100}")
    print(f"站点 {station_id} 的最新 {limit} 条数据")
    print(f"{'='*100}")
    print(df.to_string(index=False))
    print(f"{'='*100}\n")

def view_summary():
    """查看数据摘要"""
    conn = sqlite3.connect('weather_stream.db')
    
    # 基本统计
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM observations")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT MIN(time), MAX(time) FROM observations")
    time_range = cursor.fetchone()
    
    # 各站点统计
    df = pd.read_sql_query("""
        SELECT 
            station_id as '站点', 
            COUNT(*) as '记录数',
            MIN(time) as '最早',
            MAX(time) as '最新'
        FROM observations 
        GROUP BY station_id
        ORDER BY COUNT(*) DESC
    """, conn)
    
    conn.close()
    
    print(f"\n{'='*100}")
    print("数据库摘要")
    print(f"{'='*100}")
    print(f"总记录数: {total}")
    print(f"时间范围: {time_range[0]} ~ {time_range[1]}")
    print(f"\n各站点统计:")
    print(f"{'-'*100}")
    print(df.to_string(index=False))
    print(f"{'='*100}\n")

def view_realtime():
    """查看实时数据（最新一个时刻所有站点）"""
    conn = sqlite3.connect('weather_stream.db')
    
    # 获取最新时间
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(time) FROM observations")
    latest_time = cursor.fetchone()[0]
    
    query = f"""
        SELECT 
            station_id as '站点',
            temp_out as '温度(°C)', 
            out_hum as '湿度(%)', 
            wind_speed as '风速(km/h)', 
            wind_dir_str as '风向',
            bar as '气压(hPa)', 
            rain as '降雨(mm)'
        FROM observations 
        WHERE time = '{latest_time}'
        ORDER BY station_id
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    print(f"\n{'='*100}")
    print(f"实时数据快照 ({latest_time})")
    print(f"{'='*100}")
    print(df.to_string(index=False))
    print(f"{'='*100}\n")

def list_stations():
    """列出所有站点"""
    conn = sqlite3.connect('weather_stream.db')
    
    df = pd.read_sql_query("""
        SELECT 
            station_id as '站点ID',
            station_name_en as '英文名',
            station_name_gr as '希腊文名',
            latitude as '纬度',
            longitude as '经度',
            elevation as '海拔(m)'
        FROM stations
        ORDER BY station_id
    """, conn)
    
    conn.close()
    
    print(f"\n{'='*100}")
    print("所有气象站信息")
    print(f"{'='*100}")
    print(df.to_string(index=False))
    print(f"{'='*100}\n")

def export_csv(filename='weather_export.csv'):
    """导出所有数据到CSV"""
    conn = sqlite3.connect('weather_stream.db')
    
    df = pd.read_sql_query("""
        SELECT o.*, s.latitude, s.longitude, s.elevation, s.station_name_en
        FROM observations o
        LEFT JOIN stations s ON o.station_id = s.station_id
        ORDER BY o.time DESC
    """, conn)
    
    conn.close()
    
    df.to_csv(filename, index=False)
    print(f"\n✅ 已导出 {len(df)} 条记录到 {filename}\n")

def main():
    parser = argparse.ArgumentParser(
        description='气象数据查看工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python view_data.py --latest 20          # 查看最新20条数据
  python view_data.py --station volos      # 查看volos站点数据
  python view_data.py --summary            # 查看数据摘要
  python view_data.py --realtime           # 查看实时快照
  python view_data.py --stations           # 列出所有站点
  python view_data.py --export data.csv    # 导出为CSV
        """
    )
    
    parser.add_argument('--latest', type=int, metavar='N', help='查看最新N条数据')
    parser.add_argument('--station', type=str, metavar='ID', help='查看特定站点数据')
    parser.add_argument('--summary', action='store_true', help='查看数据摘要')
    parser.add_argument('--realtime', action='store_true', help='查看实时数据快照')
    parser.add_argument('--stations', action='store_true', help='列出所有站点')
    parser.add_argument('--export', type=str, metavar='FILE', help='导出数据到CSV文件')
    
    args = parser.parse_args()
    
    # 如果没有参数，显示默认视图
    if not any(vars(args).values()):
        view_latest(20)
        return
    
    if args.latest:
        view_latest(args.latest)
    
    if args.station:
        view_station(args.station)
    
    if args.summary:
        view_summary()
    
    if args.realtime:
        view_realtime()
    
    if args.stations:
        list_stations()
    
    if args.export:
        export_csv(args.export)

if __name__ == '__main__':
    main()

