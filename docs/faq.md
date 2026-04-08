# Frequently Asked Questions

## General Questions

### What is the Real-Time Anomaly Detection system?

It's a tool that monitors weather stations and automatically distinguishes between genuine equipment failures and extreme weather events using temporal and spatial analysis.

### Who is this system for?

- Weather station operators
- Meteorological agencies
- Research institutions
- Infrastructure monitoring teams

### What makes this different from traditional anomaly detection?

Traditional systems can't tell the difference between a broken sensor and extreme weather - they just flag everything as anomalous. Our **dual-verification strategy** uses neighbor stations to classify anomalies correctly.

---

## Installation & Setup

### What are the system requirements?

- Python 3.8 or higher
- 512MB RAM (minimum), 2GB recommended
- 1GB disk space
- Linux or macOS (Windows may work but is untested)

### Do I need a database server?

No. By default, the system uses SQLite which is embedded in Python. For enterprise deployments (>100 stations), you can optionally use TimescaleDB.

### How do I install it?

```bash
git clone https://github.com/datagems-eosc/real-time-anomaly-detection.git
cd real-time-anomaly-detection/stream_detection
pip install -r requirements.txt
./manage_collector.sh start
```

See [Installation Guide](setup/installation.md) for details.

### Can I run this on Windows?

The system is primarily designed for Linux/macOS. Windows support is not officially tested, but you can try:

- Use WSL (Windows Subsystem for Linux)
- Run in Docker
- Use a Linux VM

---

## Detection & Configuration

### What detection methods are supported?

Seven temporal methods:

- **ARIMA** (recommended) - Best accuracy
- **3-Sigma** - Fastest
- **MAD** - Most robust
- **IQR** - Simple baseline
- **Isolation Forest** - ML-based
- **STL** - For seasonal data
- **LOF** - Density-based

See [Detection Methods](system/detection-methods.md) for comparisons.

### Which method should I use?

**For production**: ARIMA with spatial verification

```bash
python anomaly_detector.py --end "NOW" --temporal-method arima --spatial-verify
```

**For testing**: 3-Sigma (much faster)

```bash
python anomaly_detector.py --end "NOW" --temporal-method 3sigma
```

### How do I tune detection sensitivity?

Adjust thresholds based on your needs:

**More sensitive** (more detections):
```bash
--temporal-threshold 2.5  # Lower = more sensitive
--correlation-threshold-high 0.7  # Higher = stricter weather criteria
```

**Less sensitive** (fewer detections):
```bash
--temporal-threshold 3.5  # Higher = less sensitive
--correlation-threshold-high 0.5  # Lower = more lenient weather criteria
```

### What is spatial verification?

It compares the suspect station with nearby neighbors to determine if the anomaly is:

- **Weather event**: Neighbors show similar patterns (correlation > 0.6)
- **Device failure**: Only this station is anomalous (correlation < 0.3)

**Always use `--spatial-verify` in production** to reduce false positives by ~80%.

### How does the system handle missing data?

- **Temporal detection**: Skips missing points, requires minimum data density
- **Spatial verification**: Uses linear interpolation to fill small gaps (< 3 consecutive points)

### What if a station has no neighbors?

The system skips spatial verification for that station and marks anomalies as "Suspected" (requiring manual review).

---

## Performance & Scalability

### How fast is the detection?

| Method | Time (14 stations) | Time (100 stations) |
|--------|-------------------|---------------------|
| 3-Sigma | ~0.1 seconds | ~0.7 seconds |
| ARIMA | ~2 seconds | ~15 seconds |
| Isolation Forest | ~1 second | ~8 seconds |

### How much data does the system store?

Approximately **10MB per month** for 14 stations with 10-minute intervals using SQLite.

With TimescaleDB compression: **~3MB per month**.

### Can this scale to 1000 stations?

Yes, but you'll need:

1. **Switch to TimescaleDB** instead of SQLite
2. **Use parallel processing** (future feature)
3. **Consider distributed deployment** with multiple detection workers

See [Database Options](setup/database.md) for migration guide.

### How much memory does it use?

- **Collector**: ~50MB
- **Detector (6-hour window)**: ~200MB
- **Detector (24-hour window)**: ~500MB

Memory usage is constant regardless of total database size thanks to the sliding window mechanism.

---

## Troubleshooting

### Why am I getting "Insufficient data" errors?

The detector requires at least:

- 1 hour of data for simple methods (3-sigma, MAD, IQR)
- 6 hours for ARIMA (36 data points)
- 24 hours for STL (seasonal decomposition)

**Solution**: Wait for the collector to accumulate more data, or reduce `--window` size.

### Why are there so many false positives?

Most likely you're not using spatial verification. Run with:

```bash
python anomaly_detector.py --end "NOW" --spatial-verify
```

This reduces false positives by ~80%.

### Why does MAD report everything as anomalous?

MAD is very sensitive to stable data. If your baseline is flat (e.g., barometric pressure), MAD will flag small changes.

**Solution**: Use ARIMA or 3-Sigma for variables with stable baselines.

### The collector stopped working. How do I restart it?

