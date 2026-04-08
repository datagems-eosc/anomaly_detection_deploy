#!/bin/bash
# Data collection and database tests

cd "$(dirname "$0")/.."

echo "📊 Data Collection Tests"
echo ""

# Check database
echo "1. Database status..."
if [ -f "weather_stream.db" ]; then
    echo "   ✅ Found ($(du -h weather_stream.db | cut -f1))"
else
    echo "   ❌ Not found"
    exit 1
fi

# Check data freshness
echo -e "\n2. Data freshness..."
python3 << 'EOF'
import sqlite3, pandas as pd
from datetime import datetime
conn = sqlite3.connect('weather_stream.db')
df = pd.read_sql_query('SELECT MAX(time) as t, COUNT(*) as n FROM observations', conn)
conn.close()
latest = pd.to_datetime(df['t'].iloc[0])
age = (datetime.now() - latest).total_seconds() / 60
print(f"   Latest: {latest.strftime('%Y-%m-%d %H:%M')}")
print(f"   Age: {age:.1f} min | Records: {df['n'].iloc[0]:,}")
print(f"   {'✅ Fresh' if age < 15 else '⚠️ Stale'}")
EOF

# Check collector
echo -e "\n3. Collector status..."
if pgrep -f "streaming_collector_sqlite.py" > /dev/null; then
    echo "   ✅ Running (PID: $(pgrep -f streaming_collector_sqlite.py))"
else
    echo "   ⚠️ Not running (start: ./manage_collector.sh start)"
fi

# Check stations
echo -e "\n4. Station coverage..."
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('weather_stream.db')
stations = [r[0] for r in conn.execute('SELECT DISTINCT station_id FROM observations').fetchall()]
conn.close()
print(f"   {len(stations)} stations: {', '.join(stations[:5])}...")
EOF



