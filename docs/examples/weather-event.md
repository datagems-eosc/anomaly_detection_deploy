# Weather Event Example

## Scenario: Cold Front Passing Through

### Context

On November 20, 2025, a cold front moved through central Greece, causing temperatures to drop sharply across multiple stations.

### Detection Run

```bash
python anomaly_detector.py \
  --end "2025-11-20 14:00:00" \
  --window 6 \
  --temporal-method arima \
  --spatial-verify
```

### Console Output

```
═══════════════════════════════════════════════
 ANOMALY DETECTION REPORT
═══════════════════════════════════════════════
End Time: 2025-11-20 14:00:00
Window: 6 hours
Method: arima
Spatial Verification: Enabled

Total Stations: 14
Anomalous Stations: 4
Normal Stations: 10

Anomaly Breakdown:
  🔴 Device Failures: 0      <-- ✅ No hardware issues
  🌧️ Weather Events: 4       <-- 4 stations affected by cold front
  ⚠️ Suspected: 0

═══════════════════════════════════════════════
 DETAILED REPORTS
═══════════════════════════════════════════════

[ STATION: uth_volos (Volos - University) ]
  ⚠️  Temperature Anomaly:
      Method: arima
      Expected: 15.2°C | Actual: 10.1°C
      • 2025-11-20 14:00:00: 10.10°C -> 🌧️ Extreme Weather / Env Change
        └─ Diag: Trend Consistent (Corr: 0.89, 3 neighbors)

[ STATION: volos (Volos City) ]
  ⚠️  Temperature Anomaly:
      Method: arima
      Expected: 15.5°C | Actual: 10.3°C
      • 2025-11-20 14:00:00: 10.30°C -> 🌧️ Extreme Weather / Env Change
        └─ Diag: Trend Consistent (Corr: 0.92, 4 neighbors)

[ STATION: zagora (Zagora) ]
  ⚠️  Temperature Anomaly:
      Method: arima
      Expected: 12.8°C | Actual: 8.2°C
      • 2025-11-20 14:00:00: 8.20°C -> 🌧️ Extreme Weather / Env Change
        └─ Diag: Trend Consistent (Corr: 0.87, 2 neighbors)

[ STATION: larissa (Larissa) ]
  ⚠️  Temperature Anomaly:
      Method: arima
      Expected: 16.1°C | Actual: 11.4°C
      • 2025-11-20 14:00:00: 11.40°C -> 🌧️ Extreme Weather / Env Change
        └─ Diag: Trend Consistent (Corr: 0.91, 4 neighbors)

═══════════════════════════════════════════════
 NEIGHBOR COMPARISON - Station: uth_volos
═══════════════════════════════════════════════

Time                 | uth_volos | volos | zagora | larissa
---------------------|-----------|-------|--------|--------
2025-11-20 08:00:00  | 15.2      | 15.5  | 12.8   | 16.1
2025-11-20 08:30:00  | 15.1      | 15.4  | 12.7   | 16.0
2025-11-20 09:00:00  | 14.8      | 15.2  | 12.5   | 15.8
2025-11-20 09:30:00  | 14.4      | 14.9  | 12.1   | 15.4
2025-11-20 10:00:00  | 13.9      | 14.4  | 11.6   | 14.9
2025-11-20 10:30:00  | 13.2      | 13.7  | 10.9   | 14.2
2025-11-20 11:00:00  | 12.4      | 12.9  | 10.1   | 13.4
2025-11-20 11:30:00  | 11.6      | 12.1  | 9.4    | 12.7
2025-11-20 12:00:00  | 11.0      | 11.4  | 8.8    | 12.1
2025-11-20 12:30:00  | 10.5      | 10.9  | 8.5    | 11.7
2025-11-20 13:00:00  | 10.3      | 10.6  | 8.3    | 11.5
2025-11-20 13:30:00  | 10.2      | 10.4  | 8.2    | 11.4
2025-11-20 14:00:00  | 10.1 ⚠️   | 10.3  | 8.2    | 11.4

Observation: All stations show synchronized temperature drops
→ Classification: Weather Event (Cold Front)
```

### Analysis

#### Why Was This Classified as Weather Event?

1. **Multiple Stations Affected**: 4 out of 14 stations showed anomalies
2. **High Spatial Correlation**: Average correlation = 0.90 (> 0.6 threshold)
3. **Synchronized Timing**: All anomalies occurred at the same timestamp
4. **Similar Magnitude**: All stations dropped 4-5°C from expected

#### Spatial Correlation Details

```
Station Pair         | Correlation | Distance
---------------------|-------------|----------
uth_volos ↔ volos    | 0.98        | 3.2 km
uth_volos ↔ zagora   | 0.87        | 28.5 km
uth_volos ↔ larissa  | 0.82        | 62.4 km
volos ↔ larissa      | 0.94        | 65.1 km
```

All pairs show high correlation → Indicates regional weather pattern

### Time Series Visualization

#### Temperature Trend (6-hour window)

```
Temp (°C)
    17 ┤
    16 ┤●───╮
    15 ┤    ╰──╮
    14 ┤       ╰──╮
    13 ┤          ╰──╮
    12 ┤             ╰──╮
    11 ┤                ╰──╮
    10 ┤                   ●────●────● ← Anomaly detected
     9 ┤
       └─────────────────────────────
       08:00              14:00
```

**Pattern**: Smooth, consistent decline (typical of cold front passage)

### What Would Happen Without Spatial Verification?

```bash
# Without --spatial-verify flag
python anomaly_detector.py \
  --end "2025-11-20 14:00:00" \
  --temporal-method arima
```

**Result**: All 4 stations would be flagged as potential failures!

```
Anomaly Breakdown:
  🔴 Device Failures: 4      <-- ❌ FALSE ALARMS!
  🌧️ Weather Events: 0
  ⚠️ Suspected: 0
```

**Impact**: Operations team would waste time investigating 4 "failures" that are actually normal weather.

### Meteorological Context

#### Cold Front Characteristics

- **Front Speed**: ~30 km/h
- **Temperature Drop**: 5°C over 6 hours
- **Affected Radius**: ~100 km
- **Duration**: 8-12 hours

#### Station Positions Relative to Front

```
       N
       ↑
   zagora ●
         
larissa ● ← ← [COLD FRONT] → → → uth_volos ●
                                            volos ●
```

Front moved from west (larissa) to east (volos), causing sequential temperature drops.

### Actionable Insights

#### For Operations Teams

✅ **No action required** - This is normal weather

#### For Meteorologists

- Cold front passage confirmed by sensor network
- Front speed: ~30 km/h
- Can be used to validate weather models

#### For Researchers

- Example of successful dual-verification
- Spatial correlation accurately distinguished weather from failure
- System prevented 4 false alarm notifications

---

## Key Takeaways

1. **Spatial verification is critical** - Reduced false positives from 4 to 0
2. **High correlation (> 0.6) = Weather event** - Multiple stations show similar patterns
3. **Distance doesn't matter much** - Stations 60km apart still show 0.82 correlation
4. **ARIMA detected the anomaly** - But spatial verification classified it correctly

---

## Related Examples

- [Device Failure Example](device-failure.md) - Contrasting case with low correlation
- [Detection Methods](../system/detection-methods.md) - Technical details on ARIMA
- [Station Network](../system/station-network.md) - Map of station locations