```bash
# Check status
./manage_collector.sh status

# Restart
./manage_collector.sh restart

# Check logs
tail -f streaming_collector.log
```

### How do I check if data collection is working?

```bash
# Check database
sqlite3 weather_stream.db "SELECT COUNT(*) FROM observations;"

# Check recent data
sqlite3 weather_stream.db "SELECT MAX(time), COUNT(*) FROM observations WHERE time > datetime('now', '-1 hour');"
```

Expected: ~14 new records every 10 minutes (one per station).

### Detection is too slow. How do I speed it up?

1. **Use faster method**: Switch from ARIMA to 3-Sigma
2. **Reduce window size**: Use `--window 3` instead of 6
3. **Analyze fewer variables**: Use `--variables "temp_out"` instead of all
4. **Optimize database**: Run `VACUUM` on SQLite

---

## Data & Integration

### Where does the data come from?

National Observatory of Athens (NOA) via their DataGEMS GeoJSON feed:
https://stratus.meteo.noa.gr/data/stations/latestValues_Datagems.geojson

Updated every 10 minutes.

### Can I use my own data source?

Yes. Edit `streaming_collector_sqlite.py` to:

1. Change `API_URL` to your endpoint
2. Modify `parse_geojson()` to match your data format
3. Restart the collector

### How do I export data for analysis?

```bash
# Export to CSV
sqlite3 weather_stream.db <<EOF
.headers on
.mode csv
.output data_export.csv
SELECT * FROM observations WHERE time > '2025-11-01';
EOF
```

Or use the built-in tool:

```bash
python view_data.py --start "2025-11-01" --end "2025-11-30" --output export.csv
```

### Can I integrate this with Grafana/Prometheus?

Yes! See [API Examples](api/examples.md) for Prometheus exporter code.

Future releases will include native exporters.

### How do I get JSON output?

```bash
python anomaly_detector.py --end "NOW" --spatial-verify --save report.json
```

See [Response Format](api/response.md) for JSON schema.

---

## Best Practices

### How often should I run detection?

**Recommended**: Hourly

```bash
# Add to cron
0 * * * * cd /path/to/stream_detection && python anomaly_detector.py --end "NOW" --spatial-verify
```

More frequent (every 30 min) is fine, but provides diminishing returns since weather changes slowly.

### Should I always use spatial verification?

**Yes**, unless:

- You're just testing
- You only have isolated stations (no neighbors)
- You want to analyze historical data without neighbor context

Spatial verification is the core innovation of this system - don't skip it!

### What variables should I monitor?

**Priority 1** (most reliable for failure detection):
- `temp_out` (temperature)
- `bar` (barometric pressure)

**Priority 2** (useful but noisier):
- `out_hum` (humidity)
- `rain` (rainfall)

**Priority 3** (very noisy, many false positives):
- `wind_speed` (highly variable)

Start with temp and pressure, add others as needed.

### How do I reduce false alarms?

1. **Enable spatial verification** (most important!)
2. **Use ARIMA** instead of 3-Sigma/MAD
3. **Increase thresholds** slightly
4. **Exclude wind_speed** from analysis (too noisy)
5. **Tune correlation thresholds** based on your terrain

---

## Advanced Topics

### Can I add custom detection methods?

Yes. Implement the `TemporalDetector` interface:

```python
class MyCustomDetector(TemporalDetector):
    def is_anomalous(self, station_data, variable):
        # Your logic here
        return True  # if anomalous
```

See the source code for examples.

### Can I adjust parameters per variable?

Currently, parameters are global. Per-variable configuration is a planned feature.

Workaround: Run detection separately for each variable:

```bash
python anomaly_detector.py --variables "temp_out" --temporal-threshold 3.0
python anomaly_detector.py --variables "wind_speed" --temporal-threshold 4.0
```

### How do I migrate from SQLite to TimescaleDB?

See the complete guide: [Database Migration](setup/database.md#migration-from-sqlite-to-timescaledb)

Summary:
1. Export SQLite to CSV
2. Create TimescaleDB hypertable
3. Import CSV
4. Update connection string
5. Restart services

### Can I run this as a REST API?

Not yet, but the system is designed to support it. A future release will include a Flask/FastAPI wrapper.

Current workaround: Call via subprocess and parse JSON output.

---

## Support & Contribution

### Where can I report bugs?

GitHub Issues: https://github.com/datagems-eosc/real-time-anomaly-detection/issues

### How do I contribute?

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

See CONTRIBUTING.md (coming soon) for guidelines.

### Is there a user community?

We're building one! Join the discussion:

- GitHub Discussions (coming soon)
- Mailing list (coming soon)

### Can I use this for commercial purposes?

Yes, the system is open-source under [LICENSE]. Check the license file for details.

---

## Still Have Questions?

- Read the [Overview](index.md) for system introduction
- Check [API Documentation](api/overview.md) for parameter details
- Browse [Code Examples](api/examples.md) for common use cases
- Review [Detection Methods](system/detection-methods.md) for algorithm details

If your question isn't answered, open a GitHub issue or contact the development team.

